"""Analytical MSE, scaling, cancellation and export-dialog quality checks."""
import math
from types import SimpleNamespace as NS
from _test_plc_pruning import (
    app, network, inputs, output, input_mappings, output_mappings, build,
    Iec61131ExportGenerator, XmlExportDialog, SpsExportDialog, GxWorks2ExportGenerator,
)
from PySide6.QtTest import QTest
from plcquality import PruningQualitySnapshot, PruningQualityPanel
from neurontype import NeuronType


def finish(job):
    try:
        while True:
            next(job)
    except StopIteration as done:
        return done.value


source = NS(id=1, neuron_type=NeuronType.INPUT)
edge = NS(id=1, source_neuron=source, weight=0.1)
target = NS(id=2, bias=0.0, activation_function="Linear",
            neuron_type=NeuronType.OUTPUT, incoming_connections=[edge])
net = NS(get_topological_order=lambda: [source, target])
im = [{"neuron": source, "column_index": 0}]
om = [{"neuron": target, "column_index": 1}]
snap = PruningQualitySnapshot(net, [[2, 0.15]], im, om)
r = finish(snap.compare(0.1))
assert math.isclose(r["original"], 0.0025)
assert math.isclose(r["pruned"], 0.0225)
assert math.isclose(r["percent"], 800)
assert finish(snap.compare(0))["percent"] == 0
assert edge.weight == 0.1 and target.bias == 0
zero = finish(PruningQualitySnapshot(net, [[2, 0.2]], im, om).compare(1))
assert zero["original"] == 0 and zero["percent"] is None
improved = finish(PruningQualitySnapshot(net, [[2, 0]], im, om).compare(1))
assert improved["percent"] == -100
# Inverse scaling matters: normalized 0.2 maps to 12, pruned zero maps to 10.
scaled_outputs = [{**om[0], "calibration": {
    "mode": "minmax_0_1", "source_min": 10, "source_max": 20}}]
scaled = finish(PruningQualitySnapshot(net, [[2, 11.5]], im, scaled_outputs).compare(1))
assert math.isclose(scaled["original"], 0.25)
assert math.isclose(scaled["pruned"], 2.25)
# Snapshot retains original values even if the source is subsequently edited.
edge.weight = 0.9
assert finish(snap.compare(0.1)) == r
edge.weight = 0.1

panel = PruningQualityPanel(snap)
panel.refresh({"pruning_enabled": True, "pruning_threshold": 1})
assert "wird geprüft" in panel.label.text()
QTest.qWait(40)
assert panel.result and "800,00" in panel.label.text()
assert "#be2525" in panel.label.styleSheet()
panel.refresh({"pruning_enabled": True, "pruning_threshold": 1})
panel.refresh({"pruning_enabled": True, "pruning_threshold": 0})
QTest.qWait(40)
assert panel.result["percent"] == 0
panel.refresh({"pruning_enabled": True})
panel.refresh({"pruning_enabled": False})
QTest.qWait(40)
assert panel.result is None and "ausgeschaltet" in panel.label.text()
panel.snapshot = PruningQualitySnapshot(net, [[float("nan"), 1]], im, om)
panel.refresh({"pruning_enabled": True})
QTest.qWait(40)
assert panel.result is None and "nicht geprüft" in panel.label.text()

quality_inputs = [{**m, "column_index": i} for i, m in enumerate(input_mappings)]
quality_outputs = [{**output_mappings[0], "column_index": 5}]
snapshot = PruningQualitySnapshot(network, [[1, 2, 3, 4, 5, 0.6]],
                                  quality_inputs, quality_outputs)
before = [(n.input_value, n.output_value, n.bias) for n in network.get_neurons()]
for dialog_type, generator in ((XmlExportDialog, Iec61131ExportGenerator),
                                (SpsExportDialog, GxWorks2ExportGenerator)):
    data = build(generator)
    data["quality_snapshot"] = snapshot
    data["regenerate_export"] = lambda opts, version: build(generator, opts)
    dialog = dialog_type(data)
    dialog.show()
    QTest.qWait(20)
    height = dialog.quality_panel.height()
    dialog.settings_panel.pruning.setChecked(True)
    QTest.qWait(60)
    assert dialog.quality_panel.result
    assert "Trainingsdaten" in dialog.quality_panel.label.text()
    assert dialog.quality_panel.height() == height
    if dialog_type is XmlExportDialog:
        dialog.grab().save("Programme/export_test/pruning_quality.png")
    dialog.settings_panel.pruning.setChecked(False)
    assert "ausgeschaltet" in dialog.quality_panel.label.text()
    dialog.close()
assert before == [(n.input_value, n.output_value, n.bias) for n in network.get_neurons()]
print("PLC quality: analytical MSE, scaling, isolation, cancellation and UI passed")
