"""Enable_Out is an optional, unconditional pass-through in every PLC format."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from _test_training_comparison import make_dialog
from trainingdataio import TrainingDataIO
from networktestdialog import NetworkTestDialog
from gxworks2export import GxWorks2ExportGenerator
from gxworks3export import GxWorks3ExportGenerator, GxWorks3XmlExportGenerator
from iec61131export import Iec61131ExportGenerator
from plcexportsettings import PlcExportSettingsPanel
from fbpreview import FunctionBlockPreview, FunctionBlockPreviewPanel
from plcfileexport import GxWorks2AscExporter, GxWorks3XmlExporter, Iec61131XmlExporter


class EnableOutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dependency(self):
        panel = PlcExportSettingsPanel("FB_Test", "1")
        self.assertFalse(panel.export_options()["enable_out"])
        panel.enable.setChecked(True)
        panel.enable_out.setChecked(True)
        self.assertTrue(panel.export_options()["enable_out"])
        panel.enable.setChecked(False)
        self.assertFalse(panel.enable_out.isEnabled())
        self.assertFalse(panel.export_options()["enable_out"])
        panel.enable.setChecked(True)
        self.assertTrue(panel.export_options()["enable_out"])
        self.assertEqual("Optionen", panel.options_toggle.text())

    def test_generators_preview_and_serialization(self):
        parent, training = make_dialog()
        network = training.network
        document = TrainingDataIO.create_empty_document(1, 1, "Test")
        for column, neuron in zip(document["columns"], network.get_neurons()):
            column.update(mapped_neuron_id=neuron.id, mapped_neuron_name=neuron.name)
        document["records"] = [[0., 0.], [1., 1.]]
        _, inputs, outputs = NetworkTestDialog.prepare_document(network, document, data_label="Test")
        for generator, exporter in ((GxWorks2ExportGenerator, GxWorks2AscExporter),
                                    (GxWorks3ExportGenerator, Iec61131XmlExporter),
                                    (GxWorks3XmlExportGenerator, GxWorks3XmlExporter),
                                    (Iec61131ExportGenerator, Iec61131XmlExporter)):
            for enabled, output in ((True, True), (False, True), (True, False)):
                data = generator(network, inputs, outputs, export_options={"enable": enabled, "enable_out": output, "network_active": True, "range_check": True, "range_error": True}).generate()
                pins = FunctionBlockPreview(data["headers"], data["declarations"])._pins("VAR_OUTPUT")
                code = data["code"]
                if enabled and output:
                    self.assertEqual(pins[0], ("Enable_Out", "BOOL"))
                    self.assertEqual(code.count("Enable_Out := Enable;"), 1)
                    self.assertLess(code.index("Enable_Out := Enable;"), code.index("Input_Range_Error := FALSE;"))
                    self.assertLess(code.index("Enable_Out := Enable;"), code.index("IF Enable AND"))
                    serialized = exporter.build(data["fb_name"], data["headers"], data["declarations"], code)
                    self.assertIn("Enable_Out := Enable;", serialized)
                    self.assertLess(serialized.index("Enable_Out"), serialized.index("Network_Active"))
                else:
                    self.assertNotIn("Enable_Out", code)
                    self.assertFalse(any(name == "Enable_Out" for name, _ in pins))

    def test_help(self):
        for german in (True, False):
            with patch("fbpreview.show_yellow_information_dialog") as show:
                FunctionBlockPreviewPanel.show_connection_help(SimpleNamespace(german=german))
                self.assertIn("Enable_Out", show.call_args.args[2])
                self.assertTrue(show.call_args.kwargs["scrollable"])


if __name__ == "__main__":
    unittest.main()
