import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent, Qt, QRect
from PySide6.QtGui import QScreen
from PySide6.QtTest import QTest
from _test_adam import APP, IntegrationTests
from weighttrajectory import WeightSelectionDialog
from PySide6.QtWidgets import QDialog


class ChartWindowTests(unittest.TestCase):
    setUp = IntegrationTests.setUp
    tearDown = IntegrationTests.tearDown
    make_dialog = IntegrationTests.make_dialog

    def test_live_resize_switch_and_lifecycle(self):
        dialog = self.make_dialog()
        with patch.object(QScreen, 'availableGeometry', return_value=QRect(0,0,1600,1000)):
            dialog.show()
            APP.processEvents()
            QTest.mouseDClick(dialog.error_chart, Qt.MouseButton.LeftButton)
            window = dialog.enlarged_chart_window
            self.assertIsNotNone(window)
            self.assertTrue(window.isVisible())
            self.assertFalse(window.isModal())
            dialog.execute_training(3, False, shuffle_seed=42)
            QTest.qWait(120)
            self.assertEqual(window.error_chart.points, dialog.error_chart.points)
            self.assertTrue(window.error_chart.points)
            window.resize(1200,800)
            APP.processEvents()
            self.assertGreater(window.error_chart.width(), dialog.error_chart.width())
            for metric in ('maximum', 'characteristic', 'trajectory', 'mse'):
                dialog.error_metric_combo.setCurrentIndex(dialog.error_metric_combo.findData(metric))
                QTest.qWait(120)
                if metric == 'characteristic':
                    expected = window.notice if not dialog.training_characteristic_notice.isHidden() else window.characteristic
                    self.assertIs(window.stack.currentWidget(), expected)
                elif metric == 'trajectory':
                    self.assertIs(window.stack.currentWidget(), window.trajectory)
                else:
                    self.assertIs(window.stack.currentWidget(), window.error_chart)
                    self.assertEqual(window.error_chart.error_metric, metric)
            window.grab().save('diagnostics/enlarged_chart_checked.png')
            window.close()
            self.assertFalse(window.timer.isActive())
            self.assertTrue(dialog.isVisible())
            QTest.mouseDClick(dialog.error_chart, Qt.MouseButton.LeftButton)
            self.assertIs(dialog.enlarged_chart_window, window)
            self.assertTrue(window.timer.isActive())
            dialog.reject()
            self.assertFalse(window.isVisible())
            self.assertFalse(window.timer.isActive())

    def test_trajectory_updates_during_training_and_close_is_harmless(self):
        dialog = self.make_dialog('adam')
        with patch.object(WeightSelectionDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
            dialog.record_weight_trajectory.setChecked(True)
        dialog.error_metric_combo.setCurrentIndex(dialog.error_metric_combo.findData('trajectory'))
        dialog.open_enlarged_chart()
        window = dialog.enlarged_chart_window
        original = dialog.train_epoch
        def epoch(number, total):
            window.sync_chart()
            self.assertEqual(window.trajectory.data['points'][-1][0], number-1)
            if number == 2:
                window.close()
                self.assertTrue(dialog.is_training)
            return original(number,total)
        with patch.object(dialog, 'train_epoch', side_effect=epoch):
            dialog.execute_training(3,False,shuffle_seed=42)
        self.assertEqual(dialog.current_run_weight_trajectory['points'][-1][0],3)
        dialog.open_enlarged_chart()
        self.assertEqual(window.trajectory.data['points'][-1][0],3)
        window.close()

if __name__ == '__main__':unittest.main()

