"""Regression checks for export-only pruning, including live dialog regeneration."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from xml.etree import ElementTree as ET
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLocale, QPoint, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtGui import QFont, QFontDatabase
from connection import Connection
from neuron import Neuron
from neurontype import NeuronType
from network import NeuralNetwork
from gxworks2export import GxWorks2ExportGenerator
from gxworks3export import GxWorks3XmlExportGenerator
from iec61131export import Iec61131ExportGenerator
from plcfileexport import Iec61131XmlExporter
from spsexportdialog import SpsExportDialog
from xmlexportdialog import XmlExportDialog


app = QApplication([])
# The Windows offscreen platform may not discover installed fonts automatically.
font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
if font_id >= 0:
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 9))
network = NeuralNetwork()
inputs = [Neuron(i, 0, i * 60, f"Input_{i}") for i in range(1, 6)]
output = Neuron(6, 200, 0, "Output")
output.neuron_type = NeuronType.OUTPUT
output.activation_function = "Sigmoid"
output.bias = 0.25
for neuron in inputs:
    neuron.neuron_type = NeuronType.INPUT
for neuron in inputs + [output]:
    network.add_neuron(neuron)
weights = [0.0, 0.001, -0.001, 0.002, -0.002]
for i, (neuron, weight) in enumerate(zip(inputs, weights)):
    network.add_connection(Connection(i + 1, neuron, output, weight))
input_mappings = [{"neuron": n, "column_name": n.name} for n in inputs]
output_mappings = [{"neuron": output, "column_name": output.name}]


def build(cls, options=None):
    return cls(network, input_mappings, output_mappings,
               export_options=options).generate()


for cls in (GxWorks2ExportGenerator, GxWorks3XmlExportGenerator, Iec61131ExportGenerator):
    original = build(cls)
    pruned = build(cls, {"pruning_enabled": True, "pruning_threshold": 0.001})
    assert original["operation_summary"]["multiplications"] == 5
    assert pruned["operation_summary"]["multiplications"] == 2
    assert pruned["operation_summary"]["pruned_connections"] == 3
    for i in (1, 2, 3):
        assert f"W_N_{i}_N_6" not in pruned["code"]
    assert len(pruned["declarations"]) == len(original["declarations"]) - 3
    assert pruned["model_signature"] != original["model_signature"]
    assert build(cls, {"pruning_enabled": False})["model_signature"] == original["model_signature"]
    assert build(cls, {"pruning_enabled": True, "pruning_threshold": 0})["operation_summary"]["pruned_connections"] == 1
    all_pruned = build(cls, {"pruning_enabled": True, "pruning_threshold": 1})
    assert all_pruned["operation_summary"]["multiplications"] == 0
    assert ":=\r\n      B_N_6;" in all_pruned["code"]
    assert "EXP(" in all_pruned["code"]
    assert [c.weight for c in network.get_connections()] == weights
    assert len(output.incoming_connections) == 5 and output.bias == 0.25

for threshold in (-1, float("nan"), float("inf")):
    try:
        build(Iec61131ExportGenerator, {"pruning_enabled": True, "pruning_threshold": threshold})
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid threshold accepted")

data = build(Iec61131ExportGenerator, {"pruning_enabled": True})
xml = Iec61131XmlExporter.build(data["fb_name"], data["headers"], data["declarations"], data["code"])
ET.fromstring(xml)
for dialog_cls, generator_cls in ((SpsExportDialog, GxWorks2ExportGenerator),
                                  (XmlExportDialog, Iec61131ExportGenerator),
                                  (XmlExportDialog, GxWorks3XmlExportGenerator)):
    def regenerate(options, version):
        return build(generator_cls, options)
    data = build(generator_cls)
    data["regenerate_export"] = regenerate
    dialog = dialog_cls(data)
    panel = dialog.settings_panel
    assert not panel.pruning.isChecked() and not panel.pruning_threshold.isEnabled()
    panel.pruning.setChecked(True)
    assert panel.pruning_threshold.isEnabled()
    info = dialog.operation_info_text if dialog_cls is XmlExportDialog else dialog.operation_info_label.text()
    assert len(info.splitlines()) == 3
    assert "Gewichte 5 → 2" in info
    assert "MUL 5 → 2" in info and "ADD 6 → 3" in info
    assert "kB" in info and "%" in info
    panel.pruning_threshold.setLocale(QLocale("de_DE"))
    assert panel.pruning_threshold.text() == "0,001"
    panel.pruning_threshold.setValue(0.00001)
    assert panel.pruning_threshold.text() == "0,00001"
    panel.pruning_threshold.setValue(0.001)
    dialog.show()
    app.processEvents()
    assert panel.pruning.mapTo(panel, QPoint()).x() == panel.enable.mapTo(panel, QPoint()).x()
    if generator_cls is Iec61131ExportGenerator:
        from pathlib import Path
        output_dir = Path(__file__).parent / "export_test"
        output_dir.mkdir(exist_ok=True)
        dialog.grab().save(str(output_dir / "pruning_comparison.png"))
    # Enter in the field must commit without clicking the default help button.
    panel.info_button.clicked.disconnect()
    help_clicks = QSignalSpy(panel.info_button.clicked)
    editor = panel.pruning_threshold.lineEdit()
    editor.setFocus()
    editor.selectAll()
    QTest.keyClicks(editor, "0,00001")
    QTest.qWait(400)
    assert panel.pruning_threshold.value() == 0.00001
    info = dialog.operation_info_text if dialog_cls is XmlExportDialog else dialog.operation_info_label.text()
    assert "Gewichte 5 → 4" in info
    editor.selectAll()
    QTest.keyClicks(editor, "1")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert panel.pruning_threshold.value() == 1
    assert help_clicks.count() == 0
    info = dialog.operation_info_text if dialog_cls is XmlExportDialog else dialog.operation_info_label.text()
    assert "Gewichte 5 → 0" in info
    panel.pruning.setChecked(False)
    info = dialog.operation_info_text if dialog_cls is XmlExportDialog else dialog.operation_info_label.text()
    assert "Pruning: aus" in info and len(info.splitlines()) == 3
    assert "Vergleich ohne" not in info
    # No omitted weights: the active comparison must explicitly report no savings.
    for connection in network.get_connections():
        connection.weight = 0.01
    panel.pruning_threshold.setValue(0)
    panel.pruning.setChecked(True)
    info = dialog.operation_info_text if dialog_cls is XmlExportDialog else dialog.operation_info_label.text()
    assert "Keine Einsparung" in info and len(info.splitlines()) == 3
    for connection, weight in zip(network.get_connections(), weights):
        connection.weight = weight
    panel.pruning.setChecked(False)
    assert "8 von 8" in panel.options_toggle.text()
    dialog.close()

print("PLC pruning: generator, XML and dialog regression checks passed")
