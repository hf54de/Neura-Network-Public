"""Resizable, nonmodal view of the current training chart; no network calculations."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QStackedWidget, QVBoxLayout
from trainingerrorchart import TrainingErrorChart
from analysisplot import CharacteristicPlot
from weighttrajectory import WeightTrajectoryPlot


class TrainingChartWindow(QDialog):
    ERROR_FIELDS = (
        "run_id", "points", "maximum_points", "comparison_runs", "show_full_comparison_runs",
        "error_metric", "error_limit", "scale_mode",
    )
    CHARACTERISTIC_FIELDS = (
        "fixed_base_range", "stable_range_key", "stable_base_range", "curve_points",
        "background_points", "data_points", "data_point_strengths", "comparison_active",
        "comparison_prediction", "operating_point", "record_details", "reference_point",
        "data_point_records", "background_point_records", "reference_record", "source_kind",
        "x_label", "y_label", "x_unit", "y_unit", "point_legend", "background_legend",
        "reference_legend", "compact_footer", "view_range",
    )

    def __init__(self, training):
        super().__init__(training)
        self.training = training
        self.setWindowTitle(training.language.text("training.chart.enlarged"))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setModal(False)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)
        self.error_chart = TrainingErrorChart(language_manager=training.language)
        self.characteristic = CharacteristicPlot(language_manager=training.language)
        self.characteristic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.trajectory = WeightTrajectoryPlot(training.language)
        self.notice = QLabel(training.language.text("training.characteristic.unavailable"))
        self.notice.setWordWrap(True)
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for widget in (self.error_chart, self.characteristic, self.trajectory, self.notice):
            widget.chart_colors_enabled = True
            self.stack.addWidget(widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(training.language.text("common.close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.sync_chart)
        self.resize(1100, 720)
        screen = self.screen().availableGeometry()
        self.resize(min(self.width(), screen.width()-40), min(self.height(), screen.height()-60))

    def sync_chart(self):
        source = self.training
        metric = source.error_metric_combo.currentData()
        if metric == "trajectory":
            plot = self.trajectory
            original = source.weight_trajectory_plot
            plot.set_trajectory(original.data, original.title, original.message)
        elif metric == "characteristic":
            if not source.training_characteristic_notice.isHidden():
                plot = self.notice
            else:
                plot = self.characteristic
                for field in self.CHARACTERISTIC_FIELDS:
                    setattr(plot, field, getattr(source.training_characteristic_plot, field))
        else:
            plot = self.error_chart
            for field in self.ERROR_FIELDS:
                setattr(plot, field, getattr(source.error_chart, field))
        self.stack.setCurrentWidget(plot)
        plot.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_chart()
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)
