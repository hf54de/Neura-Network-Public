import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from binarystatecolors import state_palette
from forwardcalibrationdialog import BinaryToggleButton, BinaryStateLabel
from graphicalexperimentdialog import GraphicalExperimentDialog
from language import LanguageManager
from projectio import ProjectIO
from settingsprofile import SettingsProfile
from settings import Settings
from _test_training_comparison import make_dialog
from trainingdataio import TrainingDataIO
from networktestdialog import NetworkTestDialog


class BinaryColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_widgets_and_legacy(self):
        colors = dict(binary_state_on="#123456", binary_state_off="#ffeedd")
        language = LanguageManager("de")
        toggle = BinaryToggleButton(language, color_settings=colors)
        label = BinaryStateLabel(language, color_settings=colors)
        for state, color in ((True, "#123456"), (False, "#ffeedd")):
            toggle.setChecked(state); label.set_state(state)
            self.assertIn(color, toggle.styleSheet())
            self.assertIn(color, label.styleSheet())
            self.assertEqual(toggle.numeric_value(), float(state))
        self.assertIn("#eef1f3", BinaryToggleButton(language).styleSheet())
        self.assertEqual(state_palette({}, True, ("a", "b", "c")), ("a", "b", "c"))
        self.assertEqual(state_palette(colors, True, ("", "", ""))[2], "#ffffff")
        self.assertEqual(state_palette(colors, False, ("", "", ""))[2], "#111111")
        display = ProjectIO.normalize_display_settings({"colors": {"canvas_background": "#ffffff"}})
        ProjectIO._validate_display_settings_data(display)
        display["colors"].update(colors)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Colors.json"
            SettingsProfile.write(path, SettingsProfile.build(display, Settings.default_ui_settings()))
            self.assertEqual(SettingsProfile.read(path)["display"], display)

    def test_application_inputs_and_outputs(self):
        parent, training = make_dialog()
        network = training.network
        doc = TrainingDataIO.create_empty_document(1, 1, "Test")
        for column, neuron in zip(doc["columns"], network.get_neurons()):
            column.update(mapped_neuron_id=neuron.id, mapped_neuron_name=neuron.name, data_type="binary")
        doc["records"] = [[0., 0.], [1., 1.]]
        _, inputs, outputs = NetworkTestDialog.prepare_document(network, doc, data_label="Test")
        colors = dict(binary_state_on="#123456", binary_state_off="#ffeedd")
        with patch.object(GraphicalExperimentDialog, "calculate"), patch.object(GraphicalExperimentDialog, "update_selection_actions"):
            dialog = GraphicalExperimentDialog(network, inputs, outputs, color_settings=colors, language_manager=LanguageManager("de"))
            for state, color in ((True, "#123456"), (False, "#ffeedd")):
                for _, controls, _ in dialog.input_cards:
                    controls["editor"].setChecked(state)
                    self.assertIn(color, controls["editor"].styleSheet())
                for _, _, mapping in dialog.output_cards:
                    mapping["neuron"].output_value = float(state)
                dialog.update_forward_result_widgets()
                for _, controls, _ in dialog.output_cards:
                    self.assertIn(color, controls["led"].styleSheet())
                    self.assertIn(color, controls["state_label"].styleSheet())
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
