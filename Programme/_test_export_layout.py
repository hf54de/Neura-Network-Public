"""Check export layout, collapse behaviour and the portable compact preference."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from plcexportsettings import PlcExportSettingsPanel
from settings import Settings
from settingsprofile import SettingsProfile
from settingsdialog import SettingsDialog
from projectio import ProjectIO
from language import LanguageManager
from spsexportdialog import SpsExportDialog
from xmlexportdialog import XmlExportDialog
from _test_binary_uncertainty import UncertaintyTests
from iec61131export import Iec61131ExportGenerator


class ExportLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        cls.app.setFont(QFont('Segoe UI', 9))

    def flush(self):
        for _ in range(4):
            self.app.processEvents()

    def test_spacing_and_collapse(self):
        for german in (True, False):
            panel = PlcExportSettingsPanel('FB_Test', '1', german)
            self.assertFalse(any(value for value in panel.export_options().values() if isinstance(value, bool)))
            self.assertEqual(panel.options_toggle.text(), 'Optionen' if german else 'Options')
            panel.binary_uncertainty.setChecked(True)
            panel.show()
            for width in (820, 1100):
                panel.resize(width, panel.sizeHint().height())
                self.flush()
                centre = panel.separator.mapTo(panel, panel.separator.rect().center()).x()
                self.assertLessEqual(abs(centre - panel.rect().center().x()), 1)
                controls = (panel.enable, panel.range_check, panel.range_tolerance,
                            panel.binary_uncertainty, panel.pruning)
                ys = [c.mapTo(panel, c.rect().center()).y() for c in controls]
                gaps = [b - a for a, b in zip(ys, ys[1:])]
                self.assertLessEqual(max(gaps) - min(gaps), 1, gaps)
                for left, right in ((panel.enable, panel.network_active),
                                    (panel.range_check, panel.range_error),
                                    (panel.range_tolerance, panel.invalid_number)):
                    self.assertLessEqual(abs(left.geometry().center().y() - right.geometry().center().y()), 1)
                self.assertGreaterEqual(panel.separator.geometry().bottom(), panel.binary_uncertainty.geometry().bottom())
            before = panel.export_options()
            panel.options_toggle.click()
            self.flush()
            self.assertFalse(panel.binary_uncertainty.isVisible())
            self.assertFalse(panel.pruning.isVisible())
            self.assertFalse(panel.auto_prune_button.isVisible())
            panel.options_toggle.click()
            self.flush()
            self.assertTrue(panel.pruning.isVisible())
            self.assertEqual(before, panel.export_options())
            self.assertTrue(panel.network_active.toolTip())
            panel.close()

    def test_dialog_sections_and_preview(self):
        parent, training, inputs, outputs = UncertaintyTests().fixture()
        data = Iec61131ExportGenerator(training.network, inputs, outputs).generate()
        self.assertFalse(any(value for value in data['export_options'].values() if isinstance(value, bool)))
        for cls in (SpsExportDialog, XmlExportDialog):
            for compact in (True, False):
                dialog = cls(data, compact_open=compact)
                dialog.show()
                self.flush()
                for toggle in (dialog.settings_panel.options_toggle, dialog.fb_preview_panel.toggle,
                               dialog.code_section.toggle):
                    self.assertEqual(toggle.isChecked(), not compact)
                before = dialog.settings_panel.export_options()
                dialog.fb_preview_panel.toggle.click()
                dialog.fb_preview_panel.set_expanded(True)
                self.flush()
                preview = dialog.fb_preview_panel
                self.assertEqual(preview.scroll.verticalScrollBar().maximum(), 0)
                self.assertLessEqual(preview.height(), dialog.height())
                dialog.code_section.toggle.click()
                self.flush()
                self.assertEqual(before, dialog.settings_panel.export_options())
                dialog.close()

    def test_minimum_height_follows_visible_sections(self):
        parent, training, inputs, outputs = UncertaintyTests().fixture()
        data = Iec61131ExportGenerator(training.network, inputs, outputs).generate()
        for cls in (SpsExportDialog, XmlExportDialog):
            dialog = cls(data, compact_open=True)
            dialog.show()
            self.flush()
            compact_height = dialog.minimumHeight()
            self.assertGreater(compact_height, 200)
            dialog.resize(dialog.width(), compact_height + 300)
            self.flush()
            self.assertEqual(dialog.height(), compact_height)
            dialog.resize(dialog.width(), 100)
            self.flush()
            self.assertEqual(dialog.height(), compact_height)
            self.assertEqual(dialog.export_scroll.verticalScrollBar().maximum(), 0)
            for toggle in (dialog.settings_panel.options_toggle,
                           dialog.fb_preview_panel.toggle, dialog.code_section.toggle):
                toggle.click()
                self.flush()
                expanded_height = dialog.minimumHeight()
                self.assertGreater(expanded_height, compact_height)
                if toggle is dialog.code_section.toggle:
                    self.assertGreater(dialog.maximumHeight(), expanded_height)
                else:
                    self.assertEqual(dialog.maximumHeight(), expanded_height)
                dialog.resize(dialog.width(), 100)
                self.flush()
                self.assertEqual(dialog.height(), expanded_height)
                toggle.click()
                self.flush()
                self.assertEqual(dialog.minimumHeight(), compact_height)
            dialog.close()

    def test_compact_profile(self):
        self.assertTrue(Settings.normalize_ui_settings({})['export_window_compact'])
        display = ProjectIO.default_display_settings()
        defaults = Settings.default_ui_settings()
        dialog = SettingsDialog(display, display, defaults, defaults, LanguageManager('de'))
        dialog.export_window_compact.setChecked(False)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.json'
            SettingsProfile.write(path, SettingsProfile.build(display, dialog.ui_settings()))
            self.assertFalse(SettingsProfile.read(path)['ui']['export_window_compact'])
            with patch.object(Settings, 'get_settings_path', return_value=Path(folder) / 'settings.json'), \
                 patch.object(Settings, 'get_legacy_settings_path', return_value=Path(folder) / 'absent.json'):
                Settings.save_ui_settings(dialog.ui_settings())
                self.assertFalse(Settings.get_ui_settings()['export_window_compact'])
            dialog.export_window_compact.setChecked(True)
            with patch('settingsdialog.QFileDialog.getOpenFileName', return_value=(str(path), '')):
                dialog.load_profile()
            self.assertFalse(dialog.export_window_compact.isChecked())
        dialog.category_list.setCurrentRow(5)
        dialog.restore_current_defaults()
        self.assertTrue(dialog.export_window_compact.isChecked())
        dialog.close()


if __name__ == '__main__':
    unittest.main()
