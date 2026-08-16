# -------------------------------------------------------------------------------------------------
# Datei: networkstructuredialog.py
# Zweck: Analysiert und bearbeitet die erkannte Schichtstruktur eines Netzwerks.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from language import LanguageManager


class NetworkStructureDialog(QDialog):
    """Ändert ausschließlich die Hidden-Struktur eines Netzwerkes."""

    MAX_HIDDEN_LAYERS = 20

    def __init__(self, hidden_layer_sizes, language_manager=None, parent=None):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.initial_sizes = [int(size) for size in hidden_layer_sizes]

        self.setWindowTitle(self.t("network.structure.title"))
        self.setModal(True)
        self.setMinimumWidth(430)

        main_layout = QVBoxLayout(self)

        note = QLabel(self.t("network.structure.preserved"))
        note.setWordWrap(True)
        main_layout.addWidget(note)

        self.form_layout = QFormLayout()
        main_layout.addLayout(self.form_layout)

        self.hidden_layer_count = QSpinBox()
        self.hidden_layer_count.setRange(0, self.MAX_HIDDEN_LAYERS)
        self.hidden_layer_count.setValue(len(self.initial_sizes))
        self.form_layout.addRow(
            self.t("network.create.hidden_layers"),
            self.hidden_layer_count,
        )

        self.hidden_layer_sizes = []
        self.hidden_layer_rows = []

        for layer_index in range(self.MAX_HIDDEN_LAYERS):
            label = QLabel(
                self.t(
                    "network.create.hidden_layer_neurons",
                    layer=layer_index + 1,
                )
            )
            count = QSpinBox()
            count.setRange(1, 500)
            count.setValue(
                self.initial_sizes[layer_index]
                if layer_index < len(self.initial_sizes)
                else 4
            )
            self.form_layout.addRow(label, count)
            self.hidden_layer_sizes.append(count)
            self.hidden_layer_rows.append((label, count))

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText(self.t("common.apply"))
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(self.t("common.cancel"))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.hidden_layer_count.valueChanged.connect(self.update_rows)
        self.update_rows()

    def update_rows(self):
        visible_count = self.hidden_layer_count.value()

        for index, (label, count) in enumerate(self.hidden_layer_rows):
            visible = index < visible_count
            label.setVisible(visible)
            count.setVisible(visible)

        self.adjustSize()

    def hidden_sizes(self):
        return [
            count.value()
            for count in self.hidden_layer_sizes[: self.hidden_layer_count.value()]
        ]

    def has_changes(self):
        return self.hidden_sizes() != self.initial_sizes
