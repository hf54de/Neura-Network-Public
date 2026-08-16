# -------------------------------------------------------------------------------------------------
# Datei: connection.py
# Zweck: Stellt gewichtete Verbindungen zwischen Neuronen grafisch und fachlich dar.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem
)


class Connection(QGraphicsPathItem):
    """
    Grafische Verbindung zwischen zwei Neuronen.

    Zuständig für:
        - Startneuron
        - Zielneuron
        - Gewicht
        - Gewichtsanzeige
        - kubische Bézier-Kurve
        - grafische Darstellung
        - Pfeilspitze
        - Aktualisierung der Position
        - Abmeldung von beiden Neuronen
    """

    # Verhindert, dass bei vielen gleichzeitig aktualisierten
    # Verbindungen dieselbe Szene mehrfach direkt hintereinander
    # neu angeordnet wird.
    _pending_label_layout_scenes = set()

    def __init__(
        self,
        connection_id,
        source_neuron,
        target_neuron,
        weight=1.0,
        translator=None
    ):

        super().__init__()

        self.id = connection_id
        self.source_neuron = source_neuron
        self.target_neuron = target_neuron
        self.translator = translator

        self._weight = float(weight)

        # Sichtbarkeit der Gewichtsanzeige.
        # Die Verbindungslinie und der Pfeil bleiben davon unberührt.
        self.weight_label_visible = True

        # Farbliche und gewichtete Darstellung der Verbindungslinie.
        self.weight_visualization_enabled = True
        self.positive_weight_color = QColor(40, 112, 175)
        self.negative_weight_color = QColor(195, 65, 55)
        self.neutral_weight_color = QColor(105, 105, 105)
        self.selection_color = QColor(208, 0, 0)
        self.weight_visualization_zero_limit = 0.000001
        self.weight_visualization_maximum_magnitude = 10.0
        self.weight_visualization_minimum_width = 1.5
        self.weight_visualization_maximum_width = 5.0

        self.arrow_length = 12.0
        self.arrow_width = 8.0
        self.selection_width = 12.0

        # Einstellungen der Gewichtsanzeige
        self.weight_label_padding_x = 7.0
        self.weight_label_padding_y = 4.0
        self.weight_label_short_distance = 140.0
        self.weight_label_short_offset_y = -18.0

        # Einstellungen der automatischen Kollisionsvermeidung.
        self.weight_label_collision_margin = 4.0

        # Die gefundene Position entlang der Verbindung bleibt auch
        # erhalten, wenn sich während des Trainings nur der
        # Gewichtstext ändert.
        self.weight_label_current_path_percent = 0.5

        # Wird benötigt, damit nach dem Entfernen einer Verbindung
        # die verbleibenden Gewichtsanzeigen neu verteilt werden.
        self._last_scene = None

        self.arrow_polygon = QPolygonF()

        self.weight_font = QFont()
        self.weight_font.setPointSize(9)
        self.weight_font.setBold(True)

        self.weight_text = ""
        # Optional precision used by read-only calculation previews.  The
        # normal editor deliberately keeps its compact one-decimal labels.
        self.display_decimals = None
        self.weight_text_rect = QRectF()
        self.weight_background_rect = QRectF()

        self.normal_pen = QPen(
            Qt.GlobalColor.black,
            2
        )

        self.selected_pen = QPen(
            self.selection_color,
            5
        )

        self.weight_text_pen = QPen(
            Qt.GlobalColor.black,
            1
        )

        self.weight_background_pen = QPen(
            QColor(150, 150, 150),
            1
        )

        self.weight_background_brush = QBrush(
            QColor(255, 255, 255, 255)
        )

        self.setPen(
            self.normal_pen
        )

        self.setBrush(
            Qt.BrushStyle.NoBrush
        )

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
            True
        )

        self.setZValue(-1.0)

        self.source_neuron.add_outgoing_connection(
            self
        )

        self.target_neuron.add_incoming_connection(
            self
        )

        self.update_weight_pen()
        self.update_weight_text()
        self.update_position()

    def set_weight_visualization_enabled(
        self,
        enabled
    ):
        """
        Schaltet die farbliche und nach Betrag skalierte
        Darstellung der Verbindung ein oder aus.
        """

        enabled = bool(
            enabled
        )

        if enabled == self.weight_visualization_enabled:
            return

        self.weight_visualization_enabled = enabled
        self.update_weight_pen()
        self.update()

    def apply_color_settings(self, colors):
        """Wendet die projektbezogenen Verbindungsfarben an."""

        self.positive_weight_color = QColor(
            colors["positive_weight"]
        )
        self.negative_weight_color = QColor(
            colors["negative_weight"]
        )
        self.neutral_weight_color = QColor(
            colors["neutral_weight"]
        )
        self.selection_color = QColor(
            colors["selection"]
        )
        self.update_weight_pen()
        self.update()

    def update_weight_pen(self):
        """
        Bestimmt Farbe und Linienstärke aus dem Gewicht.
        """

        self.prepareGeometryChange()

        invalid_weight = not math.isfinite(
            self._weight
        )

        if invalid_weight:
            line_color = QColor(210, 45, 45)
            line_width = 3.0

        elif self.weight_visualization_enabled:
            if (
                self._weight
                > self.weight_visualization_zero_limit
            ):
                line_color = self.positive_weight_color

            elif (
                self._weight
                < -self.weight_visualization_zero_limit
            ):
                line_color = self.negative_weight_color

            else:
                line_color = self.neutral_weight_color

            normalized_magnitude = min(
                abs(
                    self._weight
                ),
                self.weight_visualization_maximum_magnitude
            ) / self.weight_visualization_maximum_magnitude

            line_width = (
                self.weight_visualization_minimum_width
                + (
                    self.weight_visualization_maximum_width
                    - self.weight_visualization_minimum_width
                )
                * math.sqrt(
                    normalized_magnitude
                )
            )

        else:
            line_color = QColor(
                Qt.GlobalColor.black
            )
            line_width = 2.0

        self.normal_pen = QPen(
            line_color,
            line_width
        )
        self.normal_pen.setCapStyle(
            Qt.PenCapStyle.RoundCap
        )
        self.normal_pen.setJoinStyle(
            Qt.PenJoinStyle.RoundJoin
        )

        if invalid_weight:
            self.normal_pen.setStyle(
                Qt.PenStyle.DashLine
            )

        self.selected_pen = QPen(
            self.selection_color,
            line_width + 3.0
        )
        self.selected_pen.setCapStyle(
            Qt.PenCapStyle.RoundCap
        )
        self.selected_pen.setJoinStyle(
            Qt.PenJoinStyle.RoundJoin
        )

        self.setPen(
            self.selected_pen
            if self.isSelected()
            else self.normal_pen
        )

    def set_weight_label_visible(
        self,
        visible
    ):
        """
        Blendet die Gewichtsanzeige ein oder aus.

        Verbindungslinie, Pfeilspitze und Gewichtswert
        bleiben vollständig erhalten.
        """

        visible = bool(
            visible
        )

        if visible == self.weight_label_visible:
            return

        old_scene_rect = self.sceneBoundingRect()

        self.prepareGeometryChange()

        self.weight_label_visible = visible

        if visible:
            self.request_weight_label_layout()

        self.update()

        if self.scene() is not None:
            self.scene().update(
                old_scene_rect.united(
                    self.sceneBoundingRect()
                )
            )

    @property
    def weight(self):
        """
        Liefert das Gewicht der Verbindung.
        """

        return self._weight

    @weight.setter
    def weight(self, value):
        """
        Setzt das Gewicht und aktualisiert
        die sichtbare Gewichtsanzeige.
        """

        self._weight = float(value)

        self.update_weight_pen()
        self.update_weight_text()
        self.update()

    def update_weight_text(self):
        """
        Aktualisiert den Text der Gewichtsanzeige.
        """

        self.prepareGeometryChange()

        if math.isfinite(self._weight):
            decimals = 1 if self.display_decimals is None else self.display_decimals
            self.weight_text = f"W{self.id} = {self._weight:.{decimals}f}"
        else:
            invalid = (
                self.translator("canvas.connection.invalid")
                if callable(self.translator)
                else "ungültig"
            )
            self.weight_text = f"W{self.id} = {invalid}"

        self.update_weight_label_position()
        self.request_weight_label_layout()

    def calculate_weight_label_rects(
        self,
        label_center
    ):
        """
        Berechnet Text- und Hintergrundrechteck für
        den angegebenen Mittelpunkt der Gewichtsanzeige.
        """

        font_metrics = QFontMetricsF(
            self.weight_font
        )

        text_bounds = font_metrics.boundingRect(
            self.weight_text
        )

        text_width = text_bounds.width()
        text_height = text_bounds.height()

        text_rect = QRectF(
            label_center.x() - text_width / 2.0,
            label_center.y() - text_height / 2.0,
            text_width,
            text_height
        )

        background_rect = text_rect.adjusted(
            -self.weight_label_padding_x,
            -self.weight_label_padding_y,
            self.weight_label_padding_x,
            self.weight_label_padding_y
        )

        return (
            text_rect,
            background_rect
        )

    def get_weight_label_center(
        self,
        path_percent=0.5
    ):
        """
        Liefert eine Position entlang der Verbindungskurve.
        """

        path = self.path()

        if path.isEmpty():
            return None

        path_percent = max(
            0.0,
            min(
                1.0,
                float(path_percent)
            )
        )

        label_center = path.pointAtPercent(
            path_percent
        )

        start_point = path.pointAtPercent(
            0.0
        )

        end_point = path.pointAtPercent(
            1.0
        )

        direct_distance = math.hypot(
            end_point.x() - start_point.x(),
            end_point.y() - start_point.y()
        )

        if (
            direct_distance
            < self.weight_label_short_distance
        ):
            label_center = QPointF(
                label_center.x(),
                label_center.y()
                + self.weight_label_short_offset_y
            )

        return label_center

    def get_base_weight_label_center(self):
        """
        Liefert die bevorzugte Mitte der Gewichtsanzeige.
        """

        return self.get_weight_label_center(
            0.5
        )

    def set_weight_label_center(
        self,
        label_center
    ):
        """
        Setzt die Gewichtsanzeige auf den angegebenen Mittelpunkt.
        """

        (
            self.weight_text_rect,
            self.weight_background_rect
        ) = self.calculate_weight_label_rects(
            label_center
        )

    def update_weight_label_position(self):
        """
        Aktualisiert die Gewichtsanzeige an ihrer bisherigen
        kollisionsfreien Position.

        Die von der Kollisionsvermeidung ermittelte Position
        entlang der Kurve bleibt erhalten. Dadurch springen die
        W-Kästchen während des Trainings nicht bei jeder
        Gewichtsänderung an eine andere Stelle.
        """

        label_center = self.get_weight_label_center(
            self.weight_label_current_path_percent
        )

        if label_center is None:
            self.weight_label_current_path_percent = 0.5
            self.weight_text_rect = QRectF()
            self.weight_background_rect = QRectF()
            return

        self.set_weight_label_center(
            label_center
        )

    @classmethod
    def arrange_weight_labels(
        cls,
        scene
    ):
        """
        Verteilt alle Gewichtsanzeigen einer Szene so,
        dass sich ihre Kästchen nicht überschneiden.

        Die Mitte der eigenen Verbindung bleibt bevorzugt.
        Bei einer Kollision werden weitere Positionen entlang
        derselben Kurve geprüft. Die Anzeige verlässt ihre
        Verbindungslinie dabei nicht.
        """

        if scene is None:
            return

        all_connections = [
            item
            for item in scene.items()
            if isinstance(
                item,
                cls
            )
        ]

        connections = [
            connection
            for connection in all_connections
            if connection.weight_label_visible
        ]

        # Ausgeblendete Beschriftungen nehmen an der
        # Kollisionsvermeidung nicht teil.
        for connection in all_connections:
            if connection.weight_label_visible:
                continue

            connection.weight_label_current_path_percent = 0.5

        connections.sort(
            key=lambda connection: connection.id
        )

        occupied_scene_rects = []
        old_scene_rects = []

        connection_scene_paths = {
            connection: connection.mapToScene(
                connection.path()
            )
            for connection in connections
        }

        candidate_path_percents = [
            0.50,
            0.46,
            0.54,
            0.42,
            0.58,
            0.38,
            0.62,
            0.34,
            0.66,
            0.30,
            0.70,
            0.26,
            0.74,
            0.22,
            0.78,
            0.18,
            0.82,
            0.14,
            0.86
        ]

        for connection in connections:
            old_scene_rects.append(
                connection.sceneBoundingRect()
            )

            base_center = connection.get_weight_label_center(
                0.5
            )

            if base_center is None:
                connection.prepareGeometryChange()
                connection.weight_label_current_path_percent = 0.5
                connection.weight_text_rect = QRectF()
                connection.weight_background_rect = QRectF()
                continue

            (
                _,
                base_background_rect
            ) = connection.calculate_weight_label_rects(
                base_center
            )

            selected_center = base_center
            selected_path_percent = 0.5
            selected_scene_rect = (
                connection.mapRectToScene(
                    base_background_rect
                )
            )

            best_score = None

            for path_percent in candidate_path_percents:
                candidate_center = (
                    connection.get_weight_label_center(
                        path_percent
                    )
                )

                if candidate_center is None:
                    continue

                (
                    _,
                    candidate_background_rect
                ) = connection.calculate_weight_label_rects(
                    candidate_center
                )

                candidate_scene_rect = (
                    connection.mapRectToScene(
                        candidate_background_rect
                    )
                )

                collision_test_rect = (
                    candidate_scene_rect.adjusted(
                        -connection.weight_label_collision_margin,
                        -connection.weight_label_collision_margin,
                        connection.weight_label_collision_margin,
                        connection.weight_label_collision_margin
                    )
                )

                label_collision_count = sum(
                    1
                    for occupied_rect in occupied_scene_rects
                    if collision_test_rect.intersects(
                        occupied_rect
                    )
                )

                foreign_line_crossings = sum(
                    1
                    for other_connection, scene_path
                    in connection_scene_paths.items()
                    if (
                        other_connection is not connection
                        and scene_path.intersects(
                            collision_test_rect
                        )
                    )
                )

                candidate_score = (
                    label_collision_count,
                    foreign_line_crossings,
                    abs(path_percent - 0.5)
                )

                if (
                    best_score is None
                    or candidate_score < best_score
                ):
                    best_score = candidate_score
                    selected_center = candidate_center
                    selected_path_percent = path_percent
                    selected_scene_rect = collision_test_rect

            connection.prepareGeometryChange()

            connection.weight_label_current_path_percent = (
                selected_path_percent
            )

            connection.set_weight_label_center(
                selected_center
            )

            occupied_scene_rects.append(
                selected_scene_rect
            )

            connection.update()

        if old_scene_rects:
            update_rect = old_scene_rects[0]

            for old_rect in old_scene_rects[1:]:
                update_rect = update_rect.united(
                    old_rect
                )

            for connection in connections:
                update_rect = update_rect.united(
                    connection.sceneBoundingRect()
                )

            scene.update(
                update_rect
            )

    @classmethod
    def request_scene_weight_label_layout(
        cls,
        scene
    ):
        """
        Plant eine gebündelte Neuanordnung aller
        Gewichtsanzeigen der angegebenen Szene.
        """

        if scene is None:
            return

        scene_key = id(
            scene
        )

        if scene_key in cls._pending_label_layout_scenes:
            return

        cls._pending_label_layout_scenes.add(
            scene_key
        )

        def perform_layout():
            cls._pending_label_layout_scenes.discard(
                scene_key
            )

            try:
                cls.arrange_weight_labels(
                    scene
                )

            except RuntimeError:
                # Die Szene kann während des verzögerten Aufrufs
                # bereits geschlossen oder zerstört worden sein.
                pass

        QTimer.singleShot(
            0,
            perform_layout
        )

    def request_weight_label_layout(self):
        """
        Fordert für die aktuelle Szene eine gebündelte
        Kollisionsprüfung aller Gewichtsanzeigen an.
        """

        self.request_scene_weight_label_layout(
            self.scene()
        )

    def update_position(self):
        """
        Aktualisiert die Bézier-Kurve zwischen den
        Anschlussports der beiden Neuronen.
        """

        old_scene_rect = self.sceneBoundingRect()

        start_point = (
            self.source_neuron
            .get_output_port_position()
        )

        end_point = (
            self.target_neuron
            .get_input_port_position()
        )

        horizontal_distance = abs(
            end_point.x() - start_point.x()
        )

        control_offset = max(
            60.0,
            min(
                horizontal_distance * 0.5,
                180.0
            )
        )

        control_point_1 = QPointF(
            start_point.x() + control_offset,
            start_point.y()
        )

        control_point_2 = QPointF(
            end_point.x() - control_offset,
            end_point.y()
        )

        path = QPainterPath()
        path.moveTo(
            start_point
        )

        path.cubicTo(
            control_point_1,
            control_point_2,
            end_point
        )

        self.prepareGeometryChange()

        self.setPath(
            path
        )

        self.update_arrow_polygon(
            control_point_2,
            end_point
        )

        self.update_weight_label_position()
        self.request_weight_label_layout()

        self.update()

        if self.scene() is not None:
            new_scene_rect = self.sceneBoundingRect()

            self.scene().update(
                old_scene_rect.united(
                    new_scene_rect
                )
            )

    def update_arrow_polygon(
        self,
        control_point,
        arrow_tip
    ):
        """
        Berechnet die Pfeilspitze anhand der Tangente
        am Ende der Bézier-Kurve.
        """

        direction_x = (
            arrow_tip.x()
            - control_point.x()
        )

        direction_y = (
            arrow_tip.y()
            - control_point.y()
        )

        direction_length = math.hypot(
            direction_x,
            direction_y
        )

        if direction_length == 0.0:
            self.arrow_polygon = QPolygonF()
            return

        unit_x = (
            direction_x
            / direction_length
        )

        unit_y = (
            direction_y
            / direction_length
        )

        perpendicular_x = -unit_y
        perpendicular_y = unit_x

        arrow_base_center = QPointF(
            arrow_tip.x()
            - unit_x * self.arrow_length,
            arrow_tip.y()
            - unit_y * self.arrow_length
        )

        arrow_left = QPointF(
            arrow_base_center.x()
            + perpendicular_x
            * self.arrow_width
            / 2.0,
            arrow_base_center.y()
            + perpendicular_y
            * self.arrow_width
            / 2.0
        )

        arrow_right = QPointF(
            arrow_base_center.x()
            - perpendicular_x
            * self.arrow_width
            / 2.0,
            arrow_base_center.y()
            - perpendicular_y
            * self.arrow_width
            / 2.0
        )

        self.arrow_polygon = QPolygonF(
            [
                arrow_tip,
                arrow_left,
                arrow_right
            ]
        )

    def boundingRect(self):
        """
        Liefert den vollständigen Zeichenbereich
        einschließlich Kurve, Pfeilspitze,
        Gewichtsanzeige und Auswahlbereich.
        """

        rect = super().boundingRect()

        if not self.arrow_polygon.isEmpty():
            rect = rect.united(
                self.arrow_polygon.boundingRect()
            )

        if (
            self.weight_label_visible
            and not self.weight_background_rect.isEmpty()
        ):
            rect = rect.united(
                self.weight_background_rect
            )

        margin = max(
            self.arrow_width,
            self.selection_width
        )

        return rect.adjusted(
            -margin,
            -margin,
            margin,
            margin
        )

    def shape(self):
        """
        Vergrößert den unsichtbaren Auswahlbereich
        der Verbindung, ohne die Kurve breiter darzustellen.
        """

        stroker = QPainterPathStroker()
        stroker.setWidth(
            self.selection_width
        )

        selection_path = stroker.createStroke(
            self.path()
        )

        if not self.arrow_polygon.isEmpty():
            arrow_path = QPainterPath()

            arrow_path.addPolygon(
                self.arrow_polygon
            )

            arrow_path.closeSubpath()

            selection_path.addPath(
                arrow_path
            )

        if (
            self.weight_label_visible
            and not self.weight_background_rect.isEmpty()
        ):
            selection_path.addRect(
                self.weight_background_rect
            )

        return selection_path

    def itemChange(self, change, value):
        """
        Passt die Darstellung an den Auswahlstatus an.
        """

        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemSelectedChange
        ):
            if value:
                self.setPen(
                    self.selected_pen
                )
            else:
                self.setPen(
                    self.normal_pen
                )

            self.update()

        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged
        ):
            current_scene = self.scene()

            if current_scene is not None:
                self._last_scene = current_scene

                self.request_scene_weight_label_layout(
                    current_scene
                )

            elif self._last_scene is not None:
                previous_scene = self._last_scene
                self._last_scene = None

                self.request_scene_weight_label_layout(
                    previous_scene
                )

        return super().itemChange(
            change,
            value
        )

    def paint(self, painter, option, widget=None):
        """
        Zeichnet die Bézier-Kurve, die Pfeilspitze
        und das Gewicht der Verbindung.
        """

        painter.save()

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        # Eine ausgewählte Verbindung erhält eine goldene
        # Kontur. Die Gewichtsfarbe bleibt darüber sichtbar.
        if self.isSelected():
            painter.setPen(
                self.selected_pen
            )
            painter.drawPath(
                self.path()
            )

        # Bézier-Kurve in der zum Gewicht gehörenden Farbe.
        painter.setPen(
            self.normal_pen
        )

        painter.drawPath(
            self.path()
        )

        # Pfeilspitze
        if not self.arrow_polygon.isEmpty():
            painter.setBrush(
                QBrush(
                    self.normal_pen.color()
                )
            )

            painter.drawPolygon(
                self.arrow_polygon
            )
        #-------------------------------------------------------------------------
        # Hintergrund der Gewichtsanzeige
        if (
            self.weight_label_visible
            and not self.weight_background_rect.isEmpty()
        ):

            # Vollständig deckende weiße Grundfläche.
            # Dadurch kann die Verbindungslinie nicht
            # durch die Gewichtsanzeige hindurchscheinen.
            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.setBrush(
                self.weight_background_brush
            )

            painter.drawRect(
                self.weight_background_rect.adjusted(
                    -1.0,
                    -1.0,
                    1.0,
                    1.0
                )
            )

            # Sichtbarer abgerundeter Rahmen
            painter.setPen(
                self.weight_background_pen
            )

            painter.setBrush(
                self.weight_background_brush
            )

            painter.drawRoundedRect(
                self.weight_background_rect,
                4.0,
                4.0
            )

            # Gewichtstext
            painter.setFont(
                self.weight_font
            )

            painter.setPen(
                self.weight_text_pen
            )

            painter.setBrush(
                Qt.BrushStyle.NoBrush
            )

            painter.drawText(
                self.weight_text_rect,
                (
                    Qt.AlignmentFlag.AlignCenter
                    | Qt.AlignmentFlag.AlignVCenter
                ),
                self.weight_text
            )

        painter.restore()

    def disconnect(self):
        """
        Entfernt die Verbindung aus den Verbindungslisten
        des Start- und Zielneurons.
        """

        self.source_neuron.remove_outgoing_connection(
            self
        )

        self.target_neuron.remove_incoming_connection(
            self
        )
