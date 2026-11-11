import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QDialog,QMessageBox
from _test_adam import IntegrationTests as Fixture
from protocolparameters import block_at,parse_parameters,import_parameters

DE="""02.11.2026 : 15:42:18
NEUER TRAININGSLAUF - Lauf 22
Fortsetzung von Lauf 21
Optimierungsverfahren: Adam
Gewichte: Automatisch nach Aktivierung
Bias: Xavier/Glorot
Neu initialisieren: Ja
Lernrate: 0,001
Fehlergrenze: 0,0001
Maximale Epochen: 100000
Ziel: Fehlergrenze
Ergebnis: Gestoppt"""
EN="""NEW TRAINING RUN - Run 2
Optimizer: SGD with Momentum
Weights: He
Bias: 0
Reinitialize: No
Learning rate: 0.005
Momentum: 0.8
Error limit: 0.001
Maximum epochs: 5000
Target: 120 epochs"""

class ParameterTests(unittest.TestCase):
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    make_dialog=Fixture.make_dialog

    def test_parser_blocks_languages_invalid(self):
        text='-----\nOther event\n-----\n'+DE+'\n=====\n'+EN+'\n====='
        self.assertEqual(parse_parameters(block_at(text,8))['solver'],'adam')
        en=parse_parameters(EN)
        self.assertEqual(en['momentum'],.8)
        self.assertEqual(en['training_section_epochs'],120)
        for block in ('Other event',DE.replace('Lernrate: 0,001','Lernrate: nan'),
                      DE+'\nLernrate: 0,5',DE.replace('Bias: Xavier/Glorot','')):
            with self.assertRaises(ValueError):parse_parameters(block)

    def test_confirm_cancel_running_and_no_training_state_change(self):
        d=self.make_dialog('sgd');d.execute_training(1,False,shuffle_seed=42)
        settings=d.get_training_settings();state=self.w.capture_training_network_state();run=d.current_run_id
        with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(import_parameters(d,DE,d))
        self.assertEqual(d.get_training_settings(),settings)
        with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Ok):
            self.assertTrue(import_parameters(d,DE,d))
        self.assertEqual(d.solver_combo.currentData(),'adam')
        self.assertEqual(d.learning_rate.value(),.001)
        self.assertEqual(d.maximum_epochs.value(),100000)
        self.assertTrue(d.initialize_network.isChecked())
        self.assertEqual(d.current_run_id,run)
        self.assertEqual(self.w.capture_training_network_state(),state)
        with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Ok):
            self.assertTrue(import_parameters(d,EN,d))
        self.assertEqual(d.solver_combo.currentData(),'sgd')
        self.assertEqual(d.epoch_count.value(),120)
        d.is_training=True
        try:self.assertFalse(import_parameters(d,DE,d))
        finally:d.is_training=False
        with patch.object(QMessageBox,'warning') as warning:
            self.assertFalse(import_parameters(d,DE.replace('0,001','10000'),d))
            warning.assert_called_once()

    def test_menu_only_from_training_dialog(self):
        d=self.make_dialog()
        with patch('protocolparameters.install_parameter_menu') as install,patch.object(QDialog,'exec',return_value=QDialog.DialogCode.Rejected):
            self.w.open_training_protocol()
            install.assert_not_called()
            d.open_training_protocol()
            self.assertIs(install.call_args.args[1],d)

if __name__=='__main__':unittest.main()
