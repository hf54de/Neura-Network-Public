# -------------------------------------------------------------------------------------------------
# Datei: neuron.py
# Zweck: Stellt Neuronen mit Eigenschaften, Werten und grafischer Darstellung bereit.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import (
    QLineF,
    QPointF,
    QRectF,
    Qt,
    Signal
)
from math import exp, tanh

from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainterPath,
    QPen
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject
)

from neurontype import NeuronType
from numberformat import format_number


class Neuron(QGraphicsObject):
    """
    Grafische und logische Darstellung eines Neurons.

    Zuständig für:
        - ID
        - Name
        - Neuronentyp
        - Bias
        - Aktivierungsfunktion
        - Laufzeitwerte
        - Position
        - Anschlussports
        - verbundene Connections
        - grafische Darstellung
    """

    # Signal: Die Position des Neurons wurde geändert.
    position_changed = Signal(float, float)

    def __init__(self, id, x, y, name, translator=None):

        super().__init__()

        self.id = id
        self.name = name
        self.translator = translator
        self.neuron_type = NeuronType.HIDDEN
        self.bias = 0.0
        self.activation_function = "Sigmoid"

        # Laufzeitwerte für die Simulation
        self.input_value = 0.0
        self.sum_value = 0.0
        self.output_value = 0.0
        self.target_value = 0.0
        self.error_value = 0.0
        self.delta_value = 0.0

        # Zusätzliche, rein visuelle Ein-/Ausgabewerte. Sie gehören
        # nicht zur Netzberechnung und werden nicht im Projektformat
        # gespeichert.
        self.io_fields_visible = True
        self.external_input_value = None
        self.external_input_is_raw = False
        self.external_input_is_binary = False
        self.external_input_unit = ""
        self.external_output_value = None
        self.external_target_value = None
        self.external_output_is_raw = False
        self.external_output_is_binary = False
        self.external_output_unit = ""

        self.external_field_width = 120.0
        self.external_field_gap = 16.0

        self.incoming_connections = []
        self.outgoing_connections = []

        self.width = 190.0
        self.height = 185.0
        self.corner_radius = 10.0
        self.port_radius = 5.0

        self.hovered_port = None
        self.values_visible = True
        self.display_decimals = None
        self.preview_show_bias = True
        self.preview_show_first_value = True
        self.preview_show_output = True
        self.preview_message = ""
        self.activation_chart_visible = True
        self.ports_visible = True
        self.name_visible = True

        self.normal_border_pen = QPen(
            Qt.GlobalColor.black,
            1
        )

        self.selected_border_pen = QPen(
            Qt.GlobalColor.red,
            3
        )

        self.background_brush = QBrush(
            QColor(255, 247, 204)
        )

        self.input_header_brush = QBrush(
            QColor(160, 205, 245)
        )

        self.hidden_header_brush = QBrush(
            QColor(245, 210, 120)
        )

        self.output_header_brush = QBrush(
            QColor(155, 220, 165)
        )

        self.input_port_brush = QBrush(
            QColor(60, 130, 220)
        )

        self.output_port_brush = QBrush(
            QColor(40, 170, 90)
        )

        self.hover_port_brush = QBrush(
            QColor(255, 170, 0)
        )

        self.setPos(x, y)

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            True
        )

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
            True
        )

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
            True
        )

        self.setAcceptHoverEvents(True)

    def set_values_visible(self, visible):
        self.values_visible = bool(visible)
        self.update()

    def set_activation_chart_visible(self, visible):
        self.activation_chart_visible = bool(visible)
        self.update()

    def paint_activation_chart(self, painter):
        """Zeichnet eine transparente Miniatur der Aktivierungsfunktion."""

        if (
            not self.activation_chart_visible
            or self.neuron_type == NeuronType.INPUT
        ):
            return

        chart_rect = QRectF(
            self.width - 98.0,
            122.0,
            90.0,
            self.height - 128.0
        )
        plot_rect = chart_rect.adjusted(15.0, 4.0, -4.0, -12.0)
        activation = str(self.activation_function).casefold()

        if activation == "sigmoid":
            x_min, x_max = -4.0, 4.0
            y_min, y_max = 0.0, 1.0
            x_ticks = (-4.0, 0.0, 4.0)
            y_ticks = (0.0, 0.5, 1.0)
            function = lambda value: 1.0 / (1.0 + exp(-value))
        elif activation == "tanh":
            x_min, x_max = -2.0, 2.0
            y_min, y_max = -1.0, 1.0
            x_ticks = (-2.0, 0.0, 2.0)
            y_ticks = (-1.0, 0.0, 1.0)
            function = tanh
        elif activation == "relu":
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -1.0, 1.0
            x_ticks = (-1.0, 0.0, 1.0)
            y_ticks = (-1.0, 0.0, 1.0)
            function = lambda value: max(0.0, value)
        else:
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -1.0, 1.0
            x_ticks = (-1.0, 0.0, 1.0)
            y_ticks = (-1.0, 0.0, 1.0)
            function = lambda value: value

        def map_x(value):
            return plot_rect.left() + (
                (value - x_min) / (x_max - x_min)
            ) * plot_rect.width()

        def map_y(value):
            return plot_rect.bottom() - (
                (value - y_min) / (y_max - y_min)
            ) * plot_rect.height()

        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        axis_color = QColor(85, 95, 105)
        painter.setPen(QPen(axis_color, 0.8))
        axis_x = map_x(0.0)
        axis_y = map_y(0.0)
        painter.drawLine(
            QPointF(plot_rect.left(), axis_y),
            QPointF(plot_rect.right(), axis_y)
        )
        painter.drawLine(
            QPointF(axis_x, plot_rect.top()),
            QPointF(axis_x, plot_rect.bottom())
        )

        scale_font = QFont()
        scale_font.setPixelSize(8)
        painter.setFont(scale_font)
        painter.setPen(axis_color)

        def tick_text(value):
            if value == 0.5:
                return "½"
            return str(int(value)) if float(value).is_integer() else str(value)

        for value in x_ticks:
            tick_x = map_x(value)
            painter.drawLine(
                QPointF(tick_x, axis_y - 2.0),
                QPointF(tick_x, axis_y + 2.0)
            )
            painter.drawText(
                QRectF(tick_x - 9.0, plot_rect.bottom() + 2.0, 18.0, 9.0),
                Qt.AlignmentFlag.AlignCenter,
                tick_text(value)
            )

        for value in y_ticks:
            tick_y = map_y(value)
            painter.drawLine(
                QPointF(axis_x - 2.0, tick_y),
                QPointF(axis_x + 2.0, tick_y)
            )
            painter.drawText(
                QRectF(chart_rect.left(), tick_y - 5.0, 12.0, 10.0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                tick_text(value)
            )

        curve_path = QPainterPath()
        sample_count = 80

        for index in range(sample_count + 1):
            x_value = x_min + (
                (x_max - x_min) * index / sample_count
            )
            point = QPointF(
                map_x(x_value),
                map_y(function(x_value))
            )
            if index == 0:
                curve_path.moveTo(point)
            else:
                curve_path.lineTo(point)

        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(25, 105, 165), 1.8))
        painter.drawPath(curve_path)
        painter.restore()

    def text(self, key, fallback, **values):
        """Liefert einen sichtbaren Text in der gewählten Programmsprache."""

        if callable(self.translator):
            return self.translator(key, **values)

        return fallback.format(**values)

    def preview_number(self, value):
        """Uses dialog precision only for temporary read-only previews."""
        if self.display_decimals is None:
            return format_number(value)
        number = float(value)
        if abs(number) < 0.5 * (10.0 ** -self.display_decimals):
            number = 0.0
        text = f"{number:.{self.display_decimals}f}"
        return text.replace(".", ",")

    def set_ports_visible(self, visible):
        self.ports_visible = bool(visible)
        self.hovered_port = None
        self.update()

    def set_name_visible(self, visible):
        self.name_visible = bool(visible)
        self.update()

    def set_io_fields_visible(self, visible):
        visible = bool(visible)
        if visible == self.io_fields_visible:
            return
        self.prepareGeometryChange()
        self.io_fields_visible = visible
        self.update()

    def set_external_input_value(
        self, value, is_raw=False, unit="", is_binary=False
    ):
        self.external_input_value = float(value)
        self.external_input_is_raw = bool(is_raw)
        self.external_input_is_binary = bool(is_binary)
        self.external_input_unit = str(unit).strip()
        self.update()

    def set_external_output_values(
        self,
        actual_value=None,
        target_value=None,
        is_raw=False,
        unit="",
        is_binary=False
    ):
        self.external_output_value = (
            None if actual_value is None else float(actual_value)
        )
        self.external_target_value = (
            None if target_value is None else float(target_value)
        )
        self.external_output_is_raw = bool(is_raw)
        self.external_output_is_binary = bool(is_binary)
        self.external_output_unit = str(unit).strip()
        self.update()

    def clear_external_values(self):
        self.external_input_value = None
        self.external_input_is_raw = False
        self.external_input_is_binary = False
        self.external_input_unit = ""
        self.external_output_value = None
        self.external_target_value = None
        self.external_output_is_raw = False
        self.external_output_is_binary = False
        self.external_output_unit = ""
        self.update()

    def apply_color_settings(self, colors):
        """Wendet die projektbezogene Farbpalette auf das Neuron an."""

        self.background_brush = QBrush(
            QColor(colors["neuron_background"])
        )
        self.input_header_brush = QBrush(
            QColor(colors["input_header"])
        )
        self.hidden_header_brush = QBrush(
            QColor(colors["hidden_header"])
        )
        self.output_header_brush = QBrush(
            QColor(colors["output_header"])
        )
        self.input_port_brush = QBrush(
            QColor(colors["input_port"])
        )
        self.output_port_brush = QBrush(
            QColor(colors["output_port"])
        )
        self.selected_border_pen = QPen(
            QColor(colors["selection"]),
            3
        )
        self.update()

    def add_incoming_connection(self, connection):
        """
        Fügt dem Neuron eine eingehende Verbindung hinzu.
        """

        if connection not in self.incoming_connections:
            self.incoming_connections.append(connection)

    def remove_incoming_connection(self, connection):
        """
        Entfernt eine eingehende Verbindung vom Neuron.
        """

        if connection in self.incoming_connections:
            self.incoming_connections.remove(connection)

    def add_outgoing_connection(self, connection):
        """
        Fügt dem Neuron eine ausgehende Verbindung hinzu.
        """

        if connection not in self.outgoing_connections:
            self.outgoing_connections.append(connection)

    def remove_outgoing_connection(self, connection):
        """
        Entfernt eine ausgehende Verbindung vom Neuron.
        """

        if connection in self.outgoing_connections:
            self.outgoing_connections.remove(connection)

    def update_connections(self):
        """
        Aktualisiert die Position aller Verbindungen,
        die mit diesem Neuron verbunden sind.
        """

        connections = (
            self.incoming_connections
            + self.outgoing_connections
        )

        for connection in connections:
            connection.update_position()

    def reset_runtime_values(self):
        """
        Setzt alle Laufzeitwerte des Neurons zurück.
        """

        self.input_value = 0.0
        self.sum_value = 0.0
        self.output_value = 0.0
        self.target_value = 0.0
        self.error_value = 0.0
        self.delta_value = 0.0
        self.clear_external_values()

        self.update()

    def get_body_rect(self):
        """
        Liefert das eigentliche Rechteck des Neurons
        ohne den zusätzlichen Bereich der Ports.
        """

        return QRectF(
            0.0,
            0.0,
            self.width,
            self.height
        )

    def get_center_position(self):
        """
        Liefert den Mittelpunkt des Neurons
        in Szenenkoordinaten.
        """

        return self.mapToScene(
            self.get_body_rect().center()
        )

    def get_radius(self):
        """
        Liefert die halbe Höhe des Neurons.
        """

        return self.height / 2.0

    def get_input_port_local_position(self):
        """
        Liefert die lokale Position des Eingangsports.
        """

        rect = self.get_body_rect()

        return QPointF(
            rect.left(),
            rect.center().y()
        )

    def get_output_port_local_position(self):
        """
        Liefert die lokale Position des Ausgangsports.
        """

        rect = self.get_body_rect()

        return QPointF(
            rect.right(),
            rect.center().y()
        )

    def get_input_port_position(self):
        """
        Liefert die Position des Eingangsports
        in Szenenkoordinaten.
        """

        return self.mapToScene(
            self.get_input_port_local_position()
        )

    def get_output_port_position(self):
        """
        Liefert die Position des Ausgangsports
        in Szenenkoordinaten.
        """

        return self.mapToScene(
            self.get_output_port_local_position()
        )

    def is_input_port_at(self, scene_position):
        """
        Prüft, ob sich die angegebene Szenenposition
        auf dem Eingangsport befindet.
        """

        distance = QLineF(
            self.get_input_port_position(),
            scene_position
        ).length()

        return distance <= self.port_radius + 3.0

    def is_output_port_at(self, scene_position):
        """
        Prüft, ob sich die angegebene Szenenposition
        auf dem Ausgangsport befindet.
        """

        distance = QLineF(
            self.get_output_port_position(),
            scene_position
        ).length()

        return distance <= self.port_radius + 3.0

    def get_header_brush(self):
        """
        Liefert die Farbe des Kopfbereiches
        abhängig vom Neuronentyp.
        """

        if self.neuron_type == NeuronType.INPUT:
            return self.input_header_brush

        if self.neuron_type == NeuronType.OUTPUT:
            return self.output_header_brush

        return self.hidden_header_brush

    def boundingRect(self):
        """
        Liefert den vollständigen Zeichenbereich
        einschließlich der Anschlussports.
        """

        margin = self.port_radius + 3.0

        bounds = self.get_body_rect().adjusted(
            -margin,
            -margin,
            margin,
            margin
        )

        if self.io_fields_visible:
            extension = (
                self.external_field_width
                + self.external_field_gap
                + margin
            )
            if self.neuron_type == NeuronType.INPUT:
                bounds.setLeft(-extension)
            elif self.neuron_type == NeuronType.OUTPUT:
                bounds.setRight(self.width + extension)

        return bounds

    def get_external_field_rect(self):
        port_y = self.get_body_rect().center().y()
        has_target = self.external_target_value is not None
        binary = (
            self.external_input_is_binary
            if self.neuron_type == NeuronType.INPUT
            else self.external_output_is_binary
        )
        line_count = 1 + int(has_target) + int(binary)
        field_height = 34.0 + max(0, line_count - 1) * 18.0
        field_y = port_y - field_height / 2.0

        if self.neuron_type == NeuronType.INPUT:
            field_x = -self.external_field_gap - self.external_field_width
        else:
            field_x = self.width + self.external_field_gap

        return QRectF(
            field_x,
            field_y,
            self.external_field_width,
            field_height
        )

    def paint_external_value_field(self, painter):
        if (
            not self.io_fields_visible
            or self.neuron_type not in (NeuronType.INPUT, NeuronType.OUTPUT)
        ):
            return

        field_rect = self.get_external_field_rect()
        port_position = (
            self.get_input_port_local_position()
            if self.neuron_type == NeuronType.INPUT
            else self.get_output_port_local_position()
        )
        field_edge = QPointF(
            field_rect.right()
            if self.neuron_type == NeuronType.INPUT
            else field_rect.left(),
            field_rect.center().y()
        )

        painter.setPen(QPen(QColor(90, 90, 90), 1.5))
        painter.drawLine(field_edge, port_position)

        painter.setBrush(QBrush(QColor(248, 250, 252)))
        painter.setPen(QPen(QColor(90, 105, 120), 1.2))
        painter.drawRoundedRect(field_rect, 6.0, 6.0)

        field_font = QFont()
        field_font.setPointSize(8)
        field_font.setBold(True)
        painter.setFont(field_font)
        painter.setPen(Qt.GlobalColor.black)

        if self.neuron_type == NeuronType.INPUT:
            value = (
                self.input_value
                if self.external_input_value is None
                else self.external_input_value
            )
            prefix = self.text("canvas.value.raw", "Roh") if self.external_input_is_raw else self.text("canvas.value.input", "Eingabe")
            unit_text = (
                f" {self.external_input_unit}"
                if self.external_input_unit
                else ""
            )
            lines = [f"{prefix}: {format_number(value)}{unit_text}"]
            if self.external_input_is_binary:
                lines.append(
                    self.text("binary.on", "Ein")
                    if value > 0.5
                    else self.text("binary.off", "Aus")
                )
                lines[-1] = ("● " if value > 0.5 else "○ ") + lines[-1]
            text = "\n".join(lines)
        else:
            value = (
                self.output_value
                if self.external_output_value is None
                else self.external_output_value
            )
            prefix = self.text("canvas.value.actual", "Ist") if self.external_target_value is not None else self.text("canvas.value.output", "Ausgabe")
            unit_text = (
                f" {self.external_output_unit}"
                if self.external_output_unit
                else ""
            )
            lines = [f"{prefix}: {format_number(value)}{unit_text}"]
            if self.external_target_value is not None:
                lines.append(
                    f"{self.text('canvas.value.target', 'Soll')}: {format_number(self.external_target_value)}{unit_text}"
                )
            if self.external_output_is_binary:
                decision = (
                    self.text("binary.on", "Ein")
                    if value > 0.5
                    else self.text("binary.off", "Aus")
                )
                lines.append(("● " if value > 0.5 else "○ ") + decision)
            text = "\n".join(lines)

        painter.drawText(
            field_rect.adjusted(7.0, 3.0, -7.0, -3.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text
        )

    def paint(self, painter, option, widget=None):
        """
        Zeichnet das Neuron einschließlich
        Konfiguration und Laufzeitwerten.
        """

        body_rect = self.get_body_rect()
        header_separator_y = 38.0
        runtime_separator_y = 118.0

        border_pen = (
            self.selected_border_pen
            if self.isSelected()
            else self.normal_border_pen
        )

        self.paint_external_value_field(painter)

        # Grundfläche
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background_brush)

        painter.drawRoundedRect(
            body_rect,
            self.corner_radius,
            self.corner_radius
        )

        # Farbiger Kopfbereich
        painter.save()

        painter.setClipRect(
            QRectF(
                body_rect.left(),
                body_rect.top(),
                body_rect.width(),
                header_separator_y
            )
        )

        painter.setBrush(
            self.get_header_brush()
        )

        painter.drawRoundedRect(
            body_rect,
            self.corner_radius,
            self.corner_radius
        )

        painter.restore()

        # Äußerer Rahmen
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(
            body_rect,
            self.corner_radius,
            self.corner_radius
        )

        separator_pen = QPen(
            QColor(120, 120, 120),
            1
        )

        painter.setPen(separator_pen)

        painter.drawLine(
            QPointF(
                body_rect.left(),
                header_separator_y
            ),
            QPointF(
                body_rect.right(),
                header_separator_y
            )
        )

        if self.values_visible or (
            self.activation_chart_visible
            and self.neuron_type != NeuronType.INPUT
        ):
            painter.drawLine(
                QPointF(
                    body_rect.left(),
                    runtime_separator_y
                ),
                QPointF(
                    body_rect.right(),
                    runtime_separator_y
                )
            )

        # Name
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)

        painter.setFont(name_font)
        painter.setPen(Qt.GlobalColor.black)

        if self.name_visible:
            painter.drawText(
                QRectF(
                    10.0,
                    5.0,
                    self.width - 20.0,
                    28.0
                ),
                Qt.AlignmentFlag.AlignCenter,
                self.name
            )

        information_font = QFont()
        information_font.setPointSize(9)

        painter.setFont(information_font)

        painter.drawText(
            QRectF(
                10.0,
                42.0,
                self.width - 20.0,
                22.0
            ),
            (
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            ),
            f"{self.text('canvas.neuron.type', 'Typ')}: {self.neuron_type.value}"
        )

        if self.neuron_type != NeuronType.INPUT:
            painter.drawText(
                QRectF(
                    10.0,
                    66.0,
                    self.width - 20.0,
                    22.0
                ),
                (
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter
                ),
                f"{self.text('canvas.neuron.activation', 'Aktivierung')}: {self.activation_function}"
            )

            if self.values_visible or self.preview_show_bias:
                painter.drawText(
                    QRectF(
                        10.0,
                        90.0,
                        self.width - 20.0,
                        22.0
                    ),
                    (
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignVCenter
                    ),
                    f"Bias B: {self.preview_number(self.bias)}"
                )

        # Laufzeitwerte
        if self.preview_message:
            message_font = QFont()
            message_font.setPointSize(8)
            message_font.setItalic(True)
            painter.setFont(message_font)
            painter.setPen(QPen(QColor(95, 95, 95)))
            painter.drawText(
                QRectF(10.0, 88.0, self.width - 20.0, 22.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.preview_message
            )

        if self.values_visible:
            runtime_font = QFont()
            runtime_font.setPointSize(
                8
                if (
                    self.activation_chart_visible
                    and self.neuron_type != NeuronType.INPUT
                )
                else 9
            )
            runtime_font.setBold(True)

            painter.setFont(runtime_font)

            if self.neuron_type == NeuronType.INPUT:
                first_runtime_text = (
                    f"X = {self.preview_number(self.input_value)}"
                )

            else:
                first_runtime_text = (
                    f"Σ = {self.preview_number(self.sum_value)}"
                )

            runtime_text_width = (
                76.0
                if (
                    self.activation_chart_visible
                    and self.neuron_type != NeuronType.INPUT
                )
                else self.width - 20.0
            )

            if self.preview_show_first_value:
                painter.drawText(
                    QRectF(10.0, 130.0, runtime_text_width, 20.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    first_runtime_text
                )

            if self.preview_show_output:
                painter.drawText(
                QRectF(
                    10.0,
                    153.0,
                    runtime_text_width,
                    20.0
                ),
                (
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter
                ),
                    f"Y = {self.preview_number(self.output_value)}"
                )

        self.paint_activation_chart(painter)

        # Anschlussports
        if self.ports_visible or self.hovered_port is not None:
            painter.setPen(
                QPen(
                    Qt.GlobalColor.black,
                    1
                )
            )

            if self.hovered_port == "input":
                painter.setBrush(self.hover_port_brush)
            else:
                painter.setBrush(self.input_port_brush)

            painter.drawEllipse(
                self.get_input_port_local_position(),
                self.port_radius,
                self.port_radius
            )

            if self.hovered_port == "output":
                painter.setBrush(self.hover_port_brush)
            else:
                painter.setBrush(self.output_port_brush)

            painter.drawEllipse(
                self.get_output_port_local_position(),
                self.port_radius,
                self.port_radius
            )

    def hoverMoveEvent(self, event):
        """
        Hebt den Port hervor, über dem sich
        der Mauszeiger befindet.
        """

        position = event.pos()

        input_distance = QLineF(
            position,
            self.get_input_port_local_position()
        ).length()

        output_distance = QLineF(
            position,
            self.get_output_port_local_position()
        ).length()

        if input_distance <= self.port_radius + 3.0:
            new_hovered_port = "input"

        elif output_distance <= self.port_radius + 3.0:
            new_hovered_port = "output"

        else:
            new_hovered_port = None

        if new_hovered_port != self.hovered_port:
            self.hovered_port = new_hovered_port
            self.update()

        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """
        Entfernt die Hervorhebung der Ports.
        """

        if self.hovered_port is not None:
            self.hovered_port = None
            self.update()

        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """
        Reagiert auf Auswahl- und Positionsänderungen.
        """

        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged
        ):
            self.update()

        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
        ):
            scene = self.scene()
            fast_group_move = bool(
                getattr(scene, "fast_group_move_active", False)
            )

            if not fast_group_move:
                self.update_connections()

                self.position_changed.emit(
                    value.x(),
                    value.y()
                )

        return super().itemChange(change, value)
