import unittest
from copy import deepcopy
from _test_adam import APP
from _test_review_fixes import language
from traininghistorydialog import TrainingHistoryChart
from PySide6.QtGui import QFontDatabase,QFont

class ContinuationTests(unittest.TestCase):
    def test_offsets_boundaries_restart_and_unchanged_data(self):
        runs=[dict(run_id=1,completed_epochs=10,curve_points=[(1,.8),(10,.4)],maximum_error_curve_points=[(1,.9),(10,.6)]),
              dict(run_id=2,parent_run_id=1,completed_epochs=5,curve_points=[(1,.35),(5,.2)],maximum_error_curve_points=[(1,.5),(5,.3)]),
              dict(run_id=3,parent_run_id=2,completed_epochs=3,curve_points=[(1,.18),(3,.1)],maximum_error_curve_points=[(1,.28),(3,.2)]),
              dict(run_id=4,completed_epochs=4,curve_points=[(1,.7),(4,.3)],maximum_error_curve_points=[])]
        original=deepcopy(runs)
        chart=TrainingHistoryChart(language_manager=language('de'))
        self.assertTrue(chart.attach_continuations)
        chart.attach_continuations=False
        chart.set_runs(runs)
        self.assertEqual(chart.prepared_runs()[1]['curve_points'],runs[1]['curve_points'])
        chart.attach_continuations=True
        for metric,key in [('mse','curve_points'),('maximum','maximum_error_curve_points')]:
            chart.error_metric=metric
            prepared=chart.prepared_runs()
            self.assertEqual(prepared[1]['curve_points'][0],(10,runs[0][key][-1][1]))
            self.assertEqual(prepared[1]['curve_points'][-1][0],15)
            self.assertEqual(prepared[2]['curve_points'][-1][0],18)
        chart.error_metric='mse'
        self.assertEqual(chart.prepared_runs()[3]['curve_points'],runs[3]['curve_points'])
        chart.set_runs([runs[2]],runs)
        self.assertEqual(chart.prepared_runs()[0]['curve_points'][0][0],16)
        missing=dict(runs[2],parent_run_id=999)
        chart.set_runs([missing],runs+[missing])
        self.assertEqual(chart.prepared_runs()[0]['curve_points'][0][0],1)
        self.assertEqual(runs,original)
        chart.set_runs(runs)
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf');APP.setFont(QFont('Segoe UI',9))
        chart.resize(900,440);chart.show();APP.processEvents()
        self.assertEqual(chart.data_bounds[1],18)
        chart.grab().save('diagnostics/history_continuation_checked.png')
        chart.close();chart.deleteLater()

if __name__=='__main__':unittest.main()
