# -------------------------------------------------------------------------------------------------
# Datei: graphicsview.py
# Zweck: Verwaltet die grafische Netzwerkansicht, Zoom und Mausnavigation.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QGraphicsView


class GraphicsView(QGraphicsView):
    """
    Zeichenansicht des NeuronNetz-Editors.

    Zuständig für:
        - Zoomen mit dem Mausrad
        - Zoomen auf die Mausposition
        - Verschieben des sichtbaren Ausschnitts mit Alt + linker Maustaste
        - Zoomgrenzen
        - Ansicht auf 100 Prozent zurücksetzen
        - gesamtes Netzwerk einpassen
        - Szenenbereich nach abgeschlossenen Änderungen erweitern
    """

    zoom_changed = Signal(int)

    def __init__(self, scene=None, parent=None):

        super().__init__(scene, parent)

        self.zoom_factor = 1.15
        self.minimum_zoom = 0.20
        self.maximum_zoom = 4.00
        self.hand_pan_dragging = False
        self.hand_pan_last_position = None

        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self.minimum_scene_rect = QRectF(
            0.0,
            0.0,
            800.0,
            600.0
        )

        self.scene_margin = 100.0

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
        )

        self.setRenderHint(
            self.renderHints()
        )

        if (
            self.scene() is not None
            and hasattr(
                self.scene(),
                "scene_geometry_changed"
            )
        ):
            self.scene().scene_geometry_changed.connect(
                self.update_scene_rect
            )

    def get_zoom(self):
        """
        Liefert den aktuellen Zoomfaktor.
        """

        return self.transform().m11()

    def get_zoom_percent(self):
        """
        Liefert den aktuellen Zoomwert in Prozent.
        """

        return round(
            self.get_zoom() * 100
        )

    def update_scene_rect(self):
        """
        Erweitert den Szenenbereich nach einer
        abgeschlossenen geometrischen Änderung.

        Der bestehende Szenenbereich wird niemals
        automatisch verkleinert.
        """

        if self.scene() is None:
            return

        current_scene_rect = QRectF(
            self.scene().sceneRect()
        )

        if current_scene_rect.isNull():
            current_scene_rect = QRectF(
                self.minimum_scene_rect
            )

        new_scene_rect = current_scene_rect.united(
            self.minimum_scene_rect
        )

        items_rect = self.scene().itemsBoundingRect()

        if not items_rect.isNull() and not items_rect.isEmpty():
            expanded_items_rect = items_rect.adjusted(
                -self.scene_margin,
                -self.scene_margin,
                self.scene_margin,
                self.scene_margin
            )

            new_scene_rect = new_scene_rect.united(
                expanded_items_rect
            )

        if new_scene_rect == current_scene_rect:
            return

        visible_center = self.mapToScene(
            self.viewport().rect().center()
        )

        self.scene().setSceneRect(
            new_scene_rect
        )

        self.centerOn(
            visible_center
        )

    def set_zoom(self, zoom):
        """
        Setzt einen absoluten Zoomfaktor.
        """

        zoom = max(
            self.minimum_zoom,
            min(
                zoom,
                self.maximum_zoom
            )
        )

        current_zoom = self.get_zoom()

        if current_zoom == 0.0:
            return

        factor = zoom / current_zoom

        self.scale(
            factor,
            factor
        )

        self.zoom_changed.emit(
            self.get_zoom_percent()
        )

    def zoom_in(self):
        """
        Vergrößert die Ansicht um eine Stufe.
        """

        self.set_zoom(
            self.get_zoom()
            * self.zoom_factor
        )

    def zoom_out(self):
        """
        Verkleinert die Ansicht um eine Stufe.
        """

        self.set_zoom(
            self.get_zoom()
            / self.zoom_factor
        )

    def reset_zoom(self):
        """
        Setzt die Ansicht auf 100 Prozent zurück.
        """

        self.resetTransform()

        self.zoom_changed.emit(
            100
        )

    def fit_all(self):
        """
        Passt alle Objekte der Szene vollständig
        in den sichtbaren Bereich ein und zentriert
        das Netzwerk horizontal und vertikal.
        """

        if self.scene() is None:
            return

        # Alte Scrollpositionen des Handmodus dürfen die neue
        # Einpassung nicht beeinflussen.
        self.stop_hand_pan()

        items_rect = self.scene().itemsBoundingRect()

        if items_rect.isNull() or items_rect.isEmpty():
            self.scene().setSceneRect(
                self.minimum_scene_rect
            )

            self.reset_zoom()
            return

        display_margin = 40.0
        scene_margin = 100.0

        display_rect = items_rect.adjusted(
            -display_margin,
            -display_margin,
            display_margin,
            display_margin
        )

        new_scene_rect = items_rect.adjusted(
            -scene_margin,
            -scene_margin,
            scene_margin,
            scene_margin
        )

        self.scene().setSceneRect(
            new_scene_rect
        )

        # Unabhängig von der zuvor verschobenen Ansicht vollständig neu
        # einpassen.
        self.resetTransform()

        self.fitInView(
            display_rect,
            Qt.AspectRatioMode.KeepAspectRatio
        )

        current_zoom = self.get_zoom()

        if current_zoom < self.minimum_zoom:
            self.resetTransform()

            self.scale(
                self.minimum_zoom,
                self.minimum_zoom
            )

        elif current_zoom > self.maximum_zoom:
            self.resetTransform()

            self.scale(
                self.maximum_zoom,
                self.maximum_zoom
            )

        self.centerOn(
            items_rect.center()
        )

        # Qt kann nach einer starken Handverschiebung kurzzeitig noch alte
        # Scrollwerte halten. Die Mitte der neu begrenzten Szene entspricht
        # der Mitte der Projektobjekte.
        horizontal_scrollbar = self.horizontalScrollBar()
        vertical_scrollbar = self.verticalScrollBar()
        horizontal_scrollbar.setValue(
            (
                horizontal_scrollbar.minimum()
                + horizontal_scrollbar.maximum()
            ) // 2
        )
        vertical_scrollbar.setValue(
            (
                vertical_scrollbar.minimum()
                + vertical_scrollbar.maximum()
            ) // 2
        )
        self.viewport().update()

        self.zoom_changed.emit(
            self.get_zoom_percent()
        )

    def wheelEvent(self, event):
        """
        Vergrößert oder verkleinert die Ansicht
        mit dem Mausrad auf die Mausposition.
        """

        # Alt gehört vollständig dem Handmodus. Insbesondere Touchpads
        # können beim Fensterwechsel noch Radimpulse liefern, die das
        # Netzwerk sonst unbeabsichtigt stark verkleinern würden.
        if (
            event.modifiers()
            & Qt.KeyboardModifier.AltModifier
        ):
            event.accept()
            return

        if event.angleDelta().y() > 0:
            self.zoom_in()

        elif event.angleDelta().y() < 0:
            self.zoom_out()

        event.accept()

    def keyPressEvent(self, event):
        """Zeigt beim Drücken von Alt die geöffnete Hand an."""

        if (
            event.key() == Qt.Key.Key_Alt
            and not event.isAutoRepeat()
        ):
            self.update_hand_cursor(True)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Entfernt die Handanzeige beim Loslassen von Alt."""

        if (
            event.key() == Qt.Key.Key_Alt
            and not event.isAutoRepeat()
        ):
            self.stop_hand_pan()
            event.accept()
            return

        super().keyReleaseEvent(event)

    def enterEvent(self, event):
        """Zeigt bei gedrückter Alt-Taste die offene Hand an."""

        alt_pressed = bool(
            QApplication.keyboardModifiers()
            & Qt.KeyboardModifier.AltModifier
        )
        self.update_hand_cursor(
            alt_pressed,
            self.mapFromGlobal(QCursor.pos())
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Setzt außerhalb der Zeichenfläche den normalen Cursor zurück."""

        if not self.hand_pan_dragging:
            self.viewport().unsetCursor()

        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Beginnt den Handmodus nur mit Alt + linker Maustaste."""

        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers()
            & Qt.KeyboardModifier.AltModifier
        ):
            self.ensure_hand_pan_range()
            self.hand_pan_dragging = True
            self.hand_pan_last_position = event.position()
            self.viewport().setCursor(
                Qt.CursorShape.ClosedHandCursor
            )
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Verschiebt nur den sichtbaren Ausschnitt, nicht die Objekte."""

        if (
            self.hand_pan_dragging
            and self.hand_pan_last_position is not None
        ):
            movement = (
                event.position()
                - self.hand_pan_last_position
            )
            self.hand_pan_last_position = event.position()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value()
                - round(movement.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value()
                - round(movement.y())
            )

            # Bei ausgeschaltetem Netzwerkmonitor friert das
            # Trainingsfenster die automatischen Aktualisierungen der
            # Zeichenansicht ein. Eine bewusst ausgeführte Navigation
            # muss trotzdem sofort sichtbar werden. Deshalb wird nur
            # für dieses eine Bild kurz gezeichnet; anschließend bleibt
            # der bisherige Aktualisierungszustand erhalten.
            self.repaint_hand_pan_frame()

            event.accept()
            return

        self.update_hand_cursor(
            bool(event.modifiers() & Qt.KeyboardModifier.AltModifier),
            event.position().toPoint()
        )

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Beendet das Verschieben beim Loslassen der linken Maustaste."""

        if (
            self.hand_pan_dragging
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.stop_hand_pan()
            self.update_hand_cursor(
                bool(event.modifiers() & Qt.KeyboardModifier.AltModifier),
                event.position().toPoint()
            )

            event.accept()
            return

        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event):
        """Verhindert einen hängenbleibenden Handmodus bei Fokuswechsel."""

        self.stop_hand_pan()
        super().focusOutEvent(event)

    def stop_hand_pan(self):
        """Setzt alle Zustände und den Mauszeiger des Handmodus zurück."""

        self.hand_pan_dragging = False
        self.hand_pan_last_position = None
        self.viewport().unsetCursor()

    def update_hand_cursor(self, alt_pressed, position=None):
        """Zeigt die Hand ausschließlich bei gedrückter Alt-Taste."""

        if self.hand_pan_dragging:
            self.viewport().setCursor(
                Qt.CursorShape.ClosedHandCursor
            )

        elif alt_pressed:
            self.viewport().setCursor(
                Qt.CursorShape.OpenHandCursor
            )

        else:
            self.viewport().unsetCursor()

    def is_free_canvas_position(self, position):
        """Prüft, ob unter der Maus kein bedienbares Szenenobjekt liegt."""

        return self.itemAt(position) is None

    def repaint_hand_pan_frame(self):
        """Zeichnet eine manuelle Handverschiebung auch im Monitor-Aus."""

        updates_were_enabled = self.updatesEnabled()

        if not updates_were_enabled:
            self.setUpdatesEnabled(True)

        try:
            self.viewport().repaint()

        finally:
            if not updates_were_enabled:
                self.setUpdatesEnabled(False)

    def ensure_hand_pan_range(self):
        """Erweitert bei Bedarf nur den verschiebbaren Ansichtsbereich."""

        if self.scene() is None:
            return

        visible_rect = self.mapToScene(
            self.viewport().rect()
        ).boundingRect()

        if visible_rect.isNull() or visible_rect.isEmpty():
            return

        visible_center = visible_rect.center()
        pan_rect = visible_rect.adjusted(
            -visible_rect.width(),
            -visible_rect.height(),
            visible_rect.width(),
            visible_rect.height()
        )
        current_scene_rect = self.scene().sceneRect()
        expanded_scene_rect = current_scene_rect.united(
            pan_rect
        )

        if expanded_scene_rect == current_scene_rect:
            return

        self.scene().setSceneRect(
            expanded_scene_rect
        )
        self.centerOn(
            visible_center
        )
