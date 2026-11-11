import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer,QThread
from PySide6.QtWidgets import QMessageBox
from _test_adam import APP,IntegrationTests
from projectio import ProjectIO
from projectloadprogress import ProjectLoadProgress

class LoadProgressTests(unittest.TestCase):
    setUp=IntegrationTests.setUp
    tearDown=IntegrationTests.tearDown
    make_dialog=IntegrationTests.make_dialog

    def test_worker_keeps_interface_alive_and_reports_stages(self):
        self.assertTrue(self.w.write_project_file(str(self.file)))
        original=ProjectIO.load_project
        threads=[];ticks=[];phases=[]
        def delayed(*args,**kwargs):
            threads.append(QThread.currentThread())
            time.sleep(.12)
            return original(*args,**kwargs)
        timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(1));timer.start()
        try:
            with ProjectLoadProgress(self.w,self.w.language) as progress:
                old=progress.phase
                def phase(key):
                    phases.append(key);old(key)
                with patch.object(progress,'phase',side_effect=phase),patch.object(ProjectIO,'load_project',side_effect=delayed):
                    data=progress.read(str(self.file))
                self.assertTrue(data['neurons'])
                self.assertTrue(progress.dialog.isVisible())
            self.assertFalse(progress.dialog.isVisible())
            self.assertNotEqual(threads[0],APP.thread())
            self.assertGreater(len(ticks),2)
            self.assertIn('project.loading.read',phases)
            self.assertIn('project.loading.validate',phases)
        finally:timer.stop()

    def test_open_success_and_invalid_file_cleanup(self):
        self.assertTrue(self.w.write_project_file(str(self.file)))
        before=self.w.capture_training_network_state()
        with patch.object(self.w,'confirm_unsaved_changes',return_value=True):
            self.assertTrue(self.w.open_project(str(self.file),automatic_start=True))
            self.assertEqual(self.w.capture_training_network_state(),before)
            self.file.write_text('{}',encoding='utf-8')
            with patch.object(QMessageBox,'critical') as error:
                self.assertFalse(self.w.open_project(str(self.file)))
                error.assert_called_once()
            self.assertEqual(self.w.capture_training_network_state(),before)
        APP.processEvents()
        self.assertFalse(any(w.isVisible() for w in self.w.findChildren(ProjectLoadProgress)[-1].children() if hasattr(w,'isVisible')))

    def test_project_report_is_available_after_loading_without_training(self):
        from base64 import b64decode
        import re
        from zipfile import ZipFile
        from PySide6.QtWidgets import QFileDialog
        from resultanalysisdialog import ResultAnalysisDialog

        description = "Beschreibung des Testprojekts"
        self.w.project_description = description
        self.w.training_data_manager.clear()
        self.assertTrue(self.w.write_project_file(str(self.file)))
        self.w.reset_project()
        action = self.w.action_export_word_report
        self.assertFalse(action.isEnabled())

        with (
            patch.object(self.w, "confirm_unsaved_changes", return_value=True),
            patch.object(self.w, "ask_for_training_data_file", return_value=("without", None)),
        ):
            self.assertTrue(self.w.open_project(str(self.file)))
        self.assertTrue(action.isEnabled())
        self.assertFalse(self.w.training_history)
        self.assertFalse(self.w.training_data_manager.has_document)

        for suffix, filter_key in (
            ("docx", "word_filter"), ("pdf", "filter"), ("html", "html_filter"),
        ):
            path = self.root / f"Projektbericht.{suffix}"
            selected_filter = self.w.language.text(f"analysis.report.{filter_key}")
            with (
                patch.object(QFileDialog, "getSaveFileName", return_value=(str(path), selected_filter)),
                patch.object(ResultAnalysisDialog, "offer_open_report") as ready,
            ):
                action.trigger()
                ready.assert_called_once_with(str(path))
                self.assertIn(self.w.language.text("analysis.report.html_filter"),
                              QFileDialog.getSaveFileName.call_args.args[3])
            if suffix == "docx":
                with ZipFile(path) as report:
                    body = report.read("word/document.xml").decode("utf-8")
                self.assertIn(description, body)
                self.assertIn(self.w.language.text("analysis.report.network"), body)
                self.assertNotIn(self.w.language.text("analysis.report.active_run_details"), body)
                self.assertNotIn(self.w.language.text("analysis.deviations.group"), body)
            elif suffix == "pdf":
                self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
            else:
                markup = path.read_text(encoding="utf-8")
                self.assertTrue(markup.startswith("<!DOCTYPE html>"))
                self.assertIn(description, markup)
                self.assertIn(self.w.language.text("analysis.report.network"), markup)
                self.assertIn("@media print", markup)
                self.assertIn("break-before:page", markup)
                self.assertNotIn(self.w.language.text("analysis.report.active_run_details"), markup)
                images = re.findall(r'src="data:image/png;base64,([^"]+)"', markup)
                self.assertEqual(len(images), 1)
                self.assertTrue(b64decode(images[0], validate=True).startswith(b"\x89PNG\r\n\x1a\n"))

        self.w.reset_project()
        self.assertFalse(action.isEnabled())

    def test_viewport_hidden_until_ready_and_restored_on_error(self):
        self.assertTrue(self.w.write_project_file(str(self.file)))
        self.w.show();APP.processEvents()
        original=ProjectLoadProgress.phase
        seen=[]
        def phase(progress,key):
            if progress.window is self.w:
                seen.append(key)
                self.assertTrue(self.w.view.viewport().isHidden())
            original(progress,key)
        with patch.object(self.w,'confirm_unsaved_changes',return_value=True),patch.object(ProjectLoadProgress,'phase',phase):
            self.assertTrue(self.w.open_project(str(self.file)))
        self.assertTrue(seen)
        self.assertFalse(self.w.view.viewport().isHidden())
        self.assertIsNone(self.w._pending_loaded_project_fit)
        self.file.write_text('{}',encoding='utf-8')
        with patch.object(self.w,'confirm_unsaved_changes',return_value=True),patch.object(QMessageBox,'critical'):
            self.assertFalse(self.w.open_project(str(self.file)))
        self.assertFalse(self.w.view.viewport().isHidden())
        self.w.hide()

    def test_startup_reveals_only_after_fit_and_cancel_restores_view(self):
        self.assertTrue(self.w.write_project_file(str(self.file)))
        with patch.object(self.w,'confirm_unsaved_changes',return_value=True):
            self.assertTrue(self.w.open_project(str(self.file),automatic_start=True))
        self.assertTrue(self.w.view.viewport().isHidden())
        self.w.show_after_startup();APP.processEvents()
        self.assertFalse(self.w.view.viewport().isHidden())
        with patch.object(self.w,'confirm_unsaved_changes',return_value=True),patch.object(self.w,'prepare_project_training_data',return_value={'cancelled':True}):
            self.assertFalse(self.w.open_project(str(self.file)))
        self.assertFalse(self.w.view.viewport().isHidden())
        self.w.hide()

if __name__=='__main__':unittest.main()
