"""2D recording workflow, persistence and unchanged SGD/Adam calculations."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox
from _test_adam import APP, IntegrationTests, build
from _test_review_fixes import language
from weighttrajectory import WeightSelectionDialog, validate_trajectory
from traininghistorydialog import TrainingHistoryDialog
from projectio import ProjectIO


class TrajectoryTests(unittest.TestCase):
    setUp = IntegrationTests.setUp
    tearDown = IntegrationTests.tearDown
    make_dialog = IntegrationTests.make_dialog

    def enable(self, dialog):
        with patch.object(WeightSelectionDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
            dialog.record_weight_trajectory.setChecked(True)
        self.assertTrue(dialog.record_weight_trajectory.isChecked())
        self.assertEqual(len(set(dialog.weight_trajectory_pair)),2)

    def test_selection_default_distinct_axes_cancel_and_accept(self):
        net,_=build()
        for code in ('de','en'):
            selection=WeightSelectionDialog(net,language(code))
            try:
                pair=selection.pair();connections={c.id:c for c in net.get_connections()}
                self.assertNotEqual(*pair)
                self.assertIs(connections[pair[0]].target_neuron,connections[pair[1]].target_neuron)
                selection.y_combo.setCurrentIndex(selection.x_combo.currentIndex())
                self.assertFalse(selection.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
            finally:selection.deleteLater()
        dialog=self.make_dialog()
        with patch.object(WeightSelectionDialog,'exec',return_value=QDialog.DialogCode.Rejected):
            dialog.record_weight_trajectory.setChecked(True)
        self.assertFalse(dialog.record_weight_trajectory.isChecked())
        self.enable(dialog)

    def check_calculation_unchanged(self,solver):
        dialog=self.make_dialog(solver);dialog.momentum.setValue(.8)
        dialog.execute_training(5,False,shuffle_seed=42)
        self.assertIsNone(dialog.current_run_weight_trajectory)
        self.assertNotIn('weight_trajectory',self.w.training_history[-1])
        expected=deepcopy(self.w.capture_training_network_state())
        errors=deepcopy(dialog.history_curve_points)
        self.enable(dialog);dialog.select_training_target('epochs');dialog.epoch_count.setValue(5)
        dialog.error_metric_combo.setCurrentIndex(dialog.error_metric_combo.findData('trajectory'))
        dialog.repeat_with_same_initialization()
        self.assertEqual(self.w.capture_training_network_state(),expected)
        self.assertEqual(dialog.history_curve_points,errors)
        data=dialog.current_run_weight_trajectory
        self.assertEqual(len(data['points']),6)
        self.assertEqual([p[0] for p in data['points']],list(range(6)))
        self.assertEqual([p[3] for p in data['points'][1:]],[v for _,v in errors])
        validate_trajectory(data,5,dialog.current_run_initial_state)
        self.assertEqual(self.w.training_history[-1]['weight_trajectory'],data)
        self.assertIsNot(self.w.training_history[-1]['weight_trajectory'],data)

    def test_sgd_recording_does_not_change_training(self):
        self.check_calculation_unchanged('sgd')

    def test_adam_recording_does_not_change_training(self):
        self.check_calculation_unchanged('adam')

    def test_live_recording_continues_across_chart_changes(self):
        dialog=self.make_dialog();self.enable(dialog)
        original=dialog.train_epoch
        def epoch(number,total):
            self.assertFalse(dialog.record_weight_trajectory.isEnabled())
            self.assertFalse(dialog.weight_pair_button.isEnabled())
            self.assertEqual(len(dialog.current_run_weight_trajectory['points']),number)
            metric=('trajectory','mse','maximum')[number-1]
            dialog.error_metric_combo.setCurrentIndex(dialog.error_metric_combo.findData(metric))
            if metric=='trajectory':
                self.assertFalse(dialog.weight_trajectory_plot.isHidden())
                self.assertTrue(dialog.error_chart.isHidden())
            return original(number,total)
        with patch.object(dialog,'train_epoch',side_effect=epoch):dialog.execute_training(3,False,shuffle_seed=42)
        self.assertEqual(len(dialog.current_run_weight_trajectory['points']),4)
        dialog.error_metric_combo.setCurrentIndex(dialog.error_metric_combo.findData('trajectory'))
        self.assertEqual(dialog.weight_trajectory_plot.data,dialog.current_run_weight_trajectory)
        self.assertTrue(dialog.record_weight_trajectory.isEnabled())

    def test_save_reopen_continue_keeps_pair_and_prefix(self):
        dialog=self.make_dialog();self.enable(dialog);dialog.execute_training(3,False,shuffle_seed=42)
        before=deepcopy(dialog.current_run_weight_trajectory);run=dialog.current_run_id
        self.w.training_dialog_finished(dialog);self.dialog=None
        APP.processEvents();APP.sendPostedEvents(None,QEvent.Type.DeferredDelete);APP.processEvents()
        self.assertTrue(self.w.write_project_file(str(self.file)))
        self.w.project_modified=False;self.w.open_project(str(self.file));self.w.open_training_dialog()
        dialog=self.dialog=self.w.training_dialog
        self.assertEqual(dialog.current_run_weight_trajectory,before)
        self.assertTrue(dialog.record_weight_trajectory.isChecked())
        # Changes to the next-run options cannot alter an existing run's pair.
        dialog.weight_trajectory_pair=list(reversed(dialog.weight_trajectory_pair))
        dialog.record_weight_trajectory.setChecked(False)
        dialog.maximum_epochs.setValue(10);dialog.select_training_target('epochs');dialog.epoch_count.setValue(2)
        dialog.continue_selected_training()
        after=dialog.current_run_weight_trajectory
        self.assertEqual(dialog.current_run_id,run)
        self.assertEqual(after['connections'],before['connections'])
        self.assertEqual(after['points'][:4],before['points'])
        self.assertEqual(len(after['points']),6)
        self.assertEqual(dialog.weight_trajectory_pair,[c['id'] for c in before['connections']])
        self.assertTrue(dialog.record_weight_trajectory.isChecked())
        self.assertTrue(self.w.write_project_file(str(self.file)))

    def test_unrecorded_continuation_does_not_invent_earlier_points(self):
        dialog=self.make_dialog();dialog.execute_training(2,False,shuffle_seed=42)
        self.enable(dialog);dialog.execute_training(1,False,continue_existing=True)
        self.assertIsNone(dialog.current_run_weight_trajectory)
        self.assertNotIn('weight_trajectory',self.w.training_history[-1])
        self.assertFalse(dialog.record_weight_trajectory.isChecked())

    def test_new_solver_and_repeat_create_separate_paths(self):
        dialog=self.make_dialog();self.enable(dialog);dialog.execute_training(2,False,shuffle_seed=42)
        first=deepcopy(self.w.training_history[-1]);original=first['weight_trajectory']
        dialog.solver_combo.setCurrentIndex(dialog.solver_combo.findData('sgd'))
        dialog.select_training_target('one');dialog.continue_selected_training()
        second=deepcopy(self.w.training_history[-1])
        self.assertEqual(second['parent_run_id'],first['run_id'])
        self.assertEqual(second['weight_trajectory']['points'][0][1:3],original['points'][-1][1:3])
        self.assertEqual(len(second['weight_trajectory']['points']),2)
        dialog.repeat_with_same_initialization()
        self.assertIsNone(dialog.current_run_parent_id)
        self.assertEqual(dialog.current_run_weight_trajectory['points'][0],second['weight_trajectory']['points'][0])
        self.assertEqual(self.w.training_history[0]["weight_trajectory"],original)
        self.assertEqual(self.w.training_history[0]["network_state"],first["network_state"])

    def test_failed_training_restores_recording(self):
        dialog=self.make_dialog();self.enable(dialog);dialog.execute_training(2,False,shuffle_seed=42)
        before=deepcopy(dialog.current_run_weight_trajectory)
        net=deepcopy(self.w.capture_training_network_state())
        original=dialog.train_epoch
        def fail(epoch,total):
            if epoch==4:raise ValueError('Injected failure')
            return original(epoch,total)
        with patch.object(dialog,'train_epoch',side_effect=fail),patch.object(QMessageBox,'warning'):
            dialog.execute_training(2,False,continue_existing=True)
        self.assertEqual(dialog.current_run_weight_trajectory,before)
        self.assertEqual(self.w.capture_training_network_state(),net)
        self.assertEqual(dialog.weight_trajectory_plot.data,before)

    def test_history_single_multi_missing_and_delete_restore(self):
        dialog=self.make_dialog();dialog.execute_training(1,False,shuffle_seed=42)
        unrecorded=dialog.current_run_id
        self.enable(dialog);dialog.execute_training(2,False,shuffle_seed=42)
        recorded=dialog.current_run_id;data=deepcopy(dialog.current_run_weight_trajectory)
        history=TrainingHistoryDialog(self.w.training_history,language_manager=self.w.language)
        try:
            history.metric_combo.setCurrentIndex(history.metric_combo.findData('trajectory'))
            history.table.clearSelection();history.table.selectRow(0)
            self.assertEqual(history.weight_trajectory_plot.data,data)
            history.table.selectAll()
            self.assertIsNone(history.weight_trajectory_plot.data)
            self.assertEqual(history.weight_trajectory_plot.message,self.w.language.text('trajectory.select_one'))
            history.table.clearSelection();history.table.selectRow(1)
            self.assertIsNone(history.weight_trajectory_plot.data)
            self.assertEqual(history.weight_trajectory_plot.message,self.w.language.text('trajectory.no_data'))
        finally:history.deleteLater()
        with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Yes):
            dialog.load_previous_training_run(delete_run_id=recorded)
        self.assertEqual(dialog.current_run_id,unrecorded)
        self.assertIsNone(dialog.current_run_weight_trajectory)
        self.assertFalse(dialog.record_weight_trajectory.isChecked())

    def test_invalid_saved_trajectory_rejected_before_editor_changes(self):
        dialog=self.make_dialog();self.enable(dialog);dialog.execute_training(2,False,shuffle_seed=42)
        self.assertTrue(self.w.write_project_file(str(self.file)))
        saved=json.loads(self.file.read_text(encoding='utf-8'))
        before=deepcopy(self.w.capture_training_network_state());self.w.training_dialog=None
        mutations=[lambda d:d['points'].pop(),lambda d:d['points'][1].__setitem__(1,float('nan')),
                   lambda d:d['connections'].__setitem__(1,deepcopy(d['connections'][0])),
                   lambda d:d['points'][0].__setitem__(1,12345.)]
        for mutate in mutations:
            bad=deepcopy(saved);mutate(bad['training_history'][0]['weight_trajectory'])
            self.file.write_text(json.dumps(bad),encoding='utf-8');self.w.project_modified=False
            with patch.object(QMessageBox,'critical') as error:
                self.w.open_project(str(self.file));error.assert_called_once()
            self.assertEqual(self.w.capture_training_network_state(),before)

    def test_old_project_defaults_to_no_recording(self):
        self.assertTrue(self.w.write_project_file(str(self.file)))
        saved=json.loads(self.file.read_text(encoding='utf-8'));saved['version']=16
        for key in ('record_weight_trajectory','weight_trajectory_pair'):saved['training_settings'].pop(key,None)
        self.file.write_text(json.dumps(saved),encoding='utf-8')
        loaded=ProjectIO.load_project(str(self.file))
        self.assertFalse(loaded['training_settings']['record_weight_trajectory'])
        self.assertIsNone(loaded['training_settings']['weight_trajectory_pair'])


if __name__=='__main__':unittest.main()
