# -------------------------------------------------------------------------------------------------
# Datei: networktestdialog.py
# Zweck: Testet ein trainiertes Netzwerk mit Trainings- oder Testdaten.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout
)

from neurontype import NeuronType
from numberformat import format_number
from trainingdataio import TrainingDataIO
from language import LanguageManager


class NetworkTestDialog(QDialog):
    """
    Berechnet alle übergebenen Datensätze mit dem aktuellen
    Zustand des Netzwerkes, ohne Gewichte oder Bias zu ändern.

    Angezeigt werden:
        - Eingangswerte
        - Sollwerte
        - Istwerte
        - Fehler je Output
        - mittlerer quadratischer Gesamtfehler
    """

    def __init__(
        self,
        network,
        records,
        input_columns,
        output_columns,
        parent=None,
        data_label=None,
        file_path=None,
        language_manager=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        self.network = network
        self.records = records
        self.input_columns = input_columns
        self.output_columns = output_columns
        self.data_label = str(
            data_label or self.t("test.data.training")
        ).strip() or self.t("test.data.generic")
        self.file_path = file_path

        self.setWindowTitle(
            self.t("test.title", data_label=self.data_label)
        )

        self.setModal(
            True
        )

        self.resize(
            720,
            520
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        self.main_layout.setSpacing(
            10
        )

        info_text = self.t("test.info", data_label=self.data_label)

        if self.file_path:
            info_text += "\n" + self.t("test.file", file_path=self.file_path)

        self.info_label = QLabel(
            info_text
        )

        self.info_label.setWordWrap(
            True
        )

        self.main_layout.addWidget(
            self.info_label
        )

        self.table = QTableWidget()
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(
            True
        )

        fixed_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )
        self.table.setFont(
            fixed_font
        )

        headers = [
            self.t("test.column.number")
        ]
        header_tooltips = [""]

        for mapping in self.input_columns:
            unit = mapping.get("unit", "")
            neuron_name = str(mapping["neuron"].name)
            headers.append(
                (
                    f"{neuron_name} [{unit}]"
                    if unit
                    else neuron_name
                )
            )
            header_tooltips.append(
                self.t(
                    "test.column.training_source",
                    column=mapping["column_name"],
                )
            )

        for mapping in self.output_columns:
            unit = mapping.get("unit", "")
            neuron_name = str(mapping["neuron"].name)
            output_name = (
                f"{neuron_name} [{unit}]"
                if unit
                else neuron_name
            )
            headers.extend(
                [
                    self.t("test.column.target", output=output_name),
                    self.t("test.column.actual", output=output_name),
                    self.t("test.column.error", output=output_name)
                ]
            )
            tooltip = self.t(
                "test.column.training_source",
                column=mapping["column_name"],
            )
            header_tooltips.extend([tooltip, tooltip, tooltip])

        self.table.setColumnCount(
            len(headers)
        )
        self.table.setHorizontalHeaderLabels(
            headers
        )
        for index, tooltip in enumerate(header_tooltips):
            header_item = self.table.horizontalHeaderItem(index)
            if header_item is not None and tooltip:
                header_item.setToolTip(tooltip)

        self.main_layout.addWidget(
            self.table,
            1
        )

        self.only_errors_checkbox = QCheckBox(
            self.t("test.filter.only_errors")
        )
        self.only_errors_checkbox.setVisible(
            any(
                mapping.get("data_type") == "binary"
                for mapping in self.output_columns
            )
        )
        self.only_errors_checkbox.toggled.connect(
            self.apply_error_filter
        )
        self.main_layout.addWidget(self.only_errors_checkbox)

        self.summary_label = QLabel()
        summary_font = self.summary_label.font()
        summary_font.setBold(
            True
        )
        self.summary_label.setFont(
            summary_font
        )
        self.summary_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.summary_label.setWordWrap(
            True
        )

        self.main_layout.addWidget(
            self.summary_label
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.t("common.close"))
        self.button_box.rejected.connect(
            self.reject
        )

        self.main_layout.addWidget(
            self.button_box
        )

        self.calculate_results()

    def apply_error_filter(self, checked=None):
        """Blendet bei Bedarf alle binär korrekt klassifizierten Zeilen aus."""

        only_errors = (
            self.only_errors_checkbox.isChecked()
            if checked is None
            else bool(checked)
        )
        for row_index, has_error in enumerate(
            getattr(self, "row_classification_errors", [])
        ):
            self.table.setRowHidden(
                row_index,
                only_errors and not has_error,
            )

    @staticmethod
    def prepare_document(
        network,
        document,
        data_label=None,
        translator=None
    ):
        """
        Prüft Datensätze und Zuordnungen gegen das aktuelle
        Netzwerk und liefert die vorbereiteten Testdaten zurück.
        """

        def text(key, default, **values):
            if callable(translator):
                return translator(key, **values)
            return default.format(**values)

        data_label = str(
            data_label or text(
                "test.data.test",
                "Test data"
            )
        ).strip() or text(
            "test.data.generic",
            "data"
        )

        if not isinstance(document, dict):
            raise ValueError(text("test.validation.invalid_data", "Es wurden keine gültigen {data_label} übergeben.", data_label=data_label))

        prepared_document = TrainingDataIO.prepare_document(
            copy.deepcopy(document)
        )
        TrainingDataIO.validate(prepared_document, translator=translator)

        columns = prepared_document.get(
            "columns"
        )
        records = prepared_document.get(
            "records"
        )

        if not columns:
            raise ValueError(text("test.validation.no_columns", "Die {data_label} enthalten keine Spalten.", data_label=data_label))

        if not records:
            raise ValueError(text("test.validation.no_records", "Die {data_label} enthalten keine Datensätze.", data_label=data_label))

        input_mappings = []
        output_mappings = []
        used_neuron_ids = set()

        for column_index, column in enumerate(columns):
            role = column.get(
                "role"
            )
            neuron_id = column.get(
                "mapped_neuron_id"
            )
            column_name = str(
                column.get(
                    "name",
                    text("test.column.fallback", "Spalte {column}", column=column_index + 1)
                )
            )

            if role not in ("input", "output"):
                raise ValueError(text("test.validation.invalid_role", "Spalte '{column}' besitzt keinen gültigen Typ.", column=column_name))

            if neuron_id is None:
                raise ValueError(text("test.validation.unassigned", "Spalte '{column}' ist keinem Neuron zugeordnet.", column=column_name))

            neuron = network.get_neuron(
                neuron_id
            )

            if neuron is None:
                raise ValueError(text("test.validation.neuron_missing", "Das der Spalte '{column}' zugeordnete Neuron ist im aktuellen Netzwerk nicht vorhanden.", column=column_name))

            expected_type = (
                NeuronType.INPUT
                if role == "input"
                else NeuronType.OUTPUT
            )

            if neuron.neuron_type != expected_type:
                raise ValueError(text("test.validation.wrong_type", "Spalte '{column}' ist einem Neuron mit falschem Typ zugeordnet.", column=column_name))

            if neuron.id in used_neuron_ids:
                raise ValueError(text("test.validation.duplicate", "Neuron '{neuron}' ist mehreren Spalten zugeordnet.", neuron=neuron.name))

            used_neuron_ids.add(
                neuron.id
            )
            mapping = {
                "column_index": column_index,
                "column_name": column_name,
                "unit": str(column.get("unit", "")).strip(),
                "data_type": column.get("data_type", "analog"),
                "neuron": neuron,
                "calibration": TrainingDataIO.normalize_calibration(
                    column.get("calibration")
                )
            }

            if role == "input":
                input_mappings.append(
                    mapping
                )
            else:
                output_mappings.append(
                    mapping
                )

        mapped_input_ids = {
            mapping["neuron"].id
            for mapping in input_mappings
        }
        network_input_ids = {
            neuron.id
            for neuron in network.get_input_neurons()
        }
        mapped_output_ids = {
            mapping["neuron"].id
            for mapping in output_mappings
        }
        network_output_ids = {
            neuron.id
            for neuron in network.get_output_neurons()
        }

        if mapped_input_ids != network_input_ids:
            raise ValueError(text("test.validation.inputs_incomplete", "Nicht alle Input-Neuronen sind genau einer {data_label}spalte zugeordnet.", data_label=data_label))

        if mapped_output_ids != network_output_ids:
            raise ValueError(text("test.validation.outputs_incomplete", "Nicht alle Output-Neuronen sind genau einer {data_label}spalte zugeordnet.", data_label=data_label))

        numeric_records = []

        for record_index, record in enumerate(records, start=1):
            if not isinstance(record, list) or len(record) != len(columns):
                raise ValueError(text("test.validation.record_length", "Datensatz {record} besitzt nicht die erwartete Anzahl von Werten.", record=record_index))

            try:
                numeric_records.append(
                    [float(value) for value in record]
                )
            except (TypeError, ValueError) as error:
                raise ValueError(text("test.validation.record_number", "Datensatz {record} enthält einen ungültigen Zahlenwert.", record=record_index)) from error

        return (
            numeric_records,
            input_mappings,
            output_mappings
        )

    def apply_record(
        self,
        record
    ):
        """
        Legt die Eingangswerte des Datensatzes an und
        liefert die Sollwerte der zugeordneten Outputs.
        """

        for mapping in self.input_columns:
            raw_value = record[mapping["column_index"]]
            mapping["neuron"].input_value = TrainingDataIO.scale_value(
                raw_value,
                mapping["calibration"],
                translator=self.t
            )
            mapping["neuron"].set_external_input_value(
                raw_value,
                mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )
            mapping["neuron"].update()

        targets = {}
        for mapping in self.output_columns:
            raw_target = record[mapping["column_index"]]
            targets[mapping["neuron"].id] = TrainingDataIO.scale_value(
                raw_target,
                mapping["calibration"],
                translator=self.t
            )
            mapping["neuron"].set_external_output_values(
                target_value=raw_target,
                is_raw=mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )
        return targets

    def update_external_output_values(self, record):
        for mapping in self.output_columns:
            neuron = mapping["neuron"]
            raw_output = TrainingDataIO.unscale_value(
                neuron.output_value,
                mapping["calibration"],
                translator=self.t
            )
            neuron.set_external_output_values(
                actual_value=raw_output,
                target_value=record[mapping["column_index"]],
                is_raw=mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )

    @staticmethod
    def create_number_item(
        value,
        binary=False,
        translator=None
    ):
        """
        Erzeugt eine rechtsbündige Tabellenzelle
        mit kompakter Zahlendarstellung.
        """

        text = format_number(value, 7)
        if binary:
            state = float(value) > 0.5
            state_text = (
                translator("binary.on" if state else "binary.off")
                if callable(translator)
                else ("Ein" if state else "Aus")
            )
            text += ("  ● " if state else "  ○ ") + state_text
        item = QTableWidgetItem(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        return item

    def calculate_results(self):
        """
        Berechnet alle Datensätze ausschließlich mit
        einem Forward Pass und füllt die Ergebnistabelle.
        """

        self.table.setRowCount(
            len(self.records)
        )

        squared_error_sum = 0.0
        absolute_error_sum = 0.0
        maximum_absolute_error = 0.0
        output_value_count = 0
        classification_correct_count = 0
        classification_value_count = 0
        classification_record_correct_count = 0
        classification_record_error_count = 0
        self.row_classification_errors = []

        for row_index, record in enumerate(
            self.records
        ):
            self.network.reset_runtime_values()

            target_values = self.apply_record(
                record
            )

            self.network.forward_pass()
            self.update_external_output_values(record)

            number_item = QTableWidgetItem(
                str(
                    row_index + 1
                )
            )
            number_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self.table.setItem(
                row_index,
                0,
                number_item
            )

            column_index = 1
            row_has_binary_output = False
            row_binary_correct = True

            for mapping in self.input_columns:
                self.table.setItem(
                    row_index,
                    column_index,
                    self.create_number_item(
                        record[
                            mapping["column_index"]
                        ]
                    )
                )
                column_index += 1

            for mapping in self.output_columns:
                neuron = mapping["neuron"]
                target_value = record[
                    mapping["column_index"]
                ]
                actual_value = TrainingDataIO.unscale_value(
                    neuron.output_value,
                    mapping["calibration"],
                    translator=self.t
                )
                error_value = (
                    target_value
                    - actual_value
                )

                squared_error_sum += (
                    error_value
                    * error_value
                )
                absolute_error = abs(
                    error_value
                )
                absolute_error_sum += absolute_error
                maximum_absolute_error = max(
                    maximum_absolute_error,
                    absolute_error
                )
                output_value_count += 1

                is_binary = mapping.get("data_type") == "binary"
                binary_mismatch = False
                if is_binary:
                    row_has_binary_output = True
                    predicted_value = (
                        1.0
                        if actual_value > 0.5
                        else 0.0
                    )
                    classification_value_count += 1

                    if predicted_value == target_value:
                        classification_correct_count += 1
                    else:
                        row_binary_correct = False
                        binary_mismatch = True

                target_column = column_index
                self.table.setItem(
                    row_index,
                    column_index,
                    self.create_number_item(
                        target_value,
                        binary=is_binary,
                        translator=self.t
                    )
                )
                column_index += 1

                actual_column = column_index
                self.table.setItem(
                    row_index,
                    column_index,
                    self.create_number_item(
                        actual_value,
                        binary=is_binary,
                        translator=self.t
                    )
                )
                column_index += 1

                if binary_mismatch:
                    error_color = QColor("#f8d7da")
                    self.table.item(
                        row_index,
                        target_column
                    ).setBackground(error_color)
                    self.table.item(
                        row_index,
                        actual_column
                    ).setBackground(error_color)

                self.table.setItem(
                    row_index,
                    column_index,
                    self.create_number_item(
                        error_value
                    )
                )
                column_index += 1

            row_has_error = row_has_binary_output and not row_binary_correct
            self.row_classification_errors.append(row_has_error)
            if row_has_binary_output:
                if row_binary_correct:
                    classification_record_correct_count += 1
                else:
                    classification_record_error_count += 1

        if output_value_count > 0:
            mean_squared_error = (
                squared_error_sum
                / output_value_count
            )
            mean_absolute_error = (
                absolute_error_sum
                / output_value_count
            )
        else:
            mean_squared_error = 0.0
            mean_absolute_error = 0.0

        summary_parts = [
            self.t("test.summary.records", count=len(self.records)),
            self.t("test.summary.mse", value=format_number(mean_squared_error)),
            self.t("test.summary.mae", value=format_number(mean_absolute_error)),
            self.t("test.summary.maximum", value=format_number(maximum_absolute_error))
        ]

        if classification_value_count > 0:
            classification_percent = (
                100.0
                * classification_correct_count
                / classification_value_count
            )
            summary_parts.append(self.t(
                "test.summary.classified",
                correct=classification_correct_count,
                total=classification_value_count,
                percent=f"{classification_percent:.1f}"
            ))
            record_total = (
                classification_record_correct_count
                + classification_record_error_count
            )
            record_percent = (
                100.0 * classification_record_correct_count / record_total
                if record_total
                else 0.0
            )
            summary_parts.append(self.t(
                "test.summary.classified_records",
                correct=classification_record_correct_count,
                incorrect=classification_record_error_count,
                total=record_total,
                percent=f"{record_percent:.1f}",
            ))

        self.summary_label.setText(
            "   |   ".join(
                summary_parts
            )
        )
        self.apply_error_filter()

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setStretchLastSection(
            False
        )

        # Die letzte Spalte ist üblicherweise eine Fehlerspalte. Sie wurde
        # zuvor über die gesamte restliche Fensterbreite gestreckt. Jede
        # Fehlerspalte erhält nun eine kompakte, aber gut lesbare Breite.
        first_output_column = 1 + len(self.input_columns)

        for output_index in range(len(self.output_columns)):
            error_column = first_output_column + output_index * 3 + 2
            header_item = self.table.horizontalHeaderItem(
                error_column
            )
            header_text = (
                header_item.text()
                if header_item is not None
                else ""
            )
            header_width = (
                self.table.fontMetrics().horizontalAdvance(header_text)
                + 28
            )
            compact_width = max(
                self.table.columnWidth(error_column),
                self.table.sizeHintForColumn(error_column),
                header_width,
                105
            )
            header.setSectionResizeMode(
                error_column,
                QHeaderView.ResizeMode.Fixed
            )
            self.table.setColumnWidth(
                error_column,
                compact_width
            )
