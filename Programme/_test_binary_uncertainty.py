import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from binaryuncertainty import normalize_limits, is_uncertain
from forwardcalibrationdialog import BinaryStateLabel, ForwardCalibrationDialog
from graphicalexperimentdialog import GraphicalExperimentDialog
from settingsdialog import SettingsDialog
from settings import Settings
from settingsprofile import SettingsProfile
from projectio import ProjectIO
from language import LanguageManager
from _test_training_comparison import make_dialog
from trainingdataio import TrainingDataIO
from networktestdialog import NetworkTestDialog
from gxworks2export import GxWorks2ExportGenerator
from gxworks3export import GxWorks3ExportGenerator, GxWorks3XmlExportGenerator
from iec61131export import Iec61131ExportGenerator
from plcexportsettings import PlcExportSettingsPanel
from plcfileexport import GxWorks2AscExporter, GxWorks3XmlExporter, Iec61131XmlExporter


class UncertaintyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def fixture(self):
        parent, training = make_dialog()
        doc = TrainingDataIO.create_empty_document(1, 1, "Test")
        for column, neuron in zip(doc["columns"], training.network.get_neurons()):
            column.update(mapped_neuron_id=neuron.id, mapped_neuron_name=neuron.name, data_type="binary")
        doc["records"] = [[0., 0.], [1., 1.]]
        _, inputs, outputs = NetworkTestDialog.prepare_document(training.network, doc, data_label="Test")
        return parent, training, inputs, outputs

    def test_boundaries_and_invalid_limits(self):
        for value, expected in ((0, False), (.3, False), (.3001, True), (.5, True), (.6999, True), (.7, False), (1, False)):
            self.assertEqual(is_uncertain(value), expected)
        for limits in ({"lower": .5}, {"upper": .5}, {"lower": -.1}, {"upper": 1.1}, {"lower": float("nan")}, {"lower": True}):
            with self.assertRaises(ValueError):
                normalize_limits(limits)
        self.assertFalse(is_uncertain(.35, {"lower": .4, "upper": .6}))

    def test_settings_and_profiles(self):
        display = ProjectIO.normalize_display_settings({"colors": {}})
        dialog = SettingsDialog(display, display, Settings.default_ui_settings(), Settings.default_ui_settings(), LanguageManager("de"))
        dialog.uncertainty_lower.setValue(.4)
        dialog.uncertainty_upper.setValue(.6)
        data = SettingsProfile.validate(SettingsProfile.build(dialog.project_settings(), dialog.ui_settings()))
        self.assertEqual(data["display"]["binary_uncertainty"], {"lower": .4, "upper": .6})
        self.assertIn("binary_state_uncertain", data["display"]["colors"])

    def test_status_and_application(self):
        for language in ("de", "en"):
            label = BinaryStateLabel(LanguageManager(language), color_settings={"binary_state_uncertain": "#ffee00"})
            label.set_state(False, True, "diagnostic")
            self.assertIn("⚠", label.text())
            self.assertIn("#ffee00", label.styleSheet())
            label.set_state(True)
            self.assertNotIn("⚠", label.text())
        parent, training, inputs, outputs = self.fixture()
        with patch.object(GraphicalExperimentDialog, "calculate"), patch.object(GraphicalExperimentDialog, "update_selection_actions"):
            dialog = GraphicalExperimentDialog(training.network, inputs, outputs, language_manager=LanguageManager("de"), uncertainty_settings={"lower": .4, "upper": .6})
            for value in (.4, .48, .5, .52, .6):
                for _, _, mapping in dialog.output_cards:
                    mapping["neuron"].output_value = value
                dialog.update_forward_result_widgets()
                for proxy, controls, _ in dialog.output_cards:
                    uncertain = .4 < value < .6
                    self.assertEqual("⚠" in controls["state_label"].text(), uncertain)
                    self.assertEqual("#ffd966" in controls["value"].styleSheet(), uncertain)
                    self.assertIn("Ein", controls["state_label"].text())
                    self.assertEqual(
                        controls["state_label"].isChecked(), value > .5
                    )
                    dialog.set_binary_output_intermediate_value(proxy, True, record_history=False)
                    self.assertEqual(bool(controls["value"].toolTip()), uncertain)
            dialog.deleteLater()

    def test_export_gating_and_reset(self):
        parent, training, inputs, outputs = self.fixture()
        for generator in (GxWorks2ExportGenerator, GxWorks3ExportGenerator, GxWorks3XmlExportGenerator, Iec61131ExportGenerator):
            for enable, range_check in ((True, True), (False, False)):
                data = generator(training.network, inputs, outputs, export_options={"binary_uncertainty": True,
                    "uncertain_output_number": True, "uncertainty_lower": .4, "uncertainty_upper": .6,
                    "enable": enable, "range_check": range_check, "network_active": False}).generate()
                name_column = data["headers"].index("Label Name")
                names = {row[name_column] for row in data["declarations"]}
                self.assertTrue({"Binary_Output_Uncertain", "Uncertain_Output_Number"} <= names)
                code = data["code"]
                self.assertIn("> 0.400000000", code)
                self.assertIn("< 0.600000000", code)
                self.assertIn("Uncertain_Output_Number := 1;", code)
                self.assertNotIn("Network_Active", names)
                self.assertNotIn("Network_Active", code)
                self.assertLess(code.index("Binary_Output_Uncertain := FALSE;"), code.index("Binary_Output_Uncertain := TRUE;"))
                if enable:
                    self.assertLess(code.index("Uncertain_Output_Number := 0;"), code.index("IF Enable AND"))
                self.assertIn("> 0.5 THEN", code)
                exporter = GxWorks2AscExporter if generator is GxWorks2ExportGenerator else (GxWorks3XmlExporter if generator is GxWorks3XmlExportGenerator else Iec61131XmlExporter)
                serialized = exporter.build(data["fb_name"], data["headers"], data["declarations"], code)
                self.assertIn("Binary_Output_Uncertain", serialized)
                self.assertIn("Uncertain_Output_Number", serialized)
            for diagnostic in (False, True):
                status = generator(training.network, inputs, outputs, export_options={
                    "network_active": True, "binary_uncertainty": diagnostic}).generate()
                self.assertIn("Network_Active := TRUE;", status["code"])
            disabled = generator(training.network, inputs, outputs).generate()
            self.assertNotIn("Binary_Output_Uncertain", disabled["code"])
        panel = PlcExportSettingsPanel("Test", "1")
        panel.binary_uncertainty.setChecked(True)
        self.assertFalse(panel.export_options()["network_active"])
        self.assertTrue(panel.network_active.isEnabled())
        panel.network_active.setChecked(True)
        self.assertTrue(panel.export_options()["network_active"])
        panel.network_active.setChecked(False)
        self.assertFalse(panel.export_options()["network_active"])
        panel.set_export_options(dict(binary_uncertainty=True, uncertainty_lower=.4, uncertainty_upper=.6))
        self.assertEqual(panel.export_options()["uncertainty_lower"], 0.4)

    def test_forward_both_views(self):
        parent, training, inputs, outputs = self.fixture()
        network = training.network
        dialog = ForwardCalibrationDialog(network, inputs, outputs, language_manager=LanguageManager("de"),
            uncertainty_settings={"lower": .4, "upper": .6}, color_settings={"binary_state_uncertain": "#ffee00"})
        for value in (.4, .48, .5, .52, .6):
            def forward():
                for mapping in outputs:
                    mapping["neuron"].output_value = value
            with patch.object(network, "forward_pass", side_effect=forward):
                dialog.calculate()
                for data in dialog.output_widgets:
                    uncertain = .4 < value < .6
                    self.assertEqual("⚠" in data["state_label"].text(), uncertain)
                    self.assertEqual("#ffee00" in data["raw_label"].styleSheet(), uncertain)
                    self.assertEqual("#ffee00" in data["internal_label"].styleSheet(), uncertain)
                dialog.toggle_binary_view()
                self.assertEqual("⚠" in dialog.output_widgets[0]["state_label"].text(), .4 < value < .6)
        dialog.deleteLater()

    def test_multiple_outputs_and_analog_exclusion(self):
        from neuron import Neuron
        from neurontype import NeuronType
        from connection import Connection
        parent, training, inputs, outputs = self.fixture()
        outputs[0]["data_type"] = "analog"
        for identifier in (3, 4):
            neuron = Neuron(identifier, 300, identifier * 100, f"Binary_{identifier}")
            neuron.neuron_type = NeuronType.OUTPUT
            training.network.add_neuron(neuron)
            training.network.add_connection(Connection(identifier, inputs[0]["neuron"], neuron, weight=.1))
            outputs.append(dict(outputs[0], neuron=neuron, data_type="binary", column_name=f"Binary_{identifier}"))
        data = Iec61131ExportGenerator(training.network, inputs, outputs,
            export_options={"binary_uncertainty": True, "uncertain_output_number": True}).generate()
        code = data["code"]
        self.assertEqual(code.count("Binary_Output_Uncertain := TRUE;"), 2)
        self.assertNotIn("Uncertain_Output_Number := 1;", code)
        self.assertIn("Uncertain_Output_Number := 2;", code)
        self.assertIn("Uncertain_Output_Number := 3;", code)
        self.assertEqual(code.count("IF Uncertain_Output_Number = 0 THEN"), 2)
        outputs[1]["data_type"] = outputs[2]["data_type"] = "analog"
        data = Iec61131ExportGenerator(training.network, inputs, outputs,
            export_options={"binary_uncertainty": True}).generate()
        self.assertNotIn("Binary_Output_Uncertain := TRUE;", data["code"])
        self.assertNotIn("Uncertain_Output_Number", data["code"])


if __name__ == "__main__":
    unittest.main()
