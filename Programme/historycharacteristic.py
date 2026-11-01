"""Single-run characteristic preview using an isolated saved network state."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from analysisplot import CharacteristicPlot
from resultanalysisdialog import ResultAnalysisDialog
from trainingdataio import TrainingDataIO
from neurontype import NeuronType


class HistoryCharacteristic(QWidget):
    def __init__(self, language, provider=None):
        super().__init__()
        self.language, self.provider = language, provider
        self.entry = None
        self.source = None
        self.network = None
        layout = QVBoxLayout(self)
        self.controls = QWidget()
        row = QHBoxLayout(self.controls)
        row.setContentsMargins(0,0,0,0)
        row.addWidget(QLabel(language.text("training.characteristic.output")))
        self.output = QComboBox()
        row.addWidget(self.output)
        row.addStretch()
        layout.addWidget(self.controls)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.notice,1)
        self.plot = CharacteristicPlot(language_manager=language)
        self.plot.chart_colors_enabled = True
        self.plot.set_compact_footer(True)
        layout.addWidget(self.plot,1)
        self.output.currentIndexChanged.connect(self.refresh)

    def message(self, key):
        self.controls.hide()
        self.plot.hide()
        self.notice.setText(self.language.text(key))
        self.notice.show()

    def set_runs(self, runs):
        if len(runs) != 1:
            self.entry = self.source = self.network = None
            self.message("trajectory.select_one")
            return
        entry = runs[0]
        if entry is not self.entry:
            self.entry = entry
            self.source = self.network = None
            self.output.blockSignals(True)
            self.output.clear()
            try:
                prepared = self.provider(entry) if self.provider else None
                if prepared:
                    self.network,self.source = prepared
                    for mapping in self.source["outputs"]:
                        if mapping.get("data_type") != "binary":
                            self.output.addItem(ResultAnalysisDialog.characteristic_axis_label(mapping),
                                                mapping["neuron"].id)
            except (ValueError, KeyError, TypeError):
                self.source = self.network = None
            finally:
                self.output.blockSignals(False)
        self.refresh()

    def refresh(self, index=None):
        if self.source is None:
            self.message("history.characteristic.unavailable")
            return
        inputs = self.source["inputs"]
        if (len(inputs) != 1 or inputs[0].get("data_type") == "binary"
                or len([n for n in self.network.get_neurons() if n.neuron_type == NeuronType.INPUT]) != 1
                or self.output.currentData() is None):
            self.message("training.characteristic.unavailable")
            return
        inp = inputs[0]
        out = next(m for m in self.source["outputs"] if m["neuron"].id == self.output.currentData())
        try:
            minimum,maximum = ResultAnalysisDialog.characteristic_input_range(self.source,inp)
            points = []
            for index in range(101):
                x = minimum+(maximum-minimum)*index/100
                self.network.reset_runtime_values()
                inp["neuron"].input_value = TrainingDataIO.scale_value(x,inp["calibration"])
                self.network.forward_pass()
                y = TrainingDataIO.unscale_value(out["neuron"].output_value,out["calibration"])
                points.append((x,y))
            targets = [(float(r[inp["column_index"]]),float(r[out["column_index"]]))
                       for r in self.source["records"]]
            self.plot.reset_view()
            self.plot.set_data(points,ResultAnalysisDialog.limited_characteristic_points(targets),
                x_label=ResultAnalysisDialog.characteristic_axis_label(inp),
                y_label=ResultAnalysisDialog.characteristic_axis_label(out),
                point_legend=self.language.text("analysis.characteristic.legend_points"),
                x_unit=inp.get("unit", ""),y_unit=out.get("unit", ""))
        except (ValueError,KeyError,TypeError,OverflowError):
            self.message("history.characteristic.unavailable")
            return
        self.notice.hide()
        self.controls.show()
        self.plot.show()
