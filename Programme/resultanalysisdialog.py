# -------------------------------------------------------------------------------------------------
# Datei: resultanalysisdialog.py
# Zweck: Analysiert und vergleicht Ergebnisse aus Trainings- und Testdaten.
# Letzte Änderung: 03.10.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from base64 import b64encode
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from html import escape
import math
from math import log10
from pathlib import Path
import re
from time import monotonic

from PySide6.QtCore import (
    QByteArray,
    QBuffer,
    QEvent,
    QEventLoop,
    QIODevice,
    QLocale,
    QMarginsF,
    QRectF,
    QThread,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QFontDatabase, QFontMetrics, QImage, QPageLayout, QPageSize, QPainter, QPen, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSlider,
    QToolButton,
    QScrollArea,
    QFormLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from buildfeatures import author_html_export
from docxreport import DocxReport
from language import LanguageManager
from network import estimate_training_operations
from numberformat import format_number, linear_axis_ticks, linear_axis_label, logarithmic_axis_exponents
from pdfreportlayout import draw_pdf_frames, pdf_frame_marker, prepare_pdf_frames
from reportdescription import report_description_parts
from trainingdataio import TrainingDataIO
from weighttrajectory import WeightTrajectoryPlot
from analysisplot import CharacteristicPlot, FeatureImportancePlot, SollIstPlot
from graphicalexperimentdialog import (show_yellow_information_dialog,
    GraphicalExperimentDialog, calculate_forward_snapshot)


@dataclass(frozen=True)
class ReportFigure:
    key: str
    title: str
    image: QImage
    subtitle: str = ""
    caption: str = ""

    @property
    def headings(self):
        if self.key.startswith("sensitivity_") and self.subtitle:
            return f"{self.title} – {self.subtitle}", ""
        if self.key == "scatter_all":
            return self.title, ""
        return self.title, self.subtitle

    @property
    def width_inches(self):
        return min(6.75, 7.6 * self.image.width() / self.image.height())

    @property
    def height_inches(self):
        return self.width_inches * self.image.height() / self.image.width()


class FillingErrorTable(QTableWidget):
    """Distribute unused viewport width without enlarging the surrounding dialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.column_weights = ()
        self.column_minima = ()
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit_columns)
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Resize:
            self.fit_timer.start(0)
        return super().eventFilter(watched, event)

    def configure_widths(self, minima, weights):
        self.column_minima, self.column_weights = minima, weights
        self.fit_columns()
        self.fit_timer.start(0)

    def fit_columns(self):
        if not self.column_weights:
            return
        columns = [c for c in range(self.columnCount()) if not self.isColumnHidden(c)]
        header = self.horizontalHeader()
        metrics = header.fontMetrics()
        minima = {}
        for column in columns:
            item = self.horizontalHeaderItem(column)
            text = item.text() if item is not None else ""
            width = max((metrics.horizontalAdvance(line) for line in text.splitlines()), default=0) + 16
            minima[column] = max(self.column_minima[column], width)
        remaining = max(0, self.viewport().width() - sum(minima.values()))
        total_weight = sum(self.column_weights[c] for c in columns)
        used = 0
        for index, column in enumerate(columns):
            extra = remaining-used if index == len(columns)-1 else int(remaining*self.column_weights[column]/total_weight)
            used += extra
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.setColumnWidth(column, minima[column]+extra)


class AnalysisCancelled(Exception):
    """The user stopped the calculation before a result was produced."""


class ReportFileWriter(QThread):
    """Runs the document writer without blocking the progress window."""

    def __init__(self, write):
        super().__init__()
        self.write = write
        self.error = None

    def run(self):
        try:
            self.write()
        except Exception as error:
            self.error = error


class AnalysisProgressDialog(QDialog):
    def __init__(self, parent, translate, title_key):
        super().__init__(parent)
        self.translate = translate
        self.setWindowTitle(translate(title_key))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(430)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.bar = QProgressBar(self)
        self._last_count_update = 0.0
        self._cancel_requested = False
        buttons = QDialogButtonBox(self)
        self.cancel_button = buttons.addButton(
            translate("common.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addWidget(buttons)

    def reject(self):
        if self.cancel_button.isEnabled():
            self._cancel_requested = True
            self.cancel_button.setEnabled(False)

    def process_progress_events(self):
        # Application modality keeps the other windows locked while the
        # progress dialog can receive the Cancel click.
        QApplication.processEvents()
        if self._cancel_requested:
            raise AnalysisCancelled

    def phase(self, key, **values):
        self.bar.setRange(0, 0)
        self.label.setText(self.translate(key, **values))
        self.process_progress_events()

    def begin_count(self, total, key):
        self.count_text = self.translate(key)
        self.bar.setRange(0, max(1, total))
        self.set_count(0, force=True)

    def set_count(self, value, force=False):
        maximum = self.bar.maximum()
        now = monotonic()
        if not force and value != maximum and now - self._last_count_update < 0.2:
            return
        self._last_count_update = now
        percent = round(value / maximum * 100)
        self.label.setText(
            self.count_text.replace("%v", str(value)).replace("%m", str(maximum)).replace("%p", str(percent))
        )
        self.bar.setValue(value)
        self.process_progress_events()

    def save(self, write):
        self.phase("analysis.report.progress.save")
        self.cancel_button.setEnabled(False)
        writer = ReportFileWriter(write)
        loop = QEventLoop()
        writer.finished.connect(loop.quit, Qt.ConnectionType.QueuedConnection)
        writer.start()
        try:
            loop.exec()
        finally:
            writer.wait()
        if writer.error is not None:
            raise writer.error


class ResultAnalysisDialog(QDialog):
    """Fasst reine Vorwärtsberechnungen verständlich in Rohwerten zusammen."""

    def __init__(
        self,
        network,
        sources,
        parent=None,
        language_manager=None,
        initial_tab=1,
        initial_source_kind=None,
        tolerances=None,
        report_context=None,
        *,
        report_only=False,
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.network = network
        self.sources = list(sources)
        self.tolerances = tolerances if isinstance(tolerances, dict) else {}
        self.plot_percent_values = {}
        self.report_context = report_context if isinstance(report_context, dict) else {}
        self.current_result = None
        self._operation_progress = None
        self._tolerance_table_key = None
        self.results_by_source = {}
        self.sensitivity_cache = {}
        self.characteristic_values = {}
        self.characteristic_value_source = None
        self.characteristic_editors = {}
        self.characteristic_record_index = 0
        self.characteristic_plot_key = None
        self.characteristic_curve_key = None
        self.characteristic_marker_timer = QTimer(self)
        self.characteristic_marker_timer.setSingleShot(True)
        self.characteristic_marker_timer.setInterval(16)
        self.characteristic_marker_timer.timeout.connect(self.update_characteristic_point)

        self.setWindowTitle(self.t("analysis.title"))
        self.setModal(True)
        self.setMinimumWidth(760)
        self.resize(930, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel(self.t("analysis.source.label")))
        self.source_combo = QComboBox()
        for source in self.sources:
            self.source_combo.addItem(source["label"], source)
        selector_layout.addWidget(self.source_combo, 1)
        self.output_selector_label = QLabel(self.t("analysis.output_selector"))
        selector_layout.addWidget(self.output_selector_label)
        self.output_combo = QComboBox()
        selector_layout.addWidget(self.output_combo, 1)
        layout.addLayout(selector_layout)

        self.source_note = QLabel()
        self.source_note.setWordWrap(True)
        self.source_note.setStyleSheet(
            "QLabel { background: #eef4f8; border: 1px solid #b9cbd8; "
            "border-radius: 4px; padding: 7px; }"
        )
        layout.addWidget(self.source_note)

        self.analysis_progress_row = QWidget()
        analysis_progress_layout = QHBoxLayout(self.analysis_progress_row)
        analysis_progress_layout.setContentsMargins(0, 0, 0, 0)
        analysis_progress_layout.setSpacing(10)
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setTextVisible(False)
        self.analysis_progress.setMinimumHeight(20)
        self.analysis_progress_text = QLabel()
        analysis_progress_layout.addWidget(self.analysis_progress, 1)
        analysis_progress_layout.addWidget(self.analysis_progress_text)
        self.analysis_progress_row.hide()
        layout.addWidget(self.analysis_progress_row)

        information_layout = QHBoxLayout()
        self.output_legend = QLabel()
        self.output_legend.setWordWrap(True)
        legend_policy = self.output_legend.sizePolicy()
        legend_policy.setRetainSizeWhenHidden(True)
        self.output_legend.setSizePolicy(legend_policy)
        self.output_legend.hide()
        information_layout.addWidget(self.output_legend, 1)
        self.info_button = QPushButton("i", self)
        self.info_button.setFixedSize(26, 24)
        self.info_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.info_button.setAutoDefault(False)
        self.info_button.setDefault(False)
        self.info_button.clicked.connect(self.show_information)
        information_layout.addWidget(self.info_button)
        layout.addLayout(information_layout)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.records_tab = QWidget()
        records_layout = QVBoxLayout(self.records_tab)
        self.records_table = QTableWidget()
        self.configure_table(self.records_table)
        self.records_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.records_table.cellDoubleClicked.connect(self.open_record_in_plot)
        records_layout.addWidget(self.records_table, 1)
        self.records_summary = QLabel()
        self.records_summary.setWordWrap(True)
        records_layout.addWidget(self.records_summary)
        self.tabs.addTab(self.records_tab, self.t("analysis.tab.records"))

        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)

        self.summary_group = QGroupBox(self.t("analysis.summary.group"))
        summary_layout = QVBoxLayout(self.summary_group)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        overview_layout.addWidget(self.summary_group)

        self.output_group = QGroupBox(self.t("analysis.outputs.group"))
        output_layout = QVBoxLayout(self.output_group)
        self.output_table = FillingErrorTable()
        self.configure_table(self.output_table)
        self.output_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.output_table.setColumnCount(9)
        self.output_table.setHorizontalHeaderLabels([
            self.t("analysis.column.record"),
            self.t("analysis.column.output"),
            self.t("analysis.column.target"),
            self.t("analysis.column.actual"),
            self.t("analysis.column.deviation"),
            self.t("analysis.column.mean_deviation").replace(" ", "\n", 1),
            self.t("analysis.column.binary_result"),
            self.t("analysis.column.percent_target"),
            self.t("analysis.column.percent_range"),
        ])
        output_layout.addWidget(self.output_table)
        self.output_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        overview_layout.addWidget(self.output_group)

        deviations_group = QGroupBox(self.t("analysis.deviations.group"))
        deviations_layout = QVBoxLayout(deviations_group)
        deviations_note = QLabel(self.t("analysis.deviations.note"))
        deviations_note.setWordWrap(True)
        deviations_layout.addWidget(deviations_note)
        self.deviations_table = FillingErrorTable()
        self.configure_table(self.deviations_table)
        self.deviations_table.setColumnCount(7)
        self.deviations_table.setHorizontalHeaderLabels([
            self.t("analysis.column.record"),
            self.t("analysis.column.output"),
            self.t("analysis.column.target"),
            self.t("analysis.column.actual"),
            self.t("analysis.column.deviation"),
            self.t("analysis.column.percent_target"),
            self.t("analysis.column.percent_range"),
        ])
        deviations_layout.addWidget(self.deviations_table)
        overview_layout.addWidget(deviations_group, 2)

        self.technical_button = QPushButton(
            self.t("analysis.technical.show")
        )
        self.technical_button.setCheckable(True)
        self.technical_button.toggled.connect(self.toggle_technical_values)
        overview_layout.addWidget(self.technical_button)

        self.technical_group = QGroupBox(self.t("analysis.technical.group"))
        technical_layout = QVBoxLayout(self.technical_group)
        self.technical_label = QLabel()
        self.technical_label.setWordWrap(True)
        self.technical_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        technical_layout.addWidget(self.technical_label)
        self.technical_group.setVisible(False)
        overview_layout.addWidget(self.technical_group)
        self.tabs.addTab(self.overview_tab, self.t("analysis.tab.overview"))

        self.plot_tab = QWidget()
        plot_layout = QVBoxLayout(self.plot_tab)
        self.plot_explanation = QLabel(self.t("analysis.plot.explanation"))
        self.plot_explanation.setWordWrap(True)
        plot_layout.addWidget(self.plot_explanation)
        plot_tolerance_controls = QHBoxLayout()
        self.show_tolerance_checkbox = QCheckBox(
            self.t("analysis.plot.show_tolerance")
        )
        self.show_tolerance_checkbox.toggled.connect(
            self.update_plot_tolerance
        )
        plot_tolerance_controls.addWidget(self.show_tolerance_checkbox)
        self.plot_tolerance_label = QLabel(self.t("analysis.plot.tolerance_label"))
        plot_tolerance_controls.addWidget(self.plot_tolerance_label)
        self.plot_tolerance_spin = QDoubleSpinBox()
        self.plot_tolerance_spin.setDecimals(6)
        self.plot_tolerance_spin.setRange(0.0, 1_000_000_000.0)
        self.plot_tolerance_spin.valueChanged.connect(
            self.plot_tolerance_changed
        )
        plot_tolerance_controls.addWidget(self.plot_tolerance_spin)
        self.plot_tolerance_mode = QComboBox()
        german = self.language.current_language == "de"
        self.plot_tolerance_mode.addItem("Absoluter Wert" if german else "Absolute value", "absolute")
        self.plot_tolerance_mode.addItem("Prozent vom Sollwert" if german else "Percent of target", "percent")
        self.plot_tolerance_mode.addItem("Prozent der Sollwert-Spannweite" if german else "Percent of target range", "range_percent")
        self.plot_tolerance_mode.setToolTip(
            "Prozent vom Sollwert: |Sollwert| × Prozent / 100. Bei Sollwert 0 ist die Toleranz 0.\n"
            "Prozent der Sollwert-Spannweite: (größter − kleinster Sollwert) × Prozent / 100, "
            "bezogen auf die ausgewerteten Daten. Bei gleichen Sollwerten ist die Toleranz 0."
            if german else
            "Percent of target: |target| × percent / 100. At target 0, the tolerance is 0.\n"
            "Percent of target range: (maximum − minimum target) × percent / 100, "
            "based on the evaluated data. For identical targets, the tolerance is 0."
        )
        self.plot_tolerance_mode.currentIndexChanged.connect(self.plot_tolerance_mode_changed)
        plot_tolerance_controls.addWidget(self.plot_tolerance_mode)

        plot_tolerance_controls.addStretch(1)
        self.plot_show_all_button = QPushButton(
            self.t("analysis.plot.show_all")
        )
        self.plot_show_all_button.setToolTip(
            self.t("analysis.plot.navigation_tooltip")
        )
        plot_tolerance_controls.addWidget(self.plot_show_all_button)
        plot_layout.addLayout(plot_tolerance_controls)
        self.plot = SollIstPlot(language_manager=self.language)
        self.plot_show_all_button.clicked.connect(self.plot.reset_view)
        self.plot.recordActivated.connect(self.open_plot_record)
        plot_layout.addWidget(self.plot, 1)
        for widget in (self.plot_tolerance_label, self.plot_tolerance_spin,
                       self.plot_tolerance_mode, self.show_tolerance_checkbox):
            policy = widget.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            widget.setSizePolicy(policy)
        self.tabs.addTab(self.plot_tab, self.t("analysis.tab.plot"))

        self.characteristic_tab = QWidget()
        characteristic_page_layout = QVBoxLayout(self.characteristic_tab)
        self.characteristic_unavailable = QLabel(
            self.t("analysis.characteristic.unavailable"))
        self.characteristic_unavailable.setWordWrap(True)
        self.characteristic_unavailable.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.characteristic_unavailable.setMargin(32)
        self.characteristic_unavailable.hide()
        characteristic_page_layout.addWidget(self.characteristic_unavailable, 1)
        self.characteristic_content = QWidget()
        characteristic_page_layout.addWidget(self.characteristic_content, 1)
        characteristic_layout = QVBoxLayout(self.characteristic_content)
        characteristic_layout.setContentsMargins(0, 0, 0, 0)
        self.characteristic_explanation = QLabel(
            self.t("analysis.characteristic.fixed_explanation")
        )
        self.characteristic_explanation.setWordWrap(True)
        characteristic_layout.addWidget(self.characteristic_explanation)

        characteristic_controls = QHBoxLayout()
        characteristic_controls.addWidget(QLabel(self.t("analysis.characteristic.input_label")))
        self.characteristic_input_combo = QComboBox()
        self.characteristic_input_combo.setMinimumWidth(160)
        self.characteristic_input_combo.setMaximumWidth(210)
        self.characteristic_input_combo.currentIndexChanged.connect(self.refresh_characteristic)
        characteristic_controls.addWidget(self.characteristic_input_combo)
        self.characteristic_slider = QSlider(Qt.Orientation.Horizontal)
        self.characteristic_slider.setRange(0, 10000)
        self.characteristic_slider.setMinimumWidth(100)
        self.characteristic_slider.valueChanged.connect(self.characteristic_slider_changed)
        self.characteristic_slider.sliderPressed.connect(
            lambda: self.characteristic_slider_changed(self.characteristic_slider.value()))
        characteristic_controls.addWidget(self.characteristic_slider, 1)
        self.characteristic_value = QDoubleSpinBox()
        self.characteristic_value.setDecimals(8)
        self.characteristic_value.setKeyboardTracking(False)
        self.characteristic_value.setFixedWidth(125)
        self.characteristic_value.valueChanged.connect(self.characteristic_value_changed)
        characteristic_controls.addWidget(self.characteristic_value)
        characteristic_layout.addLayout(characteristic_controls)

        options = QHBoxLayout()
        self.characteristic_other_button = QToolButton()
        self.characteristic_other_button.setText(self.t("analysis.characteristic.other_inputs"))
        self.characteristic_other_button.setCheckable(True)
        self.characteristic_other_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.characteristic_other_button.setArrowType(Qt.ArrowType.RightArrow)
        options.addWidget(self.characteristic_other_button)
        self.characteristic_show_points = QCheckBox(self.t("analysis.characteristic.show_points"))
        self.characteristic_show_points.setChecked(True)
        self.characteristic_show_points.toggled.connect(self.refresh_characteristic)
        options.addWidget(self.characteristic_show_points)
        options.addStretch(1)
        self.characteristic_show_all_button = QPushButton(self.t("analysis.characteristic.reset_view"))
        self.characteristic_show_all_button.setToolTip(self.t("analysis.plot.navigation_tooltip"))
        self.characteristic_show_all_button.setEnabled(False)
        options.addWidget(self.characteristic_show_all_button)
        characteristic_layout.addLayout(options)
        self.characteristic_other_area = QScrollArea()
        self.characteristic_other_area.setWidgetResizable(True)
        self.characteristic_other_area.setMaximumHeight(140)
        self.characteristic_other_area.hide()
        self.characteristic_other_button.toggled.connect(self.toggle_characteristic_inputs)
        characteristic_layout.addWidget(self.characteristic_other_area)

        self.characteristic_context = QLabel()
        self.characteristic_context.setWordWrap(True)
        self.characteristic_context.setStyleSheet(
            "QLabel { background:#eef4f8; border:1px solid #b9cbd8; "
            "border-radius:4px; padding:7px; }"
        )
        characteristic_layout.addWidget(self.characteristic_context)
        self.characteristic_plot = CharacteristicPlot(
            language_manager=self.language
        )
        self.characteristic_plot.chart_colors_enabled = True
        self.characteristic_plot.setMinimumHeight(220)
        self.characteristic_show_all_button.clicked.connect(
            self.characteristic_plot.reset_view
        )
        self.characteristic_plot.viewChanged.connect(
            self.characteristic_show_all_button.setEnabled
        )
        self.characteristic_plot.recordActivated.connect(
            self.select_characteristic_record
        )
        characteristic_layout.addWidget(self.characteristic_plot, 1)
        self.tabs.addTab(
            self.characteristic_tab,
            self.t("analysis.tab.characteristic"),
        )

        self.tolerance_tab = QWidget()
        tolerance_layout = QVBoxLayout(self.tolerance_tab)
        tolerance_controls = QHBoxLayout()
        self.tolerance_controls_label = QLabel(self.t("analysis.tolerance.label"))
        tolerance_controls.addWidget(self.tolerance_controls_label)
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setDecimals(6)
        self.tolerance_spin.setRange(0.0, 1_000_000_000.0)
        self.tolerance_spin.valueChanged.connect(self.tolerance_changed)
        tolerance_controls.addWidget(self.tolerance_spin)
        tolerance_controls.addStretch(1)
        tolerance_layout.addLayout(tolerance_controls)
        self.tolerance_summary = QLabel()
        self.tolerance_summary.setWordWrap(True)
        self.tolerance_summary.setStyleSheet(
            "QLabel { background:#eef4f8; border:1px solid #b9cbd8; "
            "border-radius:4px; padding:8px; font-weight:bold; }"
        )
        tolerance_layout.addWidget(self.tolerance_summary)
        self.tolerance_table = QTableWidget()
        self.configure_table(self.tolerance_table)
        self.tolerance_table.setColumnCount(5)
        self.tolerance_table.setHorizontalHeaderLabels([
            self.t("analysis.column.record"),
            self.t("analysis.column.output"),
            self.t("analysis.column.target"),
            self.t("analysis.column.actual"),
            self.t("analysis.column.deviation"),
        ])
        self.tolerance_table.cellDoubleClicked.connect(self.open_tolerance_record)
        tolerance_layout.addWidget(self.tolerance_table, 1)
        self.tabs.addTab(self.tolerance_tab, self.t("analysis.tab.tolerance"))

        self.sensitivity_tab = QWidget()
        sensitivity_layout = QVBoxLayout(self.sensitivity_tab)
        self.sensitivity_note = QLabel(self.t("analysis.sensitivity.explanation"))
        self.sensitivity_note.setWordWrap(True)
        sensitivity_layout.addWidget(self.sensitivity_note)
        self.sensitivity_plot = FeatureImportancePlot(
            language_manager=self.language
        )
        self.sensitivity_group = QGroupBox(
            self.t("analysis.sensitivity.group")
        )
        sensitivity_group_layout = QVBoxLayout(self.sensitivity_group)
        sensitivity_group_layout.setContentsMargins(8, 8, 8, 8)
        sensitivity_group_layout.addWidget(self.sensitivity_plot, 1)
        sensitivity_layout.addWidget(self.sensitivity_group, 1)
        self.tabs.addTab(
            self.sensitivity_tab,
            self.t("analysis.tab.sensitivity")
        )

        self.trajectory_tab = None
        run = self.report_context.get("training_run") or {}
        trajectory = run.get("weight_trajectory")
        if trajectory and len(trajectory.get("points", ())) > 1:
            self.trajectory_tab = QWidget()
            trajectory_layout = QVBoxLayout(self.trajectory_tab)
            plot = WeightTrajectoryPlot(self.language, self.trajectory_tab,
                                        end_label=self.t("trajectory.end"))
            plot.chart_colors_enabled = True
            plot.interactive = True
            plot.set_trajectory(trajectory, self.t(
                "trajectory.run", run=run["run_id"],
                solver=self.t("adam.solver." + run.get("solver", "sgd")),
            ))
            trajectory_layout.addWidget(plot)
            self.tabs.addTab(self.trajectory_tab, self.t("trajectory.title"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.t("common.close")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if initial_source_kind:
            for index, source in enumerate(self.sources):
                if source.get("kind") == initial_source_kind:
                    self.source_combo.setCurrentIndex(index)
                    break
        self.tabs.setCurrentIndex(max(0, min(self.tabs.count() - 1, int(initial_tab))))
        self.source_combo.currentIndexChanged.connect(self.refresh_analysis)
        self.output_combo.currentIndexChanged.connect(self.output_changed)
        self.tabs.currentChanged.connect(self.tab_changed)
        # Start only after exec() has made the dialog visible so the progress
        # bar can be painted during the first evaluation as well.
        if not report_only:
            QTimer.singleShot(0, self.refresh_analysis)

    def show_information(self):
        """Zeigt die Erklärung zum aktuell sichtbaren Analyseregister."""

        information_keys = {
            self.records_tab: "records",
            self.overview_tab: "overview",
            self.plot_tab: "plot",
            self.characteristic_tab: "characteristic",
            self.tolerance_tab: "tolerance",
            self.sensitivity_tab: "sensitivity",
            self.trajectory_tab: "trajectory",
        }
        section = information_keys.get(
            self.tabs.currentWidget(),
            "records",
        )

        show_yellow_information_dialog(
            self,
            self.t(f"analysis.information.{section}.title"),
            self.t(f"analysis.information.{section}.text"),
            self.t("common.close"),
        )

    @staticmethod
    def configure_table(table):
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setStretchLastSection(False)

    def update_output_table_height(self):
        """Passt die Output-Übersicht an ihre Zeilenzahl an."""
        visible_rows = min(max(self.output_table.rowCount(), 1), 6)
        row_height = self.output_table.verticalHeader().defaultSectionSize()
        header_height = self.output_table.horizontalHeader().sizeHint().height()
        scrollbar_height = self.output_table.horizontalScrollBar().sizeHint().height()
        frame_height = self.output_table.frameWidth() * 2
        self.output_table.setFixedHeight(
            header_height
            + visible_rows * row_height
            + scrollbar_height
            + frame_height
        )

    def toggle_technical_values(self, visible):
        self.technical_group.setVisible(bool(visible))
        self.technical_button.setText(
            self.t(
                "analysis.technical.hide"
                if visible
                else "analysis.technical.show"
            )
        )

    def current_source(self):
        # QVariant may return a fresh dict on every access; use the stable source
        # object so cached analyses survive output and tab changes.
        index = self.source_combo.currentIndex()
        return self.sources[index] if 0 <= index < len(self.sources) else None

    def selected_output_mapping(self):
        neuron_id = self.output_combo.currentData()
        source = self.current_source()
        if not source or neuron_id is None:
            return None
        return next(
            (mapping for mapping in source["outputs"] if mapping["neuron"].id == neuron_id),
            None,
        )

    def selected_characteristic_input_mapping(self):
        neuron_id = self.characteristic_input_combo.currentData()
        source = self.current_source()
        if not source or neuron_id is None:
            return None
        return next(
            (
                mapping for mapping in source["inputs"]
                if mapping["neuron"].id == neuron_id
            ),
            None,
        )

    def populate_characteristic_inputs(self):
        source = self.current_source()
        previous = self.characteristic_input_combo.currentData()
        self.characteristic_input_combo.blockSignals(True)
        self.characteristic_input_combo.clear()
        if source:
            for mapping in source["inputs"]:
                unit = str(mapping.get("unit") or "").strip()
                label = mapping["column_name"]
                if unit:
                    label += f" [{unit}]"
                self.characteristic_input_combo.addItem(
                    label,
                    mapping["neuron"].id,
                )
        index = self.characteristic_input_combo.findData(previous)
        self.characteristic_input_combo.setCurrentIndex(
            index if index >= 0 else (0 if self.characteristic_input_combo.count() else -1)
        )
        self.characteristic_input_combo.blockSignals(False)

    def populate_output_combo(self):
        source = self.current_source()
        previous = self.output_combo.currentData()
        self.output_combo.blockSignals(True)
        self.output_combo.clear()
        self.output_combo.addItem(self.t("analysis.output_all"), None)
        if source:
            for mapping in source["outputs"]:
                self.output_combo.addItem(
                    f"Output – {mapping['column_name']}",
                    mapping["neuron"].id,
                )
        index = self.output_combo.findData(previous)
        self.output_combo.setCurrentIndex(index if index >= 0 else 0)
        self.update_output_selection_options()
        self.output_combo.blockSignals(False)

    def update_output_selection_options(self):
        current_tab = self.tabs.currentWidget()
        show_selector = current_tab not in (self.records_tab, self.trajectory_tab)
        self.output_combo.setVisible(show_selector)
        self.output_selector_label.setVisible(show_selector)
        if self.output_combo.count():
            specific = current_tab in (self.characteristic_tab, self.tolerance_tab, self.sensitivity_tab)
            self.output_combo.model().item(0).setEnabled(not specific)
            self.output_combo.view().setRowHidden(0, specific)
            if specific:
                self.ensure_specific_output()

    def ensure_specific_output(self):
        if self.output_combo.currentData() is None and self.output_combo.count() > 1:
            self.output_combo.setCurrentIndex(1)

    def tab_changed(self, index):
        previous_output = self.output_combo.currentIndex()
        self.update_output_selection_options()
        if previous_output != self.output_combo.currentIndex():
            # The selection signal already refreshed the newly visible tab.
            return
        self.refresh_plot_and_tolerance()
        current_tab = self.tabs.widget(index)
        if current_tab is self.characteristic_tab:
            self.refresh_characteristic()
        if current_tab is self.sensitivity_tab:
            self.refresh_sensitivity()

    def output_changed(self, index=None):
        self.refresh_overview_tables()
        self.refresh_plot_and_tolerance()
        self.refresh_characteristic()
        self.refresh_sensitivity()

    def source_information(self, source):
        source_key = {
            "test": "analysis.source.test_note",
        }.get(source.get("kind"), "analysis.source.training_note")
        text = self.t(source_key, count=len(source["records"]))
        file_path = str(source.get("file_path") or "").strip()
        if file_path:
            text += "\n" + self.t("test.file", file_path=file_path)
        text += "\n" + self.t("analysis.network_unchanged")
        return text

    def begin_analysis_progress(self, total, text_key):
        """Blendet für umfangreiche synchrone Auswertungen Fortschritt ein."""
        total = max(0, int(total))
        if self._operation_progress is not None:
            self._operation_progress.begin_count(total, text_key)
            return
        self._analysis_progress_visible = total >= 100
        self._analysis_progress_interval = max(1, total // 100)
        if not self._analysis_progress_visible:
            return
        self._analysis_progress_text_key = text_key
        self.analysis_progress.setRange(0, max(1, total))
        self.analysis_progress.setValue(0)
        self.update_analysis_progress_text(0)
        self.analysis_progress_row.show()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
        )

    def update_analysis_progress_text(self, value):
        maximum = max(1, self.analysis_progress.maximum())
        percentage = round(int(value) / maximum * 100)
        text = self.t(self._analysis_progress_text_key)
        text = text.replace("%v", str(int(value)))
        text = text.replace("%m", str(maximum))
        text = text.replace("%p", str(percentage))
        self.analysis_progress_text.setText(text)

    def update_analysis_progress(self, value, force=False):
        if self._operation_progress is not None:
            self._operation_progress.set_count(value, force=force)
            return
        if not getattr(self, "_analysis_progress_visible", False):
            return
        value = int(value)
        if not force and value % self._analysis_progress_interval:
            return
        self.analysis_progress.setValue(value)
        self.update_analysis_progress_text(value)
        # Nur die Fortschrittsanzeige unmittelbar neu zeichnen. Ein globales
        # processEvents() würde bei jedem Schritt das gesamte Fenster und die
        # dahinterliegende Oberfläche neu aufbauen.
        self.analysis_progress.repaint()
        self.analysis_progress_text.repaint()

    def finish_analysis_progress(self):
        if self._operation_progress is not None:
            return
        if not getattr(self, "_analysis_progress_visible", False):
            return
        self.analysis_progress.setValue(self.analysis_progress.maximum())
        self.update_analysis_progress_text(self.analysis_progress.maximum())
        self.analysis_progress_row.hide()
        self._analysis_progress_visible = False
        self.layout().activate()
        self.updateGeometry()
        self.update()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
        )

    @staticmethod
    def neuron_runtime_snapshot(neuron):
        names = (
            "input_value", "sum_value", "output_value", "target_value",
            "error_value", "delta_value", "external_input_value",
            "external_input_is_raw", "external_input_is_binary",
            "external_input_unit", "external_output_value",
            "external_target_value", "external_output_is_raw",
            "external_output_is_binary", "external_output_unit",
        )
        return {name: getattr(neuron, name) for name in names}

    def reset_runtime_values_silently(self):
        """Setzt Laufzeitwerte zurück, ohne Grafikaktualisierungen anzufordern."""
        for neuron in self.network.get_neurons():
            neuron.input_value = 0.0
            neuron.sum_value = 0.0
            neuron.output_value = 0.0
            neuron.target_value = 0.0
            neuron.error_value = 0.0
            neuron.delta_value = 0.0
            neuron.external_input_value = None
            neuron.external_input_is_raw = False
            neuron.external_input_is_binary = False
            neuron.external_input_unit = ""
            neuron.external_output_value = None
            neuron.external_target_value = None
            neuron.external_output_is_raw = False
            neuron.external_output_is_binary = False
            neuron.external_output_unit = ""

    def calculate(self, source):
        snapshots = {
            neuron: self.neuron_runtime_snapshot(neuron)
            for neuron in self.network.get_neurons()
        }
        trainer = getattr(self.network, "trainer", None)
        previous_visual_updates = (
            getattr(trainer, "visual_updates_enabled", True)
            if trainer is not None else None
        )
        rows = []
        internal_squared_sum = 0.0
        internal_absolute_sum = 0.0
        internal_maximum = 0.0
        range_percentages = []
        output_metrics = defaultdict(lambda: {
            "absolute_sum": 0.0,
            "maximum": -1.0,
            "maximum_record": 0,
            "count": 0,
            "binary_count": 0,
            "binary_errors": 0,
        })
        record_count = len(source["records"])
        self.begin_analysis_progress(
            record_count,
            "analysis.progress.records",
        )
        if trainer is not None:
            trainer.visual_updates_enabled = False

        try:
            for record_number, record in enumerate(source["records"], start=1):
                self.reset_runtime_values_silently()
                targets = {}
                for mapping in source["inputs"]:
                    mapping["neuron"].input_value = TrainingDataIO.scale_value(
                        record[mapping["column_index"]],
                        mapping["calibration"],
                        translator=self.t,
                    )
                for mapping in source["outputs"]:
                    targets[mapping["neuron"].id] = TrainingDataIO.scale_value(
                        record[mapping["column_index"]],
                        mapping["calibration"],
                        translator=self.t,
                    )

                self.network.forward_pass()

                for mapping in source["outputs"]:
                    neuron = mapping["neuron"]
                    raw_target = record[mapping["column_index"]]
                    raw_actual = TrainingDataIO.unscale_value(
                        neuron.output_value,
                        mapping["calibration"],
                        translator=self.t,
                    )
                    raw_error = raw_target - raw_actual
                    raw_absolute = abs(raw_error)
                    internal_error = targets[neuron.id] - neuron.output_value
                    internal_absolute = abs(internal_error)
                    calibration_mode = mapping["calibration"].get("mode", "none")
                    internal_range = {
                        "minmax_0_1": 1.0,
                        "minmax_minus1_1": 2.0,
                    }.get(calibration_mode)
                    if mapping.get("data_type") == "binary":
                        internal_range = 1.0
                    range_percentage = (
                        internal_absolute / internal_range * 100.0
                        if internal_range
                        else None
                    )
                    if range_percentage is not None:
                        range_percentages.append(range_percentage)
                    is_binary = mapping.get("data_type") == "binary"
                    binary_error = (
                        is_binary
                        and (raw_target > 0.5) != (raw_actual > 0.5)
                    )
                    metric = output_metrics[neuron.id]
                    metric["absolute_sum"] += raw_absolute
                    metric["count"] += 1
                    if raw_absolute > metric["maximum"]:
                        metric["maximum"] = raw_absolute
                        metric["maximum_record"] = record_number
                    if is_binary:
                        metric["binary_count"] += 1
                        metric["binary_errors"] += int(binary_error)

                    internal_squared_sum += internal_error * internal_error
                    internal_absolute_sum += internal_absolute
                    internal_maximum = max(internal_maximum, internal_absolute)
                    rows.append({
                        "record": record_number,
                        "neuron_id": neuron.id,
                        "output": mapping["column_name"],
                        "unit": mapping.get("unit", ""),
                        "target": raw_target,
                        "actual": raw_actual,
                        "raw_absolute": raw_absolute,
                        "internal_absolute": internal_absolute,
                        "range_percentage": range_percentage,
                        "display_range_percentage": self.raw_range_percentage(raw_absolute, mapping),
                        "is_binary": is_binary,
                        "binary_error": binary_error,
                    })
                self.update_analysis_progress(record_number)
        finally:
            for neuron, values in snapshots.items():
                for name, value in values.items():
                    setattr(neuron, name, value)
            if trainer is not None:
                trainer.visual_updates_enabled = previous_visual_updates
            for neuron in snapshots:
                neuron.update()
            self.finish_analysis_progress()

        count = len(rows)
        rows.sort(key=lambda row: row["internal_absolute"], reverse=True)
        return {
            "rows": rows,
            "outputs": output_metrics,
            "value_count": count,
            "mse": internal_squared_sum / count if count else 0.0,
            "mae": internal_absolute_sum / count if count else 0.0,
            "maximum": internal_maximum,
            "mean_range_percentage": (
                sum(range_percentages) / len(range_percentages)
                if range_percentages else None
            ),
            "maximum_range_percentage": (
                max(range_percentages) if range_percentages else None
            ),
            "percentage_count": len(range_percentages),
            "distribution": (
                sum(value <= 1.0 for value in range_percentages),
                sum(1.0 < value <= 5.0 for value in range_percentages),
                sum(5.0 < value <= 10.0 for value in range_percentages),
                sum(value > 10.0 for value in range_percentages),
            ),
        }

    def refresh_analysis(self, _index=None):
        source = self.current_source()
        if not source:
            return
        self.source_note.setText(self.source_information(source))
        self.current_result = self.calculate(source)
        self._tolerance_table_key = None
        self.populate_output_combo()
        self.populate_characteristic_inputs()
        self.results_by_source[id(source)] = self.current_result
        self.tabs.setTabText(
            0,
            self.t(
                "analysis.tab.test_data"
                if source.get("kind") == "test"
                else "analysis.tab.records"
            )
        )
        self.populate_records_table()
        self.refresh_overview_tables()
        self.refresh_plot_and_tolerance()
        self.refresh_characteristic()
        self.refresh_sensitivity()

    @staticmethod
    def characteristic_input_range(source, mapping):
        if mapping.get("data_type") == "binary":
            return 0., 1.
        values = [
            float(record[mapping["column_index"]])
            for record in source["records"]
        ]
        calibration = TrainingDataIO.normalize_calibration(
            mapping.get("calibration")
        )
        if (
            calibration["mode"] in {"minmax_0_1", "minmax_minus1_1"}
            and calibration["source_max"] > calibration["source_min"]
        ):
            return calibration["source_min"], calibration["source_max"]
        minimum = min(values)
        maximum = max(values)
        if math.isclose(minimum, maximum):
            padding = max(1.0, abs(minimum) * 0.1)
            return minimum - padding, maximum + padding
        return minimum, maximum

    @staticmethod
    def limited_characteristic_points(points, maximum_points=2000):
        """Begrenzt nur die Punktdarstellung reproduzierbar über die X-Achse."""

        points = sorted(points, key=lambda point: (point[0], point[1]))
        if len(points) <= maximum_points:
            return points
        if maximum_points <= 1:
            return points[:1]
        last_index = len(points) - 1
        indices = {
            round(index * last_index / (maximum_points - 1))
            for index in range(maximum_points)
        }
        return [points[index] for index in sorted(indices)]

    @staticmethod
    def similar_characteristic_records(
        source,
        input_mapping,
        reference_index,
        maximum_points=30,
    ):
        """Findet lokal vergleichbare Datensätze über die übrigen Eingänge."""

        other_inputs = [
            mapping for mapping in source["inputs"]
            if mapping["neuron"].id != input_mapping["neuron"].id
        ]
        if not other_inputs:
            return []
        records = source["records"]
        reference_record = records[reference_index]
        dimensions = []
        for mapping in other_inputs:
            column_index = mapping["column_index"]
            values = [float(record[column_index]) for record in records]
            span = max(values) - min(values)
            if span > 1e-12:
                dimensions.append((column_index, span))
        if not dimensions:
            return [
                (index, 0.0, 1.0)
                for index in range(len(records))
                if index != reference_index
            ][:maximum_points]

        candidates = []
        for index, record in enumerate(records):
            if index == reference_index:
                continue
            squared_distance = sum(
                (
                    (float(record[column_index])
                     - float(reference_record[column_index])) / span
                ) ** 2
                for column_index, span in dimensions
            ) / len(dimensions)
            candidates.append((index, math.sqrt(squared_distance)))
        candidates.sort(key=lambda item: (item[1], item[0]))
        selected = candidates[:maximum_points]
        if not selected:
            return []
        smallest_distance = selected[0][1]
        greatest_distance = selected[-1][1]
        distance_span = greatest_distance - smallest_distance
        return [
            (
                index,
                distance,
                1.0 if distance_span <= 1e-12
                else 0.25 + 0.75 * (
                    1.0 - (distance - smallest_distance) / distance_span
                ),
            )
            for index, distance in selected
        ]

    @staticmethod
    def characteristic_axis_label(mapping):
        unit = str(mapping.get("unit") or "").strip()
        return (
            f"{mapping['column_name']} [{unit}]"
            if unit else mapping["column_name"]
        )

    def toggle_characteristic_inputs(self, checked):
        self.characteristic_other_area.setVisible(checked)
        self.characteristic_other_button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def characteristic_record_matches(self, record, selected, include_selected=False):
        return all(math.isclose(float(record[m["column_index"]]),
                   self.characteristic_values[m["neuron"].id], rel_tol=1e-10, abs_tol=1e-12)
                   for m in self.current_source()["inputs"] if include_selected or m is not selected)

    def select_characteristic_record(self, _kind, record):
        source = self.current_source()
        selected = self.selected_characteristic_input_mapping()
        if not source or not selected or not 1 <= record <= len(source["records"]):
            return
        values = source["records"][record-1]
        if not self.characteristic_record_matches(values, selected):
            self.update_characteristic_point()
            self.characteristic_context.setText(self.characteristic_context.text() + " " +
                self.t("analysis.characteristic.incompatible_record", record=record))
            return
        self.set_characteristic_record(record-1)
        self.update_characteristic_point()

    def set_characteristic_record(self, index):
        source = self.current_source()
        mapping = self.selected_characteristic_input_mapping()
        self.characteristic_record_index = index
        raw_x = float(source["records"][index][mapping["column_index"]])
        self.characteristic_value.blockSignals(True)
        self.characteristic_value.setValue(raw_x)
        self.characteristic_value.blockSignals(False)
        # Use the exact stored value, independent of the editor's display precision.
        self.characteristic_values[mapping["neuron"].id] = raw_x
        self.sync_characteristic_slider(raw_x)
        if not self.characteristic_marker_timer.isActive():
            self.characteristic_marker_timer.start()

    def sync_characteristic_slider(self, value):
        source = self.current_source()
        mapping = self.selected_characteristic_input_mapping()
        low, high = self.characteristic_input_range(source, mapping)
        position = round((value-low)/(high-low)*self.characteristic_slider.maximum())
        self.characteristic_slider.blockSignals(True)
        self.characteristic_slider.setValue(position)
        self.characteristic_slider.blockSignals(False)

    def characteristic_slider_changed(self, position):
        mapping = self.selected_characteristic_input_mapping()
        source = self.current_source()
        if not mapping or not source or not source["records"]:
            return
        low, high = self.characteristic_input_range(source, mapping)
        raw_x = low + (high-low)*position/self.characteristic_slider.maximum()
        self.characteristic_value.blockSignals(True)
        self.characteristic_value.setValue(raw_x)
        self.characteristic_value.blockSignals(False)
        self.characteristic_value_changed(raw_x)

    def characteristic_value_changed(self, value):
        mapping = self.selected_characteristic_input_mapping()
        if mapping is None:
            return
        self.characteristic_values[mapping["neuron"].id] = value
        self.sync_characteristic_slider(value)
        if not self.characteristic_marker_timer.isActive():
            self.characteristic_marker_timer.start()

    def characteristic_other_changed(self, neuron_id, value):
        self.characteristic_values[neuron_id] = float(value)
        self.refresh_characteristic()

    def prepare_characteristic_inputs(self, source, selected):
        # Keep edits across axis/output changes; initialize again for a new data source.
        if self.characteristic_value_source is not source:
            self.characteristic_value_source = source
            # Start with a real input combination so a target is available.
            # Subsequent slider/axis/output changes must retain the fixed inputs.
            first_record = source["records"][0]
            self.characteristic_values = {
                mapping["neuron"].id: float(first_record[mapping["column_index"]])
                for mapping in source["inputs"]
            }
            self.characteristic_record_index = 0
            self.characteristic_curve_key = None
        for mapping in source["inputs"]:
            neuron_id = mapping["neuron"].id
            if neuron_id not in self.characteristic_values:
                low, high = ((0., 1.) if mapping.get("data_type") == "binary"
                             else self.characteristic_input_range(source, mapping))
                raw = TrainingDataIO.unscale_value(mapping["neuron"].input_value,
                                                   mapping["calibration"], translator=self.t)
                self.characteristic_values[neuron_id] = max(low, min(high, float(raw)))
        low, high = self.characteristic_input_range(source, selected)
        value = max(low, min(high, self.characteristic_values[selected["neuron"].id]))
        self.characteristic_values[selected["neuron"].id] = value
        self.characteristic_value.blockSignals(True)
        self.characteristic_slider.blockSignals(True)
        binary = selected.get("data_type") == "binary"
        self.characteristic_value.setDecimals(0 if binary else 8)
        self.characteristic_value.setPrefix("")
        self.characteristic_value.setRange(low, high)
        self.characteristic_value.setSingleStep(1 if binary else (high-low)/100)
        self.characteristic_value.setValue(value)
        self.characteristic_slider.setRange(0, 1 if binary else 10000)
        self.sync_characteristic_slider(value)
        self.characteristic_value.blockSignals(False)
        self.characteristic_slider.blockSignals(False)
        other = [m for m in source["inputs"] if m is not selected]
        editor_key = (id(source), selected["neuron"].id, tuple(m["neuron"].id for m in other))
        if getattr(self, "characteristic_editor_key", None) != editor_key:
            self.characteristic_editor_key = editor_key
            container = QWidget()
            form = QFormLayout(container)
            self.characteristic_editors = {}
            for mapping in other:
                neuron_id = mapping["neuron"].id
                if mapping.get("data_type") == "binary":
                    editor = QCheckBox()
                    editor.setChecked(self.characteristic_values[neuron_id] >= .5)
                    editor.toggled.connect(lambda checked, key=neuron_id:
                        self.characteristic_other_changed(key, int(checked)))
                else:
                    editor = QDoubleSpinBox()
                    editor.setDecimals(8)
                    editor.setRange(*self.characteristic_input_range(source, mapping))
                    editor.setSingleStep((editor.maximum()-editor.minimum())/100)
                    editor.setKeyboardTracking(False)
                    editor.setValue(self.characteristic_values[neuron_id])
                    editor.valueChanged.connect(lambda v, key=neuron_id:
                        self.characteristic_other_changed(key, v))
                form.addRow(self.characteristic_axis_label(mapping), editor)
                self.characteristic_editors[neuron_id] = editor
            previous = self.characteristic_other_area.takeWidget()
            if previous is not None:
                previous.deleteLater()
            self.characteristic_other_area.setWidget(container)
            self.characteristic_other_area.setFixedHeight(min(140, max(48, container.sizeHint().height()+6)))
        for mapping in other:
            editor = self.characteristic_editors[mapping["neuron"].id]
            editor.blockSignals(True)
            raw = self.characteristic_values[mapping["neuron"].id]
            if isinstance(editor, QCheckBox):
                editor.setChecked(raw >= .5)
            else:
                editor.setValue(raw)
            editor.blockSignals(False)
            editor.setEnabled(True)
        self.characteristic_other_button.setVisible(bool(other))
        self.characteristic_other_area.setVisible(bool(other) and self.characteristic_other_button.isChecked())

    def evaluate_characteristic(self, source, output_mapping, values):
        inputs = {m["neuron"].id: TrainingDataIO.scale_value(values[m["neuron"].id],
                  m["calibration"], translator=self.t) for m in source["inputs"]}
        if self.characteristic_specification is not None:
            _, outputs = calculate_forward_snapshot(self.characteristic_specification, inputs)
            internal = outputs[output_mapping["neuron"].id]
        else:
            # Also support the small network adapters used by analysis integrations.
            snapshots = {n: self.neuron_runtime_snapshot(n) for n in self.network.get_neurons()}
            trainer = getattr(self.network, "trainer", None)
            visual = getattr(trainer, "visual_updates_enabled", True)
            try:
                if trainer is not None:
                    trainer.visual_updates_enabled = False
                self.network.reset_runtime_values()
                for m in source["inputs"]:
                    m["neuron"].input_value = inputs[m["neuron"].id]
                self.network.forward_pass()
                internal = output_mapping["neuron"].output_value
            finally:
                for n, snapshot in snapshots.items():
                    for name, value in snapshot.items():
                        setattr(n, name, value)
                if trainer is not None:
                    trainer.visual_updates_enabled = visual
        return TrainingDataIO.unscale_value(internal, output_mapping["calibration"], translator=self.t)

    def characteristic_display_value(self, value):
        text = f"{value:.2f}"
        if text == "-0.00":
            text = "0.00"
        return text.replace(".", ",") if self.language.current_language == "de" else text

    def characteristic_target_at(self, source, selected, output, raw_x):
        matching = self.characteristic_matching_records
        exact = [i for i in matching if self.characteristic_record_matches(
            source["records"][i], selected, include_selected=True)]
        if exact:
            number = self.characteristic_record_index if self.characteristic_record_index in exact else exact[0]
            return float(source["records"][number][output["column_index"]]), number
        # Discrete classes have no meaningful fractional target.
        if output.get("data_type") == "binary" or selected.get("data_type") == "binary":
            return None, None
        groups = {}
        for i in matching:
            record = source["records"][i]
            x, y = float(record[selected["column_index"]]), float(record[output["column_index"]])
            groups.setdefault(x, []).append(y)
        lower = [x for x in groups if x < raw_x]
        upper = [x for x in groups if x > raw_x]
        if not lower or not upper:
            return None, None
        left, right = max(lower), min(upper)
        # Conflicting targets at a boundary do not define a unique interpolation.
        if any(not all(math.isclose(y, groups[x][0], rel_tol=1e-10, abs_tol=1e-12)
                       for y in groups[x]) for x in (left, right)):
            return None, None
        fraction = (raw_x-left)/(right-left)
        return groups[left][0]*(1-fraction)+groups[right][0]*fraction, None

    def update_characteristic_point(self):
        source = self.current_source()
        selected = self.selected_characteristic_input_mapping()
        output = self.selected_output_mapping()
        if self.tabs.currentWidget() is not self.characteristic_tab or not source or not selected or not output:
            return
        if not self.characteristic_plot.curve_points:
            return
        try:
            raw_x = self.characteristic_values[selected["neuron"].id]
            raw_y = self.evaluate_characteristic(source, output, self.characteristic_values)
            self.characteristic_plot.set_operating_point((raw_x, raw_y))
            fmt = self.characteristic_display_value
            target, number = self.characteristic_target_at(source, selected, output, raw_x)
            if target is not None:
                if number is not None:
                    self.characteristic_record_index = number
                error = abs(target-raw_y)
                relative = (error/abs(target)*100 if target != 0 and output.get("data_type") != "binary" else None)
                self.characteristic_plot.set_comparison_point(
                    (raw_x, target), number+1 if number is not None else None,
                    prediction=(raw_x, raw_y))
                key = ("analysis.characteristic.comparison_values" if number is not None
                       else "analysis.characteristic.interpolated_values")
                text = self.t(key,
                    record=number+1 if number is not None else "", count=len(source["records"]),
                    input=self.characteristic_axis_label(selected), x=fmt(raw_x),
                    output=self.characteristic_axis_label(output), target=fmt(target), actual=fmt(raw_y),
                    error=fmt(error), percent=fmt(relative) if relative is not None and math.isfinite(relative) else "—")
            else:
                self.characteristic_plot.set_comparison_point(None)
                text = self.t("analysis.characteristic.current", input=self.characteristic_axis_label(selected),
                              x=fmt(raw_x), output=self.characteristic_axis_label(output), y=fmt(raw_y))
                text += " " + self.t("analysis.characteristic.no_matching_target")
            if self.characteristic_show_points.isChecked() and len(source["inputs"]) > 1:
                text += " " + self.t("analysis.characteristic.points_warning")
            self.characteristic_context.setText(text)
            self.characteristic_context.setToolTip(self.t("analysis.characteristic.fixed_tip"))
        except (ValueError, ArithmeticError, KeyError) as error:
            self.characteristic_plot.set_operating_point(None)
            self.characteristic_plot.set_comparison_point(None)
            self.characteristic_context.setText(str(error))

    def refresh_characteristic(self, _value=None):
        """Recompute the slice only when a fixed input or axis changes."""
        if self.tabs.currentWidget() is not self.characteristic_tab:
            return
        self.characteristic_marker_timer.stop()
        source = self.current_source()
        selected = self.selected_characteristic_input_mapping()
        output = self.selected_output_mapping()
        supported = bool(source and len(source["inputs"]) == 1
                         and source["inputs"][0].get("data_type") != "binary"
                         and output and output.get("data_type") != "binary")
        self.characteristic_content.setVisible(supported)
        self.characteristic_unavailable.setVisible(not supported)
        if not supported:
            self.characteristic_plot.set_operating_point(None)
            self.characteristic_plot.set_comparison_point(None)
            self.characteristic_plot.set_data([], [])
            self.characteristic_plot_key = None
            self.characteristic_curve_key = None
            return
        message = ("analysis.characteristic.no_records" if not source or not source["records"] else
                   "analysis.characteristic.no_input" if selected is None else
                   "analysis.output_required" if output is None else None)
        for widget in (self.characteristic_slider, self.characteristic_value,
                       self.characteristic_other_button, self.characteristic_other_area,
                       self.characteristic_show_points):
            widget.setEnabled(message is None)
        if message:
            self.characteristic_plot.set_operating_point(None)
            self.characteristic_plot.set_comparison_point(None)
            self.characteristic_plot.set_data([], [])
            self.characteristic_plot_key = None
            self.characteristic_curve_key = None
            self.characteristic_context.setText(self.t(message))
            return
        self.prepare_characteristic_inputs(source, selected)
        self.characteristic_explanation.setText(self.t("analysis.characteristic.fixed_explanation"))
        low, high = self.characteristic_input_range(source, selected)
        key = (id(source), selected["neuron"].id, output["neuron"].id, low, high,
               tuple((m["neuron"].id, self.characteristic_values[m["neuron"].id])
                     for m in source["inputs"] if m is not selected))
        try:
            if key != self.characteristic_curve_key:
                self.characteristic_specification = (
                    GraphicalExperimentDialog.create_forward_specification(self)
                    if hasattr(self.network, "prepared_training_order") else None)
                values = dict(self.characteristic_values)
                points = []
                sample_count = 2 if selected.get("data_type") == "binary" else 201
                for index in range(sample_count):
                    x = low + (high-low)*index/(sample_count-1)
                    values[selected["neuron"].id] = x
                    points.append((x, self.evaluate_characteristic(source, output, values)))
                self.characteristic_cached_points = points
                self.characteristic_curve_key = key
            plot_key = (key, self.characteristic_show_points.isChecked())
            if self.characteristic_plot_key == plot_key:
                self.update_characteristic_point()
                return
            self.characteristic_matching_records = [i for i, record in enumerate(source["records"])
                if self.characteristic_record_matches(record, selected)]
            matching = set(self.characteristic_matching_records)
            entries = []
            if self.characteristic_show_points.isChecked():
                entries = self.limited_characteristic_points([
                    (float(record[selected["column_index"]]), float(record[output["column_index"]]), i+1)
                    for i, record in enumerate(source["records"])])
            comparable = [(x,y,i) for x,y,i in entries if i-1 in matching]
            other = [(x,y,i) for x,y,i in entries if i-1 not in matching]
            self.characteristic_plot.set_operating_point(None)
            self.characteristic_plot.set_comparison_point(None)
            self.characteristic_plot.set_data(self.characteristic_cached_points,
                [(x, y) for x, y, i in comparable],
                self.characteristic_axis_label(selected), self.characteristic_axis_label(output),
                self.t("analysis.characteristic.comparable_points"),
                data_point_records=[i for x, y, i in comparable],
                background_points=[(x,y) for x,y,i in other],
                background_point_records=[i for x,y,i in other],
                background_legend=self.t("analysis.characteristic.other_points"),
                source_kind=str(source.get("kind") or "data"),
                x_unit=str(selected.get("unit") or ""), y_unit=str(output.get("unit") or ""))
            # Keep the axes fixed while the selected input moves, including when
            # a matching target outside the network's range becomes highlighted.
            bounds_points = list(self.characteristic_cached_points) + [(x,y) for x,y,i in entries]
            bounds_points += [(float(source["records"][i][selected["column_index"]]),
                               float(source["records"][i][output["column_index"]]))
                              for i in self.characteristic_matching_records]
            self.characteristic_plot.fixed_base_range = (
                *self.characteristic_plot.padded_range([x for x,y in bounds_points]),
                *self.characteristic_plot.padded_range([y for x,y in bounds_points]))
            details = {}
            for x, y, number in entries:
                record = source["records"][number-1]
                differences = []
                for m in source["inputs"]:
                    if m is selected:
                        continue
                    actual = float(record[m["column_index"]])
                    fixed = self.characteristic_values[m["neuron"].id]
                    if not math.isclose(actual, fixed, rel_tol=1e-10, abs_tol=1e-12):
                        differences.append(self.t("analysis.characteristic.input_difference",
                            input=self.characteristic_axis_label(m),
                            actual=self.characteristic_plot.axis_tick_label(actual),
                            fixed=self.characteristic_plot.axis_tick_label(fixed)))
                details[number] = (self.t("analysis.characteristic.different_inputs") + "\n" + "\n".join(differences)
                                   if differences else self.t("analysis.characteristic.matching_inputs"))
            self.characteristic_plot.record_details = details
            self.characteristic_plot_key = plot_key
            self.update_characteristic_point()
        except (ValueError, ArithmeticError, KeyError) as error:
            self.characteristic_plot_key = None
            self.characteristic_curve_key = None
            self.characteristic_plot.set_operating_point(None)
            self.characteristic_plot.set_comparison_point(None)
            self.characteristic_plot.set_data([], [])
            self.characteristic_context.setText(str(error))

    def refresh_sensitivity(self):
        if self.tabs.currentWidget() is not self.sensitivity_tab or self._operation_progress is not None:
            return
        source = self.current_source()
        mapping = self.selected_output_mapping()
        if source is None or mapping is None:
            self.sensitivity_plot.set_values([])
            return
        try:
            values = self.calculate_sensitivity(source, mapping)
        except AnalysisCancelled:
            values = []
        self.sensitivity_plot.set_values(values)

    def calculate_sensitivity(self, source, output_mapping):
        cache_key = (id(source), int(output_mapping["neuron"].id))
        if cache_key not in self.sensitivity_cache:
            if self._operation_progress is None:
                with self.operation_progress("analysis.tab.sensitivity"):
                    values = self.calculate_all_sensitivities(source)
            else:
                values = self.calculate_all_sensitivities(source)
            for neuron_id, result in values.items():
                self.sensitivity_cache[(id(source), neuron_id)] = result
        return sorted(self.sensitivity_cache[cache_key], key=lambda item: item[1], reverse=True)

    def calculate_all_sensitivities(self, source):
        """Schätzt den mittleren lokalen Einfluss jedes Inputs per Vorwärtslauf."""
        snapshots = {
            neuron: self.neuron_runtime_snapshot(neuron)
            for neuron in self.network.get_neurons()
        }
        trainer = getattr(self.network, "trainer", None)
        previous_visual_updates = (
            getattr(trainer, "visual_updates_enabled", True)
            if trainer is not None else None
        )
        outputs = source['outputs']
        effects = {int(m['neuron'].id): [] for m in outputs}
        total_steps = len(source["inputs"]) * len(source["records"])
        completed_steps = 0
        self.begin_analysis_progress(
            total_steps,
            "analysis.progress.sensitivity",
        )
        if trainer is not None:
            trainer.visual_updates_enabled = False
        try:
            for input_mapping in source["inputs"]:
                values = [
                    float(record[input_mapping["column_index"]])
                    for record in source["records"]
                ]
                observed_range = max(values) - min(values) if values else 0.0
                calibration = TrainingDataIO.normalize_calibration(
                    input_mapping["calibration"]
                )
                configured_range = (
                    calibration["source_max"] - calibration["source_min"]
                )
                step = max(observed_range, configured_range, 1.0) * 0.01
                total_effect = {int(m['neuron'].id): 0.0 for m in outputs}
                for record in source["records"]:
                    self.reset_runtime_values_silently()
                    for current in source["inputs"]:
                        raw_value = float(record[current["column_index"]])
                        current["neuron"].input_value = TrainingDataIO.scale_value(
                            raw_value, current["calibration"], translator=self.t
                        )
                    self.network.forward_pass()
                    baseline = {int(m['neuron'].id): TrainingDataIO.unscale_value(
                        m['neuron'].output_value, m['calibration'], translator=self.t)
                        for m in outputs}
                    raw_value = float(record[input_mapping["column_index"]])
                    if input_mapping.get("data_type") == "binary":
                        changed_value = 0.0 if raw_value > 0.5 else 1.0
                    else:
                        changed_value = raw_value + step
                    input_mapping["neuron"].input_value = TrainingDataIO.scale_value(
                        changed_value,
                        input_mapping["calibration"],
                        translator=self.t,
                    )
                    self.network.forward_pass()
                    for m in outputs:
                        neuron_id = int(m['neuron'].id)
                        changed = TrainingDataIO.unscale_value(m['neuron'].output_value, m['calibration'], translator=self.t)
                        total_effect[neuron_id] += abs(changed - baseline[neuron_id])
                    completed_steps += 1
                    self.update_analysis_progress(completed_steps)
                for neuron_id in effects:
                    effects[neuron_id].append((input_mapping['column_name'], total_effect[neuron_id] / max(1, len(source['records']))))
        finally:
            for neuron, values in snapshots.items():
                for name, value in values.items():
                    setattr(neuron, name, value)
            if trainer is not None:
                trainer.visual_updates_enabled = previous_visual_updates
            for neuron in snapshots:
                neuron.update()
            self.finish_analysis_progress()
        normalized = {}
        for neuron_id, values in effects.items():
            total = sum(value for _name, value in values)
            normalized[neuron_id] = [(name, value / total * 100.0 if total else 0.0) for name, value in values]
        return normalized

    def refresh_overview_tables(self):
        source = self.source_combo.currentData()
        if not source:
            return
        result = self.current_result or self.calculate(source)
        record_count = len(source["records"])
        selected_id = self.output_combo.currentData()
        displayed_outputs = [
            mapping for mapping in source["outputs"]
            if selected_id is None or mapping["neuron"].id == selected_id
        ]
        output_count = len(displayed_outputs)
        displayed_ids = {mapping["neuron"].id for mapping in displayed_outputs}
        displayed_rows = [
            row for row in result["rows"] if row["neuron_id"] in displayed_ids
        ]

        largest = displayed_rows[0] if displayed_rows else None
        binary_total = sum(
            result["outputs"][mapping["neuron"].id]["binary_count"]
            for mapping in displayed_outputs
        )
        binary_errors = sum(
            result["outputs"][mapping["neuron"].id]["binary_errors"]
            for mapping in displayed_outputs
        )
        if largest:
            summary = self.t(
                "analysis.summary.text_one"
                if output_count == 1
                else "analysis.summary.text",
                records=record_count,
                outputs=output_count,
                record=largest["record"],
                output=largest["output"],
            )
        else:
            summary = self.t("analysis.summary.empty")
        if binary_total:
            summary += "\n" + self.t(
                "analysis.summary.binary",
                correct=binary_total - binary_errors,
                total=binary_total,
                errors=binary_errors,
            )
        self.summary_label.setText(summary)
        self.output_table.setColumnHidden(6, binary_total == 0)

        self.output_table.setRowCount(len(displayed_outputs))
        for row_index, mapping in enumerate(displayed_outputs):
            name = mapping["column_name"]
            metric = result["outputs"][mapping["neuron"].id]
            unit = mapping.get("unit", "")
            suffix = self.deviation_suffix(unit)
            mean_value = metric["absolute_sum"] / max(1, metric["count"])
            maximum_item = next(
                (
                    item for item in displayed_rows
                    if item["neuron_id"] == mapping["neuron"].id
                    and item["record"] == metric["maximum_record"]
                ),
                None,
            )
            binary_text = "–"
            if metric["binary_count"]:
                correct = metric["binary_count"] - metric["binary_errors"]
                binary_text = self.t(
                    "analysis.binary.result",
                    errors=metric["binary_errors"],
                    total=metric["binary_count"],
                    percent=self.display_number(
                        correct / metric["binary_count"] * 100.0
                    ),
                )
            if metric["binary_count"]:
                if maximum_item is not None:
                    target = self.t(
                        "binary.on" if maximum_item["target"] > 0.5 else "binary.off"
                    )
                    actual = self.t(
                        "binary.on" if maximum_item["actual"] > 0.5 else "binary.off"
                    )
                    deviation = self.t(
                        "analysis.binary.incorrect"
                        if maximum_item["binary_error"] else "analysis.binary.correct"
                    )
                else:
                    target = actual = deviation = "–"
                values = (
                    str(metric["maximum_record"] or "–"), name, target,
                    actual, deviation, "–", binary_text,
                )
            else:
                value_suffix = f" {unit}" if unit else ""
                values = (
                    str(metric["maximum_record"]),
                    name,
                    f"{self.display_number(maximum_item['target'])}{value_suffix}",
                    f"{self.display_number(maximum_item['actual'])}{value_suffix}",
                    f"{self.display_number(metric['maximum'])}{suffix}",
                    f"{self.display_number(mean_value)}{suffix}",
                    binary_text,
                )
            values += self.percentage_texts(maximum_item)
            for column, value in enumerate(values):
                self.output_table.setItem(
                    row_index, column, self.table_item(value, column != 1)
                )

        visible_rows = displayed_rows[:20]
        self.deviations_table.setRowCount(len(visible_rows))
        for row_index, item in enumerate(visible_rows):
            unit = item["unit"]
            value_suffix = f" {unit}" if unit else ""
            deviation_suffix = self.deviation_suffix(unit)
            if item.get("is_binary"):
                target_state = self.t(
                    "binary.on" if item["target"] > 0.5 else "binary.off"
                )
                actual_state = self.t(
                    "binary.on" if item["actual"] > 0.5 else "binary.off"
                )
                values = (
                    str(item["record"]),
                    item["output"],
                    target_state,
                    f"{actual_state} ({self.display_number(item['actual'])})",
                    self.t(
                        "analysis.binary.incorrect"
                        if item["binary_error"]
                        else "analysis.binary.correct"
                    ),
                )
            else:
                values = (
                    str(item["record"]),
                    item["output"],
                    f"{self.display_number(item['target'])}{value_suffix}",
                    f"{self.display_number(item['actual'])}{value_suffix}",
                    f"{self.display_number(item['raw_absolute'])}{deviation_suffix}",
                )
            values += self.percentage_texts(item)
            for column, value in enumerate(values):
                self.deviations_table.setItem(
                    row_index, column, self.table_item(value, column != 1)
                )

        self.set_percentage_tooltips()
        self.apply_compact_column_widths(binary_total > 0)
        self.update_output_table_height()

        internal_values = [row["internal_absolute"] for row in displayed_rows]
        range_values = [
            row["range_percentage"] for row in displayed_rows
            if row["range_percentage"] is not None
        ]
        technical_count = len(internal_values)
        technical_mse = (
            sum(value * value for value in internal_values) / technical_count
            if technical_count else 0.0
        )
        technical_mae = (
            sum(internal_values) / technical_count if technical_count else 0.0
        )
        technical_maximum = max(internal_values, default=0.0)

        self.technical_label.setText(
            self.t(
                "analysis.technical.values",
                mse=format_number(technical_mse),
                mae=format_number(technical_mae),
                maximum=format_number(technical_maximum),
                mae_percent=(
                    self.t(
                        "analysis.technical.percentage_value",
                        value=self.display_number(sum(range_values) / len(range_values))
                    )
                    if range_values
                    else self.t("analysis.technical.percentage_unavailable")
                ),
                maximum_percent=(
                    self.t(
                        "analysis.technical.percentage_value",
                        value=self.display_number(max(range_values))
                    )
                    if range_values
                    else self.t("analysis.technical.percentage_unavailable")
                ),
                percent_count=len(range_values),
                count=technical_count,
                very_small=sum(value <= 1.0 for value in range_values),
                small=sum(1.0 < value <= 5.0 for value in range_values),
                medium=sum(5.0 < value <= 10.0 for value in range_values),
                large=sum(value > 10.0 for value in range_values),
            )
        )

    def populate_records_table(self):
        source = self.current_source()
        result = self.current_result
        if not source or not result:
            return
        headers = [self.t("test.column.number")]
        for mapping in source["inputs"]:
            unit = mapping.get("unit", "")
            headers.append(
                f"{mapping['column_name']} [{unit}]" if unit else mapping["column_name"]
            )
        for mapping in source["outputs"]:
            unit = "" if mapping.get("data_type") == "binary" else mapping.get("unit", "")
            name = f"{mapping['column_name']} [{unit}]" if unit else mapping["column_name"]
            headers.extend([
                self.t("test.column.target", output=name),
                self.t("test.column.actual", output=name),
                self.t("test.column.error", output=name),
            ])
        self.records_table.setColumnCount(len(headers))
        self.records_table.setHorizontalHeaderLabels(headers)
        self.records_table.setRowCount(len(source["records"]))
        rows_by_key = {
            (row["record"], row["neuron_id"]): row for row in result["rows"]
        }
        for row_index, record in enumerate(source["records"]):
            self.records_table.setItem(row_index, 0, self.table_item(row_index + 1, True))
            column = 1
            for mapping in source["inputs"]:
                self.records_table.setItem(
                    row_index, column,
                    self.table_item(self.display_number(record[mapping["column_index"]]), True),
                )
                column += 1
            for mapping in source["outputs"]:
                item = rows_by_key[(row_index + 1, mapping["neuron"].id)]
                if item["is_binary"]:
                    target = self.t("binary.on" if item["target"] > 0.5 else "binary.off")
                    actual_state = self.t("binary.on" if item["actual"] > 0.5 else "binary.off")
                    actual = f"{actual_state} ({self.display_number(item['actual'])})"
                    deviation = self.display_number(item["raw_absolute"])
                else:
                    unit = str(item.get("unit") or "")
                    suffix = f" {unit}" if unit else ""
                    target = f"{self.display_number(item['target'])}{suffix}"
                    actual = f"{self.display_number(item['actual'])}{suffix}"
                    deviation = (
                        f"{self.display_number(item['raw_absolute'])} %"
                        if unit == "%"
                        else f"{self.display_number(item['raw_absolute'])}{suffix}"
                    )
                for value in (target, actual, deviation):
                    self.records_table.setItem(row_index, column, self.table_item(value, True))
                    column += 1
        self.records_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.records_summary.setText(
            self.t(
                "analysis.records.summary",
                records=len(source["records"]),
                mse=format_number(result["mse"]),
                mae=format_number(result["mae"]),
                maximum=format_number(result["maximum"]),
            )
        )

    @staticmethod
    def combined_plot_data(source, result):
        """Bereitet die farbigen Punkte und die Legende für alle Ausgänge vor."""
        outputs = source['outputs']
        colors = {m['neuron'].id: QColor.fromHsv((i * 137) % 360, 190, 185).name()
                  for i, m in enumerate(outputs)}
        legend = []
        for m in outputs:
            unit = str(m.get('unit') or '')
            title = m['column_name'] + (f' (in {unit})' if unit else '')
            legend.append(f'<span style="color:{colors[m["neuron"].id]}">●</span> {escape(title)}')
        rows = [dict(row, plot_color=colors[row['neuron_id']],
                     source_kind=source.get('kind', 'data'), source_label=source.get('label', ''))
                for row in result.get('rows', [])]
        return rows, ' &nbsp; &nbsp; '.join(legend)

    def refresh_combined_plot(self):
        rows, legend = self.combined_plot_data(self.current_source(), self.current_result or {})
        self.output_legend.setText(legend)
        self.plot.set_rows(rows)
        self.plot.set_tolerance(0, False)
        german = self.language.current_language == 'de'
        self.plot_explanation.setText(
            'Alle Ausgänge in einem Diagramm. Die Farben kennzeichnen die Ausgänge; Einheiten stehen in der Legende. Ein Klick auf einen Punkt öffnet den Datensatz.'
            if german else
            'All outputs in one plot. Colors identify outputs; units are shown in the legend. Click a point to open its record.')

    def rows_for_selected_output(self):
        source = self.current_source()
        mapping = self.selected_output_mapping()
        if (
            mapping is None
            and self.output_combo.currentData() is None
            and source is not None
            and len(source["outputs"]) == 1
        ):
            mapping = source["outputs"][0]
        if mapping is None or not self.current_result:
            return [], None
        return (
            [
                row for row in self.current_result["rows"]
                if row["neuron_id"] == mapping["neuron"].id
            ],
            mapping,
        )

    def refresh_plot_and_tolerance(self):
        all_outputs = self.output_combo.currentData() is None
        source = self.current_source()
        combined_outputs = bool(
            all_outputs
            and source is not None
            and len(source["outputs"]) > 1
        )
        self.output_legend.setVisible(
            combined_outputs and self.tabs.currentWidget() is self.plot_tab
        )
        for widget in (self.plot_tolerance_label, self.plot_tolerance_spin,
                       self.plot_tolerance_mode, self.show_tolerance_checkbox):
            widget.setVisible(True)
        if combined_outputs:
            self.refresh_combined_plot()
            self.configure_combined_plot_tolerance()
            return
        rows, mapping = self.rows_for_selected_output()
        if mapping is None:
            self.plot.set_rows([])
            self.refresh_tolerance()
            return
        binary = mapping.get("data_type") == "binary"
        source = self.current_source()
        plot_rows = []
        if source is not None:
            for row in rows:
                plot_row = dict(row)
                plot_row["source_kind"] = str(source.get("kind") or "data")
                plot_row["source_label"] = str(source.get("label") or "")
                plot_rows.append(plot_row)
        self.plot.set_rows(
            plot_rows,
            binary=binary,
            unit="" if binary else mapping.get("unit", ""),
        )
        self.plot_explanation.setText(
            self.t("analysis.plot.binary_explanation" if binary else "analysis.plot.explanation")
        )
        self.show_tolerance_checkbox.setEnabled(not binary)
        self.plot_tolerance_spin.setEnabled(not binary)
        self.plot_tolerance_mode.setEnabled(not binary)
        key = self.tolerance_key(mapping)
        if key not in self.tolerances:
            legacy_values = [
                self.tolerances[legacy_key]
                for legacy_key in (
                    ("training", int(mapping["neuron"].id)),
                    ("test", int(mapping["neuron"].id)),
                )
                if legacy_key in self.tolerances
            ]
            if legacy_values:
                self.tolerances[key] = float(legacy_values[0])
            elif binary:
                self.tolerances[key] = 0.0
            else:
                raw_values = [row["target"] for row in rows]
                raw_range = max(raw_values) - min(raw_values) if raw_values else 0.0
                self.tolerances[key] = 5.0 if mapping.get("unit") == "%" else max(raw_range * 0.05, 0.0)
        self.tolerance_spin.blockSignals(True)
        self.tolerance_spin.setEnabled(not binary)
        self.tolerance_spin.setSuffix(
            "" if binary or not mapping.get("unit") else f" {mapping['unit']}"
        )
        self.tolerance_spin.setValue(float(self.tolerances[key]))
        self.tolerance_spin.blockSignals(False)
        if not binary:
            self.tolerances[key] = float(self.tolerance_spin.value())
        self.plot_tolerance_mode_changed()
        self.refresh_tolerance()

    def tolerance_key(self, mapping):
        return ("output", int(mapping["neuron"].id))

    @staticmethod
    def combined_tolerance_key():
        return ("all_outputs", -1)

    def combined_output_context(self):
        source = self.current_source()
        if (
            self.output_combo.currentData() is not None
            or source is None
            or len(source["outputs"]) <= 1
        ):
            return None
        analog_outputs = [
            mapping for mapping in source["outputs"]
            if mapping.get("data_type") != "binary"
        ]
        analog_ids = {
            int(mapping["neuron"].id) for mapping in analog_outputs
        }
        rows = [
            row for row in (self.current_result or {}).get("rows", [])
            if int(row["neuron_id"]) in analog_ids
        ]
        units = {
            str(mapping.get("unit") or "").strip()
            for mapping in analog_outputs
        }
        return {
            "outputs": analog_outputs,
            "rows": rows,
            "same_unit": len(units) <= 1,
            "unit": next(iter(units), ""),
        }

    def configure_combined_plot_tolerance(self):
        context = self.combined_output_context()
        enabled = bool(context and context["outputs"])
        self.show_tolerance_checkbox.setEnabled(enabled)
        self.plot_tolerance_spin.setEnabled(enabled)
        self.plot_tolerance_mode.setEnabled(
            enabled and context["same_unit"]
        )
        if not enabled:
            self.plot.set_tolerance(0.0, False)
            return

        if not context["same_unit"]:
            percent_index = self.plot_tolerance_mode.findData("percent")
            self.plot_tolerance_mode.blockSignals(True)
            self.plot_tolerance_mode.setCurrentIndex(percent_index)
            self.plot_tolerance_mode.blockSignals(False)

        key = self.combined_tolerance_key()
        if key not in self.tolerances:
            targets = [float(row["target"]) for row in context["rows"]]
            span = max(targets) - min(targets) if targets else 0.0
            self.tolerances[key] = (
                5.0 if context["unit"] == "%" else max(span * 0.05, 0.0)
            )
        self.plot_tolerance_mode_changed()

    def plot_tolerance_mode_changed(self, _index=None):
        rows, mapping = self.rows_for_selected_output()
        combined = self.combined_output_context()
        if combined is not None:
            mode = self.plot_tolerance_mode.currentData()
            percent = mode in ("percent", "range_percent")
            key = self.combined_tolerance_key()
            unit = combined["unit"] if combined["same_unit"] else ""
            context = self.t("analysis.output_all")
            if unit:
                context += f" in {unit}"
            label = self.t("analysis.plot.tolerance_label").rstrip().rstrip(":")
            self.plot_tolerance_label.setText(f"{label} ({context}):")
            self.plot_tolerance_spin.blockSignals(True)
            self.plot_tolerance_spin.setSuffix(" %" if percent else (f" {unit}" if unit else ""))
            self.plot_tolerance_spin.setValue(
                self.plot_percent_values.get(key, 5.0)
                if percent else self.tolerances.get(key, 0.0)
            )
            self.plot_tolerance_spin.blockSignals(False)
            self.update_plot_tolerance()
            return
        if mapping is None:
            return
        percent = self.plot_tolerance_mode.currentData() in ("percent", "range_percent")
        key = self.tolerance_key(mapping)
        self.plot_tolerance_spin.blockSignals(True)
        unit = str(mapping.get("unit") or "").strip()
        name = mapping["column_name"]
        context = f"{name} in {unit}" if unit else name
        label = self.t("analysis.plot.tolerance_label").rstrip().rstrip(":")
        self.plot_tolerance_label.setText(f"{label} ({context}):")
        self.plot_tolerance_spin.setSuffix(" %" if percent else "")
        self.plot_tolerance_spin.setValue(self.plot_percent_values.get(key, 5.0) if percent else self.tolerances.get(key, 0.0))
        self.plot_tolerance_spin.blockSignals(False)
        self.update_plot_tolerance()

    def update_plot_tolerance(self, _checked=None):
        rows, mapping = self.rows_for_selected_output()
        combined = self.combined_output_context()
        if combined is not None:
            rows = combined["rows"]
            key = self.combined_tolerance_key()
            mode = self.plot_tolerance_mode.currentData()
            percent = mode in ("percent", "range_percent")
            tolerance = (
                self.plot_percent_values.get(key, 5.0)
                if percent else float(self.tolerances.get(key, 0.0))
            )
            if mode == "range_percent":
                targets = [float(row["target"]) for row in rows]
                span = max(targets) - min(targets) if targets else 0.0
                tolerance = span * tolerance / 100.0
            self.plot.set_tolerance(
                tolerance,
                self.show_tolerance_checkbox.isChecked() and bool(rows),
                percent=mode == "percent",
            )
            return
        if mapping is None:
            self.plot.set_tolerance(0.0, False)
            return
        binary = mapping.get("data_type") == "binary"
        mode = self.plot_tolerance_mode.currentData()
        percent = mode in ("percent", "range_percent")
        tolerance = (self.plot_percent_values.get(self.tolerance_key(mapping), 5.0) if percent
                     else float(self.tolerances.get(self.tolerance_key(mapping), 0.0)))
        if mode == "range_percent":
            targets = [row["target"] for row in rows]
            span = max(targets) - min(targets) if targets else 0.0
            tolerance = span * tolerance / 100
        self.plot.set_tolerance(
            tolerance,
            self.show_tolerance_checkbox.isChecked() and not binary,
            percent=mode == "percent",
        )

    def plot_tolerance_changed(self, value):
        rows, mapping = self.rows_for_selected_output()
        combined = self.combined_output_context()
        if combined is not None:
            key = self.combined_tolerance_key()
            if self.plot_tolerance_mode.currentData() in (
                "percent", "range_percent"
            ):
                self.plot_percent_values[key] = float(value)
            else:
                self.tolerances[key] = float(value)
            self.update_plot_tolerance()
            return
        if mapping is None or mapping.get("data_type") == "binary":
            return
        if self.plot_tolerance_mode.currentData() in ("percent", "range_percent"):
            self.plot_percent_values[self.tolerance_key(mapping)] = float(value)
            self.update_plot_tolerance()
            return
        self.tolerance_spin.blockSignals(True)
        self.tolerance_spin.setValue(float(value))
        self.tolerance_spin.blockSignals(False)
        self.tolerance_changed(self.tolerance_spin.value())

    def tolerance_changed(self, value):
        _, mapping = self.rows_for_selected_output()
        if mapping is None or mapping.get("data_type") == "binary":
            return
        self.tolerances[self.tolerance_key(mapping)] = float(value)
        self.plot_tolerance_mode_changed()
        self.refresh_tolerance()

    def refresh_tolerance(self):
        if self.tabs.currentWidget() is not self.tolerance_tab:
            return
        rows, mapping = self.rows_for_selected_output()
        if mapping is None:
            self.tolerance_summary.setText(self.t("analysis.output_required"))
            self.tolerance_table.setRowCount(0)
            self._tolerance_table_key = None
            return
        binary = mapping.get("data_type") == "binary"
        tolerance = float(self.tolerances.get(self.tolerance_key(mapping), 0.0))
        table_key = (mapping["neuron"].id, None if binary else tolerance)
        if self._tolerance_table_key == table_key:
            return
        self._tolerance_table_key = None
        if binary:
            outside = [row for row in rows if row.get("binary_error")]
            correct = len(rows) - len(outside)
            self.tolerance_summary.setText(
                self.t(
                    "analysis.tolerance.binary_summary",
                    correct=correct,
                    total=len(rows),
                    incorrect=len(outside),
                )
            )
        else:
            outside = [row for row in rows if row["raw_absolute"] > tolerance]
            inside = len(rows) - len(outside)
            percent = inside / len(rows) * 100.0 if rows else 0.0
            suffix = f" {mapping.get('unit', '')}" if mapping.get("unit") else ""
            self.tolerance_summary.setText(
                self.t(
                    "analysis.tolerance.summary",
                    inside=inside,
                    total=len(rows),
                    percent=self.display_number(percent),
                    tolerance=f"{self.display_number(tolerance)}{suffix}",
                )
            )
        self.begin_analysis_progress(len(outside), "analysis.progress.tolerance")
        try:
            self.tolerance_table.setRowCount(len(outside))
            for row_index, item in enumerate(outside):
                if item.get("is_binary"):
                    target = self.t("binary.on" if item["target"] > 0.5 else "binary.off")
                    actual = self.t("binary.on" if item["actual"] > 0.5 else "binary.off")
                    deviation = self.t("analysis.binary.incorrect")
                else:
                    unit = str(item.get("unit") or "")
                    suffix = f" {unit}" if unit else ""
                    target = f"{self.display_number(item['target'])}{suffix}"
                    actual = f"{self.display_number(item['actual'])}{suffix}"
                    deviation = (
                        f"{self.display_number(item['raw_absolute'])} %"
                        if unit == "%" else f"{self.display_number(item['raw_absolute'])}{suffix}"
                    )
                values = (item["record"], item["output"], target, actual, deviation)
                for column, cell_value in enumerate(values):
                    self.tolerance_table.setItem(
                        row_index, column, self.table_item(cell_value, column != 1)
                    )
                self.update_analysis_progress(row_index + 1)
            self.tolerance_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            self._tolerance_table_key = table_key
        finally:
            self.finish_analysis_progress()

    def select_record(self, record):
        row_index = max(0, int(record) - 1)
        if row_index < self.records_table.rowCount():
            self.records_table.selectRow(row_index)
            self.records_table.scrollToItem(self.records_table.item(row_index, 0))
        source = self.current_source() or {}
        self.plot.highlight_record(record, source.get("kind"))

    def open_plot_record(self, source_kind, record):
        for index, source in enumerate(self.sources):
            if str(source.get("kind") or "data") == str(source_kind):
                if self.source_combo.currentIndex() != index:
                    self.source_combo.setCurrentIndex(index)
                break
        self.select_record(record)
        self.tabs.setCurrentIndex(0)

    def open_record_in_plot(self, row, column):
        source = self.current_source()
        if not source:
            return
        first_output = 1 + len(source["inputs"])
        if column >= first_output:
            output_index = min(
                len(source["outputs"]) - 1,
                max(0, (column - first_output) // 3),
            )
            neuron_id = source["outputs"][output_index]["neuron"].id
            combo_index = self.output_combo.findData(neuron_id)
            if combo_index >= 0:
                self.output_combo.setCurrentIndex(combo_index)
        else:
            self.ensure_specific_output()
        self.tabs.setCurrentIndex(2)
        source = self.current_source() or {}
        self.plot.highlight_record(row + 1, source.get("kind"))

    def open_tolerance_record(self, row, column):
        item = self.tolerance_table.item(row, 0)
        if item is None:
            return
        try:
            record = int(item.text())
        except ValueError:
            return
        self.select_record(record)
        self.tabs.setCurrentIndex(0)

    def deviation_suffix(self, unit):
        unit = str(unit or "").strip()
        if unit == "%":
            return " %"
        return f" {unit}" if unit else ""

    @staticmethod
    def display_number(value):
        """Begrenzt reine Anzeigezahlen auf vier Nachkommastellen."""

        number = float(value)
        if number != 0.0 and abs(number) < 0.00005:
            return format_number(number, 4)
        return f"{number:.4f}".rstrip("0").rstrip(".")

    @staticmethod
    def raw_range_percentage(error, mapping):
        calibration = mapping.get("calibration", {})
        if mapping.get("data_type") == "binary" or calibration.get("mode") not in (
            "minmax_0_1", "minmax_minus1_1"
        ):
            return None
        try:
            span = float(calibration["source_max"]) - float(calibration["source_min"])
            value = error / span * 100.0 if span > 0 else None
            return value if value is not None and math.isfinite(value) else None
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

    def percentage_texts(self, row):
        if row is None or row.get("is_binary"):
            return ("—", "—")
        target = abs(row["target"])
        relative = row["raw_absolute"] / target * 100.0 if target else None
        values = (relative, row.get("display_range_percentage"))
        return tuple(self.display_number(value) + " %"
                     if value is not None and math.isfinite(value) else "—" for value in values)

    def set_percentage_tooltips(self):
        for table, first in ((self.output_table, 7), (self.deviations_table, 5)):
            for offset, key in enumerate(("target", "range")):
                column = first + offset
                tip = self.t("analysis.percent." + key + "_tip")
                table.horizontalHeaderItem(column).setToolTip(tip)
                for row in range(table.rowCount()):
                    table.item(row, column).setToolTip(tip)
            for row in range(table.rowCount()):
                for column in range(first):
                    item = table.item(row, column)
                    if item is not None:
                        item.setToolTip(item.text())

    def apply_compact_column_widths(self, has_binary_outputs):
        """Use the full existing table width; emphasize errors and percentages."""
        self.output_table.configure_widths(
            (68, 90, 74, 74, 90, 94, 140, 90, 94), (1, 1, 1, 1, 2, 2, 2, 2, 2))
        self.deviations_table.configure_widths(
            (68, 90, 74, 74, 90, 90, 94), (1, 1, 1, 1, 2, 2, 2))

    def report_error_curve_image(self, points, axis_label, logarithmic, *, compact=False):
        """Zeichnet eine Fehlerkurve mit glatten Teilstrichen für den Bericht."""
        size = (780, 410) if compact else (1200, 520)
        image = QImage(*size, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        left, top, right, bottom = (125, 28, 58, 69) if compact else (132, 30, 82, 64)
        width = image.width() - left - right
        height = image.height() - top - bottom
        if not points:
            painter.setPen(QPen(QColor("#c9d2dc"), 1))
            painter.drawRect(left, top, width, height)
            painter.setPen(QColor("#666666"))
            painter.drawText(left, top, width, height, Qt.AlignmentFlag.AlignCenter, "–")
            painter.end()
            return image

        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        low, high = min(ys), max(ys)
        if logarithmic:
            low = math.floor(log10(low))
            high = max(low + 1, math.ceil(log10(high)))
            y_ticks = logarithmic_axis_exponents(low, high)
        else:
            if high <= low:
                high = low + 1.0
            padding = (high - low) * 0.06
            low -= padding
            high += padding
            y_ticks = linear_axis_ticks(low, high)
        x_low, x_high = min(xs), max(xs)
        if x_high <= x_low:
            x_high = x_low + 1.0

        tick_font = QFont("Segoe UI")
        tick_font.setPixelSize(26 if compact else 22)
        painter.setFont(tick_font)
        intervals = 4 if compact else 5
        x_ticks = [x_low + (x_high - x_low) * index / intervals for index in range(intervals + 1)]
        y_labels = [
            f"1e{value:+d}" if logarithmic and not -4 <= value <= 6
            else linear_axis_label(10.0 ** value if logarithmic else value, self.language.current_language)
            for value in y_ticks
        ]
        label_width = 110
        if compact:
            metrics = QFontMetrics(tick_font)
            left = max(
                max((metrics.horizontalAdvance(label) for label in y_labels), default=0) + 16,
                metrics.horizontalAdvance(f"{x_ticks[0]:.0f}") // 2 + 6,
            )
            right = metrics.horizontalAdvance(f"{x_ticks[-1]:.0f}") // 2 + 7
            label_width = max(metrics.horizontalAdvance(f"{value:.0f}") for value in x_ticks) + 8
            width = image.width() - left - right

        def px(value):
            return left + (float(value) - x_low) / (x_high - x_low) * width

        def py(value):
            return top + height - (float(value) - low) / (high - low) * height

        tick_pen = QPen(QColor("#d4dee7"), 2)
        label_pen = QPen(QColor("#465968"), 1)
        label_height = 30 if compact else 25
        for x_value in x_ticks:
            x_position = int(px(x_value))
            painter.setPen(tick_pen)
            painter.drawLine(x_position, top, x_position, top + height)
            painter.setPen(label_pen)
            painter.drawText(
                x_position - label_width // 2, top + height + 7, label_width, label_height,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{x_value:.0f}",
            )
        for value, label in zip(y_ticks, y_labels, strict=True):
            y_position = int(py(value))
            painter.setPen(tick_pen)
            painter.drawLine(left, y_position, left + width, y_position)
            painter.setPen(label_pen)
            painter.drawText(
                2, y_position - label_height // 2, left - 10, label_height if compact else 24,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label,
            )
        painter.setPen(QPen(QColor("#aebbc7"), 1))
        painter.drawRect(left, top, width, height)
        axis_font = QFont("Segoe UI")
        axis_font.setPixelSize(26 if compact else 23)
        axis_font.setBold(True)
        painter.setFont(axis_font)
        painter.drawText(
            left, top + height + label_height + 4, width, label_height if compact else 23,
            Qt.AlignmentFlag.AlignCenter, str(axis_label)
        )
        painter.setPen(QPen(QColor("#1676b8"), 2))
        previous = None
        for epoch, error in zip(xs, ys):
            current = (int(px(epoch)), int(py(log10(error) if logarithmic else error)))
            if previous is not None:
                painter.drawLine(previous[0], previous[1], current[0], current[1])
            previous = current
        painter.end()
        return image

    @staticmethod
    def image_png_bytes(image, *, corner_radius=0):
        """Encode an image as PNG, optionally rounding its corners by a pixel radius."""
        if corner_radius:
            rounded = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawRoundedRect(QRectF(rounded.rect()), corner_radius, corner_radius)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.drawImage(rounded.rect(), image)
            painter.end()
            image = rounded

        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return bytes(data)

    def report_network_image(self, *, image_width=1400, transparent_background=False):
        """Rendert das vollständige Netzwerk für den Bericht."""
        scene = self.report_context.get("scene")
        if scene is None:
            return None
        bounds = scene.itemsBoundingRect()
        if bounds.isEmpty():
            return None
        bounds = bounds.adjusted(-30, -30, 30, 30)
        source_ratio = bounds.width() / max(bounds.height(), 1.0)
        report_width_inches = 6.75
        desired_height_inches = min(
            7.35,
            max(3.2, (report_width_inches / max(source_ratio, 0.05)) * 1.10),
        )
        image_height = int(round(
            image_width * desired_height_inches / report_width_inches
        ))
        image = QImage(
            image_width, image_height, QImage.Format.Format_ARGB32
        )
        image.fill(QColor("transparent" if transparent_background else "white"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        padding = 38.0 * image_width / 1400
        available_width = image.width() - 2.0 * padding
        available_height = image.height() - 2.0 * padding
        available_ratio = available_width / max(available_height, 1.0)
        if source_ratio <= available_ratio:
            target_height = available_height
            target_width = target_height * source_ratio
        else:
            target_width = available_width
            target_height = target_width / source_ratio
        target = QRectF(
            (image.width() - target_width) / 2.0,
            (image.height() - target_height) / 2.0,
            target_width,
            target_height,
        )
        background = scene.backgroundBrush() if transparent_background else None
        try:
            if background is not None:
                scene.setBackgroundBrush(QBrush())
            scene.render(painter, target, bounds, Qt.AspectRatioMode.KeepAspectRatio)
        finally:
            painter.end()
            if background is not None:
                scene.setBackgroundBrush(background)
        return image

    def report_default_path(self, suffix):
        """Schlägt den Exporte-Ordner des aktuellen Projekts vor."""
        name = str(self.report_context.get("project_name") or "NeuronNetz")
        report_suffix = self.t("analysis.report.file_suffix")
        filename = f"{name}_{report_suffix}.{suffix}".replace(" ", "-")
        export_dir = str(self.report_context.get("export_dir") or "").strip()
        if export_dir:
            directory = Path(export_dir)
            directory.mkdir(parents=True, exist_ok=True)
            return str(directory / filename)
        return filename

    @staticmethod
    def report_integer(value):
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return "–"

    @staticmethod
    def report_decimal(value, digits=4):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "–"
        if number and abs(number) < 10 ** (-digits):
            return f"{number:.2e}"
        return f"{number:.{digits}f}".rstrip("0").rstrip(".")

    def report_datetime(self, value, include_seconds=True):
        text_value = str(value or "").strip()
        if not text_value:
            return "–"
        try:
            parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
            format_key = (
                "analysis.report.datetime_format"
                if include_seconds
                else "analysis.report.created_datetime_format"
            )
            return parsed.strftime(self.t(format_key))
        except ValueError:
            return text_value.replace("T", " ")

    @staticmethod
    def report_curve_is_logarithmic(points):
        values = [float(point[1]) for point in points if float(point[1]) > 0.0]
        return bool(values) and len(values) == len(points) and max(values) / min(values) >= 100.0

    def report_output_title(self, mapping):
        name = str(mapping.get("column_name") or f"Output {mapping['neuron'].id}")
        unit = str(mapping.get("unit") or "").strip()
        if mapping.get("data_type") == "binary":
            prefix = "Entscheidungsdiagramm"
            unit = unit or "Ein/Aus"
        else:
            prefix = "Soll-Ist-Diagramm"
        return f"{prefix} – {name}" + (f" [{unit}]" if unit else "")

    def report_deviation_values(self, row):
        if row.get("is_binary"):
            target = self.t("binary.on" if row["target"] > 0.5 else "binary.off")
            actual_state = self.t("binary.on" if row["actual"] > 0.5 else "binary.off")
            actual = f"{actual_state} ({self.display_number(row['actual'])})"
            deviation = self.t(
                "analysis.binary.incorrect" if row["binary_error"]
                else "analysis.binary.correct"
            )
            return target, actual, deviation
        unit = str(row.get("unit") or "").strip()
        suffix = f" {unit}" if unit else ""
        deviation_suffix = " %" if unit == "%" else suffix
        return (
            f"{self.display_number(row['target'])}{suffix}",
            f"{self.display_number(row['actual'])}{suffix}",
            f"{self.display_number(row['raw_absolute'])}{deviation_suffix}",
        )

    def export_report(self):
        """Lässt das Berichtsformat passend zur Programmfassung wählen."""

        word_filter = self.t("analysis.report.word_filter")
        pdf_filter = self.t("analysis.report.filter")
        exporters = {
            word_filter: (".docx", self.export_word_report),
            pdf_filter: (".pdf", self.export_pdf_report),
        }
        if author_html_export is not None:
            exporters[self.t("analysis.report.html_filter")] = (".html", self.export_html_report)
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.t("analysis.report.create_title"),
            self.report_default_path("docx"),
            ";;".join(exporters),
            word_filter,
        )
        if not file_path:
            return False

        desired_suffix, export = exporters.get(selected_filter, exporters[word_filter])
        selected_path = Path(file_path)
        if selected_path.suffix.lower() in {".pdf", ".docx", ".html", ".htm"}:
            selected_path = selected_path.with_suffix(desired_suffix)
        else:
            selected_path = Path(f"{selected_path}{desired_suffix}")
        return export(str(selected_path))

    @contextmanager
    def operation_progress(self, title_key):
        parent = self if self.isVisible() else self.parentWidget()
        progress = AnalysisProgressDialog(parent, self.t, title_key)
        self._operation_progress = progress
        try:
            progress.show()
            yield progress
        finally:
            self._operation_progress = None
            progress.hide()
            progress.deleteLater()

    def run_report_export(self, file_path, write):
        if self._operation_progress is not None:
            return False
        try:
            with self.operation_progress("analysis.report.create_title") as progress:
                progress.phase("analysis.report.progress.prepare")
                write(file_path)
        except AnalysisCancelled:
            return False
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(self, self.t("analysis.report.error_title"), str(error))
            return False
        self.offer_open_report(file_path)
        return True

    def report_export_phase(self, key, **values):
        if self._operation_progress is not None:
            self._operation_progress.phase(key, **values)

    def offer_open_report(self, file_path):
        """Fragt nach erfolgreichem Export, ob die Datei geöffnet werden soll."""

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Information)
        message_box.setWindowTitle(self.t("analysis.report.create_title"))
        message_box.setText(
            self.t("analysis.report.saved_open", file=file_path)
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Open
            | QMessageBox.StandardButton.Close
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Open)
        if message_box.exec() == QMessageBox.StandardButton.Open:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(file_path).resolve()))
            )

    REPORT_HISTORY_COLUMNS = (
        ("history.column.run", 7),
        ("history.column.time", 14),
        ("adam.solver.label", 20),
        ("history.column.learning_rate", 9),
        ("history.column.momentum", 11),
        ("history.column.epochs", 9),
        ("history.column.end_error", 10),
        ("history.column.maximum_error", 13),
        ("history.column.duration", 7),
    )

    PDF_REPORT_CSS = """
        body{font-family:'Segoe UI';font-size:10pt;color:#172c44;}
        h1{font-size:24pt;margin-top:4px;margin-bottom:15px;color:#172c44;}
        h2{font-size:15pt;margin-top:10px;margin-bottom:7px;color:#172c44;}
        h3{font-size:11pt;margin-top:8px;margin-bottom:5px;color:#172c44;}
        p{margin-top:4px;margin-bottom:5px;}
        .pdf-eyebrow{font-size:9pt;font-weight:bold;color:#21517c;}
        td,th{vertical-align:top;}
        th{background:#eff5fa;color:#172c44;text-align:left;}
        .note,.pdf-caption{color:#415a71;font-size:9pt;}
    """

    def report_training_figures(self, run, *, compact=False, pair_trajectory=False):
        """Rendert die optionalen Diagramme aus dem gespeicherten Trainingslauf."""
        provider = self.report_context.get("characteristic_provider")
        if run and provider:
            from historycharacteristic import HistoryCharacteristic

            view = HistoryCharacteristic(self.language, provider)
            view.setParent(self)
            try:
                view.set_runs([run])
                view.plot.chart_colors_enabled = False
                if compact:
                    font = view.plot.font()
                    font.setPixelSize(16)
                    view.plot.setFont(font)
                view.plot.resize(*(570, 350) if compact else (850, 450))
                for index in range(view.output.count()):
                    view.output.setCurrentIndex(index)
                    if not view.plot.isHidden() and view.plot.curve_points:
                        title = (
                            f"{self.t('analysis.characteristic.legend_curve')} – "
                            f"{view.output.itemText(index)}"
                        )
                        yield ReportFigure(f"training_figure_{index}", title, view.plot.grab().toImage())
            finally:
                view.deleteLater()

        trajectory = run.get("weight_trajectory")
        if trajectory and len(trajectory.get("points", ())) > 1:
            title = self.t("trajectory.title")
            plot = WeightTrajectoryPlot(self.language, self, end_label=self.t("trajectory.end"))
            try:
                if pair_trajectory:
                    font = plot.font()
                    font.setPixelSize(16)
                    plot.setFont(font)
                plot.resize(*(570, 350) if pair_trajectory else (850, 450))
                plot.set_trajectory(trajectory, self.t("analysis.report.run", run=run["run_id"]))
                yield ReportFigure("weight_trajectory", title, plot.grab().toImage())
            finally:
                plot.deleteLater()

    def report_single_plot_image(self, mapping, rows, tolerance, *, compact=False):
        plot = SollIstPlot(self, language_manager=self.language)
        try:
            plot.chart_colors_enabled = False
            font = plot.font()
            font.setPixelSize(17 if compact else 15)
            plot.setFont(font)
            plot.resize(*(570, 350) if compact else (1050, 340))
            plot.set_rows(rows, binary=mapping.get("data_type") == "binary", unit=mapping.get("unit"))
            plot.set_tolerance(tolerance, visible=tolerance > 0)
            return plot.grab().toImage()
        finally:
            plot.deleteLater()

    def report_combined_plot_image(self, source, result, *, compact=False):
        """Rendert die Ansicht „Alle Outputs“ mitsamt Legende für den Bericht."""
        rows, legend = self.combined_plot_data(source, result)
        panel = QWidget(self)
        try:
            panel.setStyleSheet("background-color:#ffffff; color:#243746;")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(8, 6, 8, 6)
            label = QLabel(legend, panel)
            label.setWordWrap(True)
            layout.addWidget(label)
            plot = SollIstPlot(panel, language_manager=self.language)
            plot.chart_colors_enabled = False
            plot.set_rows(rows)
            layout.addWidget(plot, 1)
            width, height = (570, 350) if compact else (900, 425)
            if compact:
                font = plot.font()
                font.setPixelSize(17)
                plot.setFont(font)
                label.setFont(font)
            panel.resize(width, height + max(0, label.heightForWidth(width - 16)))
            return panel.grab().toImage()
        finally:
            panel.deleteLater()

    def report_sensitivity_figures(self, source, *, print_layout=False):
        if not source.get("records") or not source.get("inputs"):
            return
        rows_per_page = 20
        pages_per_output = (len(source["inputs"]) + rows_per_page - 1) // rows_per_page
        figure_count = pages_per_output * len(source["outputs"])
        figure_number = 0
        for mapping in source["outputs"]:
            values = self.calculate_sensitivity(source, mapping)
            page_count = (len(values) + rows_per_page - 1) // rows_per_page
            output_label = self.characteristic_axis_label(mapping)
            plot = FeatureImportancePlot(self, language_manager=self.language)
            font = plot.font()
            font.setPixelSize(17)
            plot.setFont(font)
            try:
                for page, start in enumerate(range(0, len(values), rows_per_page), 1):
                    rows = values[start:start + rows_per_page]
                    figure_number += 1
                    paired = print_layout and (figure_number < figure_count or figure_count % 2 == 0)
                    plot.set_values(rows, maximum=100.0)
                    plot.resize(570 if paired else 900, 34 + 28 * len(rows))
                    label = output_label
                    if page_count > 1:
                        label += f" ({page}/{page_count})"
                    yield label, plot.grab().toImage()
            finally:
                plot.deleteLater()

    def report_output_summary(self, mapping, rows):
        if not rows:
            return self.t("analysis.report.no_output_data"), 0.0
        if mapping.get("data_type") == "binary":
            correct = sum(not row["binary_error"] for row in rows)
            return self.t(
                "analysis.tolerance.binary_summary",
                correct=correct, total=len(rows), incorrect=len(rows) - correct,
            ), 0.0

        key = self.tolerance_key(mapping)
        if key not in self.tolerances:
            raw_values = [row["target"] for row in rows]
            raw_range = max(raw_values) - min(raw_values)
            self.tolerances[key] = 5.0 if mapping.get("unit") == "%" else raw_range * 0.05
        tolerance = float(self.tolerances[key])
        inside = sum(row["raw_absolute"] <= tolerance for row in rows)
        return self.t(
            "analysis.report.tolerance_result",
            inside=inside, total=len(rows), tolerance=self.display_number(tolerance),
            unit=str(mapping.get("unit") or ""),
        ), tolerance

    def report_figures(self, run, source, result, *, print_layout=False):
        for curve_key, title_key, image_key in (
            ("curve_points", "analysis.report.active_curve", "error_curve"),
            ("maximum_error_curve_points", "analysis.report.active_maximum_curve", "maximum_error_curve"),
        ):
            curve = run.get(curve_key)
            if not curve:
                continue
            logarithmic = self.report_curve_is_logarithmic(curve)
            scale = self.t("analysis.report.scale_logarithmic" if logarithmic else "analysis.report.scale_linear")
            caption = " · ".join((
                self.t("analysis.report.run", run=run.get("run_id", "–")),
                self.report_datetime(run.get("timestamp")),
                self.t("analysis.report.epoch_count", epochs=self.report_integer(run.get("completed_epochs"))),
                scale,
            ))
            yield ReportFigure(
                image_key, self.t(title_key),
                self.report_error_curve_image(
                    curve, self.t("history.chart.epoch"), logarithmic, compact=print_layout,
                ),
                caption=caption,
            )

        outputs = source.get("outputs", ())
        has_scatter = bool(outputs and result["rows"])
        trajectory = run.get("weight_trajectory")
        paired = print_layout and has_scatter and bool(trajectory and len(trajectory.get("points", ())) > 1)
        yield from self.report_training_figures(run, compact=print_layout, pair_trajectory=paired)

        if has_scatter:
            title = self.t("analysis.report.output_results")
            if len(outputs) > 1:
                yield ReportFigure(
                    "scatter_all", title, self.report_combined_plot_image(source, result, compact=paired),
                    subtitle=self.t("analysis.output_all"),
                )
            else:
                mapping = outputs[0]
                rows = result["rows"]
                summary, tolerance = self.report_output_summary(mapping, rows)
                image = self.report_single_plot_image(mapping, rows, tolerance, compact=paired)
                yield ReportFigure("scatter_0", title, image, self.report_output_title(mapping), summary)

        for index, (label, image) in enumerate(self.report_sensitivity_figures(source, print_layout=print_layout)):
            yield ReportFigure(
                f"sensitivity_{index}", self.t("analysis.tab.sensitivity"), image, label,
                self.t("analysis.sensitivity.explanation") if index == 0 else "",
            )

    @staticmethod
    def report_classification_targets(source):
        """Recognize dimensionless class scores with exactly one 1 per record."""
        outputs = source.get("outputs", ())
        if len(outputs) < 2 or any(
            mapping.get("data_type") == "binary" or str(mapping.get("unit") or "").strip()
            for mapping in outputs
        ):
            return []
        targets = []
        for record in source["records"]:
            values = [record[mapping["column_index"]] for mapping in outputs]
            if values.count(1) != 1 or any(value not in (0, 1) for value in values):
                return []
            targets.append(outputs[values.index(1)]["neuron"].id)
        return targets

    def report_classification_rows(self, source, result):
        """Count one decision per record, keeping training and test results separate."""
        basis = next((item for item in self.sources if item["kind"] == "training"), source)
        basis_targets = self.report_classification_targets(basis)
        if len(set(basis_targets)) < 2:
            return []

        locale = QLocale(self.language.current_language)
        summaries = []
        for item in self.sources:
            targets = basis_targets if item is basis else self.report_classification_targets(item)
            if not targets:
                continue
            analysis = result if item is source else self.calculate(item)
            predictions = defaultdict(dict)
            for row in analysis["rows"]:
                predictions[row["record"]][row["neuron_id"]] = row["actual"]

            output_count = len(item["outputs"])
            correct = 0
            for record, target in enumerate(targets, 1):
                scores = predictions[record]
                if len(scores) != output_count or target not in scores:
                    break
                correct += all(scores[target] > score for neuron_id, score in scores.items() if neuron_id != target)
            else:
                total = len(targets)
                summaries.append((item["label"], self.t(
                    "analysis.report.classified",
                    correct=locale.toString(correct),
                    total=locale.toString(total),
                    percent=locale.toString(100 * correct / total, "f", 1),
                )))
        return summaries

    def report_output_notes(self, source, result):
        outputs = source.get("outputs", ())
        if len(outputs) == 1 and result["rows"]:
            return
        for mapping in outputs:
            rows = [row for row in result["rows"] if row["neuron_id"] == mapping["neuron"].id]
            summary, _ = self.report_output_summary(mapping, rows)
            yield self.characteristic_axis_label(mapping), summary

    def report_figure_pages(self, run, source, result, *, print_layout=False):
        """Group related charts in pairs for the report formats."""
        page = []
        previous_group = None
        self.report_export_phase("analysis.report.progress.figures", count=0)
        figures = self.report_figures(run, source, result, print_layout=print_layout)
        for count, figure in enumerate(figures, 1):
            self.report_export_phase("analysis.report.progress.figures", count=count)
            if figure.key in {"error_curve", "maximum_error_curve"}:
                group = "training_figure" if print_layout else "training_error"
            elif figure.key == "weight_trajectory" or figure.key.startswith("scatter_"):
                group = "training_result"
            else:
                group = figure.key.rpartition("_")[0]
            if page and (len(page) == 2 or group != previous_group):
                yield page
                page = []
            page.append(figure)
            previous_group = group
        if page:
            yield page

    def report_initialization_lines(self, run, training_history):
        parent_run_id = run.get("parent_run_id")
        if parent_run_id is not None:
            return [self.t("history.initialization.changed_parameters", run=parent_run_id)]

        lines = []
        start_state = run.get("initial_network_state")
        run_id = run.get("run_id")
        if start_state and isinstance(run_id, int):
            for entry in training_history:
                source_id = entry.get("run_id")
                if isinstance(source_id, int) and source_id < run_id and entry.get("initial_network_state") == start_state:
                    lines.append(self.t("history.initialization.repeated", run=source_id))
                    run = entry
                    break

        if run.get("initialized") is False or run.get("parent_run_id") is not None:
            return lines or [self.t("analysis.report.initialization_existing")]

        weights_key = {
            "auto": "training.initialization.auto_recommended",
            "xavier": "training.initialization.xavier_all",
            "he": "training.initialization.he_all",
            "zero": "training.initialization.weights_zero",
        }.get(run.get("weight_initialization"))
        bias_key = {
            "zero": "training.initialization.bias_zero",
            "xavier": "training.initialization.xavier",
        }.get(run.get("bias_initialization"))
        for label_key, method_key in (
            ("training.initialization.weights", weights_key),
            ("training.initialization.bias", bias_key),
        ):
            method = self.t(method_key) if method_key else "–"
            lines.append(f"{self.t(label_key)} {method}")
        return lines

    def report_history_rows(self, training_history, active_run_id):
        history_rows = [[self.t(key).rstrip(":") for key, _ in self.REPORT_HISTORY_COLUMNS]]
        for entry in reversed(training_history):
            run_number = str(entry.get("run_id", "–"))
            if entry.get("run_id") == active_run_id:
                run_number += f" – {self.t('history.active')}"
            history_rows.append([
                run_number,
                self.report_datetime(entry.get("timestamp")),
                self.t("adam.solver." + entry.get("solver", "sgd")),
                self.report_decimal(entry.get("learning_rate"), 6),
                self.report_decimal(entry.get("momentum", 0.0), 2),
                self.report_integer(entry.get("completed_epochs")),
                self.report_decimal(entry.get("end_error"), 6),
                self.report_decimal(entry.get("maximum_absolute_error"), 6),
                f"{self.report_decimal(entry.get('elapsed_seconds'), 1)} s",
            ])
        return history_rows

    REPORT_TRAINING_COLUMNS = (
        ("analysis.report.training_column", 23),
        ("data.column_properties.name", 28),
        ("data.column_properties.unit", 10),
        ("data.column_properties.data_type", 12),
        ("forward.column.scaling", 27),
    )

    def report_training_data(self):
        document = self.report_context.get("training_document")
        if document is None:
            return None

        locale = QLocale(self.language.current_language)
        count = f"{self.t('training.data.records')} {locale.toString(len(document.get('records', ())))}"
        rows = [[self.t(key).rstrip(":") for key, _ in self.REPORT_TRAINING_COLUMNS]]
        for index, column in enumerate(document.get("columns", ()), 1):
            binary = column.get("data_type") == "binary"
            calibration = TrainingDataIO.normalize_calibration(column.get("calibration"))
            mode = "none" if binary else calibration["mode"]
            scaling = self.t(f"data.calibration.{mode}")
            if mode in ("minmax_0_1", "minmax_minus1_1"):
                scaling += "\n" + self.t(
                    "analysis.report.training_raw_range",
                    minimum=locale.toString(calibration["source_min"], "g", 8),
                    maximum=locale.toString(calibration["source_max"], "g", 8),
                )
            mapping = [str(index)]
            neuron_id = column.get("mapped_neuron_id")
            if neuron_id is not None:
                mapping.append(f"N{neuron_id}")
            mapping.append(self.t(f"analysis.report.training_{column['role']}"))
            rows.append([
                " · ".join(mapping),
                column.get("name") or "–",
                column.get("unit") or "–",
                self.t("data.type.binary" if binary else "data.type.analog"),
                scaling,
            ])
        return count, rows

    def report_operations_per_epoch(self):
        document = self.report_context.get("training_document") or {}
        records = document.get("records")
        if not records:
            return "–"
        operations = estimate_training_operations(
            int(self.report_context.get("connections", 0)), len(records)
        )
        return self.t(
            "analysis.report.operations_estimate",
            operations=QLocale(self.language.current_language).toString(operations),
        )

    def report_title(self):
        project_name = self.report_context.get("project_name") or self.t("common.unknown")
        return self.t("analysis.report.heading", project=project_name)

    def build_report_markup(self, *, inline_images=False, pdf_width=None):
        """Erstellt den Berichtstext und formatiert Tabellen und Rahmen für das Zielformat."""
        source = self.current_source() or {}
        result = (self.current_result or self.calculate(source)) if source else {"rows": []}
        run = self.report_context.get("training_run") or {}
        context = self.report_context
        training_history = [
            entry for entry in context.get("training_history", [])
            if isinstance(entry, dict)
        ]
        active_run_id = context.get("active_training_run_id", run.get("run_id"))
        images = {}
        pdf_table = '<table width="100%" cellspacing="0" cellpadding="{padding}">'
        pdf_grid = pdf_frame_marker("grid") + pdf_table
        table_tag = pdf_grid.format(padding=5) if pdf_width else "<table>"
        facts_table = '<table class="report-facts">' if inline_images else table_tag
        first_cell = '<td width="29%">' if pdf_width else "<td>"
        number_cell = '<td class="report-number">' if inline_images else "<td>"
        scroll_open = '<div class="table-scroll" tabindex="0">' if inline_images else ""
        scroll_close = "</div>" if inline_images else ""
        section_open = "<div class='section'>"
        pdf_gap = '<p style="margin:0;font-size:5pt">&nbsp;</p>'
        if pdf_width:
            section_open += (
                pdf_gap + '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                '<td bgcolor="#d7e2ec"><p style="margin:0;font-size:1px">&nbsp;</p></td></tr></table>'
                + pdf_gap
            )

        def pdf_cell(content, *, width="100%"):
            return f'<td width="{width}" valign="top">{content}</td>'

        def pdf_card(content, *, keep_together=False, keep_with_next=False):
            return (
                pdf_frame_marker("card", keep_together=keep_together, keep_with_next=keep_with_next)
                + '<table width="100%" cellspacing="0" cellpadding="8"><tr>'
                + pdf_cell(content) + "</tr></table>" + pdf_gap
            )

        def pdf_pair(left, right, *, keep_together=False):
            padding = 6 if keep_together else 8
            return (
                pdf_frame_marker("pair", keep_together=keep_together)
                + f'<table width="100%" cellspacing="0" cellpadding="{padding}"><tr>'
                + pdf_cell(left, width="49%")
                + '<td width="2%" style="padding:0"></td>'
                + pdf_cell(right, width="49%") + "</tr></table>" + pdf_gap
            )

        def pdf_image(url, image, width, label):
            images[url] = image
            return (
                f'<p align="center"><img src="{url}" width="{width}" '
                f'alt="{escape(label)}"></p>'
            )

        def image_markup(url, image, frame, width, label):
            if inline_images:
                png = b64encode(self.image_png_bytes(image)).decode("ascii")
                return (
                    f'<img src="data:image/png;base64,{png}" '
                    f'width="{image.width()}" height="{image.height()}" alt="{escape(label)}">'
                )
            if pdf_width:
                image_content = pdf_image(url, image, min(width, pdf_width - 20), label)
                return pdf_card(
                    image_content + f'<p class="pdf-caption">{escape(label)}</p>', keep_together=True,
                )
            images[url] = image
            return (
                f'<div class="{frame}">'
                f'<img src="{url}" width="{width}" alt="{escape(label)}" /></div>'
            )

        if inline_images:
            project_name = context.get("project_name") or self.t("common.unknown")
            header = (
                f'<header><p class="eyebrow">{escape(self.t("analysis.report.web_label"))}</p>'
                f"<h1>{escape(str(project_name))}</h1></header>"
            )
            overview_start = '<div class="report-meta">' + facts_table
        elif pdf_width:
            project_name = context.get("project_name") or self.t("common.unknown")
            overview_start = (
                f'<p class="pdf-eyebrow" align="center">{escape(self.t("analysis.report.web_label").upper())}</p>'
                f'<h1 align="center">{escape(str(project_name))}</h1>'
                + pdf_frame_marker("meta") + pdf_table.format(padding=5)
            )
        else:
            overview_start = f"<h1 style='text-align:center'>{escape(self.report_title())}</h1>{table_tag}"
        html = [
            overview_start,
            f"<tr>{first_cell}{escape(self.t('analysis.report.data_origin'))}</td><td>{escape(str(context.get('training_data_origin') or self.t('data.origin.unspecified')))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.created'))}</td><td>{escape(self.report_datetime(datetime.now(), include_seconds=False))}</td></tr>",
        ]
        if run:
            html.append(
                f"<tr><td>{escape(self.t('analysis.report.active_run'))}</td>"
                f"<td>{escape(self.t('analysis.report.run', run=run.get('run_id', '–')))}</td></tr>"
            )
        html.append("</table></div>" if inline_images else "</table>")
        description = str(context.get("project_description") or "").strip()
        if inline_images:
            if description:
                html.append(author_html_export.project_description_html(
                    description, self.t("project_description.title")
                ))
            overview = html
            html = []
        elif pdf_width:
            html.append(pdf_gap)
            if description:
                intro, inputs, outputs = report_description_parts(description)
                heading = f"<h2>{escape(self.t('project_description.title'))}</h2>"
                html.append(pdf_card(heading + intro))
                if inputs and outputs:
                    html.append(pdf_pair(inputs, outputs))
            overview = html
            html = []
        elif description:
            html.extend([
                f"<h2>{escape(self.t('project_description.title'))}</h2>",
                f"<div>{description}</div>",
            ])
        self.report_export_phase("analysis.report.progress.tables")
        training_data = self.report_training_data()
        if training_data is not None:
            count, (headers, *rows) = training_data
            columns_table = (
                '<table class="training-data-table">' if inline_images
                else pdf_grid.format(padding=4) if pdf_width else "<table>"
            )
            html.extend([
                f"{section_open}<h2>{escape(self.t('training.data.group'))}</h2>",
                f"<p>{escape(count)}</p>",
                scroll_open + columns_table + "<thead><tr>",
                *(f'<th width="{width}%">{escape(label)}</th>'
                  for label, (_, width) in zip(headers, self.REPORT_TRAINING_COLUMNS)),
                "</tr></thead><tbody>",
            ])
            for row in rows:
                cells = ("<br>".join(escape(line) for line in value.splitlines()) for value in row)
                html.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
            html.append("</tbody></table>" + scroll_close + "</div>")

        self.report_export_phase("analysis.report.progress.network")
        network_image = self.report_network_image(
            image_width=2100 if pdf_width else 1400,
            transparent_background=inline_images or bool(pdf_width),
        )
        network_title = escape(self.t("analysis.report.network"))
        network_markup = [
            f"<h2>{network_title}</h2>",
            facts_table,
            f"<tr><td width='29%'>{escape(self.t('project_overview.structure'))}</td><td>{escape(str(context.get('structure','–')))}</td></tr>",
            f"<tr><td>{escape(self.t('project_overview.neurons'))}</td>{number_cell}{int(context.get('neurons',0))}</td></tr>",
            f"<tr><td>{escape(self.t('project_overview.connections'))}</td>{number_cell}{int(context.get('connections',0))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.operations_per_epoch'))}</td>{number_cell}{escape(self.report_operations_per_epoch())}</td></tr>",
            "</table>",
        ]
        network_figure = ""
        if network_image is not None:
            network_figure = image_markup(
                "report:network", network_image, "network-frame", 680,
                self.t("analysis.report.network"),
            )
        if inline_images:
            if network_figure:
                network_figure = (
                    f'<figure class="report-figure network-figure">{network_figure}'
                    f"<figcaption>{network_title}</figcaption></figure>"
                )
            html = [
                header, *overview, '<div class="section">',
                *network_markup, network_figure, "</div>", *html,
            ]
        elif pdf_width:
            html = [*overview, section_open, *network_markup, network_figure, "</div>", *html]
        else:
            html.extend([section_open, *network_markup, network_figure, "</div>"])
        if training_history or run:
            html.append(
                f"{section_open}<h2 style='text-align:center'>{escape(self.t('analysis.report.training'))}</h2>"
            )
        if training_history:
            header, *history_rows = self.report_history_rows(training_history, active_run_id)
            history_table = (
                '<table class="history-table">' if inline_images
                else pdf_grid.format(padding=4) if pdf_width else "<table>"
            )
            cell_style = "" if pdf_width or inline_images else "style='padding:3px;border:1px solid #b7c1cc'"
            font_size = "8.5pt" if pdf_width else "7pt"

            def history_cell(value):
                value = escape(value)
                return value if inline_images else f'<span style="font-size:{font_size}">{value}</span>'

            html.extend([
                f"<h3 style='text-align:center'>{escape(self.t('analysis.report.training_runs'))}</h3>",
                scroll_open + history_table + "<thead><tr>",
                *(f'<th width="{width}%" {cell_style}>{history_cell(title)}</th>'
                  for title, (_, width) in zip(header, self.REPORT_HISTORY_COLUMNS)),
                "</tr></thead><tbody>",
            ])
            for row in history_rows:
                html.extend([
                    "<tr>",
                    *(f'<td {cell_style}>{history_cell(value)}</td>' for value in row),
                    "</tr>",
                ])
            html.append("</tbody></table>" + scroll_close)
        if run:
            initialization = "<br>".join(
                escape(line) for line in self.report_initialization_lines(run, training_history)
            )
            html.extend([
                "<div style='page-break-inside:avoid'>",
                f"<h3 style='text-align:center'>{escape(self.t('analysis.report.active_run_details'))}</h3>",
                facts_table,
                f"<tr>{first_cell}{escape(self.t('analysis.source.label'))}</td><td>{escape(str(source.get('label') or '–'))}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.data_file'))}</td><td>{escape(str(source.get('file_path') or '–'))}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.date'))}</td><td>{escape(self.report_datetime(run.get('timestamp')))}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.epochs'))}</td>{number_cell}{self.report_integer(run.get('completed_epochs'))}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.duration'))}</td>{number_cell}{self.report_decimal(run.get('elapsed_seconds'), 1)} s</td></tr>",
                f"<tr><td>{escape(self.t('training.parameters.learning_rate'))}</td>{number_cell}{self.report_decimal(run.get('learning_rate'), 6)}</td></tr>",
                f"<tr><td>{escape(self.t('training.parameters.momentum'))}</td>{number_cell}{self.report_decimal(run.get('momentum', 0.0), 2)}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.error_limit'))}</td>{number_cell}{self.report_decimal(run.get('error_limit'), 6)}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.requested_epochs'))}</td>{number_cell}{self.report_integer(run.get('requested_epochs'))}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.initialization'))}</td><td>{initialization}</td></tr>",
                f"<tr><td>{escape(self.t('analysis.report.mode'))}</td><td>{escape(self.t('analysis.report.fast_mode' if run.get('fast_mode') else 'analysis.report.normal_mode'))}</td></tr>",
                f"<tr><td>{escape(self.t('project_overview.mean_error'))}</td>{number_cell}{self.report_decimal(run.get('end_error'), 6)}</td></tr>",
                f"<tr><td>{escape(self.t('training.result.maximum_error'))}</td>{number_cell}{self.report_decimal(run.get('maximum_absolute_error'), 6)}</td></tr>",
                "</table></div>",
            ])
        if training_history or run:
            html.append("</div>")

        for figures in self.report_figure_pages(
            run, source, result, print_layout=bool(pdf_width),
        ):
            if inline_images:
                layout = " report-pair" if len(figures) == 2 else ""
                html.append(f'<div class="section figure-page{layout}">')
                for figure in figures:
                    label = " · ".join(filter(None, (figure.title, figure.subtitle)))
                    title, subtitle = figure.headings
                    html.extend([
                        '<figure class="report-figure">',
                        f"<h2>{escape(title)}</h2>",
                    ])
                    if subtitle:
                        html.append(f"<h3>{escape(subtitle)}</h3>")
                    html.append(image_markup(
                        f"report:{figure.key}", figure.image, "chart-frame", 660, label,
                    ))
                    if figure.caption:
                        html.append(f"<figcaption>{escape(figure.caption)}</figcaption>")
                    html.append("</figure>")
                html.append("</div>")
                continue
            html.append("<div class='section figure-page'>")
            if pdf_width:
                pair = len(figures) == 2
                panels = []
                for figure in figures:
                    label = " · ".join(filter(None, (figure.title, figure.subtitle)))
                    if figure.key == "sensitivity_0" and figure.caption:
                        html.append(pdf_card(
                            f'<p>{escape(figure.caption)}</p>', keep_with_next=True,
                        ))
                    if pair:
                        width = int(pdf_width * .49) - 16
                    else:
                        aspect_ratio = figure.image.width() / figure.image.height()
                        width = min(pdf_width - 20, round(7.6 * 96 * aspect_ratio))
                    title = figure.title
                    if pair and figure.key in {"error_curve", "maximum_error_curve"}:
                        metric = "mse" if figure.key == "error_curve" else "maximum"
                        title = self.t(f"training.metric.{metric}")
                    panel = f"<h3>{escape(title)}</h3>"
                    if figure.subtitle:
                        panel += f"<p><strong>{escape(figure.subtitle)}</strong></p>"
                    panel += pdf_image(f"report:{figure.key}", figure.image, width, label)
                    if figure.caption and figure.key != "sensitivity_0":
                        panel += f'<p class="pdf-caption">{escape(figure.caption)}</p>'
                    panels.append(panel)
                if pair:
                    html.append(pdf_pair(*panels, keep_together=True))
                else:
                    html.extend(pdf_card(panel, keep_together=True) for panel in panels)
            else:
                for figure in figures:
                    html.append(f'<div class="report-figure" style="--figure-width:{figure.width_inches:.3f}in">')
                    html.append(f"<h2 style='text-align:center'>{escape(figure.title)}</h2>")
                    if figure.subtitle:
                        html.append(f"<h3 style='text-align:center'>{escape(figure.subtitle)}</h3>")
                    if figure.caption:
                        html.append(f"<p style='text-align:center'>{escape(figure.caption)}</p>")
                    label = " · ".join(filter(None, (figure.title, figure.subtitle)))
                    html.append(image_markup(f"report:{figure.key}", figure.image, "chart-frame", 660, label))
                    html.append("</div>")
            html.append("</div>")

        classification = self.report_classification_rows(source, result) if inline_images or pdf_width else []
        output_notes = classification or list(self.report_output_notes(source, result))
        if output_notes:
            title_key = "analysis.report.classification" if classification else "analysis.report.output_results"
            notes = [f"<h2>{escape(self.t(title_key))}</h2>"]
            note_alignment = "" if pdf_width else " style='text-align:center'"
            for label, summary in output_notes:
                notes.append(f"<h3>{escape(label)}</h3>")
                notes.append(
                    f'<p class="classification-score"><strong>{escape(summary)}</strong></p>'
                    if classification else f"<p{note_alignment}>{escape(summary)}</p>"
                )
            if classification:
                notes.append(f'<p class="note">{escape(self.t("analysis.report.classification_rule"))}</p>')
            notes_markup = "".join(notes)
            if pdf_width:
                notes_markup = pdf_card(notes_markup)
            elif inline_images:
                notes_markup = f'<div class="report-result">{notes_markup}</div>'
            html.extend([section_open, notes_markup, "</div>"])
        if result["rows"]:
            deviations_table = (
                '<table class="deviation-table">' if inline_images
                else pdf_grid.format(padding=2) if pdf_width else table_tag
            )
            html.extend([
                f"{section_open}<h2>{escape(self.t('analysis.deviations.group'))}</h2>",
                scroll_open + deviations_table + "<thead><tr>",
                f"<th>{escape(self.t('analysis.column.record'))}</th>",
                f"<th>{escape(self.t('analysis.column.output'))}</th>",
                f"<th>{escape(self.t('analysis.column.target'))}</th>",
                f"<th>{escape(self.t('analysis.column.actual'))}</th>",
                f"<th>{escape(self.t('analysis.column.deviation'))}</th></tr></thead><tbody>",
            ])
            for row in result["rows"][:20]:
                target, actual, deviation = self.report_deviation_values(row)
                html.append(
                    "<tr>" + "".join(
                        f"<td>{escape(str(value))}</td>" for value in (
                            row["record"], row["output"], target, actual, deviation,
                        )
                    ) + "</tr>"
                )
            html.append("</tbody></table>" + scroll_close)
            if any(str(row.get("unit") or "").strip() == "%" for row in result["rows"][:20]):
                html.append(f"<p>{escape(self.t('analysis.report.percentage_note'))}</p>")
            html.append("</div>")
        return "\n".join(html), images

    def export_pdf_report(self, file_path=None):
        """Erstellt einen kompakten PDF-Bericht des aktiven Trainingsstands."""
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.t("analysis.report.title"),
                self.report_default_path("pdf"),
                self.t("analysis.report.filter"),
            )
        if not file_path:
            return
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        return self.run_report_export(file_path, self.write_pdf_report)

    def write_pdf_report(self, file_path):
        layout_dpi = 96
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
            QMarginsF(16, 16, 16, 16), QPageLayout.Unit.Millimeter,
        )
        page = page_layout.paintRectPixels(layout_dpi)
        markup, images = self.build_report_markup(pdf_width=page.width())
        self._operation_progress.save(
            lambda: self.write_pdf_file(file_path, page_layout, layout_dpi, markup, images)
        )

    @classmethod
    def write_pdf_file(cls, file_path, page_layout, layout_dpi, markup, images):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageLayout(page_layout)
        printer.setFontEmbeddingEnabled(True)
        printer.setResolution(300)

        # Lay out text at a fixed DPI and paint directly to preserve fonts and images.
        page = page_layout.paintRectPixels(layout_dpi)
        layout_device = QImage(1, 1, QImage.Format.Format_RGB32)
        layout_device.setDotsPerMeterX(round(layout_dpi / 0.0254))
        layout_device.setDotsPerMeterY(round(layout_dpi / 0.0254))
        document = QTextDocument()
        document.documentLayout().setPaintDevice(layout_device)
        document.setDefaultFont(QFont("Segoe UI", 10))
        document.setDocumentMargin(0)
        for url, image in images.items():
            document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(url), image)
        document.setHtml(f"<style>{cls.PDF_REPORT_CSS}</style>{markup}")
        document.setPageSize(page.size())
        frames_by_page = prepare_pdf_frames(document, page.width(), page.height())

        painter = QPainter()
        if not painter.begin(printer):
            raise OSError(file_path)
        try:
            painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            scale = printer.resolution() / layout_dpi
            for index, frames in enumerate(frames_by_page):
                if index and not printer.newPage():
                    raise OSError(file_path)
                top = index * page.height()
                painter.save()
                painter.scale(scale, scale)
                painter.translate(0, -top)
                draw_pdf_frames(painter, frames, background=True)
                document.drawContents(painter, QRectF(0, top, page.width(), page.height()))
                draw_pdf_frames(painter, frames, background=False)
                painter.restore()
        finally:
            painter.end()

    def export_html_report(self, file_path):
        """Speichert einen eigenständigen HTML-Bericht mit eingebetteten Grafiken."""
        if author_html_export is None:
            return False
        return self.run_report_export(file_path, self.write_html_report)

    def write_html_report(self, file_path):
        if author_html_export is None:
            return
        markup, _ = self.build_report_markup(inline_images=True)
        document = author_html_export.project_report_html(
            self.language.current_language, self.report_title(), markup
        )
        self._operation_progress.save(lambda: author_html_export.write_html_file(file_path, document))

    def export_word_report(self, file_path=None):
        """Erstellt einen bearbeitbaren Word-Bericht im DOCX-Format."""
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.t("analysis.report.word_title"),
                self.report_default_path("docx"),
                self.t("analysis.report.word_filter"),
            )
        if not file_path:
            return
        if not file_path.lower().endswith(".docx"):
            file_path += ".docx"
        return self.run_report_export(file_path, self.write_word_report)

    def write_word_report(self, file_path):
        source = self.current_source() or {}
        result = (self.current_result or self.calculate(source)) if source else {"rows": []}
        run = self.report_context.get("training_run") or {}
        context = self.report_context
        training_history = [
            entry for entry in context.get("training_history", [])
            if isinstance(entry, dict)
        ]
        active_run_id = context.get("active_training_run_id", run.get("run_id"))
        report_title = self.report_title()
        report = DocxReport(report_title)
        report.paragraph(self.t("analysis.report.web_label").upper(), style="ReportLabel",
                         centered=True, keep_next=True)
        report.paragraph(context.get("project_name") or self.t("common.unknown"),
                         style="Title", centered=True, keep_next=True)
        header_rows = [
            [self.t("analysis.report.data_origin"), context.get("training_data_origin") or self.t("data.origin.unspecified")],
            [self.t("analysis.report.created"), self.report_datetime(datetime.now(), include_seconds=False)],
        ]
        if run:
            header_rows.append([
                self.t("analysis.report.active_run"),
                self.t("analysis.report.run", run=run.get("run_id", "–")),
            ])
        report.table(header_rows, widths=[2, 5], keep_together=True, shaded=True)
        description = str(context.get("project_description") or "").strip()
        if description:
            intro, inputs, outputs = report_description_parts(description)

            def write_description():
                report.heading(self.t("project_description.title"), 2)
                report.formatted_html(intro)

            report.panels(write_description)
            if inputs and outputs:
                report.panels(
                    lambda: report.formatted_html(inputs),
                    lambda: report.formatted_html(outputs),
                )

        self.report_export_phase("analysis.report.progress.tables")
        training_data = self.report_training_data()
        if training_data is not None:
            count, rows = training_data
            report.heading(self.t("training.data.group"), 1)
            report.paragraph(count, keep_next=True)
            report.table(
                rows, widths=[width for _, width in self.REPORT_TRAINING_COLUMNS],
                header=True,
            )

        report.heading(self.t("analysis.report.network"), 1)
        report.table([
            [self.t("project_overview.structure"), context.get("structure", "–")],
            [self.t("project_overview.neurons"), context.get("neurons", 0)],
            [self.t("project_overview.connections"), context.get("connections", 0)],
            [self.t("analysis.report.operations_per_epoch"), self.report_operations_per_epoch()],
        ], widths=[2, 5])
        self.report_export_phase("analysis.report.progress.network")
        network_image = self.report_network_image(transparent_background=True)
        if network_image is not None:
            def write_network():
                report.image(
                    self.image_png_bytes(network_image), network_image.width(), network_image.height(),
                    width_inches=min(report.panel_image_width(), 7.6 * network_image.width() / network_image.height()),
                    alt_text=self.t("analysis.report.network"),
                )

            report.panels(write_network, keep_together=True)

        if training_history or run:
            report.heading(self.t("analysis.report.training"))
        if training_history:
            report.heading(
                self.t("analysis.report.training_runs"), 2
            )
            report.table(
                self.report_history_rows(training_history, active_run_id),
                widths=[width for _, width in self.REPORT_HISTORY_COLUMNS],
                header=True,
                font_points=8.5,
            )
        if run:
            report.heading(
                self.t("analysis.report.active_run_details"), 2
            )
            report.table([
                [self.t("analysis.source.label"), source.get("label") or "–"],
                [self.t("analysis.report.data_file"), source.get("file_path") or "–"],
                [self.t("analysis.report.date"), self.report_datetime(run.get("timestamp"))],
                [self.t("analysis.report.epochs"), self.report_integer(run.get("completed_epochs"))],
                [self.t("analysis.report.duration"), f"{self.report_decimal(run.get('elapsed_seconds'), 1)} s"],
                [self.t("training.parameters.learning_rate"), self.report_decimal(run.get("learning_rate"), 6)],
                [self.t("training.parameters.momentum"), self.report_decimal(run.get("momentum", 0.0), 2)],
                [self.t("analysis.report.error_limit"), self.report_decimal(run.get("error_limit"), 6)],
                [self.t("analysis.report.requested_epochs"), self.report_integer(run.get("requested_epochs"))],
                [self.t("analysis.report.initialization"),
                 "\n".join(self.report_initialization_lines(run, training_history))],
                [self.t("analysis.report.mode"),
                 self.t("analysis.report.fast_mode" if run.get("fast_mode") else "analysis.report.normal_mode")],
                [self.t("project_overview.mean_error"), self.report_decimal(run.get("end_error"), 6)],
                [self.t("training.result.maximum_error"), self.report_decimal(run.get("maximum_absolute_error"), 6)],
            ], widths=[2, 5], keep_together=True)

        def write_figure(figure, column_count):
            title, subtitle = figure.headings
            report.heading(title, 2)
            if subtitle:
                report.paragraph(subtitle, bold=True, keep_next=True)
            image = figure.image
            width_inches = min(
                report.panel_image_width(column_count),
                7.6 * image.width() / image.height(),
            )
            # Keep the six-point corner radius consistent at both column widths.
            corner_radius = 6 * image.width() / (72 * width_inches)
            report.image(
                self.image_png_bytes(image, corner_radius=corner_radius),
                image.width(), image.height(),
                width_inches=width_inches,
                alt_text=" · ".join(filter(None, (figure.title, figure.subtitle))),
            )
            if figure.caption and figure.key != "sensitivity_0":
                report.paragraph(figure.caption, style="ReportCaption")

        for figures in self.report_figure_pages(run, source, result, print_layout=True):
            first = figures[0]
            if first.key == "sensitivity_0" and first.caption:
                report.panels(
                    lambda: report.paragraph(first.caption, keep_next=True),
                    keep_together=True, keep_with_next=True,
                )
            report.panels(
                *(lambda figure=figure: write_figure(figure, len(figures)) for figure in figures),
                keep_together=True,
            )

        classification = self.report_classification_rows(source, result)
        output_notes = classification or list(self.report_output_notes(source, result))
        if output_notes:
            title_key = "analysis.report.classification" if classification else "analysis.report.output_results"
            report.heading(self.t(title_key))

            def write_output_notes():
                for title, summary in output_notes:
                    report.paragraph(title, bold=True, keep_next=True)
                    report.paragraph(summary)
                if classification:
                    report.paragraph(self.t("analysis.report.classification_rule"), style="ReportCaption")

            report.panels(write_output_notes)

        if result["rows"]:
            report.heading(self.t("analysis.deviations.group"), 1)
            deviation_rows = [[
                self.t("analysis.column.record"),
                self.t("analysis.column.output"),
                self.t("analysis.column.target"),
                self.t("analysis.column.actual"),
                self.t("analysis.column.deviation"),
            ]]
            for row in result["rows"][:20]:
                target, actual, deviation = self.report_deviation_values(row)
                deviation_rows.append([
                    row["record"], row["output"], target, actual, deviation,
                ])
            report.table(deviation_rows, widths=[1, 2, 1.2, 1.2, 1.4], header=True)
            if any(str(row.get("unit") or "").strip() == "%" for row in result["rows"][:20]):
                report.paragraph(self.t("analysis.report.percentage_note"))
        self._operation_progress.save(lambda: report.save(file_path))

    @staticmethod
    def table_item(value, numeric=False):
        item = QTableWidgetItem(str(value))
        if numeric:
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        return item
