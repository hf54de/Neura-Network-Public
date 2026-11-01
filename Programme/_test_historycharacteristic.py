import unittest
from copy import deepcopy
from PySide6.QtGui import QFont,QFontDatabase
from _test_adam import APP,IntegrationTests
from _test_review_fixes import document
from traininghistorydialog import TrainingHistoryDialog

class HistoryCharacteristicTests(unittest.TestCase):
    setUp=IntegrationTests.setUp
    tearDown=IntegrationTests.tearDown
    make_dialog=IntegrationTests.make_dialog

    def test_saved_state_and_selection(self):
        dialog=self.make_dialog()
        self.w.training_data_manager.set_document(document())
        dialog.execute_training(2,False,shuffle_seed=42)
        entry=deepcopy(self.w.training_history[-1])
        before=deepcopy(self.w.capture_training_network_state())
        source=self.w.history_characteristic_source(entry)
        self.assertIsNotNone(source)
        h=TrainingHistoryDialog([entry],language_manager=self.w.language,
            characteristic_provider=self.w.history_characteristic_source)
        try:
            h.metric_combo.setCurrentIndex(h.metric_combo.findData('characteristic'))
            h.table.selectRow(0)
            view=h.characteristic_view
            self.assertFalse(view.plot.isHidden(),view.notice.text())
            first=list(view.plot.curve_points)
            self.assertEqual(len(first),101)
            modified=deepcopy(entry)
            modified['network_state']['connections'][0]['weight']+=.5
            view.set_runs([modified])
            self.assertNotEqual(view.plot.curve_points,first)
            self.assertEqual(self.w.capture_training_network_state(),before)
            view.set_runs([entry,modified])
            self.assertFalse(view.notice.isHidden())
            self.assertEqual(view.notice.text(),self.w.language.text('trajectory.select_one'))
            view.set_runs([dict(entry,invalidated_reason='data')])
            self.assertFalse(view.notice.isHidden())
            self.assertTrue(view.plot.isHidden())
            view.set_runs([entry])
            QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
            APP.setFont(QFont('Segoe UI',9))
            h.resize(1100,800);h.show();APP.processEvents()
            h.grab().save('diagnostics/history_characteristic_checked.png')
        finally:h.close();h.deleteLater()

    def test_multiple_outputs_and_ineligible_inputs(self):
        from historycharacteristic import HistoryCharacteristic
        from neuron import Neuron
        from neurontype import NeuronType
        from connection import Connection
        dialog=self.make_dialog()
        self.w.training_data_manager.set_document(document())
        dialog.execute_training(1,False,shuffle_seed=42)
        entry=self.w.training_history[-1]
        net,source=self.w.history_characteristic_source(entry)
        extra=Neuron(999,0,0,"Second output")
        extra.neuron_type=NeuronType.OUTPUT
        extra.activation_function="Linear"
        net.add_neuron(extra)
        net.add_connection(Connection(999,source['inputs'][0]['neuron'],extra,.8))
        mapping=dict(source['outputs'][0],neuron=extra)
        source['outputs'].append(mapping)
        view=HistoryCharacteristic(self.w.language,lambda run:(net,source))
        try:
            view.set_runs([entry])
            self.assertEqual(view.output.count(),2)
            first=list(view.plot.curve_points)
            view.output.setCurrentIndex(1)
            self.assertNotEqual(view.plot.curve_points,first)
            source['inputs'][0]['data_type']='binary'
            view.refresh()
            self.assertTrue(view.plot.isHidden())
            self.assertEqual(view.notice.text(),self.w.language.text('training.characteristic.unavailable'))
            source['inputs'][0]['data_type']='analog'
            added=Neuron(998,0,0,"Second input");added.neuron_type=NeuronType.INPUT
            net.add_neuron(added)
            view.refresh()
            self.assertTrue(view.plot.isHidden())
        finally:view.deleteLater()

if __name__=='__main__':unittest.main()
