# -------------------------------------------------------------------------------------------------
# Datei: resultanalysisdialog.py
# Zweck: Analysiert und vergleicht Ergebnisse aus Trainings- und Testdaten.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from collections import defaultdict
from datetime import datetime
from html import escape
from math import log10
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMarginsF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QImage, QPageLayout, QPainter, QPen, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from docxreport import DocxReport
from language import LanguageManager
from numberformat import format_number
from trainingdataio import TrainingDataIO
from analysisplot import FeatureImportancePlot, SollIstPlot


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
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.network = network
        self.sources = list(sources)
        self.tolerances = tolerances if isinstance(tolerances, dict) else {}
        self.report_context = report_context if isinstance(report_context, dict) else {}
        self.current_result = None
        self.results_by_source = {}
        self.sensitivity_cache = {}

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
        selector_layout.addWidget(QLabel(self.t("analysis.output_selector")))
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

        output_group = QGroupBox(self.t("analysis.outputs.group"))
        output_layout = QVBoxLayout(output_group)
        self.output_table = QTableWidget()
        self.configure_table(self.output_table)
        self.output_table.setColumnCount(7)
        self.output_table.setHorizontalHeaderLabels([
            self.t("analysis.column.record"),
            self.t("analysis.column.output"),
            self.t("analysis.column.target"),
            self.t("analysis.column.actual"),
            self.t("analysis.column.deviation"),
            self.t("analysis.column.mean_deviation"),
            self.t("analysis.column.binary_result"),
        ])
        output_layout.addWidget(self.output_table)
        overview_layout.addWidget(output_group, 1)

        deviations_group = QGroupBox(self.t("analysis.deviations.group"))
        deviations_layout = QVBoxLayout(deviations_group)
        deviations_note = QLabel(self.t("analysis.deviations.note"))
        deviations_note.setWordWrap(True)
        deviations_layout.addWidget(deviations_note)
        self.deviations_table = QTableWidget()
        self.configure_table(self.deviations_table)
        self.deviations_table.setColumnCount(5)
        self.deviations_table.setHorizontalHeaderLabels([
            self.t("analysis.column.record"),
            self.t("analysis.column.output"),
            self.t("analysis.column.target"),
            self.t("analysis.column.actual"),
            self.t("analysis.column.deviation"),
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
        plot_tolerance_controls.addWidget(
            QLabel(self.t("analysis.plot.tolerance_label"))
        )
        self.plot_tolerance_spin = QDoubleSpinBox()
        self.plot_tolerance_spin.setDecimals(6)
        self.plot_tolerance_spin.setRange(0.0, 1_000_000_000.0)
        self.plot_tolerance_spin.valueChanged.connect(
            self.plot_tolerance_changed
        )
        plot_tolerance_controls.addWidget(self.plot_tolerance_spin)
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
        self.tabs.addTab(self.plot_tab, self.t("analysis.tab.plot"))

        self.tolerance_tab = QWidget()
        tolerance_layout = QVBoxLayout(self.tolerance_tab)
        tolerance_controls = QHBoxLayout()
        tolerance_controls.addWidget(QLabel(self.t("analysis.tolerance.label")))
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setDecimals(6)
        self.tolerance_spin.setRange(0.0, 1_000_000_000.0)
        self.tolerance_spin.valueChanged.connect(self.refresh_tolerance)
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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.t("common.close")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.source_combo.currentIndexChanged.connect(self.refresh_analysis)
        self.output_combo.currentIndexChanged.connect(self.output_changed)
        self.tabs.currentChanged.connect(self.tab_changed)
        if initial_source_kind:
            for index, source in enumerate(self.sources):
                if source.get("kind") == initial_source_kind:
                    self.source_combo.setCurrentIndex(index)
                    break
        self.tabs.setCurrentIndex(max(0, min(4, int(initial_tab))))
        self.refresh_analysis()

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
        return self.source_combo.currentData()

    def selected_output_mapping(self):
        neuron_id = self.output_combo.currentData()
        source = self.current_source()
        if not source or neuron_id is None:
            return None
        return next(
            (mapping for mapping in source["outputs"] if mapping["neuron"].id == neuron_id),
            None,
        )

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
        self.output_combo.blockSignals(False)

    def ensure_specific_output(self):
        if self.output_combo.currentData() is None and self.output_combo.count() > 1:
            self.output_combo.setCurrentIndex(1)

    def tab_changed(self, index):
        if index in (2, 3, 4):
            self.ensure_specific_output()
        self.refresh_plot_and_tolerance()
        if index == 4:
            self.refresh_sensitivity()

    def output_changed(self, index=None):
        if self.tabs.currentIndex() in (2, 3, 4):
            self.ensure_specific_output()
        self.refresh_overview_tables()
        self.refresh_plot_and_tolerance()
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

    def calculate(self, source):
        snapshots = {
            neuron: self.neuron_runtime_snapshot(neuron)
            for neuron in self.network.get_neurons()
        }
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

        try:
            for record_number, record in enumerate(source["records"], start=1):
                self.network.reset_runtime_values()
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
                        "is_binary": is_binary,
                        "binary_error": binary_error,
                    })
        finally:
            for neuron, values in snapshots.items():
                for name, value in values.items():
                    setattr(neuron, name, value)
                neuron.update()

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
        self.populate_output_combo()
        self.current_result = self.calculate(source)
        self.results_by_source[id(source)] = self.current_result
        if self.tabs.currentIndex() in (2, 3, 4):
            self.ensure_specific_output()
        self.tabs.setTabText(
            0,
            self.t(
                "analysis.tab.test_data"
                if source.get("kind") == "test"
                else "analysis.tab.records"
            )
        )
        self.source_note.setText(self.source_information(source))
        self.populate_records_table()
        self.refresh_overview_tables()
        self.refresh_plot_and_tolerance()
        self.refresh_sensitivity()

    def refresh_sensitivity(self):
        if self.tabs.currentIndex() != 4:
            return
        source = self.current_source()
        mapping = self.selected_output_mapping()
        if source is None or mapping is None:
            self.sensitivity_plot.set_values([])
            return
        cache_key = (id(source), int(mapping["neuron"].id))
        if cache_key not in self.sensitivity_cache:
            self.sensitivity_cache[cache_key] = self.calculate_sensitivity(
                source, mapping
            )
        self.sensitivity_plot.set_values(self.sensitivity_cache[cache_key])

    def calculate_sensitivity(self, source, output_mapping):
        """Schätzt den mittleren lokalen Einfluss jedes Inputs per Vorwärtslauf."""
        snapshots = {
            neuron: self.neuron_runtime_snapshot(neuron)
            for neuron in self.network.get_neurons()
        }
        effects = []
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
                total_effect = 0.0
                for record in source["records"]:
                    self.network.reset_runtime_values()
                    for current in source["inputs"]:
                        raw_value = float(record[current["column_index"]])
                        current["neuron"].input_value = TrainingDataIO.scale_value(
                            raw_value, current["calibration"], translator=self.t
                        )
                    self.network.forward_pass()
                    baseline = TrainingDataIO.unscale_value(
                        output_mapping["neuron"].output_value,
                        output_mapping["calibration"],
                        translator=self.t,
                    )
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
                    changed = TrainingDataIO.unscale_value(
                        output_mapping["neuron"].output_value,
                        output_mapping["calibration"],
                        translator=self.t,
                    )
                    total_effect += abs(changed - baseline)
                effects.append((
                    input_mapping["column_name"],
                    total_effect / max(1, len(source["records"])),
                ))
        finally:
            for neuron, values in snapshots.items():
                for name, value in values.items():
                    setattr(neuron, name, value)
                neuron.update()
        total = sum(value for _name, value in effects)
        normalized = [
            (name, value / total * 100.0 if total else 0.0)
            for name, value in effects
        ]
        return sorted(normalized, key=lambda item: item[1], reverse=True)

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
            for column, value in enumerate(values):
                self.deviations_table.setItem(
                    row_index, column, self.table_item(value, column != 1)
                )

        self.apply_compact_column_widths(binary_total > 0)

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

    def rows_for_selected_output(self):
        mapping = self.selected_output_mapping()
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
        rows, mapping = self.rows_for_selected_output()
        if mapping is None:
            self.plot.set_rows([])
            self.tolerance_summary.setText(self.t("analysis.output_required"))
            self.tolerance_table.setRowCount(0)
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
        self.plot_tolerance_spin.blockSignals(True)
        self.plot_tolerance_spin.setSuffix(
            "" if binary or not mapping.get("unit") else f" {mapping['unit']}"
        )
        self.plot_tolerance_spin.setValue(float(self.tolerances[key]))
        self.plot_tolerance_spin.blockSignals(False)
        self.refresh_tolerance()

    def tolerance_key(self, mapping):
        return ("output", int(mapping["neuron"].id))

    def update_plot_tolerance(self, _checked=None):
        rows, mapping = self.rows_for_selected_output()
        if mapping is None:
            self.plot.set_tolerance(0.0, False)
            return
        binary = mapping.get("data_type") == "binary"
        tolerance = float(self.tolerances.get(self.tolerance_key(mapping), 0.0))
        self.plot.set_tolerance(
            tolerance,
            self.show_tolerance_checkbox.isChecked() and not binary,
        )

    def plot_tolerance_changed(self, value):
        rows, mapping = self.rows_for_selected_output()
        if mapping is None or mapping.get("data_type") == "binary":
            return
        self.tolerances[self.tolerance_key(mapping)] = float(value)
        self.tolerance_spin.blockSignals(True)
        self.tolerance_spin.setValue(float(value))
        self.tolerance_spin.blockSignals(False)
        self.refresh_tolerance()

    def refresh_tolerance(self, value=None):
        rows, mapping = self.rows_for_selected_output()
        if mapping is None:
            return
        binary = mapping.get("data_type") == "binary"
        key = self.tolerance_key(mapping)
        if not binary:
            self.tolerances[key] = float(self.tolerance_spin.value())
            self.plot_tolerance_spin.blockSignals(True)
            self.plot_tolerance_spin.setValue(float(self.tolerance_spin.value()))
            self.plot_tolerance_spin.blockSignals(False)
        tolerance = float(self.tolerances.get(key, 0.0))
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
        self.tolerance_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.update_plot_tolerance()

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

    def apply_compact_column_widths(self, has_binary_outputs):
        """Verhindert breite Restspalten und hält Zahlenfelder gleichmäßig."""

        shared_widths = (90, 175, 105, 145, 175)
        output_widths = shared_widths + (150, 165)
        deviation_widths = shared_widths
        for table, widths in (
            (self.output_table, output_widths),
            (self.deviations_table, deviation_widths),
        ):
            header = table.horizontalHeader()
            for column, width in enumerate(widths):
                if table.isColumnHidden(column):
                    continue
                header.setSectionResizeMode(
                    column, QHeaderView.ResizeMode.Fixed
                )
                table.setColumnWidth(column, width)

    @staticmethod
    def report_chart_image(
        points, scatter=False, tolerance=0.0, axis_label="", logarithmic=False,
        binary=False, image_width=1200, image_height=520,
    ):
        """Zeichnet eine druckfähige Fehler- oder Soll-Ist-Grafik."""
        image = QImage(
            int(image_width), int(image_height), QImage.Format.Format_ARGB32
        )
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        left, top, right, bottom = 132, 30, 82, 64
        width = image.width() - left - right
        height = image.height() - top - bottom
        painter.setPen(QPen(QColor("#c9d2dc"), 1))
        painter.drawRect(left, top, width, height)
        if not points:
            painter.setPen(QColor("#666666"))
            painter.drawText(left, top, width, height, Qt.AlignmentFlag.AlignCenter, "–")
            painter.end()
            return image

        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        if logarithmic and not scatter:
            positive = [value for value in ys if value > 0.0]
            logarithmic = bool(positive) and len(positive) == len(ys)
            if logarithmic:
                ys = [log10(value) for value in ys]
        low = min(xs + ys) if scatter else min(ys)
        high = max(xs + ys) if scatter else max(ys)
        if high <= low:
            high = low + 1.0
        padding = (high - low) * 0.06
        low -= padding
        high += padding
        x_low = low if scatter else min(xs)
        x_high = high if scatter else max(xs)
        if x_high <= x_low:
            x_high = x_low + 1.0

        def px(value):
            return left + (float(value) - x_low) / (x_high - x_low) * width

        def py(value):
            return top + height - (float(value) - low) / (high - low) * height

        tick_pen = QPen(QColor("#d4dee7"), 2)
        label_pen = QPen(QColor("#465968"), 1)
        tick_font = QFont("Segoe UI")
        tick_font.setPixelSize(22)
        painter.setFont(tick_font)
        for index in range(6):
            fraction = index / 5.0
            x_value = x_low + (x_high - x_low) * fraction
            y_value = low + (high - low) * fraction
            x_position = int(px(x_value))
            y_position = int(py(y_value))
            painter.setPen(tick_pen)
            painter.drawLine(x_position, top, x_position, top + height)
            painter.drawLine(left, y_position, left + width, y_position)
            painter.setPen(label_pen)
            painter.drawText(
                x_position - 55, top + height + 7, 110, 25,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                (f"{x_value:.0f}" if not scatter else f"{x_value:.5g}"),
            )
            painter.drawText(
                2, y_position - 12, left - 10, 24,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{(10 ** y_value if logarithmic else y_value):.5g}",
            )
        painter.setPen(QPen(QColor("#aebbc7"), 1))
        painter.drawRect(left, top, width, height)
        axis_font = QFont("Segoe UI")
        axis_font.setPixelSize(23)
        axis_font.setBold(True)
        painter.setFont(axis_font)
        painter.drawText(
            left, top + height + 29, width, 23,
            Qt.AlignmentFlag.AlignCenter, str(axis_label)
        )
        if scatter:
            painter.setPen(QPen(QColor("#6f7f8f"), 2, Qt.PenStyle.DashLine))
            painter.drawLine(int(px(low)), int(py(low)), int(px(high)), int(py(high)))
            if binary:
                painter.setPen(QPen(QColor("#8495a5"), 2, Qt.PenStyle.DashLine))
                painter.drawLine(int(px(0.5)), top, int(px(0.5)), top + height)
                painter.drawLine(left, int(py(0.5)), left + width, int(py(0.5)))
                painter.setPen(QColor("#566573"))
                labels = (
                    ("fälschlich Ein", 0.25, 0.82),
                    ("richtig Ein", 0.75, 0.82),
                    ("richtig Aus", 0.25, 0.18),
                    ("fälschlich Aus", 0.75, 0.18),
                )
                for label, x_value, y_value in labels:
                    painter.drawText(
                        int(px(x_value)) - 70, int(py(y_value)) - 10, 140, 20,
                        Qt.AlignmentFlag.AlignCenter, label,
                    )
            if tolerance > 0:
                painter.setPen(QPen(QColor("#80b894"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(px(low)), int(py(low + tolerance)), int(px(high)), int(py(high + tolerance)))
                painter.drawLine(int(px(low)), int(py(low - tolerance)), int(px(high)), int(py(high - tolerance)))
            for target, actual in points:
                outside = abs(float(target) - float(actual)) > tolerance if tolerance > 0 else False
                painter.setBrush(QColor("#d62828" if outside else "#1676b8"))
                painter.setPen(QPen(QColor("white"), 1))
                painter.drawEllipse(int(px(target)) - 4, int(py(actual)) - 4, 8, 8)
        else:
            painter.setPen(QPen(QColor("#1676b8"), 2))
            previous = None
            for epoch, error in points:
                if logarithmic:
                    error = log10(float(error))
                current = (int(px(epoch)), int(py(error)))
                if previous is not None:
                    painter.drawLine(previous[0], previous[1], current[0], current[1])
                previous = current
        painter.end()
        return image

    @staticmethod
    def image_png_bytes(image):
        """Wandelt ein QImage verlustfrei in PNG-Daten um."""
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return bytes(data)

    def report_network_image(self):
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
        image_width = 1400
        image_height = int(round(
            image_width * desired_height_inches / report_width_inches
        ))
        image = QImage(
            image_width, image_height, QImage.Format.Format_ARGB32
        )
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        padding = 38.0
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
        scene.render(
            painter,
            target,
            bounds,
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        painter.end()
        return image

    def report_default_path(self, suffix):
        """Schlägt den Exporte-Ordner des aktuellen Projekts vor."""
        name = str(self.report_context.get("project_name") or "NeuronNetz")
        report_suffix = self.t("analysis.report.file_suffix")
        export_dir = str(self.report_context.get("export_dir") or "").strip()
        if export_dir:
            directory = Path(export_dir)
            directory.mkdir(parents=True, exist_ok=True)
            return str(directory / f"{name}_{report_suffix}.{suffix}")
        return f"{name}_{report_suffix}.{suffix}"

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
        """Lässt PDF oder DOCX wählen und erzeugt den gewünschten Bericht."""

        word_filter = self.t("analysis.report.word_filter")
        pdf_filter = self.t("analysis.report.filter")
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.t("analysis.report.create_title"),
            self.report_default_path("docx"),
            f"{word_filter};;{pdf_filter}",
            word_filter,
        )
        if not file_path:
            return False

        pdf_selected = selected_filter == pdf_filter
        desired_suffix = ".pdf" if pdf_selected else ".docx"
        selected_path = Path(file_path)
        if selected_path.suffix.lower() in {".pdf", ".docx"}:
            selected_path = selected_path.with_suffix(desired_suffix)
        elif selected_path.suffix.lower() != desired_suffix:
            selected_path = Path(f"{selected_path}{desired_suffix}")

        if pdf_selected:
            return self.export_pdf_report(str(selected_path))
        return self.export_word_report(str(selected_path))

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

    def export_pdf_report(self, file_path=None):
        """Erstellt einen kompakten PDF-Bericht des aktiven Trainingsstands."""
        source = self.current_source()
        if not source:
            return
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

        result = self.current_result or self.calculate(source)
        run = self.report_context.get("training_run") or {}
        context = self.report_context
        training_history = [
            entry for entry in context.get("training_history", [])
            if isinstance(entry, dict)
        ]
        active_run_id = context.get("active_training_run_id", run.get("run_id"))
        document = QTextDocument()
        resources = []
        html = [
            "<style>body{font-family:sans-serif;font-size:10pt;color:#18212b;}"
            "h1{color:#17375e;}h2{color:#17375e;border-bottom:1px solid #9fb3c8;page-break-after:avoid;}"
            ".section{page-break-before:always;}"
            "table{border-collapse:collapse;width:100%;margin:6px 0 14px 0;page-break-inside:auto;}"
            "th{background:#17375e;color:white;}td,th{border:1px solid #b7c1cc;padding:5px 5px 5px 7px;vertical-align:middle;}"
            "tr{page-break-inside:avoid;}thead{display:table-header-group;}"
            "img{display:block;width:100%;margin:8px 0 0 0;}"
            ".network-frame{border:1px solid #000;padding:6px;text-align:center;}"
            ".chart-frame{border:1px solid #000;padding:3px;text-align:center;}"
            ".network-frame img{margin:auto;max-width:98%;}"
            ".chart-frame img{margin:auto;max-width:99%;}"
            ".note{background:#eef4f8;border:1px solid #b9cbd8;padding:7px;}</style>",
            f"<h1>{escape(self.t('analysis.report.heading'))}</h1><table>",
            f"<tr><td>{escape(self.t('analysis.report.project').rstrip(':'))}</td><td>{escape(str(context.get('project_name') or '–'))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.created'))}</td><td>{escape(self.report_datetime(datetime.now(), include_seconds=False))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.active_run'))}</td><td>{escape(self.t('analysis.report.run', run=run.get('run_id', '–')))}</td></tr></table>",
        ]
        description = str(context.get("project_description") or "").strip()
        if description:
            html.extend([
                f"<h2>{escape(self.t('project_description.title'))}</h2>",
                f"<div>{description}</div>",
            ])
        network_image = self.report_network_image()
        html.extend([
            f"<div class='section'><h2>{escape(self.t('analysis.report.network'))}</h2>",
            "<table>",
            f"<tr><td>{escape(self.t('project_overview.structure'))}</td><td>{escape(str(context.get('structure','–')))}</td></tr>",
            f"<tr><td>{escape(self.t('project_overview.neurons'))}</td><td>{int(context.get('neurons',0))}</td></tr>",
            f"<tr><td>{escape(self.t('project_overview.connections'))}</td><td>{int(context.get('connections',0))}</td></tr>",
            "</table>",
        ])
        if network_image is not None:
            network_url = QUrl("report:network")
            document.addResource(
                QTextDocument.ResourceType.ImageResource,
                network_url,
                network_image,
            )
            resources.append(network_image)
            html.append('<div class="network-frame"><img src="report:network" width="680" /></div>')
        html.extend([
            "</div>",
            f"<div class='section'><h2 style='text-align:center'>{escape(self.t('analysis.report.training'))}</h2>",
        ])
        if training_history:
            html.extend([
                f"<h3 style='text-align:center'>{escape(self.t('analysis.report.training_runs'))}</h3>",
                "<table><thead><tr>",
                f"<th>{escape(self.t('history.column.run'))}</th>",
                f"<th>{escape(self.t('history.column.time'))}</th>",
                f"<th>{escape(self.t('history.column.learning_rate'))}</th>",
                f"<th>{escape(self.t('history.column.momentum'))}</th>",
                f"<th>{escape(self.t('history.column.epochs'))}</th>",
                f"<th>{escape(self.t('history.column.end_error'))}</th>",
                f"<th>{escape(self.t('history.column.maximum_error'))}</th>",
                f"<th>{escape(self.t('history.column.duration'))}</th>",
                "</tr></thead><tbody>",
            ])
            for entry in reversed(training_history):
                run_number = str(entry.get("run_id", "–"))
                if entry.get("run_id") == active_run_id:
                    run_number += f" – {self.t('history.active')}"
                html.extend([
                    "<tr>",
                    f"<td>{escape(run_number)}</td>",
                    f"<td>{escape(self.report_datetime(entry.get('timestamp')))}</td>",
                    f"<td>{self.report_decimal(entry.get('learning_rate'), 6)}</td>",
                    f"<td>{self.report_decimal(entry.get('momentum', 0.0), 2)}</td>",
                    f"<td>{self.report_integer(entry.get('completed_epochs'))}</td>",
                    f"<td>{self.report_decimal(entry.get('end_error'), 6)}</td>",
                    f"<td>{self.report_decimal(entry.get('maximum_absolute_error'), 6)}</td>",
                    f"<td>{self.report_decimal(entry.get('elapsed_seconds'), 1)} s</td>",
                    "</tr>",
                ])
            html.extend(["</tbody></table>"])
        html.extend([
            "<div style='page-break-inside:avoid'>",
            f"<h3 style='text-align:center'>{escape(self.t('analysis.report.active_run_details'))}</h3>",
            "<table>",
            f"<tr><td>{escape(self.t('analysis.source.label'))}</td><td>{escape(str(source.get('label') or '–'))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.data_file'))}</td><td>{escape(str(source.get('file_path') or '–'))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.date'))}</td><td>{escape(self.report_datetime(run.get('timestamp')))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.epochs'))}</td><td>{self.report_integer(run.get('completed_epochs'))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.duration'))}</td><td>{self.report_decimal(run.get('elapsed_seconds'), 1)} s</td></tr>",
            f"<tr><td>{escape(self.t('training.parameters.learning_rate'))}</td><td>{self.report_decimal(run.get('learning_rate'), 6)}</td></tr>",
            f"<tr><td>{escape(self.t('training.parameters.momentum'))}</td><td>{self.report_decimal(run.get('momentum', 0.0), 2)}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.error_limit'))}</td><td>{self.report_decimal(run.get('error_limit'), 6)}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.requested_epochs'))}</td><td>{self.report_integer(run.get('requested_epochs'))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.initialization'))}</td><td>{escape(str(run.get('weight_initialization','–')))} / {escape(str(run.get('bias_initialization','–')))}</td></tr>",
            f"<tr><td>{escape(self.t('analysis.report.mode'))}</td><td>{escape(self.t('analysis.report.fast_mode' if run.get('fast_mode') else 'analysis.report.normal_mode'))}</td></tr>",
            f"<tr><td>{escape(self.t('project_overview.mean_error'))}</td><td>{self.report_decimal(run.get('end_error'), 6)}</td></tr>",
            "</table></div>",
        ])
        curve = run.get("curve_points", []) if isinstance(run, dict) else []
        if curve:
            logarithmic = self.report_curve_is_logarithmic(curve)
            scale_text = self.t(
                "analysis.report.scale_logarithmic" if logarithmic
                else "analysis.report.scale_linear"
            )
            image = self.report_chart_image(
                curve,
                axis_label=self.t("history.chart.epoch"),
                logarithmic=logarithmic,
            )
            url = QUrl("report:error_curve")
            document.addResource(QTextDocument.ResourceType.ImageResource, url, image)
            resources.append(image)
            html.extend([
                "<div style='page-break-inside:avoid'>",
                f"<h2 style='text-align:center'>{escape(self.t('analysis.report.active_curve'))}</h2>",
                f"<p style='text-align:center'>{escape(self.t('analysis.report.run', run=run.get('run_id', '–')))} · {escape(self.report_datetime(run.get('timestamp')))} · "
                f"{escape(self.t('analysis.report.epoch_count', epochs=self.report_integer(run.get('completed_epochs'))))} · {scale_text}</p>",
                '<div class="chart-frame"><img src="report:error_curve" width="660" /></div>',
                "</div>",
            ])
        html.append("</div>")

        html.append(
            f"<div class='section'><h2 style='text-align:center'>{escape(self.t('analysis.report.output_results'))}</h2>"
        )
        for index, mapping in enumerate(source["outputs"]):
            rows = [row for row in result["rows"] if row["neuron_id"] == mapping["neuron"].id]
            key = self.tolerance_key(mapping)
            if key not in self.tolerances:
                raw_values = [row["target"] for row in rows]
                raw_range = max(raw_values) - min(raw_values) if raw_values else 0.0
                self.tolerances[key] = (
                    0.0
                    if mapping.get("data_type") == "binary"
                    else 5.0
                    if mapping.get("unit") == "%"
                    else max(raw_range * 0.05, 0.0)
                )
            tolerance = float(self.tolerances[key])
            outside = sum(row["raw_absolute"] > tolerance for row in rows)
            if index and index % 3 == 0:
                html.append("</div><div class='section'>")
            html.append(
                f"<h3 style='text-align:center'>{escape(self.report_output_title(mapping))}</h3>"
            )
            if mapping.get("data_type") == "binary":
                correct = sum(not row["binary_error"] for row in rows)
                summary = self.t(
                    "analysis.tolerance.binary_summary",
                    correct=correct,
                    total=len(rows),
                    incorrect=len(rows) - correct,
                )
            else:
                summary = self.t(
                    "analysis.report.tolerance_result",
                    inside=len(rows) - outside,
                    total=len(rows),
                    tolerance=self.display_number(tolerance),
                    unit=str(mapping.get("unit") or ""),
                )
            html.append(f"<p style='text-align:center'>{escape(summary)}</p>")
            image = self.report_chart_image(
                [(row["target"], row["actual"]) for row in rows],
                scatter=True,
                tolerance=tolerance,
                axis_label=self.t("analysis.plot.target_axis"),
                binary=mapping.get("data_type") == "binary",
                image_width=1400,
                image_height=450,
            )
            url = QUrl(f"report:scatter_{index}")
            document.addResource(QTextDocument.ResourceType.ImageResource, url, image)
            resources.append(image)
            html.append(
                f'<div class="chart-frame"><img src="report:scatter_{index}" width="660" /></div>'
            )

        html.extend([
            "</div>",
            f"<div class='section'><h2>{escape(self.t('analysis.deviations.group'))}</h2>",
            "<table><thead><tr>",
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
        html.append("</tbody></table>")
        if any(str(row.get("unit") or "").strip() == "%" for row in result["rows"][:20]):
            html.append(f"<p>{escape(self.t('analysis.report.percentage_note'))}</p>")
        html.append("</div>")
        document.setHtml("".join(html))
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageMargins(
            QMarginsF(14.0, 14.0, 14.0, 14.0),
            QPageLayout.Unit.Millimeter,
        )
        document.setPageSize(
            printer.pageLayout().paintRect(QPageLayout.Unit.Point).size()
        )
        try:
            document.print_(printer)
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self, self.t("analysis.report.error_title"), str(error))
            return False
        self.offer_open_report(file_path)
        return True

    def export_word_report(self, file_path=None):
        """Erstellt einen bearbeitbaren Word-Bericht im DOCX-Format."""
        source = self.current_source()
        if not source:
            return
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

        result = self.current_result or self.calculate(source)
        run = self.report_context.get("training_run") or {}
        context = self.report_context
        training_history = [
            entry for entry in context.get("training_history", [])
            if isinstance(entry, dict)
        ]
        active_run_id = context.get("active_training_run_id", run.get("run_id"))
        report_title = self.t("analysis.report.heading")
        report = DocxReport(report_title)
        report.heading(report_title, 1)
        report.table([
            [self.t("analysis.report.project").rstrip(":"), context.get("project_name") or "–"],
            [self.t("analysis.report.created"), self.report_datetime(datetime.now(), include_seconds=False)],
            [self.t("analysis.report.active_run"), self.t("analysis.report.run", run=run.get("run_id", "–"))],
        ], widths=[2, 5], keep_together=True)
        description = str(context.get("project_description") or "").strip()
        if description:
            report.heading(self.t("project_description.title"), 2)
            report.formatted_html(description)

        report.page_break()
        report.heading(self.t("analysis.report.network"), 1)
        report.table([
            [self.t("project_overview.structure"), context.get("structure", "–")],
            [self.t("project_overview.neurons"), context.get("neurons", 0)],
            [self.t("project_overview.connections"), context.get("connections", 0)],
        ], widths=[2, 5])
        network_image = self.report_network_image()
        if network_image is not None:
            report.image(
                self.image_png_bytes(network_image),
                network_image.width(),
                network_image.height(),
                width_inches=6.75,
                framed=True,
                frame_padding_twips=70,
            )

        report.page_break()
        report.heading(self.t("analysis.report.training"), 1, centered=True)
        if training_history:
            report.heading(
                self.t("analysis.report.training_runs"), 2, centered=True
            )
            history_rows = [[
                self.t("history.column.run"),
                self.t("history.column.time"),
                self.t("history.column.learning_rate"),
                self.t("history.column.momentum"),
                self.t("history.column.epochs"),
                self.t("history.column.end_error"),
                self.t("history.column.maximum_error"),
                self.t("history.column.duration"),
            ]]
            for entry in reversed(training_history):
                run_number = str(entry.get("run_id", "–"))
                if entry.get("run_id") == active_run_id:
                    run_number += f" – {self.t('history.active')}"
                history_rows.append([
                    run_number,
                    self.report_datetime(entry.get("timestamp")),
                    self.report_decimal(entry.get("learning_rate"), 6),
                    self.report_decimal(entry.get("momentum", 0.0), 2),
                    self.report_integer(entry.get("completed_epochs")),
                    self.report_decimal(entry.get("end_error"), 6),
                    self.report_decimal(entry.get("maximum_absolute_error"), 6),
                    f"{self.report_decimal(entry.get('elapsed_seconds'), 1)} s",
                ])
            report.table(
                history_rows,
                widths=[0.7, 1.5, 0.9, 0.8, 0.8, 0.9, 1.0, 0.8],
                header=True,
            )
            report.spacer(8)
        report.heading(
            self.t("analysis.report.active_run_details"), 2, centered=True
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
             f"{run.get('weight_initialization', '–')} / {run.get('bias_initialization', '–')}"],
            [self.t("analysis.report.mode"),
             self.t("analysis.report.fast_mode" if run.get("fast_mode") else "analysis.report.normal_mode")],
            [self.t("project_overview.mean_error"), self.report_decimal(run.get("end_error"), 6)],
        ], widths=[2, 5], keep_together=True)
        report.spacer(10)

        curve = run.get("curve_points", []) if isinstance(run, dict) else []
        if curve:
            logarithmic = self.report_curve_is_logarithmic(curve)
            scale_text = self.t(
                "analysis.report.scale_logarithmic" if logarithmic
                else "analysis.report.scale_linear"
            )
            report.heading(self.t("analysis.report.active_curve"), 2, centered=True)
            report.paragraph(
                f"{self.t('analysis.report.run', run=run.get('run_id', '–'))} · "
                f"{self.report_datetime(run.get('timestamp'))} · "
                f"{self.t('analysis.report.epoch_count', epochs=self.report_integer(run.get('completed_epochs')))} · {scale_text}",
                centered=True,
                keep_next=True,
            )
            curve_image = self.report_chart_image(
                curve,
                axis_label=self.t("history.chart.epoch"),
                logarithmic=logarithmic,
            )
            report.image(
                self.image_png_bytes(curve_image),
                curve_image.width(),
                curve_image.height(),
                width_inches=6.75,
                framed=True,
                frame_padding_twips=60,
            )

        for output_index, mapping in enumerate(source["outputs"]):
            rows = [
                row for row in result["rows"]
                if row["neuron_id"] == mapping["neuron"].id
            ]
            key = self.tolerance_key(mapping)
            if key not in self.tolerances:
                raw_values = [row["target"] for row in rows]
                raw_range = max(raw_values) - min(raw_values) if raw_values else 0.0
                self.tolerances[key] = (
                    0.0
                    if mapping.get("data_type") == "binary"
                    else 5.0
                    if mapping.get("unit") == "%"
                    else max(raw_range * 0.05, 0.0)
                )
            tolerance = float(self.tolerances.get(key, 0.0))
            outside = sum(row["raw_absolute"] > tolerance for row in rows)
            if output_index % 3 == 0:
                report.page_break()
                report.heading(
                    self.t("analysis.report.output_results"), 1, centered=True
                )
            report.heading(self.report_output_title(mapping), 2, centered=True)
            if not rows:
                report.paragraph(self.t("analysis.report.no_output_data"))
                continue
            if mapping.get("data_type") == "binary":
                correct = sum(not row["binary_error"] for row in rows)
                summary = self.t(
                    "analysis.tolerance.binary_summary",
                    correct=correct,
                    total=len(rows),
                    incorrect=len(rows) - correct,
                )
            else:
                summary = self.t(
                    "analysis.report.tolerance_result",
                    inside=len(rows) - outside,
                    total=len(rows),
                    tolerance=self.display_number(tolerance),
                    unit=str(mapping.get("unit") or ""),
                )
            report.paragraph(summary, centered=True, keep_next=True)
            chart = self.report_chart_image(
                [(row["target"], row["actual"]) for row in rows],
                scatter=True,
                tolerance=tolerance,
                axis_label=self.t("analysis.plot.target_axis"),
                binary=mapping.get("data_type") == "binary",
                image_width=1400,
                image_height=450,
            )
            report.image(
                self.image_png_bytes(chart),
                chart.width(),
                chart.height(),
                width_inches=6.75,
                framed=True,
                frame_padding_twips=60,
            )

        report.page_break()
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
        try:
            report.save(file_path)
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(self, self.t("analysis.report.error_title"), str(error))
            return False
        self.offer_open_report(file_path)
        return True

    @staticmethod
    def table_item(value, numeric=False):
        item = QTableWidgetItem(str(value))
        if numeric:
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        return item
