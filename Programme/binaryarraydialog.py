# -------------------------------------------------------------------------------------------------
# Datei: binaryarraydialog.py
# Zweck: Definiert und visualisiert zweidimensionale binäre Eingabe-Arrays.
# Letzte Änderung: 05.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from language import LanguageManager
from numberformat import format_number


class BinaryArrayPreview(QGroupBox):
    """Kompakte, nicht editierbare Vorschau eines binären Eingaberasters."""

    def __init__(self, language, color_settings=None, parent=None):
        super().__init__(language.text("data.array.preview"), parent)
        self.language = language
        colors = color_settings or {}
        self.active_color = colors.get("binary_array_on", "#242424")
        self.inactive_color = colors.get("binary_array_off", "#ffffff")
        self.grid = QGridLayout(self)
        self.grid.setSpacing(5)
        self.cells = []

    def rebuild(self, rows, columns):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.cells = []
        for row in range(rows):
            row_cells = []
            for column in range(columns):
                cell = QLabel()
                cell.setFixedSize(42, 42)
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid.addWidget(cell, row, column)
                row_cells.append(cell)
            self.cells.append(row_cells)
        self.set_values([0.0] * (rows * columns))

    def set_values(self, values):
        flat_cells = [cell for row in self.cells for cell in row]
        for cell, value in zip(flat_cells, values):
            active = float(value) > 0.5
            cell.setText("")
            cell.setStyleSheet(
                "QLabel { border: 1px solid #aab1b6; border-radius: 3px; "
                f"background: {self.active_color if active else self.inactive_color}; "
                f"color: {self.inactive_color if active else self.active_color}; }}"
            )


class BinaryInputArrayDialog(QDialog):
    """Definiert die zweidimensionale Anordnung binärer Input-Spalten."""

    def __init__(
        self,
        document,
        language_manager=None,
        color_settings=None,
        parent=None,
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.document = copy.deepcopy(document)
        self.color_settings = dict(color_settings or {})
        self.columns = self.document.get("columns", [])
        self.records = self.document.get("records", [])
        self.binary_inputs = [
            (index, column)
            for index, column in enumerate(self.columns)
            if column.get("role") == "input"
            and column.get("data_type", "analog") == "binary"
        ]
        self.result_definition = None
        self.assignment_combos = []
        self.record_index = 0
        self._assignment_swap_active = False
        self._dimension_sync_active = False

        self.setWindowTitle(self.language.text("data.array.title"))
        self.setModal(True)
        self.resize(760, 470)
        layout = QVBoxLayout(self)

        intro = QLabel(self.language.text("data.array.introduction"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        dimensions = QHBoxLayout()
        dimensions.addWidget(QLabel(self.language.text("data.array.rows")))
        self.rows_spin = QSpinBox()
        dimensions.addWidget(self.rows_spin)
        dimensions.addSpacing(18)
        dimensions.addWidget(QLabel(self.language.text("data.array.columns")))
        self.columns_spin = QSpinBox()
        dimensions.addWidget(self.columns_spin)
        dimensions.addStretch(1)
        layout.addLayout(dimensions)

        count = len(self.binary_inputs)
        self.rows_spin.setRange(1, max(1, count))
        self.columns_spin.setRange(1, max(1, count))
        rows, columns = self.default_dimensions(count)
        existing = self.document.get("input_array")
        if isinstance(existing, dict):
            rows = int(existing.get("rows", rows))
            columns = int(existing.get("columns", columns))
        self.rows_spin.setValue(rows)
        self.columns_spin.setValue(columns)

        content = QHBoxLayout()
        self.assignment_group = QGroupBox(
            self.language.text("data.array.assignment")
        )
        self.assignment_layout = QGridLayout(self.assignment_group)
        self.assignment_layout.setVerticalSpacing(6)
        self.assignment_layout.setHorizontalSpacing(8)
        self.assignment_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content.addWidget(
            self.assignment_group, 1, Qt.AlignmentFlag.AlignTop
        )

        preview_column = QVBoxLayout()
        self.preview = BinaryArrayPreview(
            self.language,
            self.color_settings,
        )
        preview_column.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        navigation = QHBoxLayout()
        self.previous_button = QPushButton(self.language.text("data.array.previous"))
        self.next_button = QPushButton(self.language.text("data.array.next"))
        self.record_label = QLabel()
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.record_label, 1, Qt.AlignmentFlag.AlignCenter)
        navigation.addWidget(self.next_button)
        preview_column.addLayout(navigation)
        self.target_label = QLabel()
        self.target_label.setWordWrap(True)
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_label.setStyleSheet(
            "QLabel { background: #eef5fb; border: 1px solid #9db8cc; "
            "border-radius: 4px; padding: 5px; }"
        )
        preview_column.addWidget(self.target_label)
        preview_column.addStretch(1)
        content.addLayout(preview_column, 1)
        layout.addLayout(content)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self.language.text("data.array.apply")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self.language.text("common.cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.rows_spin.valueChanged.connect(self.rows_changed)
        self.columns_spin.valueChanged.connect(self.columns_changed)
        self.previous_button.clicked.connect(lambda: self.change_record(-1))
        self.next_button.clicked.connect(lambda: self.change_record(1))
        self.rebuild_assignments()

    def nearest_divisor(self, value):
        count = len(self.binary_inputs)
        divisors = [number for number in range(1, count + 1) if count % number == 0]
        return min(divisors, key=lambda number: (abs(number - value), number))

    def rows_changed(self, value):
        if self._dimension_sync_active:
            return
        self._dimension_sync_active = True
        rows = self.nearest_divisor(value)
        self.rows_spin.setValue(rows)
        self.columns_spin.setValue(len(self.binary_inputs) // rows)
        self._dimension_sync_active = False
        self.rebuild_assignments()

    def columns_changed(self, value):
        if self._dimension_sync_active:
            return
        self._dimension_sync_active = True
        columns = self.nearest_divisor(value)
        self.columns_spin.setValue(columns)
        self.rows_spin.setValue(len(self.binary_inputs) // columns)
        self._dimension_sync_active = False
        self.rebuild_assignments()

    @staticmethod
    def default_dimensions(count):
        if count < 1:
            return 1, 1
        columns = max(
            divisor
            for divisor in range(1, int(math.sqrt(count)) + 1)
            if count % divisor == 0
        )
        return count // columns, columns

    def existing_order(self):
        existing = self.document.get("input_array")
        if not isinstance(existing, dict):
            return [index for index, _column in self.binary_inputs]
        order = existing.get("column_indices")
        available = {index for index, _column in self.binary_inputs}
        if (
            isinstance(order, list)
            and len(order) == len(available)
            and set(order) == available
        ):
            return order
        return [index for index, _column in self.binary_inputs]

    def rebuild_assignments(self, *_args):
        previous = [combo.currentData() for combo in self.assignment_combos]
        if not previous:
            previous = self.existing_order()
        available_order = [index for index, _column in self.binary_inputs]
        desired_order = []
        for column_index in previous + available_order:
            if (
                column_index in available_order
                and column_index not in desired_order
            ):
                desired_order.append(column_index)
        while self.assignment_layout.count():
            item = self.assignment_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.assignment_combos = []
        rows = self.rows_spin.value()
        columns = self.columns_spin.value()
        for position in range(rows * columns):
            combo = QComboBox()
            for column_index, column in self.binary_inputs:
                combo.addItem(column.get("name", str(column_index + 1)), column_index)
            if position < len(desired_order):
                index = combo.findData(desired_order[position])
                combo.setCurrentIndex(max(0, index))
            combo._previous_data = combo.currentData()
            combo.currentIndexChanged.connect(
                lambda _index, changed_combo=combo:
                self.assignment_changed(changed_combo)
            )
            self.assignment_layout.addWidget(combo, position // columns, position % columns)
            self.assignment_combos.append(combo)
        self.preview.rebuild(rows, columns)
        self.update_preview()

    def assignment_changed(self, changed_combo):
        """Tauscht doppelt gewählte Eingänge automatisch miteinander."""

        if self._assignment_swap_active:
            return
        self._assignment_swap_active = True
        old_value = getattr(changed_combo, "_previous_data", None)
        new_value = changed_combo.currentData()
        for combo in self.assignment_combos:
            if combo is changed_combo or combo.currentData() != new_value:
                continue
            replacement_index = combo.findData(old_value)
            if replacement_index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(replacement_index)
                combo._previous_data = old_value
                combo.blockSignals(False)
            break
        changed_combo._previous_data = new_value
        self._assignment_swap_active = False
        self.update_preview()

    def update_preview(self, *_args):
        valid_size = len(self.assignment_combos) == len(self.binary_inputs)
        order = [combo.currentData() for combo in self.assignment_combos]
        unique = len(set(order)) == len(order)
        valid = bool(self.binary_inputs) and valid_size and unique
        self.status_label.setText(
            self.language.text(
                "data.array.valid" if valid else "data.array.invalid",
                count=len(self.binary_inputs)
            )
        )
        values = []
        record = self.records[self.record_index] if self.records else []
        for column_index in order:
            values.append(
                record[column_index]
                if isinstance(record, list) and column_index < len(record)
                else 0.0
            )
        self.preview.set_values(values)
        self.record_label.setText(
            self.language.text(
                "data.array.record",
                current=self.record_index + 1 if self.records else 0,
                total=len(self.records),
            )
        )
        self.update_target_label(record)
        self.previous_button.setEnabled(self.record_index > 0)
        self.next_button.setEnabled(self.record_index + 1 < len(self.records))

    def update_target_label(self, record):
        """Zeigt die Sollausgänge des gewählten Trainingsdatensatzes."""

        binary_outputs = []
        analog_outputs = []
        has_binary_output = False
        for column_index, column in enumerate(self.columns):
            if column.get("role") != "output":
                continue
            value = (
                record[column_index]
                if isinstance(record, list) and column_index < len(record)
                else 0.0
            )
            name = str(column.get("name", f"Output {column_index + 1}"))
            if column.get("data_type", "analog") == "binary":
                has_binary_output = True
                if float(value) > 0.5:
                    binary_outputs.append(
                        self.language.text("data.array.target_binary", name=name)
                    )
            else:
                unit = str(column.get("unit", "")).strip()
                analog_outputs.append(
                    self.language.text(
                        "data.array.target_analog",
                        name=name,
                        value=format_number(value, 7),
                        unit=(f" {unit}" if unit else ""),
                    )
                )
        values = binary_outputs + analog_outputs
        if not values and has_binary_output:
            values = [self.language.text("data.array.target_none")]
        self.target_label.setText(
            self.language.text(
                "data.array.target",
                values=", ".join(values) if values else "–",
            )
        )

    def change_record(self, difference):
        if not self.records:
            return
        self.record_index = max(
            0, min(len(self.records) - 1, self.record_index + difference)
        )
        self.update_preview()

    def accept(self):
        order = [combo.currentData() for combo in self.assignment_combos]
        if (
            not self.binary_inputs
            or len(order) != len(self.binary_inputs)
            or len(set(order)) != len(order)
        ):
            QMessageBox.warning(
                self,
                self.language.text("data.array.error.title"),
                self.language.text("data.array.invalid", count=len(self.binary_inputs)),
            )
            return
        self.result_definition = {
            "rows": self.rows_spin.value(),
            "columns": self.columns_spin.value(),
            "column_indices": order,
        }
        super().accept()
