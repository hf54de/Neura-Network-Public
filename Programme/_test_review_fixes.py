"""Gezielte Regressionstests für die vereinbarten Reviewpunkte 1–4 und 6.

Alle temporären Dateien bleiben im Quellcodeordner. Kein Start der Anwendung,
keine persönlichen Einstellungen, kein Zugriff auf Beispielprojekte.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import math
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from atomicjson import write_json_atomic
from connection import Connection
from graphicalexperimentdialog import GraphicalExperimentDialog
from language import LanguageManager
from mainwindow import MainWindow
from network import NeuralNetwork
from neuron import Neuron
from neurontype import NeuronType
from projectio import ProjectIO
from trainingdataio import TrainingDataIO
from trainingdatamanager import TrainingDataManager
from trainingdialog import TrainingDialog
from traininghistorydialog import TrainingHistoryDialog
from trainingvalidity import data_signature, training_context, invalidate_history

ROOT = Path(__file__).resolve().parent
APP = QApplication.instance() or QApplication([])


def language(code):
    return LanguageManager(code, ROOT / "languages.json")


def network(code="de"):
    net = NeuralNetwork(translator=language(code).text)
    for identifier, kind in [(1, NeuronType.INPUT), (2, NeuronType.HIDDEN), (3, NeuronType.OUTPUT)]:
        n = Neuron(identifier, identifier * 220, 0, f"N{identifier}")
        n.neuron_type = kind
        n.activation_function = "Linear" if kind != NeuronType.HIDDEN else "Tanh"
        net.add_neuron(n)
    net.add_connection(Connection(1, net.get_neuron(1), net.get_neuron(2), 0.2))
    net.add_connection(Connection(2, net.get_neuron(2), net.get_neuron(3), 0.3))
    return net


def document():
    doc = TrainingDataIO.create_empty_document(1, 1, "Test")
    doc["columns"][0]["mapped_neuron_id"] = 1
    doc["columns"][1]["mapped_neuron_id"] = 3
    doc["records"] = [[0.0, 0.0], [1.0, 1.0]]
    return doc


def window(net=None, doc=None):
    net = net or network()
    manager = TrainingDataManager(language_manager=language("de"))
    manager.set_document(doc or document(), file_path=str(ROOT / "test.nndata"))
    w = SimpleNamespace(scene=SimpleNamespace(network=net), training_data_manager=manager,
                        training_history=[], _invalidated_training_runs={},
                        active_training_run_id=None, project_modified=False, _history_restoring=False)
    for name in ("current_training_context", "refresh_training_history_validity",
                 "training_run_matches_active_data", "active_training_history_entry",
                 "capture_training_network_state", "training_network_state_is_compatible"):
        setattr(w, name, getattr(MainWindow, name).__get__(w))
    return w


def entry(w, run_id=1):
    return dict(run_id=run_id, timestamp="2026-10-14T12:00:00", training_data="Test",
                initialized=True, weight_initialization="xavier", bias_initialization="zero",
                learning_rate=0.01, momentum=0.0, error_limit=0.01, requested_epochs=2,
                completed_epochs=2, start_error=0.2, end_error=0.1, maximum_absolute_error=0.3,
                elapsed_seconds=0.1, status_text="OK", stop_at_error_limit=False,
                training_stopped=False, curve_points=[[1, 0.2], [2, 0.1]],
                network_state=w.capture_training_network_state(), continuable=True,
                training_context=w.current_training_context())


def project(edges):
    d = dict(version=ProjectIO.PROJECT_VERSION, neurons=[
        dict(id=i, name=f"N{i}", type=kind.value, bias=0.0, activation="Linear",
             input_value=0.0, target_value=0.0, x=0.0, y=0.0)
        for i, kind in [(1, NeuronType.INPUT), (2, NeuronType.HIDDEN),
                        (3, NeuronType.HIDDEN), (4, NeuronType.OUTPUT)]
    ], connections=[dict(id=i+1, source=a, target=b, weight=0.5)
                    for i, (a,b) in enumerate(edges)])
    ProjectIO._prepare_project_data(d)
    return d


class ReviewFixTests(unittest.TestCase):
    def test_invalid_topologies_rejected_in_both_languages(self):
        for code in ("de", "en"):
            for edges in ([(2,2)], [(4,2)], [(2,1)], [(2,3),(3,2)]):
                with self.subTest(code=code, edges=edges):
                    with self.assertRaises(ValueError) as error:
                        ProjectIO._validate_project_data(project(edges), language(code).text)
                    self.assertIn("unverändert" if code == "de" else "unchanged", str(error.exception))

    def test_incomplete_and_valid_projects_remain_loadable(self):
        for edges in ([], [(1,2)], [(1,2),(2,3),(3,4)]):
            ProjectIO._validate_project_data(project(edges), language("en").text)

    def test_invalid_project_does_not_reset_current_project(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="review_test_") as directory:
            self.assertEqual(Path(directory).resolve().parent, ROOT)
            path = Path(directory) / "invalid.nnproj"
            path.write_text(json.dumps(project([(2,3),(3,2)])), encoding="utf-8")
            w = SimpleNamespace(confirm_unsaved_changes=lambda: True,
                                language=language("en"), reset_project=Mock())
            with patch("mainwindow.QMessageBox.critical") as warning:
                self.assertFalse(MainWindow.open_project(w, str(path)))
            w.reset_project.assert_not_called()
            warning.assert_called_once()

    def test_activation_change_invalidates_every_old_run(self):
        w = window()
        w.training_history = [entry(w,1), entry(w,2)]
        w.active_training_run_id = 2
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.refresh_training_history_validity()
        self.assertIsNone(w.active_training_run_id)
        self.assertIsNone(w.active_training_history_entry())
        for run in w.training_history:
            self.assertEqual(run["invalidated_reason"], "activation")
            self.assertFalse(run["continuable"])
            self.assertFalse(w.training_network_state_is_compatible(run["network_state"]))

    def test_reverting_activation_does_not_reenable_runs(self):
        w = window(); w.training_history = [entry(w)]
        before = deepcopy(w.training_history)
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.refresh_training_history_validity()
        w.scene.network.get_neuron(2).activation_function = "Tanh"
        w.training_history = before  # also covers editor undo
        self.assertIsNone(w.active_training_history_entry())
        self.assertEqual(w.training_history[0]["invalidated_reason"], "activation")

    def test_new_training_after_invalidation_is_allowed(self):
        w = window(); w.training_history = [entry(w)]
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.refresh_training_history_validity()
        fresh = entry(w,2); w.training_history.append(fresh)
        self.assertIs(w.active_training_history_entry(), fresh)

    def test_data_values_scaling_and_assignment_invalidate(self):
        for kind in ("input", "target", "scaling", "mapping"):
            with self.subTest(kind=kind):
                w=window(); w.training_history=[entry(w)]; w.active_training_run_id=1
                d=w.training_data_manager.document
                if kind == "input": d["records"][1][0]=0.7
                elif kind == "target": d["records"][1][1]=0.4
                elif kind == "scaling": d["columns"][0]["calibration"]["mode"]="minmax_minus1_1"
                else: d["columns"][0]["mapped_neuron_id"]=2
                w.training_data_manager.set_document(d)
                self.assertIsNone(w.active_training_history_entry())
                self.assertEqual(w.training_history[0]["invalidated_reason"],"data")
                self.assertIsNone(w.active_training_run_id)

    def test_rename_move_and_metadata_do_not_invalidate(self):
        w=window(); run=entry(w); w.training_history=[run]
        d=w.training_data_manager.document
        d["name"]="Renamed"; d["data_origin"]="empirical"
        d["columns"][0]["name"]="Renamed input"
        w.training_data_manager.set_document(d,file_path=str(ROOT / "moved" / "renamed.nndata"))
        self.assertIs(w.active_training_history_entry(),run)

    def test_same_filename_different_data_does_not_match(self):
        w=window(); w.training_history=[entry(w)]
        d=w.training_data_manager.document;d["records"]=[[1.0,9.0]]
        w.training_data_manager.set_document(d,file_path=str(ROOT / "other" / "test.nndata"))
        self.assertIsNone(w.active_training_history_entry())

    def test_legacy_history_gets_baseline_then_invalidates(self):
        w=window(); run=entry(w); del run["training_context"]
        for n in run["network_state"]["neurons"]: n.pop("activation")
        w.training_history=[run]
        self.assertIs(w.active_training_history_entry(),run)
        w.scene.network.get_neuron(2).activation_function="ReLU"
        self.assertIsNone(w.active_training_history_entry())

    def test_invalidated_history_survives_json_and_renumbering(self):
        w=window(); w.training_history=[entry(w,7)]
        w.scene.network.get_neuron(2).activation_function="Sigmoid"
        w.refresh_training_history_validity()
        w.training_history=json.loads(json.dumps(w.training_history))
        w.training_history[0]["run_id"]=1
        w._invalidated_training_runs={}
        w.scene.network.get_neuron(2).activation_function="Tanh"
        self.assertIsNone(w.active_training_history_entry())
        ProjectIO._validate_training_history_data(w.training_history)

    def test_history_dialog_labels_and_blocks_invalid_runs(self):
        for code in ("de", "en"):
            w=window(); run=entry(w); run["invalidated_reason"]="data"; run["continuable"]=False
            dialog=TrainingHistoryDialog([run], language_manager=language(code), restorable_run_ids={1})
            try:
                dialog.table.selectRow(0); dialog.update_chart_selection()
                self.assertFalse(dialog.restore_button.isEnabled())
                self.assertIn("Ungültig" if code=="de" else "Invalid",dialog.table.item(0,0).text())
                dialog.request_restore_selected_run()
                self.assertIsNone(dialog.restore_run_id)
            finally: dialog.deleteLater()

    def test_delete_active_run_does_not_restore_invalid_fallback(self):
        w=window(); bad=entry(w,1);bad["invalidated_reason"]="data";good=entry(w,2)
        dialog=TrainingHistoryDialog([bad,good],language_manager=language("en"),restorable_run_ids={2},active_run_id=2)
        try:
            dialog.table.selectRow(0)
            # Test the deletion path with a confirmed answer, without opening a box.
            from PySide6.QtWidgets import QMessageBox
            with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.Yes):
                dialog.delete_selected_runs()
            self.assertIsNone(dialog.restore_run_id)
            self.assertIsNone(dialog.active_run_id)
            self.assertEqual(len(dialog.training_history),1)
        finally: dialog.deleteLater()

    def test_initialization_state_checks_activation(self):
        net=network(); holder=SimpleNamespace(network=net)
        state=TrainingDialog.capture_training_state(holder)
        self.assertTrue(TrainingDialog.training_state_is_compatible(holder,state))
        net.get_neuron(2).activation_function="Sigmoid"
        self.assertFalse(TrainingDialog.training_state_is_compatible(holder,state))

    def test_atomic_write_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix="review_test_") as directory:
            self.assertEqual(Path(directory).resolve().parent,ROOT)
            path=Path(directory)/"layout.json"; original=b'{"cards":{"old":true}}'
            path.write_bytes(original)
            with patch("atomicjson.os.replace",side_effect=OSError("test failure")):
                with self.assertRaises(OSError): write_json_atomic(path,{"cards":{"new":True}})
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(list(Path(directory).iterdir()),[path])

    def test_layout_and_geometry_use_atomic_writer(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix="review_test_") as directory:
            self.assertEqual(Path(directory).resolve().parent,ROOT)
            path=Path(directory)/"layout.json"
            w=SimpleNamespace(finish_nudge_history=lambda:None,layout_file=path,background_item=None,
                layout_state=lambda:{"cards":{"test":True}},width=lambda:900,height=lambda:600,
                update_save_button=lambda:None,status_label=Mock(),tr=lambda de,en:en,
                saveGeometry=lambda:b"geometry")
            self.assertTrue(GraphicalExperimentDialog.save_layout(w))
            before=path.read_bytes()
            with patch("graphicalexperimentdialog.QSettings"),patch("atomicjson.os.replace",side_effect=OSError("test failure")):
                GraphicalExperimentDialog.save_window_geometry(w)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(json.loads(before)["cards"],{"test":True})

    def test_numerical_messages_follow_language(self):
        for code in ("de","en"):
            net=network(code);net.get_neuron(1).input_value=2.0;net.get_connection(1).weight=1e308
            with self.assertRaises(ValueError) as error:net.forward_pass()
            self.assertIn("numerisch instabil" if code=="de" else "numerically unstable",str(error.exception))
            with self.assertRaises(ValueError) as error:net.set_learning_rate(0)
            self.assertIn("Lernrate" if code=="de" else "learning rate",str(error.exception))

    def test_hidden_training_error_is_translated(self):
        for code in ("de","en"):
            net=network(code);net.get_neuron(2).activation_function="Linear"
            net.get_neuron(1).input_value=0.0;net.get_connection(2).weight=1e308
            net.forward_pass()
            with self.assertRaises(ValueError) as error:net.calculate_training_deltas({3:1e308})
            self.assertIn("Hidden-Neuron" if code=="de" else "hidden neuron",str(error.exception))

    def test_saved_project_loads_history_after_data_and_restores_momentum(self):
        from editorscene import EditorScene
        for change_data in (False, True):
            with self.subTest(change_data=change_data):
                original=window(); run=entry(original)
                run["network_state"]["momentum_state"]={"connections":{"1":0.25},"biases":{}}
                saved=project([])
                saved["neurons"]=[dict(id=n.id,name=n.name,type=n.neuron_type.value,
                    bias=n.bias,activation=n.activation_function,input_value=0.0,target_value=0.0,
                    x=n.x(),y=n.y()) for n in original.scene.network.get_neurons()]
                saved["connections"]=[dict(id=c.id,source=c.source_neuron.id,target=c.target_neuron.id,
                    weight=c.weight) for c in original.scene.network.get_connections()]
                saved["training_history"]=[run];saved["active_training_run_id"]=1
                saved["momentum_state"]=None
                w=window();w.scene=EditorScene(language_manager=language("en"));w.language=language("en")
                w.test_data_manager=TrainingDataManager(language_manager=w.language)
                w.confirm_unsaved_changes=lambda:True
                def reset():
                    w.training_history=[];w._invalidated_training_runs={};w.active_training_run_id=None
                    w.scene.clear_project();w.training_data_manager.clear();w.test_data_manager.clear()
                w.reset_project=reset
                w.training_data_manager.state_changed.connect(w.refresh_training_history_validity)
                d=document()
                if change_data:d["records"][1][1]=0.7
                w.prepare_project_training_data=lambda *args:dict(cancelled=False,document=d,
                    file_path=str(ROOT/"same.nndata"),association_changed=False)
                w.prepare_project_test_data=lambda *args:dict(cancelled=False,document=None,
                    file_path=None,association_changed=False)
                w.view=SimpleNamespace(set_zoom=Mock(),centerOn=Mock())
                for name in ("apply_display_settings","update_project_image_action","remember_project_directory",
                             "reset_undo_history","set_project_modified","schedule_loaded_project_fit"):
                    setattr(w,name,Mock())
                w.reconcile_active_data_mappings=lambda:False
                status=Mock();w.statusBar=lambda:status
                with tempfile.TemporaryDirectory(dir=ROOT,prefix="review_test_") as directory:
                    self.assertEqual(Path(directory).resolve().parent,ROOT)
                    path=Path(directory)/"project.nnproj";path.write_text(json.dumps(saved),encoding="utf-8")
                    with patch("mainwindow.QTimer.singleShot"):
                        self.assertTrue(MainWindow.open_project(w,str(path)))
                self.assertEqual(w.scene.network.trainer.connection_velocities,{1:0.25})
                if change_data:
                    self.assertIsNone(w.active_training_history_entry())
                    self.assertEqual(w.training_history[0]["invalidated_reason"],"data")
                else:
                    self.assertEqual(w.active_training_history_entry()["run_id"],1)
                    self.assertNotIn("invalidated_reason",w.training_history[0])
                    w.set_project_modified.assert_called_with(False)
                w.scene.deleteLater()

    def test_malformed_history_metadata_rejected_before_loading(self):
        for code in ("de","en"):
            w=window()
            for field,value in [("validity_id",[]),("training_context",[]),("invalidated_reason","unknown")]:
                run=entry(w);run[field]=value
                with self.subTest(code=code,field=field):
                    with self.assertRaises(ValueError) as error:
                        ProjectIO._validate_training_history_data([run],translator=language(code).text)
                    self.assertIn("ungültig" if code=="de" else "invalid",str(error.exception))

    def test_language_keys_have_matching_placeholders(self):
        from string import Formatter
        data=json.loads((ROOT/"languages.json").read_text(encoding="utf-8"))["languages"]
        for key,en in data["en"]["texts"].items():
            if key.startswith(("calculation.error.","history.invalid","dialog.project_open.topology","dialog.project_open.invalid_topology")):
                de=data["de"]["texts"][key]
                fields=lambda s:{f for _,f,_,_ in Formatter().parse(s) if f is not None}
                self.assertEqual(fields(en),fields(de),key)
                self.assertEqual(language("en").BUILTIN_ENGLISH[key],en)

class ProjectDeletionTests(unittest.TestCase):
    def setUp(self):
        from settings import Settings
        from PySide6.QtWidgets import QMessageBox
        self.settings = Settings
        self.message_type = QMessageBox
        self.temp = tempfile.TemporaryDirectory(prefix=".project_delete_test_", dir=ROOT)
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, ROOT.resolve())
        self.addCleanup(self.temp.cleanup)
        p = patch.object(Settings, "get_settings_path", return_value=self.root / "settings.json")
        p.start(); self.addCleanup(p.stop)
        ui = dict(Settings.default_ui_settings(), project_directory=str(self.root), language="de")
        with patch.object(Settings, "get_ui_settings", return_value=ui), patch.object(Settings, "restore_window", return_value=False):
            self.w = MainWindow(defer_initial_show=True)
        self.addCleanup(self.dispose_window)
        self.folder = self.root / "Demo"
        self.folder.mkdir()
        self.file = self.folder / "Demo.nnproj"
        self.file.write_text("{}", encoding="utf8")
        (self.folder / "data" / "nested").mkdir(parents=True)
        (self.folder / "data" / "nested" / "values.txt").write_text("preserve until confirmed", encoding="utf8")
        self.neighbor = self.root / "Neighbor.txt"
        self.neighbor.write_text("keep", encoding="utf8")
        self.w.current_project_path = str(self.file)
        self.w.project_description = "Unsaved description"
        self.w.project_modified = True
        self.w.scene.network.add_neuron(Neuron(1, 0, 0, "N1"))
        self.w.update_window_title()

    def dispose_window(self):
        from PySide6.QtCore import QEvent
        APP.processEvents()  # Drain constructor callbacks while their widgets still exist.
        self.w._history_timer.stop()
        self.w.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()

    def confirm(self, accepted=True, after=None):
        from contextlib import ExitStack
        stack = ExitStack()
        selected = {}
        def execute(box):
            self.assertIn(str(self.folder), box.text())
            self.assertEqual(box.buttonRole(box.defaultButton()), self.message_type.ButtonRole.RejectRole)
            role = self.message_type.ButtonRole.DestructiveRole if accepted else self.message_type.ButtonRole.RejectRole
            selected[id(box)] = next(button for button in box.buttons() if box.buttonRole(button) == role)
            if after:
                after()
            return 0
        stack.enter_context(patch.object(self.message_type, "exec", execute))
        stack.enter_context(patch.object(self.message_type, "clickedButton", lambda box: selected.get(id(box))))
        return stack

    def test_cancel_preserves_project_and_unsaved_changes(self):
        with self.confirm(False), patch("mainwindow.shutil.rmtree") as remove:
            self.assertFalse(self.w.delete_current_project())
            remove.assert_not_called()
        self.assertTrue(self.file.exists())
        self.assertTrue(self.w.project_modified)
        self.assertEqual(self.w.project_description, "Unsaved description")
        self.assertEqual(self.w.current_project_path, str(self.file))

    def test_confirm_deletes_only_project_and_leaves_no_active_project(self):
        self.settings.add_recent_project_file(str(self.file), "de")
        self.settings.add_recent_project_file(str(self.file), "en")
        self.settings.save_last_project_file(str(self.file))
        bar = self.w.menuBar()
        file_action = bar.actions()[0]
        file_menu = file_action.menu()
        menu = file_menu.actions()
        self.assertEqual(menu.index(self.w.action_delete_project), menu.index(self.w.action_rename_project)+1)
        self.assertTrue(self.w.action_delete_project.isEnabled())
        with self.confirm():
            self.assertTrue(self.w.delete_current_project())
        self.assertFalse(self.folder.exists())
        self.assertEqual(self.neighbor.read_text(encoding="utf8"), "keep")
        self.assertIsNone(self.w.current_project_path)
        self.assertEqual(self.w.scene.network.get_neurons(), [])
        self.assertEqual(self.w.project_description, "")
        self.assertFalse(self.w.project_modified)
        self.assertEqual(self.w.undo_history, [])
        self.assertFalse(self.w.action_delete_project.isEnabled())
        self.assertFalse(self.w.action_save.isEnabled())
        self.assertIn("Kein Projekt geöffnet", self.w.windowTitle())
        self.assertEqual(self.settings.get_last_project_file(), "")
        for code in ("de", "en"):
            self.assertNotIn(str(self.file), self.settings.get_recent_project_files(code))
        self.w.language = language("en")
        self.w.update_window_title()
        self.assertIn("No Project Open", self.w.windowTitle())
        self.w.initialize_new_project()
        self.assertIn("New Project", self.w.windowTitle())

    def test_rejects_collections_and_links(self):
        self.assertEqual(self.w.project_deletion_directory(), self.folder)
        other = self.folder / "Another.nnproj"
        other.write_text("{}", encoding="utf8")
        self.assertIsNone(self.w.project_deletion_directory())
        other.unlink()
        self.w.ui_settings["project_directory"] = str(self.folder)
        self.assertIsNone(self.w.project_deletion_directory())
        self.w.ui_settings["project_directory"] = str(self.root)
        self.w.current_project_path = str(self.folder / "Different.nnproj")
        Path(self.w.current_project_path).write_text("{}", encoding="utf8")
        self.assertIsNone(self.w.project_deletion_directory())
        self.w.current_project_path = str(self.file)
        with patch.object(Path, "is_junction", return_value=True):
            self.assertIsNone(self.w.project_deletion_directory())
        with patch.object(Path, "is_symlink", return_value=True):
            self.assertIsNone(self.w.project_deletion_directory())

    def test_failure_preserves_editor_and_reports_error(self):
        with self.confirm(), patch("mainwindow.shutil.rmtree", side_effect=PermissionError("locked")), patch.object(self.message_type, "critical") as report:
            self.assertFalse(self.w.delete_current_project())
            report.assert_called_once()
        self.assertTrue(self.file.exists())
        self.assertEqual(self.w.current_project_path, str(self.file))
        self.assertEqual(len(self.w.scene.network.get_neurons()), 1)
        self.assertTrue(self.w.project_modified)

    def test_rechecks_folder_after_confirmation_and_blocks_training(self):
        def alter():
            (self.folder / "Other.nnproj").write_text("{}", encoding="utf8")
        with self.confirm(after=alter), patch.object(self.message_type, "warning") as report, patch("mainwindow.shutil.rmtree") as remove:
            self.assertFalse(self.w.delete_current_project())
            remove.assert_not_called()
            report.assert_called_once()
        self.assertTrue(self.file.exists())
        self.w.training_observation_mode = True
        self.w.update_window_title()
        self.assertFalse(self.w.action_delete_project.isEnabled())
        self.assertFalse(self.w.delete_current_project())


class AutomaticScalingPreviewTests(unittest.TestCase):
    def setUp(self):
        from PySide6.QtGui import QFont, QFontDatabase
        previous = APP.font()
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        APP.setFont(QFont("Segoe UI", 9))
        self.addCleanup(lambda: APP.setFont(previous))

    def make_dialog(self, code):
        from trainingdatadialog import TrainingDataDialog
        net = network(code)
        net.get_neuron(1).name = "Position"
        net.get_neuron(3).name = "Sensorspannung"
        net.get_neuron(3).activation_function = "Tanh"
        doc = document()
        doc["columns"][0]["name"] = "Position"
        doc["columns"][1]["name"] = "Sensorspannung"
        doc["records"] = [[0., .5], [120., 4.5]]
        doc["columns"][0]["calibration"] = dict(mode="standard", source_min=0., source_max=120., mean=60., stddev=12.)
        return TrainingDataDialog(net, doc, language_manager=language(code))

    def execute_preview(self, editor, code, accept, selections=None):
        from trainingdatadialog import AutomaticScalingPreviewDialog
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialogButtonBox
        from PySide6.QtTest import QTest
        before = deepcopy(editor.document)
        history = deepcopy(editor._edit_history)
        failures = []
        def inspect():
            preview = APP.activeModalWidget()
            try:
                self.assertIsInstance(preview, AutomaticScalingPreviewDialog)
                self.assertEqual(editor.document, before)
                self.assertEqual(editor._edit_history, history)
                self.assertEqual(preview.table.columnCount(), 5)
                self.assertEqual(preview.table.item(0, 0).text(), "Position")
                self.assertEqual(preview.table.item(0, 1).text(), "Input")
                self.assertEqual(preview.table.item(0, 2).text(), "0")
                self.assertEqual(preview.table.item(0, 3).text(), "120")
                self.assertEqual(preview.table.item(1, 0).text(), "Sensorspannung")
                self.assertEqual(preview.table.item(1, 1).text(), "Output")
                self.assertEqual(preview.table.item(1, 4).text(), "")
                for row, combo in preview.method_combos.items():
                    self.assertEqual(preview.table.item(row, 4).text(), "")
                    self.assertGreaterEqual(preview.table.rowHeight(row), combo.sizeHint().height()+2)
                self.assertEqual(preview.selected_methods(), {0: "minmax_0_1", 1: "minmax_minus1_1"})
                for row, mode in (selections or {}).items():
                    combo = preview.method_combos[row]
                    self.assertEqual(combo.count(), 4)
                    combo.setCurrentIndex(combo.findData(mode))
                    self.assertEqual(combo.currentData(), mode)
                self.assertEqual(editor.document, before)
                preview.grab().save(str(Path(tempfile.gettempdir()) / f"scaling_preview_{code}.png"))
                button = QDialogButtonBox.StandardButton.Ok if accept else QDialogButtonBox.StandardButton.Cancel
                QTest.mouseClick(preview.buttons.button(button), Qt.MouseButton.LeftButton)
            except BaseException as error:
                failures.append(error)
                if preview is not None:
                    preview.reject()
        QTimer.singleShot(30, inspect)
        editor.automatically_scale_from_table()
        if failures:
            raise failures[0]

    def dispose(self, editor):
        from PySide6.QtCore import QEvent
        editor.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()

    def test_cancel_leaves_document_modified_flag_and_history_untouched(self):
        for code in ("de", "en"):
            editor = self.make_dialog(code)
            try:
                before = deepcopy(editor.document)
                modified, index = editor.modified, editor._edit_history_index
                history = deepcopy(editor._edit_history)
                self.execute_preview(editor, code, False, {0: "none", 1: "standard"})
                self.assertEqual(editor.document, before)
                self.assertEqual(editor.modified, modified)
                self.assertEqual(editor._edit_history_index, index)
                self.assertEqual(editor._edit_history, history)
                self.assertTrue(editor.automatic_scaling_status_label.isHidden())
            finally:
                self.dispose(editor)

    def test_accept_applies_existing_input_and_tanh_rules(self):
        for code in ("de", "en"):
            editor = self.make_dialog(code)
            try:
                records = deepcopy(editor.document["records"])
                self.execute_preview(editor, code, True)
                first, second = editor.document["columns"]
                self.assertEqual(first["calibration"]["mode"], "minmax_0_1")
                self.assertEqual(first["calibration"]["source_max"], 120.)
                self.assertEqual(second["calibration"]["mode"], "minmax_minus1_1")
                self.assertEqual(second["calibration"]["source_min"], .5)
                self.assertEqual(second["calibration"]["source_max"], 4.5)
                self.assertEqual(editor.document["records"], records)
                self.assertTrue(editor.modified)
                self.assertFalse(editor.automatic_scaling_status_label.isHidden())
            finally:
                self.dispose(editor)

    def test_selected_methods_are_applied_only_after_accept(self):
        for code in ("de", "en"):
            for selections in ({0: "standard", 1: "none"}, {0: "minmax_minus1_1", 1: "standard"}):
                editor = self.make_dialog(code)
                try:
                    self.execute_preview(editor, code, True, selections)
                    first, second = [column["calibration"] for column in editor.document["columns"]]
                    self.assertEqual(first["mode"], selections[0])
                    self.assertEqual(second["mode"], selections[1])
                    self.assertEqual(first["source_min"], 0.)
                    self.assertEqual(first["source_max"], 120.)
                    self.assertEqual(first["mean"], 60.)
                    self.assertEqual(first["stddev"], 60.)
                    self.assertEqual(second["mean"], 2.5)
                    self.assertEqual(second["stddev"], 2.)
                    self.assertEqual(TrainingDataIO.scale_value(60., first), 0.)
                    self.assertEqual(TrainingDataIO.scale_value(2.5, second), 2.5 if selections[1] == "none" else 0.)
                finally:
                    self.dispose(editor)

    def test_compact_width_and_long_names_are_screen_limited(self):
        from trainingdatadialog import AutomaticScalingPreviewDialog
        from PySide6.QtWidgets import QAbstractItemView
        for code in ("de", "en"):
            method = language(code).text("data.calibration.minmax_0_1")
            short = AutomaticScalingPreviewDialog([("Position", "Input", "0", "120", method)], language(code), modes=["minmax_0_1"])
            name = "Very long neuron designation " * 50
            long = AutomaticScalingPreviewDialog([(name, "Input", "0", "120", method)], language(code), modes=["minmax_0_1"])
            try:
                self.assertEqual(short.table.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers)
                self.assertLess(short.width(), 600)
                self.assertGreater(long.width(), short.width())
                self.assertLessEqual(long.width(), long.screen().availableGeometry().width()-40)
                self.assertEqual(long.table.item(0, 0).toolTip(), name)
                self.assertEqual([short.table.columnWidth(i) for i in range(1, 5)],
                                 [long.table.columnWidth(i) for i in range(1, 5)])
                self.assertLess(short.height(), 200)
            finally:
                self.dispose(short); self.dispose(long)

    def test_preview_describes_binary_constant_and_empty_columns(self):
        editor = self.make_dialog("de")
        try:
            editor.document["columns"][0]["data_type"] = "binary"
            before = deepcopy(editor.document)
            with patch.object(editor, "get_column_numeric_values", side_effect=[[0., 1.], [7., 7.]]):
                rows = editor.automatic_scaling_preview_rows()
            self.assertEqual(rows[0][4], language("de").text("data.calibration.none"))
            self.assertEqual(rows[1][4], language("de").text("data.auto_scale_preview.constant"))
            with patch.object(editor, "get_column_numeric_values", return_value=[]):
                rows = editor.automatic_scaling_preview_rows()
            self.assertEqual(rows[1][2:4], ("—", "—"))
            self.assertEqual(rows[1][4], language("de").text("data.auto_scale_preview.empty"))
            self.assertEqual(editor.document, before)
            from trainingdatadialog import AutomaticScalingPreviewDialog
            preview = AutomaticScalingPreviewDialog(rows, language("de"), modes=[None, None])
            try:
                self.assertEqual(preview.selected_methods(), {})
                self.assertIsNone(preview.table.cellWidget(0, 4))
                self.assertIsNone(preview.table.cellWidget(1, 4))
            finally:
                self.dispose(preview)
        finally:
            self.dispose(editor)


if __name__ == "__main__":
    unittest.main(verbosity=2)
