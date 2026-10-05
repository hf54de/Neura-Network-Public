"""Regression checks for shared sensitivity passes and aggregate views."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication, QDoubleSpinBox
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtTest import QTest
from resultanalysisdialog import ResultAnalysisDialog
from trainingdataio import TrainingDataIO

class Neuron:
    def __init__(self, id):
        self.id = id
        self.update_count = 0
    def __getattr__(self, name):
        return 0.0
    def update(self):
        self.update_count += 1

class Trainer:
    def __init__(self):
        self.visual_updates_enabled = True

class Network:
    def __init__(self):
        self.nodes = [Neuron(i) for i in range(5)]
        self.calls = 0
        self.trainer = Trainer()
    def get_neurons(self):
        return self.nodes
    def reset_runtime_values(self):
        for n in self.nodes:
            n.input_value = n.output_value = 0.0
            if self.trainer.visual_updates_enabled:
                n.update()
    def forward_pass(self):
        self.calls += 1
        a, b = [n.input_value for n in self.nodes[:2]]
        for n, value in zip(self.nodes[2:], (a + 3*b, 4*a, 0)):
            n.output_value = value
        if self.trainer.visual_updates_enabled:
            for n in self.nodes:
                n.update()

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
    dialog.populate_characteristic_inputs()
    for neuron in network.nodes:
        neuron.update_count = 0
    dialog.current_result = dialog.calculate(source)
    assert network.trainer.visual_updates_enabled
    assert all(neuron.update_count == 1 for neuron in network.nodes)
    network.calls = 0
    for neuron in network.nodes:
        neuron.update_count = 0
    values = dialog.calculate_all_sensitivities(source)
    assert network.calls == 2 * 2 * 2, network.calls
    assert network.trainer.visual_updates_enabled
    assert all(neuron.update_count == 1 for neuron in network.nodes)
    assert all(abs(a-b)<1e-7 for (_,a),b in zip(values[2], (25,75)))
    assert all(abs(a-b)<1e-7 for (_,a),b in zip(values[3], (100,0)))
    assert values[4] == [('Channel 0',0),('Channel 1',0)]
    assert network.nodes[0].input_value == 0
    dialog.resize(930,720)
    dialog.show()
    app.processEvents()
    dialog.begin_analysis_progress(100, 'analysis.progress.records')
    dialog.update_analysis_progress(50, force=True)
    assert dialog.analysis_progress_row.isVisible()
    assert dialog.analysis_progress_row.layout().spacing() == 10
    assert '50' in dialog.analysis_progress_text.text(), repr(
        dialog.analysis_progress_text.text()
    )
    dialog.finish_analysis_progress()
    assert not dialog.analysis_progress_row.isVisible()
    large_source = dict(source)
    large_source['records'] = source['records'] * 50
    dialog.calculate(large_source)
    assert not dialog.analysis_progress_row.isVisible()
    out = Path('../.tmp_analysis_qa');out.mkdir(exist_ok=True)
    dialog.tabs.setCurrentIndex(2)
    app.processEvents()
    assert dialog.output_combo.currentData() is None
    assert len(dialog.plot.rows) == 6
    assert len({r['plot_color'] for r in dialog.plot.rows}) == 3
    assert dialog.output_legend.isVisible()
    assert dialog.show_tolerance_checkbox.isVisible()
    assert dialog.plot_tolerance_spin.isVisible()
    assert dialog.plot_tolerance_mode.isVisible()
    assert dialog.plot_tolerance_mode.currentData() == 'percent'
    assert not dialog.plot_tolerance_mode.isEnabled()
    dialog.show_tolerance_checkbox.setChecked(True)
    dialog.plot_tolerance_spin.setValue(7.5)
    assert dialog.plot.show_tolerance and dialog.plot.tolerance_percent
    assert dialog.plot.tolerance == 7.5
    mappings[3]['unit'] = '%'
    dialog.refresh_plot_and_tolerance()
    assert dialog.plot_tolerance_mode.isEnabled()
    mappings[3]['unit'] = '°C'
    dialog.refresh_plot_and_tolerance()
    dialog.grab().save(str(out/'combined-plot.png'))
    expected_tabs = [
        dialog.records_tab,
        dialog.overview_tab,
        dialog.plot_tab,
        dialog.characteristic_tab,
        dialog.tolerance_tab,
        dialog.sensitivity_tab,
    ]
    assert dialog.tabs.count() == len(expected_tabs)
    assert all(dialog.tabs.indexOf(tab) >= 0 for tab in expected_tabs)
    dialog.tabs.setCurrentIndex(3)
    app.processEvents()
    assert dialog.tabs.currentWidget() is dialog.characteristic_tab
    assert dialog.output_combo.currentData() is None
    assert dialog.output_combo.model().item(0).isEnabled()
    assert not dialog.output_combo.view().isRowHidden(0)
    assert dialog.characteristic_context.text() == dialog.t(
        'analysis.output_required'
    )
    assert dialog.characteristic_plot.curve_points == []
    dialog.grab().save(str(out/'all-outputs-characteristic-message.png'))
    dialog.output_combo.setCurrentIndex(1)
    app.processEvents()
    assert dialog.output_combo.currentData() == 2
    assert dialog.output_combo.model().item(0).isEnabled()
    assert not dialog.output_combo.view().isRowHidden(0)
    assert len(dialog.characteristic_plot.curve_points) == 201
    assert dialog.characteristic_plot.data_points == [(.6, .8)]
    assert dialog.characteristic_plot.data_point_records == [2]
    assert dialog.characteristic_plot.reference_point == (.2, 1.5)
    assert dialog.characteristic_plot.reference_record == 1
    assert dialog.characteristic_plot.data_point_strengths == [1.0]
    assert not dialog.characteristic_show_points.isVisible()
    assert dialog.characteristic_show_all_records.isVisible()
    assert not dialog.characteristic_show_all_records.isChecked()
    assert dialog.characteristic_reference_label.isVisible()
    assert dialog.characteristic_reference_record.isVisible()
    similarity_source = dict(
        inputs=mappings[:2],
        records=[[0, 0, 0], [10, .1, 0], [20, .5, 0], [30, 1, 0]],
    )
    similar = dialog.similar_characteristic_records(
        similarity_source, mappings[0], 0, maximum_points=2
    )
    assert [item[0] for item in similar] == [1, 2]
    assert similar[0][2] == 1.0 and similar[1][2] == .25
    assert len(dialog.similar_characteristic_records(
        similarity_source, mappings[0], 0, maximum_points=99
    )) == 3
    assert all(abs(a - b) < 1e-12 for a, b in zip(
        dialog.characteristic_plot.curve_points[0], (.2, 1.4)
    ))
    assert all(abs(a - b) < 1e-12 for a, b in zip(
        dialog.characteristic_plot.curve_points[-1], (.6, 1.8)
    ))
    assert network.nodes[0].input_value == 0
    dialog.grab().save(str(out/'network-characteristic.png'))
    assert not dialog.characteristic_show_all_button.isEnabled()
    class WheelEvent:
        def position(self):
            return dialog.characteristic_plot.plot_rect().center()
        def angleDelta(self):
            return QPoint(0, 120)
        def accept(self):
            self.accepted = True
    dialog.characteristic_plot.wheelEvent(WheelEvent())
    app.processEvents()
    assert dialog.characteristic_plot.view_range is not None
    assert dialog.characteristic_show_all_button.isEnabled()
    zoomed_range = dialog.characteristic_plot.view_range
    class MouseEvent:
        def __init__(self, position):
            self._position = position
        def position(self):
            return self._position
        def button(self):
            return Qt.MouseButton.LeftButton
        def accept(self):
            self.accepted = True
    center = dialog.characteristic_plot.plot_rect().center()
    dialog.characteristic_plot.mousePressEvent(MouseEvent(center))
    dialog.characteristic_plot.mouseMoveEvent(
        MouseEvent(center + QPointF(20, 10))
    )
    dialog.characteristic_plot.mouseReleaseEvent(
        MouseEvent(center + QPointF(20, 10))
    )
    assert dialog.characteristic_plot.view_range != zoomed_range
    dialog.characteristic_show_all_button.click()
    app.processEvents()
    assert dialog.characteristic_plot.view_range is None
    assert not dialog.characteristic_show_all_button.isEnabled()
    dialog.characteristic_show_all_records.setChecked(True)
    app.processEvents()
    assert dialog.characteristic_plot.point_legend == 'Similar training records'
    assert dialog.characteristic_plot.background_legend == 'All training records'
    assert dialog.characteristic_plot.background_points == [(.6, .8)]
    assert dialog.characteristic_plot.background_point_records == [2]
    assert len(dialog.characteristic_plot.data_points) == 1
    record_two_points = [
        entry for entry in dialog.characteristic_plot.screen_points
        if entry['record'] == 2
    ]
    assert record_two_points
    chosen = dialog.characteristic_plot.nearest_record(
        record_two_points[0]['point']
    )
    assert chosen['priority'] == 1
    class HoverEvent:
        def __init__(self, position):
            self._position = position
        def position(self):
            return self._position
        def globalPosition(self):
            return self._position
    dialog.characteristic_plot.mouseMoveEvent(
        HoverEvent(record_two_points[0]['point'])
    )
    app.processEvents()
    assert dialog.characteristic_plot.hovered_screen_entry()['priority'] == 1
    assert dialog.characteristic_plot.x_unit == '%'
    assert dialog.characteristic_plot.y_unit == '%'
    dialog.grab().save(str(out/'characteristic-hover-values.png'))
    dialog.characteristic_plot.hovered_record = None
    dialog.characteristic_plot.update()
    app.processEvents()
    dialog.grab().save(str(out/'all-records-characteristic.png'))
    dialog.characteristic_show_all_records.setChecked(False)
    app.processEvents()
    source['inputs'] = mappings[:1]
    dialog.populate_characteristic_inputs()
    dialog.refresh_characteristic()
    app.processEvents()
    assert not dialog.characteristic_reference_label.isVisible()
    assert not dialog.characteristic_reference_record.isVisible()
    assert dialog.characteristic_show_points.isVisible()
    assert not dialog.characteristic_show_all_records.isVisible()
    assert len(dialog.characteristic_plot.data_points) == 2
    assert 'reference record' not in dialog.characteristic_explanation.text().lower()
    dialog.grab().save(str(out/'single-input-characteristic.png'))
    source['inputs'] = mappings[:2]
    dialog.populate_characteristic_inputs()
    dialog.refresh_characteristic()
    dialog.populate_records_table()
    app.processEvents()
    record_two = next(
        entry for entry in dialog.characteristic_plot.screen_points
        if entry['record'] == 2 and entry['priority'] == 1
    )
    QTest.mouseClick(
        dialog.characteristic_plot,
        Qt.MouseButton.LeftButton,
        pos=record_two['point'].toPoint(),
    )
    app.processEvents()
    assert dialog.tabs.currentIndex() == 0
    assert dialog.records_table.currentRow() == 1
    dialog.tabs.setCurrentIndex(4)
    app.processEvents()
    dialog.tolerance_spin.setValue(.125)
    assert dialog.tolerances[('output',2)] == .125
    dialog.grab().save(str(out/'single-tolerance.png'))
    dialog.tabs.setCurrentIndex(5)
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
