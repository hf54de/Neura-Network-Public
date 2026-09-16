"""Regression checks for portable settings and project fallback."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from language import LanguageManager
from projectio import ProjectIO
from settings import Settings
from settingsdialog import SettingsDialog
from settingsprofile import SettingsProfile


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for target, value in (("get_settings_path", self.root / "local" / "settings.json"),
                              ("get_legacy_settings_path", self.root / "absent.json")):
            patcher = patch.object(Settings, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(SettingsProfile, "directory", return_value=self.root / "Profile")
        patcher.start()
        self.addCleanup(patcher.stop)

    def dialog(self, language="de"):
        return SettingsDialog(ProjectIO.default_display_settings(), ProjectIO.default_display_settings(),
                              Settings.default_ui_settings(), Settings.default_ui_settings(), LanguageManager(language))

    def test_roundtrip_and_validation(self):
        display = ProjectIO.default_display_settings()
        display["colors"]["canvas_background"] = "#123456"
        ui = dict(Settings.default_ui_settings(), project_directory="C:/local-only", toolbar_icon_size=24)
        data = SettingsProfile.build(display, ui)
        self.assertNotIn("project_directory", data["ui"])
        path = self.root / "test.json"
        SettingsProfile.write(path, data)
        self.assertEqual(SettingsProfile.read(path), data)
        before = path.read_bytes()
        data["display"]["colors"]["selection"] = "bad"
        with self.assertRaises(ValueError):
            SettingsProfile.write(path, data)
        self.assertEqual(path.read_bytes(), before)
        minimal = SettingsProfile.validate(dict(format="NeuronNetz-settings-profile", version=1))
        self.assertEqual(minimal["display"], ProjectIO.default_display_settings())
        for bad in ({}, [], dict(format="NeuronNetz-settings-profile", version=99),
                    dict(format="NeuronNetz-settings-profile", version=1, ui={"toolbar_show_text": "false"})):
            with self.assertRaises(ValueError):
                SettingsProfile.validate(bad)

    def test_dialog_save_load_cancel(self):
        for language in ("de", "en"):
            dialog = self.dialog(language)
            directory = Path(dialog.profile_directory())
            self.assertTrue(directory.is_dir())
            profile = directory / "Meine Farben.json"
            dialog.color_buttons["canvas_background"].set_color("#123456")
            dialog.toolbar_icon_size.setValue(24)
            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(profile), "")):
                dialog.save_profile()
            self.assertEqual(dialog.profile_name, "Meine Farben")
            dialog.color_buttons["canvas_background"].set_color("#abcdef")
            self.assertIn("(", dialog.profile_label.text())
            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(profile), "")):
                dialog.load_profile()
            self.assertEqual(dialog.project_settings()["colors"]["canvas_background"], "#123456")
            self.assertEqual(dialog.toolbar_icon_size.value(), 24)
            dialog.reject()
            self.assertNotIn("active_profile", Settings.load())
            self.assertTrue(profile.exists())
            dialog.deleteLater()

    def test_invalid_load_is_non_destructive(self):
        dialog = self.dialog()
        path = self.root / "bad.json"
        path.write_text("{bad", encoding="utf-8")
        before = dialog.project_settings()
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(path), "")), patch.object(QMessageBox, "warning") as warning:
            dialog.load_profile()
            warning.assert_called_once()
        self.assertEqual(before, dialog.project_settings())

    def test_mainwindow_project_fallback_and_profile(self):
        from mainwindow import MainWindow
        project = Path(__file__).parent / "dist" / "Projects_en" / "AND 01" / "AND 01.nnproj"
        raw = json.loads(project.read_text(encoding="utf-8"))
        raw["display_settings"]["colors"]["canvas_background"] = "#abcdef"
        window = MainWindow()
        with patch.object(ProjectIO, "load_project", return_value=raw):
            self.assertTrue(window.open_project(str(project)))
        self.assertEqual(window.display_settings["colors"]["canvas_background"], "#abcdef")
        display = dict(raw["display_settings"], colors=dict(raw["display_settings"]["colors"], canvas_background="#123456"))
        # A leftover active-profile snapshot from the previous version must be ignored.
        Settings.save({"ui": window.ui_settings, "active_profile": dict(SettingsProfile.build(display, window.ui_settings), name="Test")})
        self.assertTrue(window.open_project(str(project)))
        self.assertEqual(window.display_settings, ProjectIO.normalize_display_settings(json.loads(project.read_text(encoding="utf-8"))["display_settings"]))
        window.reset_project()
        self.assertEqual(window.display_settings, ProjectIO.default_display_settings())
        window.deleteLater()

    def test_settings_cancel_and_ok(self):
        from mainwindow import MainWindow
        window = MainWindow()
        project = Path(__file__).parent / "dist" / "Projects_en" / "AND 01" / "AND 01.nnproj"
        self.assertTrue(window.open_project(str(project)))
        original = window.display_settings["colors"]["canvas_background"]
        display = ProjectIO.default_display_settings()
        display["colors"]["canvas_background"] = "#123456"
        display["colors"]["negative_weight"] = "#abcdef"
        display["show_ports"] = False
        profile = self.root / "Test.json"
        SettingsProfile.write(profile, SettingsProfile.build(display, Settings.default_ui_settings()))
        def load(dialog):
            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(profile), "")):
                dialog.load_profile()
        def cancel(dialog):
            load(dialog)
            return dialog.DialogCode.Rejected
        with patch.object(SettingsDialog, "exec", cancel):
            window.open_settings_dialog()
        self.assertEqual(window.display_settings["colors"]["canvas_background"], original)
        self.assertNotIn("active_profile", Settings.load())
        def accept(dialog):
            load(dialog)
            return dialog.DialogCode.Accepted
        with patch.object(SettingsDialog, "exec", accept):
            window.open_settings_dialog()
        self.assertEqual(window.display_settings, display)
        self.assertTrue(window.project_modified)
        saved = self.root / "Saved.nnproj"
        with patch.object(QMessageBox, "critical", side_effect=AssertionError("Project save error")):
            self.assertTrue(window.write_project_file(str(saved), data_file_paths={"training": window.training_data_manager.file_path, "test": window.test_data_manager.file_path}))
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["display_settings"], display)
        profile.unlink()  # Projects retain values, not a dependency on the template file.
        window.reset_project()
        self.assertEqual(window.display_settings, ProjectIO.default_display_settings())
        self.assertTrue(window.open_project(str(saved)))
        self.assertEqual(window.display_settings, display)
        other = Path(__file__).parent / "dist" / "Projects_en" / "AND 01" / "AND 01.nnproj"
        self.assertTrue(window.open_project(str(other)))
        self.assertEqual(window.display_settings, ProjectIO.normalize_display_settings(json.loads(other.read_text(encoding="utf-8"))["display_settings"]))
        restarted = MainWindow()
        self.assertEqual(restarted.display_settings, ProjectIO.default_display_settings())
        restarted.deleteLater()
        window.deleteLater()

    @unittest.skipUnless(os.name == "nt", "Windows release batch")
    def test_release_profile_copy(self):
        batch = (Path(__file__).parent.parent / "Veroeffentlichung-erstellen.bat").read_text(encoding="utf-8")
        start = batch.index('mkdir "%PACKAGE_DIR%\\Profile"')
        end = batch.index('\ncopy /Y', start)
        script = self.root / "copy-profiles.bat"
        script.write_text('@echo off\n' + batch[start:end] + '\nexit /b 0\n:cleanup_failed\nexit /b 1\n')
        dist, package = self.root / "dist", self.root / "package"
        dist.mkdir(); package.mkdir()
        env = dict(os.environ, DIST_DIR=str(dist), PACKAGE_DIR=str(package))
        self.assertEqual(subprocess.run(["cmd", "/c", str(script)], env=env, capture_output=True).returncode, 0)
        self.assertTrue((package / "Profile").is_dir())
        (dist / "Profile").mkdir()
        (dist / "Profile" / "Test.json").write_text('{"test":true}')
        self.assertEqual(subprocess.run(["cmd", "/c", str(script)], env=env, capture_output=True).returncode, 0)
        self.assertEqual((package / "Profile" / "Test.json").read_bytes(), (dist / "Profile" / "Test.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
