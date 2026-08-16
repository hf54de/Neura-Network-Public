# -------------------------------------------------------------------------------------------------
# Datei: networkfromtrainingdialog.py
# Zweck: Erzeugt aus Trainingsdaten einen passenden Netzwerkvorschlag.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from language import LanguageManager
from network import NeuralNetwork
from neuron import Neuron
from neurontype import NeuronType
from trainingdatadialog import TrainingDataDialog
from trainingdataio import TrainingDataIO


class NetworkFromTrainingDataDialog(QDialog):
    """Getrennter Assistent: Tabelle zuerst, Netzwerk danach."""

    MAX_HIDDEN_LAYERS = 5

    def __init__(
        self,
        existing_network=False,
        default_directory=None,
        language_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.existing_network = bool(existing_network)
        self.default_directory = default_directory
        self.training_document = None
        self.training_file_path = None
        self._document_counts = None
        self.output_activation_boxes = []

        self.setWindowTitle(self.t("network.from_data.title"))
        self.setMinimumWidth(650)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        intro = QLabel(self.t("network.from_data.introduction"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        structure_group = QGroupBox(self.t("network.from_data.step_structure"))
        structure_layout = QFormLayout(structure_group)
        self.input_count = QSpinBox()
        self.input_count.setRange(1, 100)
        self.input_count.setValue(3)
        self.output_count = QSpinBox()
        self.output_count.setRange(1, 100)
        self.output_count.setValue(1)
        self.input_count.valueChanged.connect(self.structure_changed)
        self.output_count.valueChanged.connect(self.structure_changed)
        structure_layout.addRow(
            self.t("network.create.input_neurons"), self.input_count
        )
        structure_layout.addRow(
            self.t("network.create.output_neurons"), self.output_count
        )
        layout.addWidget(structure_group)

        data_group = QGroupBox(self.t("network.from_data.step_data"))
        data_layout = QVBoxLayout(data_group)
        self.edit_data_button = QPushButton(
            self.t("network.from_data.edit_table")
        )
        self.edit_data_button.clicked.connect(self.edit_training_table)
        self.data_status = QLabel(self.t("network.from_data.no_data"))
        self.data_status.setWordWrap(True)
        data_layout.addWidget(self.edit_data_button)
        data_layout.addWidget(self.data_status)
        layout.addWidget(data_group)

        self.proposal_group = QGroupBox(
            self.t("network.from_data.step_proposal")
        )
        proposal_layout = QVBoxLayout(self.proposal_group)
        proposal_form = QFormLayout()
        self.hidden_layer_count = QSpinBox()
        self.hidden_layer_count.setRange(0, self.MAX_HIDDEN_LAYERS)
        self.hidden_layer_count.valueChanged.connect(
            self.update_hidden_controls
        )
        proposal_form.addRow(
            self.t("network.create.hidden_layers"),
            self.hidden_layer_count,
        )
        self.hidden_layer_sizes = []
        self.hidden_rows = []
        for layer_index in range(self.MAX_HIDDEN_LAYERS):
            label = QLabel(
                self.t(
                    "network.create.hidden_layer_neurons",
                    layer=layer_index + 1,
                )
            )
            spin = QSpinBox()
            spin.setRange(1, 100)
            spin.setValue(4)
            proposal_form.addRow(label, spin)
            self.hidden_layer_sizes.append(spin)
            self.hidden_rows.append((label, spin))
        self.hidden_activation = QComboBox()
        self.hidden_activation.addItems(["Tanh", "Sigmoid", "ReLU", "Linear"])
        proposal_form.addRow(
            self.t("network.create.hidden_neurons"), self.hidden_activation
        )
        proposal_layout.addLayout(proposal_form)

        self.output_activation_widget = QWidget()
        self.output_activation_layout = QFormLayout(
            self.output_activation_widget
        )
        self.output_activation_layout.setContentsMargins(0, 0, 0, 0)
        proposal_layout.addWidget(self.output_activation_widget)

        self.fully_connected = QCheckBox(
            self.t("network.create.fully_connected")
        )
        self.fully_connected.setChecked(True)
        proposal_layout.addWidget(self.fully_connected)

        self.proposal_summary = QLabel()
        self.proposal_summary.setWordWrap(True)
        proposal_layout.addWidget(self.proposal_summary)
        self.proposal_group.setEnabled(False)
        layout.addWidget(self.proposal_group)

        if self.existing_network:
            warning = QLabel(self.t("network.from_data.existing_warning"))
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #a05000;")
            layout.addWidget(warning)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.create_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.create_button.setText(self.t("network.from_data.create"))
        self.create_button.setEnabled(False)
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(self.t("common.cancel"))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        for spin in self.hidden_layer_sizes:
            spin.valueChanged.connect(self.update_proposal_summary)
        self.fully_connected.toggled.connect(self.update_proposal_summary)
        self.update_hidden_controls()

    def structure_changed(self):
        """Verhindert, dass eine alte Tabelle zu neuen Anzahlen benutzt wird."""
        if self.training_document is None:
            return
        counts = (self.input_count.value(), self.output_count.value())
        if counts == self._document_counts:
            return
        self.data_status.setText(self.t("network.from_data.structure_changed"))
        self.proposal_group.setEnabled(False)
        self.create_button.setEnabled(False)

    def create_staging_network(self, document):
        """Erzeugt nur für den Dateneditor passende Zuordnungsziele."""
        network = NeuralNetwork()
        neuron_id = 1
        for column in document.get("columns", []):
            neuron = Neuron(
                neuron_id,
                0.0,
                0.0,
                str(column.get("name") or f"N{neuron_id}"),
                translator=self.t,
            )
            neuron.neuron_type = (
                NeuronType.INPUT
                if column.get("role") == "input"
                else NeuronType.OUTPUT
            )
            neuron.activation_function = "Linear"
            network.add_neuron(neuron)
            column["mapped_neuron_id"] = neuron_id
            column["mapped_neuron_name"] = neuron.name
            neuron_id += 1
        return network

    @staticmethod
    def clear_temporary_mappings(document):
        """Entfernt Zuordnungen, bevor die wirklichen Neuronen existieren."""

        for column in document.get("columns", []):
            if not isinstance(column, dict):
                continue
            column["mapped_neuron_id"] = None
            column["mapped_neuron_name"] = None

    @staticmethod
    def sanitize_binary_columns(document):
        """Stellt für Binärspalten zuverlässig 'Keine Skalierung' her."""

        for column in document.get("columns", []):
            if (
                isinstance(column, dict)
                and column.get("data_type", "analog") == "binary"
            ):
                column["calibration"] = TrainingDataIO.default_calibration()
                column.pop("calibration_source", None)
                column.pop("training_calibration", None)

    def edit_training_table(self):
        counts = (self.input_count.value(), self.output_count.value())
        if self.training_document is None or self._document_counts != counts:
            if self.training_document is not None:
                answer = QMessageBox.question(
                    self,
                    self.t("network.from_data.reset_title"),
                    self.t("network.from_data.reset_question"),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            document = TrainingDataIO.create_empty_document(
                counts[0],
                counts[1],
                self.t("network.from_data.document_name"),
            )
        else:
            document = copy.deepcopy(self.training_document)

        staging_network = self.create_staging_network(document)
        editor = TrainingDataDialog(
            staging_network,
            document=document,
            file_path=self.training_file_path,
            parent=self,
            document_modified=self.training_document is not None,
            default_directory=self.default_directory,
            language_manager=self.language,
            temporary_mappings=True,
        )
        if editor.exec() != QDialog.DialogCode.Accepted:
            return

        edited_document = copy.deepcopy(editor.document)
        self.clear_temporary_mappings(edited_document)
        self.sanitize_binary_columns(edited_document)
        edited_input_count = sum(
            1
            for column in edited_document.get("columns", [])
            if column.get("role") == "input"
        )
        edited_output_count = sum(
            1
            for column in edited_document.get("columns", [])
            if column.get("role") == "output"
        )
        if (edited_input_count, edited_output_count) != counts:
            QMessageBox.warning(
                self,
                self.t("network.from_data.structure_error_title"),
                self.t(
                    "network.from_data.structure_error",
                    inputs=counts[0],
                    outputs=counts[1],
                ),
            )
            self.data_status.setText(
                self.t("network.from_data.structure_changed")
            )
            self.proposal_group.setEnabled(False)
            self.create_button.setEnabled(False)
            return

        self.training_document = edited_document
        self.training_file_path = editor.current_file_path
        self._document_counts = counts
        self.apply_automatic_scaling()
        self.build_proposal()

    def apply_automatic_scaling(self):
        scaled = 0
        constant = []
        empty = []
        records = self.training_document.get("records", [])
        for index, column in enumerate(
            self.training_document.get("columns", [])
        ):
            values = [
                float(record[index])
                for record in records
                if index < len(record)
            ]
            name = str(column.get("name") or index + 1)
            column.pop("calibration_source", None)
            column.pop("training_calibration", None)
            if column.get("data_type", "analog") == "binary":
                column["calibration"] = TrainingDataIO.default_calibration()
                continue
            if not values:
                empty.append(name)
                column["calibration"] = TrainingDataIO.default_calibration()
                continue
            source_min = min(values)
            source_max = max(values)
            if not source_min < source_max:
                constant.append(name)
                column["calibration"] = TrainingDataIO.default_calibration()
                continue
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            column["calibration"] = {
                "mode": "minmax_0_1",
                "source_min": source_min,
                "source_max": source_max,
                "mean": mean,
                "stddev": math.sqrt(variance),
            }
            scaled += 1

        if not records:
            self.data_status.setText(self.t("network.from_data.no_records"))
            self.proposal_group.setEnabled(False)
            self.create_button.setEnabled(False)
            return

        self.data_status.setText(
            self.t(
                "network.from_data.data_ready",
                records=len(records),
                scaled=scaled,
                constant=len(constant),
            )
        )

    def suggested_output_activation(self, column_index):
        records = self.training_document.get("records", [])
        values = {
            round(float(record[column_index]), 12)
            for record in records
            if column_index < len(record)
        }
        if values and values.issubset({0.0, 1.0}) and len(values) > 1:
            return "Sigmoid"
        return "Linear"

    def build_proposal(self):
        if not self.training_document.get("records"):
            return
        input_count = self.input_count.value()
        output_count = self.output_count.value()
        if input_count >= 4 or output_count > 1:
            sizes = [max(4, input_count * 2)]
            sizes.append(max(2, sizes[0] // 2, output_count * 2))
        else:
            sizes = [max(2, input_count * 2)]
        self.hidden_layer_count.setValue(len(sizes))
        for index, size in enumerate(sizes):
            self.hidden_layer_sizes[index].setValue(size)

        while self.output_activation_layout.count():
            item = self.output_activation_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.output_activation_boxes = []
        columns = self.training_document.get("columns", [])
        input_columns = [c for c in columns if c.get("role") == "input"]
        output_columns = [c for c in columns if c.get("role") == "output"]
        for index, column in enumerate(output_columns):
            combo = QComboBox()
            combo.addItems(["Linear", "Sigmoid", "Tanh", "ReLU"])
            activation = self.suggested_output_activation(
                len(input_columns) + index
            )
            combo.setCurrentText(activation)
            self.output_activation_layout.addRow(
                self.t(
                    "network.from_data.output_activation",
                    name=str(column.get("name") or index + 1),
                ),
                combo,
            )
            self.output_activation_boxes.append(combo)
        self.proposal_group.setEnabled(True)
        self.create_button.setEnabled(True)
        self.update_hidden_controls()

    def update_hidden_controls(self):
        count = self.hidden_layer_count.value()
        for index, (label, spin) in enumerate(self.hidden_rows):
            visible = index < count
            label.setVisible(visible)
            spin.setVisible(visible)
        self.hidden_activation.setEnabled(count > 0)
        self.update_proposal_summary()
        self.adjustSize()

    def update_proposal_summary(self):
        if not self.training_document:
            self.proposal_summary.setText("")
            return
        layer_counts = [self.input_count.value()]
        layer_counts.extend(
            spin.value()
            for spin in self.hidden_layer_sizes[
                : self.hidden_layer_count.value()
            ]
        )
        layer_counts.append(self.output_count.value())
        connections = 0
        if self.fully_connected.isChecked():
            connections = sum(
                layer_counts[index] * layer_counts[index + 1]
                for index in range(len(layer_counts) - 1)
            )
        self.proposal_summary.setText(
            self.t(
                "network.from_data.proposal_summary",
                structure=" → ".join(str(value) for value in layer_counts),
                connections=connections,
            )
        )

    def get_result(self):
        document = copy.deepcopy(self.training_document)
        self.clear_temporary_mappings(document)
        self.sanitize_binary_columns(document)
        return {
            "input_count": self.input_count.value(),
            "output_count": self.output_count.value(),
            "hidden_layer_count": self.hidden_layer_count.value(),
            "hidden_layer_sizes": [
                spin.value()
                for spin in self.hidden_layer_sizes[
                    : self.hidden_layer_count.value()
                ]
            ],
            "hidden_activation": self.hidden_activation.currentText(),
            "output_activations": [
                combo.currentText() for combo in self.output_activation_boxes
            ],
            "fully_connected": self.fully_connected.isChecked(),
            "replace_network": True,
            "training_document": document,
            "training_file_path": self.training_file_path,
        }

    def accept(self):
        if not self.training_document or not self.training_document.get("records"):
            QMessageBox.warning(
                self,
                self.t("network.from_data.missing_title"),
                self.t("network.from_data.missing_data"),
            )
            return
        self.clear_temporary_mappings(self.training_document)
        self.sanitize_binary_columns(self.training_document)
        try:
            TrainingDataIO.validate(
                self.training_document,
                translator=self.t,
            )
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.t("network.create.error_title"),
                str(error),
            )
            return
        layer_counts = [self.input_count.value()]
        layer_counts.extend(
            spin.value()
            for spin in self.hidden_layer_sizes[
                : self.hidden_layer_count.value()
            ]
        )
        layer_counts.append(self.output_count.value())
        neuron_count = sum(layer_counts)
        connection_count = sum(
            layer_counts[index] * layer_counts[index + 1]
            for index in range(len(layer_counts) - 1)
        ) if self.fully_connected.isChecked() else 0
        if neuron_count > 500 or connection_count > 50000:
            QMessageBox.warning(
                self,
                self.t("network.create.too_large.title"),
                self.t("network.create.too_many_connections")
                if connection_count > 50000
                else self.t("network.create.too_many_neurons"),
            )
            return
        super().accept()
