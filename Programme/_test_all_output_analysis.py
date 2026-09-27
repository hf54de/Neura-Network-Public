"""Regression checks for shared sensitivity passes and aggregate views."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication, QDoubleSpinBox
from PySide6.QtGui import QFontDatabase, QFont
from resultanalysisdialog import ResultAnalysisDialog
from trainingdataio import TrainingDataIO

class Neuron:
    def __init__(self, id):
        self.id = id
    def __getattr__(self, name):
        return 0.0
    def update(self):
        pass

class Network:
    def __init__(self):
        self.nodes = [Neuron(i) for i in range(5)]
        self.calls = 0
    def get_neurons(self):
        return self.nodes
    def reset_runtime_values(self):
        for n in self.nodes:
            n.input_value = n.output_value = 0.0
    def forward_pass(self):
        self.calls += 1
        a, b = [n.input_value for n in self.nodes[:2]]
        for n, value in zip(self.nodes[2:], (a + 3*b, 4*a, 0)):
            n.output_value = value

def main():
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    app.setFont(QFont('Segoe UI', 9))
    network = Network()
    mappings = [dict(neuron=n, column_name=f'Channel {i}', column_index=i,
                     calibration=TrainingDataIO.default_calibration(), data_type='analog',
                     unit='%' if i != 3 else '°C') for i,n in enumerate(network.nodes)]
    source = dict(label='Training', kind='training', inputs=mappings[:2], outputs=mappings[2:],
                  records=[[.2,.4,1.5,.7,.1], [.6,.1,.8,2.5,.2]])
    dialog = ResultAnalysisDialog(network, [])
    dialog.source_combo.blockSignals(True)
    dialog.source_combo.addItem('Training', source)
    dialog.source_combo.blockSignals(False)
    dialog.sources = [source]
    dialog.populate_output_combo()
    dialog.current_result = dialog.calculate(source)
    network.calls = 0
    values = dialog.calculate_all_sensitivities(source)
    assert network.calls == 2 * 2 * 2, network.calls
    assert all(abs(a-b)<1e-7 for (_,a),b in zip(values[2], (25,75)))
    assert all(abs(a-b)<1e-7 for (_,a),b in zip(values[3], (100,0)))
    assert values[4] == [('Channel 0',0),('Channel 1',0)]
    assert network.nodes[0].input_value == 0
    dialog.resize(930,720)
    dialog.show()
    out = Path('../.tmp_analysis_qa');out.mkdir(exist_ok=True)
    dialog.tabs.setCurrentIndex(2)
    app.processEvents()
    assert dialog.output_combo.currentData() is None
    assert len(dialog.plot.rows) == 6
    assert len({r['plot_color'] for r in dialog.plot.rows}) == 3
    assert dialog.output_legend.isVisible()
    dialog.grab().save(str(out/'combined-plot.png'))
    dialog.tabs.setCurrentIndex(3)
    app.processEvents()
    assert dialog.output_combo.currentData() == 2
    assert not dialog.output_combo.model().item(0).isEnabled()
    assert dialog.output_combo.view().isRowHidden(0)
    dialog.tolerance_spin.setValue(.125)
    assert dialog.tolerances[('output',2)] == .125
    dialog.grab().save(str(out/'single-tolerance.png'))
    dialog.tabs.setCurrentIndex(4)
    app.processEvents()
    assert dialog.output_combo.currentData() == 2
    assert dialog.output_combo.view().isRowHidden(0)
    assert dialog.sensitivity_plot.values[0][0] == 'Channel 1'
    cached_calls = network.calls
    dialog.refresh_sensitivity()
    assert network.calls == cached_calls
    dialog.grab().save(str(out/'single-sensitivity.png'))
    dialog.tabs.setCurrentIndex(0)
    app.processEvents()
    assert not dialog.output_combo.isVisible() and not dialog.output_selector_label.isVisible()
    dialog.tabs.setCurrentIndex(1)
    app.processEvents()
    assert dialog.output_combo.isVisible() and not dialog.output_combo.view().isRowHidden(0)
    dialog.tabs.setCurrentIndex(2)
    dialog.output_combo.setCurrentIndex(0)
    app.processEvents()
    assert len(dialog.plot.rows) == 6 and dialog.output_legend.isVisible()
    dialog.output_combo.setCurrentIndex(2)
    app.processEvents()
    assert len(dialog.plot.rows) == 2 and not dialog.output_legend.isVisible()
    assert dialog.plot_show_all_button.isVisible() and dialog.plot_show_all_button.isEnabled()
    single_geometry = dialog.plot.geometry()
    dialog.output_combo.setCurrentIndex(0)
    app.processEvents()
    assert dialog.plot.geometry() == single_geometry, (single_geometry, dialog.plot.geometry())
    assert dialog.output_legend.mapTo(dialog, dialog.output_legend.rect().bottomLeft()).y() < dialog.tabs.y()
    dialog.close()
    print('PASS: shared passes, known sensitivities, zero effects, runtime restoration, cache, tab changes, per-output tolerance and single/all switching')

if __name__ == '__main__':
    main()
