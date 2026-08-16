# -------------------------------------------------------------------------------------------------
# Datei: networklayoutdialog.py
# Zweck: Ordnet ein vorhandenes Netzwerk automatisch und schichtweise an.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from collections import deque
from statistics import median

from PySide6.QtCore import QPointF, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout
)

from neurontype import NeuronType
from language import LanguageManager


class NetworkLayoutDialog(QDialog):
    """Ordnet ein vorhandenes, azyklisches Netzwerk in Schichten an."""

    # Das Dictionary verwendet Neuronenobjekte als Schlüssel und darf
    # deshalb nicht als Qt-Dictionary nach C++ konvertiert werden.
    preview_changed = Signal(object)

    DEFAULT_HORIZONTAL_SPACING = 400
    DEFAULT_VERTICAL_SPACING = 225

    def __init__(self, network, parent=None, language_manager=None):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        self.network = network
        self.neurons = list(network.get_neurons())
        self.connections = list(network.get_connections())
        self.structure = self.analyze_structure()
        self.layout_center = self.calculate_current_center()

        self.setWindowTitle(self.t("network.layout.title"))
        self.setModal(True)
        self.setMinimumWidth(470)

        main_layout = QVBoxLayout(self)

        spacing_group = QGroupBox(self.t("network.layout.spacing"))
        spacing_layout = QFormLayout(spacing_group)

        self.horizontal_spacing = QSpinBox()
        self.horizontal_spacing.setRange(200, 1200)
        self.horizontal_spacing.setSuffix(" px")
        self.horizontal_spacing.setValue(
            self.current_horizontal_spacing()
        )

        self.vertical_spacing = QSpinBox()
        self.vertical_spacing.setRange(180, 800)
        self.vertical_spacing.setSuffix(" px")
        self.vertical_spacing.setValue(
            self.current_vertical_spacing()
        )

        spacing_layout.addRow(
            self.t("network.layout.between_layers"),
            self.horizontal_spacing
        )
        spacing_layout.addRow(
            self.t("network.layout.between_neurons"),
            self.vertical_spacing
        )
        main_layout.addWidget(spacing_group)

        self.summary_label = QLabel(
            self.create_summary_text()
        )
        self.summary_label.setWordWrap(True)
        main_layout.addWidget(self.summary_label)

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
        self.default_button = QPushButton(self.t("common.defaults"))
        self.button_box.addButton(
            self.default_button,
            QDialogButtonBox.ButtonRole.ResetRole
        )
        self.default_button.clicked.connect(self.restore_defaults)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.horizontal_spacing.valueChanged.connect(
            self.emit_preview
        )
        self.vertical_spacing.valueChanged.connect(
            self.emit_preview
        )

    def analyze_structure(self):
        """Erkennt Schichten und bricht bei gerichteten Zyklen ab."""

        outgoing = {
            neuron: []
            for neuron in self.neurons
        }
        incoming = {
            neuron: []
            for neuron in self.neurons
        }

        for connection in self.connections:
            source = connection.source_neuron
            target = connection.target_neuron

            if source in outgoing and target in incoming:
                outgoing[source].append(target)
                incoming[target].append(source)

        indegree = {
            neuron: len(incoming[neuron])
            for neuron in self.neurons
        }
        ready = deque(
            sorted(
                (
                    neuron
                    for neuron in self.neurons
                    if indegree[neuron] == 0
                ),
                key=lambda neuron: neuron.id
            )
        )
        topological_order = []

        while ready:
            neuron = ready.popleft()
            topological_order.append(neuron)

            for target in sorted(
                outgoing[neuron],
                key=lambda item: item.id
            ):
                indegree[target] -= 1

                if indegree[target] == 0:
                    ready.append(target)

        if len(topological_order) != len(self.neurons):
            cycle_neurons = sorted(
                (
                    neuron.name
                    for neuron in self.neurons
                    if indegree[neuron] > 0
                )
            )
            cycle_text = ", ".join(cycle_neurons[:12])

            if len(cycle_neurons) > 12:
                cycle_text += ", ..."

            raise ValueError(self.t("network.layout.cycle", neurons=cycle_text))

        input_neurons = [
            neuron
            for neuron in self.neurons
            if neuron.neuron_type == NeuronType.INPUT
        ]
        output_neurons = [
            neuron
            for neuron in self.neurons
            if neuron.neuron_type == NeuronType.OUTPUT
        ]

        reachable = set(input_neurons)

        for neuron in topological_order:
            if neuron not in reachable:
                continue

            reachable.update(outgoing[neuron])

        reachable_hidden = [
            neuron
            for neuron in topological_order
            if (
                neuron.neuron_type == NeuronType.HIDDEN
                and neuron in reachable
            )
        ]
        separate_hidden = [
            neuron
            for neuron in topological_order
            if (
                neuron.neuron_type == NeuronType.HIDDEN
                and neuron not in reachable
            )
        ]

        reachable_depth = {
            neuron: 0
            for neuron in input_neurons
        }

        for neuron in topological_order:
            if neuron not in reachable_depth:
                continue

            for target in outgoing[neuron]:
                if target.neuron_type == NeuronType.INPUT:
                    continue

                reachable_depth[target] = max(
                    reachable_depth.get(target, 0),
                    reachable_depth[neuron] + 1
                )

        hidden_depth_values = sorted({
            reachable_depth.get(neuron, 1)
            for neuron in reachable_hidden
        })
        hidden_depth_map = {
            depth: index + 1
            for index, depth in enumerate(hidden_depth_values)
        }

        separate_set = set(separate_hidden)
        separate_depth = {}

        for neuron in topological_order:
            if neuron not in separate_set:
                continue

            predecessors = [
                source
                for source in incoming[neuron]
                if source in separate_set
            ]
            separate_depth[neuron] = (
                max(
                    separate_depth[source]
                    for source in predecessors
                )
                + 1
                if predecessors
                else 0
            )

        separate_depth_values = sorted(
            set(separate_depth.values())
        )
        separate_depth_map = {
            depth: index + 1
            for index, depth in enumerate(separate_depth_values)
        }

        hidden_layer_count = max(
            len(hidden_depth_values),
            len(separate_depth_values),
            0
        )
        output_layer = hidden_layer_count + 1

        main_layers = {
            0: list(input_neurons),
            output_layer: list(output_neurons)
        }

        for neuron in reachable_hidden:
            layer_index = hidden_depth_map[
                reachable_depth.get(neuron, 1)
            ]
            main_layers.setdefault(layer_index, []).append(neuron)

        separate_layers = {}

        for neuron in separate_hidden:
            layer_index = separate_depth_map[
                separate_depth[neuron]
            ]
            separate_layers.setdefault(layer_index, []).append(neuron)

        for layer in main_layers.values():
            layer.sort(key=lambda neuron: (neuron.y(), neuron.id))

        for layer in separate_layers.values():
            layer.sort(key=lambda neuron: (neuron.y(), neuron.id))

        self.reduce_crossings(
            main_layers,
            incoming,
            outgoing,
            output_layer
        )

        return {
            "main_layers": main_layers,
            "separate_layers": separate_layers,
            "output_layer": output_layer,
            "incoming": incoming,
            "outgoing": outgoing
        }

    @staticmethod
    def reduce_crossings(
        layers,
        incoming,
        outgoing,
        output_layer
    ):
        """Sortiert Schichten mit mehreren Baryzentrum-Durchläufen."""

        for _ in range(3):
            positions = {
                neuron: index
                for layer in layers.values()
                for index, neuron in enumerate(layer)
            }

            for layer_index in range(1, output_layer + 1):
                layer = layers.get(layer_index, [])
                original_order = {
                    neuron: index
                    for index, neuron in enumerate(layer)
                }

                def predecessor_key(neuron):
                    values = [
                        positions[source]
                        for source in incoming[neuron]
                        if source in positions
                    ]
                    return (
                        sum(values) / len(values)
                        if values
                        else original_order[neuron]
                    )

                layer.sort(
                    key=lambda neuron: (
                        predecessor_key(neuron),
                        original_order[neuron]
                    )
                )

            positions = {
                neuron: index
                for layer in layers.values()
                for index, neuron in enumerate(layer)
            }

            for layer_index in range(output_layer - 1, -1, -1):
                layer = layers.get(layer_index, [])
                original_order = {
                    neuron: index
                    for index, neuron in enumerate(layer)
                }

                def successor_key(neuron):
                    values = [
                        positions[target]
                        for target in outgoing[neuron]
                        if target in positions
                    ]
                    return (
                        sum(values) / len(values)
                        if values
                        else original_order[neuron]
                    )

                layer.sort(
                    key=lambda neuron: (
                        successor_key(neuron),
                        original_order[neuron]
                    )
                )

    def calculate_current_center(self):
        left = min(neuron.x() for neuron in self.neurons)
        top = min(neuron.y() for neuron in self.neurons)
        right = max(
            neuron.x() + neuron.width
            for neuron in self.neurons
        )
        bottom = max(
            neuron.y() + neuron.height
            for neuron in self.neurons
        )

        return QPointF(
            (left + right) / 2.0,
            (top + bottom) / 2.0
        )

    def positions(self):
        horizontal = float(self.horizontal_spacing.value())
        vertical = float(self.vertical_spacing.value())
        main_layers = self.structure["main_layers"]
        separate_layers = self.structure["separate_layers"]
        output_layer = self.structure["output_layer"]

        neuron_width = max(neuron.width for neuron in self.neurons)
        neuron_height = max(neuron.height for neuron in self.neurons)
        layout_width = output_layer * horizontal + neuron_width
        start_x = self.layout_center.x() - layout_width / 2.0

        maximum_main_count = max(
            (len(layer) for layer in main_layers.values()),
            default=1
        )
        main_height = (
            (maximum_main_count - 1) * vertical
            + neuron_height
        )
        start_y = self.layout_center.y() - main_height / 2.0
        result = {}

        for layer_index, layer in main_layers.items():
            layer_height = (
                (len(layer) - 1) * vertical
                + neuron_height
                if layer
                else 0.0
            )
            layer_y = start_y + (main_height - layer_height) / 2.0

            for neuron_index, neuron in enumerate(layer):
                result[neuron] = QPointF(
                    start_x + layer_index * horizontal,
                    layer_y + neuron_index * vertical
                )

        separate_start_y = start_y + main_height + vertical

        for layer_index, layer in separate_layers.items():
            for neuron_index, neuron in enumerate(layer):
                result[neuron] = QPointF(
                    start_x + layer_index * horizontal,
                    separate_start_y + neuron_index * vertical
                )

        return result

    def create_summary_text(self):
        main_layers = self.structure["main_layers"]
        separate_layers = self.structure["separate_layers"]
        output_layer = self.structure["output_layer"]
        layer_counts = [
            len(main_layers.get(index, []))
            for index in range(output_layer + 1)
        ]
        text = self.t(
            "network.layout.main_structure",
            structure=" → ".join(str(count) for count in layer_counts)
        )
        separate_count = sum(
            len(layer)
            for layer in separate_layers.values()
        )

        if separate_count:
            text += "\n" + self.t(
                "network.layout.separate_hidden",
                count=separate_count
            )

        text += "\n" + self.t("network.layout.preview_hint")
        return text

    def restore_defaults(self, _checked=False):
        self.horizontal_spacing.setValue(
            self.recommended_horizontal_spacing()
        )
        self.vertical_spacing.setValue(
            self.DEFAULT_VERTICAL_SPACING
        )
        self.emit_preview()

    def recommended_horizontal_spacing(self):
        """Gibt dichten Schichten zusätzlichen Raum für Linien und Gewichte."""

        maximum_count = max(
            (
                len(layer)
                for layer in self.structure["main_layers"].values()
            ),
            default=1
        )
        return int(
            self.DEFAULT_HORIZONTAL_SPACING
            + min(320, max(0, maximum_count - 4) * 18)
        )

    def current_horizontal_spacing(self):
        """Schätzt den vorhandenen mittleren Abstand der erkannten Schichten."""

        centers = []
        for layer in self.structure["main_layers"].values():
            if layer:
                centers.append(sum(neuron.x() for neuron in layer) / len(layer))
        centers.sort()
        gaps = [
            second - first
            for first, second in zip(centers, centers[1:])
            if second - first > 1.0
        ]
        value = median(gaps) if gaps else self.recommended_horizontal_spacing()
        return max(
            self.horizontal_spacing.minimum(),
            min(self.horizontal_spacing.maximum(), int(round(value))),
        )

    def current_vertical_spacing(self):
        """Schätzt robust den vorhandenen Abstand innerhalb der Schichten."""

        gaps = []
        for layer in self.structure["main_layers"].values():
            positions = sorted(neuron.y() for neuron in layer)
            gaps.extend(
                second - first
                for first, second in zip(positions, positions[1:])
                if second - first > 1.0
            )
        value = median(gaps) if gaps else self.DEFAULT_VERTICAL_SPACING
        return max(
            self.vertical_spacing.minimum(),
            min(self.vertical_spacing.maximum(), int(round(value))),
        )

    def emit_preview(self, _value=None):
        self.preview_changed.emit(
            self.positions()
        )
