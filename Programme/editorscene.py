# -------------------------------------------------------------------------------------------------
# Datei: editorscene.py
# Zweck: Verwaltet Netzwerkobjekte, Auswahl und Bearbeitung auf der Zeichenfläche.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QTransform
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QMenu
)

from commentitem import CommentItem
from connection import Connection
from connectionpreview import ConnectionPreview
from network import NeuralNetwork
from neuron import Neuron
from language import LanguageManager


class EditorScene(QGraphicsScene):
    """
    Verwaltet die komplette Zeichenfläche.

    Zuständig für:
        - grafische Darstellung
        - Mausbedienung
        - Einzel- und Mehrfachauswahl
        - gemeinsames Verschieben ausgewählter Neuronen
        - Erzeugen und Löschen grafischer Objekte
        - Verbindungserstellung per Maus

    Die fachliche Verwaltung der Neuronen und
    Verbindungen übernimmt NeuralNetwork.
    """

    # Signal: Ein Objekt wurde ausgewählt.
    object_selected = Signal(object)

    # Signal: Die Position eines Objektes wurde geändert.
    object_position_changed = Signal(object)

    # Signal: Der Inhalt der Szene wurde geändert.
    scene_content_changed = Signal()

    # Signal: Die geometrische Ausdehnung der Szene
    # muss nach einer abgeschlossenen Änderung geprüft werden.
    scene_geometry_changed = Signal()

    # Löschwünsche laufen über das Hauptfenster, damit dort bei
    # Ein- und Ausgabeneuronen vorab auf Datenzuordnungen hingewiesen wird.
    delete_requested = Signal(object)

    # Das kompakte Bearbeitungsfenster wird vom Hauptfenster geöffnet.
    edit_neuron_requested = Signal(object)

    # Kommentare erhalten denselben kompakten Bearbeitungsweg.
    edit_comment_requested = Signal(object)

    def __init__(self, language_manager=None):

        super().__init__()

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        # Fachliches Netzwerkmodell
        self.network = NeuralNetwork()

        # Nächste freie Neuronen-ID
        self.next_id = 1

        # Nächste freie Verbindungs-ID
        self.next_connection_id = 1

        # Nächste freie Kommentar-ID
        self.next_comment_id = 1

        # Darstellungsoption für Gewichtsanzeigen.
        self.weight_labels_visible = True
        self.focused_neuron_id = None

        # Farbliche Darstellung und Linienstärke nach Gewicht.
        self.weight_visualization_enabled = True

        self.neuron_values_visible = True
        self.activation_charts_visible = True
        self.neuron_io_fields_visible = True
        self.neuron_ports_visible = True
        self.neuron_names_visible = True
        self.comments_visible = True
        self.color_settings = {}
        self.observation_mode = False

        # Aktueller Zustand beim Erstellen einer Verbindung
        self.connection_source_neuron = None
        self.connection_preview = None

        # Aktueller Zustand der Rechteckauswahl
        self.selection_start_position = None
        self.selection_rectangle = None
        self.selection_initial_items = set()

        # Positionen ausgewählter Neuronen vor einer
        # möglichen Verschiebung.
        self.movement_start_positions = {}

        # Bei großen Mehrfachauswahlen werden die vielen Verbindungslinien
        # während des Ziehens vorübergehend ausgeblendet. Dadurch muss ihre
        # Geometrie nicht für jedes einzelne Mausereignis neu berechnet werden.
        self.simplify_large_moves = True
        self.fast_group_move_active = False
        self.fast_group_move_connections = {}

        # Auf Änderungen der Auswahl reagieren
        self.selectionChanged.connect(
            self.selection_changed
        )

    def set_observation_mode(self, enabled):
        """Sperrt im Trainingsfenster nur das Erzeugen neuer Verbindungen."""

        self.observation_mode = bool(enabled)

        if self.observation_mode:
            self.cancel_connection()

    def add_neuron(
        self,
        neuron_id,
        x,
        y,
        name,
        mark_as_modified=True
    ):
        """
        Erzeugt ein Neuron, registriert es im Netzwerk
        und fügt es der Zeichenfläche hinzu.
        """

        neuron = Neuron(
            neuron_id,
            x,
            y,
            name,
            translator=self.t
        )

        neuron.set_values_visible(
            self.neuron_values_visible
        )
        neuron.set_activation_chart_visible(
            self.activation_charts_visible
        )
        neuron.set_io_fields_visible(
            self.neuron_io_fields_visible
        )
        neuron.set_ports_visible(
            self.neuron_ports_visible
        )
        neuron.set_name_visible(
            self.neuron_names_visible
        )

        if self.color_settings:
            neuron.apply_color_settings(
                self.color_settings
            )

        neuron.position_changed.connect(
            lambda changed_x, changed_y, obj=neuron:
            self.object_position_changed.emit(obj)
        )

        self.network.add_neuron(neuron)
        self.addItem(neuron)

        if mark_as_modified:
            self.scene_content_changed.emit()

        self.scene_geometry_changed.emit()

        return neuron

    def add_comment(
        self,
        comment_id,
        x,
        y,
        text=None,
        width=240.0,
        height=120.0,
        font_size=12,
        mark_as_modified=True
    ):
        """
        Erzeugt ein Kommentarfeld und fügt es
        der Zeichenfläche hinzu.
        """

        if text is None:
            text = self.t("canvas.default_comment")

        comment = CommentItem(
            comment_id,
            x,
            y,
            text,
            width,
            height,
            font_size,
            translator=self.t
        )
        comment.setVisible(
            self.comments_visible
        )

        if self.color_settings:
            comment.apply_color_settings(
                self.color_settings
            )

        comment.position_changed.connect(
            lambda changed_x, changed_y, obj=comment:
            self.object_position_changed.emit(obj)
        )

        comment.content_changed.connect(
            self.scene_content_changed.emit
        )

        comment.geometry_changed.connect(
            lambda obj=comment:
            self.object_position_changed.emit(obj)
        )

        comment.geometry_changed.connect(
            self.scene_geometry_changed.emit
        )

        self.addItem(comment)

        if mark_as_modified:
            self.scene_content_changed.emit()

        self.scene_geometry_changed.emit()

        return comment

    def add_connection(
        self,
        connection_id,
        source_neuron,
        target_neuron,
        weight=1.0,
        mark_as_modified=True
    ):
        """
        Erzeugt eine Verbindung, registriert sie im Netzwerk
        und fügt sie der Zeichenfläche hinzu.
        """

        connection = Connection(
            connection_id,
            source_neuron,
            target_neuron,
            weight,
            translator=self.t
        )

        connection.set_weight_label_visible(
            self.weight_labels_visible
        )
        connection.set_weight_visualization_enabled(
            self.weight_visualization_enabled
        )

        if self.color_settings:
            connection.apply_color_settings(
                self.color_settings
            )

        try:
            self.network.add_connection(connection)

        except (TypeError, ValueError):
            connection.disconnect()
            raise

        self.addItem(connection)
        self.apply_connection_focus()

        if mark_as_modified:
            self.scene_content_changed.emit()

        self.scene_geometry_changed.emit()

        return connection

    def set_weight_labels_visible(
        self,
        visible
    ):
        """
        Blendet die Gewichtsanzeigen aller vorhandenen
        und künftig erzeugten Verbindungen ein oder aus.
        """

        visible = bool(
            visible
        )

        self.weight_labels_visible = visible

        for connection in self.network.get_connections():
            connection.set_weight_label_visible(
                visible
            )

        self.apply_connection_focus()

        if visible:
            Connection.request_scene_weight_label_layout(
                self
            )

        self.update()

    def set_weight_visualization_enabled(
        self,
        enabled
    ):
        """
        Schaltet die farbliche Gewichtsdarstellung für alle
        vorhandenen und künftig erzeugten Verbindungen um.
        """

        enabled = bool(
            enabled
        )

        self.weight_visualization_enabled = enabled

        for connection in self.network.get_connections():
            connection.set_weight_visualization_enabled(
                enabled
            )

        self.update()

    def set_neuron_values_visible(self, visible):
        self.neuron_values_visible = bool(visible)

        for neuron in self.network.get_neurons():
            neuron.set_values_visible(
                self.neuron_values_visible
            )

        self.update()

    def set_activation_charts_visible(self, visible):
        self.activation_charts_visible = bool(visible)

        for neuron in self.network.get_neurons():
            neuron.set_activation_chart_visible(
                self.activation_charts_visible
            )

        self.update()

    def set_neuron_io_fields_visible(self, visible):
        self.neuron_io_fields_visible = bool(visible)

        for neuron in self.network.get_neurons():
            neuron.set_io_fields_visible(
                self.neuron_io_fields_visible
            )

        self.scene_geometry_changed.emit()
        self.update()

    def set_neuron_ports_visible(self, visible):
        self.neuron_ports_visible = bool(visible)

        for neuron in self.network.get_neurons():
            neuron.set_ports_visible(
                self.neuron_ports_visible
            )

        self.update()

    def set_neuron_names_visible(self, visible):
        self.neuron_names_visible = bool(visible)

        for neuron in self.network.get_neurons():
            neuron.set_name_visible(
                self.neuron_names_visible
            )

        self.update()

    def set_comments_visible(self, visible):
        self.comments_visible = bool(visible)

        for item in self.items():
            if isinstance(item, CommentItem):
                item.setVisible(
                    self.comments_visible
                )

        self.update()

    def set_color_settings(self, colors):
        """Wendet eine Farbpalette auf alle Projektobjekte an."""

        self.color_settings = dict(colors)
        self.setBackgroundBrush(
            QBrush(
                QColor(colors["canvas_background"])
            )
        )

        for neuron in self.network.get_neurons():
            neuron.apply_color_settings(colors)

        for connection in self.network.get_connections():
            connection.apply_color_settings(colors)

        for item in self.items():
            if isinstance(item, CommentItem):
                item.apply_color_settings(colors)

        self.update()

    def connection_exists(
        self,
        source_neuron,
        target_neuron
    ):
        """
        Prüft, ob bereits eine gerichtete Verbindung
        zwischen zwei Neuronen vorhanden ist.
        """

        return self.network.connection_exists(
            source_neuron,
            target_neuron
        )

    def start_connection(self, source_neuron):
        """
        Beginnt das Erstellen einer neuen Verbindung.
        """

        self.cancel_connection()

        self.connection_source_neuron = source_neuron

        start_position = (
            source_neuron.get_output_port_position()
        )

        self.connection_preview = ConnectionPreview(
            start_position
        )

        self.addItem(
            self.connection_preview
        )

    def cancel_connection(self):
        """
        Bricht das Erstellen einer Verbindung ab
        und entfernt die temporäre Linie.
        """

        if (
            self.connection_preview is not None
            and self.connection_preview.scene() is self
        ):
            self.removeItem(
                self.connection_preview
            )

        self.connection_preview = None
        self.connection_source_neuron = None

    def find_input_neuron_at(self, scene_position):
        """
        Sucht an der angegebenen Position nach
        einem Eingangsport eines Neurons.
        """

        for item in (
            []
            if self.observation_mode
            else self.items(scene_position)
        ):
            if (
                isinstance(item, Neuron)
                and item.is_input_port_at(scene_position)
            ):
                return item

        return None

    def remove_graphics_item(self, item):
        """
        Entfernt ein Neuron oder eine Verbindung
        aus dem Netzwerk und aus der Zeichenfläche.
        """

        item_removed = False

        if isinstance(item, Connection):
            self.network.remove_connection(item)

            if item.scene() is self:
                self.removeItem(item)

            item_removed = True

        elif isinstance(item, CommentItem):
            if item.scene() is self:
                self.removeItem(item)

            item_removed = True

        elif isinstance(item, Neuron):
            if item.id == self.focused_neuron_id:
                self.focused_neuron_id = None
            connected_items = list(
                item.incoming_connections
                + item.outgoing_connections
            )

            self.network.remove_neuron(item)

            for connection in connected_items:
                if connection.scene() is self:
                    self.removeItem(connection)

            if item.scene() is self:
                self.removeItem(item)

            item_removed = True

        if item_removed:
            self.scene_geometry_changed.emit()

    def clear_project(self):
        """
        Entfernt alle Projektobjekte aus dem Netzwerk
        und aus der Zeichenfläche.
        """

        self.cancel_connection()
        self.cancel_selection_rectangle()
        self.focused_neuron_id = None

        self.movement_start_positions = {}

        self.network.clear()
        super().clear()

        self.next_id = 1
        self.next_connection_id = 1
        self.next_comment_id = 1

        self.object_selected.emit(None)
        self.scene_geometry_changed.emit()

    def start_selection_rectangle(
        self,
        scene_position,
        keep_current_selection
    ):
        """
        Beginnt eine Rechteckauswahl auf der freien Fläche.
        """

        self.selection_start_position = QPointF(
            scene_position
        )

        if keep_current_selection:
            self.selection_initial_items = set(
                self.selectedItems()
            )
        else:
            self.clearSelection()
            self.selection_initial_items = set()

        self.selection_rectangle = QGraphicsRectItem()
        self.selection_rectangle.setPen(
            QPen(
                Qt.GlobalColor.blue,
                1,
                Qt.PenStyle.DashLine
            )
        )
        self.selection_rectangle.setBrush(
            QBrush(
                Qt.BrushStyle.NoBrush
            )
        )
        self.selection_rectangle.setZValue(1000.0)

        self.addItem(
            self.selection_rectangle
        )

        self.update_selection_rectangle(
            scene_position
        )

    def update_selection_rectangle(self, scene_position):
        """
        Aktualisiert Größe und Inhalt
        der aktuellen Rechteckauswahl.
        """

        if (
            self.selection_rectangle is None
            or self.selection_start_position is None
        ):
            return

        selection_rect = QRectF(
            self.selection_start_position,
            scene_position
        ).normalized()

        self.selection_rectangle.setRect(
            selection_rect
        )

        matching_items = set()

        for item in self.items():
            if not isinstance(
                item,
                (Neuron, Connection, CommentItem)
            ):
                continue

            if item.sceneBoundingRect().intersects(
                selection_rect
            ):
                matching_items.add(item)

        selected_items = (
            self.selection_initial_items
            | matching_items
        )

        for item in self.items():
            if isinstance(
                item,
                (Neuron, Connection, CommentItem)
            ):
                item.setSelected(
                    item in selected_items
                )

    def cancel_selection_rectangle(self):
        """
        Beendet die Rechteckauswahl und entfernt
        das grafische Auswahlrechteck.
        """

        if (
            self.selection_rectangle is not None
            and self.selection_rectangle.scene() is self
        ):
            self.removeItem(
                self.selection_rectangle
            )

        self.selection_rectangle = None
        self.selection_start_position = None
        self.selection_initial_items = set()

    def store_movement_start_positions(self):
        """
        Speichert die Positionen aller aktuell
        ausgewählten Neuronen vor einer Verschiebung.
        """

        self.movement_start_positions = {
            neuron: QPointF(neuron.pos())
            for neuron in self.selectedItems()
            if isinstance(neuron, (Neuron, CommentItem))
        }

    def selected_neurons_were_moved(self):
        """
        Prüft, ob sich mindestens eines der zuvor
        gespeicherten Neuronen tatsächlich bewegt hat.
        """

        for neuron, start_position in (
            self.movement_start_positions.items()
        ):
            if neuron.scene() is not self:
                continue

            if neuron.pos() != start_position:
                return True

        return False

    def begin_fast_group_move(self):
        """Bereitet eine flüssige Verschiebung großer Netzbereiche vor."""

        self.finish_fast_group_move()

        if not self.simplify_large_moves:
            return

        neurons = [
            item
            for item in self.movement_start_positions
            if isinstance(item, Neuron)
        ]
        connections = {
            connection
            for neuron in neurons
            for connection in (
                neuron.incoming_connections
                + neuron.outgoing_connections
            )
        }

        # Kleine Auswahlen bleiben unverändert; dort ist die laufende
        # Darstellung der Verbindungen weiterhin angenehm und schnell genug.
        if len(connections) < 100:
            return

        self.fast_group_move_active = True
        self.fast_group_move_connections = {
            connection: connection.isVisible()
            for connection in connections
            if connection.scene() is self
        }

        for connection in self.fast_group_move_connections:
            connection.setVisible(False)

    def finish_fast_group_move(self):
        """Stellt Linien wieder her und berechnet sie genau einmal neu."""

        if not self.fast_group_move_active:
            return

        self.fast_group_move_active = False

        for connection, was_visible in (
            self.fast_group_move_connections.items()
        ):
            if connection.scene() is not self:
                continue
            connection.update_position()
            connection.setVisible(was_visible)

        for item, start_position in self.movement_start_positions.items():
            if (
                isinstance(item, Neuron)
                and item.scene() is self
                and item.pos() != start_position
            ):
                item.position_changed.emit(
                    item.pos().x(),
                    item.pos().y()
                )

        self.fast_group_move_connections = {}
        self.update()

    def mousePressEvent(self, event):
        """
        Verarbeitet den Beginn einer Verbindung,
        einer Rechteckauswahl oder einer normalen Auswahl.
        """

        self.movement_start_positions = {}

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        scene_position = event.scenePos()

        # Ausgangsport angeklickt:
        # Verbindungserstellung beginnen.
        for item in self.items(scene_position):
            if (
                isinstance(item, Neuron)
                and item.is_output_port_at(scene_position)
            ):
                if not item.isSelected():
                    if not (
                        event.modifiers()
                        & Qt.KeyboardModifier.ControlModifier
                    ):
                        self.clearSelection()

                    item.setSelected(True)

                self.start_connection(item)

                event.accept()
                return

        clicked_item = self.itemAt(
            scene_position,
            QTransform()
        )

        # Klick auf freie Fläche:
        # Rechteckauswahl beginnen.
        if clicked_item is None:
            keep_current_selection = bool(
                event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            )

            self.start_selection_rectangle(
                scene_position,
                keep_current_selection
            )

            event.accept()
            return

        # Ein Kommentar wird bei einem normalen Klick
        # immer allein ausgewählt. Dadurch bewegt sich
        # beim Ziehen nicht versehentlich ein zuvor
        # ausgewähltes Neuron mit.
        if isinstance(
            clicked_item,
            CommentItem
        ):
            keep_current_selection = bool(
                event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            )

            if not keep_current_selection:
                self.clearSelection()
                clicked_item.setSelected(
                    True
                )

        # Qt übernimmt anschließend die eigentliche
        # Mausbewegung. Mit gedrückter Strg-Taste bleibt
        # eine bewusst erzeugte Mehrfachauswahl erhalten.
        super().mousePressEvent(event)

        self.store_movement_start_positions()
        self.begin_fast_group_move()

    def mouseMoveEvent(self, event):
        """
        Aktualisiert die temporäre Verbindung,
        die Rechteckauswahl oder verschiebt ausgewählte Objekte.
        """

        if self.connection_preview is not None:
            self.connection_preview.update_end_position(
                event.scenePos()
            )

            event.accept()
            return

        if self.selection_rectangle is not None:
            self.update_selection_rectangle(
                event.scenePos()
            )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Beendet die Verbindungserstellung,
        die Rechteckauswahl oder eine Verschiebung.
        """

        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.connection_preview is not None
        ):
            source_neuron = self.connection_source_neuron

            target_neuron = self.find_input_neuron_at(
                event.scenePos()
            )

            self.cancel_connection()

            if (
                target_neuron is not None
                and target_neuron is not source_neuron
                and not self.connection_exists(
                    source_neuron,
                    target_neuron
                )
            ):
                connection = self.add_connection(
                    self.next_connection_id,
                    source_neuron,
                    target_neuron
                )

                self.next_connection_id += 1

                self.clearSelection()
                connection.setSelected(True)

            event.accept()
            return

        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.selection_rectangle is not None
        ):
            self.update_selection_rectangle(
                event.scenePos()
            )

            self.cancel_selection_rectangle()

            event.accept()
            return

        super().mouseReleaseEvent(event)

        self.finish_fast_group_move()

        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.selected_neurons_were_moved()
        ):
            self.scene_geometry_changed.emit()

        self.movement_start_positions = {}

    def mouseDoubleClickEvent(self, event):
        """
        Leitet Doppelklicks an vorhandene Objekte weiter.

        Auf freier Fläche wird kein Objekt erzeugt.
        """

        super().mouseDoubleClickEvent(event)

    def selection_changed(self):
        """
        Wird von Qt aufgerufen, wenn sich die Auswahl
        innerhalb der Zeichenfläche geändert hat.
        """

        selected_items = self.selectedItems()

        if not selected_items:
            self.object_selected.emit(None)
            return

        # Bei genau einem Objekt werden dessen Eigenschaften angezeigt.
        if len(selected_items) == 1:
            selected_item = selected_items[0]

            if isinstance(
                selected_item,
                (Neuron, Connection, CommentItem)
            ):
                self.object_selected.emit(
                    selected_item
                )
                return

        # Bei Mehrfachauswahl wird kein einzelnes Objekt
        # im Eigenschaftenfenster angezeigt.
        self.object_selected.emit(None)

    def contextMenuEvent(self, event):
        """
        Öffnet das Kontextmenü der Zeichenfläche.
        """

        item = self.itemAt(
            event.scenePos(),
            QTransform()
        )

        # Falls ein untergeordnetes Grafikelement getroffen wurde, wird
        # dessen eigentliches Projektobjekt verwendet.
        while item is not None and not isinstance(
            item,
            (Neuron, Connection, CommentItem)
        ):
            item = item.parentItem()

        menu = QMenu()

        edit_action = None
        delete_action = None
        focus_action = None

        if isinstance(item, Neuron):
            edit_action = menu.addAction(
                self.t("common.edit")
            )
            delete_action = menu.addAction(
                self.t("common.delete")
            )
            menu.addSeparator()
            focus_action = menu.addAction(
                self.t(
                    "canvas.connections.show_all"
                    if self.focused_neuron_id == item.id
                    else "canvas.connections.focus"
                )
            )
        elif isinstance(item, CommentItem):
            edit_action = menu.addAction(
                self.t("common.edit")
            )
            delete_action = menu.addAction(
                self.t("common.delete")
            )
        elif isinstance(item, Connection):
            delete_action = menu.addAction(
                self.t("common.delete")
            )
        else:
            insert_action = menu.addAction(
                self.t("canvas.insert_neuron")
            )

            insert_comment_action = menu.addAction(
                self.t("canvas.insert_comment")
            )

        action = menu.exec(
            event.screenPos()
        )

        if action is None:
            return

        if action == edit_action:
            # Eine bestehende Mehrfachauswahl bleibt beim Rechtsklick auf
            # eines ihrer Elemente erhalten.
            if item not in self.selectedItems():
                self.clearSelection()
                item.setSelected(True)
            if isinstance(item, Neuron):
                self.edit_neuron_requested.emit(item)
            elif isinstance(item, CommentItem):
                self.edit_comment_requested.emit(item)

        elif action == delete_action:
            selected_items = list(self.selectedItems())

            if item in selected_items:
                self.delete_requested.emit(selected_items)
            elif item is not None:
                self.delete_requested.emit([item])

        elif action == focus_action:
            if self.focused_neuron_id == item.id:
                self.clear_connection_focus()
            else:
                self.focus_connections_for_neuron(item)

        elif action == insert_action:
            pos = event.scenePos()

            neuron = self.add_neuron(
                self.next_id,
                pos.x(),
                pos.y(),
                f"N{self.next_id}"
            )

            self.clearSelection()
            neuron.setSelected(True)

            self.next_id += 1

        elif action == insert_comment_action:
            pos = event.scenePos()

            comment = self.add_comment(
                self.next_comment_id,
                pos.x(),
                pos.y()
            )

            self.clearSelection()
            comment.setSelected(True)

            self.next_comment_id += 1

    def focus_connections_for_neuron(self, neuron):
        """Zeigt ausschließlich die direkten Verbindungen eines Neurons."""

        self.focused_neuron_id = neuron.id
        self.apply_connection_focus()

    def clear_connection_focus(self):
        """Hebt den Verbindungsfokus auf und zeigt das gesamte Netz."""

        self.focused_neuron_id = None
        self.apply_connection_focus()

    def apply_connection_focus(self):
        """Wendet den aktuellen, rein visuellen Verbindungsfilter erneut an."""

        focused_id = self.focused_neuron_id
        for connection in self.network.get_connections():
            visible = (
                focused_id is None
                or connection.source_neuron.id == focused_id
                or connection.target_neuron.id == focused_id
            )
            connection.setVisible(visible)
            connection.set_weight_label_visible(
                visible and self.weight_labels_visible
            )
        if self.weight_labels_visible:
            Connection.request_scene_weight_label_layout(self)
        self.update()

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Escape
            and self.focused_neuron_id is not None
        ):
            self.clear_connection_focus()
            event.accept()
            return
        super().keyPressEvent(event)
