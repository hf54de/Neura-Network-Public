# -------------------------------------------------------------------------------------------------
# Datei: networkcreatedialog.py
# Zweck: Erfasst die Vorgaben für die automatische Erzeugung eines Netzwerks.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout
)

from language import LanguageManager


class NetworkCreateDialog(QDialog):
    """
    Erfasst die Struktur eines automatisch zu erzeugenden Netzwerkes.
    """

    def __init__(
        self,
        language_manager=None,
        parent=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        self.setWindowTitle(
            self.t("network.create.title")
        )

        self.setMinimumWidth(
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
            12
        )

        self.structure_group = QGroupBox(
            self.t("network.create.structure")
        )

        self.structure_layout = QFormLayout(
            self.structure_group
        )

        self.input_count = QSpinBox()
        self.input_count.setRange(
            1,
            100
        )
        self.input_count.setValue(
            3
        )

        self.hidden_layer_count = QSpinBox()
        self.hidden_layer_count.setRange(
            0,
            5
        )
        self.hidden_layer_count.setValue(
            1
        )

        self.hidden_layer_sizes = []
        self.hidden_layer_rows = []

        for layer_index in range(5):
            neuron_count = QSpinBox()
            neuron_count.setRange(
                1,
                100
            )
            neuron_count.setValue(
                4
            )
            label = QLabel(
                self.t(
                    "network.create.hidden_layer_neurons",
                    layer=layer_index + 1
                )
            )
            self.hidden_layer_sizes.append(
                neuron_count
            )
            self.hidden_layer_rows.append(
                (label, neuron_count)
            )

        self.output_count = QSpinBox()
        self.output_count.setRange(
            1,
            100
        )
        self.output_count.setValue(
            1
        )

        self.structure_layout.addRow(
            self.t("network.create.input_neurons"),
            self.input_count
        )

        self.structure_layout.addRow(
            self.t("network.create.hidden_layers"),
            self.hidden_layer_count
        )

        for label, neuron_count in self.hidden_layer_rows:
            self.structure_layout.addRow(
                label,
                neuron_count
            )

        self.structure_layout.addRow(
            self.t("network.create.output_neurons"),
            self.output_count
        )

        self.activation_group = QGroupBox(
            self.t("network.create.activations")
        )

        self.activation_layout = QFormLayout(
            self.activation_group
        )

        self.hidden_activation = QComboBox()
        self.hidden_activation.addItems(
            [
                "Sigmoid",
                "Tanh",
                "ReLU",
                "Linear"
            ]
        )

        self.output_activation = QComboBox()
        self.output_activation.addItems(
            [
                "Sigmoid",
                "Tanh",
                "Linear",
                "ReLU"
            ]
        )

        self.activation_layout.addRow(
            self.t("network.create.hidden_neurons"),
            self.hidden_activation
        )

        self.activation_layout.addRow(
            self.t("network.create.output_neurons"),
            self.output_activation
        )

        self.options_group = QGroupBox(
            self.t("network.create.options")
        )

        self.options_layout = QVBoxLayout(
            self.options_group
        )

        self.fully_connected = QCheckBox(
            self.t("network.create.fully_connected")
        )
        self.fully_connected.setChecked(
            True
        )

        self.create_training_data = QCheckBox(
            self.t("network.create.training_data")
        )
        self.create_training_data.setChecked(
            True
        )
        self.create_training_data.setToolTip(
            self.t("network.create.training_data_tooltip")
        )

        self.options_layout.addWidget(
            self.fully_connected
        )

        self.options_layout.addWidget(
            self.create_training_data
        )

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(
            True
        )
        self.summary_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText(self.t("common.ok"))
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(self.t("common.cancel"))

        self.button_box.accepted.connect(
            self.accept
        )

        self.button_box.rejected.connect(
            self.reject
        )

        self.main_layout.addWidget(
            self.structure_group
        )

        self.main_layout.addWidget(
            self.activation_group
        )

        self.main_layout.addWidget(
            self.options_group
        )

        self.main_layout.addWidget(
            self.summary_label
        )

        self.main_layout.addWidget(
            self.button_box
        )

        self.input_count.valueChanged.connect(
            self.update_summary
        )

        self.hidden_layer_count.valueChanged.connect(
            self.update_hidden_controls
        )

        for neuron_count in self.hidden_layer_sizes:
            neuron_count.valueChanged.connect(
                self.update_summary
            )

        self.output_count.valueChanged.connect(
            self.update_summary
        )

        self.fully_connected.toggled.connect(
            self.update_summary
        )

        self.update_hidden_controls()

    def update_hidden_controls(self):
        """
        Aktiviert die Hidden-Einstellungen nur,
        wenn mindestens eine Hidden-Schicht vorgesehen ist.
        """

        has_hidden_layers = (
            self.hidden_layer_count.value()
            > 0
        )

        visible_layer_count = self.hidden_layer_count.value()

        for layer_index, row in enumerate(self.hidden_layer_rows):
            label, neuron_count = row
            visible = layer_index < visible_layer_count
            label.setVisible(
                visible
            )
            neuron_count.setVisible(
                visible
            )
            neuron_count.setEnabled(
                visible
            )

        self.hidden_activation.setEnabled(
            has_hidden_layers
        )

        self.update_summary()
        self.adjustSize()

    def calculate_structure_size(self):
        """
        Berechnet die Anzahl der zu erzeugenden
        Neuronen und Verbindungen.
        """

        layer_counts = [
            self.input_count.value()
        ]

        layer_counts.extend(
            neuron_count.value()
            for neuron_count in self.hidden_layer_sizes[
                :self.hidden_layer_count.value()
            ]
        )

        layer_counts.append(
            self.output_count.value()
        )

        neuron_count = sum(
            layer_counts
        )

        connection_count = 0

        if self.fully_connected.isChecked():
            for layer_index in range(
                len(layer_counts) - 1
            ):
                connection_count += (
                    layer_counts[layer_index]
                    * layer_counts[layer_index + 1]
                )

        return (
            layer_counts,
            neuron_count,
            connection_count
        )

    def update_summary(self):
        """
        Zeigt die Größe des entstehenden Netzwerkes an.
        """

        (
            layer_counts,
            neuron_count,
            connection_count
        ) = self.calculate_structure_size()

        layer_text = " → ".join(
            str(
                count
            )
            for count in layer_counts
        )

        self.summary_label.setText(
            (
                self.t("network.create.summary_structure", structure=layer_text)
                + "\n"
                + self.t(
                    "network.create.summary_counts",
                    neurons=neuron_count,
                    connections=connection_count
                )
            )
        )

    def get_settings(self):
        """
        Liefert die gewählten Einstellungen.
        """

        return {
            "input_count": int(
                self.input_count.value()
            ),
            "hidden_layer_count": int(
                self.hidden_layer_count.value()
            ),
            "hidden_layer_sizes": [
                int(neuron_count.value())
                for neuron_count in self.hidden_layer_sizes[
                    :self.hidden_layer_count.value()
                ]
            ],
            "output_count": int(
                self.output_count.value()
            ),
            "hidden_activation": (
                self.hidden_activation.currentText()
            ),
            "output_activation": (
                self.output_activation.currentText()
            ),
            "fully_connected": (
                self.fully_connected.isChecked()
            ),
            "create_training_data": (
                self.create_training_data.isChecked()
            )
        }

    def accept(self):
        """
        Verhindert versehentlich extrem große Netzwerke.
        """

        (
            _,
            neuron_count,
            connection_count
        ) = self.calculate_structure_size()

        if connection_count > 50000:
            QMessageBox.warning(
                self,
                self.t("network.create.too_large.title"),
                self.t("network.create.too_many_connections")
            )
            return

        if neuron_count > 500:
            QMessageBox.warning(
                self,
                self.t("network.create.too_large.title"),
                self.t("network.create.too_many_neurons")
            )
            return

        super().accept()
