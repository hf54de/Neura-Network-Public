# -------------------------------------------------------------------------------------------------
# Datei: commentitem.py
# Zweck: Zeigt und bearbeitet frei platzierbare Kommentare auf der Zeichenfläche.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QInputDialog


class CommentItem(QGraphicsObject):
    """
    Frei positionierbares und größenveränderbares Kommentarfeld.
    """

    position_changed = Signal(float, float)
    content_changed = Signal()
    geometry_changed = Signal()

    def __init__(self, comment_id, x, y, text="Kommentar", width=240.0, height=120.0, font_size=12, translator=None):
        super().__init__()
        self.id = comment_id
        self.text = str(text)
        self.font_size = max(8, min(int(font_size), 48))
        self.minimum_width = 120.0
        self.minimum_height = 36.0
        self.width = max(self.minimum_width, float(width))
        self.height = max(self.minimum_height, float(height))
        self.corner_radius = 6.0
        self.resize_handle_size = 12.0
        self.is_resizing = False
        self.resize_start_position = QPointF()
        self.resize_start_width = self.width
        self.resize_start_height = self.height
        self.normal_border_pen = QPen(QColor(120, 105, 45), 1)
        self.selected_border_pen = QPen(Qt.GlobalColor.red, 2)
        self.background_brush = QBrush(QColor(255, 248, 180))
        self.resize_handle_brush = QBrush(QColor(120, 105, 45))
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    def apply_color_settings(self, colors):
        """Wendet die projektbezogenen Kommentarfarben an."""

        self.background_brush = QBrush(
            QColor(colors["comment_background"])
        )
        self.selected_border_pen = QPen(
            QColor(colors["selection"]),
            2
        )
        self.update()

    def get_body_rect(self):
        return QRectF(0.0, 0.0, self.width, self.height)

    def get_resize_handle_rect(self):
        return QRectF(
            self.width - self.resize_handle_size,
            self.height - self.resize_handle_size,
            self.resize_handle_size,
            self.resize_handle_size
        )

    def boundingRect(self):
        return self.get_body_rect().adjusted(-3.0, -3.0, 3.0, 3.0)

    def paint(self, painter, option, widget=None):
        body_rect = self.get_body_rect()
        border_pen = self.selected_border_pen if self.isSelected() else self.normal_border_pen
        painter.setPen(border_pen)
        painter.setBrush(self.background_brush)
        painter.drawRoundedRect(body_rect, self.corner_radius, self.corner_radius)
        text_font = QFont()
        text_font.setPointSize(self.font_size)
        painter.setFont(text_font)
        painter.setPen(Qt.GlobalColor.black)
        text_rect = body_rect.adjusted(10.0, 8.0, -10.0, -8.0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self.text
        )
        if self.isSelected():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.resize_handle_brush)
            painter.drawRect(self.get_resize_handle_rect())

    def set_text(self, text, mark_as_modified=True):
        text = str(text)
        if text == self.text:
            return
        self.text = text
        self.update()
        if mark_as_modified:
            self.content_changed.emit()

    def set_font_size(self, font_size, mark_as_modified=True):
        new_font_size = max(8, min(int(font_size), 48))
        if new_font_size == self.font_size:
            return
        self.font_size = new_font_size
        self.update()
        if mark_as_modified:
            self.content_changed.emit()

    def set_size(self, width, height, mark_as_modified=True):
        new_width = max(self.minimum_width, float(width))
        new_height = max(self.minimum_height, float(height))
        if new_width == self.width and new_height == self.height:
            return
        self.prepareGeometryChange()
        self.width = new_width
        self.height = new_height
        self.update()
        if mark_as_modified:
            self.content_changed.emit()
            self.geometry_changed.emit()

    def mouseDoubleClickEvent(self, event):
        text, accepted = QInputDialog.getMultiLineText(
            None,
            self.translator("comment.edit.title") if callable(self.translator) else "Kommentar bearbeiten",
            self.translator("comment.edit.text") if callable(self.translator) else "Text:",
            self.text
        )
        if accepted:
            self.set_text(text)
        event.accept()

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.isSelected()
            and self.get_resize_handle_rect().contains(event.pos())
        ):
            self.is_resizing = True
            self.resize_start_position = QPointF(event.pos())
            self.resize_start_width = self.width
            self.resize_start_height = self.height
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            delta = event.pos() - self.resize_start_position
            self.set_size(
                self.resize_start_width + delta.x(),
                self.resize_start_height + delta.y(),
                mark_as_modified=False
            )

            self.geometry_changed.emit()

            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_resizing:
            self.is_resizing = False
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.content_changed.emit()
            self.geometry_changed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """
        Meldet Auswahl- und Positionsänderungen.

        Kommentare dürfen sich wie Neuronen auch
        in negative Szenenkoordinaten bewegen.
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
            self.position_changed.emit(
                value.x(),
                value.y()
            )

        return super().itemChange(
            change,
            value
        )
