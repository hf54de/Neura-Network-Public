import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QFont,QFontDatabase,QWheelEvent
from PySide6.QtCore import QPoint,Qt
from _test_adam import APP,IntegrationTests
from weighttrajectory import WeightSelectionDialog
from traininghistorydialog import TrainingHistoryDialog
from chartcolors import set_chart_background

class ComparisonTests(unittest.TestCase):
    setUp=IntegrationTests.setUp
    tearDown=IntegrationTests.tearDown
    make_dialog=IntegrationTests.make_dialog

    def test_compare_zoom_and_selection(self):
        d=self.make_dialog()
        with patch.object(WeightSelectionDialog,'exec',return_value=QDialog.DialogCode.Accepted):
            d.record_weight_trajectory.setChecked(True)
        d.execute_training(3,False,shuffle_seed=42)
        d.execute_training(4,False,shuffle_seed=43)
        original=deepcopy(self.w.training_history)
        h=TrainingHistoryDialog(self.w.training_history,language_manager=self.w.language)
        try:
            h.metric_combo.setCurrentIndex(h.metric_combo.findData('trajectory'))
            h.table.selectAll();p=h.weight_trajectory_plot
            self.assertEqual(len(p.comparison),2)
            for _,data in p.comparison:
                for _,x,y,_ in data['points']:
                    self.assertLessEqual(p._bounds[0],x);self.assertGreaterEqual(p._bounds[1],x)
                    self.assertLessEqual(p._bounds[2],y);self.assertGreaterEqual(p._bounds[3],y)
            p.resize(900,500);pos=p.plot_area().center()
            p.wheelEvent(QWheelEvent(pos,pos,QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False))
            self.assertIsNotNone(p.view_bounds)
            h.show_full_range();self.assertIsNone(p.view_bounds)
            QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf');APP.setFont(QFont('Segoe UI',9))
            set_chart_background('#303030');p.show();APP.processEvents()
            p.grab().save('diagnostics/trajectory_comparison_checked.png')
            h.table.clearSelection();h.table.selectRow(0)
            self.assertEqual(p.comparison,[])
            self.assertIsNotNone(p.data)
            a,b=deepcopy(original)
            self.assertTrue(h.compatible_weight_trajectories([a,b]))
            b['weight_trajectory']['connections'].reverse()
            self.assertFalse(h.compatible_weight_trajectories([a,b]))
            a,b=deepcopy(original);b['network_state']['connections'][0]['source']+=999
            self.assertFalse(h.compatible_weight_trajectories([a,b]))
            a,b=deepcopy(original);b.pop('weight_trajectory')
            self.assertFalse(h.compatible_weight_trajectories([a,b]))
            self.assertEqual(self.w.training_history,original)
        finally:
            set_chart_background('#ffffff');h.close();h.deleteLater()

    def test_default_and_weight_continuation_toggle(self):
        d=self.make_dialog()
        with patch.object(WeightSelectionDialog,'exec',return_value=QDialog.DialogCode.Accepted):
            d.record_weight_trajectory.setChecked(True)
        d.execute_training(2,False,shuffle_seed=42)
        d.execute_training(2,False,shuffle_seed=43)
        runs=deepcopy(self.w.training_history)
        runs[1]['parent_run_id']=runs[0]['run_id']
        runs[1]['weight_trajectory']['points'][0][1:3]=runs[0]['weight_trajectory']['points'][-1][1:3]
        h=TrainingHistoryDialog(list(reversed(runs)),language_manager=self.w.language)
        try:
            self.assertTrue(h.attach_continuations.isChecked())
            self.assertTrue(h.chart.attach_continuations)
            h.metric_combo.setCurrentIndex(h.metric_combo.findData('trajectory'))
            h.table.selectAll()
            self.assertFalse(h.attach_continuations.isHidden())
            self.assertTrue(h.weight_trajectory_plot.joined_comparison)
            self.assertIs(h.weight_trajectory_plot.comparison[0][1],h.training_history[1]['weight_trajectory'])
            h.attach_continuations.setChecked(False)
            self.assertFalse(h.weight_trajectory_plot.joined_comparison)
            h.attach_continuations.setChecked(True)
            self.assertTrue(h.weight_trajectory_plot.joined_comparison)
            h.metric_combo.setCurrentIndex(h.metric_combo.findData('characteristic'))
            self.assertTrue(h.attach_continuations.isHidden())
            self.assertEqual(list(reversed(h.training_history)),runs)
        finally:h.close();h.deleteLater()

if __name__=='__main__':unittest.main()
