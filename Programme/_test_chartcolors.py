import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from _test_adam import APP
from _test_review_fixes import language
from settings import Settings
from settingsdialog import SettingsDialog
from settingsprofile import SettingsProfile
from projectio import ProjectIO
from chartcolors import set_chart_background, contrast
from trainingerrorchart import TrainingErrorChart
from analysisplot import CharacteristicPlot

class ChartColorTests(unittest.TestCase):
    def tearDown(self):
        set_chart_background("#ffffff")

    def test_contrast_and_scope(self):
        plot=TrainingErrorChart();plot.chart_colors_enabled=True
        application=CharacteristicPlot()
        for bg in ("#182536", "#fff2cc", "#1676b8", "#777777", "#ff0000", "#000000"):
            set_chart_background(bg)
            self.assertEqual(plot.chart_color('white'),QColor(bg))
            self.assertEqual(application.chart_color('white'),QColor('white'))
            for color in ('#1676b8','#ef7528','#25844b','#f4c430','#d02020','#243746'):
                self.assertGreaterEqual(contrast(plot.chart_color(color),QColor(bg)),4.45)
        plot.deleteLater();application.deleteLater()

    def test_analysis_characteristic_uses_chart_background(self):
        from resultanalysisdialog import ResultAnalysisDialog
        from _test_review_fixes import network
        from PySide6.QtCore import QEvent
        dialog = ResultAnalysisDialog(network("de"), [], language_manager=language("de"))
        try:
            plot = dialog.characteristic_plot
            plot.resize(640, 400)
            plot.set_data([(0., 0.), (1., 1.)], [(0., 0.), (1., 1.)])
            for bg in ("#303030", "#fff2cc", "#ffffff"):
                set_chart_background(bg)
                self.assertTrue(plot.chart_colors_enabled)
                self.assertEqual(plot.chart_color("#ffffff"), QColor(bg))
                for color in ("#1676b8", "#e05829", "#f4c430", "#243746"):
                    if bg != "#ffffff":
                        self.assertGreaterEqual(contrast(plot.chart_color(color), QColor(bg)), 4.45)
                image = plot.grab().toImage()
                rect = plot.plot_rect()
                samples = [image.pixelColor(int(rect.left()+rect.width()*x/20),
                                            int(rect.top()+rect.height()*y/20))
                           for x in range(1, 20) for y in range(1, 20)]
                self.assertGreater(sum(color == QColor(bg) for color in samples), len(samples)//2)
        finally:
            APP.processEvents()
            dialog.deleteLater()
            APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            APP.processEvents()

    def test_settings_reset_save_profile(self):
        defaults=Settings.default_ui_settings();project=ProjectIO.default_display_settings()
        dialog=SettingsDialog(project,project,defaults,defaults,language('de'),initial_page='colors')
        try:
            dialog.chart_background_button.set_color('#182536')
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'settings.json'
                with patch.object(Settings,'get_settings_path',return_value=path):
                    Settings.save_ui_settings(dialog.ui_settings())
                    self.assertEqual(Settings.get_ui_settings()['chart_background'],'#182536')
                profile=Path(tmp)/'profile.json'
                SettingsProfile.write(profile,SettingsProfile.build(project,dialog.ui_settings()))
                before = dialog.project_settings(), dialog.ui_settings()
                with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Cancel):
                    dialog.restore_current_defaults()
                self.assertEqual((dialog.project_settings(), dialog.ui_settings()), before)
                self.assertFalse(dialog.loading)
                with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Reset):
                    dialog.restore_current_defaults()
                self.assertEqual(dialog.ui_settings()['chart_background'],'#ffffff')
                with patch('settingsdialog.QFileDialog.getOpenFileName',return_value=(str(profile),'')),patch.object(dialog,'profile_directory',return_value=tmp):
                    dialog.load_profile()
                self.assertEqual(dialog.ui_settings()['chart_background'],'#182536')
            self.assertEqual(Settings.normalize_ui_settings({'chart_background':'invalid'})['chart_background'],'#ffffff')
        finally:dialog.deleteLater()

if __name__=='__main__':unittest.main()
