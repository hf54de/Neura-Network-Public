"""Isolated tests for permanent run numbers and the editable training protocol."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QMessageBox, QPlainTextEdit, QDialogButtonBox
from _test_review_fixes import APP, ROOT, language, network, document, entry, window
from settings import Settings
from mainwindow import MainWindow
from trainingdialog import TrainingDialog
from traininghistorydialog import TrainingHistoryDialog
from trainingprotocol import TrainingProtocol, write_text_atomic
from trainingdataio import TrainingDataIO
from projectio import ProjectIO


class ProtocolStorageTests(unittest.TestCase):
    def test_notes_append_copy_reopen_and_conflict(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".protocol_test_") as directory:
            root = Path(directory)
            journal = TrainingProtocol(language("de"))
            journal.add("TRAINING GESTARTET · Lauf 7", ["Lernrate: 0,01"])
            journal.flush(root / "trainingsprotokoll.txt")
            original = journal.text()
            journal.replace(original, original + "Eigene Notiz: gut.\n\n")
            journal.add("TRAINING BEENDET · Lauf 7", ["MSE: 0,2 → 0,01"])
            self.assertIn("Eigene Notiz", journal.text())
            journal.flush(root / "copy.txt")
            other = TrainingProtocol(language("de"), root / "copy.txt")
            self.assertEqual(other.text(), journal.text())
            old = other.text()
            other.path.write_text(old + "Extern ergänzt\n", encoding="utf-8")
            with self.assertRaises(OSError): other.replace(old, "overwrite")
            self.assertIn("Extern ergänzt", other.text())

    def test_failed_write_preserves_file_and_retries_pending_entries(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".protocol_test_") as directory:
            path = Path(directory) / "log.txt"
            path.write_text("Original\n", encoding="utf-8")
            journal = TrainingProtocol(language("en"), path)
            with patch("trainingprotocol.os.replace", side_effect=OSError("failure")):
                with self.assertRaises(OSError): journal.add("Run 4", ["Result"])
            self.assertEqual(path.read_text(encoding="utf-8"), "Original\n")
            self.assertIn("Run 4", journal.pending)
            journal.flush()
            self.assertEqual(journal.text().count("Run 4"), 1)

    def test_temporary_windows_denial_retries_without_duplicate_entries(self):
        import os
        original_replace = os.replace
        for code in (5, 32, 33):
            with self.subTest(winerror=code), tempfile.TemporaryDirectory(dir=ROOT, prefix=".protocol_test_") as directory:
                path = Path(directory) / "log.txt"
                path.write_text("Original\n", encoding="utf-8")
                journal = TrainingProtocol(language("de"), path)
                denied = PermissionError("Temporary Windows access denial")
                denied.winerror = code
                calls = []
                def replace(source, target):
                    calls.append(source)
                    if len(calls) < 3:
                        self.assertEqual(path.read_text(encoding="utf-8"), "Original\n")
                        raise denied
                    original_replace(source, target)
                with patch("trainingprotocol.os.replace", side_effect=replace), patch("trainingprotocol.time.sleep") as sleep:
                    journal.add("Optimierungsverfahren: Adam → SGD", [])
                self.assertEqual(len(calls), 3)
                self.assertEqual(sleep.call_count, 2)
                self.assertEqual(journal.pending, "")
                self.assertEqual(journal.text().count("Adam → SGD"), 1)
                self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_persistent_windows_denial_is_bounded_and_keeps_pending(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".protocol_test_") as directory:
            path = Path(directory) / "log.txt"
            path.write_text("Original\n", encoding="utf-8")
            journal = TrainingProtocol(language("de"), path)
            denied = PermissionError("Persistent Windows access denial")
            denied.winerror = 5
            with patch("trainingprotocol.os.replace", side_effect=denied) as replace, patch("trainingprotocol.time.sleep") as sleep:
                with self.assertRaises(PermissionError):journal.add("Adam → SGD", [])
            self.assertEqual(replace.call_count, 5)
            self.assertEqual(sleep.call_count, 4)
            self.assertEqual(path.read_text(encoding="utf-8"), "Original\n")
            self.assertIn("Adam → SGD", journal.pending)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
            journal.flush()
            self.assertEqual(journal.text().count("Adam → SGD"), 1)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows sharing semantics")
    def test_real_windows_file_lock_is_retried(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".protocol_test_") as directory:
            path = Path(directory) / "log.txt"
            path.write_text("Original\n", encoding="utf-8")
            handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            try:
                def release(_delay):
                    nonlocal handle
                    self.assertEqual(path.read_text(encoding="utf-8"), "Original\n")
                    self.assertTrue(kernel.CloseHandle(handle));handle=None
                with patch("trainingprotocol.time.sleep", side_effect=release) as sleep:
                    write_text_atomic(path, "Saved after unlocking\n")
                self.assertEqual(sleep.call_count, 1)
                self.assertEqual(path.read_text(encoding="utf-8"), "Saved after unlocking\n")
            finally:
                if handle is not None:kernel.CloseHandle(handle)

    def test_history_keeps_gaps_and_parent_identifiers(self):
        host = window()
        runs = [entry(host, 2), entry(host, 7), entry(host, 10)]
        runs[2]["parent_run_id"] = 7
        dialog = TrainingHistoryDialog(runs, language_manager=language("en"),
                                       restorable_run_ids={2, 7, 10}, active_run_id=10)
        try:
            self.assertEqual([r["run_id"] for r in dialog.training_history], [2, 7, 10])
            with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
                dialog.delete_selected_runs(run_id=10)
            self.assertEqual([r["run_id"] for r in dialog.training_history], [2, 7])
            self.assertEqual(dialog.restore_run_id, 7)
            self.assertEqual(runs[2]["parent_run_id"], 7)
        finally:
            APP.processEvents(); dialog.deleteLater()


class ProtocolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix=".protocol_test_")
        self.root = Path(self.temp.name)
        self.settings_patch = patch.object(Settings, "get_settings_path", return_value=self.root / "settings.json")
        self.settings_patch.start()
        ui = dict(Settings.default_ui_settings(), project_directory=str(self.root), language="de")
        with patch.object(Settings, "get_ui_settings", return_value=ui), patch.object(Settings, "restore_window", return_value=False):
            self.w = MainWindow(defer_initial_show=True)
        APP.processEvents()
        self.w.reset_project()
        net = network()
        self.w.scene.network = net
        for n in net.get_neurons(): self.w.scene.addItem(n)
        for c in net.get_connections(): self.w.scene.addItem(c)
        self.file = self.root / "Demo.nnproj"
        self.w.current_project_path = str(self.file)
        self.data_path = self.root / "trainingsdaten.nndata"
        TrainingDataIO.save(self.data_path, document())
        self.w.training_data_manager.set_document(document(), file_path=str(self.data_path))
        self.w.initialize_training_protocol()
        self.dialog = None

    def tearDown(self):
        APP.processEvents()
        if self.dialog is not None: self.dialog.deleteLater()
        self.w._history_timer.stop()
        self.w.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
        self.settings_patch.stop()
        self.temp.cleanup()

    def test_adam_to_sgd_logs_once_after_temporary_windows_denial(self):
        import os
        settings = dict(self.w.training_settings, solver="adam", learning_rate=.001)
        self.dialog = TrainingDialog(self.w.scene.network, document(), parent=self.w,
            training_settings=settings, language_manager=self.w.language)
        self.w.training_dialog = self.dialog
        self.dialog.training_completed.connect(self.w.training_step_completed)
        self.dialog.execute_training(1, False, shuffle_seed=42)
        parent_run = self.dialog.current_run_id
        self.dialog.solver_combo.setCurrentIndex(self.dialog.solver_combo.findData("sgd"))
        original_replace = os.replace
        failures = []
        def replace(source, target):
            if Path(target).name == "trainingsprotokoll.txt" and len(failures) < 2:
                failures.append(target)
                denied = PermissionError("Temporary Windows access denial")
                denied.winerror = 5
                raise denied
            return original_replace(source, target)
        with patch("trainingprotocol.os.replace", side_effect=replace), patch("trainingprotocol.time.sleep"), patch.object(QMessageBox, "warning") as warning:
            self.dialog.execute_training(1, False, continue_existing=True)
            warning.assert_not_called()
        self.assertEqual(len(failures), 2)
        self.assertEqual(self.dialog.current_run_parent_id, parent_run)
        self.assertEqual(self.w.scene.network.get_solver(), "sgd")
        self.assertEqual(self.w.training_history[-1]["solver"], "sgd")
        self.assertEqual(self.w.training_protocol.pending, "")
        self.assertEqual(self.w.training_protocol.path.read_text(encoding="utf-8").count("Adam → SGD mit Momentum"), 1)

    def test_changes_manual_editor_and_no_duplicate_entries(self):
        w = self.w
        baseline = w.training_protocol.text()
        self.assertEqual(baseline, "")
        self.assertFalse(w.training_protocol.path.exists())
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.training_settings["learning_rate"] = 0.123
        doc = document(); doc["records"][1][1] = .8
        doc["columns"][0]["calibration"]["source_max"] = 5
        w.training_data_manager.set_document(doc, file_path=str(self.data_path))
        w.protocol_checkpoint()
        text = w.training_protocol.text()
        self.assertIn("Tanh → Sigmoid", text)
        self.assertIn("0,123", text)
        self.assertIn("Datenwerte geändert", text)
        w.protocol_checkpoint(); self.assertEqual(text, w.training_protocol.text())
        errors = []
        def edit():
            try:
                dlg = APP.activeModalWidget()
                box = dlg.findChild(QPlainTextEdit)
                self.assertLess(dlg.width(), 900)
                self.assertLessEqual(dlg.width(), w.screen().availableGeometry().width() - 40)
                box.setPlainText(box.toPlainText() + "\nEigene Notiz\n")
                dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
            except BaseException as error:
                errors.append(error); APP.activeModalWidget().reject()
        QTimer.singleShot(20, edit)
        w.open_training_protocol()
        if errors: raise errors[0]
        self.assertIn("Eigene Notiz", w.training_protocol.text())
        self.assertTrue(w.training_protocol.text().startswith(baseline))

    def test_real_training_delete_save_reload_and_next_number(self):
        w = self.w
        self.dialog = TrainingDialog(w.scene.network, document(), parent=w, language_manager=w.language)
        w.training_dialog = self.dialog
        self.dialog.training_completed.connect(w.training_step_completed)
        with patch.object(QMessageBox, "warning") as warning:
            self.dialog.execute_training(2, False)
            warning.assert_not_called()
        self.assertEqual(len(w.training_history), 1)
        for line in self.dialog.workload_label.text().splitlines():
            self.assertIn(line, w.training_protocol.text())
        self.assertEqual(w.last_training_run_id, 1)
        self.assertEqual(self.dialog.error_chart.run_id, 1)
        self.assertNotIn("TRAINING GESTARTET", w.training_protocol.text())
        self.assertNotIn("TRAINING BEENDET", w.training_protocol.text())
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.delete_current_training_run()
        self.assertEqual(w.training_history, [])
        self.assertIsNone(self.dialog.error_chart.run_id)
        self.assertEqual(self.dialog.next_training_run_id, 2)
        self.assertIn("TRAININGSLAUF GELÖSCHT · Lauf 1", w.training_protocol.text())
        w.training_dialog = None
        self.assertTrue(w.write_project_file(str(self.file)))
        stored = json.loads(self.file.read_text(encoding="utf-8"))
        self.assertEqual(stored["last_training_run_id"], 1)
        self.assertEqual(stored["training_history"], [])
        before = w.training_protocol.text()
        w.project_modified = False
        w.open_project(str(self.file))
        self.assertEqual(w.last_training_run_id, 1)
        self.assertEqual(w.training_protocol.text(), before)
        self.assertEqual(w.reserve_training_run_id(), 2)
        w.training_history = []
        self.assertEqual(w.reserve_training_run_id(), 3)

    def test_resume_after_reopen_only_records_actual_parameter_changes(self):
        w = self.w
        w.training_settings["weight_initialization"] = "xavier"
        w.training_protocol.baseline = w.protocol_state()
        self.dialog = TrainingDialog(w.scene.network, document(), parent=w,
                                     training_settings=w.training_settings, language_manager=w.language)
        w.training_dialog = self.dialog
        self.assertEqual(self.dialog.weight_initialization_combo.currentData(), "xavier")
        self.dialog.training_completed.connect(w.training_step_completed)
        self.dialog.execute_training(2, False)
        original = w.training_protocol.text()
        self.assertIn("NEUER TRAININGSLAUF · Lauf 1", original)
        self.assertEqual(original.count("=" * 56), 2)
        saved_epochs = self.dialog.current_run_completed_epochs
        saved_id = self.dialog.current_run_id
        w.training_dialog = None
        self.assertTrue(w.write_project_file(str(self.file)))
        self.dialog.deleteLater(); APP.processEvents()
        self.dialog = None
        w.project_modified = False
        w.open_project(str(self.file))
        w.open_training_dialog()
        self.dialog = w.training_dialog
        self.assertIsNotNone(self.dialog)
        self.assertEqual(self.dialog.current_run_id, saved_id)
        self.assertTrue(self.dialog.current_run_can_continue)
        self.dialog.continue_selected_training()
        self.assertEqual(self.dialog.current_run_id, saved_id)
        self.assertGreater(self.dialog.current_run_completed_epochs, saved_epochs)
        updated = w.training_protocol.text()
        self.assertEqual(updated.count("=" * 56), 2)
        self.assertEqual(updated.count("Ergebnis:"), 1)
        self.assertIn("Epochen: " + str(self.dialog.current_run_completed_epochs), updated)
        # A real parameter edit creates exactly one change event.
        self.dialog.learning_rate.setValue(0.123)
        w.protocol_training_started(self.dialog, True)
        changed = w.training_protocol.text()
        self.assertIn("0,123", changed)
        self.assertEqual(changed.count("-" * 56), 1)
        w.protocol_training_started(self.dialog, True)
        self.assertEqual(w.training_protocol.text(), changed)

    def test_delete_and_load_only_logs_deletion_and_loaded_run(self):
        w = self.w
        w.training_history = [entry(w, 1), entry(w, 2)]
        w.training_history[0]["learning_rate"] = 0.125
        w.active_training_run_id = 2
        w.last_training_run_id = 2
        w._protocol_runs = list(w.training_history)
        before = w.training_protocol.text()
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
            restored = w.open_training_history(delete_run_id=2)
        self.assertEqual(restored["run_id"], 1)
        self.assertEqual(w.training_settings["learning_rate"], 0.125)
        w.protocol_checkpoint()
        added = w.training_protocol.text()[len(before):]
        self.assertIn("TRAININGSLAUF GELÖSCHT · Lauf 2", added)
        self.assertIn("Lauf 1 geladen", added)
        self.assertNotIn("Trainingsparameter geändert", added)
        self.assertEqual(added.count("-" * 56), 2)

    def test_new_run_parameters_and_targets_in_both_languages(self):
        from types import SimpleNamespace
        for code in ("de", "en"):
            w = self.w
            w.language = language(code)
            w.training_protocol = TrainingProtocol(w.language)
            for target in ("one", "epochs", "limit"):
                settings = dict(w.training_settings, weight_initialization="he", bias_initialization="xavier",
                                learning_rate=0.005, momentum=0.8, error_limit=0.001, maximum_epochs=10000,
                                training_target_mode=target, training_section_epochs=25)
                w.training_settings = settings
                w.training_protocol.baseline = w.protocol_state()
                dialog = SimpleNamespace(current_run_id=4, current_run_initialized=True,
                                         get_training_settings=lambda: settings,
                                         workload_label=SimpleNamespace(text=lambda: "Network: 1 → 1 → 1\nParameters: 4 (2 W + 2 B)\nOperations: approx. 12 per epoch"))
                before = w.training_protocol.text()
                w.protocol_training_started(dialog, False)
                added = w.training_protocol.text()[len(before):]
                self.assertIn("He", added)
                self.assertIn("Xavier/Glorot", added)
                self.assertIn("0,005" if code == "de" else "0.005", added)
                self.assertIn("0,8" if code == "de" else "0.8", added)
                self.assertIn("0,001" if code == "de" else "0.001", added)
                self.assertIn("10000", added)
                self.assertIn(w.language.text("training.view.target_" + target, epochs=25), added)
                self.assertEqual(added.count("=" * 56), 2)
                lines = added.splitlines()
                self.assertEqual(lines[2], w.language.text("protocol.new_run", run=4))
                self.assertRegex(lines[1], r"^\d{2}\.\d{2}\.\d{4} · \d{2}:\d{2}:\d{2}$")
                self.assertEqual(lines[3], w.language.text("adam.solver.label") + " " + w.language.text("adam.solver.sgd"))
                self.assertEqual(lines[4:7], dialog.workload_label.text().splitlines())
                self.assertEqual(len(lines[7:15]), 8)
                for line, key in zip(lines[7:14], ("training.initialization.weights", "training.initialization.bias",
                        "protocol.run_reinitialize", "protocol.param.learning_rate", "protocol.param.momentum",
                        "protocol.param.error_limit", "protocol.param.maximum_epochs")):
                    self.assertTrue(line.startswith(w.language.text(key)))

                dialog.current_run_parent_id = 3
                before_parent = w.training_protocol.text()
                w.protocol_training_started(dialog, False)
                parent_entry = w.training_protocol.text()[len(before_parent):]
                self.assertIn(w.language.text("protocol.new_run", run=4), parent_entry.splitlines()[2])
                self.assertEqual(parent_entry.splitlines()[3], w.language.text("protocol.parent_run_suffix", run=3))
                self.assertEqual(parent_entry.splitlines()[4:16], lines[3:15])
                self.assertNotIn(w.language.text("protocol.parent_run_suffix", run=3), added)
                after = w.training_protocol.text()
                w.protocol_training_started(dialog, True)
                self.assertEqual(after, w.training_protocol.text())

    def test_legacy_long_lines_do_not_widen_protocol_window(self):
        w = self.w
        w.training_protocol.pending = "Long old heading " * 20 + "\n" + "=" * 56
        errors = []
        def inspect():
            dlg = APP.activeModalWidget()
            try:
                editor = dlg.findChild(QPlainTextEdit)
                margins = dlg.layout().contentsMargins()
                maximum = (editor.fontMetrics().horizontalAdvance("=" * 56)
                           + 2 * editor.frameWidth() + 2 * editor.document().documentMargin()
                           + editor.verticalScrollBar().sizeHint().width()
                           + margins.left() + margins.right() + 3)
                self.assertLessEqual(dlg.width(), maximum)
                self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
            except BaseException as error: errors.append(error)
            finally: dlg.reject()
        QTimer.singleShot(20, inspect)
        w.open_training_protocol()
        if errors: raise errors[0]

    def test_result_events_update_one_section_and_preserve_notes(self):
        w = self.w
        for code in ("de", "en"):
            w.language = language(code)
            w.training_protocol = TrainingProtocol(w.language)
            title = w.language.text("protocol.new_run", run=4)
            w.protocol_add(title, ["Momentum: 0,4", "Manual note"], highlighted=True)
            for stopped, error, key in ((True, .2, "protocol.result_stopped"),
                                        (False, .0001, "protocol.result_limit"),
                                        (False, .2, "protocol.result_epochs_limit")):
                run = dict(run_id=4, training_stopped=stopped, stop_at_error_limit=True,
                           end_error=error, error_limit=.001, completed_epochs=25,
                           maximum_absolute_error=.023, elapsed_seconds=12.5)
                w.protocol_training_result(run)
                text = w.training_protocol.text()
                self.assertEqual(text.count("=" * 56), 2)
                self.assertEqual(text.count(w.language.text("protocol.result") + ":"), 1)
                self.assertIn(w.language.text(key), text)
                self.assertIn("Manual note", text)
                self.assertIn("Momentum: 0,4", text)
                self.assertEqual(text.count("MSE:"), 1)
                maximum_label = w.language.text("protocol.result_maximum") + ":"
                self.assertEqual(text.count(maximum_label), 1)
                result_lines = text.splitlines()
                mse_index = next(i for i, line in enumerate(result_lines) if line.startswith("MSE:"))
                self.assertTrue(result_lines[mse_index + 1].startswith(maximum_label))

                elapsed_label = w.language.text("training.result.elapsed")
                epoch_label = w.language.text("protocol.result_epoch_time") + ":"
                self.assertEqual(text.count(elapsed_label), 1)
                self.assertEqual(text.count(epoch_label), 1)
                self.assertIn("12,5 s" if code == "de" else "12.5 s", text)
                self.assertIn("500 ms", text)
            run.update(completed_epochs=50, elapsed_seconds=20.)
            w.protocol_training_result(run)
            text = w.training_protocol.text()
            self.assertIn(elapsed_label + " 20 s", text)
            self.assertIn(epoch_label + " 400 ms", text)
            self.assertEqual(text.count(epoch_label), 1)
            run.update(completed_epochs=0)
            w.protocol_training_result(run)
            self.assertIn(epoch_label + " —", w.training_protocol.text())


    def test_counter_is_not_undone_and_structure_changes_are_logged(self):
        w = self.w
        snap = w.capture_editor_snapshot()
        self.assertEqual(w.reserve_training_run_id(), 1)
        w.scene.network.get_neuron(2).name = "Hidden changed"
        w.protocol_checkpoint()
        w.restore_editor_snapshot(snap)
        self.assertEqual(w.reserve_training_run_id(), 2)
        self.assertIn("Netzwerkstruktur geändert", w.training_protocol.text())


if __name__ == "__main__":
    unittest.main()
