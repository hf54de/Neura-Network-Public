# -------------------------------------------------------------------------------------------------
# Datei: trainingdatadialog.py
# Zweck: Erfasst, importiert, prüft und skaliert Trainings- und Testdaten.
# Letzte Änderung: 06.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import csv
import io
import math
import os
import random

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QDoubleValidator,
    QFont,
    QFontDatabase,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout
)

from neurontype import NeuronType
from numberformat import format_number
from language import LanguageManager
from trainingdataio import TrainingDataIO
from binaryarraydialog import BinaryInputArrayDialog


class NumericItemDelegate(QStyledItemDelegate):
    """Lässt in Trainingsdatenzellen ausschließlich Zahlen zu."""

    def __init__(self, number_parser, parent=None):
        super().__init__(parent)
        self.number_parser = number_parser

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight)
        validator = QDoubleValidator(editor)
        validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        validator.setDecimals(15)
        editor.setValidator(validator)
        return editor

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        try:
            self.number_parser(text)
        except ValueError:
            return
        model.setData(index, text, Qt.ItemDataRole.EditRole)


class ColumnPropertiesDialog(QDialog):
    """
    Bearbeitet Name, Typ und Neuronenzuordnung
    einer einzelnen Trainingsdatenspalte.
    """

    def __init__(
        self,
        column_data,
        network,
        column_values=None,
        language_manager=None,
        parent=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        text = self.language.text
        self.network = network
        self.column_data_original = copy.deepcopy(
            column_data
        )
        original_calibration = TrainingDataIO.normalize_calibration(
            self.column_data_original.get("calibration")
        )
        self.remembered_analog_calibration = TrainingDataIO.normalize_calibration(
            self.column_data_original.get(
                "analog_calibration",
                original_calibration,
            )
        )
        self.previous_data_type = self.column_data_original.get(
            "data_type",
            "analog",
        )
        self.column_data = copy.deepcopy(
            column_data
        )
        self.column_values = list(
            column_values or []
        )

        self.setWindowTitle(
            text("data.column_properties.title")
        )

        self.resize(
            520,
            500
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.form_layout = QFormLayout()

        self.name_edit = QLineEdit(
            self.column_data["name"]
        )
        self.unit_edit = QLineEdit(
            str(self.column_data.get("unit", ""))
        )
        role = self.column_data.get("role", "input")
        self.role_display = QLineEdit(
            text("data.role.input" if role == "input" else "data.role.output")
        )
        self.role_display.setReadOnly(True)

        self.data_type_combo = QComboBox()
        self.data_type_combo.addItem(
            text("data.type.analog"), "analog"
        )
        self.data_type_combo.addItem(
            text("data.type.binary"), "binary"
        )
        self.data_type_combo.setCurrentIndex(
            max(0, self.data_type_combo.findData(
                self.column_data.get("data_type", "analog")
            ))
        )

        neuron_id = self.column_data.get("mapped_neuron_id")
        mapped_neuron = self.network.get_neuron(neuron_id)
        neuron_name = (
            mapped_neuron.name
            if mapped_neuron is not None
            else self.column_data.get("mapped_neuron_name") or "–"
        )
        neuron_text = (
            f"{neuron_name} (ID {neuron_id})"
            if neuron_id is not None
            else "–"
        )
        self.neuron_display = QLineEdit(neuron_text)
        self.neuron_display.setReadOnly(True)

        self.form_layout.addRow(
            text("data.column_properties.name"),
            self.name_edit
        )
        self.form_layout.addRow(
            text("data.column_properties.unit"),
            self.unit_edit
        )
        self.form_layout.addRow(
            text("data.column_properties.type"),
            self.role_display
        )
        self.form_layout.addRow(
            text("data.column_properties.data_type"),
            self.data_type_combo
        )
        self.form_layout.addRow(
            text("data.column_properties.neuron"),
            self.neuron_display
        )

        self.main_layout.addLayout(
            self.form_layout
        )

        self.calibration_group = QGroupBox(
            text("data.calibration.group")
        )
        self.calibration_layout = QGridLayout(
            self.calibration_group
        )

        self.calibration_combo = QComboBox()
        self.calibration_combo.addItem(
            text("data.calibration.none"),
            "none"
        )
        self.calibration_combo.addItem(
            text("data.calibration.minmax_0_1"),
            "minmax_0_1"
        )
        self.calibration_combo.addItem(
            text("data.calibration.minmax_minus1_1"),
            "minmax_minus1_1"
        )
        self.calibration_combo.addItem(
            text("data.calibration.standard"),
            "standard"
        )
        calibration_tooltips = {
            "none": text("data.calibration.method_tooltip.none"),
            "minmax_0_1": text("data.calibration.method_tooltip.minmax_0_1"),
            "minmax_minus1_1": text("data.calibration.method_tooltip.minmax_minus1_1"),
            "standard": text("data.calibration.method_tooltip.standard"),
        }
        for index in range(self.calibration_combo.count()):
            mode = self.calibration_combo.itemData(index)
            self.calibration_combo.setItemData(
                index,
                calibration_tooltips.get(mode, ""),
                Qt.ItemDataRole.ToolTipRole,
            )

        calibration = TrainingDataIO.normalize_calibration(
            self.column_data.get("calibration")
        )
        calibration_index = self.calibration_combo.findData(
            calibration["mode"]
        )
        self.calibration_combo.setCurrentIndex(
            max(0, calibration_index)
        )

        self.source_min_spin = self.create_number_spinbox(
            calibration["source_min"]
        )
        self.source_max_spin = self.create_number_spinbox(
            calibration["source_max"]
        )
        self.mean_spin = self.create_number_spinbox(
            calibration["mean"]
        )
        self.stddev_spin = self.create_number_spinbox(
            calibration["stddev"],
            minimum=0.00000001
        )

        self.auto_values_button = QPushButton(
            text("data.calibration.from_table")
        )
        self.preview_value_spin = self.create_number_spinbox(
            calibration["mean"]
        )
        self.preview_result_label = QLabel()

        self.calibration_layout.addWidget(
            QLabel(text("data.calibration.method")), 0, 0
        )
        self.calibration_layout.addWidget(
            self.calibration_combo, 0, 1, 1, 2
        )
        self.calibration_layout.addWidget(
            QLabel(text("data.calibration.source_min")), 1, 0
        )
        self.calibration_layout.addWidget(
            self.source_min_spin, 1, 1
        )
        self.calibration_layout.addWidget(
            QLabel(text("data.calibration.source_max")), 2, 0
        )
        self.calibration_layout.addWidget(
            self.source_max_spin, 2, 1
        )
        self.calibration_layout.addWidget(
            QLabel(text("data.calibration.mean")), 3, 0
        )
        self.calibration_layout.addWidget(
            self.mean_spin, 3, 1
        )
        self.calibration_layout.addWidget(
            QLabel(text("data.calibration.stddev")), 4, 0
        )
        self.calibration_layout.addWidget(
            self.stddev_spin, 4, 1
        )
        self.calibration_layout.addWidget(
            self.auto_values_button, 1, 2, 4, 1
        )
        self.calibration_layout.addWidget(
            QLabel(text("data.calibration.preview_raw")), 5, 0
        )
        self.calibration_layout.addWidget(
            self.preview_value_spin, 5, 1
        )
        self.calibration_layout.addWidget(
            self.preview_result_label, 5, 2
        )

        self.calibration_note_label = QLabel(
            text("data.calibration.note")
        )
        self.calibration_note_label.setWordWrap(True)
        self.calibration_layout.addWidget(
            self.calibration_note_label, 6, 0, 1, 3
        )

        self.main_layout.addWidget(
            self.calibration_group
        )

        self.hint_label = QLabel(
            text("data.column_properties.mapping_hint")
        )
        self.hint_label.setWordWrap(
            True
        )

        self.main_layout.addWidget(
            self.hint_label
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText(text("common.ok"))
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(text("common.cancel"))
        self.button_box.accepted.connect(
            self.accept
        )
        self.button_box.rejected.connect(
            self.reject
        )

        self.main_layout.addWidget(
            self.button_box
        )

        self.calibration_combo.currentIndexChanged.connect(
            self.update_calibration_controls
        )
        self.data_type_combo.currentIndexChanged.connect(
            self.update_data_type_controls
        )
        self.auto_values_button.clicked.connect(
            self.calculate_automatic_values
        )

        for spin_box in (
            self.source_min_spin,
            self.source_max_spin,
            self.mean_spin,
            self.stddev_spin,
            self.preview_value_spin
        ):
            spin_box.valueChanged.connect(
                self.update_calibration_preview
            )

        self.update_data_type_controls()

    @staticmethod
    def create_number_spinbox(value, minimum=-1.0e12):
        spin_box = QDoubleSpinBox()
        spin_box.setRange(
            minimum,
            1.0e12
        )
        spin_box.setDecimals(8)
        spin_box.setValue(float(value))
        spin_box.setKeyboardTracking(False)
        return spin_box

    def update_calibration_controls(self):
        if self.data_type_combo.currentData() == "binary":
            self.calibration_group.setEnabled(False)
            return
        self.calibration_group.setEnabled(True)
        mode = self.calibration_combo.currentData()
        minmax_enabled = mode in (
            "minmax_0_1",
            "minmax_minus1_1"
        )
        standard_enabled = mode == "standard"

        self.source_min_spin.setEnabled(
            minmax_enabled
        )
        self.source_max_spin.setEnabled(
            minmax_enabled
        )
        self.mean_spin.setEnabled(
            standard_enabled
        )
        self.stddev_spin.setEnabled(
            standard_enabled
        )
        self.auto_values_button.setEnabled(
            any(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in self.column_values
            )
        )
        self.update_calibration_preview()

    def update_data_type_controls(self, *_):
        binary = self.data_type_combo.currentData() == "binary"
        if binary and self.previous_data_type != "binary":
            self.remembered_analog_calibration = {
                "mode": self.calibration_combo.currentData(),
                "source_min": self.source_min_spin.value(),
                "source_max": self.source_max_spin.value(),
                "mean": self.mean_spin.value(),
                "stddev": self.stddev_spin.value(),
            }
            self.calibration_combo.setCurrentIndex(
                self.calibration_combo.findData("none")
            )
        elif not binary and self.previous_data_type == "binary":
            calibration = self.remembered_analog_calibration
            self.calibration_combo.setCurrentIndex(max(
                0,
                self.calibration_combo.findData(calibration["mode"]),
            ))
            self.source_min_spin.setValue(calibration["source_min"])
            self.source_max_spin.setValue(calibration["source_max"])
            self.mean_spin.setValue(calibration["mean"])
            self.stddev_spin.setValue(calibration["stddev"])
        self.previous_data_type = "binary" if binary else "analog"
        self.calibration_group.setEnabled(not binary)
        self.update_calibration_controls()

    def calculate_automatic_values(self):
        values = [
            float(value)
            for value in self.column_values
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            )
        ]

        if not values:
            QMessageBox.information(
                self,
                self.language.text("data.message.no_table_values.title"),
                self.language.text("data.message.no_table_values.message")
            )
            return

        source_min = min(values)
        source_max = max(values)
        mean = sum(values) / len(values)
        variance = sum(
            (value - mean) ** 2
            for value in values
        ) / len(values)

        self.source_min_spin.setValue(source_min)
        self.source_max_spin.setValue(source_max)
        self.mean_spin.setValue(mean)
        self.stddev_spin.setValue(
            math.sqrt(variance)
        )
        self.preview_value_spin.setValue(mean)
        self.update_calibration_preview()

    def update_calibration_preview(self):
        mode = self.calibration_combo.currentData()
        value = self.preview_value_spin.value()

        if mode == "none":
            result = value
        elif mode in (
            "minmax_0_1",
            "minmax_minus1_1"
        ):
            source_min = self.source_min_spin.value()
            source_max = self.source_max_spin.value()
            difference = source_max - source_min

            if difference <= 0:
                self.preview_result_label.setText(
                    self.language.text("data.calibration.preview_invalid_range")
                )
                return

            result = (value - source_min) / difference

            if mode == "minmax_minus1_1":
                result = result * 2.0 - 1.0
        else:
            stddev = self.stddev_spin.value()

            if stddev <= 0:
                self.preview_result_label.setText(
                    self.language.text("data.calibration.preview_invalid_stddev")
                )
                return

            result = (
                value - self.mean_spin.value()
            ) / stddev

        self.preview_result_label.setText(
            self.language.text(
                "data.calibration.preview_network_value",
                value=format_number(result)
            )
        )

    def accept(self):
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                self.language.text("data.message.invalid_column_name.title"),
                self.language.text("data.message.invalid_column_name.message")
            )
            return

        role = self.column_data_original.get("role", "input")
        data_type = self.data_type_combo.currentData()
        neuron_id = self.column_data_original.get("mapped_neuron_id")
        neuron_name = None

        if neuron_id is not None:
            neuron = self.network.get_neuron(
                neuron_id
            )

            if neuron is not None:
                duplicate = next(
                    (
                        candidate
                        for candidate in self.network.get_neurons()
                        if candidate.id != neuron.id
                        and str(candidate.name).strip().casefold()
                        == name.casefold()
                    ),
                    None,
                )
                if duplicate is not None:
                    QMessageBox.warning(
                        self,
                        self.language.text("data.name.duplicate.title"),
                        self.language.text(
                            "data.name.duplicate.message",
                            name=name,
                        ),
                    )
                    return
                neuron_name = name

        if data_type == "binary":
            invalid_values = [
                value for value in self.column_values
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and float(value) not in (0.0, 1.0)
                )
            ]
            if invalid_values:
                QMessageBox.warning(
                    self,
                    self.language.text("data.binary.invalid_values.title"),
                    self.language.text("data.binary.invalid_values.message")
                )
                return

        mode = (
            "none" if data_type == "binary"
            else self.calibration_combo.currentData()
        )

        if (
            mode in ("minmax_0_1", "minmax_minus1_1")
            and self.source_min_spin.value()
            >= self.source_max_spin.value()
        ):
            QMessageBox.warning(
                self,
                self.language.text("data.message.invalid_raw_range.title"),
                self.language.text("data.message.invalid_raw_range.message")
            )
            return

        calibration = {
            "mode": mode,
            "source_min": self.source_min_spin.value(),
            "source_max": self.source_max_spin.value(),
            "mean": self.mean_spin.value(),
            "stddev": self.stddev_spin.value()
        }

        self.column_data = {
            "name": name,
            "unit": self.unit_edit.text().strip(),
            "role": role,
            "data_type": data_type,
            "mapped_neuron_id": neuron_id,
            "mapped_neuron_name": neuron_name,
            "calibration": calibration
        }

        if data_type == "binary":
            self.column_data["analog_calibration"] = copy.deepcopy(
                self.remembered_analog_calibration
            )

        if self.column_data_original.get(
            "calibration_source"
        ) == "training_data":
            self.column_data["calibration_source"] = "training_data"
            self.column_data["training_calibration"] = copy.deepcopy(
                self.column_data_original.get(
                    "training_calibration",
                    self.column_data_original.get("calibration")
                )
            )

        super().accept()


class ColumnOverviewDialog(QDialog):
    """Bearbeitet die Kopfdaten aller Trainingsdatenspalten gemeinsam."""

    def __init__(
        self,
        columns,
        network,
        records,
        initial_row=0,
        language_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.network = network
        self.records = list(records or [])
        self.columns = copy.deepcopy(columns)
        self.data_type_combos = []

        self.setWindowTitle(
            self.language.text("data.column_overview.title")
        )
        self.setMinimumWidth(780)
        self.resize(780, 500)
        layout = QVBoxLayout(self)

        info = QLabel(
            self.language.text("data.column_overview.introduction")
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(len(self.columns), 4)
        self.table.setHorizontalHeaderLabels([
            self.language.text("data.column_overview.assignment"),
            self.language.text("data.column_overview.name"),
            self.language.text("data.column_overview.unit"),
            self.language.text("data.column_overview.data_type"),
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, column in enumerate(self.columns):
            role_text = self.language.text(
                "data.role.input"
                if column.get("role", "input") == "input"
                else "data.role.output"
            )
            neuron_id = column.get("mapped_neuron_id")
            assignment_item = QTableWidgetItem(
                self.language.text(
                    "data.column_overview.assignment_value",
                    column=row + 1,
                    neuron=(f"N{neuron_id}" if neuron_id is not None else "–"),
                    role=role_text,
                )
            )
            assignment_item.setFlags(
                assignment_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.table.setItem(row, 0, assignment_item)
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(str(column.get("name", ""))),
            )
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(str(column.get("unit", ""))),
            )

            data_type_combo = QComboBox()
            data_type_combo.addItem(
                self.language.text("data.type.analog"),
                "analog",
            )
            data_type_combo.addItem(
                self.language.text("data.type.binary"),
                "binary",
            )
            data_type_combo.setCurrentIndex(max(
                0,
                data_type_combo.findData(
                    column.get("data_type", "analog")
                ),
            ))
            self.table.setCellWidget(row, 3, data_type_combo)
            self.data_type_combos.append(data_type_combo)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, max(235, self.table.columnWidth(0)))
        self.table.setColumnWidth(1, max(220, self.table.columnWidth(1)))
        self.table.setColumnWidth(2, max(110, self.table.columnWidth(2)))
        self.table.setColumnWidth(3, max(150, self.table.columnWidth(3)))
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.columns:
            initial_row = max(0, min(int(initial_row), len(self.columns) - 1))
            self.table.selectRow(initial_row)
            self.table.scrollToItem(self.table.item(initial_row, 1))

    def column_values(self, column_index):
        values = []
        for record in self.records:
            if not isinstance(record, list) or column_index >= len(record):
                continue
            value = record[column_index]
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            ):
                values.append(float(value))
        return values

    def accept(self):
        updated_columns = []
        for row, old_column in enumerate(self.columns):
            name_item = self.table.item(row, 1)
            unit_item = self.table.item(row, 2)
            name = name_item.text().strip() if name_item is not None else ""
            unit = unit_item.text().strip() if unit_item is not None else ""
            if not name:
                QMessageBox.warning(
                    self,
                    self.language.text("data.message.invalid_column_name.title"),
                    self.language.text("data.message.invalid_column_name.message"),
                )
                self.table.selectRow(row)
                return

            data_type = self.data_type_combos[row].currentData()

            if data_type == "binary" and any(
                value not in (0.0, 1.0)
                for value in self.column_values(row)
            ):
                QMessageBox.warning(
                    self,
                    self.language.text("data.binary.invalid_values.title"),
                    self.language.text("data.binary.invalid_values.message"),
                )
                self.table.selectRow(row)
                return

            column = copy.deepcopy(old_column)
            old_data_type = column.get("data_type", "analog")
            if old_data_type != data_type:
                if data_type == "binary":
                    column["analog_calibration"] = (
                        TrainingDataIO.normalize_calibration(
                            column.get("calibration")
                        )
                    )
                    column["calibration"] = TrainingDataIO.default_calibration()
                else:
                    column["calibration"] = (
                        TrainingDataIO.normalize_calibration(
                            column.get(
                                "analog_calibration",
                                column.get("calibration"),
                            )
                        )
                    )
                    column.pop("analog_calibration", None)

            column.update({
                "name": name,
                "unit": unit,
                "data_type": data_type,
            })
            neuron = self.network.get_neuron(
                column.get("mapped_neuron_id")
            )
            if neuron is not None:
                column["mapped_neuron_name"] = name
            updated_columns.append(column)

        self.columns = updated_columns
        super().accept()


class TestDataSplitDialog(QDialog):
    """Wählt reproduzierbar vorhandene Trainingszeilen zum Kopieren aus."""

    def __init__(
        self,
        training_document,
        training_file_path=None,
        language_manager=None,
        parent=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        text = self.language.text
        self.training_document = copy.deepcopy(training_document)
        self.records = self.training_document.get("records", [])
        self.columns = self.training_document.get("columns", [])
        self.selected_indices = []

        self.setWindowTitle(text("data.split.title"))
        self.resize(820, 520)

        layout = QVBoxLayout(self)
        introduction = QLabel(
            text("data.split.introduction")
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        source_text = (
            str(training_file_path)
            if training_file_path
            else text("data.split.unsaved_source")
        )
        source_label = QLabel(
            text("data.split.source", source=source_text)
        )
        source_label.setWordWrap(True)
        source_label.setStyleSheet(
            "QLabel { background: #e8f7e8; border: 1px solid #92c892; "
            "padding: 5px; color: #215f21; }"
        )
        layout.addWidget(source_label)

        settings_group = QGroupBox(text("data.split.group"))
        settings_layout = QGridLayout(settings_group)

        self.percentage_spin = QSpinBox()
        self.percentage_spin.setRange(1, 50)
        self.percentage_spin.setValue(20)
        self.percentage_spin.setSuffix(" %")

        self.method_combo = QComboBox()
        self.method_combo.addItem(
            text("data.split.method.even"),
            "even"
        )
        self.method_combo.addItem(
            text("data.split.method.random"),
            "random"
        )

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999999)
        self.seed_spin.setValue(
            random.SystemRandom().randrange(1000000000)
        )
        self.remix_button = QPushButton(text("data.split.remix"))
        self.remix_button.clicked.connect(self.remix_selection)

        settings_layout.addWidget(QLabel(text("data.split.percentage")), 0, 0)
        settings_layout.addWidget(self.percentage_spin, 0, 1)
        settings_layout.addWidget(QLabel(text("data.split.method")), 1, 0)
        settings_layout.addWidget(self.method_combo, 1, 1, 1, 2)
        settings_layout.addWidget(QLabel(text("data.split.seed")), 2, 0)
        settings_layout.addWidget(self.seed_spin, 2, 1)
        settings_layout.addWidget(self.remix_button, 2, 2)
        layout.addWidget(settings_group)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table, 1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText(text("data.split.apply"))
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(text("common.cancel"))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.percentage_spin.valueChanged.connect(self.update_preview)
        self.method_combo.currentIndexChanged.connect(self.update_preview)
        self.seed_spin.valueChanged.connect(self.update_preview)
        self.update_preview()

    def test_record_count(self):
        total_count = len(self.records)

        if total_count < 2:
            return 0

        calculated_count = int(
            total_count * self.percentage_spin.value() / 100.0
            + 0.5
        )
        return max(1, min(calculated_count, total_count - 1))

    def calculate_selected_indices(self):
        total_count = len(self.records)
        test_count = self.test_record_count()

        if test_count < 1:
            return []

        if self.method_combo.currentData() == "random":
            generator = random.Random(self.seed_spin.value())
            return sorted(
                generator.sample(range(total_count), test_count)
            )

        return [
            min(
                total_count - 1,
                int((index + 0.5) * total_count / test_count)
            )
            for index in range(test_count)
        ]

    def remix_selection(self, checked=False):
        self.seed_spin.setValue(
            random.SystemRandom().randrange(1000000000)
        )

    def update_preview(self, *args):
        is_random = self.method_combo.currentData() == "random"
        self.seed_spin.setEnabled(is_random)
        self.remix_button.setEnabled(is_random)
        self.selected_indices = self.calculate_selected_indices()

        total_count = len(self.records)
        test_count = len(self.selected_indices)
        self.summary_label.setText(
            self.language.text(
                "data.split.summary",
                test_count=test_count,
                total_count=total_count
            )
        )

        self.preview_table.clear()
        self.preview_table.setColumnCount(len(self.columns) + 1)
        self.preview_table.setRowCount(test_count)
        self.preview_table.setHorizontalHeaderLabels(
            [self.language.text("data.split.previous_number")]
            + [
                column.get("name", self.language.text("data.column.fallback"))
                for column in self.columns
            ]
        )

        for preview_row, record_index in enumerate(self.selected_indices):
            number_item = QTableWidgetItem(str(record_index + 1))
            number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_table.setItem(preview_row, 0, number_item)

            for column_index, value in enumerate(self.records[record_index]):
                value_item = QTableWidgetItem(format_number(value, 7))
                value_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )
                self.preview_table.setItem(
                    preview_row,
                    column_index + 1,
                    value_item
                )

        self.preview_table.resizeColumnsToContents()


class TrainingDataDialog(QDialog):
    """
    Unabhängiger Editor für Trainingsdatendateien.

    Jede Datenspalte kann über das Kontextmenü ihrer
    Tabellenüberschrift einem passenden Input- oder
    Output-Neuron zugeordnet werden.
    """

    def __init__(
        self,
        network,
        document=None,
        file_path=None,
        parent=None,
        document_modified=False,
        data_label="Trainingsdaten",
        data_extension=".nndata",
        default_directory=None,
        training_document=None,
        training_file_path=None,
        language_manager=None,
        temporary_mappings=False,
        color_settings=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        text = self.language.text
        self.network = network
        self.color_settings = dict(color_settings or {})
        self.temporary_mappings = bool(temporary_mappings)
        self.data_extension = str(
            data_extension
        ).strip().lower() or ".nndata"

        if not self.data_extension.startswith("."):
            self.data_extension = "." + self.data_extension
        self.data_kind = (
            "test"
            if self.data_extension == ".nntest"
            else "training"
        )
        self.data_label = text(f"data.{self.data_kind}.label")
        self.default_directory = (
            os.path.abspath(str(default_directory))
            if default_directory
            else ""
        )
        self.training_document = (
            copy.deepcopy(training_document)
            if isinstance(training_document, dict)
            else None
        )
        self.training_file_path = training_file_path
        self.current_file_path = file_path
        self.loading_table = False
        self.modified = False
        self._edit_history = []
        self._edit_history_index = -1
        self._restoring_edit_history = False

        if document is None:
            input_count = max(
                1,
                len(network.get_input_neurons())
            )
            output_count = max(
                1,
                len(network.get_output_neurons())
            )
            document = TrainingDataIO.create_empty_document(
                input_count,
                output_count,
                text(
                    "data.editor.new_document",
                    data_label=self.data_label
                )
            )
        else:
            document = TrainingDataIO.prepare_document(
                copy.deepcopy(document)
            )

        self.document = copy.deepcopy(
            document
        )

        mapping_repaired = self.reconcile_document_mappings()

        TrainingDataIO.validate(
            self.document,
            self.language.text
        )
        names_synchronized = self.synchronize_document_neuron_names()

        self.resize(
            940,
            560
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.file_label = QLabel(self)
        self.main_layout.addWidget(
            self.file_label
        )

        self.compatibility_layout = QHBoxLayout()

        self.compatibility_label = QLabel(self)
        self.compatibility_label.setWordWrap(
            True
        )

        self.adjust_structure_button = QPushButton(
            text("data.editor.adjust_structure", data_label=self.data_label),
            self,
        )
        self.adjust_structure_button.clicked.connect(
            self.adjust_structure_to_network
        )

        self.compatibility_layout.addWidget(
            self.compatibility_label,
            1
        )
        self.compatibility_layout.addWidget(
            self.adjust_structure_button
        )

        self.main_layout.addLayout(
            self.compatibility_layout
        )

        self.calibration_source_label = QLabel(self)
        self.calibration_source_label.setWordWrap(True)
        self.calibration_source_label.setStyleSheet(
            "QLabel { background: #eaf4ff; border: 1px solid #9fc8ef; "
            "padding: 5px; color: #174f7a; }"
        )
        self.main_layout.addWidget(
            self.calibration_source_label
        )

        self.mapping_hint_label = QLabel(text("data.editor.mapping_hint"), self)
        self.mapping_info_button = QPushButton("i", self)
        self.mapping_info_button.setFixedSize(26, 24)
        self.mapping_info_button.setToolTip(
            text("data.editor.header_colors_info_tooltip")
        )
        self.mapping_info_button.clicked.connect(
            self.show_header_colors_information
        )
        mapping_hint_layout = QHBoxLayout()
        mapping_hint_layout.setContentsMargins(0, 0, 0, 0)
        mapping_hint_layout.addWidget(self.mapping_hint_label, 1)
        mapping_hint_layout.addWidget(self.mapping_info_button)
        self.main_layout.addLayout(mapping_hint_layout)

        self.scaling_warning_label = QLabel(
            text("data.editor.scaling_warning"),
            self,
        )
        self.scaling_warning_label.setWordWrap(True)
        self.scaling_warning_label.setStyleSheet(
            "QLabel { background: #fff2be; border: 1px solid #d6a53a; "
            "border-radius: 4px; padding: 6px; color: #7a4700; }"
        )
        self.scaling_warning_label.setVisible(False)
        self.main_layout.addWidget(self.scaling_warning_label)

        self.automatic_scaling_status_label = QLabel(self)
        self.automatic_scaling_status_label.setWordWrap(True)
        self.automatic_scaling_status_label.setStyleSheet(
            "QLabel { background: #e8f5e9; border: 1px solid #81c784; "
            "padding: 5px; color: #1b5e20; }"
        )
        self.automatic_scaling_status_label.setVisible(False)
        self.main_layout.addWidget(
            self.automatic_scaling_status_label
        )

        self.table = QTableWidget(self)
        self.table.setItemDelegate(
            NumericItemDelegate(self.parse_import_number, self.table)
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setAlternatingRowColors(
            True
        )
        self.table.setFont(
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        )
        self.table.verticalHeader().setVisible(
            False
        )
        self.table.horizontalHeader().setMinimumHeight(
            44
        )
        self.table.horizontalHeader().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.horizontalHeader().customContextMenuRequested.connect(
            self.show_column_header_context_menu
        )
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.customContextMenuRequested.connect(
            self.show_table_context_menu
        )
        self.table.itemChanged.connect(
            self.table_item_changed
        )

        self.paste_shortcut = QShortcut(
            QKeySequence.StandardKey.Paste,
            self.table
        )
        self.paste_shortcut.activated.connect(
            self.paste_from_clipboard
        )

        self.copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self.table
        )
        self.copy_shortcut.activated.connect(
            self.copy_selection_to_clipboard
        )

        self.cut_shortcut = QShortcut(
            QKeySequence.StandardKey.Cut,
            self.table
        )
        self.cut_shortcut.activated.connect(
            self.cut_selection_to_clipboard
        )

        self.select_all_shortcut = QShortcut(
            QKeySequence.StandardKey.SelectAll,
            self.table
        )
        self.select_all_shortcut.activated.connect(
            self.table.selectAll
        )

        self.delete_selection_shortcut = QShortcut(
            QKeySequence.StandardKey.Delete,
            self.table
        )
        self.delete_selection_shortcut.activated.connect(
            self.delete_selected_rows
        )

        self.undo_shortcut = QShortcut(
            QKeySequence.StandardKey.Undo,
            self.table
        )
        self.undo_shortcut.activated.connect(
            self.undo_table_edit
        )

        self.redo_shortcut = QShortcut(
            QKeySequence.StandardKey.Redo,
            self.table
        )
        self.redo_shortcut.activated.connect(
            self.redo_table_edit
        )

        self.main_layout.addWidget(
            self.table
        )

        self.row_button_layout = QHBoxLayout()

        self.add_row_button = QPushButton(
            text("data.editor.add_record"),
            self,
        )
        self.add_row_button.clicked.connect(
            self.add_row
        )

        self.delete_row_button = QPushButton(
            text("data.editor.delete_records"),
            self,
        )
        self.delete_row_button.clicked.connect(
            self.delete_selected_rows
        )

        self.import_csv_button = QPushButton(
            text("data.editor.import_csv"),
            self,
        )
        self.import_csv_button.clicked.connect(
            self.import_csv
        )

        self.auto_scale_button = QPushButton(
            text("data.editor.auto_scale"),
            self,
        )
        self.auto_scale_button.setToolTip(
            text("data.editor.auto_scale_tooltip")
        )
        self.auto_scale_button.clicked.connect(
            self.automatically_scale_from_table
        )
        self.auto_scale_button.setVisible(
            self.data_kind == "training"
        )

        self.column_overview_button = QPushButton(
            text("data.column_overview.button"),
            self,
        )
        self.column_overview_button.setToolTip(
            text("data.column_overview.tooltip")
        )
        self.column_overview_button.clicked.connect(
            self.edit_column_overview
        )

        self.input_array_button = QPushButton(
            text("data.editor.input_array"),
            self,
        )
        self.input_array_button.clicked.connect(
            self.edit_input_array
        )
        self.input_array_button.setVisible(
            self.data_kind == "training"
        )

        self.input_array_info_button = QPushButton("i", self)
        self.input_array_info_button.setFixedWidth(28)
        self.input_array_info_button.clicked.connect(
            self.show_input_array_information
        )
        self.input_array_info_button.setVisible(
            self.data_kind == "training"
        )

        self.split_training_data_button = QPushButton(
            text("data.editor.create_test_data"),
            self,
        )
        self.split_training_data_button.setToolTip(
            text("data.editor.create_test_data_tooltip")
        )
        self.split_training_data_button.clicked.connect(
            self.copy_from_training_data
        )
        self.split_training_data_button.setVisible(
            self.data_extension == ".nntest"
        )

        self.row_button_layout.addWidget(
            self.add_row_button
        )
        self.row_button_layout.addWidget(
            self.delete_row_button
        )
        self.row_button_layout.addSpacing(
            18
        )
        self.row_button_layout.addWidget(
            self.import_csv_button
        )
        self.row_button_layout.addWidget(
            self.auto_scale_button
        )
        self.row_button_layout.addSpacing(18)
        self.row_button_layout.addWidget(
            self.column_overview_button
        )
        self.row_button_layout.addSpacing(18)
        self.row_button_layout.addWidget(
            self.input_array_button
        )
        self.row_button_layout.addWidget(
            self.input_array_info_button
        )
        self.row_button_layout.addSpacing(18)
        self.row_button_layout.addWidget(
            self.split_training_data_button
        )
        self.row_button_layout.addStretch()

        self.main_layout.addLayout(
            self.row_button_layout
        )

        self.new_button = QPushButton(
            text("common.new"),
            self,
        )
        self.new_button.clicked.connect(
            self.new_document
        )

        self.open_button = QPushButton(
            text("common.open"),
            self,
        )
        self.open_button.clicked.connect(
            self.open_document
        )

        self.save_button = QPushButton(
            text("common.save"),
            self,
        )
        self.save_button.clicked.connect(
            self.save_document
        )

        self.save_as_button = QPushButton(
            text("common.save_as"),
            self,
        )
        self.save_as_button.clicked.connect(
            self.save_document_as
        )

        self.file_button_layout = QHBoxLayout()
        self.file_button_layout.addWidget(
            self.new_button
        )
        self.file_button_layout.addWidget(
            self.open_button
        )
        self.file_button_layout.addWidget(
            self.save_button
        )
        self.file_button_layout.addWidget(
            self.save_as_button
        )
        self.file_button_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText(text("common.ok"))
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(text("common.cancel"))
        self.button_box.accepted.connect(
            self.accept
        )
        self.button_box.rejected.connect(
            self.reject
        )

        self.bottom_button_layout = QHBoxLayout()
        self.bottom_button_layout.addLayout(
            self.file_button_layout
        )
        self.bottom_button_layout.addWidget(
            self.button_box
        )

        self.main_layout.addLayout(
            self.bottom_button_layout
        )

        self.load_document_into_table()
        self.set_modified(
            document_modified or mapping_repaired or names_synchronized
        )
        self.reset_edit_history()

    def reconcile_document_mappings(self):
        """Repariert eindeutige Zuordnungen gegen das tatsächlich geladene Netz."""

        changed = False
        columns = self.document.get("columns", [])

        for role, neuron_type in (
            ("input", NeuronType.INPUT),
            ("output", NeuronType.OUTPUT),
        ):
            role_columns = [
                column
                for column in columns
                if isinstance(column, dict) and column.get("role") == role
            ]
            neurons = self.get_current_neurons_for_role(role)

            # Nur bei gleicher Anzahl ist eine Reparatur nach Reihenfolge
            # eindeutig und verändert keine beabsichtigte Teilzuordnung.
            if len(role_columns) != len(neurons):
                continue

            neurons_by_id = {neuron.id: neuron for neuron in neurons}
            neurons_by_name = {
                str(neuron.name).strip().casefold(): neuron
                for neuron in neurons
            }
            used_ids = set()

            for column_index, column in enumerate(role_columns):
                neuron = neurons_by_id.get(column.get("mapped_neuron_id"))
                if neuron is not None and neuron.id in used_ids:
                    neuron = None

                if neuron is None:
                    for candidate_name in (
                        column.get("mapped_neuron_name"),
                        column.get("name"),
                    ):
                        normalized_name = str(
                            candidate_name or ""
                        ).strip().casefold()
                        candidate = neurons_by_name.get(normalized_name)
                        if candidate is not None and candidate.id not in used_ids:
                            neuron = candidate
                            break

                if neuron is None:
                    candidate = neurons[column_index]
                    if candidate.id not in used_ids:
                        neuron = candidate

                if neuron is None or neuron.neuron_type != neuron_type:
                    continue

                used_ids.add(neuron.id)
                if (
                    column.get("mapped_neuron_id") != neuron.id
                    or column.get("mapped_neuron_name") != neuron.name
                ):
                    column["mapped_neuron_id"] = neuron.id
                    column["mapped_neuron_name"] = neuron.name
                    changed = True

        return changed

    def get_current_neurons_for_role(self, role):
        """Liest die Typen direkt aus dem aktuellen Netzwerkzustand."""

        expected_type = (
            NeuronType.INPUT if role == "input" else NeuronType.OUTPUT
        )
        return [
            neuron
            for neuron in self.network.get_neurons()
            if neuron.neuron_type == expected_type
        ]

    @staticmethod
    def create_test_document_from_training(
        training_document,
        parent=None,
        language_manager=None
    ):
        """Fragt ab, welche Struktur in neue Testdaten übernommen wird."""

        language = language_manager or LanguageManager()
        text = language.text

        if not isinstance(training_document, dict):
            return True, None

        message_box = QMessageBox(parent)
        message_box.setWindowTitle(text("data.new_test.title"))
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setText(
            text("data.new_test.question")
        )
        message_box.setInformativeText(
            text("data.new_test.information")
        )

        all_button = message_box.addButton(
            text("data.new_test.structure_and_scaling"),
            QMessageBox.ButtonRole.AcceptRole
        )
        structure_button = message_box.addButton(
            text("data.new_test.structure_only"),
            QMessageBox.ButtonRole.ActionRole
        )
        blank_button = message_box.addButton(
            text("data.new_test.blank"),
            QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = message_box.addButton(
            text("common.cancel"),
            QMessageBox.ButtonRole.RejectRole
        )
        message_box.setDefaultButton(all_button)
        message_box.exec()

        clicked_button = message_box.clickedButton()

        if clicked_button is cancel_button or clicked_button is None:
            return False, None

        if clicked_button is blank_button:
            return True, None

        document = TrainingDataIO.prepare_document(
            copy.deepcopy(training_document)
        )
        document["name"] = text("data.new_test.document_name")
        document["records"] = []

        for column in document["columns"]:
            if clicked_button is all_button:
                calibration = TrainingDataIO.normalize_calibration(
                    column.get("calibration")
                )
                column["calibration"] = copy.deepcopy(calibration)
                column["calibration_source"] = "training_data"
                column["training_calibration"] = copy.deepcopy(calibration)
            else:
                column["calibration"] = (
                    TrainingDataIO.default_calibration()
                )
                column.pop("calibration_source", None)
                column.pop("training_calibration", None)

        return True, document

    def count_columns_by_role(self, role):
        return sum(
            1
            for column in self.document["columns"]
            if column["role"] == role
        )

    def get_role_neurons(self, role):
        return self.get_current_neurons_for_role(role)

    def get_valid_mapped_neuron(self, column):
        neuron_id = column.get(
            "mapped_neuron_id"
        )

        if neuron_id is None:
            return None

        expected_type = (
            NeuronType.INPUT
            if column["role"] == "input"
            else NeuronType.OUTPUT
        )

        neuron = self.network.get_neuron(neuron_id)

        if neuron is not None and neuron.neuron_type == expected_type:
            return neuron

        role_neurons = self.get_current_neurons_for_role(column["role"])
        neurons_by_name = {
            str(candidate.name).strip().casefold(): candidate
            for candidate in role_neurons
        }

        for candidate_name in (
            column.get("mapped_neuron_name"),
            column.get("name"),
        ):
            normalized_name = str(candidate_name or "").strip().casefold()
            candidate = neurons_by_name.get(normalized_name)
            if candidate is not None:
                neuron = candidate
                break
        else:
            role_columns = [
                candidate
                for candidate in self.document.get("columns", [])
                if isinstance(candidate, dict)
                and candidate.get("role") == column["role"]
            ]
            neuron = None
            if len(role_columns) == len(role_neurons):
                for column_index, candidate_column in enumerate(role_columns):
                    if candidate_column is column:
                        neuron = role_neurons[column_index]
                        break

        if neuron is None or neuron.neuron_type != expected_type:
            return None

        column["mapped_neuron_id"] = neuron.id
        column["mapped_neuron_name"] = neuron.name

        return neuron

    def get_column_mapping_status(self, column, duplicate_ids):
        """
        Ermittelt den sichtbaren Zuordnungsstatus einer Spalte.

        Rückgabewert:
            - status: ok, missing, invalid oder duplicate
            - anzuzeigender Zuordnungstext
        """

        neuron_id = column.get(
            "mapped_neuron_id"
        )

        if neuron_id is None:
            return (
                "missing",
                self.language.text("data.mapping.missing")
            )

        neuron = self.get_valid_mapped_neuron(
            column
        )

        if neuron is None:
            existing_neuron = self.network.get_neuron(neuron_id)
            stored_name = column.get(
                "mapped_neuron_name"
            )

            if existing_neuron is not None:
                mapping_text = self.language.text(
                    "data.mapping.wrong_type",
                    name=existing_neuron.name,
                )
            elif stored_name:
                mapping_text = (
                    self.language.text(
                        "data.mapping.not_found",
                        name=stored_name
                    )
                )
            else:
                mapping_text = (
                    self.language.text("data.mapping.invalid")
                )

            return (
                "invalid",
                mapping_text
            )

        if neuron.id in duplicate_ids:
            return (
                "duplicate",
                self.language.text(
                    "data.mapping.duplicate",
                    name=neuron.name
                )
            )

        return (
            "ok",
            self.language.text("data.mapping.ok", name=neuron.name)
        )

    def get_duplicate_mapping_ids(self):
        """
        Liefert die mehrfach verwendeten Neuronen-IDs,
        getrennt nach Input- und Output-Zuordnungen.
        """

        occurrences = {}

        for column in self.document["columns"]:
            neuron = self.get_valid_mapped_neuron(
                column
            )

            if neuron is None:
                continue

            key = (
                column["role"],
                neuron.id
            )

            occurrences[key] = (
                occurrences.get(
                    key,
                    0
                )
                + 1
            )

        return {
            neuron_id
            for (role, neuron_id), count in occurrences.items()
            if count > 1
        }

    def get_column_numeric_values(self, data_index):
        """Liefert alle gültigen endlichen Rohwerte einer Datenspalte."""

        values = []
        table_column = data_index + 1

        for row in range(self.table.rowCount()):
            item = self.table.item(
                row,
                table_column
            )

            if item is None:
                continue

            try:
                value = self.number_from_item(item)

            except ValueError:
                continue

            if math.isfinite(value):
                values.append(value)

        if not values and self.table.rowCount() == 0:
            for record in self.document.get("records", []):
                if not isinstance(record, list) or data_index >= len(record):
                    continue

                try:
                    value = float(record[data_index])

                except (TypeError, ValueError):
                    continue

                if math.isfinite(value):
                    values.append(value)

        return values

    def get_column_value_range(self, data_index):
        """Liefert Minimum und Maximum der sichtbaren Rohwerte."""

        values = self.get_column_numeric_values(
            data_index
        )

        if not values:
            return None

        return min(values), max(values)

    def automatic_calibration_mode(self, column):
        """Wählt den Netzbereich passend zur Spalte und Output-Aktivierung."""

        if column.get("role") != "output":
            return "minmax_0_1"

        neuron = self.get_valid_mapped_neuron(
            column
        )

        if (
            neuron is not None
            and str(neuron.activation_function).strip().casefold() == "tanh"
        ):
            return "minmax_minus1_1"

        return "minmax_0_1"

    def automatically_scale_from_table(self):
        """Skaliert alle geeigneten Trainingsspalten anhand ihrer Rohwerte."""

        if not self.has_complete_numeric_record():
            return

        scaled_count = 0
        constant_columns = []
        empty_columns = []
        document_changed = False

        for data_index, column in enumerate(
            self.document.get("columns", [])
        ):
            if column.get("data_type", "analog") == "binary":
                if TrainingDataIO.normalize_calibration(
                    column.get("calibration")
                )["mode"] != "none":
                    column.setdefault(
                        "analog_calibration",
                        TrainingDataIO.normalize_calibration(
                            column.get("calibration")
                        ),
                    )
                    column["calibration"] = TrainingDataIO.default_calibration()
                    document_changed = True
                continue
            values = self.get_column_numeric_values(
                data_index
            )
            column_name = str(
                column.get("name") or f"{data_index + 1}"
            )

            if not values:
                empty_columns.append(column_name)
                continue

            source_min = min(values)
            source_max = max(values)

            if not source_min < source_max:
                constant_columns.append(column_name)
                continue

            mean = sum(values) / len(values)
            variance = sum(
                (value - mean) ** 2
                for value in values
            ) / len(values)
            new_calibration = {
                "mode": self.automatic_calibration_mode(column),
                "source_min": source_min,
                "source_max": source_max,
                "mean": mean,
                "stddev": math.sqrt(variance)
            }
            old_calibration = TrainingDataIO.normalize_calibration(
                column.get("calibration")
            )

            if not TrainingDataIO.calibrations_equal(
                old_calibration,
                new_calibration
            ):
                document_changed = True

            column["calibration"] = new_calibration

            if (
                "calibration_source" in column
                or "training_calibration" in column
            ):
                document_changed = True

            column.pop("calibration_source", None)
            column.pop("training_calibration", None)
            scaled_count += 1

        self.update_headers()

        if document_changed:
            self.set_modified(True)

        self.automatic_scaling_status_label.setText(
            self.language.text(
                "data.editor.auto_scale_result",
                scaled=scaled_count,
                constant=len(constant_columns),
                empty=len(empty_columns)
            )
        )

        skipped_columns = constant_columns + empty_columns
        self.automatic_scaling_status_label.setToolTip(
            self.language.text(
                "data.editor.auto_scale_skipped",
                columns=", ".join(skipped_columns)
            )
            if skipped_columns
            else ""
        )
        self.automatic_scaling_status_label.setVisible(True)

        if document_changed:
            self.record_edit_history()

    def get_calibration_presentation(self, column, data_index):
        """Erzeugt Überschrift, Hilfetext und Warnstatus einer Skalierung."""

        if column.get("data_type", "analog") == "binary":
            return (
                self.language.text("data.type.header_binary"),
                self.language.text("data.type.tooltip_binary"),
                False
            )

        calibration = TrainingDataIO.normalize_calibration(
            column.get("calibration")
        )
        mode = calibration["mode"]
        inherited = (
            column.get("calibration_source") == "training_data"
            and isinstance(column.get("training_calibration"), dict)
        )
        reference = TrainingDataIO.normalize_calibration(
            column.get("training_calibration")
        ) if inherited else None
        value_range = self.get_column_value_range(
            data_index
        )

        if (
            inherited
            and not TrainingDataIO.calibrations_equal(
                calibration,
                reference
            )
        ):
            return (
                self.language.text("data.calibration.changed"),
                self.language.text("data.calibration.changed_tooltip"),
                True
            )

        outside_training_range = False

        if (
            inherited
            and value_range is not None
            and reference["mode"] in (
                "minmax_0_1",
                "minmax_minus1_1"
            )
        ):
            minimum, maximum = value_range
            outside_training_range = (
                minimum < reference["source_min"]
                or maximum > reference["source_max"]
            )

        if outside_training_range:
            minimum, maximum = value_range
            return (
                self.language.text("data.calibration.outside_training"),
                self.language.text(
                    "data.calibration.outside_training_tooltip",
                    minimum=f"{minimum:g}",
                    maximum=f"{maximum:g}",
                    source_min=f"{reference['source_min']:g}",
                    source_max=f"{reference['source_max']:g}"
                ),
                True
            )

        source_suffix = (
            self.language.text("data.calibration.training_suffix")
            if inherited
            else ""
        )

        if mode == "minmax_0_1":
            return (
                self.language.text(
                    "data.calibration.header_0_1",
                    suffix=source_suffix
                ),
                self.language.text(
                    "data.calibration.tooltip_0_1",
                    source_min=f"{calibration['source_min']:g}",
                    source_max=f"{calibration['source_max']:g}",
                    inherited=(
                        self.language.text("data.calibration.inherited_sentence")
                        if inherited else ""
                    )
                ),
                False
            )

        if mode == "minmax_minus1_1":
            return (
                self.language.text(
                    "data.calibration.header_minus1_1",
                    suffix=source_suffix
                ),
                self.language.text(
                    "data.calibration.tooltip_minus1_1",
                    source_min=f"{calibration['source_min']:g}",
                    source_max=f"{calibration['source_max']:g}",
                    inherited=(
                        self.language.text("data.calibration.inherited_sentence")
                        if inherited else ""
                    )
                ),
                False
            )

        if mode == "standard":
            return (
                self.language.text(
                    "data.calibration.header_standard",
                    suffix=source_suffix
                ),
                self.language.text(
                    "data.calibration.tooltip_standard",
                    mean=f"{calibration['mean']:g}",
                    stddev=f"{calibration['stddev']:g}",
                    inherited=(
                        self.language.text("data.calibration.inherited_sentence")
                        if inherited else ""
                    )
                ),
                False
            )

        if value_range is None:
            return (
                self.language.text(
                    "data.calibration.header_none",
                    suffix=source_suffix
                ),
                self.language.text(
                    "data.calibration.tooltip_none_empty",
                    inherited=(
                        self.language.text("data.calibration.inherited_setting")
                        if inherited else ""
                    )
                ),
                False
            )

        minimum, maximum = value_range
        range_text = f"{minimum:g} … {maximum:g}"
        warning = minimum < -1.0 or maximum > 1.0

        if warning:
            return (
                self.language.text(
                    "data.calibration.header_unscaled_warning",
                    range=range_text
                ),
                self.language.text(
                    "data.calibration.tooltip_unscaled_warning",
                    range=range_text
                ),
                True
            )

        return (
            self.language.text(
                "data.calibration.header_unscaled",
                range=range_text
            ),
            self.language.text(
                "data.calibration.tooltip_unscaled",
                range=range_text
            ),
            False
        )

    def has_complete_numeric_record(self):
        """Prüft, ob mindestens eine vollständig ausgefüllte Zahlenzeile existiert."""

        data_column_count = self.table.columnCount() - 1
        if data_column_count <= 0:
            return False

        for row in range(self.table.rowCount()):
            complete = True

            for column in range(1, self.table.columnCount()):
                item = self.table.item(row, column)

                if item is None or not item.text().strip():
                    complete = False
                    break

                try:
                    value = self.number_from_item(item)
                except ValueError:
                    complete = False
                    break

                if not math.isfinite(value):
                    complete = False
                    break

            if complete:
                return True

        return False

    def update_auto_scale_button_state(self):
        """Aktiviert die Skalierung nur bei auswertbaren Trainingsdaten."""

        if not hasattr(self, "auto_scale_button"):
            return

        self.auto_scale_button.setEnabled(
            self.data_kind == "training"
            and self.has_complete_numeric_record()
        )

    def update_headers(self):
        """
        Aktualisiert Text, Farbe und Hinweis aller
        Tabellenüberschriften entsprechend ihrer Zuordnung.
        """

        self.table.setHorizontalHeaderLabels(
            [
                self.language.text("data.table.number")
            ]
            + [
                ""
                for column in self.document["columns"]
            ]
        )

        duplicate_ids = self.get_duplicate_mapping_ids()

        number_header = self.table.horizontalHeaderItem(
            0
        )

        if number_header is not None:
            number_header.setText(
                self.language.text("data.table.number")
            )
            number_header.setToolTip(
                self.language.text(
                    "data.table.number_tooltip",
                    data_label=self.data_label
                )
            )

        status_colors = {
            "ok": (
                QColor(0, 110, 35),
                QColor(220, 245, 225)
            ),
            "missing": (
                QColor(170, 0, 0),
                QColor(255, 220, 220)
            ),
            "invalid": (
                QColor(160, 85, 0),
                QColor(255, 235, 195)
            ),
            "duplicate": (
                QColor(170, 0, 0),
                QColor(255, 210, 210)
            ),
            "unscaled_warning": (
                QColor(145, 85, 0),
                QColor(255, 242, 190)
            ),
            "unscaled_neutral": (
                QColor(75, 75, 75),
                QColor(235, 235, 235)
            )
        }

        unscaled_value_warning = False

        for data_index, column in enumerate(
            self.document["columns"]
        ):
            table_column = data_index + 1
            header_item = self.table.horizontalHeaderItem(
                table_column
            )

            if header_item is None:
                header_item = QTableWidgetItem()
                self.table.setHorizontalHeaderItem(
                    table_column,
                    header_item
                )

            status, mapping_text = self.get_column_mapping_status(
                column,
                duplicate_ids
            )

            (
                calibration_text,
                calibration_tooltip,
                calibration_warning
            ) = self.get_calibration_presentation(
                column,
                data_index
            )
            if (
                calibration_warning
                and column.get("data_type", "analog") != "binary"
            ):
                unscaled_value_warning = True
            if column.get("data_type", "analog") != "binary":
                calibration_text = self.language.text(
                    "data.type.header_analog",
                    calibration=calibration_text
                )
            unit = str(
                column.get("unit", "")
            ).strip()
            display_name = (
                f"{column['name']} [{unit}]"
                if unit
                else column["name"]
            )
            header_lines = [
                self.language.text(
                    "data.table.role_input"
                    if column.get("role") == "input"
                    else "data.table.role_output"
                ),
                f"{display_name}  ⚙"
            ]

            header_lines.append(
                calibration_text
            )

            header_item.setText(
                "\n".join(header_lines)
            )

            calibration_mode = TrainingDataIO.normalize_calibration(
                column.get("calibration")
            )["mode"]

            if column.get("data_type", "analog") == "binary":
                display_status = status
            elif calibration_warning and status == "ok":
                display_status = "unscaled_warning"
            elif calibration_mode == "none" and status == "ok":
                display_status = "unscaled_neutral"
            else:
                display_status = status
            foreground, background = status_colors[
                display_status
            ]

            header_item.setForeground(
                foreground
            )
            header_item.setBackground(
                background
            )

            header_font = QFont(
                self.table.font()
            )
            header_font.setBold(
                True
            )
            header_item.setFont(
                header_font
            )

            if status == "ok":
                tooltip = self.language.text("data.mapping.tooltip_ok")
            elif status == "missing":
                tooltip = self.language.text("data.mapping.tooltip_missing")
            elif status == "invalid":
                tooltip = self.language.text("data.mapping.tooltip_invalid")
            else:
                tooltip = self.language.text("data.mapping.tooltip_duplicate")

            header_item.setToolTip(
                tooltip
                + (
                    self.language.text(
                        "data.table.unit_tooltip",
                        unit=unit
                    )
                    if unit
                    else self.language.text("data.table.no_unit_tooltip")
                )
                + "\n"
                + calibration_tooltip
                + self.language.text("data.table.raw_values_tooltip")
            )

        self.scaling_warning_label.setVisible(unscaled_value_warning)

        self.table.horizontalHeader().setMinimumHeight(
            62
        )

        self.table.setColumnWidth(
            0,
            55
        )

        for column_index in range(
            1,
            self.table.columnCount()
        ):
            self.table.setColumnWidth(
                column_index,
                190
            )

        self.update_auto_scale_button_state()

    def show_column_header_context_menu(self, position):
        """
        Öffnet das Kontextmenü einer Spaltenüberschrift.
        """

        header = self.table.horizontalHeader()
        section = header.logicalIndexAt(
            position
        )

        if section <= 0:
            return

        self.edit_column_properties(section)

    def show_table_context_menu(self, position):
        """Zeigt die üblichen Bearbeitungsbefehle für Tabellenzellen."""

        clicked_index = self.table.indexAt(position)

        if (
            clicked_index.isValid()
            and not self.table.selectionModel().isSelected(clicked_index)
        ):
            self.table.clearSelection()
            self.table.setCurrentCell(
                clicked_index.row(),
                clicked_index.column()
            )
            clicked_item = self.table.item(
                clicked_index.row(),
                clicked_index.column()
            )

            if clicked_item is not None:
                clicked_item.setSelected(True)

        menu = QMenu(self)
        undo_action = menu.addAction(self.language.text("action.undo"))
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.setEnabled(self.can_undo_table_edit())
        redo_action = menu.addAction(self.language.text("action.redo"))
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.setEnabled(self.can_redo_table_edit())
        menu.addSeparator()
        cut_action = menu.addAction(self.language.text("action.cut"))
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        copy_action = menu.addAction(self.language.text("action.copy"))
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        paste_action = menu.addAction(self.language.text("action.paste"))
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        menu.addSeparator()
        select_all_action = menu.addAction(
            self.language.text("action.select_all")
        )
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        delete_action = menu.addAction(self.language.text("action.delete"))
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)

        selected_action = menu.exec(
            self.table.viewport().mapToGlobal(position)
        )

        if selected_action == undo_action:
            self.undo_table_edit()
        elif selected_action == redo_action:
            self.redo_table_edit()
        elif selected_action == cut_action:
            self.cut_selection_to_clipboard()
        elif selected_action == copy_action:
            self.copy_selection_to_clipboard()
        elif selected_action == paste_action:
            self.paste_from_clipboard()
        elif selected_action == select_all_action:
            self.table.selectAll()
        elif selected_action == delete_action:
            self.delete_selected_rows()

    def edit_column_properties(self, section):
        if section == 0:
            return

        data_index = section - 1

        if (
            data_index < 0
            or data_index >= len(self.document["columns"])
        ):
            return

        column_values = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, section)
            if item is None or not item.text().strip():
                continue
            try:
                value = self.number_from_item(item)
            except ValueError:
                continue
            if math.isfinite(value):
                column_values.append(value)

        dialog = ColumnPropertiesDialog(
            self.document["columns"][data_index],
            self.network,
            column_values,
            language_manager=self.language,
            parent=self
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_column = dialog.column_data
        old_role = self.document["columns"][data_index]["role"]
        new_role = new_column["role"]
        if old_role != new_role and self.count_columns_by_role(old_role) <= 1:
            QMessageBox.warning(
                self,
                self.language.text("data.message.role_change.title"),
                self.language.text("data.message.role_change.message"),
            )
            return

        self.document["columns"][data_index] = new_column
        self.remove_invalid_input_array()
        self.synchronize_column_neuron_name(new_column)

        self.update_headers()
        self.update_compatibility_label()
        self.set_modified(
            True
        )
        self.record_edit_history()

    def edit_column_overview(self):
        """Öffnet die gemeinsame Tabelle für die Kopfdaten aller Spalten."""

        current_section = self.table.currentColumn()
        initial_row = max(0, current_section - 1)
        dialog = ColumnOverviewDialog(
            self.document["columns"],
            self.network,
            self.document.get("records", []),
            initial_row=initial_row,
            language_manager=self.language,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.columns == self.document["columns"]:
            return

        self.document["columns"] = copy.deepcopy(dialog.columns)
        self.remove_invalid_input_array()
        for column in self.document["columns"]:
            self.synchronize_column_neuron_name(column)
        self.update_headers()
        self.update_compatibility_label()
        self.set_modified(True)
        self.record_edit_history()

    def remove_invalid_input_array(self):
        """Entfernt eine Rasterdefinition, wenn die Inputstruktur geändert wurde."""

        if "input_array" not in self.document:
            return False
        try:
            TrainingDataIO._validate_input_array(
                self.document,
                self.document.get("columns", []),
                self.language.text
            )
        except ValueError:
            self.document.pop("input_array", None)
            return True
        return False

    def synchronize_column_neuron_name(self, column):
        """Übernimmt einen bestätigten Spaltennamen in das zugeordnete Neuron."""

        mapped_neuron = self.network.get_neuron(
            column.get("mapped_neuron_id")
        )
        if mapped_neuron is None or mapped_neuron.name == column.get("name"):
            return False

        mapped_neuron.name = column["name"]
        mapped_neuron.update()
        column["mapped_neuron_name"] = mapped_neuron.name

        parent_window = self.parentWidget()
        synchronize = getattr(
            parent_window,
            "synchronize_neuron_name_in_data",
            None,
        )
        if callable(synchronize):
            synchronize(mapped_neuron, mapped_neuron.name)
        scene = getattr(parent_window, "scene", None)
        if scene is not None:
            scene.update()
        return True

    def synchronize_document_neuron_names(self):
        """Gleicht vorhandene Input-/Output-Namen an ihre Datenspalten an."""

        changed = False
        for column in self.document.get("columns", []):
            desired_name = str(column.get("name") or "").strip()
            neuron = self.get_valid_mapped_neuron(column)
            if not desired_name or neuron is None or neuron.name == desired_name:
                continue
            duplicate = next(
                (
                    candidate
                    for candidate in self.network.get_neurons()
                    if candidate.id != neuron.id
                    and str(candidate.name).strip().casefold()
                    == desired_name.casefold()
                ),
                None,
            )
            if duplicate is not None:
                continue
            if self.synchronize_column_neuron_name(column):
                changed = True
        return changed

    def update_window_title(self):
        if self.current_file_path:
            file_name = os.path.basename(
                self.current_file_path
            )
        else:
            file_name = self.language.text(
                "data.editor.new_document",
                data_label=self.data_label
            )

        marker = " *" if self.modified else ""

        self.setWindowTitle(
            self.language.text(
                "data.editor.window_title",
                data_label=self.data_label,
                file_name=file_name,
                marker=marker
            )
        )

        self.file_label.setText(
            self.language.text(
                "data.editor.file",
                path=(
                    self.current_file_path
                    or self.language.text("data.editor.not_saved")
                )
            )
        )

    def update_compatibility_label(self):
        network_input_count = len(
            self.network.get_input_neurons()
        )
        network_output_count = len(
            self.network.get_output_neurons()
        )

        data_input_count = self.count_columns_by_role(
            "input"
        )
        data_output_count = self.count_columns_by_role(
            "output"
        )

        structure_compatible = (
            network_input_count == data_input_count
            and network_output_count == data_output_count
        )

        invalid_mapping_count = 0
        used_input_ids = set()
        used_output_ids = set()
        duplicate_mapping_count = 0

        for column in self.document["columns"]:
            neuron = self.get_valid_mapped_neuron(
                column
            )

            if neuron is None:
                invalid_mapping_count += 1
                continue

            used_ids = (
                used_input_ids
                if column["role"] == "input"
                else used_output_ids
            )

            if neuron.id in used_ids:
                duplicate_mapping_count += 1
            else:
                used_ids.add(
                    neuron.id
                )

        if not structure_compatible:
            compatibility_text = self.language.text(
                "data.compatibility.incompatible",
                data_label=self.data_label,
                data_inputs=data_input_count,
                data_outputs=data_output_count,
                network_inputs=network_input_count,
                network_outputs=network_output_count
            )
        elif invalid_mapping_count > 0:
            compatibility_text = self.language.text(
                "data.compatibility.invalid_mapping",
                count=invalid_mapping_count
            )
        elif duplicate_mapping_count > 0:
            compatibility_text = self.language.text(
                "data.compatibility.duplicate_mapping"
            )
        else:
            compatibility_text = self.language.text(
                "data.compatibility.complete",
                data_label=self.data_label,
                inputs=data_input_count,
                outputs=data_output_count
            )

        self.compatibility_label.setText(
            compatibility_text
        )

        self.adjust_structure_button.setVisible(
            not structure_compatible
        )
        self.update_input_array_button_state()

    def can_define_input_array(self):
        input_columns = [
            column
            for column in self.document.get("columns", [])
            if column.get("role") == "input"
        ]
        return bool(input_columns) and all(
            column.get("data_type") == "binary"
            for column in input_columns
        )

    def update_input_array_button_state(self):
        if not hasattr(self, "input_array_button"):
            return
        enabled = (
            self.data_kind == "training"
            and self.can_define_input_array()
        )
        self.input_array_button.setEnabled(enabled)
        self.input_array_button.setToolTip(
            self.language.text(
                "data.editor.input_array_tooltip"
                if enabled
                else "data.editor.input_array_unavailable"
            )
        )

    def edit_input_array(self):
        if not self.can_define_input_array():
            return
        dialog = BinaryInputArrayDialog(
            self.document,
            language_manager=self.language,
            color_settings=self.color_settings,
            parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self.document.get("input_array") == dialog.result_definition:
            return
        self.document["input_array"] = copy.deepcopy(
            dialog.result_definition
        )
        self.set_modified(True)
        self.record_edit_history()

    def show_input_array_information(self):
        QMessageBox.information(
            self,
            self.language.text(
                "data.editor.input_array_information_title"
            ),
            self.language.text(
                "data.editor.input_array_information"
            )
        )

    def set_modified(self, modified):
        self.modified = bool(
            modified
        )
        self.update_window_title()

    def capture_edit_history_state(self):
        """Erfasst auch vorübergehend leere oder noch ungültige Tabellenzellen."""

        cells = []

        for row in range(self.table.rowCount()):
            row_cells = []

            for column in range(1, self.table.columnCount()):
                item = self.table.item(row, column)
                row_cells.append(
                    {
                        "text": item.text() if item is not None else "",
                        "value": (
                            copy.deepcopy(
                                item.data(Qt.ItemDataRole.UserRole)
                            )
                            if item is not None
                            else None
                        )
                    }
                )

            cells.append(row_cells)

        return {
            "document": copy.deepcopy(self.document),
            "cells": cells,
            "modified": bool(self.modified)
        }

    @staticmethod
    def edit_history_content(state):
        return {
            "document": state.get("document"),
            "cells": state.get("cells")
        }

    def reset_edit_history(self):
        """Beginnt für die aktuell geladene Datei einen neuen lokalen Verlauf."""

        self._edit_history = [
            self.capture_edit_history_state()
        ]
        self._edit_history_index = 0

    def record_edit_history(self):
        """Fügt eine neue Tabellenmomentaufnahme hinzu."""

        if self._restoring_edit_history:
            return

        state = self.capture_edit_history_state()

        if self._edit_history_index >= 0:
            current_state = self._edit_history[
                self._edit_history_index
            ]

            if (
                self.edit_history_content(current_state)
                == self.edit_history_content(state)
            ):
                current_state["modified"] = state["modified"]
                return

        del self._edit_history[
            self._edit_history_index + 1:
        ]
        self._edit_history.append(state)
        self._edit_history_index = len(self._edit_history) - 1

        # Große Datenmengen sollen den Speicher nicht unbegrenzt anwachsen
        # lassen. 100 vollständige Bearbeitungsschritte reichen für den Editor.
        if len(self._edit_history) > 101:
            del self._edit_history[0]
            self._edit_history_index -= 1

    def restore_edit_history_state(self, state):
        """Stellt eine Tabellenmomentaufnahme ohne neue Verlaufsschritte her."""

        self._restoring_edit_history = True
        self.loading_table = True

        try:
            self.document = copy.deepcopy(state["document"])
            columns = self.document.get("columns", [])
            cells = state.get("cells", [])
            self.table.clear()
            self.table.setColumnCount(len(columns) + 1)
            self.table.setRowCount(len(cells))
            self.update_headers()

            for row, row_cells in enumerate(cells):
                number_item = QTableWidgetItem(str(row + 1))
                number_item.setFlags(
                    number_item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                    & ~Qt.ItemFlag.ItemIsSelectable
                )
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, number_item)

                for data_index, cell in enumerate(row_cells):
                    item = QTableWidgetItem(str(cell.get("text", "")))
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        copy.deepcopy(cell.get("value"))
                    )
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.table.setItem(row, data_index + 1, item)
        finally:
            self.loading_table = False
            self._restoring_edit_history = False

        self.automatic_scaling_status_label.setVisible(False)
        self.update_headers()
        self.update_compatibility_label()
        self.update_calibration_source_label()
        self.set_modified(state.get("modified", True))

    def can_undo_table_edit(self):
        return self._edit_history_index > 0

    def can_redo_table_edit(self):
        return (
            0 <= self._edit_history_index < len(self._edit_history) - 1
        )

    def undo_table_edit(self):
        if not self.can_undo_table_edit():
            return

        self._edit_history_index -= 1
        self.restore_edit_history_state(
            self._edit_history[self._edit_history_index]
        )

    def redo_table_edit(self):
        if not self.can_redo_table_edit():
            return

        self._edit_history_index += 1
        self.restore_edit_history_state(
            self._edit_history[self._edit_history_index]
        )

    def mark_edit_history_saved(self):
        if self._edit_history_index < 0:
            return

        self._edit_history[self._edit_history_index]["modified"] = False

    def update_calibration_source_label(self):
        inherited_count = sum(
            1
            for column in self.document.get("columns", [])
            if column.get("calibration_source") == "training_data"
        )

        visible = self.data_extension == ".nntest" and inherited_count > 0
        self.calibration_source_label.setVisible(visible)

        if visible:
            self.calibration_source_label.setText(
                self.language.text("data.calibration.source_training")
            )

    def load_document_into_table(self):
        self.automatic_scaling_status_label.setVisible(False)
        self.loading_table = True

        try:
            columns = self.document["columns"]
            records = self.document["records"]

            self.table.clear()
            self.table.setColumnCount(
                len(columns) + 1
            )
            self.table.setRowCount(
                len(records)
            )

            self.update_headers()

            for row_index, record in enumerate(
                records
            ):
                number_item = QTableWidgetItem(
                    str(row_index + 1)
                )
                number_item.setFlags(
                    number_item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                    & ~Qt.ItemFlag.ItemIsSelectable
                )
                number_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.table.setItem(
                    row_index,
                    0,
                    number_item
                )

                for value_index, value in enumerate(
                    record
                ):
                    self.table.setItem(
                        row_index,
                        value_index + 1,
                        self.create_number_item(
                            value
                        )
                    )

        finally:
            self.loading_table = False

        self.update_headers()
        self.update_compatibility_label()
        self.update_calibration_source_label()
        self.update_window_title()

    def create_number_item(self, value):
        number = float(value)
        item = QTableWidgetItem(
            format_number(number, 7)
        )
        item.setData(
            Qt.ItemDataRole.UserRole,
            number
        )
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        return item

    def number_from_item(self, item):
        """Liest den exakten Originalwert oder einen bearbeiteten Zelltext."""

        if item is None:
            raise ValueError(
                self.language.text("data.error.empty_cell")
            )

        stored_value = item.data(
            Qt.ItemDataRole.UserRole
        )

        if stored_value is not None:
            return float(stored_value)

        return float(item.text().strip())

    def insert_record(self, values=None):
        if values is None:
            values = [
                0.0
                for _ in self.document["columns"]
            ]

        if len(values) != len(self.document["columns"]):
            raise ValueError(
                self.language.text("data.error.invalid_record_length")
            )

        row = self.table.rowCount()
        self.table.insertRow(
            row
        )

        number_item = QTableWidgetItem(
            str(row + 1)
        )
        number_item.setFlags(
            number_item.flags()
            & ~Qt.ItemFlag.ItemIsEditable
            & ~Qt.ItemFlag.ItemIsSelectable
        )
        number_item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.table.setItem(
            row,
            0,
            number_item
        )

        for value_index, value in enumerate(
            values
        ):
            self.table.setItem(
                row,
                value_index + 1,
                self.create_number_item(
                    value
                )
            )

    def add_row(self):
        self.loading_table = True

        try:
            self.insert_record()
        finally:
            self.loading_table = False

        last_row = self.table.rowCount() - 1
        self.table.setCurrentCell(
            last_row,
            1
        )
        self.table.scrollToBottom()
        self.set_modified(
            True
        )
        self.update_headers()
        self.record_edit_history()

    def delete_selected_rows(self):
        rows = sorted(
            {
                index.row()
                for index in self.table.selectedIndexes()
            },
            reverse=True
        )

        if not rows:
            return

        confirmation = QMessageBox.question(
            self,
            self.language.text("data.delete.title"),
            self.language.text(
                "data.delete.question",
                count=len(rows),
                data_label=self.data_label
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        for row in rows:
            self.table.removeRow(
                row
            )

        self.update_row_numbers()
        self.set_modified(
            True
        )
        self.update_headers()
        self.record_edit_history()

    def update_row_numbers(self):
        for row in range(
            self.table.rowCount()
        ):
            item = self.table.item(
                row,
                0
            )

            if item is not None:
                item.setText(
                    str(row + 1)
                )

    def table_item_changed(self, item):
        if self.loading_table:
            return

        if item.column() == 0:
            return

        # Nach einer echten Benutzereingabe gilt der neue Zelltext. Der beim
        # Laden hinterlegte, ungerundete Originalwert darf dann nicht mehr
        # verwendet werden.
        if item.data(Qt.ItemDataRole.UserRole) is not None:
            self.table.blockSignals(True)

            try:
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    None
                )

            finally:
                self.table.blockSignals(False)

        self.set_modified(
            True
        )
        self.update_headers()
        self.record_edit_history()

    def show_header_colors_information(self):
        """Erläutert Datentypen und Warnfarben der Spaltenköpfe."""

        QMessageBox.information(
            self,
            self.language.text("data.editor.header_colors_info_title"),
            self.language.text("data.editor.header_colors_info_text"),
        )

    def parse_import_number(self, text):
        cleaned_text = str(text).strip()

        if not cleaned_text:
            raise ValueError(
                self.language.text("data.error.empty_import_value")
            )

        if "," in cleaned_text and "." not in cleaned_text:
            cleaned_text = cleaned_text.replace(
                ",",
                "."
            )

        try:
            return float(
                cleaned_text
            )

        except ValueError as error:
            raise ValueError(
                self.language.text(
                    "data.error.invalid_number",
                    value=text
                )
            ) from error

    def detect_csv_dialect(self, text):
        try:
            return csv.Sniffer().sniff(
                text,
                delimiters=";,\t"
            )
        except csv.Error:
            return csv.excel

    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.language.text("data.csv.open_title"),
            "",
            self.language.text("data.csv.filter")
        )

        if not file_path:
            return

        try:
            with open(
                file_path,
                mode="r",
                encoding="utf-8-sig",
                newline=""
            ) as csv_file:
                text = csv_file.read()

        except OSError as error:
            QMessageBox.critical(
                self,
                self.language.text("data.csv.error_title"),
                str(error)
            )
            return

        try:
            dialect = self.detect_csv_dialect(
                text
            )
            reader = csv.reader(
                io.StringIO(text),
                dialect
            )

            raw_rows = [
                row
                for row in reader
                if any(cell.strip() for cell in row)
            ]

            if not raw_rows:
                raise ValueError(
                    self.language.text("data.csv.no_data")
                )

            expected_columns = len(
                self.document["columns"]
            )

            first_row_is_header = False

            try:
                [
                    self.parse_import_number(value)
                    for value in raw_rows[0]
                ]
            except ValueError:
                first_row_is_header = True

            if first_row_is_header:
                raw_rows = raw_rows[1:]

            imported_records = []

            for row_number, raw_row in enumerate(
                raw_rows,
                start=2 if first_row_is_header else 1
            ):
                if len(raw_row) == expected_columns + 1:
                    raw_row = raw_row[1:]

                if len(raw_row) != expected_columns:
                    raise ValueError(
                        self.language.text(
                            "data.csv.invalid_column_count",
                            row=row_number,
                            actual=len(raw_row),
                            expected=expected_columns
                        )
                    )

                imported_records.append(
                    [
                        self.parse_import_number(value)
                        for value in raw_row
                    ]
                )

        except ValueError as error:
            QMessageBox.warning(
                self,
                self.language.text("data.csv.error_title"),
                str(error)
            )
            return

        self.loading_table = True

        try:
            self.table.setRowCount(
                0
            )

            for record in imported_records:
                self.insert_record(
                    record
                )

        finally:
            self.loading_table = False

        self.update_row_numbers()
        self.automatic_scaling_status_label.setVisible(False)
        self.update_headers()
        self.set_modified(
            True
        )
        self.record_edit_history()

    def copy_selection_to_clipboard(self):
        """Kopiert Datenzellen als TSV; die sichtbare Nr.-Spalte entfällt."""

        selected_ranges = self.table.selectedRanges()

        if not selected_ranges:
            current_item = self.table.currentItem()

            if current_item is None or current_item.column() == 0:
                return

            QApplication.clipboard().setText(
                current_item.text()
            )
            return

        blocks = []

        for selected_range in selected_ranges:
            left_column = max(
                1,
                selected_range.leftColumn()
            )

            if left_column > selected_range.rightColumn():
                continue

            rows = []

            for row in range(
                selected_range.topRow(),
                selected_range.bottomRow() + 1
            ):
                values = []

                for column in range(
                    left_column,
                    selected_range.rightColumn() + 1
                ):
                    item = self.table.item(
                        row,
                        column
                    )
                    values.append(
                        item.text()
                        if item is not None
                        else ""
                    )

                rows.append(
                    "\t".join(values)
                )

            blocks.append(
                "\n".join(rows)
            )

        if blocks:
            QApplication.clipboard().setText(
                "\n".join(blocks)
            )

    def clear_selected_cells(self):
        """Leert markierte Datenzellen, verändert aber nie die Nr.-Spalte."""

        selected_items = [
            item
            for item in self.table.selectedItems()
            if item.column() > 0
        ]

        if not selected_items:
            return

        self.loading_table = True

        try:
            for item in selected_items:
                item.setText("")
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    None
                )
        finally:
            self.loading_table = False

        self.set_modified(True)
        self.update_headers()
        self.record_edit_history()

    def cut_selection_to_clipboard(self):
        """Kopiert die Auswahl ohne Nr.-Spalte und leert ihre Datenzellen."""

        self.copy_selection_to_clipboard()
        self.clear_selected_cells()

    def paste_from_clipboard(self):
        clipboard_text = QApplication.clipboard().text()

        if not clipboard_text.strip():
            QMessageBox.information(
                self,
                self.language.text("data.paste.title"),
                self.language.text("data.paste.empty")
            )
            return

        raw_rows = [
            row.split("\t")
            for row in clipboard_text.replace(
                "\r\n",
                "\n"
            ).replace(
                "\r",
                "\n"
            ).split("\n")
            if row.strip()
        ]

        if not raw_rows:
            return

        start_row = max(
            0,
            self.table.currentRow()
        )
        start_column = self.table.currentColumn()

        if start_column < 1:
            start_column = 1

        maximum_data_column = self.table.columnCount() - 1

        try:
            parsed_rows = []

            for raw_row in raw_rows:
                target_row = start_row + len(parsed_rows)
                last_target_column = (
                    start_column + len(raw_row) - 1
                )

                if last_target_column > maximum_data_column:
                    raise ValueError(
                        self.language.text("data.paste.too_many_columns")
                    )

                if (
                    target_row >= self.table.rowCount()
                    and (
                        start_column != 1
                        or len(raw_row) != maximum_data_column
                    )
                ):
                    raise ValueError(
                        self.language.text(
                            "data.paste.incomplete_new_record",
                            actual=len(raw_row),
                            expected=maximum_data_column,
                        )
                    )

                parsed_rows.append(
                    [
                        self.parse_import_number(raw_value)
                        for raw_value in raw_row
                    ]
                )

        except ValueError as error:
            QMessageBox.warning(
                self,
                self.language.text("data.paste.error_title"),
                str(error)
            )
            return

        self.loading_table = True

        try:
            for row_offset, parsed_row in enumerate(parsed_rows):
                target_row = start_row + row_offset

                while target_row >= self.table.rowCount():
                    self.insert_record()

                for column_offset, number_value in enumerate(parsed_row):
                    target_column = start_column + column_offset

                    self.table.setItem(
                        target_row,
                        target_column,
                        self.create_number_item(
                            number_value
                        )
                    )

        finally:
            self.loading_table = False

        self.update_row_numbers()
        self.update_headers()
        self.set_modified(
            True
        )
        self.record_edit_history()

    def read_number(self, row, column):
        item = self.table.item(
            row,
            column
        )

        text = "" if item is None else item.text().strip()

        try:
            return self.number_from_item(item)

        except ValueError as error:
            raise ValueError(
                self.language.text(
                    "data.error.cell_invalid_number",
                    row=row + 1,
                    column=column + 1
                )
            ) from error

    def collect_document(self):
        records = []

        for row in range(
            self.table.rowCount()
        ):
            values = []

            for column in range(
                1,
                self.table.columnCount()
            ):
                values.append(
                    self.read_number(
                        row,
                        column
                    )
                )

            records.append(
                values
            )

        document = copy.deepcopy(
            self.document
        )
        document["records"] = records

        TrainingDataIO.validate(
            document,
            self.language.text
        )

        return document

    def ask_integer(self, title, label, value, minimum, maximum, step=1):
        """Zahleneingabe mit sprachabhängigen Standardschaltflächen."""

        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.IntInput)
        dialog.setIntRange(minimum, maximum)
        dialog.setIntStep(step)
        dialog.setIntValue(value)
        dialog.setOkButtonText(self.language.text("common.ok"))
        dialog.setCancelButtonText(self.language.text("common.cancel"))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return value, False

        return dialog.intValue(), True

    def ask_choice(self, title, label, choices, current=0):
        """Listenauswahl mit sprachabhängigen Standardschaltflächen."""

        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setComboBoxItems(choices)
        dialog.setComboBoxEditable(False)
        dialog.setTextValue(choices[current] if choices else "")
        dialog.setOkButtonText(self.language.text("common.ok"))
        dialog.setCancelButtonText(self.language.text("common.cancel"))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return "", False

        return dialog.textValue(), True

    def choose_structure_change(self, role, difference):
        count = abs(
            difference
        )
        role_text = (
            self.language.text("data.structure.input_column")
            if role == "input"
            else self.language.text("data.structure.output_column")
        )

        if count != 1:
            role_text = self.language.text(
                "data.structure.columns_plural",
                role=role_text
            )

        if difference > 0:
            choices = [
                self.language.text(
                    "data.structure.add_end",
                    count=count,
                    role=role_text
                ),
                self.language.text(
                    "data.structure.add_start",
                    count=count,
                    role=role_text
                )
            ]
        else:
            choices = [
                self.language.text(
                    "data.structure.remove_end",
                    count=count,
                    role=role_text
                ),
                self.language.text(
                    "data.structure.remove_start",
                    count=count,
                    role=role_text
                )
            ]

        choice, accepted = self.ask_choice(
            self.language.text(
                "data.editor.adjust_structure_title",
                data_label=self.data_label
            ),
            self.language.text("data.structure.location_question"),
            choices,
            0
        )

        if not accepted:
            return None

        return (
            "end"
            if choice == choices[0]
            else "start"
        )

    def resize_role_columns(self, role, new_count, side):
        current_indices = [
            index
            for index, column in enumerate(
                self.document["columns"]
            )
            if column["role"] == role
        ]
        current_count = len(
            current_indices
        )
        difference = new_count - current_count

        if difference == 0:
            return

        if difference > 0:
            for addition_index in range(difference):
                role_number = current_count + addition_index + 1
                new_column = {
                    "name": (
                        f"Input {role_number}"
                        if role == "input"
                        else f"Output {role_number}"
                    ),
                    "unit": "",
                    "role": role,
                    "data_type": "analog",
                    "mapped_neuron_id": None,
                    "mapped_neuron_name": None,
                    "calibration": TrainingDataIO.default_calibration()
                }

                if side == "start":
                    insert_index = (
                        current_indices[0]
                        if current_indices
                        else 0
                    )
                else:
                    if current_indices:
                        insert_index = current_indices[-1] + 1 + addition_index
                    elif role == "input":
                        insert_index = 0
                    else:
                        insert_index = len(
                            self.document["columns"]
                        )

                self.document["columns"].insert(
                    insert_index,
                    new_column
                )

                for record in self.document["records"]:
                    record.insert(
                        insert_index,
                        0.0
                    )

        else:
            remove_count = abs(
                difference
            )
            indices_to_remove = (
                current_indices[-remove_count:]
                if side == "end"
                else current_indices[:remove_count]
            )

            for remove_index in sorted(
                indices_to_remove,
                reverse=True
            ):
                del self.document["columns"][remove_index]

                for record in self.document["records"]:
                    del record[remove_index]

        self.remove_invalid_input_array()

    def adjust_structure_to_network(self):
        target_counts = {
            "input": len(
                self.network.get_input_neurons()
            ),
            "output": len(
                self.network.get_output_neurons()
            )
        }

        if target_counts["input"] < 1 or target_counts["output"] < 1:
            QMessageBox.warning(
                self,
                self.language.text(
                    "data.editor.adjust_structure_title",
                    data_label=self.data_label
                ),
                self.language.text("data.structure.network_minimum")
            )
            return

        working_document = copy.deepcopy(
            self.document
        )

        for role in (
            "input",
            "output"
        ):
            current_count = sum(
                1
                for column in working_document["columns"]
                if column["role"] == role
            )
            difference = target_counts[role] - current_count

            if difference == 0:
                continue

            side = self.choose_structure_change(
                role,
                difference
            )

            if side is None:
                return

            self.document = working_document
            self.resize_role_columns(
                role,
                target_counts[role],
                side
            )
            working_document = copy.deepcopy(
                self.document
            )

        self.document = working_document
        self.load_document_into_table()
        self.set_modified(
            True
        )
        self.record_edit_history()

    def copy_from_training_data(self):
        """Kopiert ausgewählte Trainingszeilen in die Testdatentabelle."""

        if not self.confirm_unsaved_changes():
            return

        if not isinstance(self.training_document, dict):
            QMessageBox.information(
                self,
                self.language.text("data.message.no_training.title"),
                self.language.text("data.message.no_training.message")
            )
            return

        training_records = self.training_document.get("records", [])

        if len(training_records) < 2:
            QMessageBox.information(
                self,
                self.language.text("data.message.too_few_training.title"),
                self.language.text("data.message.too_few_training.message")
            )
            return

        dialog = TestDataSplitDialog(
            self.training_document,
            self.training_file_path,
            language_manager=self.language,
            parent=self
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_indices = set(dialog.selected_indices)

        if not selected_indices:
            return

        test_count = len(selected_indices)
        warning_text = (
            self.language.text(
                "data.copy_test.confirm_message",
                test_count=test_count,
                training_count=len(training_records)
            )
        )

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle(
            self.language.text("data.copy_test.confirm_title")
        )
        message_box.setText(warning_text)
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.No)
        message_box.button(QMessageBox.StandardButton.Yes).setText(
            self.language.text("common.yes")
        )
        message_box.button(QMessageBox.StandardButton.No).setText(
            self.language.text("common.no")
        )
        answer = message_box.exec()

        if answer != QMessageBox.StandardButton.Yes:
            return

        test_records = [
            copy.deepcopy(record)
            for index, record in enumerate(training_records)
            if index in selected_indices
        ]
        test_columns = copy.deepcopy(
            self.training_document["columns"]
        )

        for column in test_columns:
            calibration = TrainingDataIO.normalize_calibration(
                column.get("calibration")
            )
            column["calibration"] = copy.deepcopy(calibration)
            column["calibration_source"] = "training_data"
            column["training_calibration"] = copy.deepcopy(calibration)

        self.document = {
            "version": TrainingDataIO.FILE_VERSION,
            "name": self.language.text("data.copy_test.document_name"),
            "columns": test_columns,
            "records": test_records
        }
        self.current_file_path = None

        self.load_document_into_table()
        self.set_modified(True)
        self.record_edit_history()

        QMessageBox.information(
            self,
            self.language.text("data.copy_test.done_title"),
            self.language.text(
                "data.copy_test.done_message",
                test_count=test_count,
                training_count=len(training_records)
            )
        )

    def new_document(self):
        if not self.confirm_unsaved_changes():
            return

        if self.data_extension == ".nntest":
            accepted, document = self.create_test_document_from_training(
                self.training_document,
                self,
                self.language
            )

            if not accepted:
                return

            if document is not None:
                self.document = document
                self.current_file_path = None
                self.load_document_into_table()
                self.set_modified(False)
                self.reset_edit_history()
                return

        input_count, accepted = self.ask_integer(
            self.language.text(
                "data.editor.new_title",
                data_label=self.data_label
            ),
            self.language.text("data.editor.input_count"),
            max(
                1,
                len(self.network.get_input_neurons())
            ),
            1,
            1000,
            1
        )

        if not accepted:
            return

        output_count, accepted = self.ask_integer(
            self.language.text(
                "data.editor.new_title",
                data_label=self.data_label
            ),
            self.language.text("data.editor.output_count"),
            max(
                1,
                len(self.network.get_output_neurons())
            ),
            1,
            1000,
            1
        )

        if not accepted:
            return

        self.document = TrainingDataIO.create_empty_document(
            input_count,
            output_count,
            self.language.text(
                "data.editor.new_document",
                data_label=self.data_label
            )
        )
        self.current_file_path = None
        self.load_document_into_table()
        self.set_modified(
            False
        )
        self.reset_edit_history()

    def open_document(self):
        if not self.confirm_unsaved_changes():
            return

        if self.data_extension == ".nntest":
            file_filter = (
                self.language.text("data.file_filter.test_open")
            )
        else:
            file_filter = (
                self.language.text("data.file_filter.training")
            )

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.language.text(
                "data.editor.open_title",
                data_label=self.data_label
            ),
            self.current_data_directory(),
            file_filter
        )

        if not file_path:
            return

        try:
            document = TrainingDataIO.load(
                file_path,
                self.language.text
            )

        except (
            OSError,
            ValueError,
            TypeError
        ) as error:
            QMessageBox.critical(
                self,
                self.language.text("data.message.open_error_title"),
                str(error)
            )
            return

        self.document = document
        self.current_file_path = file_path
        self.load_document_into_table()
        self.set_modified(
            False
        )
        self.reset_edit_history()

    def save_document(self):
        current_extension = os.path.splitext(
            str(self.current_file_path or "")
        )[1].lower()

        if (
            self.current_file_path is None
            or (
                self.data_extension == ".nntest"
                and current_extension != ".nntest"
            )
        ):
            return self.save_document_as()

        return self.write_document(
            self.current_file_path
        )

    def save_document_as(self):
        if self.data_extension == ".nntest":
            file_filter = (
                self.language.text("data.file_filter.test_save")
            )

            current_extension = os.path.splitext(
                str(self.current_file_path or "")
            )[1].lower()
            start_directory = (
                self.current_data_directory()
                if current_extension == ".nntest"
                else self.default_directory
            )
        else:
            file_filter = (
                self.language.text("data.file_filter.training")
            )
            start_directory = self.current_data_directory()

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.language.text(
                "data.editor.save_as_title",
                data_label=self.data_label
            ),
            start_directory,
            file_filter
        )

        if not file_path:
            return False

        if not file_path.lower().endswith(
            (
                self.data_extension,
                ".json"
            )
        ):
            file_path += self.data_extension

        return self.write_document(
            file_path
        )

    def current_data_directory(self):
        if self.current_file_path:
            return os.path.dirname(
                os.path.abspath(
                    str(self.current_file_path)
                )
            )

        return self.default_directory

    def write_document(self, file_path):
        try:
            document = self.collect_document()
            stored_document = copy.deepcopy(document)
            if self.temporary_mappings:
                for column in stored_document.get("columns", []):
                    column["mapped_neuron_id"] = None
                    column["mapped_neuron_name"] = None
            TrainingDataIO.save(
                file_path,
                stored_document,
                self.language.text
            )

        except (
            OSError,
            ValueError,
            TypeError
        ) as error:
            QMessageBox.critical(
                self,
                self.language.text("data.message.save_error_title"),
                str(error)
            )
            return False

        self.document = document
        self.current_file_path = file_path
        self.set_modified(
            False
        )
        self.mark_edit_history_saved()

        return True

    def confirm_unsaved_changes(self):
        if not self.modified:
            return True

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle(
            self.language.text(
                "data.unsaved.title",
                data_label=self.data_label
            )
        )
        message_box.setText(
            self.language.text(
                "data.unsaved.message",
                data_label=self.data_label
            )
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Save)
        message_box.button(QMessageBox.StandardButton.Save).setText(
            self.language.text("common.save")
        )
        message_box.button(QMessageBox.StandardButton.Discard).setText(
            self.language.text("common.discard")
        )
        message_box.button(QMessageBox.StandardButton.Cancel).setText(
            self.language.text("common.cancel")
        )
        result = message_box.exec()

        if result == QMessageBox.StandardButton.Save:
            return self.save_document()

        if result == QMessageBox.StandardButton.Discard:
            return True

        return False

    def accept(self):
        try:
            self.document = self.collect_document()

        except ValueError as error:
            QMessageBox.warning(
                self,
                self.language.text(
                    "data.message.invalid_data_title",
                    data_label=self.data_label
                ),
                str(error)
            )
            return

        super().accept()

    def reject(self):
        if not self.confirm_unsaved_changes():
            return

        super().reject()

    def closeEvent(self, event):
        if not self.confirm_unsaved_changes():
            event.ignore()
            return

        event.accept()
