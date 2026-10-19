# -------------------------------------------------------------------------------------------------
# Datei: graphicalexperimentdialog.py
# Zweck: Stellt ein frei gestaltbares grafisches Bedienpult für Netzwerkexperimente bereit.
# Letzte Änderung: 05.10.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import json
import math
from applicationcurve import CurvePlot, CurveController
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    QSettings,
    Signal,
    QStandardPaths,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QMessageBox,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QStyle,
    QStyleOptionButton,
    QStyleOptionSlider,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QToolTip,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from colorpalette import choose_color, restore_custom_colors, save_custom_colors
from toolbaricons import ToolbarIcons as SharedToolbarIcons

from numberformat import format_number
from trainingdataio import TrainingDataIO
from atomicjson import write_json_atomic
from activationfunctions import ActivationFunctions


class ToolbarIcons(SharedToolbarIcons):
    """Symbole des grafischen Experiments im Petrolton der Netzwerkgruppe."""

    @classmethod
    def icon(cls, symbol_name, color="#34495e", accent="#168a83"):
        return SharedToolbarIcons.icon(
            symbol_name,
            color=color,
            accent=accent,
        )


def format_application_output_value(value):
    """Formatiert analoge Kachelwerte kompakt und erhält sehr kleine Werte."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return str(number)
    if number == 0.0:
        return "0"
    if abs(number) < 0.01:
        return format_number(number, 5)
    return f"{number:.2f}".rstrip("0").rstrip(".")


def show_yellow_information_dialog(parent, title, text, close_text, scrollable=False, rich_text=False):
    """Zeigt einen einheitlichen, gut lesbaren Informationsdialog an."""

    dialog = QDialog(parent)
    dialog.setWindowTitle(str(title))
    dialog.setModal(True)
    dialog.setMinimumWidth(500)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    if scrollable:
        information = QTextEdit(dialog)
        information.setReadOnly(True)
        if rich_text:
            information.setHtml(str(text))
        else:
            information.setPlainText(str(text))
    else:
        information = QLabel(str(text), dialog)
        information.setWordWrap(True)
    information.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    information.setStyleSheet(
        "QLabel, QTextEdit {"
        " background-color: #fff8d8;"
        " color: #202020;"
        " border: 1px solid #d8b34f;"
        " border-radius: 5px;"
        " padding: 12px;"
        "}"
    )
    layout.addWidget(information)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    close_button = QPushButton(str(close_text), dialog)
    close_button.clicked.connect(dialog.accept)
    button_row.addWidget(close_button)
    layout.addLayout(button_row)

    dialog.adjustSize()
    if scrollable:
        available = dialog.screen().availableGeometry()
        dialog.resize(min(620, available.width() - 40), min(720, available.height() - 80))
    dialog.exec()


from binarystatecolors import state_palette
from binaryuncertainty import normalize_limits, is_uncertain, warning_style, warning_text


class ForwardCalculationBridge(QObject):
    """Bringt Ergebnisse einer reinen Hintergrundrechnung sicher zur GUI."""

    completed = Signal(int, object, object)


def calculate_forward_snapshot(specification, input_values):
    """Berechnet einen Forward-Pass ohne Zugriff auf Qt- oder GUI-Objekte."""

    values = {}
    sums = {}
    for neuron in specification:
        neuron_id = neuron["id"]
        if neuron["input"]:
            output = float(input_values[neuron_id])
            weighted_sum = 0.0
        else:
            weighted_sum = float(neuron["bias"])
            for source_id, weight in neuron["incoming"]:
                weighted_sum += values[source_id] * weight
            output = ActivationFunctions.apply(neuron["activation"], weighted_sum)
        if not math.isfinite(weighted_sum) or not math.isfinite(output):
            raise ValueError(
                f"Neuron {neuron['name']} hat keinen endlichen Wert erzeugt."
            )
        sums[neuron_id] = weighted_sum
        values[neuron_id] = output
    return sums, values


class CompactInputSpinBox(QDoubleSpinBox):
    """Zeigt Rohwerte kompakt an, behält intern aber ihre Genauigkeit."""

    def textFromValue(self, value):
        number = float(value)
        if number == 0.0:
            text = "0"
        elif abs(number) < 0.01:
            text = f"{number:.{self.decimals()}f}".rstrip("0").rstrip(".")
        else:
            text = f"{number:.2f}".rstrip("0").rstrip(".")
        decimal_point = self.locale().decimalPoint()
        return text.replace(".", decimal_point)


class CenteredCheckMarkBox(QCheckBox):
    """Behält das native Kontrollfeld bei und zentriert dessen Häkchen."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.checkState() != Qt.CheckState.Checked:
            return

        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator,
            option,
            self,
        )
        if indicator.isEmpty():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        inset = max(1.0, indicator.width() * 0.08)
        interior = QRectF(indicator).adjusted(inset, inset, -inset, -inset)
        fill_color = option.palette.highlight().color()
        mark_color = option.palette.highlightedText().color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_color)
        corner_radius = max(1.0, interior.width() * 0.16)
        painter.drawRoundedRect(interior, corner_radius, corner_radius)

        path = QPainterPath()
        path.moveTo(
            interior.left() + interior.width() * 0.25,
            interior.top() + interior.height() * 0.52,
        )
        path.lineTo(
            interior.left() + interior.width() * 0.43,
            interior.top() + interior.height() * 0.68,
        )
        path.lineTo(
            interior.left() + interior.width() * 0.75,
            interior.top() + interior.height() * 0.34,
        )
        pen = QPen(mark_color, max(1.2, interior.width() * 0.10))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class CompactInputSlider(QSlider):
    """Analoger Schieberegler im segmentierten Stil der Ausgabekacheln."""

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.foreground_color = QColor("#333333")

    def set_foreground_color(self, color):
        self.foreground_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )
        handle_width = max(10.0, float(handle_rect.width()))
        track_left = handle_width / 2.0
        track_right = max(track_left, self.width() - handle_width / 2.0)
        track_width = max(1.0, track_right - track_left)
        span = self.maximum() - self.minimum()
        ratio = (
            0.0
            if span <= 0
            else (self.value() - self.minimum()) / float(span)
        )
        ratio = max(0.0, min(1.0, ratio))
        if option.upsideDown:
            ratio = 1.0 - ratio

        segment_count = 15
        gap = max(1.0, min(2.2, track_width * 0.009))
        segment_width = max(
            1.0,
            (track_width - gap * (segment_count - 1)) / segment_count,
        )
        bar_height = max(5.0, min(8.0, self.height() * 0.34))
        top = (self.height() - bar_height) / 2.0
        inactive_color = QColor(self.foreground_color)
        inactive_color.setAlpha(55)
        active_count = int(math.ceil(ratio * segment_count - 1e-9))

        painter.setPen(Qt.PenStyle.NoPen)
        for step in range(segment_count):
            painter.setBrush(
                self.foreground_color
                if step < active_count
                else inactive_color
            )
            x = track_left + step * (segment_width + gap)
            painter.drawRoundedRect(
                QRectF(x, top, segment_width, bar_height),
                1.2,
                1.2,
            )

        handle_center = QPointF(
            track_left + ratio * track_width,
            self.height() / 2.0,
        )
        handle_radius = max(4.5, min(6.5, self.height() * 0.30))
        if self.hasFocus():
            focus_color = QColor(self.foreground_color)
            focus_color.setAlpha(80)
            painter.setPen(QPen(focus_color, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                handle_center,
                handle_radius + 2.0,
                handle_radius + 2.0,
            )
        painter.setPen(QPen(self.foreground_color, 1.2))
        painter.setBrush(QColor("#c51d24"))
        painter.drawEllipse(handle_center, handle_radius, handle_radius)


class CompactInputDial(QSlider):
    """Bedienbarer Halbkreis-Drehregler im Stil der Zeigeranzeige."""

    def __init__(self, display_minimum=0.0, display_maximum=1.0, unit="", parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.display_minimum = float(display_minimum)
        self.display_maximum = float(display_maximum)
        self.unit = str(unit or "")
        self.foreground_color = QColor("#333333")
        self.setProperty("nn_max_font_size", 10.0)
        self.setMinimumHeight(64)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_foreground_color(self, color):
        self.foreground_color = QColor(color)
        self.update()

    def visible_bottom(self):
        """Liefert die durch alle Elternwidgets tatsächlich sichtbare Unterkante."""

        bottom = float(self.height())
        ancestor = self.parentWidget()
        while ancestor is not None:
            top_in_ancestor = self.mapTo(ancestor, QPoint(0, 0)).y()
            bottom = min(
                bottom,
                float(ancestor.contentsRect().bottom() + 1 - top_in_ancestor),
            )
            ancestor = ancestor.parentWidget()
        return max(0.0, bottom)

    def _geometry(self):
        label_height = max(16.0, float(self.fontMetrics().height()) + 2.0)
        label_gap = 3.0
        # Etwas mehr Abstand hält die Prozentangaben auch bei kleinen Karten
        # vollständig oberhalb des unteren Kartenrahmens.
        vertical_margin = 8.0
        available_width = max(20.0, self.width() - 16.0)
        available_height = max(
            20.0,
            2.0 * (
                self.height()
                - 2.0 * vertical_margin
                - label_gap
                - label_height
            ),
        )
        diameter = max(20.0, min(available_width, available_height))
        group_height = diameter / 2.0 + label_gap + label_height
        group_top = max(
            vertical_margin,
            (self.height() - group_height) / 2.0,
        )
        rect = QRectF(
            (self.width() - diameter) / 2.0,
            group_top,
            diameter,
            diameter,
        )
        return rect, QPointF(rect.center().x(), rect.center().y())

    def _set_value_from_position(self, position):
        _rect, center = self._geometry()
        dx = float(position.x()) - center.x()
        dy = center.y() - float(position.y())
        if dy < 0.0:
            angle = math.pi if dx < 0.0 else 0.0
        else:
            angle = math.atan2(dy, dx)
            angle = max(0.0, min(math.pi, angle))
        ratio = 1.0 - angle / math.pi
        value = self.minimum() + ratio * (self.maximum() - self.minimum())
        self.setValue(round(value))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setSliderDown(True)
        self._set_value_from_position(event.position())
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.isSliderDown():
            return super().mouseMoveEvent(event)
        self._set_value_from_position(event.position())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.isSliderDown():
            return super().mouseReleaseEvent(event)
        self._set_value_from_position(event.position())
        self.setSliderDown(False)
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect, center = self._geometry()
        span = self.maximum() - self.minimum()
        ratio = (
            0.0
            if span <= 0
            else (self.value() - self.minimum()) / float(span)
        )
        ratio = max(0.0, min(1.0, ratio))

        segment_count = 15
        segment_angle = 180.0 / segment_count
        gap_angle = 2.6
        scale_width = max(4.0, min(8.0, rect.width() * 0.055))
        scale_rect = rect.adjusted(
            scale_width / 2.0,
            scale_width / 2.0,
            -scale_width / 2.0,
            -scale_width / 2.0,
        )
        inactive_color = QColor(self.foreground_color)
        inactive_color.setAlpha(55)
        active_count = int(math.ceil(ratio * segment_count - 1e-9))
        for step in range(segment_count):
            pen = QPen(
                self.foreground_color if step < active_count else inactive_color,
                scale_width,
            )
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            start_angle = 180.0 - (step + 1) * segment_angle + gap_angle / 2.0
            painter.drawArc(
                scale_rect,
                int(round(start_angle * 16.0)),
                int(round((segment_angle - gap_angle) * 16.0)),
            )

        radius = min(scale_rect.width(), scale_rect.height()) / 2.0
        angle = math.radians(180.0 - ratio * 180.0)
        direction = QPointF(math.cos(angle), -math.sin(angle))
        perpendicular = QPointF(-direction.y(), direction.x())
        needle_length = radius * 0.78
        counterweight_length = radius * 0.14
        half_base_width = max(2.6, rect.width() * 0.026)
        tip = center + direction * needle_length
        left = center + perpendicular * half_base_width
        counterweight = center - direction * counterweight_length
        right = center - perpendicular * half_base_width
        needle = QPainterPath()
        needle.moveTo(tip)
        needle.lineTo(left)
        needle.lineTo(counterweight)
        needle.lineTo(right)
        needle.closeSubpath()
        needle_color = QColor("#c51d24")
        painter.setPen(QPen(self.foreground_color, 0.8))
        painter.setBrush(needle_color)
        painter.drawPath(needle)

        hub_radius = max(3.8, rect.width() * 0.036)
        painter.drawEllipse(center, hub_radius, hub_radius)
        inner_color = QColor(
            "#111111"
            if (
                0.2126 * self.foreground_color.red()
                + 0.7152 * self.foreground_color.green()
                + 0.0722 * self.foreground_color.blue()
            ) > 145.0
            else "#ffffff"
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(inner_color)
        painter.drawEllipse(center, hub_radius * 0.36, hub_radius * 0.36)

        painter.setPen(self.foreground_color)
        label_height = max(16.0, float(painter.fontMetrics().height()) + 2.0)
        visible_bottom = self.visible_bottom()
        label_top = min(
            center.y() + 3.0,
            visible_bottom - 10.0 - label_height,
        )
        label_top = max(0.0, label_top)
        label_margin = 8.0
        label_gap = 8.0
        label_center = self.width() / 2.0
        painter.drawText(
            QRectF(
                label_margin,
                label_top,
                max(1.0, label_center - label_margin - label_gap / 2.0),
                label_height,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "0 %",
        )
        painter.drawText(
            QRectF(
                label_center + label_gap / 2.0,
                label_top,
                max(
                    1.0,
                    self.width()
                    - label_margin
                    - label_center
                    - label_gap / 2.0,
                ),
                label_height,
            ),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "100 %",
        )

        if self.hasFocus():
            focus_color = QColor(self.foreground_color)
            focus_color.setAlpha(80)
            painter.setPen(QPen(focus_color, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 5, 5)


class CompactVerticalInputSlider(QSlider):
    """Bedienbarer vertikaler Eingaberegler im segmentierten Stil."""

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.foreground_color = QColor("#333333")
        self.setMinimumHeight(64)
        self.setFixedWidth(22)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

    def set_foreground_color(self, color):
        self.foreground_color = QColor(color)
        self.update()

    def _set_value_from_position(self, position):
        top = 2.0
        track_height = max(1.0, self.height() - 2.0 * top)
        ratio = (top + track_height - float(position.y())) / track_height
        ratio = max(0.0, min(1.0, ratio))
        value = self.minimum() + ratio * (self.maximum() - self.minimum())
        self.setValue(round(value))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setSliderDown(True)
        self._set_value_from_position(event.position())
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.isSliderDown():
            return super().mouseMoveEvent(event)
        self._set_value_from_position(event.position())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.isSliderDown():
            return super().mouseReleaseEvent(event)
        self._set_value_from_position(event.position())
        self.setSliderDown(False)
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        span = self.maximum() - self.minimum()
        ratio = (
            0.0
            if span <= 0
            else (self.value() - self.minimum()) / float(span)
        )
        ratio = max(0.0, min(1.0, ratio))

        segment_count = 15
        gap = max(1.0, min(2.2, self.height() * 0.009))
        top = 2.0
        track_height = max(float(segment_count), self.height() - 2.0 * top)
        segment_height = max(
            1.0,
            (track_height - gap * (segment_count - 1)) / segment_count,
        )
        segment_width = max(8.0, self.width() - 4.0)
        left = (self.width() - segment_width) / 2.0
        bottom = top + track_height
        inactive_color = QColor(self.foreground_color)
        inactive_color.setAlpha(55)
        active_count = int(math.ceil(ratio * segment_count - 1e-9))

        painter.setPen(Qt.PenStyle.NoPen)
        for step in range(segment_count):
            painter.setBrush(
                self.foreground_color
                if step < active_count
                else inactive_color
            )
            y = bottom - (step + 1) * segment_height - step * gap
            painter.drawRoundedRect(
                QRectF(left, y, segment_width, segment_height),
                1.3,
                1.3,
            )

        marker_y = bottom - ratio * track_height
        marker_y = max(top + 1.0, min(bottom - 1.0, marker_y))
        marker_left = left - 1.5
        marker_right = left + segment_width + 1.5
        painter.setPen(QPen(self.foreground_color, 3.6))
        painter.drawLine(
            QPointF(marker_left, marker_y),
            QPointF(marker_right, marker_y),
        )
        painter.setPen(QPen(QColor("#c51d24"), 2.0))
        painter.drawLine(
            QPointF(marker_left, marker_y),
            QPointF(marker_right, marker_y),
        )

        if self.hasFocus():
            focus_color = QColor(self.foreground_color)
            focus_color.setAlpha(80)
            painter.setPen(QPen(focus_color, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)


class CompactVerticalInputPage(QWidget):
    """Ordnet Skalentexte und vertikalen Eingaberegler mittig an."""

    def __init__(self, minimum, maximum, unit="", parent=None):
        super().__init__(parent)
        self.maximum_label = QLabel("100 %", self)
        self.minimum_label = QLabel("0 %", self)
        for label in (self.maximum_label, self.minimum_label):
            label.setProperty("nn_max_font_size", 10.0)
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        self.slider = CompactVerticalInputSlider(self)
        self.setMinimumHeight(64)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_positions()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_positions()

    def update_positions(self):
        vertical_padding = 2
        slider_width = self.slider.width()
        slider_left = round((self.width() - slider_width) / 2.0)
        self.slider.setGeometry(
            slider_left,
            vertical_padding,
            slider_width,
            max(1, self.height() - 2 * vertical_padding),
        )
        gap = 4
        label_width = max(0, slider_left - gap)
        label_height = max(
            12,
            self.maximum_label.fontMetrics().height() + 2,
            self.minimum_label.fontMetrics().height() + 2,
        )
        self.maximum_label.setGeometry(
            0,
            vertical_padding,
            label_width,
            label_height,
        )
        self.minimum_label.setGeometry(
            0,
            max(0, self.height() - label_height - vertical_padding),
            label_width,
            label_height,
        )


class CompactOutputBar(QWidget):
    """Segmentierte Balkenanzeige mit genauer Positionsmarke."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.minimum = 0
        self.maximum = 1000
        self.value = 0
        self.foreground_color = QColor("#333333")
        self.setFixedHeight(14)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def setRange(self, minimum, maximum):
        self.minimum = int(minimum)
        self.maximum = int(maximum)
        self.value = max(self.minimum, min(self.maximum, self.value))
        self.update()

    def setValue(self, value):
        self.value = max(self.minimum, min(self.maximum, int(value)))
        self.update()

    def set_foreground_color(self, color):
        self.foreground_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        span = self.maximum - self.minimum
        ratio = 0.0 if span <= 0 else (self.value - self.minimum) / span
        ratio = max(0.0, min(1.0, ratio))

        segment_count = 15
        gap = max(1.2, min(2.4, self.width() * 0.009))
        left = 2.0
        available_width = max(
            float(segment_count),
            self.width() - 2.0 * left - gap * (segment_count - 1),
        )
        segment_width = available_width / segment_count
        bar_height = max(6.0, min(9.0, self.height() * 0.62))
        top = (self.height() - bar_height) / 2.0
        inactive_color = QColor(self.foreground_color)
        inactive_color.setAlpha(55)
        active_count = int(math.ceil(ratio * segment_count - 1e-9))

        painter.setPen(Qt.PenStyle.NoPen)
        for step in range(segment_count):
            painter.setBrush(
                self.foreground_color
                if step < active_count
                else inactive_color
            )
            x = left + step * (segment_width + gap)
            segment = QRectF(x, top, segment_width, bar_height)
            painter.drawRoundedRect(segment, 1.3, 1.3)

        marker_x = left + ratio * (
            self.width() - 2.0 * left
        )
        marker_x = max(left + 1.0, min(self.width() - left - 1.0, marker_x))
        marker_top = top - 1.5
        marker_bottom = top + bar_height + 1.5
        painter.setPen(QPen(self.foreground_color, 3.6))
        painter.drawLine(
            QPointF(marker_x, marker_top),
            QPointF(marker_x, marker_bottom),
        )
        painter.setPen(QPen(QColor("#c51d24"), 2.0))
        painter.drawLine(
            QPointF(marker_x, marker_top),
            QPointF(marker_x, marker_bottom),
        )


class CompactVerticalOutputBar(QWidget):
    """Vertikale Variante der segmentierten analogen Balkenanzeige."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.minimum = 0
        self.maximum = 1000
        self.value = 0
        self.foreground_color = QColor("#333333")
        self.setMinimumHeight(64)
        self.setFixedWidth(22)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

    def setRange(self, minimum, maximum):
        self.minimum = int(minimum)
        self.maximum = int(maximum)
        self.value = max(self.minimum, min(self.maximum, self.value))
        self.update()

    def setValue(self, value):
        self.value = max(self.minimum, min(self.maximum, int(value)))
        self.update()

    def set_foreground_color(self, color):
        self.foreground_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        span = self.maximum - self.minimum
        ratio = 0.0 if span <= 0 else (self.value - self.minimum) / span
        ratio = max(0.0, min(1.0, ratio))

        segment_count = 15
        gap = max(1.0, min(2.2, self.height() * 0.009))
        top = 2.0
        track_height = max(
            float(segment_count),
            self.height() - 2.0 * top,
        )
        segment_height = max(
            1.0,
            (track_height - gap * (segment_count - 1)) / segment_count,
        )
        segment_width = max(8.0, self.width() - 4.0)
        left = (self.width() - segment_width) / 2.0
        bottom = top + track_height
        inactive_color = QColor(self.foreground_color)
        inactive_color.setAlpha(55)
        active_count = int(math.ceil(ratio * segment_count - 1e-9))

        painter.setPen(Qt.PenStyle.NoPen)
        for step in range(segment_count):
            painter.setBrush(
                self.foreground_color
                if step < active_count
                else inactive_color
            )
            y = bottom - (step + 1) * segment_height - step * gap
            painter.drawRoundedRect(
                QRectF(left, y, segment_width, segment_height),
                1.3,
                1.3,
            )

        marker_y = bottom - ratio * track_height
        marker_y = max(top + 1.0, min(bottom - 1.0, marker_y))
        marker_left = left - 1.5
        marker_right = left + segment_width + 1.5
        painter.setPen(QPen(self.foreground_color, 3.6))
        painter.drawLine(
            QPointF(marker_left, marker_y),
            QPointF(marker_right, marker_y),
        )
        painter.setPen(QPen(QColor("#c51d24"), 2.0))
        painter.drawLine(
            QPointF(marker_left, marker_y),
            QPointF(marker_right, marker_y),
        )


class CompactVerticalOutputPage(QWidget):
    """Zentriert den Balken an der Kachel, unabhängig von den Skalentexten."""

    def __init__(self, minimum, maximum, unit, card, parent=None):
        super().__init__(parent)
        self.card = card
        self.maximum_label = QLabel("100 %", self)
        self.minimum_label = QLabel("0 %", self)
        for label in (self.maximum_label, self.minimum_label):
            label.setProperty("nn_max_font_size", 10.0)
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )
        self.bar = CompactVerticalOutputBar(card)
        self.bar.setVisible(False)
        self.setMinimumHeight(64)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_positions()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.update_positions()

    def paintEvent(self, event):
        self.update_positions()
        super().paintEvent(event)

    def update_positions(self):
        card_center = self.card.width() / 2.0
        bar_width = self.bar.width()
        bar_left = round(card_center - bar_width / 2.0)
        page_top = self.mapTo(self.card, QPoint(0, 0)).y()
        self.bar.setGeometry(
            bar_left,
            page_top,
            bar_width,
            self.height(),
        )
        if self.bar.isVisible():
            self.bar.raise_()

        gap = 4
        card_center_in_page = self.mapFrom(
            self.card,
            QPoint(round(card_center), 0),
        ).x()
        label_width = max(
            0,
            round(card_center_in_page - bar_width / 2.0 - gap),
        )
        label_height = max(
            12,
            self.maximum_label.fontMetrics().height() + 2,
            self.minimum_label.fontMetrics().height() + 2,
        )
        self.maximum_label.setGeometry(0, 0, label_width, label_height)
        self.minimum_label.setGeometry(
            0,
            max(0, self.height() - label_height),
            label_width,
            label_height,
        )


class CompactOutputGauge(QWidget):
    """Kompakte halbkreisförmige Zeigeranzeige für einen Output."""

    def __init__(self, minimum, maximum, unit="", parent=None):
        super().__init__(parent)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.value = self.minimum
        self.unit = str(unit or "")
        self.foreground_color = QColor("#333333")
        self.setProperty("nn_max_font_size", 10.0)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_value(self, value):
        self.value = float(value)
        self.update()

    def set_foreground_color(self, color):
        self.foreground_color = QColor(color)
        self.update()

    def visible_bottom(self):
        """Liefert die durch alle Elternwidgets tatsächlich sichtbare Unterkante."""

        bottom = float(self.height())
        ancestor = self.parentWidget()
        while ancestor is not None:
            top_in_ancestor = self.mapTo(ancestor, QPoint(0, 0)).y()
            bottom = min(
                bottom,
                float(ancestor.contentsRect().bottom() + 1 - top_in_ancestor),
            )
            ancestor = ancestor.parentWidget()
        return max(0.0, bottom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        label_height = max(16.0, float(self.fontMetrics().height()) + 2.0)
        label_gap = 3.0
        vertical_margin = 8.0
        available_width = max(20.0, self.width() - 16.0)
        available_height = max(
            20.0,
            2.0 * (
                self.height()
                - 2.0 * vertical_margin
                - label_gap
                - label_height
            ),
        )
        diameter = max(20.0, min(available_width, available_height))
        group_height = diameter / 2.0 + label_gap + label_height
        group_top = max(
            vertical_margin,
            (self.height() - group_height) / 2.0,
        )
        rect = QRectF(
            (self.width() - diameter) / 2.0,
            group_top,
            diameter,
            diameter,
        )
        center = QPointF(rect.center().x(), rect.center().y())
        span = self.maximum - self.minimum
        ratio = 0.0 if span <= 0.0 else (self.value - self.minimum) / span
        ratio = max(0.0, min(1.0, ratio))

        # Die segmentierte Skala verwendet ausschließlich die automatisch zur
        # Kachelfarbe gewählte Kontrastfarbe. Dadurch entsteht keine
        # irreführende Grün-Gelb-Rot-Bewertung des Messwerts.
        segment_count = 15
        segment_angle = 180.0 / segment_count
        gap_angle = 2.6
        scale_width = max(4.0, min(8.0, diameter * 0.055))
        scale_rect = rect.adjusted(
            scale_width / 2.0,
            scale_width / 2.0,
            -scale_width / 2.0,
            -scale_width / 2.0,
        )
        inactive_color = QColor(self.foreground_color)
        inactive_color.setAlpha(55)
        active_count = int(math.ceil(ratio * segment_count - 1e-9))
        for step in range(segment_count):
            segment_color = (
                self.foreground_color
                if step < active_count
                else inactive_color
            )
            pen = QPen(segment_color, scale_width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            start_angle = (
                180.0 - (step + 1) * segment_angle + gap_angle / 2.0
            )
            painter.drawArc(
                scale_rect,
                int(round(start_angle * 16.0)),
                int(round((segment_angle - gap_angle) * 16.0)),
            )

        radius_x = scale_rect.width() / 2.0
        radius_y = scale_rect.height() / 2.0
        angle = math.radians(180.0 - ratio * 180.0)
        direction = QPointF(math.cos(angle), -math.sin(angle))
        perpendicular = QPointF(-direction.y(), direction.x())
        needle_length = min(radius_x, radius_y) * 0.78
        counterweight_length = min(radius_x, radius_y) * 0.14
        half_base_width = max(2.6, diameter * 0.026)
        tip = QPointF(
            center.x() + direction.x() * needle_length,
            center.y() + direction.y() * needle_length,
        )
        left = QPointF(
            center.x() + perpendicular.x() * half_base_width,
            center.y() + perpendicular.y() * half_base_width,
        )
        counterweight = QPointF(
            center.x() - direction.x() * counterweight_length,
            center.y() - direction.y() * counterweight_length,
        )
        right = QPointF(
            center.x() - perpendicular.x() * half_base_width,
            center.y() - perpendicular.y() * half_base_width,
        )
        needle = QPainterPath()
        needle.moveTo(tip)
        needle.lineTo(left)
        needle.lineTo(counterweight)
        needle.lineTo(right)
        needle.closeSubpath()
        needle_color = QColor("#c51d24")
        painter.setPen(QPen(self.foreground_color, 0.8))
        painter.setBrush(needle_color)
        painter.drawPath(needle)

        hub_radius = max(3.8, diameter * 0.036)
        painter.setBrush(needle_color)
        painter.drawEllipse(center, hub_radius, hub_radius)
        foreground_luminance = (
            0.2126 * self.foreground_color.red()
            + 0.7152 * self.foreground_color.green()
            + 0.0722 * self.foreground_color.blue()
        )
        hub_inner_color = QColor(
            "#111111" if foreground_luminance > 145.0 else "#ffffff"
        )
        painter.setBrush(hub_inner_color)
        painter.drawEllipse(center, hub_radius * 0.36, hub_radius * 0.36)

        painter.setPen(self.foreground_color)
        visible_bottom = self.visible_bottom()
        label_top = min(
            rect.center().y() + 3.0,
            visible_bottom - 10.0 - label_height,
        )
        label_top = max(0.0, label_top)
        label_margin = 8.0
        horizontal_label_gap = 8.0
        label_center = self.width() / 2.0
        painter.drawText(
            QRectF(
                label_margin,
                label_top,
                max(
                    1.0,
                    label_center - label_margin - horizontal_label_gap / 2.0,
                ),
                label_height,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "0 %",
        )
        painter.drawText(
            QRectF(
                label_center + horizontal_label_gap / 2.0,
                label_top,
                max(
                    1.0,
                    self.width()
                    - label_margin
                    - label_center
                    - horizontal_label_gap / 2.0,
                ),
                label_height,
            ),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "100 %",
        )


class ExperimentCard(QFrame):
    """Weiße Bedienkarte mit sauber transparenten, abgerundeten Ecken."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_for_editing = False
        self.card_color = QColor("#ffffff")
        self.card_transparent = False
        self.text_color = QColor("#111111")
        self.show_border = True
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.apply_card_colors()

    def set_card_color(self, color):
        selected = QColor(color)
        if not selected.isValid():
            return
        self.card_color = selected
        luminance = (
            0.2126 * selected.red()
            + 0.7152 * selected.green()
            + 0.0722 * selected.blue()
        )
        self.text_color = QColor("#ffffff" if luminance < 145.0 else "#111111")
        self.apply_card_colors()
        for slider in self.findChildren(CompactInputSlider):
            slider.set_foreground_color(self.text_color)
        for dial in self.findChildren(CompactInputDial):
            dial.set_foreground_color(self.text_color)
        for slider in self.findChildren(CompactVerticalInputSlider):
            slider.set_foreground_color(self.text_color)
        for bar in self.findChildren(CompactOutputBar):
            bar.set_foreground_color(self.text_color)
        for bar in self.findChildren(CompactVerticalOutputBar):
            bar.set_foreground_color(self.text_color)
        for gauge in self.findChildren(CompactOutputGauge):
            gauge.set_foreground_color(self.text_color)
        self.update()

    def set_card_transparent(self, transparent):
        self.card_transparent = bool(transparent)
        self.update()

    def apply_card_colors(self):
        color_name = self.text_color.name()
        self.setStyleSheet(
            "QLabel { border:none; background:transparent; color:%s; } "
            "QCheckBox { color:%s; }" % (color_name, color_name)
        )

    def set_selected_for_editing(self, selected):
        self.selected_for_editing = bool(selected)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_responsive_input_editor()
        for page in self.findChildren(CompactVerticalInputPage):
            page.update_positions()
            QTimer.singleShot(0, page.update_positions)
        for page in self.findChildren(CompactVerticalOutputPage):
            page.update_positions()
            QTimer.singleShot(0, page.update_positions)

    def resize_responsive_input_editor(self):
        """Hält das gestapelte Eingabefeld kompakt und mittig."""

        editor = getattr(self, "responsive_input_editor", None)
        if (
            editor is None
            or not getattr(self, "responsive_input_stacked", False)
        ):
            return

        desired_width = editor.fontMetrics().horizontalAdvance(editor.text()) + 28
        outer_layout = self.layout()
        if outer_layout is not None:
            margins = outer_layout.contentsMargins()
            horizontal_margins = margins.left() + margins.right()
        else:
            horizontal_margins = 16
        available_width = max(1, self.width() - horizontal_margins)
        editor.setFixedWidth(max(64, min(available_width, desired_width)))

    def prepare_responsive_layout(self, width, height):
        """Ordnet den Inhalt hoher Eingabekarten übersichtlich untereinander an."""

        binary_grid = getattr(self, "responsive_binary_grid", None)
        binary_name = getattr(self, "responsive_binary_name", None)
        binary_value = getattr(self, "responsive_binary_value", None)
        binary_state_label = getattr(
            self, "responsive_binary_state_label", None
        )
        if (
            binary_grid is not None
            and binary_name is not None
            and binary_value is not None
        ):
            intermediate = bool(
                getattr(self, "binary_intermediate_enabled", False)
            )
            tall = bool(intermediate and float(height) >= 78.0)
            binary_stacked = bool(not intermediate and float(height) >= 78.0)
            state = (intermediate, tall, binary_stacked)
            if state != getattr(self, "responsive_binary_state", None):
                self.responsive_binary_state = state
                binary_grid.removeWidget(binary_name)
                binary_grid.removeWidget(binary_value)
                if binary_state_label is not None:
                    binary_grid.removeWidget(binary_state_label)
                for column in range(5):
                    binary_grid.setColumnStretch(column, 0)
                    binary_grid.setColumnMinimumWidth(column, 0)
                binary_grid.setHorizontalSpacing(0)
                binary_grid.setRowMinimumHeight(1, 0)
                if not intermediate:
                    binary_name.setMinimumWidth(1)
                    binary_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    if binary_stacked:
                        binary_grid.setAlignment(Qt.AlignmentFlag(0))
                        binary_grid.setHorizontalSpacing(4)
                        binary_grid.setVerticalSpacing(0)
                        binary_grid.addWidget(binary_name, 0, 0, 1, 5)
                        if binary_state_label is not None:
                            binary_grid.addWidget(
                                binary_state_label,
                                1,
                                0,
                                1,
                                5,
                                Qt.AlignmentFlag.AlignCenter,
                            )
                    else:
                        binary_grid.setAlignment(Qt.AlignmentFlag(0))
                        binary_grid.setHorizontalSpacing(4)
                        binary_grid.setColumnStretch(0, 1)
                        binary_grid.setColumnStretch(1, 1)
                        binary_grid.addWidget(binary_name, 0, 0)
                        if binary_state_label is not None:
                            binary_grid.addWidget(
                                binary_state_label,
                                0,
                                1,
                                Qt.AlignmentFlag.AlignCenter,
                            )
                elif tall:
                    # Das Raster muss die volle Kartenbreite behalten. Eine
                    # zentrierte Rasterbreite würde sich nach einem zuvor
                    # gekürzten Namen richten und beim Vergrößern nicht mehr
                    # auf den vollständigen Text anwachsen.
                    binary_grid.setAlignment(Qt.AlignmentFlag(0))
                    binary_grid.setVerticalSpacing(0)
                    binary_grid.setRowMinimumHeight(1, 10)
                    binary_name.setMinimumWidth(28)
                    binary_name.setSizePolicy(
                        QSizePolicy.Policy.Preferred,
                        QSizePolicy.Policy.Preferred,
                    )
                    binary_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    binary_grid.addWidget(binary_name, 0, 0, 1, 5)
                    binary_grid.addWidget(
                        binary_value, 2, 0, 1, 5,
                        Qt.AlignmentFlag.AlignCenter,
                    )
                else:
                    # In flachen Karten bilden Name und Zwischenwert eine
                    # zentrierte Gruppe. Die mittlere Spalte garantiert einen
                    # kleinen Abstand, ohne beide Texte auseinanderzuziehen.
                    binary_grid.setAlignment(Qt.AlignmentFlag(0))
                    binary_grid.setVerticalSpacing(0)
                    binary_grid.setColumnStretch(0, 1)
                    binary_grid.setColumnMinimumWidth(2, 8)
                    binary_grid.setColumnStretch(4, 1)
                    binary_name.setMinimumWidth(1)
                    binary_name.setSizePolicy(
                        QSizePolicy.Policy.Preferred,
                        QSizePolicy.Policy.Preferred,
                    )
                    binary_name.setAlignment(
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                    binary_grid.addWidget(binary_name, 0, 1)
                    binary_grid.addWidget(
                        binary_value, 0, 3, Qt.AlignmentFlag.AlignLeft
                    )
                main_layout = getattr(
                    self, "responsive_binary_main_layout", None
                )
                if main_layout is not None:
                    spacer_policy = (
                        QSizePolicy.Policy.Expanding
                        if intermediate
                        else QSizePolicy.Policy.Fixed
                    )
                    for index in (0, 2, 4):
                        item = main_layout.itemAt(index)
                        spacer = item.spacerItem() if item is not None else None
                        if spacer is not None:
                            spacer.changeSize(
                                0,
                                0,
                                QSizePolicy.Policy.Minimum,
                                spacer_policy,
                            )
                    if intermediate:
                        main_layout.setStretch(0, 1)
                        # In hohen Zwischenwertkacheln liegen Name und Wert
                        # oben, die eigentliche Anzeige weiter unten.
                        main_layout.setStretch(2, 2 if tall else 0)
                        main_layout.setStretch(4, 1)
                    else:
                        # Ohne Zwischenwert soll das Raster exakt wie bei
                        # der binären Eingangskachel die Höhe ausfüllen.
                        main_layout.setStretch(0, 0)
                        main_layout.setStretch(2, 0)
                        main_layout.setStretch(4, 0)
                    main_layout.invalidate()
                binary_grid.invalidate()
            return tall

        grid = getattr(self, "responsive_input_grid", None)
        name = getattr(self, "responsive_input_name", None)
        editor = getattr(self, "responsive_input_editor", None)
        if grid is not None and name is not None and editor is not None:
            name_text = getattr(name, "full_text", name.text())
            required_width = (
                name.fontMetrics().horizontalAdvance(str(name_text))
                + editor.fontMetrics().horizontalAdvance(editor.text())
                + max(0, grid.horizontalSpacing())
                + 28
            )
            width_requires_stacking = float(width) < float(required_width)
            stacked = bool(
                float(height) >= 78.0
                or (width_requires_stacking and float(height) >= 62.0)
            )
            if stacked != getattr(self, "responsive_input_stacked", None):
                self.responsive_input_stacked = stacked
                if stacked:
                    grid.addWidget(name, 0, 0, 1, 2)
                    editor.setSizePolicy(
                        QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Fixed,
                    )
                    if hasattr(editor, "setAlignment"):
                        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    grid.addWidget(
                        editor,
                        1,
                        0,
                        1,
                        2,
                        Qt.AlignmentFlag.AlignCenter,
                    )
                else:
                    grid.addWidget(name, 0, 0, 1, 1)
                    editor.setSizePolicy(
                        QSizePolicy.Policy.Preferred,
                        QSizePolicy.Policy.Fixed,
                    )
                    if hasattr(editor, "setAlignment"):
                        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    grid.addWidget(
                        editor, 0, 1, 1, 1, Qt.AlignmentFlag.AlignCenter
                    )
                grid.invalidate()
            if stacked:
                self.resize_responsive_input_editor()
            return stacked

        grid = getattr(self, "responsive_output_grid", None)
        name = getattr(self, "responsive_output_name", None)
        value = getattr(self, "responsive_output_value", None)
        if grid is None or name is None or value is None:
            return False
        name_text = getattr(name, "full_text", name.text())
        value_text = getattr(value, "full_text", value.text())
        required_width = (
            name.fontMetrics().horizontalAdvance(str(name_text))
            + value.fontMetrics().horizontalAdvance(str(value_text))
            + max(0, grid.horizontalSpacing())
            + 20
        )
        width_requires_stacking = float(width) < float(required_width)
        stacked = bool(
            (
                getattr(self, "responsive_output_bar_mode", False)
                or getattr(self, "responsive_output_pointer_mode", False)
            )
            and (
                float(height) >= 78.0
                or (width_requires_stacking and float(height) >= 62.0)
            )
        )
        if stacked != getattr(self, "responsive_output_stacked", None):
            self.responsive_output_stacked = stacked
            if stacked:
                grid.addWidget(name, 0, 0, 1, 2)
                value.setAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
                grid.addWidget(value, 1, 0, 1, 2)
            else:
                grid.addWidget(name, 0, 0, 1, 1)
                value.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                grid.addWidget(value, 0, 1, 1, 1)
            grid.invalidate()
        return stacked

    def content_scale_for_size(self, width, height):
        stacked = self.prepare_responsive_layout(width, height)
        if getattr(self, "responsive_binary_output", False):
            if getattr(self, "binary_intermediate_enabled", False):
                if stacked:
                    return min(float(width) / 150.0, float(height) / 100.0)
                return min(float(width) / 190.0, float(height) / 50.0)
            return min(float(width) / 150.0, float(height) / 80.0)
        if getattr(self, "responsive_input_grid", None) is not None:
            if stacked:
                return min(float(width) / 150.0, float(height) / 100.0)
            return min(float(width) / 180.0, float(height) / 50.0)
        if getattr(self, "responsive_output_grid", None) is not None:
            if (
                getattr(self, "responsive_output_bar_mode", False)
                or getattr(self, "responsive_output_pointer_mode", False)
            ):
                if stacked:
                    return min(float(width) / 150.0, float(height) / 100.0)
                return min(float(width) / 180.0, float(height) / 50.0)
            return min(float(width) / 245.0, float(height) / 62.0)
        return min(float(width) / 245.0, float(height) / 62.0)

    def apply_content_scale(self, scale):
        """Passt Schrift und Innenabstände proportional an die Kartengröße an."""

        maximum_factor = float(getattr(self, "maximum_content_scale", 2.50))
        if (
            getattr(self, "responsive_output_grid", None) is not None
            and not getattr(self, "responsive_output_bar_mode", False)
            and not getattr(self, "responsive_output_pointer_mode", False)
        ):
            maximum_factor = min(maximum_factor, 2.50)
        minimum_factor = float(getattr(self, "minimum_content_scale", 0.70))
        factor = max(minimum_factor, min(maximum_factor, float(scale)))

        for widget in [self] + self.findChildren(QWidget):
            base_size = widget.property("nn_base_font_size")
            if base_size is None:
                current_size = widget.font().pointSizeF()
                if current_size <= 0.0:
                    continue
                base_size = float(current_size)
                widget.setProperty("nn_base_font_size", base_size)

            font_size = max(6.0, float(base_size) * factor)
            maximum_font_size = widget.property("nn_max_font_size")
            if maximum_font_size is not None:
                font_size = min(font_size, float(maximum_font_size))
            font = widget.font()
            font.setPointSizeF(font_size)
            widget.setFont(font)

            base_minimum_width = widget.property("nn_base_minimum_width")
            base_maximum_width = widget.property("nn_base_maximum_width")
            if base_minimum_width is not None:
                widget.setMinimumWidth(
                    max(1, round(float(base_minimum_width) * factor))
                )
            if base_maximum_width is not None:
                widget.setMaximumWidth(
                    max(1, round(float(base_maximum_width) * factor))
                )

            if isinstance(widget, ElidedLabel):
                widget.update_elided_text()

        input_editor = getattr(self, "responsive_input_editor", None)
        if input_editor is not None:
            if hasattr(input_editor, "setAlignment"):
                input_editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if getattr(self, "responsive_input_stacked", False):
                input_editor.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )

        self.scale_layout(self.layout(), factor)
        self.resize_responsive_input_editor()
        self.updateGeometry()
        self.update()

    @classmethod
    def scale_layout(cls, layout, factor):
        if layout is None:
            return

        base_margins = getattr(layout, "nn_base_margins", None)
        if base_margins is None:
            margins = layout.contentsMargins()
            base_margins = (
                margins.left(), margins.top(), margins.right(), margins.bottom()
            )
            layout.nn_base_margins = base_margins

        layout.setContentsMargins(
            *[max(0, round(value * factor)) for value in base_margins]
        )

        base_spacing = getattr(layout, "nn_base_spacing", None)
        if base_spacing is None:
            base_spacing = max(0, layout.spacing())
            layout.nn_base_spacing = base_spacing
        layout.setSpacing(max(0, round(base_spacing * factor)))

        for index in range(layout.count()):
            child_layout = layout.itemAt(index).layout()
            if child_layout is not None:
                cls.scale_layout(child_layout, factor)

    def paintEvent(self, event):
        for page in self.findChildren(CompactVerticalOutputPage):
            page.update_positions()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            6.0,
            6.0,
        )
        if not self.card_transparent:
            painter.fillPath(path, self.card_color)
        if self.selected_for_editing:
            painter.setPen(QPen(QColor("#c51d24"), 2.0))
        elif self.show_border:
            painter.setPen(QPen(QColor("#000000"), 1.0))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)


class CharacteristicCard(ExperimentCard):
    """Resizable characteristic card using the shared design appearance."""

    def __init__(self, translator, settings):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        self.plot = CurvePlot(translator, settings, self)
        layout.addWidget(self.plot)

    def content_scale_for_size(self, width, height):
        return 1.0  # Grow the plotting area, keep axis labels legible.


class SimplifiedNetworkCard(ExperimentCard):
    """Zeigt das aktuelle Netz kompakt und ohne Bearbeitungsfunktionen an."""

    def __init__(
        self, network, translate, color_settings=None, input_mappings=None,
        output_mappings=None, parent=None,
    ):
        super().__init__(parent)
        self.network = network
        self.translate = translate
        self.color_settings = dict(color_settings or {})
        self.show_input_values = False
        self.show_output_values = True
        self.input_mappings = {
            mapping["neuron"].id: mapping
            for mapping in (input_mappings or [])
            if mapping.get("neuron") is not None
        }
        self.output_mappings = {
            mapping["neuron"].id: mapping
            for mapping in (output_mappings or [])
            if mapping.get("neuron") is not None
        }
        self.hovered_neuron_id = None
        self.visible_tooltip_neuron_id = None
        self.pinned_neuron_id = None
        self.reset_focus_rect = QRectF()
        self.formula_rect = QRectF()
        self.formula_info_rect = QRectF()
        self.formula_tooltip = ""
        self.formula_details = {}
        self.node_hit_areas = []
        self.connection_hit_areas = []
        # Die Netzstruktur ändert sich während eines Experiments nicht. Sie
        # wird deshalb nur einmal ermittelt; Laufzeitwerte bleiben weiterhin
        # direkt an den Neuron- und Verbindungsobjekten aktuell.
        try:
            self.cached_layers = [
                list(layer) for layer in self.network.get_topological_layers()
                if layer
            ]
        except (AttributeError, ValueError):
            self.cached_layers = []
        self.cached_connections = list(self.network.get_connections())
        self.cached_inputs = list(self.network.get_input_neurons())
        self.cached_outputs = list(self.network.get_output_neurons())
        # Schnell aufeinanderfolgende Reglerereignisse dürfen nicht für jeden
        # Zwischenwert ein vollständiges Neuzeichnen der Netzwerkkarte starten.
        self.repaint_timer = QTimer(self)
        self.repaint_timer.setSingleShot(True)
        self.repaint_timer.setInterval(25)
        self.repaint_timer.timeout.connect(self.update)
        self.setMouseTracking(True)
        self.setMinimumSize(240, 170)

    @staticmethod
    def activity_ratio(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(value):
            return 0.0
        if -1.0 <= value <= 1.0:
            return max(0.0, min(1.0, (value + 1.0) / 2.0 if value < 0.0 else value))
        return max(0.0, min(1.0, 0.5 + math.atan(value) / math.pi))

    def layers(self):
        return self.cached_layers

    def set_show_output_values(self, enabled):
        self.show_output_values = bool(enabled)
        self.update()

    def set_show_input_values(self, enabled):
        self.show_input_values = bool(enabled)
        self.update()

    @staticmethod
    def neuron_id_text(neuron):
        """Gibt die technische Neuron-ID in der sichtbaren Form N15 zurück."""

        neuron_id = str(getattr(neuron, "id", ""))
        return neuron_id if neuron_id.upper().startswith("N") else f"N{neuron_id}"

    def output_display_data(self, neuron):
        """Liefert Balkenposition und lesbaren Wert eines Output-Neurons."""

        mapping = self.output_mappings.get(neuron.id, {})
        internal_value = float(neuron.output_value)
        if mapping.get("data_type") == "binary":
            ratio = max(0.0, min(1.0, internal_value))
            decision = 1 if ratio >= 0.5 else 0
            return ratio, f"{decision}  {round(ratio * 100.0):d}%"
        calibration = TrainingDataIO.normalize_calibration(mapping.get("calibration"))
        raw_value = TrainingDataIO.unscale_value(
            internal_value, calibration, getattr(self.translate, "text", None)
        )
        if calibration["mode"] in ("minmax_0_1", "minmax_minus1_1"):
            minimum = float(calibration["source_min"])
            maximum = float(calibration["source_max"])
            ratio = (
                0.0 if maximum <= minimum
                else (raw_value - minimum) / (maximum - minimum)
            )
        else:
            ratio = self.activity_ratio(internal_value)
        unit = str(mapping.get("unit") or "")
        text = format_number(raw_value, 5)
        if unit:
            text += f" {unit}"
        return max(0.0, min(1.0, ratio)), text

    def input_display_data(self, neuron):
        """Liefert Balkenposition und lesbaren Wert eines Input-Neurons."""

        mapping = self.input_mappings.get(neuron.id, {})
        internal_value = float(neuron.output_value)
        if mapping.get("data_type") == "binary":
            ratio = max(0.0, min(1.0, internal_value))
            return ratio, f"{round(ratio * 100.0):d}%"
        calibration = TrainingDataIO.normalize_calibration(mapping.get("calibration"))
        raw_value = TrainingDataIO.unscale_value(
            internal_value, calibration, getattr(self.translate, "text", None)
        )
        if calibration["mode"] in ("minmax_0_1", "minmax_minus1_1"):
            minimum = float(calibration["source_min"])
            maximum = float(calibration["source_max"])
            ratio = (
                0.0 if maximum <= minimum
                else (raw_value - minimum) / (maximum - minimum)
            )
        else:
            ratio = self.activity_ratio(internal_value)
        unit = str(mapping.get("unit") or "")
        text = format_number(raw_value, 5)
        if unit:
            text += f" {unit}"
        return max(0.0, min(1.0, ratio)), text

    def update_network_state(self):
        if not self.repaint_timer.isActive():
            self.repaint_timer.start()

    def calculation_text(self, neuron_id):
        """Liefert Kurzform und Details der aktuellen Neuronenberechnung."""

        self.formula_details = {}

        neuron = next(
            (
                item
                for layer in self.cached_layers
                for item in layer
                if item.id == neuron_id
            ),
            None,
        )
        if neuron is None:
            return "", ""
        output_value = float(getattr(neuron, "output_value", 0.0))
        neuron_label = self.neuron_id_text(neuron)
        if neuron in self.cached_inputs:
            input_value = float(getattr(neuron, "input_value", output_value))
            short_text = self.translate(
                f"{neuron_label}: X = {format_number(input_value, 6)} → "
                f"Y = {format_number(output_value, 6)}",
                f"{neuron_label}: X = {format_number(input_value, 6)} → "
                f"Y = {format_number(output_value, 6)}",
            )
            tooltip = self.translate(
                f"{neuron_label} ist ein Eingabeneuron.\n"
                f"Der Eingangswert X = {format_number(input_value, 8)} wird als "
                f"Ausgabewert Y = {format_number(output_value, 8)} weitergegeben.",
                f"{neuron_label} is an input neuron.\n"
                f"Input value X = {format_number(input_value, 8)} is passed on as "
                f"output value Y = {format_number(output_value, 8)}.",
            )
            self.formula_details = {
                "kind": "input",
                "neuron": neuron_label,
                "input": input_value,
                "output": output_value,
            }
            return short_text, tooltip

        bias = float(getattr(neuron, "bias", 0.0))
        terms = []
        contribution_rows = []
        weighted_sum = bias
        for connection in getattr(neuron, "incoming_connections", []):
            source = connection.source_neuron
            source_value = float(getattr(source, "output_value", 0.0))
            weight = float(getattr(connection, "weight", 0.0))
            contribution = source_value * weight
            weighted_sum += contribution
            terms.append(
                f"{self.neuron_id_text(source)}.Y "
                f"({format_number(source_value, 6)}) × "
                f"W{connection.id} ({format_number(weight, 6)})"
            )
            contribution_rows.append(
                (
                    self.neuron_id_text(source),
                    source_value,
                    f"W{connection.id}",
                    weight,
                    contribution,
                )
            )
        activation = str(getattr(neuron, "activation_function", "Linear"))
        raw_output = None
        raw_output_unit = ""
        if neuron in self.cached_outputs:
            mapping = self.output_mappings.get(neuron.id, {})
            calibration = TrainingDataIO.normalize_calibration(
                mapping.get("calibration")
            )
            if (
                mapping.get("data_type") != "binary"
                and calibration["mode"] != "none"
            ):
                raw_output = TrainingDataIO.unscale_value(
                    output_value,
                    calibration,
                    getattr(self.translate, "text", None),
                )
                raw_output_unit = str(mapping.get("unit") or "")
        short_text = (
            f"{neuron_label}: Σ = {format_number(weighted_sum, 6)}  →  "
            f"{activation}(Σ) = {format_number(output_value, 6)}"
        )
        expression = " + ".join(terms)
        if expression:
            expression += " + "
        expression += self.translate(
            f"Bias ({format_number(bias, 6)})",
            f"bias ({format_number(bias, 6)})",
        )
        tooltip = self.translate(
            f"Berechnung für {neuron_label}\n"
            f"Σ = {expression}\n"
            f"Σ = {format_number(weighted_sum, 8)}\n"
            f"Y = {activation}(Σ) = {format_number(output_value, 8)}",
            f"Calculation for {neuron_label}\n"
            f"Σ = {expression}\n"
            f"Σ = {format_number(weighted_sum, 8)}\n"
            f"Y = {activation}(Σ) = {format_number(output_value, 8)}",
        )
        self.formula_details = {
            "kind": "calculation",
            "neuron": neuron_label,
            "rows": contribution_rows,
            "contribution_sum": sum(row[4] for row in contribution_rows),
            "bias": bias,
            "sum": weighted_sum,
            "activation": activation,
            "output": output_value,
            "raw_output": raw_output,
            "raw_output_unit": raw_output_unit,
        }
        return short_text, tooltip

    def paintEvent(self, event):
        super().paintEvent(event)
        layers = self.layers()
        if not layers:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Die Karte wird innerhalb der Anwendungsansicht mitgezoomt. Durch
        # den Kehrwert bleiben die Verbindungslinien am Bildschirm trotzdem
        # gut lesbar, ohne ihre relative Gewichtung zu verlieren.
        view_zoom = 1.0
        proxy = self.graphicsProxyWidget()
        if proxy is not None and proxy.scene() is not None:
            views = proxy.scene().views()
            if views:
                view_zoom = max(0.2, abs(float(views[0].transform().m11())))
        # Ein proportionaler Innenrand hält die äußeren Neuronen sichtbar vom
        # Kartenrahmen fern. Unten bleibt zusätzlich Platz für die Fokus-Taste.
        card_rect = QRectF(self.rect())
        horizontal_margin = max(24.0, min(42.0, card_rect.width() * 0.065))
        top_margin = max(22.0, min(36.0, card_rect.height() * 0.06))
        bottom_margin = max(42.0, min(54.0, card_rect.height() * 0.10))
        inputs = self.cached_inputs
        outputs = self.cached_outputs
        input_panel_width = 0.0
        if (
            self.show_input_values
            and inputs
            and card_rect.width() >= 275.0
            and card_rect.height() / max(1, len(inputs)) >= 11.0
        ):
            input_panel_width = max(
                78.0, min(140.0, card_rect.width() * 0.23)
            )
        output_panel_width = 0.0
        if (
            self.show_output_values
            and outputs
            and card_rect.width() >= 275.0
            and card_rect.height() / max(1, len(outputs)) >= 11.0
        ):
            output_panel_width = max(
                78.0, min(140.0, card_rect.width() * 0.23)
            )
        inner = card_rect.adjusted(
            horizontal_margin + input_panel_width,
            top_margin,
            -(horizontal_margin + output_panel_width),
            -bottom_margin,
        )
        if inner.width() < 20.0 or inner.height() < 20.0:
            return
        max_count = max(len(layer) for layer in layers)
        column_count = max(1, len(layers))
        radius = max(
            3.0,
            min(
                11.0,
                inner.height() / max(3.2, max_count * 2.7),
                inner.width() / max(4.0, column_count * 4.0),
            ),
        )
        positions = {}
        self.node_hit_areas = []
        self.connection_hit_areas = []
        vertical_step = (
            0.0 if max_count <= 1 else inner.height() / (max_count - 1)
        )
        for column, layer in enumerate(layers):
            x = inner.center().x() if column_count == 1 else (
                inner.left() + column * inner.width() / (column_count - 1)
            )
            layer_top = inner.center().y() - (len(layer) - 1) * vertical_step / 2.0
            for row, neuron in enumerate(layer):
                y = layer_top + row * vertical_step
                positions[neuron.id] = QPointF(x, y)

        connections = self.cached_connections
        focus_id = (
            self.pinned_neuron_id
            if self.pinned_neuron_id is not None
            else self.hovered_neuron_id
        )
        contributions = []
        for connection in connections:
            contribution = abs(
                float(connection.weight)
                * float(connection.source_neuron.output_value)
            )
            contributions.append(contribution if math.isfinite(contribution) else 0.0)
        maximum = max(contributions, default=0.0)
        weight_labels = []
        for connection, contribution in zip(connections, contributions):
            focused = focus_id is not None
            belongs_to_focus = (
                connection.source_neuron.id == focus_id
                or connection.target_neuron.id == focus_id
            )
            if focused and not belongs_to_focus:
                continue
            start = positions.get(connection.source_neuron.id)
            end = positions.get(connection.target_neuron.id)
            if start is None or end is None:
                continue
            strength = 0.0 if maximum <= 0.0 else contribution / maximum
            if connection.weight > 0.000001:
                color_key, default_color = "positive_weight", "#2870af"
            elif connection.weight < -0.000001:
                color_key, default_color = "negative_weight", "#c34137"
            else:
                color_key, default_color = "neutral_weight", "#696969"
            color = QColor(self.color_settings.get(color_key, default_color))
            if not color.isValid():
                color = QColor(default_color)
            # Farbe, Deckkraft und Linienstärke bleiben in der Gesamt- und
            # Einzelansicht identisch. Die Einzelansicht blendet lediglich
            # nicht zum gewählten Neuron gehörende Verbindungen aus.
            color.setAlpha(255)
            screen_width = 0.55 + strength * 1.65
            painter.setPen(QPen(color, screen_width / view_zoom))
            painter.drawLine(start, end)
            self.connection_hit_areas.append((start, end, connection, contribution))
            if focused:
                weight_labels.append((start, end, connection, color))

        if weight_labels:
            label_font = painter.font()
            natural_label_size = max(6.0, min(8.0, radius * 0.62))
            if view_zoom < 0.75:
                natural_label_size = max(
                    natural_label_size,
                    min(36.0, 7.0 / view_zoom),
                )
            label_font.setPixelSize(round(natural_label_size))
            painter.setFont(label_font)
            label_height = max(11.0, painter.fontMetrics().height() + 2.0)
            focused_center = positions.get(focus_id)

            def other_endpoint(label_data):
                start, end, connection, _color = label_data
                return (
                    end
                    if connection.source_neuron.id == focus_id
                    else start
                )

            # Die Werte werden je Seite in einer eigenen, gleichmaessig
            # verteilten Spalte angeordnet. Damit bleiben sie auch bei
            # mehreren Hidden-Schichten getrennt.
            side_groups = {"left": [], "right": []}
            for label_data in weight_labels:
                side = (
                    "left"
                    if other_endpoint(label_data).x() < focused_center.x()
                    else "right"
                )
                side_groups[side].append(label_data)

            for labels in side_groups.values():
                labels.sort(key=lambda item: other_endpoint(item).y())
                if not labels:
                    continue
                top = card_rect.top() + label_height / 2.0 + 5.0
                bottom = card_rect.bottom() - label_height / 2.0 - 5.0
                minimum_step = label_height + 1.0
                desired_y = [other_endpoint(item).y() for item in labels]
                if len(labels) > 1 and (
                    any(
                        desired_y[index] - desired_y[index - 1] < minimum_step
                        for index in range(1, len(desired_y))
                    )
                    or desired_y[0] < top
                    or desired_y[-1] > bottom
                ):
                    step = min(
                        minimum_step,
                        max(1.0, (bottom - top) / (len(labels) - 1)),
                    )
                    group_height = step * (len(labels) - 1)
                    group_top = max(
                        top,
                        min(
                            sum(desired_y) / len(desired_y) - group_height / 2.0,
                            bottom - group_height,
                        ),
                    )
                    desired_y = [
                        group_top + index * step
                        for index in range(len(labels))
                    ]

                for label_data, label_y in zip(labels, desired_y):
                    _start, _end, connection, color = label_data
                    other = other_endpoint(label_data)
                    text = format_number(connection.weight, 3)
                    text_width = painter.fontMetrics().horizontalAdvance(text)
                    # Naeher an der aeusseren Schicht ist zwischen den
                    # benachbarten Linien mehr freier Raum.
                    column_x = other.x() + (
                        focused_center.x() - other.x()
                    ) * 0.38
                    label_rect = QRectF(
                        column_x - text_width / 2.0 - 2.0,
                        label_y - label_height / 2.0,
                        text_width + 4.0,
                        label_height,
                    )
                    label_rect.moveLeft(max(
                        card_rect.left() + 3.0,
                        min(
                            label_rect.left(),
                            card_rect.right() - label_rect.width() - 3.0,
                        ),
                    ))
                    background = QColor(self.card_color)
                    background.setAlpha(225)
                    painter.fillRect(label_rect, background)
                    painter.setPen(QPen(color, 1.0))
                    painter.drawText(
                        label_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        text,
                    )

        strongest = max(outputs, key=lambda neuron: neuron.output_value, default=None)
        for layer in layers:
            for neuron in layer:
                center = positions[neuron.id]
                activity = self.activity_ratio(neuron.output_value)
                shade = round(52 + activity * 196)
                painter.setBrush(QColor(shade, shade, shade))
                if neuron is strongest:
                    painter.setPen(QPen(QColor("#00a84f"), 2.8))
                elif neuron.id == focus_id:
                    painter.setPen(QPen(QColor("#d08000"), 2.8))
                else:
                    painter.setPen(QPen(QColor("#606870"), 1.0))
                painter.drawEllipse(center, radius, radius)
                self.node_hit_areas.append((center, radius + 4.0, neuron))

        if output_panel_width > 0.0:
            side_padding = max(5.0, min(10.0, card_rect.width() * 0.015))
            panel_left = (
                inner.right() + max(7.0, radius * 1.15)
            )
            panel_right = card_rect.right() - side_padding
            panel_width = max(40.0, panel_right - panel_left)
            row_height = max(
                12.0, min(30.0, inner.height() / max(1, len(outputs)))
            )
            output_font = painter.font()
            natural_font_size = max(7.0, min(10.0, row_height * 0.32))
            if view_zoom < 0.75:
                natural_font_size = max(
                    natural_font_size,
                    min(48.0, 9.0 / view_zoom),
                )
            output_font.setPixelSize(round(natural_font_size))
            painter.setFont(output_font)
            metrics = painter.fontMetrics()
            # Beide Seiten verwenden feste, spiegelbildliche Spaltenanteile.
            # Dadurch bleiben Balkenlänge und Abstände unabhängig von der
            # jeweiligen Textlänge optisch identisch.
            value_width = panel_width * 0.43
            label_width = panel_width * 0.20
            bar_left = panel_left + label_width + 2.0
            bar_right = panel_right - value_width - 3.0
            bar_width = max(14.0, bar_right - bar_left)
            bar_height = min(
                row_height * 0.35,
                max(4.0, 3.0 / view_zoom),
            )
            for neuron in outputs:
                center = positions.get(neuron.id)
                if center is None:
                    continue
                ratio, value_text = self.output_display_data(neuron)
                y = center.y()
                label = self.neuron_id_text(neuron)
                label = metrics.elidedText(
                    label, Qt.TextElideMode.ElideRight, round(label_width)
                )
                painter.setPen(QPen(self.text_color, 1.0))
                painter.drawText(
                    QRectF(panel_left, y - row_height / 2.0, label_width, row_height),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    label,
                )
                track_y = y - bar_height / 2.0
                painter.setPen(QPen(QColor("#7d858c"), 1.0))
                painter.setBrush(QColor("#e4e7e9"))
                painter.drawRoundedRect(
                    QRectF(bar_left, track_y, bar_width, bar_height), 1.5, 1.5
                )
                active_color = (
                    QColor("#ff9a2e") if neuron is strongest
                    else QColor("#2788c9")
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(active_color)
                painter.drawRoundedRect(
                    QRectF(
                        bar_left, track_y, bar_width * ratio, bar_height
                    ),
                    1.5,
                    1.5,
                )
                painter.setPen(QPen(active_color, 1.0))
                painter.drawText(
                    QRectF(
                        bar_right + 3.0, y - row_height / 2.0,
                        value_width, row_height,
                    ),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    value_text,
                )

        if input_panel_width > 0.0:
            side_padding = max(5.0, min(10.0, card_rect.width() * 0.015))
            panel_right = (
                inner.left() - max(7.0, radius * 1.15)
            )
            panel_left = card_rect.left() + side_padding
            panel_width = max(40.0, panel_right - panel_left)
            row_height = max(
                12.0, min(30.0, inner.height() / max(1, len(inputs)))
            )
            input_font = painter.font()
            natural_font_size = max(7.0, min(10.0, row_height * 0.32))
            if view_zoom < 0.75:
                natural_font_size = max(
                    natural_font_size,
                    min(48.0, 9.0 / view_zoom),
                )
            input_font.setPixelSize(round(natural_font_size))
            painter.setFont(input_font)
            metrics = painter.fontMetrics()
            value_width = panel_width * 0.43
            label_width = panel_width * 0.20
            # Spiegelbildlich zur Ausgabeseite: außen der Wert, danach der
            # Balken und unmittelbar vor dem Neuron dessen technische ID.
            value_left = panel_left
            bar_left = value_left + value_width + 3.0
            label_left = panel_right - label_width
            bar_right = label_left - 2.0
            bar_width = max(14.0, bar_right - bar_left)
            bar_height = min(
                row_height * 0.35,
                max(4.0, 3.0 / view_zoom),
            )
            for neuron in inputs:
                center = positions.get(neuron.id)
                if center is None:
                    continue
                ratio, value_text = self.input_display_data(neuron)
                y = center.y()
                label = metrics.elidedText(
                    self.neuron_id_text(neuron),
                    Qt.TextElideMode.ElideLeft,
                    round(label_width),
                )
                active_color = QColor("#2788c9")
                painter.setPen(QPen(active_color, 1.0))
                painter.drawText(
                    QRectF(value_left, y - row_height / 2.0, value_width, row_height),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                    value_text,
                )
                track_y = y - bar_height / 2.0
                painter.setPen(QPen(QColor("#7d858c"), 1.0))
                painter.setBrush(QColor("#e4e7e9"))
                painter.drawRoundedRect(
                    QRectF(bar_left, track_y, bar_width, bar_height), 1.5, 1.5
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(active_color)
                painter.drawRoundedRect(
                    QRectF(
                        bar_left, track_y, bar_width * ratio, bar_height
                    ),
                    1.5,
                    1.5,
                )
                painter.setPen(QPen(self.text_color, 1.0))
                painter.drawText(
                    QRectF(label_left, y - row_height / 2.0, label_width, row_height),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                    label,
                )

        self.reset_focus_rect = QRectF()
        self.formula_rect = QRectF()
        self.formula_info_rect = QRectF()
        self.formula_tooltip = ""
        if self.pinned_neuron_id is not None:
            button_text = self.translate("Alle", "All")
            button_font = painter.font()
            button_font.setPixelSize(8)
            painter.setFont(button_font)
            button_width = max(
                34.0,
                painter.fontMetrics().horizontalAdvance(button_text) + 14.0,
            )
            self.reset_focus_rect = QRectF(
                QRectF(self.rect()).right() - button_width - 9.0,
                QRectF(self.rect()).bottom() - 27.0,
                button_width,
                20.0,
            )
            painter.setPen(QPen(QColor("#707880"), 1.0))
            painter.setBrush(QColor(self.card_color).lighter(118))
            painter.drawRoundedRect(self.reset_focus_rect, 4.0, 4.0)
            painter.setPen(QPen(self.text_color, 1.0))
            painter.drawText(
                self.reset_focus_rect,
                Qt.AlignmentFlag.AlignCenter,
                button_text,
            )
            formula_text, self.formula_tooltip = self.calculation_text(
                self.pinned_neuron_id
            )
            info_size = self.reset_focus_rect.height()
            self.formula_info_rect = QRectF(
                self.reset_focus_rect.left() - info_size - 7.0,
                self.reset_focus_rect.top(),
                info_size,
                info_size,
            )
            painter.setPen(QPen(QColor("#707880"), 1.0))
            painter.setBrush(QColor(self.card_color).lighter(118))
            painter.drawRoundedRect(self.formula_info_rect, 4.0, 4.0)
            info_font = painter.font()
            info_font.setBold(True)
            info_font.setPixelSize(9)
            painter.setFont(info_font)
            painter.setPen(QPen(self.text_color, 1.0))
            painter.drawText(
                self.formula_info_rect,
                Qt.AlignmentFlag.AlignCenter,
                "i",
            )
            painter.setFont(button_font)
            formula_left = QRectF(self.rect()).left() + 9.0
            formula_right = self.formula_info_rect.left() - 7.0
            if formula_text and formula_right - formula_left >= 80.0:
                self.formula_rect = QRectF(
                    formula_left,
                    self.reset_focus_rect.top(),
                    formula_right - formula_left,
                    self.reset_focus_rect.height(),
                )
                painter.setPen(QPen(QColor("#707880"), 1.0))
                painter.setBrush(QColor(self.card_color).lighter(112))
                painter.drawRoundedRect(self.formula_rect, 4.0, 4.0)
                painter.setPen(QPen(self.text_color, 1.0))
                elided_text = painter.fontMetrics().elidedText(
                    formula_text,
                    Qt.TextElideMode.ElideRight,
                    max(1, round(self.formula_rect.width() - 12.0)),
                )
                painter.drawText(
                    self.formula_rect.adjusted(6.0, 0.0, -6.0, 0.0),
                    Qt.AlignmentFlag.AlignVCenter
                    | Qt.AlignmentFlag.AlignLeft,
                    elided_text,
                )

    @staticmethod
    def point_segment_distance(point, start, end):
        delta = end - start
        length_squared = delta.x() ** 2 + delta.y() ** 2
        if length_squared <= 0.0:
            return math.hypot(point.x() - start.x(), point.y() - start.y())
        factor = max(0.0, min(1.0, (
            (point.x() - start.x()) * delta.x()
            + (point.y() - start.y()) * delta.y()
        ) / length_squared))
        nearest = start + delta * factor
        return math.hypot(point.x() - nearest.x(), point.y() - nearest.y())

    def mouseMoveEvent(self, event):
        point = event.position()
        tooltip = (
            self.translate(
                "Alle Verbindungen anzeigen",
                "Show all connections",
            )
            if self.pinned_neuron_id is not None
            and self.reset_focus_rect.contains(point)
            else ""
        )
        if self.formula_info_rect.contains(point):
            tooltip = self.translate(
                "Vollständigen Rechenweg anzeigen",
                "Show complete calculation",
            )
        hovered_neuron_id = None
        hovered_center = None
        hovered_radius = 0.0
        neuron_tooltip = ""
        for center, radius, neuron in self.node_hit_areas:
            if math.hypot(point.x() - center.x(), point.y() - center.y()) <= radius:
                hovered_neuron_id = neuron.id
                hovered_center = center
                hovered_radius = radius
                neuron_id = self.neuron_id_text(neuron)
                neuron_kind = str(getattr(neuron, "neuron_type", "")).lower()
                display_name = (
                    self.translate("Hidden", "Hidden")
                    if "hidden" in neuron_kind
                    else neuron.name
                )
                neuron_tooltip = self.translate(
                    f"{neuron_id} – {display_name}\n"
                    f"Ausgabewert: {format_number(neuron.output_value, 8)}",
                    f"{neuron_id} – {display_name}\n"
                    f"Output value: {format_number(neuron.output_value, 8)}",
                )
                tooltip = neuron_tooltip
                break
        if neuron_tooltip:
            if hovered_neuron_id != self.visible_tooltip_neuron_id:
                tooltip_width = max(
                    self.fontMetrics().horizontalAdvance(line)
                    for line in neuron_tooltip.splitlines()
                ) + 24
                output_ids = {neuron.id for neuron in self.cached_outputs}
                # Die Karte liegt als QGraphicsProxyWidget in einer zoombaren
                # QGraphicsView. QWidget.mapToGlobal() kennt deren Szenen-
                # transformation nicht. Deshalb wird die Neuronenposition
                # zuerst in die Szene und anschließend in den Viewport sowie
                # dessen globale Bildschirmkoordinaten übertragen.
                proxy = self.graphicsProxyWidget()
                views = proxy.scene().views() if proxy is not None and proxy.scene() else []
                if views:
                    view = views[0]
                    center_scene = proxy.mapToScene(hovered_center)
                    if hovered_neuron_id in output_ids:
                        edge_scene = proxy.mapToScene(
                            hovered_center - QPointF(hovered_radius, 0.0)
                        )
                    else:
                        edge_scene = proxy.mapToScene(
                            hovered_center + QPointF(hovered_radius, 0.0)
                        )
                    center_view = view.mapFromScene(center_scene)
                    edge_view = view.mapFromScene(edge_scene)
                    if hovered_neuron_id in output_ids:
                        tooltip_x = edge_view.x() - tooltip_width - 10
                    else:
                        tooltip_x = edge_view.x() + 10
                    tooltip_y = center_view.y() - 16
                    tooltip_position = view.viewport().mapToGlobal(
                        QPoint(round(tooltip_x), round(tooltip_y))
                    )
                else:
                    if hovered_neuron_id in output_ids:
                        tooltip_x = (
                            hovered_center.x() - hovered_radius
                            - tooltip_width - 10.0
                        )
                    else:
                        tooltip_x = hovered_center.x() + hovered_radius + 10.0
                    tooltip_y = hovered_center.y() - 16.0
                    tooltip_position = self.mapToGlobal(
                        QPoint(round(tooltip_x), round(tooltip_y))
                    )
                QToolTip.showText(
                    tooltip_position, neuron_tooltip, self
                )
                self.visible_tooltip_neuron_id = hovered_neuron_id
        elif self.visible_tooltip_neuron_id is not None:
            QToolTip.hideText()
            self.visible_tooltip_neuron_id = None
        if (
            self.pinned_neuron_id is None
            and hovered_neuron_id != self.hovered_neuron_id
        ):
            self.hovered_neuron_id = hovered_neuron_id
            self.update()
        if not tooltip:
            for start, end, connection, contribution in self.connection_hit_areas:
                if self.point_segment_distance(point, start, end) <= 5.0:
                    tooltip = self.translate(
                        f"W{connection.id}: {format_number(connection.weight, 8)}\n"
                        f"Signalbeitrag: {format_number(contribution, 8)}",
                        f"W{connection.id}: {format_number(connection.weight, 8)}\n"
                        f"Signal contribution: {format_number(contribution, 8)}",
                    )
                    break
        self.setToolTip(tooltip)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position()
            if self.show_formula_information_at(point):
                event.accept()
                return
            if self.clear_focus_at(point):
                event.accept()
                return
            if self.pin_neuron_at(point):
                event.accept()
                return
        super().mousePressEvent(event)

    def pin_neuron_at(self, point):
        """Fixiert das Neuron unter dem Mauszeiger für die reduzierte Ansicht."""

        point = QPointF(point)
        for center, radius, neuron in self.node_hit_areas:
            if math.hypot(point.x() - center.x(), point.y() - center.y()) <= radius:
                self.pinned_neuron_id = neuron.id
                self.hovered_neuron_id = None
                self.update()
                return True
        return False

    def show_formula_information_at(self, point):
        """Zeigt den vollständigen Rechenweg des fixierten Neurons an."""

        if (
            self.pinned_neuron_id is None
            or not self.formula_tooltip
            or not self.formula_info_rect.contains(QPointF(point))
        ):
            return False

        # Die Netzwerkkarte liegt als Widget in einem QGraphicsProxyWidget.
        # self.window() liefert dort nicht zuverlässig den eigentlichen
        # Anwendungsdialog als Elternfenster. Ein Dialog mit diesem falschen
        # Parent kann von Qt in die Szene eingebettet werden und dadurch die
        # Anwendungsansicht überdecken bzw. deren Layout verändern.
        dialog_parent = None
        proxy = self.graphicsProxyWidget()
        if proxy is not None and proxy.scene() is not None:
            views = proxy.scene().views()
            if views:
                dialog_parent = views[0].window()
        if dialog_parent is None:
            dialog_parent = self.parentWidget() or self.window()

        QToolTip.hideText()
        self.setToolTip("")
        self.show_structured_calculation(dialog_parent)
        return True

    def show_structured_calculation(self, dialog_parent):
        """Zeigt den Rechenweg gegliedert; nur die Beitragsliste scrollt."""

        details = dict(self.formula_details or {})
        dialog = QDialog(dialog_parent)
        dialog.setWindowTitle(self.translate("Rechenweg", "Calculation"))
        dialog.setModal(True)
        dialog.setMinimumWidth(680)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        heading = QLabel(
            self.translate(
                f"Berechnung für {details.get('neuron', '')}",
                f"Calculation for {details.get('neuron', '')}",
            )
        )
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)

        if details.get("kind") == "input":
            explanation = QLabel(
                self.translate(
                    "Eingabeneuron: Der Eingangswert X wird unverändert als "
                    "Ausgabewert Y weitergegeben.\n\n"
                    f"X = {format_number(details.get('input', 0.0), 8)}\n"
                    f"Y = {format_number(details.get('output', 0.0), 8)}",
                    "Input neuron: Input value X is passed on unchanged as "
                    "output value Y.\n\n"
                    f"X = {format_number(details.get('input', 0.0), 8)}\n"
                    f"Y = {format_number(details.get('output', 0.0), 8)}",
                )
            )
            explanation.setStyleSheet(
                "QLabel { background-color: #fff8d8; color: #202020; "
                "border: 1px solid #d8b34f; border-radius: 5px; "
                "padding: 12px; }"
            )
            explanation.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(explanation)
        else:
            table = QTableWidget(len(details.get("rows", [])), 5, dialog)
            table.setHorizontalHeaderLabels(
                self.translate(
                    ["Quelle", "Ausgang Y", "Gewicht", "Wert W", "Beitrag Y × W"],
                    ["Source", "Output Y", "Weight", "Value W", "Contribution Y × W"],
                )
            )
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            for row, values in enumerate(details.get("rows", [])):
                display_values = (
                    values[0],
                    format_number(values[1], 8),
                    values[2],
                    format_number(values[3], 8),
                    format_number(values[4], 8),
                )
                for column, value in enumerate(display_values):
                    item = QTableWidgetItem(str(value))
                    if column in (1, 3, 4):
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    table.setItem(row, column, item)
            table.resizeColumnsToContents()
            row_height = table.verticalHeader().defaultSectionSize()
            visible_rows = min(9, max(1, table.rowCount()))
            table.setMinimumHeight(105)
            table.setMaximumHeight(
                table.horizontalHeader().height() + visible_rows * row_height + 8
            )
            layout.addWidget(table)

            german_summary = (
                f"Summe der Beiträge: "
                f"{format_number(details.get('contribution_sum', 0.0), 8)}\n"
                f"Bias: {format_number(details.get('bias', 0.0), 8)}\n"
                f"Summe einschließlich Bias: Σ = "
                f"{format_number(details.get('sum', 0.0), 8)}\n\n"
                f"Aktivierung: {details.get('activation', 'Linear')}(Σ)\n"
                f"Ausgang: Y = {format_number(details.get('output', 0.0), 8)}"
            )
            english_summary = (
                f"Sum of contributions: "
                f"{format_number(details.get('contribution_sum', 0.0), 8)}\n"
                f"Bias: {format_number(details.get('bias', 0.0), 8)}\n"
                f"Sum including bias: Σ = "
                f"{format_number(details.get('sum', 0.0), 8)}\n\n"
                f"Activation: {details.get('activation', 'Linear')}(Σ)\n"
                f"Output: Y = {format_number(details.get('output', 0.0), 8)}"
            )
            if details.get("raw_output") is not None:
                raw_output_text = format_number(details["raw_output"], 5)
                raw_output_unit = str(details.get("raw_output_unit") or "")
                if raw_output_unit:
                    raw_output_text += f" {raw_output_unit}"
                german_summary += (
                    f"\nRückskalierter Ausgangswert: {raw_output_text}"
                )
                english_summary += (
                    f"\nUnscaled output value: {raw_output_text}"
                )
            summary = QLabel(self.translate(german_summary, english_summary))
            summary.setStyleSheet(
                "QLabel { background-color: #fff8d8; color: #202020; "
                "border: 1px solid #d8b34f; border-radius: 5px; "
                "padding: 12px; }"
            )
            summary.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(summary)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.translate("Schließen", "Close")
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def clear_focus_at(self, point):
        """Hebt eine fixierte Neuronenauswahl über die kleine Alle-Taste auf."""

        if (
            self.pinned_neuron_id is None
            or not self.reset_focus_rect.contains(QPointF(point))
        ):
            return False
        self.pinned_neuron_id = None
        self.hovered_neuron_id = None
        self.setToolTip("")
        self.update()
        return True

    def leaveEvent(self, event):
        if self.pinned_neuron_id is None and self.hovered_neuron_id is not None:
            self.hovered_neuron_id = None
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)


class ElidedLabel(QLabel):
    """Kürzt lange Kartennamen, ohne die Schriftgröße zu verändern."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        """Speichert den vollständigen Text und zeigt bei Bedarf Auslassungspunkte."""
        self.full_text = str(text)
        self.setToolTip(self.full_text)
        self.update_elided_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elided_text()

    def update_elided_text(self):
        available = max(1, self.width())
        QLabel.setText(
            self,
            self.fontMetrics().elidedText(
                self.full_text, Qt.TextElideMode.ElideRight, available
            ),
        )


class CommentEditDialog(QDialog):
    """Bearbeitet den Inhalt und die Textdarstellung eines Kommentarfeldes."""

    def __init__(self, data, translator, parent=None):
        super().__init__(parent)
        self.tr_text = translator
        self.font_color = QColor(data.get("font_color", "#111111"))
        self.setWindowTitle(translator("Kommentar bearbeiten", "Edit comment"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(str(data.get("text", "")))
        self.text_edit.setMinimumSize(360, 130)
        form.addRow(translator("Text:", "Text:"), self.text_edit)
        self.font_size_spin = QSpinBox(self)
        self.font_size_spin.setRange(1, 48)
        self.font_size_spin.setValue(int(data.get("font_size", 11)))
        form.addRow(translator("Schriftgröße:", "Font size:"), self.font_size_spin)
        self.bold_check = QCheckBox(translator("Fett", "Bold"), self)
        self.bold_check.setChecked(bool(data.get("bold", False)))
        form.addRow("", self.bold_check)
        self.alignment_combo = QComboBox(self)
        self.alignment_combo.addItem(translator("Links", "Left"), "left")
        self.alignment_combo.addItem(translator("Mittig", "Center"), "center")
        self.alignment_combo.addItem(translator("Rechts", "Right"), "right")
        index = self.alignment_combo.findData(data.get("alignment", "left"))
        self.alignment_combo.setCurrentIndex(max(0, index))
        form.addRow(translator("Textausrichtung:", "Text alignment:"), self.alignment_combo)
        self.color_button = QPushButton(self)
        self.color_button.clicked.connect(self.choose_font_color)
        self.update_color_button()
        form.addRow(translator("Schriftfarbe:", "Font color:"), self.color_button)
        self.frame_check = QCheckBox(translator("Rahmen anzeigen", "Show frame"), self)
        self.frame_check.setChecked(bool(data.get("frame", True)))
        form.addRow("", self.frame_check)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_font_color(self):
        color = choose_color(self.font_color, self)
        if color.isValid():
            self.font_color = color
            self.update_color_button()

    def update_color_button(self):
        background = self.font_color.name()
        luminance = (
            0.2126 * self.font_color.red()
            + 0.7152 * self.font_color.green()
            + 0.0722 * self.font_color.blue()
        )
        foreground = "#ffffff" if luminance < 145.0 else "#111111"
        self.color_button.setText(background.upper())
        self.color_button.setStyleSheet(
            "QPushButton {"
            f"color: {foreground}; background-color: {background};"
            "border: 1px solid #b8b8b8; border-radius: 4px; padding: 3px;"
            "}"
        )

    def comment_data(self):
        return {
            "text": self.text_edit.toPlainText(),
            "font_size": self.font_size_spin.value(),
            "bold": self.bold_check.isChecked(),
            "alignment": self.alignment_combo.currentData(),
            "font_color": self.font_color.name(),
            "frame": self.frame_check.isChecked(),
        }


class CommentCard(ExperimentCard):
    """Frei platzierbares und formatierbares Kommentarfeld."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.comment_data = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        self.text_label = QLabel(self)
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)
        self.set_comment_data(data)

    def set_comment_data(self, data):
        self.comment_data = dict(data)
        self.text_label.setText(str(data.get("text", "")))
        font = self.text_label.font()
        font.setPointSize(int(data.get("font_size", 11)))
        font.setBold(bool(data.get("bold", False)))
        self.text_label.setFont(font)
        alignments = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }
        self.text_label.setAlignment(
            alignments.get(data.get("alignment", "left"), Qt.AlignmentFlag.AlignLeft)
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.show_border = bool(data.get("frame", True))
        self.apply_comment_style()
        self.update()

    def set_card_color(self, color):
        super().set_card_color(color)
        self.apply_comment_style()

    def apply_comment_style(self):
        if not hasattr(self, "text_label"):
            return
        color = QColor(self.comment_data.get("font_color", "#111111"))
        self.text_label.setStyleSheet(
            f"border:none; background:transparent; color:{color.name()};"
        )


class BinaryArrayPaintController(QObject):
    """Schaltet jedes mit gedrückter Maustaste neu betretene Rasterfeld um."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = set()
        self.last_button = None
        self.press_started_on_button = False
        self.application = QApplication.instance()
        self.filter_installed = False
        if self.application is not None:
            self.application.installEventFilter(self)
            self.filter_installed = True

    def deactivate(self):
        """Meldet den globalen Mausfilter beim Schließen wieder ab."""

        if self.filter_installed and self.application is not None:
            self.application.removeEventFilter(self)
        self.filter_installed = False
        self.buttons.clear()
        self.last_button = None
        self.press_started_on_button = False

    def set_buttons(self, buttons):
        self.buttons = set(buttons)
        self.last_button = None

    def button_at(self, event):
        card = self.parent()
        if not isinstance(card, QWidget):
            return None
        proxy = card.graphicsProxyWidget()
        if proxy is None or proxy.scene() is None or not proxy.scene().views():
            return None
        view = proxy.scene().views()[0]
        viewport_position = view.viewport().mapFromGlobal(
            event.globalPosition().toPoint()
        )
        scene_position = view.mapToScene(viewport_position)
        for button in self.buttons:
            if not button.isVisible() or not button.isEnabled():
                continue
            top_left = button.mapTo(card, QPoint(0, 0))
            button_rect = QRectF(
                float(top_left.x()),
                float(top_left.y()),
                float(button.width()),
                float(button.height()),
            )
            if proxy.mapRectToScene(button_rect).contains(scene_position):
                return button
        return None

    def eventFilter(self, watched, event):
        event_type = event.type()
        if (
            event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            button = self.button_at(event)
            self.last_button = button
            self.press_started_on_button = button is not None
            if button is not None:
                button.setChecked(not button.isChecked())
                return True
        elif event_type == QEvent.Type.MouseMove:
            if not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                self.last_button = None
                return False
            button = self.button_at(event)
            if button is not self.last_button:
                self.last_button = button
                if button is not None:
                    button.setChecked(not button.isChecked())
        elif (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            suppress_release = self.press_started_on_button
            self.last_button = None
            self.press_started_on_button = False
            return suppress_release
        return False


class BinaryArrayButton(QToolButton):
    """Zeichnet ein Bitfeld ohne Qt-Stylesheet-Abhängigkeit."""

    def __init__(self, active_color, inactive_color, parent=None):
        super().__init__(parent)
        self.active_color = QColor(active_color)
        self.inactive_color = QColor(inactive_color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fill_color = QColor(
            self.active_color if self.isChecked() else self.inactive_color
        )
        if self.underMouse():
            fill_color = fill_color.lighter(106)
        painter.setPen(QPen(QColor("#8795a1"), 1.0))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 3.0, 3.0)


class BinaryArrayCard(ExperimentCard):
    """Bedienkarte für ein in den Trainingsdaten definiertes binäres Eingabe-Array."""

    def __init__(
        self, rows, columns, ordered_controls, changed_callback,
        color_settings=None, parent=None
    ):
        super().__init__(parent)
        colors = dict(color_settings or {})
        active_color = QColor(colors.get("binary_array_on", "#242424"))
        inactive_color = QColor(colors.get("binary_array_off", "#ffffff"))
        if not active_color.isValid():
            active_color = QColor("#242424")
        if not inactive_color.isValid():
            inactive_color = QColor("#ffffff")
        # In ein Qt-Stylesheet dürfen nur CSS-kompatible Farbtexte gelangen.
        # Insbesondere ein gespeichertes QColor-Objekt würde sonst als dessen
        # Python-Darstellung eingesetzt und die QToolButton-Regel ungültig machen.
        self.active_color = active_color.name(QColor.NameFormat.HexRgb)
        self.inactive_color = inactive_color.name(QColor.NameFormat.HexRgb)
        self.rows = int(rows)
        self.columns = int(columns)
        self.custom_title = self.tr_default_title()
        self.ordered_controls = list(ordered_controls)
        self.buttons = []
        self.paint_controller = BinaryArrayPaintController(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 8)
        outer.setSpacing(5)
        self.title_label = QLabel(self)
        self.title_label.setStyleSheet(
            "font-weight:600; border:none; background:transparent;"
        )
        outer.addWidget(self.title_label)
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        outer.addLayout(layout, 1)
        for index, controls in enumerate(self.ordered_controls):
            button = BinaryArrayButton(
                self.active_color, self.inactive_color, self
            )
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            button.setMinimumSize(22, 22)
            button.setChecked(bool(controls["editor"].isChecked()))
            mapping = controls.get("mapping", {})
            neuron = mapping.get("neuron")
            name = str(mapping.get("name") or getattr(neuron, "name", ""))
            neuron_id = getattr(neuron, "id", "")
            neuron_label = str(neuron_id)
            if neuron_label and not neuron_label.upper().startswith("N"):
                neuron_label = "N" + neuron_label
            button.setToolTip(
                f"{name} · {neuron_label}" if neuron_label else name
            )
            button.toggled.connect(
                lambda checked, target=controls["editor"], callback=changed_callback:
                self.apply_cell_value(target, checked, callback)
            )
            layout.addWidget(button, index // columns, index % columns)
            self.buttons.append(button)
        self.paint_controller.set_buttons(self.buttons)
        for row in range(rows):
            layout.setRowStretch(row, 1)
        for column in range(columns):
            layout.setColumnStretch(column, 1)
        self.update_title()

    @staticmethod
    def tr_default_title():
        return "Eingabemuster"

    def set_title(self, title):
        self.custom_title = str(title or self.tr_default_title()).strip()
        self.update_title()

    def update_title(self):
        self.title_label.setText(
            f"{self.custom_title} · {self.rows} × {self.columns}"
        )

    @staticmethod
    def apply_cell_value(editor, checked, callback):
        checked = bool(checked)
        if editor.isChecked() != checked:
            editor.setChecked(checked)
        else:
            callback()

    def sync_from_inputs(self):
        for button, controls in zip(self.buttons, self.ordered_controls):
            button.blockSignals(True)
            button.setChecked(bool(controls["editor"].isChecked()))
            button.blockSignals(False)

    def set_input_enabled(self, enabled):
        """Erlaubt das Schalten des Rasters ausschließlich im Anwendungsmodus."""

        for button in self.buttons:
            button.setEnabled(bool(enabled))


class ExperimentCanvasView(QGraphicsView):
    """Zoomt um den Mauszeiger und kann die gesamte Arbeitsfläche einpassen."""

    zoom_changed = Signal(float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRubberBandSelectionMode(
            Qt.ItemSelectionMode.ContainsItemShape
        )
        self.setAcceptDrops(True)
        self.normal_view_style = (
            "QGraphicsView { selection-background-color: transparent; } "
            "QRubberBand { background-color: rgba(0,0,0,0); "
            "border: 2px solid #c51d24; }"
        )
        self.drop_view_style = (
            self.normal_view_style
            + " QGraphicsView { border: 2px solid #2d7dd2; }"
        )
        self.setStyleSheet(self.normal_view_style)
        palette = self.palette()
        palette.setBrush(QPalette.ColorRole.Highlight, QBrush(Qt.BrushStyle.NoBrush))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#c51d24"))
        self.setPalette(palette)
        self.viewport().setPalette(palette)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.minimum_scale = 0.0
        self.show_all_scale = 0.0
        self.fitting_view = False
        self.alt_panning = False
        self.pan_last_global_position = None
        self.rubber_band_started_on_empty_space = False

    def clear_selected_line_endpoints(self):
        dialog = self.window()
        for item in getattr(dialog, "shape_items", []):
            if isinstance(item, DesignShapeItem) and item.selected_endpoints:
                item.selected_endpoints.clear()
                item.update()

    def select_line_endpoints_in_rect(self, selection_rect):
        dialog = self.window()
        for item in getattr(dialog, "shape_items", []):
            if not isinstance(item, DesignShapeItem) or not item.is_connector():
                continue
            item.selected_endpoints.clear()
            for endpoint in ("start", "end"):
                if selection_rect.contains(item.endpoint_scene_position(endpoint)):
                    item.selected_endpoints.add(endpoint)
            item.update()

    def expand_scene_to_viewport(self):
        """Vergrößert die Arbeitsfläche bis zu den sichtbaren Fensterrändern."""

        scale = max(0.001, self.transform().m11())
        visible_width = self.viewport().width() / scale
        visible_height = self.viewport().height() / scale
        scene_rect = self.scene().sceneRect()
        required_width = max(scene_rect.width(), visible_width)
        required_height = max(scene_rect.height(), visible_height)
        if (
            required_width > scene_rect.width() + 0.5
            or required_height > scene_rect.height() + 0.5
        ):
            self.scene().setSceneRect(
                scene_rect.left(),
                scene_rect.top(),
                required_width,
                required_height,
            )
        self.sync_grid_rect()

    def sync_grid_rect(self):
        dialog = self.window()
        grid_item = getattr(dialog, "grid_item", None)
        if grid_item is not None:
            grid_rect = QRectF(self.scene().sceneRect())
            if self.viewport().width() > 0 and self.viewport().height() > 0:
                visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
                grid_rect = grid_rect.united(visible_rect)
            grid_item.set_rect(grid_rect)

    def content_items_bounding_rect(self):
        result = QRectF()
        for item in self.scene().items():
            if isinstance(item, DesignGridItem) or not item.isVisible():
                continue
            item_rect = item.sceneBoundingRect()
            result = item_rect if result.isNull() else result.united(item_rect)
        return result

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.fitting_view:
            self.expand_scene_to_viewport()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        rubber_band = self.rubberBandRect()
        if rubber_band.isNull() or rubber_band.width() < 1 or rubber_band.height() < 1:
            return
        pen = QPen(QColor("#c51d24"), 2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(self.mapToScene(rubber_band))

    def contextMenuEvent(self, event):
        dialog = self.window()
        if not getattr(dialog, "edit_mode", False):
            return super().contextMenuEvent(event)
        item = self.itemAt(event.pos())
        while item is not None and not isinstance(
            item, (MovableCardProxy, DesignShapeItem, ResizableBackgroundItem)
        ):
            item = item.parentItem()
        if isinstance(item, MovableCardProxy):
            dialog.show_card_context_menu(item, event.globalPos())
        elif isinstance(item, DesignShapeItem):
            dialog.show_shape_context_menu(item, event.globalPos())
        elif isinstance(item, ResizableBackgroundItem):
            dialog.show_background_context_menu(item, event.globalPos())
        else:
            dialog.show_empty_context_menu(
                event.globalPos(),
                self.mapToScene(event.pos()),
            )
        event.accept()

    def is_zoomed_in(self):
        return self.transform().m11() > self.show_all_scale + 1.0e-6

    def begin_alt_pan(self, global_position):
        if not self.is_zoomed_in():
            return False
        self.alt_panning = True
        self.pan_last_global_position = global_position
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        return True

    def continue_alt_pan(self, global_position):
        if not self.alt_panning or self.pan_last_global_position is None:
            return False
        delta = global_position - self.pan_last_global_position
        self.pan_last_global_position = global_position
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - delta.x()
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - delta.y()
        )
        return True

    def end_alt_pan(self):
        if not self.alt_panning:
            return False
        self.alt_panning = False
        self.pan_last_global_position = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        return True

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        current = self.transform().m11()
        target = current * factor
        minimum = max(0.001, self.minimum_scale)
        if target < minimum:
            factor = minimum / max(0.001, current)
        if current * factor <= 5.0:
            self.scale(factor, factor)
            if event.angleDelta().y() < 0:
                self.expand_scene_to_viewport()
        if self.show_all_scale > 0.0:
            self.zoom_changed.emit(
                self.transform().m11() / self.show_all_scale * 100.0
            )
        event.accept()

    def show_all(self):
        self.fitting_view = True
        content_rect = self.content_items_bounding_rect()
        if not content_rect.isEmpty():
            self.scene().setSceneRect(content_rect.adjusted(-25.0, -25.0, 25.0, 25.0))
            self.sync_grid_rect()
        self.fitInView(
            self.scene().sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.show_all_scale = self.transform().m11()
        self.minimum_scale = self.show_all_scale * 0.25
        self.zoom_changed.emit(100.0)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        QTimer.singleShot(0, self.finish_show_all)

    def finish_show_all(self):
        """Passt nach der internen Ansichtsaktualisierung ein zweites Mal stabil ein."""

        content_rect = self.content_items_bounding_rect()
        if not content_rect.isEmpty():
            self.scene().setSceneRect(content_rect.adjusted(-25.0, -25.0, 25.0, 25.0))
            self.sync_grid_rect()
        self.fitInView(
            self.scene().sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.show_all_scale = self.transform().m11()
        self.minimum_scale = self.show_all_scale * 0.25
        self.zoom_changed.emit(100.0)
        QTimer.singleShot(0, self.finish_show_all_update)

    def finish_show_all_update(self):
        self.fitting_view = False
        self.sync_grid_rect()

    def keyPressEvent(self, event):
        dialog = self.window()
        if (
            event.key() == Qt.Key.Key_Escape
            and getattr(dialog, "placement_items", [])
        ):
            dialog.cancel_element_placement()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Alt and self.is_zoomed_in():
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and not self.alt_panning:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        dialog = self.window()
        if getattr(dialog, "placement_items", []):
            if event.button() == Qt.MouseButton.LeftButton:
                dialog.finish_element_placement(
                    self.mapToScene(event.pos()), event.modifiers()
                )
                event.accept()
                return
            if event.button() == Qt.MouseButton.RightButton:
                dialog.cancel_element_placement()
                event.accept()
                return
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.pos())
            while item is not None and not isinstance(item, MovableCardProxy):
                item = item.parentItem()
            if (
                isinstance(item, MovableCardProxy)
                and item.isSelected()
                and hasattr(dialog, "selected_movable_items")
            ):
                dialog.pending_context_card_selection = list(
                    dialog.selected_movable_items()
                )
            else:
                dialog.pending_context_card_selection = []
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
            and self.begin_alt_pan(event.globalPosition().toPoint())
        ):
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            # Die vereinfachte Netzwerkansicht liegt als Widget in einem
            # QGraphicsProxyWidget. Ein erster Klick wurde bislang von der
            # Szene als Auswahl der gesamten Kachel verarbeitet; erst der
            # zweite Klick erreichte das Neuron. Den Neuronentreffer deshalb
            # bereits hier, vor der normalen Szenenbehandlung, auswerten.
            scene_point = self.mapToScene(event.pos())
            item = self.itemAt(event.pos())
            while item is not None and not isinstance(item, MovableCardProxy):
                item = item.parentItem()
            if isinstance(item, MovableCardProxy) and item.card_role == "network_view":
                card = item.widget()
                if isinstance(card, SimplifiedNetworkCard):
                    local_point = item.mapFromScene(scene_point)
                    if (
                        card.clear_focus_at(QPointF(local_point))
                        or card.pin_neuron_at(QPointF(local_point))
                    ):
                        event.accept()
                        return
        if event.button() == Qt.MouseButton.LeftButton:
            self.rubber_band_started_on_empty_space = self.itemAt(event.pos()) is None
            if self.rubber_band_started_on_empty_space:
                self.clear_selected_line_endpoints()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.continue_alt_pan(event.globalPosition().toPoint()):
            event.accept()
            return
        dialog = self.window()
        if getattr(dialog, "placement_items", []):
            dialog.update_element_placement(self.mapToScene(event.pos()))
            event.accept()
            return
        super().mouseMoveEvent(event)
        self.viewport().update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.end_alt_pan():
            event.accept()
            return
        rubber_band = self.rubberBandRect()
        selection_rect = (
            self.mapToScene(rubber_band).boundingRect()
            if self.rubber_band_started_on_empty_space
            and rubber_band.width() > 2
            and rubber_band.height() > 2
            else QRectF()
        )
        super().mouseReleaseEvent(event)
        if not selection_rect.isEmpty():
            self.select_line_endpoints_in_rect(selection_rect)
        self.rubber_band_started_on_empty_space = False
        self.viewport().update()

    def dragEnterEvent(self, event):
        dialog = self.window()
        if (
            getattr(dialog, "edit_mode", False)
            and dialog.image_path_from_mime_data(event.mimeData()) is not None
        ):
            event.acceptProposedAction()
            self.setStyleSheet(self.drop_view_style)
            return
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.normal_view_style)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        dialog = self.window()
        if (
            getattr(dialog, "edit_mode", False)
            and dialog.image_path_from_mime_data(event.mimeData()) is not None
        ):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        self.setStyleSheet(self.normal_view_style)
        dialog = self.window()
        image_path = dialog.image_path_from_mime_data(event.mimeData())
        if getattr(dialog, "edit_mode", False) and image_path is not None:
            if dialog.select_background_image(image_path):
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class DesignGridItem(QGraphicsItem):
    """Projektbezogenes Gestaltungsraster hinter allen Bedienelementen."""

    def __init__(self, rect, spacing=20):
        super().__init__()
        self.grid_rect = QRectF(rect)
        self.spacing = max(5, int(spacing))
        self.setZValue(-90.0)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return self.grid_rect

    def set_rect(self, rect):
        self.prepareGeometryChange()
        self.grid_rect = QRectF(rect)
        self.update()

    def set_spacing(self, spacing):
        self.spacing = max(5, int(spacing))
        self.update()

    def paint(self, painter, option, widget=None):
        exposed = option.exposedRect.intersected(self.grid_rect)
        if exposed.isEmpty():
            return
        spacing = float(self.spacing)
        left = math.floor(exposed.left() / spacing) * spacing
        top = math.floor(exposed.top() / spacing) * spacing
        pen = QPen(QColor(100, 110, 120, 90), 2.0)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        y = top
        while y <= exposed.bottom():
            x = left
            while x <= exposed.right():
                painter.drawPoint(QPointF(x, y))
                x += spacing
            y += spacing


def draw_locked_indicator(painter, rect, size=12.0):
    """Zeichnet eine dezente Schlossmarkierung innerhalb eines Elements."""

    size = max(8.0, float(size))
    margin = size * 0.18
    badge = QRectF(
        rect.right() - size - margin,
        rect.top() + margin,
        size,
        size,
    )
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    badge_pen = QPen(QColor(23, 96, 106, 125), 0.7)
    badge_pen.setCosmetic(True)
    painter.setPen(badge_pen)
    painter.setBrush(QColor(255, 255, 255, 205))
    painter.drawRoundedRect(badge, size * 0.18, size * 0.18)

    body = QRectF(
        badge.left() + size * 0.25,
        badge.top() + size * 0.49,
        size * 0.50,
        size * 0.31,
    )
    lock_pen = QPen(QColor("#17606a"), 0.9)
    lock_pen.setCosmetic(True)
    painter.setPen(lock_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(body, size * 0.07, size * 0.07)
    shackle = QPainterPath()
    shackle.moveTo(body.left() + size * 0.09, body.top())
    shackle.lineTo(body.left() + size * 0.09, badge.top() + size * 0.38)
    shackle.cubicTo(
        body.left() + size * 0.09,
        badge.top() + size * 0.17,
        body.right() - size * 0.09,
        badge.top() + size * 0.17,
        body.right() - size * 0.09,
        badge.top() + size * 0.38,
    )
    shackle.lineTo(body.right() - size * 0.09, body.top())
    painter.drawPath(shackle)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#17606a"))
    painter.drawEllipse(
        QPointF(badge.center().x(), body.center().y()),
        size * 0.045,
        size * 0.045,
    )
    painter.restore()


class ResizableBackgroundItem(QGraphicsPixmapItem):
    """Verschiebbares Bild mit proportionaler Größenänderung an der rechten unteren Ecke."""

    HANDLE_SIZE = 22.0

    def __init__(self, pixmap):
        super().__init__(pixmap)
        self.editable = True
        self.locked = False
        self.resizing = False
        self.resize_start = QPointF()
        self.start_scale = 1.0
        self.group_drag_proxy = None
        self.setZValue(-100.0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def set_editable(self, editable):
        self.editable = bool(editable)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            self.editable and not self.locked,
        )
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, self.editable)
        if not self.editable:
            self.setSelected(False)
        self.update()

    def set_locked(self, locked):
        self.locked = bool(locked)
        self.resizing = False
        self.group_drag_proxy = None
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            self.editable and not self.locked,
        )
        self.update()

    def handle_rect(self):
        rect = self.boundingRect()
        size = self.HANDLE_SIZE / max(0.001, self.scale())
        return QRectF(rect.right() - size, rect.bottom() - size, size, size)

    def shape(self):
        """Bezieht auch transparente Bildbereiche und den Skaliergriff ein."""

        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def history_dialog(self):
        views = self.scene().views() if self.scene() is not None else []
        return views[0].window() if views else None

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        dialog = self.history_dialog()
        handles_hidden = bool(
            dialog is not None
            and getattr(dialog, "nudge_handles_hidden", False)
        )
        if (
            self.editable
            and not self.locked
            and not handles_hidden
            and (self.isSelected() or self.resizing)
        ):
            painter.setPen(QPen(QColor("#245a94"), 2.0 / max(0.001, self.scale())))
            painter.setBrush(QColor("#ffffff"))
            painter.drawRect(self.handle_rect())
        if self.editable and self.locked:
            draw_locked_indicator(
                painter,
                self.boundingRect(),
                12.0 / max(0.001, self.scale()),
            )

    def mousePressEvent(self, event):
        dialog = self.history_dialog()
        if dialog is not None and hasattr(dialog, "begin_history_action"):
            dialog.begin_history_action()
            dialog.last_selected_card = self
        if self.editable and not self.locked and self.handle_rect().contains(event.pos()):
            self.setSelected(True)
            self.resizing = True
            self.resize_start = event.scenePos()
            self.start_scale = self.scale()
            self.update()
            event.accept()
            return
        if self.editable and not self.locked and self.isSelected() and dialog is not None:
            selected_cards = dialog.selected_card_proxies()
            if selected_cards:
                self.group_drag_proxy = selected_cards[0]
                self.group_drag_proxy.begin_card_drag(
                    event.scenePos(), Qt.KeyboardModifier.NoModifier
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.group_drag_proxy is not None:
            self.group_drag_proxy.move_selected_cards(event.scenePos())
            event.accept()
            return
        if self.resizing:
            self.setSelected(True)
            pixmap_width = max(1.0, float(self.pixmap().width()))
            delta = event.scenePos().x() - self.resize_start.x()
            new_scale = self.start_scale + delta / pixmap_width
            dialog = self.history_dialog()
            if (
                dialog is not None
                and hasattr(dialog, "grid_snap_active")
                and dialog.grid_snap_active()
            ):
                target_right = self.pos().x() + pixmap_width * new_scale
                snapped_right = dialog.snap_scene_position(
                    QPointF(target_right, self.pos().y())
                ).x()
                new_scale = (snapped_right - self.pos().x()) / pixmap_width
            self.setScale(max(0.05, min(10.0, new_scale)))
            event.accept()
            return
        super().mouseMoveEvent(event)
        dialog = self.history_dialog()
        if (
            dialog is not None
            and hasattr(dialog, "grid_snap_active")
            and dialog.grid_snap_active()
        ):
            raw_position = QPointF(self.pos())
            snapped_position = dialog.snap_scene_position(raw_position)
            correction = snapped_position - raw_position
            if not correction.isNull() and self.scene() is not None:
                for item in self.scene().selectedItems():
                    if (
                        isinstance(item, DesignShapeItem)
                        and not item.locked
                    ):
                        item.setPos(item.pos() + correction)
            self.setPos(snapped_position)

    def mouseReleaseEvent(self, event):
        was_group_drag = self.group_drag_proxy is not None
        if was_group_drag:
            self.group_drag_proxy.finish_card_drag()
            self.group_drag_proxy = None
        self.resizing = False
        if not was_group_drag:
            super().mouseReleaseEvent(event)
        else:
            event.accept()
        self.setSelected(True)
        self.update()
        dialog = self.history_dialog()
        if dialog is not None and hasattr(dialog, "finish_history_action"):
            dialog.finish_history_action()


STANDARD_DESIGN_ICONS = (
    ("arrow", "Pfeil", "Arrow"),
    ("double_arrow", "Doppelpfeil", "Double arrow"),
    ("curved_arrow", "Gebogener Pfeil", "Curved arrow"),
    ("chevron", "Winkelpfeil", "Chevron"),
    ("check", "Haken", "Check mark"),
    ("cross", "Kreuz", "Cross"),
    ("plus", "Plus", "Plus"),
    ("minus", "Minus", "Minus"),
    ("warning", "Warnung", "Warning"),
    ("information", "Information", "Information"),
    ("power", "Ein / Aus", "Power"),
    ("home", "Haus", "Home"),
    ("circle", "Kreis", "Circle"),
    ("diamond", "Raute", "Diamond"),
    ("back", "Rücksprung", "Back"),
    ("forward", "Vorwärts", "Forward"),
    ("exchange", "Austausch", "Exchange"),
    ("split", "Aufteilen", "Split"),
    ("merge", "Zusammenführen", "Merge"),
    ("play", "Start", "Start"),
    ("stop", "Stopp", "Stop"),
    ("pause", "Pause", "Pause"),
    ("reset", "Zurücksetzen", "Reset"),
    ("refresh", "Aktualisieren", "Refresh"),
    ("question", "Fragezeichen", "Question"),
    ("prohibited", "Verbot", "Prohibited"),
    ("valve", "Ventil", "Valve"),
    ("pump", "Pumpe", "Pump"),
    ("motor", "Motor", "Motor"),
    ("fan", "Lüfter", "Fan"),
    ("heater", "Heizung", "Heater"),
    ("tank", "Behälter", "Tank"),
    ("pipe", "Rohrleitung", "Pipe"),
    ("meter", "Messgerät", "Meter"),
    ("temperature", "Temperatur", "Temperature"),
    ("pressure", "Druck", "Pressure"),
    ("flow", "Durchfluss", "Flow"),
    ("level", "Füllstand", "Level"),
    ("lock", "Schloss", "Lock"),
    ("unlock", "Entsperren", "Unlock"),
    ("eye", "Auge", "Eye"),
    ("clock", "Uhr", "Clock"),
    ("gear", "Zahnrad", "Gear"),
    ("person", "Person", "Person"),
    ("logic_and", "UND", "AND"),
    ("logic_or", "ODER", "OR"),
    ("logic_not", "NICHT", "NOT"),
    ("logic_nand", "NAND", "NAND"),
    ("logic_nor", "NOR", "NOR"),
    ("logic_xor", "XOR", "XOR"),
    ("logic_xnor", "XNOR", "XNOR"),
    ("logic_zero", "Logisch 0", "Logic 0"),
    ("logic_one", "Logisch 1", "Logic 1"),
)

STANDARD_DESIGN_ICON_GROUPS = (
    (
        "general",
        "Allgemein",
        "General",
        (
            "arrow", "double_arrow", "curved_arrow", "chevron",
            "check", "cross", "plus", "minus", "warning",
            "information", "power", "home", "circle", "diamond",
            "question", "prohibited",
        ),
    ),
    (
        "operation",
        "Bedienung",
        "Operation",
        (
            "back", "forward", "exchange", "split", "merge", "play",
            "stop", "pause", "reset", "refresh",
        ),
    ),
    (
        "process",
        "Prozess",
        "Process",
        (
            "valve", "pump", "motor", "fan", "heater", "tank", "pipe",
            "meter", "temperature", "pressure", "flow", "level",
        ),
    ),
    (
        "logic",
        "Logik",
        "Logic",
        (
            "logic_and", "logic_or", "logic_not", "logic_nand",
            "logic_nor", "logic_xor", "logic_xnor", "logic_zero",
            "logic_one",
        ),
    ),
    (
        "other",
        "Sonstige",
        "Other",
        ("lock", "unlock", "eye", "clock", "gear", "person"),
    ),
)


def draw_standard_design_icon(painter, rect, icon_name, color):
    """Zeichnet ein einfarbiges Standardsymbol skalierbar als Vektorgrafik."""

    size = max(1.0, min(rect.width(), rect.height()))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(rect.center())
    painter.scale(size / 100.0, size / 100.0)
    pen = QPen(QColor(color), 3.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    name = str(icon_name)

    path = QPainterPath()
    if name == "arrow":
        path.moveTo(-38.0, 0.0)
        path.lineTo(30.0, 0.0)
        path.moveTo(9.0, -21.0)
        path.lineTo(32.0, 0.0)
        path.lineTo(9.0, 21.0)
        painter.drawPath(path)
    elif name == "double_arrow":
        path.moveTo(-28.0, 0.0)
        path.lineTo(28.0, 0.0)
        path.moveTo(-9.0, -20.0)
        path.lineTo(-31.0, 0.0)
        path.lineTo(-9.0, 20.0)
        path.moveTo(9.0, -20.0)
        path.lineTo(31.0, 0.0)
        path.lineTo(9.0, 20.0)
        painter.drawPath(path)
    elif name == "curved_arrow":
        path.moveTo(-32.0, 25.0)
        path.cubicTo(-34.0, -17.0, -2.0, -34.0, 27.0, -14.0)
        painter.drawPath(path)
        head = QPainterPath()
        head.moveTo(7.0, -31.0)
        head.lineTo(31.0, -12.0)
        head.lineTo(4.0, -4.0)
        painter.drawPath(head)
    elif name == "chevron":
        path.moveTo(-14.0, -30.0)
        path.lineTo(17.0, 0.0)
        path.lineTo(-14.0, 30.0)
        painter.drawPath(path)
    elif name == "check":
        path.moveTo(-34.0, 2.0)
        path.lineTo(-10.0, 27.0)
        path.lineTo(35.0, -28.0)
        painter.drawPath(path)
    elif name == "cross":
        painter.drawLine(QPointF(-29.0, -29.0), QPointF(29.0, 29.0))
        painter.drawLine(QPointF(29.0, -29.0), QPointF(-29.0, 29.0))
    elif name == "plus":
        painter.drawLine(QPointF(-34.0, 0.0), QPointF(34.0, 0.0))
        painter.drawLine(QPointF(0.0, -34.0), QPointF(0.0, 34.0))
    elif name == "minus":
        painter.drawLine(QPointF(-34.0, 0.0), QPointF(34.0, 0.0))
    elif name == "warning":
        path.moveTo(0.0, -39.0)
        path.lineTo(40.0, 34.0)
        path.lineTo(-40.0, 34.0)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(0.0, -13.0), QPointF(0.0, 12.0))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(0.0, 24.0), 3.5, 3.5)
    elif name == "information":
        painter.drawEllipse(QRectF(-38.0, -38.0, 76.0, 76.0))
        painter.drawLine(QPointF(0.0, -5.0), QPointF(0.0, 25.0))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(0.0, -20.0), 3.5, 3.5)
    elif name == "power":
        painter.drawArc(QRectF(-35.0, -35.0, 70.0, 70.0), 45 * 16, 270 * 16)
        painter.drawLine(QPointF(0.0, -39.0), QPointF(0.0, 1.0))
    elif name == "home":
        path.moveTo(-38.0, -4.0)
        path.lineTo(0.0, -36.0)
        path.lineTo(38.0, -4.0)
        path.moveTo(-29.0, -10.0)
        path.lineTo(-29.0, 34.0)
        path.lineTo(29.0, 34.0)
        path.lineTo(29.0, -10.0)
        painter.drawPath(path)
    elif name == "diamond":
        path.moveTo(0.0, -38.0)
        path.lineTo(38.0, 0.0)
        path.lineTo(0.0, 38.0)
        path.lineTo(-38.0, 0.0)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "back":
        painter.drawLine(QPointF(34.0, -30.0), QPointF(34.0, 30.0))
        path.moveTo(28.0, 0.0)
        path.lineTo(-29.0, 0.0)
        path.moveTo(-8.0, -21.0)
        path.lineTo(-31.0, 0.0)
        path.lineTo(-8.0, 21.0)
        painter.drawPath(path)
    elif name == "forward":
        painter.drawLine(QPointF(-34.0, -30.0), QPointF(-34.0, 30.0))
        path.moveTo(-28.0, 0.0)
        path.lineTo(29.0, 0.0)
        path.moveTo(8.0, -21.0)
        path.lineTo(31.0, 0.0)
        path.lineTo(8.0, 21.0)
        painter.drawPath(path)
    elif name == "exchange":
        path.moveTo(-34.0, -14.0)
        path.lineTo(27.0, -14.0)
        path.moveTo(8.0, -30.0)
        path.lineTo(29.0, -14.0)
        path.lineTo(8.0, 2.0)
        path.moveTo(34.0, 14.0)
        path.lineTo(-27.0, 14.0)
        path.moveTo(-8.0, -2.0)
        path.lineTo(-29.0, 14.0)
        path.lineTo(-8.0, 30.0)
        painter.drawPath(path)
    elif name == "split":
        path.moveTo(-36.0, 0.0)
        path.lineTo(-9.0, 0.0)
        path.lineTo(27.0, -26.0)
        path.moveTo(-9.0, 0.0)
        path.lineTo(27.0, 26.0)
        path.moveTo(12.0, -29.0)
        path.lineTo(31.0, -28.0)
        path.lineTo(25.0, -10.0)
        path.moveTo(12.0, 29.0)
        path.lineTo(31.0, 28.0)
        path.lineTo(25.0, 10.0)
        painter.drawPath(path)
    elif name == "merge":
        path.moveTo(-30.0, -27.0)
        path.lineTo(9.0, 0.0)
        path.lineTo(34.0, 0.0)
        path.moveTo(-30.0, 27.0)
        path.lineTo(9.0, 0.0)
        path.moveTo(14.0, -19.0)
        path.lineTo(35.0, 0.0)
        path.lineTo(14.0, 19.0)
        painter.drawPath(path)
    elif name == "play":
        path.moveTo(-25.0, -35.0)
        path.lineTo(36.0, 0.0)
        path.lineTo(-25.0, 35.0)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPath(path)
    elif name == "stop":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(-33.0, -33.0, 66.0, 66.0), 5.0, 5.0)
    elif name == "pause":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(-29.0, -35.0, 20.0, 70.0), 3.0, 3.0)
        painter.drawRoundedRect(QRectF(9.0, -35.0, 20.0, 70.0), 3.0, 3.0)
    elif name == "reset":
        painter.drawArc(QRectF(-34.0, -34.0, 68.0, 68.0), 35 * 16, 285 * 16)
        path.moveTo(-35.0, -4.0)
        path.lineTo(-36.0, 22.0)
        path.lineTo(-12.0, 15.0)
        painter.drawPath(path)
    elif name == "refresh":
        painter.drawArc(QRectF(-34.0, -34.0, 68.0, 68.0), 25 * 16, 135 * 16)
        painter.drawArc(QRectF(-34.0, -34.0, 68.0, 68.0), 205 * 16, 135 * 16)
        path.moveTo(31.0, -25.0)
        path.lineTo(32.0, -4.0)
        path.lineTo(12.0, -8.0)
        path.moveTo(-31.0, 25.0)
        path.lineTo(-32.0, 4.0)
        path.lineTo(-12.0, 8.0)
        painter.drawPath(path)
    elif name == "question":
        painter.drawEllipse(QRectF(-38.0, -38.0, 76.0, 76.0))
        path.moveTo(-15.0, -15.0)
        path.cubicTo(-9.0, -31.0, 18.0, -30.0, 19.0, -9.0)
        path.cubicTo(20.0, 4.0, 1.0, 5.0, 1.0, 17.0)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(1.0, 29.0), 3.8, 3.8)
    elif name == "prohibited":
        painter.drawEllipse(QRectF(-36.0, -36.0, 72.0, 72.0))
        painter.drawLine(QPointF(-25.0, -25.0), QPointF(25.0, 25.0))
    elif name == "valve":
        path.moveTo(-38.0, -25.0)
        path.lineTo(0.0, 0.0)
        path.lineTo(-38.0, 25.0)
        path.closeSubpath()
        path.moveTo(38.0, -25.0)
        path.lineTo(0.0, 0.0)
        path.lineTo(38.0, 25.0)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(0.0, 0.0), QPointF(0.0, -31.0))
        painter.drawLine(QPointF(-15.0, -31.0), QPointF(15.0, -31.0))
    elif name == "pump":
        painter.drawEllipse(QRectF(-35.0, -35.0, 70.0, 70.0))
        path.moveTo(-18.0, -22.0)
        path.lineTo(25.0, 0.0)
        path.lineTo(-18.0, 22.0)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPath(path)
    elif name == "motor":
        painter.drawEllipse(QRectF(-38.0, -38.0, 76.0, 76.0))
        path.moveTo(-22.0, 22.0)
        path.lineTo(-22.0, -22.0)
        path.lineTo(0.0, 8.0)
        path.lineTo(22.0, -22.0)
        path.lineTo(22.0, 22.0)
        painter.drawPath(path)
    elif name == "fan":
        painter.drawEllipse(QRectF(-7.0, -7.0, 14.0, 14.0))
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        for _step in range(3):
            blade = QPainterPath()
            blade.moveTo(4.0, -3.0)
            blade.cubicTo(16.0, -35.0, 36.0, -28.0, 29.0, -9.0)
            blade.cubicTo(24.0, 3.0, 12.0, 5.0, 4.0, 3.0)
            blade.closeSubpath()
            painter.drawPath(blade)
            painter.rotate(120.0)
        painter.restore()
    elif name == "heater":
        path.moveTo(-35.0, 22.0)
        path.lineTo(-25.0, -22.0)
        path.lineTo(-13.0, 22.0)
        path.lineTo(-1.0, -22.0)
        path.lineTo(11.0, 22.0)
        path.lineTo(23.0, -22.0)
        path.lineTo(35.0, 22.0)
        painter.drawPath(path)
        painter.drawLine(QPointF(-37.0, 33.0), QPointF(37.0, 33.0))
    elif name == "tank":
        painter.drawEllipse(QRectF(-34.0, -37.0, 68.0, 20.0))
        painter.drawArc(QRectF(-34.0, 17.0, 68.0, 20.0), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(-34.0, -27.0), QPointF(-34.0, 27.0))
        painter.drawLine(QPointF(34.0, -27.0), QPointF(34.0, 27.0))
    elif name == "pipe":
        thick_pen = QPen(QColor(color), 6.0)
        thick_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        thick_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(thick_pen)
        path.moveTo(-34.0, -28.0)
        path.lineTo(-8.0, -28.0)
        path.lineTo(-8.0, 28.0)
        path.lineTo(34.0, 28.0)
        painter.drawPath(path)
    elif name == "meter":
        painter.drawArc(QRectF(-38.0, -25.0, 76.0, 76.0), 0, 180 * 16)
        painter.drawLine(QPointF(-38.0, 13.0), QPointF(38.0, 13.0))
        painter.drawLine(QPointF(0.0, 13.0), QPointF(22.0, -12.0))
        painter.drawEllipse(QPointF(0.0, 13.0), 3.5, 3.5)
    elif name == "temperature":
        painter.drawEllipse(QRectF(-16.0, 16.0, 32.0, 32.0))
        painter.drawRoundedRect(QRectF(-10.0, -39.0, 20.0, 66.0), 10.0, 10.0)
        painter.drawLine(QPointF(0.0, 20.0), QPointF(0.0, -25.0))
    elif name == "pressure":
        painter.drawEllipse(QRectF(-36.0, -36.0, 72.0, 72.0))
        painter.drawLine(QPointF(0.0, 0.0), QPointF(22.0, -20.0))
        painter.drawEllipse(QPointF(0.0, 0.0), 3.5, 3.5)
        painter.drawLine(QPointF(0.0, 36.0), QPointF(0.0, 43.0))
    elif name == "flow":
        for vertical in (-22.0, 0.0, 22.0):
            path.moveTo(-36.0, vertical)
            path.cubicTo(-17.0, vertical - 12.0, 5.0, vertical + 12.0, 28.0, vertical)
            path.moveTo(12.0, vertical - 12.0)
            path.lineTo(31.0, vertical)
            path.lineTo(12.0, vertical + 12.0)
        painter.drawPath(path)
    elif name == "level":
        path.moveTo(-33.0, -35.0)
        path.lineTo(-33.0, 35.0)
        path.lineTo(33.0, 35.0)
        path.lineTo(33.0, -35.0)
        painter.drawPath(path)
        painter.drawLine(QPointF(-24.0, 20.0), QPointF(24.0, 20.0))
        painter.drawLine(QPointF(-24.0, 5.0), QPointF(24.0, 5.0))
        painter.drawLine(QPointF(-24.0, -10.0), QPointF(24.0, -10.0))
    elif name in ("logic_and", "logic_nand"):
        painter.drawLine(QPointF(-48.0, -18.0), QPointF(-34.0, -18.0))
        painter.drawLine(QPointF(-48.0, 18.0), QPointF(-34.0, 18.0))
        path.moveTo(-34.0, -34.0)
        path.lineTo(-5.0, -34.0)
        path.cubicTo(19.0, -34.0, 34.0, -19.0, 34.0, 0.0)
        path.cubicTo(34.0, 19.0, 19.0, 34.0, -5.0, 34.0)
        path.lineTo(-34.0, 34.0)
        path.closeSubpath()
        painter.drawPath(path)
        if name == "logic_nand":
            painter.drawEllipse(QPointF(40.0, 0.0), 6.0, 6.0)
            painter.drawLine(QPointF(46.0, 0.0), QPointF(50.0, 0.0))
        else:
            painter.drawLine(QPointF(34.0, 0.0), QPointF(49.0, 0.0))
    elif name in (
        "logic_or", "logic_nor", "logic_xor", "logic_xnor"
    ):
        painter.drawLine(QPointF(-48.0, -18.0), QPointF(-29.0, -18.0))
        painter.drawLine(QPointF(-48.0, 18.0), QPointF(-29.0, 18.0))
        path.moveTo(-34.0, -34.0)
        path.cubicTo(-10.0, -33.0, 22.0, -28.0, 35.0, 0.0)
        path.cubicTo(22.0, 28.0, -10.0, 33.0, -34.0, 34.0)
        path.cubicTo(-18.0, 14.0, -18.0, -14.0, -34.0, -34.0)
        path.closeSubpath()
        painter.drawPath(path)
        if name in ("logic_xor", "logic_xnor"):
            extra = QPainterPath()
            extra.moveTo(-41.0, -34.0)
            extra.cubicTo(-25.0, -14.0, -25.0, 14.0, -41.0, 34.0)
            painter.drawPath(extra)
        if name in ("logic_nor", "logic_xnor"):
            painter.drawEllipse(QPointF(41.0, 0.0), 6.0, 6.0)
            painter.drawLine(QPointF(47.0, 0.0), QPointF(50.0, 0.0))
        else:
            painter.drawLine(QPointF(35.0, 0.0), QPointF(49.0, 0.0))
    elif name == "logic_not":
        painter.drawLine(QPointF(-48.0, 0.0), QPointF(-32.0, 0.0))
        path.moveTo(-32.0, -34.0)
        path.lineTo(-32.0, 34.0)
        path.lineTo(26.0, 0.0)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawEllipse(QPointF(33.0, 0.0), 7.0, 7.0)
        painter.drawLine(QPointF(40.0, 0.0), QPointF(49.0, 0.0))
    elif name in ("logic_zero", "logic_one"):
        painter.drawRoundedRect(QRectF(-32.0, -35.0, 64.0, 70.0), 5.0, 5.0)
        painter.drawLine(QPointF(32.0, 0.0), QPointF(49.0, 0.0))
        if name == "logic_zero":
            painter.drawEllipse(QRectF(-12.0, -23.0, 24.0, 46.0))
        else:
            path.moveTo(-9.0, -14.0)
            path.lineTo(0.0, -23.0)
            path.lineTo(0.0, 23.0)
            path.moveTo(-11.0, 23.0)
            path.lineTo(12.0, 23.0)
            painter.drawPath(path)
    elif name == "lock":
        painter.drawRoundedRect(QRectF(-32.0, -2.0, 64.0, 43.0), 5.0, 5.0)
        painter.drawArc(QRectF(-22.0, -36.0, 44.0, 48.0), 0, 180 * 16)
        painter.drawLine(QPointF(-22.0, -12.0), QPointF(-22.0, 0.0))
        painter.drawLine(QPointF(22.0, -12.0), QPointF(22.0, 0.0))
        painter.drawLine(QPointF(0.0, 14.0), QPointF(0.0, 27.0))
    elif name == "unlock":
        painter.drawRoundedRect(QRectF(-32.0, -2.0, 64.0, 43.0), 5.0, 5.0)
        painter.drawArc(QRectF(-9.0, -40.0, 44.0, 48.0), 0, 180 * 16)
        painter.drawLine(QPointF(35.0, -16.0), QPointF(35.0, 2.0))
        painter.drawLine(QPointF(0.0, 14.0), QPointF(0.0, 27.0))
    elif name == "eye":
        path.moveTo(-40.0, 0.0)
        path.cubicTo(-22.0, -29.0, 22.0, -29.0, 40.0, 0.0)
        path.cubicTo(22.0, 29.0, -22.0, 29.0, -40.0, 0.0)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(0.0, 0.0), 12.0, 12.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(0.0, 0.0), 4.0, 4.0)
    elif name == "clock":
        painter.drawEllipse(QRectF(-37.0, -37.0, 74.0, 74.0))
        painter.drawLine(QPointF(0.0, 0.0), QPointF(0.0, -23.0))
        painter.drawLine(QPointF(0.0, 0.0), QPointF(19.0, 12.0))
    elif name == "gear":
        painter.drawEllipse(QRectF(-25.0, -25.0, 50.0, 50.0))
        painter.drawEllipse(QRectF(-8.0, -8.0, 16.0, 16.0))
        for step in range(8):
            angle = math.radians(step * 45.0)
            inner = QPointF(math.cos(angle) * 27.0, math.sin(angle) * 27.0)
            outer = QPointF(math.cos(angle) * 40.0, math.sin(angle) * 40.0)
            painter.drawLine(inner, outer)
    elif name == "person":
        painter.drawEllipse(QRectF(-14.0, -38.0, 28.0, 28.0))
        path.moveTo(-32.0, 35.0)
        path.cubicTo(-29.0, 6.0, -17.0, -2.0, 0.0, -2.0)
        path.cubicTo(17.0, -2.0, 29.0, 6.0, 32.0, 35.0)
        painter.drawPath(path)
    else:
        painter.drawEllipse(QRectF(-36.0, -36.0, 72.0, 72.0))
    painter.restore()


def standard_design_icon_preview(icon_name, color="#34495e", size=56):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_standard_design_icon(
        painter,
        QRectF(4.0, 4.0, size - 8.0, size - 8.0),
        icon_name,
        color,
    )
    painter.end()
    return QIcon(pixmap)


class StandardIconDialog(QDialog):
    """Kompakte Auswahl der eingebauten Gestaltungssymbole."""

    def __init__(self, translator, parent=None, current_icon=None):
        super().__init__(parent)
        self.translate = translator
        self.selected_icon = None
        self.setWindowTitle(translator("Symbol auswählen", "Select symbol"))
        layout = QVBoxLayout(self)
        introduction = QLabel(
            translator(
                "Wählen Sie ein Symbol. Farbe, Größe und Drehung können danach geändert werden.",
                "Select a symbol. Its color, size, and rotation can be changed afterward.",
            ),
            self,
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        icon_definitions = {
            name: (german, english)
            for name, german, english in STANDARD_DESIGN_ICONS
        }
        tabs = QTabWidget(self)
        current_tab_index = 0
        for tab_index, (_key, german, english, icon_names) in enumerate(
            STANDARD_DESIGN_ICON_GROUPS
        ):
            page = QWidget(tabs)
            grid = QGridLayout(page)
            grid.setContentsMargins(6, 6, 6, 6)
            grid.setSpacing(5)
            for index, name in enumerate(icon_names):
                label_parts = icon_definitions.get(name)
                if label_parts is None:
                    continue
                label = translator(*label_parts)
                button = QToolButton(page)
                button.setIcon(standard_design_icon_preview(name))
                button.setIconSize(QSize(28, 28))
                button.setText(label)
                button.setToolTip(label)
                button.setToolButtonStyle(
                    Qt.ToolButtonStyle.ToolButtonTextUnderIcon
                )
                button_font = button.font()
                button_font.setPointSize(max(7, button_font.pointSize() - 1))
                button.setFont(button_font)
                button.setFixedSize(74, 58)
                if name == current_icon:
                    button.setCheckable(True)
                    button.setChecked(True)
                    current_tab_index = tab_index
                button.clicked.connect(
                    lambda _checked=False, selected=name:
                    self.choose_icon(selected)
                )
                grid.addWidget(button, index // 6, index % 6)
            grid.setRowStretch((len(icon_names) + 5) // 6, 1)
            tabs.addTab(page, translator(german, english))
        tabs.setCurrentIndex(current_tab_index)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            translator("Abbrechen", "Cancel")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_icon(self, icon_name):
        self.selected_icon = str(icon_name)
        self.accept()


class DesignShapeItem(QGraphicsItem):
    """Frei platzierbare Linie, Bézierkurve, Rechteck- oder Ellipsenform."""

    HANDLE_SIZE = 14.0

    def __init__(self, shape_type, width=160.0, height=90.0, data=None):
        super().__init__()
        values = dict(data or {})
        self.shape_type = str(shape_type)
        self.item_width = max(24.0, float(values.get("width", width)))
        self.item_height = max(24.0, float(values.get("height", height)))
        self.line_start = QPointF(
            float(values.get("x1", 0.0)),
            float(values.get("y1", self.item_height)),
        )
        self.line_end = QPointF(
            float(values.get("x2", self.item_width)),
            float(values.get("y2", 0.0)),
        )
        if "c1x" in values or "c2x" in values:
            self.control_point_1 = QPointF(
                float(values.get("c1x", self.item_width / 3.0)),
                float(values.get("c1y", -self.item_height / 2.0)),
            )
            self.control_point_2 = QPointF(
                float(values.get("c2x", self.item_width * 2.0 / 3.0)),
                float(values.get("c2y", -self.item_height / 2.0)),
            )
        elif "cx" in values or "cy" in values:
            # Eine ältere quadratische Kurve wird geometrisch gleichwertig
            # in eine kubische Kurve mit zwei Kontrollpunkten überführt.
            old_control = QPointF(
                float(values.get("cx", self.item_width / 2.0)),
                float(values.get("cy", -self.item_height / 2.0)),
            )
            self.control_point_1 = self.line_start + (
                old_control - self.line_start
            ) * (2.0 / 3.0)
            self.control_point_2 = self.line_end + (
                old_control - self.line_end
            ) * (2.0 / 3.0)
        else:
            self.control_point_1 = QPointF(
                self.item_width / 3.0, -self.item_height / 2.0
            )
            self.control_point_2 = QPointF(
                self.item_width * 2.0 / 3.0, -self.item_height / 2.0
            )
        self.line_color = QColor(values.get("line_color", "#202020"))
        self.line_width = max(1.0, float(values.get("line_width", 1.0)))
        self.arrow_enabled = bool(values.get("arrow_enabled", False))
        self.icon_name = str(values.get("icon_name", "arrow"))
        fill = values.get("fill_color")
        self.fill_color = QColor(fill) if fill else None
        self.editable = True
        self.locked = bool(values.get("locked", False))
        self.resizing = False
        self.rotating = False
        self.moving = False
        self.drag_allowed = False
        self.line_endpoint = None
        self.selected_endpoints = set()
        self.partial_endpoint_start_positions = {}
        self.whole_move_start_position = QPointF()
        self.endpoint_group_moving = False
        self.endpoint_drag_start_position = QPointF()
        self.endpoint_drag_anchor_position = QPointF()
        self.group_endpoint_start_positions = {}
        self.resize_start = QPointF()
        self.resize_start_size = (self.item_width, self.item_height)
        self.setZValue(float(values.get("layer", 0.0)))
        self.setTransformOriginPoint(
            self.item_width / 2.0,
            self.item_height / 2.0,
        )
        self.setRotation(float(values.get("rotation", 0.0)))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def is_connector(self):
        return self.shape_type in ("line", "curve")

    def history_dialog(self):
        views = self.scene().views() if self.scene() is not None else []
        return views[0].window() if views else None

    def snapped_scene_position(self, position):
        dialog = self.history_dialog()
        if dialog is not None and hasattr(dialog, "snap_scene_position"):
            return dialog.snap_scene_position(position)
        return QPointF(position)

    def connector_path(self):
        path = QPainterPath(self.line_start)
        if self.shape_type == "curve":
            path.cubicTo(
                self.control_point_1,
                self.control_point_2,
                self.line_end,
            )
        else:
            path.lineTo(self.line_end)
        return path

    def set_editable(self, editable):
        self.editable = bool(editable)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            self.editable and not self.locked,
        )
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, self.editable)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if not self.editable:
            self.setSelected(False)
        self.update()

    def set_locked(self, locked):
        self.locked = bool(locked)
        self.resizing = False
        self.rotating = False
        self.moving = False
        self.drag_allowed = False
        self.line_endpoint = None
        self.finish_group_endpoint_drag()
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            self.editable and not self.locked,
        )
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def boundingRect(self):
        arrow_margin = self.arrow_size() if self.is_connector() else 0.0
        margin = max(self.line_width, self.HANDLE_SIZE, arrow_margin)
        rect = self.content_rect().adjusted(
            -margin, -margin, margin, margin
        )
        if self.shape_type == "icon":
            rect = rect.united(self.rotation_handle_rect().adjusted(
                -margin, -margin, margin, margin
            ))
        return rect

    def arrow_size(self):
        return max(10.0, min(60.0, 6.0 + self.line_width * 3.0))

    def content_rect(self):
        if self.is_connector():
            rect = self.connector_path().boundingRect()
            if self.shape_type == "curve":
                rect = rect.united(self.line_handle_rect(self.control_point_1))
                rect = rect.united(self.line_handle_rect(self.control_point_2))
            return rect
        return QRectF(0.0, 0.0, self.item_width, self.item_height)

    def shape(self):
        """Begrenzt den Trefferbereich einer Linie auf ihren sichtbaren Verlauf."""

        if not self.is_connector():
            return super().shape()
        stroker = QPainterPathStroker()
        stroker.setWidth(max(4.0, self.line_width + 2.0))
        hit_path = stroker.createStroke(self.connector_path())
        if self.isSelected():
            hit_path.addRect(self.line_handle_rect(self.line_start))
            hit_path.addRect(self.line_handle_rect(self.line_end))
            if self.shape_type == "curve":
                hit_path.addRect(self.line_handle_rect(self.control_point_1))
                hit_path.addRect(self.line_handle_rect(self.control_point_2))
        else:
            if "start" in self.selected_endpoints:
                hit_path.addRect(self.line_handle_rect(self.line_start))
            if "end" in self.selected_endpoints:
                hit_path.addRect(self.line_handle_rect(self.line_end))
        return hit_path

    def handle_rect(self):
        size = self.HANDLE_SIZE
        return QRectF(
            self.item_width - size,
            self.item_height - size,
            size,
            size,
        )

    def rotation_handle_center(self):
        return QPointF(self.item_width / 2.0, -24.0)

    def rotation_handle_rect(self):
        size = self.HANDLE_SIZE
        center = self.rotation_handle_center()
        return QRectF(
            center.x() - size / 2.0,
            center.y() - size / 2.0,
            size,
            size,
        )

    def line_handle_rect(self, point):
        size = self.HANDLE_SIZE
        return QRectF(
            point.x() - size / 2.0,
            point.y() - size / 2.0,
            size,
            size,
        )

    def endpoint_scene_position(self, endpoint):
        point = self.line_start if endpoint == "start" else self.line_end
        return self.mapToScene(point)

    def set_endpoint_scene_position(self, endpoint, scene_position):
        self.prepareGeometryChange()
        point = self.mapFromScene(scene_position)
        if endpoint == "start":
            self.line_start = point
        else:
            self.line_end = point
        self.update()

    def begin_whole_move(self):
        """Merkt die durch den Auswahlrahmen zusätzlich erfassten Linienenden."""

        self.whole_move_start_position = QPointF(self.pos())
        self.partial_endpoint_start_positions = {}
        if self.scene() is not None:
            for item in self.scene().items():
                if not isinstance(item, DesignShapeItem) or not item.is_connector():
                    continue
                if item.locked:
                    continue
                for endpoint in item.selected_endpoints:
                    self.partial_endpoint_start_positions[(item, endpoint)] = (
                        item.endpoint_scene_position(endpoint)
                    )
                    item.endpoint_group_moving = True
                    item.update()
        self.moving = True
        self.update()

    def update_selected_endpoints(self):
        delta = self.pos() - self.whole_move_start_position
        for (item, endpoint), start_position in self.partial_endpoint_start_positions.items():
            if item.scene() is self.scene():
                item.set_endpoint_scene_position(
                    endpoint,
                    start_position + delta,
                )

    def finish_whole_move(self):
        self.update_selected_endpoints()
        for item, _endpoint in self.partial_endpoint_start_positions:
            item.endpoint_group_moving = False
            item.update()
        self.partial_endpoint_start_positions = {}
        self.moving = False
        self.update()

    def begin_group_endpoint_drag(self, endpoint, scene_position):
        """Startet das gemeinsame Ziehen überlagerter markierter Linienenden."""

        if self.scene() is None:
            return False
        clicked_position = self.endpoint_scene_position(endpoint)
        candidates = {(self, endpoint): clicked_position}
        tolerance = self.HANDLE_SIZE
        for item in self.scene().items():
            if not isinstance(item, DesignShapeItem) or not item.is_connector():
                continue
            if item.locked:
                continue
            selectable_endpoints = set(item.selected_endpoints)
            if item.isSelected():
                selectable_endpoints.update(("start", "end"))
            for other_endpoint in selectable_endpoints:
                other_position = item.endpoint_scene_position(other_endpoint)
                if math.hypot(
                    other_position.x() - clicked_position.x(),
                    other_position.y() - clicked_position.y(),
                ) <= tolerance:
                    candidates[(item, other_endpoint)] = other_position
        if len(candidates) < 2:
            return False
        self.endpoint_drag_start_position = QPointF(scene_position)
        self.endpoint_drag_anchor_position = QPointF(clicked_position)
        self.group_endpoint_start_positions = candidates
        for item, _other_endpoint in candidates:
            item.endpoint_group_moving = True
            item.update()
        return True

    def move_group_endpoints(self, scene_position):
        raw_delta = scene_position - self.endpoint_drag_start_position
        anchor_target = self.endpoint_drag_anchor_position + raw_delta
        snapped_anchor = self.snapped_scene_position(anchor_target)
        delta = snapped_anchor - self.endpoint_drag_anchor_position
        for (item, endpoint), start_position in self.group_endpoint_start_positions.items():
            if item.scene() is self.scene():
                item.set_endpoint_scene_position(endpoint, start_position + delta)

    def finish_group_endpoint_drag(self):
        for item, _endpoint in self.group_endpoint_start_positions:
            item.endpoint_group_moving = False
            item.update()
        self.group_endpoint_start_positions = {}
        self.endpoint_drag_anchor_position = QPointF()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.line_color, self.line_width))
        painter.setBrush(
            QBrush(self.fill_color)
            if self.fill_color is not None
            else QBrush(Qt.BrushStyle.NoBrush)
        )
        rect = self.content_rect().adjusted(
            self.line_width / 2.0,
            self.line_width / 2.0,
            -self.line_width / 2.0,
            -self.line_width / 2.0,
        )
        if self.is_connector():
            painter.drawPath(self.connector_path())
            if self.arrow_enabled:
                tangent_start = (
                    self.control_point_2
                    if self.shape_type == "curve"
                    else self.line_start
                )
                dx = self.line_end.x() - tangent_start.x()
                dy = self.line_end.y() - tangent_start.y()
                length = math.hypot(dx, dy)
                if length > 0.001:
                    unit_x, unit_y = dx / length, dy / length
                    size = self.arrow_size()
                    base_x = self.line_end.x() - unit_x * size
                    base_y = self.line_end.y() - unit_y * size
                    half_width = size * 0.42
                    normal_x, normal_y = -unit_y, unit_x
                    arrow = QPainterPath(self.line_end)
                    arrow.lineTo(
                        base_x + normal_x * half_width,
                        base_y + normal_y * half_width,
                    )
                    arrow.lineTo(
                        base_x - normal_x * half_width,
                        base_y - normal_y * half_width,
                    )
                    arrow.closeSubpath()
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(self.line_color)
                    painter.drawPath(arrow)
        elif self.shape_type == "icon":
            draw_standard_design_icon(
                painter,
                rect.adjusted(5.0, 5.0, -5.0, -5.0),
                self.icon_name,
                self.line_color,
            )
        elif self.shape_type == "ellipse":
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        dialog = (
            self.scene().views()[0].window()
            if self.scene() is not None and self.scene().views()
            else None
        )
        handles_hidden = bool(
            dialog is not None
            and getattr(dialog, "nudge_handles_hidden", False)
        )
        if self.editable and not self.locked and self.isSelected() and not self.moving:
            selection_pen = QPen(QColor("#c51d24"), 1.5)
            selection_pen.setCosmetic(True)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if not self.is_connector():
                painter.drawRect(self.content_rect())
            painter.setBrush(QColor("#ffffff"))
            if self.is_connector() and not handles_hidden:
                if self.line_endpoint != "start":
                    painter.drawRect(self.line_handle_rect(self.line_start))
                if self.line_endpoint != "end":
                    painter.drawRect(self.line_handle_rect(self.line_end))
                if self.shape_type == "curve":
                    control_pen = QPen(QColor("#777777"), 1.0, Qt.PenStyle.DashLine)
                    control_pen.setCosmetic(True)
                    painter.setPen(control_pen)
                    painter.drawLine(self.line_start, self.control_point_1)
                    painter.drawLine(self.control_point_2, self.line_end)
                    painter.setPen(selection_pen)
                    if self.line_endpoint != "control_1":
                        painter.drawRect(self.line_handle_rect(self.control_point_1))
                    if self.line_endpoint != "control_2":
                        painter.drawRect(self.line_handle_rect(self.control_point_2))
            elif not self.is_connector() and not self.resizing and not handles_hidden:
                painter.drawRect(self.handle_rect())
                if self.shape_type == "icon" and not self.rotating:
                    center = self.rotation_handle_center()
                    painter.drawLine(
                        QPointF(self.item_width / 2.0, 0.0),
                        center,
                    )
                    painter.setBrush(QColor("#ffffff"))
                    painter.drawEllipse(self.rotation_handle_rect())
        elif (
            self.editable
            and not self.locked
            and self.is_connector()
            and self.selected_endpoints
            and not self.endpoint_group_moving
            and not handles_hidden
        ):
            selection_pen = QPen(QColor("#c51d24"), 1.5)
            selection_pen.setCosmetic(True)
            painter.setPen(selection_pen)
            painter.setBrush(QColor("#ffffff"))
            for endpoint in self.selected_endpoints:
                point = self.line_start if endpoint == "start" else self.line_end
                painter.drawRect(self.line_handle_rect(point))
        if self.editable and self.locked:
            draw_locked_indicator(painter, self.content_rect())

    def mousePressEvent(self, event):
        dialog = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
        if dialog is not None and hasattr(dialog, "begin_history_action"):
            dialog.begin_history_action()
        self.drag_allowed = bool(
            self.editable and not self.locked and self.isSelected()
        )
        if (
            self.editable
            and self.drag_allowed
            and self.shape_type == "icon"
            and self.rotation_handle_rect().contains(event.pos())
        ):
            self.rotating = True
            self.update()
            event.accept()
            return
        if (
            self.editable
            and not self.locked
            and self.is_connector()
            and (self.drag_allowed or self.selected_endpoints)
        ):
            if (
                self.shape_type == "curve"
                and self.drag_allowed
                and self.line_handle_rect(self.control_point_1).contains(event.pos())
            ):
                self.line_endpoint = "control_1"
                self.update()
                event.accept()
                return
            if (
                self.shape_type == "curve"
                and self.drag_allowed
                and self.line_handle_rect(self.control_point_2).contains(event.pos())
            ):
                self.line_endpoint = "control_2"
                self.update()
                event.accept()
                return
            if self.line_handle_rect(self.line_start).contains(event.pos()):
                if self.begin_group_endpoint_drag("start", event.scenePos()):
                    event.accept()
                    return
                self.line_endpoint = "start"
                self.update()
                event.accept()
                return
            if self.line_handle_rect(self.line_end).contains(event.pos()):
                if self.begin_group_endpoint_drag("end", event.scenePos()):
                    event.accept()
                    return
                self.line_endpoint = "end"
                self.update()
                event.accept()
                return
        if (
            self.editable
            and self.drag_allowed
            and not self.is_connector()
            and self.handle_rect().contains(event.pos())
        ):
            self.resizing = True
            self.resize_start = event.scenePos()
            self.resize_start_size = (self.item_width, self.item_height)
            self.setSelected(True)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.group_endpoint_start_positions:
            self.move_group_endpoints(event.scenePos())
            event.accept()
            return
        if self.rotating:
            center = self.mapToScene(
                QPointF(self.item_width / 2.0, self.item_height / 2.0)
            )
            delta = event.scenePos() - center
            angle = math.degrees(math.atan2(delta.y(), delta.x())) + 90.0
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                angle = round(angle / 15.0) * 15.0
            self.setRotation(angle % 360.0)
            self.update()
            event.accept()
            return
        if self.line_endpoint is not None:
            self.prepareGeometryChange()
            point = self.mapFromScene(
                self.snapped_scene_position(event.scenePos())
            )
            if self.line_endpoint == "control_1":
                self.control_point_1 = point
                self.update()
                event.accept()
                return
            if self.line_endpoint == "control_2":
                self.control_point_2 = point
                self.update()
                event.accept()
                return
            anchor = self.line_end if self.line_endpoint == "start" else self.line_start
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if abs(point.x() - anchor.x()) >= abs(point.y() - anchor.y()):
                    point.setY(anchor.y())
                else:
                    point.setX(anchor.x())
            if self.line_endpoint == "start":
                self.line_start = point
            else:
                self.line_end = point
            self.update()
            event.accept()
            return
        if self.resizing:
            delta = event.scenePos() - self.resize_start
            if self.shape_type == "icon" and self.rotation():
                angle = math.radians(-self.rotation())
                delta = QPointF(
                    delta.x() * math.cos(angle) - delta.y() * math.sin(angle),
                    delta.x() * math.sin(angle) + delta.y() * math.cos(angle),
                )
            self.prepareGeometryChange()
            start_width, start_height = self.resize_start_size

            dialog = self.history_dialog()
            if (
                dialog is not None
                and hasattr(dialog, "grid_snap_active")
                and dialog.grid_snap_active()
            ):
                target_corner = self.mapToScene(
                    QPointF(start_width + delta.x(), start_height + delta.y())
                )
                snapped_corner = dialog.snap_scene_position(target_corner)
                local_corner = self.mapFromScene(snapped_corner)
                delta = QPointF(
                    local_corner.x() - start_width,
                    local_corner.y() - start_height,
                )

            if (
                self.shape_type == "icon"
                or event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                relative_x = delta.x() / max(start_width, 1.0)
                relative_y = delta.y() / max(start_height, 1.0)
                scale = (
                    1.0 + relative_x
                    if abs(relative_x) >= abs(relative_y)
                    else 1.0 + relative_y
                )
                minimum_scale = max(
                    24.0 / max(start_width, 1.0),
                    24.0 / max(start_height, 1.0),
                )
                scale = max(minimum_scale, scale)
                self.item_width = start_width * scale
                self.item_height = start_height * scale
            else:
                self.item_width = max(24.0, start_width + delta.x())
                self.item_height = max(24.0, start_height + delta.y())
            self.setTransformOriginPoint(
                self.item_width / 2.0,
                self.item_height / 2.0,
            )
            self.update()
            event.accept()
            return
        if not self.drag_allowed:
            event.accept()
            return
        if not self.moving:
            self.begin_whole_move()
        super().mouseMoveEvent(event)
        dialog = self.history_dialog()
        if (
            dialog is not None
            and hasattr(dialog, "grid_snap_active")
            and dialog.grid_snap_active()
        ):
            raw_position = QPointF(self.pos())
            snapped_position = dialog.snap_scene_position(raw_position)
            correction = snapped_position - raw_position
            if not correction.isNull() and self.scene() is not None:
                for item in self.scene().selectedItems():
                    if item is self:
                        continue
                    if isinstance(item, DesignShapeItem) and not item.locked:
                        item.setPos(item.pos() + correction)
                    elif isinstance(item, ResizableBackgroundItem) and not item.locked:
                        item.setPos(item.pos() + correction)
                    elif isinstance(item, MovableCardProxy) and not item.locked:
                        item.setPos(item.pos() + correction)
            self.setPos(snapped_position)
        self.update_selected_endpoints()

    def mouseReleaseEvent(self, event):
        was_group_endpoint_drag = bool(self.group_endpoint_start_positions)
        if was_group_endpoint_drag:
            self.move_group_endpoints(event.scenePos())
            self.finish_group_endpoint_drag()
        was_resizing = self.resizing
        self.resizing = False
        if was_resizing:
            self.update()
        was_line_resize = self.line_endpoint is not None
        self.line_endpoint = None
        if was_line_resize:
            self.update()
        was_rotating = self.rotating
        self.rotating = False
        if was_rotating:
            self.update()
        if (
            self.drag_allowed
            and not was_line_resize
            and not was_group_endpoint_drag
            and not was_rotating
        ):
            super().mouseReleaseEvent(event)
        else:
            event.accept()
        if self.moving:
            self.finish_whole_move()
        self.drag_allowed = False
        dialog = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
        if dialog is not None and hasattr(dialog, "finish_history_action"):
            dialog.finish_history_action()

    def to_data(self):
        data = {
            "type": self.shape_type,
            "x": self.pos().x(),
            "y": self.pos().y(),
            "width": self.item_width,
            "height": self.item_height,
            "line_color": self.line_color.name(),
            "line_width": self.line_width,
            "fill_color": self.fill_color.name() if self.fill_color is not None else None,
            "layer": self.zValue(),
            "locked": self.locked,
        }
        if self.shape_type == "icon":
            data.update({
                "icon_name": self.icon_name,
                "rotation": self.rotation(),
            })
        if self.is_connector():
            data.update({
                "x1": self.line_start.x(),
                "y1": self.line_start.y(),
                "x2": self.line_end.x(),
                "y2": self.line_end.y(),
                "arrow_enabled": self.arrow_enabled,
            })
            if self.shape_type == "curve":
                data.update({
                    "c1x": self.control_point_1.x(),
                    "c1y": self.control_point_1.y(),
                    "c2x": self.control_point_2.x(),
                    "c2y": self.control_point_2.y(),
                })
        return data


class MovableCardProxy(QGraphicsProxyWidget):
    """Verschiebt eine Bedienkarte im Bearbeitungsmodus zuverlässig."""

    RESIZE_HANDLE_SIZE = 14.0

    def __init__(self, card_role):
        super().__init__()
        self.card_role = str(card_role)
        self.editable = True
        self.locked = False
        self.dragging = False
        self.resizing = False
        self.drag_offset = QPointF()
        self.drag_start_scene_position = QPointF()
        self.drag_start_positions = {}
        self.drag_start_bounds = {}
        self.attached_endpoint_start_positions = {}
        self.resize_start_scene_position = QPointF()
        self.resize_start_sizes = {}
        self.minimum_card_width = 180.0
        self.minimum_card_height = 46.0
        self.mouse_grabber = None
        self.context_selection_snapshot = []
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def configure_card_size(self, minimum_width=180.0, minimum_height=None):
        card = self.widget()
        if card is None:
            return
        card.adjustSize()
        initial_width = card.width()
        initial_height = card.height()
        size_hint = card.minimumSizeHint()
        self.minimum_card_width = float(minimum_width)
        self.minimum_card_height = float(
            minimum_height if minimum_height is not None else max(42, size_hint.height())
        )
        card.setMinimumSize(
            round(self.minimum_card_width), round(self.minimum_card_height)
        )
        card.setMaximumSize(16777215, 16777215)
        self.set_card_size(initial_width, initial_height)

    def set_card_size(self, width, height):
        card = self.widget()
        if card is None:
            return
        target_width = round(max(self.minimum_card_width, float(width)))
        target_height = round(max(self.minimum_card_height, float(height)))
        card.setMinimumSize(
            round(self.minimum_card_width), round(self.minimum_card_height)
        )
        card.setMaximumSize(16777215, 16777215)
        self.resize(target_width, target_height)
        card.resize(target_width, target_height)
        if (
            isinstance(card, ExperimentCard)
            and self.card_role != "comment"
        ):
            content_scale = card.content_scale_for_size(
                target_width, target_height
            )
            card.apply_content_scale(content_scale)
            for page in card.findChildren(CompactVerticalInputPage):
                page.update_positions()
            for page in card.findChildren(CompactVerticalOutputPage):
                page.update_positions()
        card.updateGeometry()
        self.updateGeometry()
        self.update()

    def resize_handle_rect(self):
        rect = self.boundingRect()
        size = self.RESIZE_HANDLE_SIZE
        return QRectF(rect.right() - size, rect.bottom() - size, size, size)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        dialog = self.history_dialog()
        handles_hidden = bool(
            dialog is not None
            and getattr(dialog, "nudge_handles_hidden", False)
        )
        if self.editable and not self.locked and self.isSelected() and not handles_hidden:
            painter.setPen(QPen(QColor("#c51d24"), 1.5))
            painter.setBrush(QColor("#ffffff"))
            painter.drawRect(self.resize_handle_rect().adjusted(1.0, 1.0, -1.0, -1.0))
        if self.editable and self.locked:
            draw_locked_indicator(painter, self.boundingRect())

    def setWidget(self, widget):
        super().setWidget(widget)
        self.install_widget_filters(widget)

    def install_widget_filters(self, widget):
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def set_editable(self, editable):
        self.editable = bool(editable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, self.editable)
        if not self.editable:
            self.setSelected(False)
        if not self.editable and self.mouse_grabber is not None:
            self.mouse_grabber.releaseMouse()
            self.mouse_grabber = None
            self.dragging = False
            self.resizing = False
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if self.editable and not self.locked
            else Qt.CursorShape.ArrowCursor
        )

    def set_locked(self, locked):
        self.locked = bool(locked)
        if self.mouse_grabber is not None:
            self.mouse_grabber.releaseMouse()
            self.mouse_grabber = None
        self.dragging = False
        self.resizing = False
        self.drag_start_positions = {}
        self.drag_start_bounds = {}
        self.resize_start_sizes = {}
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if self.editable and not self.locked
            else Qt.CursorShape.ArrowCursor
        )
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            card = self.widget()
            if isinstance(card, ExperimentCard):
                card.set_selected_for_editing(bool(value))
        return super().itemChange(change, value)

    def preserve_selection_for_context_menu(self):
        """Behält eine Mehrfachauswahl beim Rechtsklick auf eine markierte Karte."""

        if self.isSelected():
            self.context_selection_snapshot = self.selected_movable_items()
            return
        if self.scene() is not None:
            self.scene().clearSelection()
        self.setSelected(True)
        self.context_selection_snapshot = [self]

    def restore_context_selection(self):
        if self.scene() is None or not self.context_selection_snapshot:
            return
        targets = [
            item for item in self.context_selection_snapshot
            if item.scene() is self.scene()
        ]
        self.scene().clearSelection()
        for item in targets:
            item.setSelected(True)
        self.context_selection_snapshot = []

    def mousePressEvent(self, event):
        if (
            self.card_role == "network_view"
            and event.button() == Qt.MouseButton.LeftButton
        ):
            card = self.widget()
            if isinstance(card, SimplifiedNetworkCard):
                # QGraphicsProxyWidget kann den ersten Klick selbst erhalten,
                # bevor er an das eingebettete Widget weitergereicht wird.
                # Daher die Neuronenauswahl bereits hier auswerten.
                local_point = QPointF(event.pos())
                if card.clear_focus_at(local_point) or card.pin_neuron_at(local_point):
                    event.accept()
                    return
        if (
            self.editable
            and event.button() == Qt.MouseButton.RightButton
        ):
            self.preserve_selection_for_context_menu()
            event.accept()
            return
        super().mousePressEvent(event)

    def selected_card_proxies(self):
        if self.scene() is None:
            return [self]
        selected = [
            item for item in self.scene().selectedItems()
            if isinstance(item, MovableCardProxy) and item.editable and not item.locked
        ]
        return selected or [self]

    def selected_movable_items(self):
        if self.scene() is None:
            return [self]
        selected = [
            item for item in self.scene().selectedItems()
            if (
                isinstance(item, MovableCardProxy)
                and item.editable and not item.locked
            ) or (
                isinstance(item, ResizableBackgroundItem)
                and item.editable and not item.locked
            ) or (
                isinstance(item, DesignShapeItem)
                and item.editable and not item.locked
            )
        ]
        return selected or [self]

    def history_dialog(self):
        views = self.scene().views() if self.scene() is not None else []
        return views[0].window() if views else None

    def begin_card_drag(self, scene_position, modifiers):
        if self.locked:
            return False
        if not modifiers & Qt.KeyboardModifier.ShiftModifier:
            if not self.isSelected() and self.scene() is not None:
                self.scene().clearSelection()
            self.setSelected(True)
        else:
            self.setSelected(not self.isSelected())
            if not self.isSelected():
                return False
        dialog = self.history_dialog()
        if dialog is not None and hasattr(dialog, "begin_history_action"):
            dialog.begin_history_action()
        self.dragging = True
        self.drag_start_scene_position = scene_position
        self.drag_start_positions = {
            item: QPointF(item.pos()) for item in self.selected_movable_items()
        }
        self.drag_start_bounds = {
            item: QRectF(item.sceneBoundingRect()) for item in self.drag_start_positions
        }
        self.attached_endpoint_start_positions = {}
        if self.scene() is not None:
            # Linienenden folgen einer bewegten Auswahl ausschließlich dann,
            # wenn der Auswahlrahmen den jeweiligen Endpunkt selbst erfasst
            # hat. Eine räumliche Nähe oder vermeintliche Andockstelle reicht
            # bewusst nicht aus. Das gilt einheitlich für alle Kartenarten.
            for shape in self.scene().items():
                if (
                    not isinstance(shape, DesignShapeItem)
                    or not shape.is_connector()
                    or shape.locked
                    or shape in self.drag_start_positions
                ):
                    continue
                for endpoint in shape.selected_endpoints:
                    self.attached_endpoint_start_positions[(shape, endpoint)] = (
                        QPointF(shape.endpoint_scene_position(endpoint))
                    )
        for item in self.drag_start_positions:
            if isinstance(item, DesignShapeItem):
                item.begin_whole_move()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        return True

    def finish_card_drag(self):
        for item in self.drag_start_positions:
            if isinstance(item, DesignShapeItem):
                item.finish_whole_move()
        self.dragging = False
        self.drag_start_positions = {}
        self.drag_start_bounds = {}
        self.attached_endpoint_start_positions = {}
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def begin_card_resize(self, scene_position, modifiers):
        if self.locked:
            return False
        if not modifiers & Qt.KeyboardModifier.ShiftModifier:
            if not self.isSelected() and self.scene() is not None:
                self.scene().clearSelection()
            self.setSelected(True)
        dialog = self.history_dialog()
        if dialog is not None and hasattr(dialog, "begin_history_action"):
            dialog.begin_history_action()
            dialog.last_selected_card = self
        targets = [
            item for item in self.selected_card_proxies()
            if item.card_role == self.card_role
        ]
        self.resizing = True
        self.resize_start_scene_position = scene_position
        self.resize_start_sizes = {
            item: (item.widget().width(), item.widget().height()) for item in targets
        }
        return True

    def resize_selected_cards(self, scene_position):
        if not self.resize_start_sizes:
            return
        delta = scene_position - self.resize_start_scene_position
        dialog = self.history_dialog()
        if (
            dialog is not None
            and hasattr(dialog, "grid_snap_active")
            and dialog.grid_snap_active()
            and self in self.resize_start_sizes
        ):
            start_width, start_height = self.resize_start_sizes[self]
            start_top_left = self.mapToScene(QPointF(0.0, 0.0))
            target_corner = QPointF(
                start_top_left.x() + start_width + delta.x(),
                start_top_left.y() + start_height + delta.y(),
            )
            snapped_corner = dialog.snap_scene_position(target_corner)
            delta = QPointF(
                snapped_corner.x() - start_top_left.x() - start_width,
                snapped_corner.y() - start_top_left.y() - start_height,
            )
        for item, (width, height) in self.resize_start_sizes.items():
            item.set_card_size(width + delta.x(), height + delta.y())

    def finish_card_resize(self):
        if not self.resizing:
            return
        self.resizing = False
        self.resize_start_sizes = {}
        dialog = self.history_dialog()
        if dialog is not None and hasattr(dialog, "finish_history_action"):
            dialog.finish_history_action()

    def move_selected_cards(self, scene_position):
        if not self.drag_start_positions or self.scene() is None:
            return
        delta = scene_position - self.drag_start_scene_position
        scene_rect = self.scene().sceneRect()
        margin = 50.0
        desired_right = max(
            bounds.right() + delta.x()
            for bounds in self.drag_start_bounds.values()
        )
        desired_bottom = max(
            bounds.bottom() + delta.y()
            for bounds in self.drag_start_bounds.values()
        )
        expanded_right = max(scene_rect.right(), desired_right + margin)
        expanded_bottom = max(scene_rect.bottom(), desired_bottom + margin)
        if (
            expanded_right > scene_rect.right() + 0.5
            or expanded_bottom > scene_rect.bottom() + 0.5
        ):
            self.scene().setSceneRect(QRectF(
                scene_rect.topLeft(),
                QPointF(expanded_right, expanded_bottom),
            ))
            views = self.scene().views()
            if views and hasattr(views[0], "sync_grid_rect"):
                views[0].sync_grid_rect()
            scene_rect = self.scene().sceneRect()
        minimum_dx = max(
            scene_rect.left() - bounds.left()
            for bounds in self.drag_start_bounds.values()
        )
        maximum_dx = min(
            scene_rect.right() - bounds.right()
            for bounds in self.drag_start_bounds.values()
        )
        minimum_dy = max(
            scene_rect.top() - bounds.top()
            for bounds in self.drag_start_bounds.values()
        )
        maximum_dy = min(
            scene_rect.bottom() - bounds.bottom()
            for bounds in self.drag_start_bounds.values()
        )
        delta.setX(max(minimum_dx, min(maximum_dx, delta.x())))
        delta.setY(max(minimum_dy, min(maximum_dy, delta.y())))
        dialog = self.history_dialog()
        anchor_start = self.drag_start_positions.get(self)
        if (
            anchor_start is not None
            and dialog is not None
            and hasattr(dialog, "grid_snap_active")
            and dialog.grid_snap_active()
        ):
            snapped_anchor = dialog.snap_scene_position(anchor_start + delta)
            delta = snapped_anchor - anchor_start
            delta.setX(max(minimum_dx, min(maximum_dx, delta.x())))
            delta.setY(max(minimum_dy, min(maximum_dy, delta.y())))
        for item, start in self.drag_start_positions.items():
            item.setPos(start + delta)
        for (shape, endpoint), start in self.attached_endpoint_start_positions.items():
            if shape.scene() is self.scene():
                shape.set_endpoint_scene_position(endpoint, start + delta)
        for item in self.drag_start_positions:
            if isinstance(item, DesignShapeItem):
                item.update_selected_endpoints()

    def scene_position_from_mouse_event(self, event):
        views = self.scene().views() if self.scene() is not None else []
        if not views:
            return QPointF()
        view = views[0]
        viewport_position = view.viewport().mapFromGlobal(
            event.globalPosition().toPoint()
        )
        return view.mapToScene(viewport_position)

    def move_to_scene_position(self, scene_position):
        new_position = scene_position - self.drag_offset
        scene_rect = self.scene().sceneRect()
        item_rect = self.boundingRect()
        new_position.setX(max(
            scene_rect.left(),
            min(new_position.x(), scene_rect.right() - item_rect.width()),
        ))
        new_position.setY(max(
            scene_rect.top(),
            min(new_position.y(), scene_rect.bottom() - item_rect.height()),
        ))
        self.setPos(new_position)

    def eventFilter(self, watched, event):
        views = self.scene().views() if self.scene() is not None else []
        view = views[0] if views else None
        if (
            view is not None
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
            and view.begin_alt_pan(event.globalPosition().toPoint())
        ):
            self.mouse_grabber = watched
            watched.grabMouse()
            return True
        if view is not None and view.alt_panning:
            if event.type() == QEvent.Type.MouseMove:
                view.continue_alt_pan(event.globalPosition().toPoint())
                return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
            ):
                view.end_alt_pan()
                if self.mouse_grabber is not None:
                    self.mouse_grabber.releaseMouse()
                    self.mouse_grabber = None
                return True
        if (
            self.card_role == "network_view"
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            card = self.widget()
            if isinstance(card, SimplifiedNetworkCard):
                # Das Widget steckt in einem zoombaren QGraphicsProxyWidget.
                # Der Klick wird deshalb ueber Viewport und Szene in die
                # lokalen Kartenkoordinaten umgerechnet.
                if view is not None:
                    viewport_point = view.viewport().mapFromGlobal(
                        event.globalPosition().toPoint()
                    )
                    scene_point = view.mapToScene(viewport_point)
                    local_point = self.mapFromScene(scene_point)
                else:
                    local_point = QPointF(card.mapFromGlobal(
                        event.globalPosition().toPoint()
                    ))
                if card.clear_focus_at(QPointF(local_point)):
                    return True
                if card.pin_neuron_at(QPointF(local_point)):
                    return True
        if not self.editable:
            return False
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.RightButton
        ):
            self.preserve_selection_for_context_menu()
            return False
        if event.type() == QEvent.Type.ContextMenu:
            self.restore_context_selection()
            dialog = self.history_dialog()
            if dialog is not None:
                dialog.show_card_context_menu(self, event.globalPos())
            return True
        if (
            self.card_role == "comment"
            and event.type() == QEvent.Type.MouseButtonDblClick
            and event.button() == Qt.MouseButton.LeftButton
        ):
            dialog = self.history_dialog()
            if dialog is not None:
                dialog.edit_comment(self)
            return True
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            if self.locked:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.setSelected(not self.isSelected())
                else:
                    if not self.isSelected() and self.scene() is not None:
                        self.scene().clearSelection()
                    self.setSelected(True)
                return True
            scene_position = self.scene_position_from_mouse_event(event)
            if self.resize_handle_rect().contains(self.mapFromScene(scene_position)):
                self.begin_card_resize(scene_position, event.modifiers())
                self.mouse_grabber = watched
                watched.grabMouse()
                return True
            if not self.begin_card_drag(
                scene_position, event.modifiers()
            ):
                return True
            self.mouse_grabber = watched
            watched.grabMouse()
            return True
        if event.type() == QEvent.Type.MouseMove and self.resizing:
            self.resize_selected_cards(self.scene_position_from_mouse_event(event))
            return True
        if event.type() == QEvent.Type.MouseMove and self.dragging:
            self.move_selected_cards(self.scene_position_from_mouse_event(event))
            return True
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and (self.dragging or self.resizing)
        ):
            was_resizing = self.resizing
            if self.mouse_grabber is not None:
                self.mouse_grabber.releaseMouse()
                self.mouse_grabber = None
            if was_resizing:
                self.finish_card_resize()
            else:
                self.finish_card_drag()
                dialog = self.history_dialog()
                if dialog is not None and hasattr(dialog, "finish_history_action"):
                    dialog.finish_history_action()
            return True
        return False

    def mousePressEvent(self, event):
        views = self.scene().views() if self.scene() is not None else []
        view = views[0] if views else None
        if (
            view is not None
            and event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
            and view.begin_alt_pan(event.screenPos())
        ):
            event.accept()
            return
        if self.editable and not self.locked and event.button() == Qt.MouseButton.LeftButton:
            if self.resize_handle_rect().contains(event.pos()):
                self.begin_card_resize(event.scenePos(), event.modifiers())
                event.accept()
                return
            self.begin_card_drag(event.scenePos(), event.modifiers())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        views = self.scene().views() if self.scene() is not None else []
        view = views[0] if views else None
        if view is not None and view.alt_panning:
            view.continue_alt_pan(event.screenPos())
            event.accept()
            return
        if self.resizing:
            self.resize_selected_cards(event.scenePos())
            event.accept()
            return
        if self.dragging:
            self.move_selected_cards(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        views = self.scene().views() if self.scene() is not None else []
        view = views[0] if views else None
        if view is not None and view.end_alt_pan():
            event.accept()
            return
        if self.resizing:
            self.finish_card_resize()
            event.accept()
            return
        if self.dragging:
            self.finish_card_drag()
            dialog = self.history_dialog()
            if dialog is not None and hasattr(dialog, "finish_history_action"):
                dialog.finish_history_action()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class GraphicalExperimentDialog(QDialog):
    """Projektbezogenes grafisches Experiment mit frei platzierbaren Bedienkarten."""

    CANVAS_WIDTH = 1200.0
    CANVAS_HEIGHT = 700.0
    COMPACT_IO_CARD_WIDTH = 170.0
    COMPACT_IO_CARD_HEIGHT = 50.0
    COMPACT_IO_COLUMN_GAP = 12.0
    COMPACT_IO_ROW_GAP = 10.0
    COMPACT_IO_SECTION_GAP = 30.0
    SHAPE_CLIPBOARD_MIME = "application/x-neuronnetz-design-shapes+json"

    def __init__(
        self,
        network,
        input_columns,
        output_columns,
        records=None,
        file_path=None,
        input_array=None,
        color_settings=None,
        initial_input_values=None,
        language_manager=None,
        parent=None,
        uncertainty_settings=None,
    ):
        super().__init__(parent)
        self.network = network
        self.input_columns = list(input_columns or [])
        self.output_columns = list(output_columns or [])
        self.records = list(records or [])
        self.file_path = file_path
        self.input_array = input_array if isinstance(input_array, dict) else None
        self.color_settings = dict(color_settings or {})
        self.initial_input_values = dict(initial_input_values or {})
        self.uncertainty_settings = normalize_limits(uncertainty_settings)
        self.language = language_manager
        self.input_cards = []
        self.output_cards = []
        self.comment_cards = []
        self.curves = CurveController(self, CharacteristicCard, MovableCardProxy, calculate_forward_snapshot)
        self.shape_items = []
        self.input_array_card = None
        self.network_view_card = None
        self.background_item = None
        self.background_relative_path = ""
        self.background_color = "#f5f5f5"
        self.grid_enabled = False
        self.grid_snap_enabled = False
        self.grid_spacing = 20
        self.grid_item = None
        self.edit_mode = True
        self.saved_state = None
        self.input_state_dirty = False
        self.undo_stack = []
        self.redo_stack = []
        self.active_history_state = None
        self.restoring_history = False
        self.nudge_history_active = False
        self.nudge_handles_hidden = False
        self.last_selected_card = None
        self.placement_items = []
        self.placement_start_positions = {}
        self.placement_origin = QPointF()
        self.placement_repeat_factory = None
        self.active_input_sliders = 0
        self.drag_calculation_pending = False
        self.forward_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="NeuronNetzForward",
        )
        self.forward_bridge = ForwardCalculationBridge(self)
        self.forward_bridge.completed.connect(self.forward_calculation_finished)
        self.forward_calculation_running = False
        self.pending_forward_request = None
        self.forward_request_number = 0
        self.forward_specification = self.create_forward_specification()
        # Eingabeelemente müssen ihren sichtbaren Zustand sofort ändern
        # können. Die etwas aufwendigere Vorwärtsberechnung wird deshalb
        # gesammelt nach dem aktuellen Maus-/Tastaturereignis ausgeführt.
        self.calculation_timer = QTimer(self)
        self.calculation_timer.setSingleShot(True)
        self.calculation_timer.setInterval(16)
        self.calculation_timer.timeout.connect(self.perform_calculation)
        # Während ein Regler gezogen wird, wird höchstens etwa 60-mal pro
        # Sekunde mit dem jeweils neuesten Wert gerechnet. Das hält sowohl die
        # Mausbedienung als auch die Netzwerkanzeige sichtbar flüssig.
        self.drag_calculation_timer = QTimer(self)
        self.drag_calculation_timer.setInterval(16)
        self.drag_calculation_timer.timeout.connect(
            self.perform_pending_drag_calculation
        )
        self.project_directory = self.determine_project_directory()
        self.layout_file = (
            self.project_directory / "grafisches_experiment" / "layout.json"
            if self.project_directory is not None
            else None
        )
        self.project_window_size = None

        self.setWindowTitle(self.tr("Anwendungsansicht", "Application View"))
        self.resize(1100, 720)
        main_layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel(self.tr("Modus:", "Mode:"), self))
        self.mode_combo = QComboBox(self)
        self.mode_combo.addItem(self.tr("Bearbeiten", "Edit"), "edit")
        self.mode_combo.addItem(self.tr("Erproben", "Explore"), "experiment")
        self.mode_combo.currentIndexChanged.connect(self.change_mode)
        toolbar.addWidget(self.mode_combo)

        self.undo_button = QPushButton(self.tr("Rückgängig", "Undo"), self)
        self.redo_button = QPushButton(self.tr("Wiederholen", "Redo"), self)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo_design_change)
        self.redo_button.clicked.connect(self.redo_design_change)

        self.load_image_button = QPushButton(
            self.tr("Grafik laden…", "Load image…"), self
        )
        self.show_all_button = QPushButton(
            self.tr("Alles zeigen", "Show all"), self
        )
        self.view_info_button = QPushButton("i", self)
        self.view_info_button.setFixedSize(24, 24)
        self.view_info_button.setToolTip(
            self.tr(
                "Zweck der Anwendungsansicht erklären",
                "Explain the purpose of the application view",
            )
        )
        self.view_info_button.clicked.connect(self.show_view_information)
        self.description_button = QPushButton(
            self.language.text("forward.button.description")
            if self.language is not None
            else self.tr("Beschreibung…", "Description…"),
            self,
        )
        self.test_results_button = QPushButton(
            self.language.text("forward.button.test_data")
            if self.language is not None
            else self.tr("Testauswertung…", "Test Results…"),
            self,
        )
        self.description_button.clicked.connect(self.open_project_description)
        self.test_results_button.clicked.connect(self.open_test_results)
        self.background_color_button = QPushButton(
            self.tr("Hintergrundfarbe…", "Background color…"), self
        )
        self.align_button = QPushButton(self.tr("Ausrichten…", "Align…"), self)
        self.align_menu = QMenu(self.align_button)
        self.align_menu.setTitle(self.tr("Ausrichten", "Align"))
        self.align_menu.setIcon(ToolbarIcons.icon("align"))
        self.align_left_action = self.align_menu.addAction(
            self.tr("Linksbündig", "Align left")
        )
        self.align_left_action.setIcon(ToolbarIcons.icon("align_left"))
        self.align_right_action = self.align_menu.addAction(
            self.tr("Rechtsbündig", "Align right")
        )
        self.align_right_action.setIcon(ToolbarIcons.icon("align_right"))
        self.align_top_action = self.align_menu.addAction(
            self.tr("Oben ausrichten", "Align top")
        )
        self.align_top_action.setIcon(ToolbarIcons.icon("align_top"))
        self.align_bottom_action = self.align_menu.addAction(
            self.tr("Unten ausrichten", "Align bottom")
        )
        self.align_bottom_action.setIcon(ToolbarIcons.icon("align_bottom"))
        self.align_menu.addSeparator()
        self.distribute_horizontal_action = self.align_menu.addAction(
            self.tr("Horizontal gleichmäßig verteilen", "Distribute horizontally")
        )
        self.distribute_horizontal_action.setIcon(
            ToolbarIcons.icon("distribute_horizontal")
        )
        self.distribute_vertical_action = self.align_menu.addAction(
            self.tr("Vertikal gleichmäßig verteilen", "Distribute vertically")
        )
        self.distribute_vertical_action.setIcon(
            ToolbarIcons.icon("distribute_vertical")
        )
        self.align_button.setMenu(self.align_menu)
        self.align_button.setEnabled(False)
        self.size_button = QPushButton(self.tr("Größe…", "Size…"), self)
        self.size_menu = QMenu(self.size_button)
        self.size_menu.setTitle(self.tr("Größe", "Size"))
        self.size_menu.setIcon(ToolbarIcons.icon("equal_size"))
        self.equal_width_action = self.size_menu.addAction(
            self.tr("Gleiche Breite", "Same width")
        )
        self.equal_width_action.setIcon(ToolbarIcons.icon("equal_width"))
        self.equal_height_action = self.size_menu.addAction(
            self.tr("Gleiche Höhe", "Same height")
        )
        self.equal_height_action.setIcon(ToolbarIcons.icon("equal_height"))
        self.equal_size_action = self.size_menu.addAction(
            self.tr("Gleiche Größe", "Same size")
        )
        self.equal_size_action.setIcon(ToolbarIcons.icon("equal_size"))
        self.size_menu.addSeparator()
        self.size_all_inputs_action = self.size_menu.addAction(
            self.tr("Größe auf alle Inputs übertragen", "Apply size to all inputs")
        )
        self.size_all_inputs_action.setIcon(ToolbarIcons.icon("input"))
        self.size_all_outputs_action = self.size_menu.addAction(
            self.tr("Größe auf alle Outputs übertragen", "Apply size to all outputs")
        )
        self.size_all_outputs_action.setIcon(ToolbarIcons.icon("output"))
        self.size_button.setMenu(self.size_menu)
        self.size_button.setEnabled(False)
        self.card_color_button = QPushButton(
            self.tr("Kachelfarbe…", "Card color…"), self
        )
        self.card_color_menu = QMenu(self.card_color_button)
        self.card_color_menu.setTitle(self.tr("Kachelfarbe", "Card color"))
        self.card_color_menu.setIcon(ToolbarIcons.icon("color"))
        self.choose_card_color_action = self.card_color_menu.addAction(
            self.tr("Farbe wählen…", "Choose color…")
        )
        self.choose_card_color_action.setIcon(ToolbarIcons.icon("color"))
        self.reset_card_color_action = self.card_color_menu.addAction(
            self.tr("Standardfarbe (Weiß)", "Default color (white)")
        )
        self.reset_card_color_action.setIcon(ToolbarIcons.icon("color"))
        self.card_color_button.setMenu(self.card_color_menu)
        self.card_color_button.setEnabled(False)
        self.choose_card_color_action.triggered.connect(
            lambda _checked=False: self.choose_card_color()
        )
        self.reset_card_color_action.triggered.connect(
            lambda: self.apply_card_color("#ffffff")
        )
        self.default_layout_button = QPushButton(
            self.tr("Standardlayout", "Default layout"), self
        )
        self.add_comment_button = QPushButton(
            self.tr("Kommentar hinzufügen", "Add comment"), self
        )
        self.add_comment_button.clicked.connect(self.add_comment_at_visible_center)
        self.default_layout_button.clicked.connect(self.reset_to_default_layout)
        self.align_left_action.triggered.connect(lambda: self.align_selected("left"))
        self.align_right_action.triggered.connect(lambda: self.align_selected("right"))
        self.align_top_action.triggered.connect(lambda: self.align_selected("top"))
        self.align_bottom_action.triggered.connect(lambda: self.align_selected("bottom"))
        self.distribute_horizontal_action.triggered.connect(
            lambda: self.distribute_selected("horizontal")
        )
        self.distribute_vertical_action.triggered.connect(
            lambda: self.distribute_selected("vertical")
        )
        self.equal_width_action.triggered.connect(
            lambda: self.equalize_selected_size("width")
        )
        self.equal_height_action.triggered.connect(
            lambda: self.equalize_selected_size("height")
        )
        self.equal_size_action.triggered.connect(
            lambda: self.equalize_selected_size("both")
        )
        self.size_all_inputs_action.triggered.connect(
            lambda: self.apply_reference_size_to_role("input")
        )
        self.size_all_outputs_action.triggered.connect(
            lambda: self.apply_reference_size_to_role("output")
        )
        self.load_image_button.clicked.connect(self.load_background_image)
        self.background_color_button.clicked.connect(self.choose_background_color)
        self.show_all_button.clicked.connect(self.view_show_all)
        self.edit_menu = QMenu(self)
        self.undo_action = self.edit_menu.addAction(self.tr("Rückgängig", "Undo"))
        self.undo_action.setIcon(ToolbarIcons.icon("undo"))
        self.redo_action = self.edit_menu.addAction(self.tr("Wiederholen", "Redo"))
        self.redo_action.setIcon(ToolbarIcons.icon("redo"))
        self.edit_menu.addSeparator()
        self.copy_shapes_action = self.edit_menu.addAction(
            self.tr("Kopieren", "Copy")
        )
        self.copy_shapes_action.setIcon(ToolbarIcons.icon("copy"))
        self.copy_shapes_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_shapes_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.undo_action.triggered.connect(self.undo_design_change)
        self.redo_action.triggered.connect(self.redo_design_change)
        self.copy_shapes_action.triggered.connect(self.copy_selected_shapes)
        self.design_menu = QMenu(self)
        self.add_elements_menu = self.design_menu.addMenu(
            self.tr("Element hinzufügen", "Add element")
        )
        self.input_elements_menu = self.add_elements_menu.addMenu(
            self.tr("Eingang", "Input")
        )
        self.input_elements_menu.setIcon(ToolbarIcons.icon("input"))
        self.output_elements_menu = self.add_elements_menu.addMenu(
            self.tr("Ausgang", "Output")
        )
        self.output_elements_menu.setIcon(ToolbarIcons.icon("output"))
        self.add_all_io_action = self.add_elements_menu.addAction(
            self.tr(
                "Alle Ein- und Ausgänge hinzufügen",
                "Add all inputs and outputs",
            )
        )
        self.add_all_io_action.setIcon(ToolbarIcons.icon("add_all"))
        self.array_element_action = self.add_elements_menu.addAction(
            self.tr("Binäres Eingabe-Array", "Binary input array")
        )
        self.array_element_action.setIcon(ToolbarIcons.icon("binary_array"))
        self.network_view_action = self.add_elements_menu.addAction(
            self.tr("Vereinfachte Netzwerkansicht", "Simplified network view")
        )
        self.network_view_action.setIcon(ToolbarIcons.icon("network_layout"))
        self.characteristic_action = self.add_elements_menu.addAction(
            self.tr("Netzkennlinie", "Network characteristic")
        )
        self.characteristic_action.triggered.connect(self.curves.add)
        self.add_elements_menu.addSeparator()
        self.add_comment_design_action = self.add_elements_menu.addAction(
            self.tr("Kommentar", "Comment")
        )
        self.add_comment_design_action.setIcon(ToolbarIcons.icon("comment"))
        self.load_image_action = self.add_elements_menu.addAction(
            self.tr("Grafik laden…", "Load image…")
        )
        self.load_image_action.setIcon(ToolbarIcons.icon("project_image"))
        self.add_icon_action = self.add_elements_menu.addAction(
            self.tr("Symbol…", "Symbol…")
        )
        self.add_icon_action.setIcon(standard_design_icon_preview("arrow", size=24))
        self.shape_elements_menu = self.add_elements_menu.addMenu(
            self.tr("Grafische Form", "Graphic shape")
        )
        self.shape_elements_menu.setIcon(ToolbarIcons.icon("rectangle"))
        self.add_line_action = self.shape_elements_menu.addAction(
            self.tr("Linie", "Line")
        )
        self.add_line_action.setIcon(ToolbarIcons.icon("line"))
        self.add_curve_action = self.shape_elements_menu.addAction(
            self.tr("Kurvenverbindung", "Curved connection")
        )
        self.add_curve_action.setIcon(ToolbarIcons.icon("curve"))
        self.add_rectangle_action = self.shape_elements_menu.addAction(
            self.tr("Rechteck", "Rectangle")
        )
        self.add_rectangle_action.setIcon(ToolbarIcons.icon("rectangle"))
        self.add_ellipse_action = self.shape_elements_menu.addAction(
            self.tr("Kreis / Ellipse", "Circle / ellipse")
        )
        self.add_ellipse_action.setIcon(ToolbarIcons.icon("ellipse"))
        self.paste_clipboard_action = self.add_elements_menu.addAction(
            self.tr("Einfügen", "Paste")
        )
        self.paste_clipboard_action.setIcon(ToolbarIcons.icon("paste"))
        self.paste_clipboard_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_clipboard_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.design_menu.addSeparator()
        self.background_color_action = self.design_menu.addAction(
            self.tr("Hintergrundfarbe…", "Background color…")
        )
        self.background_color_action.setIcon(ToolbarIcons.icon("color"))
        self.design_menu.addMenu(self.card_color_menu)
        self.grid_visible_action = self.design_menu.addAction(
            self.tr("Raster anzeigen", "Show grid")
        )
        self.grid_visible_action.setIcon(ToolbarIcons.icon("grid"))
        self.grid_visible_action.setCheckable(True)
        self.grid_snap_action = self.design_menu.addAction(
            self.tr("Am Raster einrasten", "Snap to grid")
        )
        self.grid_snap_action.setIcon(ToolbarIcons.icon("grid"))
        self.grid_snap_action.setCheckable(True)
        self.grid_snap_action.setToolTip(
            self.tr(
                "Wirksam, wenn das Raster angezeigt wird.",
                "Active while the grid is visible.",
            )
        )
        self.grid_spacing_action = self.design_menu.addAction(
            self.tr("Rasterabstand…", "Grid spacing…")
        )
        self.grid_spacing_action.setIcon(ToolbarIcons.icon("grid_spacing"))
        self.design_menu.addSeparator()
        self.default_layout_action = self.design_menu.addAction(
            self.tr("Standardlayout", "Default layout")
        )
        self.default_layout_action.setIcon(ToolbarIcons.icon("network_layout"))
        self.load_image_action.triggered.connect(
            self.load_background_image_for_placement
        )
        self.background_color_action.triggered.connect(self.choose_background_color)
        self.add_comment_design_action.triggered.connect(
            self.request_comment_placement
        )
        self.add_icon_action.triggered.connect(
            lambda _checked=False: self.choose_standard_icon()
        )
        self.add_line_action.triggered.connect(
            lambda: self.request_shape_placement("line")
        )
        self.add_curve_action.triggered.connect(
            lambda: self.request_shape_placement("curve")
        )
        self.add_rectangle_action.triggered.connect(
            lambda: self.request_shape_placement("rectangle")
        )
        self.add_ellipse_action.triggered.connect(
            lambda: self.request_shape_placement("ellipse")
        )
        self.paste_clipboard_action.triggered.connect(
            lambda: self.paste_clipboard_content()
        )
        self.add_all_io_action.triggered.connect(
            self.request_all_input_output_placement
        )
        self.array_element_action.triggered.connect(
            lambda: self.request_existing_element_placement(self.input_array_card)
        )
        self.network_view_action.triggered.connect(
            lambda: self.request_existing_element_placement(self.network_view_card)
        )
        self.grid_visible_action.toggled.connect(self.set_grid_enabled)
        self.grid_snap_action.toggled.connect(self.set_grid_snap_enabled)
        self.grid_spacing_action.triggered.connect(self.choose_grid_spacing)
        self.default_layout_action.triggered.connect(self.reset_to_default_layout)
        self.arrange_menu = QMenu(self)
        self.arrange_menu.setIcon(ToolbarIcons.icon("align"))
        self.arrange_menu.addMenu(self.align_menu)
        self.arrange_menu.addMenu(self.size_menu)
        self.arrange_grid_action = self.arrange_menu.addAction(
            self.tr("Als Raster anordnen", "Arrange as grid")
        )
        self.arrange_grid_action.setIcon(ToolbarIcons.icon("grid"))
        self.arrange_grid_action.triggered.connect(self.arrange_selected_as_grid)

        for obsolete_button in (
            self.undo_button,
            self.redo_button,
            self.load_image_button,
            self.background_color_button,
            self.align_button,
            self.size_button,
            self.card_color_button,
            self.add_comment_button,
            self.default_layout_button,
        ):
            obsolete_button.setVisible(False)
        self.menu_container = QWidget(self)
        menu_container_layout = QHBoxLayout(self.menu_container)
        menu_container_layout.setContentsMargins(0, 0, 0, 0)
        menu_container_layout.setSpacing(0)
        self.menu_bar = QMenuBar(self.menu_container)
        self.menu_bar.setNativeMenuBar(False)
        self.top_edit_menu = self.menu_bar.addMenu(
            self.tr("Bearbeiten", "Edit")
        )
        self.top_edit_menu.addAction(self.undo_action)
        self.top_edit_menu.addAction(self.redo_action)
        self.top_edit_menu.addSeparator()
        self.top_edit_menu.addAction(self.copy_shapes_action)
        self.top_edit_menu.aboutToShow.connect(self.update_selection_actions)

        self.add_elements_menu.setTitle(self.tr("Elemente", "Elements"))
        self.top_add_menu = self.menu_bar.addMenu(self.add_elements_menu)
        self.add_elements_menu.setToolTipsVisible(True)
        self.input_elements_menu.setToolTipsVisible(True)
        self.output_elements_menu.setToolTipsVisible(True)
        self.shape_elements_menu.setToolTipsVisible(True)

        self.top_design_menu = self.menu_bar.addMenu(
            self.tr("Gestaltung", "Design")
        )
        self.top_design_menu.addAction(self.background_color_action)
        self.top_design_menu.addMenu(self.card_color_menu)
        self.top_design_menu.addAction(self.grid_visible_action)
        self.top_design_menu.addAction(self.grid_snap_action)
        self.top_design_menu.addAction(self.grid_spacing_action)
        self.top_design_menu.addSeparator()
        self.top_design_menu.addAction(self.default_layout_action)

        self.top_arrange_menu = self.menu_bar.addMenu(
            self.tr("Anordnen", "Arrange")
        )
        self.top_arrange_menu.addMenu(self.align_menu)
        self.top_arrange_menu.addMenu(self.size_menu)
        self.top_arrange_menu.addAction(self.arrange_grid_action)
        self.menu_bar.setMinimumWidth(360)
        self.menu_bar.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        menu_container_layout.addWidget(self.menu_bar)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.menu_container)
        toolbar.addStretch(1)
        toolbar.addWidget(self.view_info_button)
        toolbar.addWidget(self.description_button)
        toolbar.addWidget(self.test_results_button)
        toolbar.addWidget(self.show_all_button)
        main_layout.addLayout(toolbar)
        layout_margins = main_layout.contentsMargins()
        self.setMinimumWidth(
            toolbar.minimumSize().width()
            + layout_margins.left()
            + layout_margins.right()
        )

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0.0, 0.0, self.CANVAS_WIDTH, self.CANVAS_HEIGHT)
        self.scene.setBackgroundBrush(QColor("#f5f5f5"))
        self.grid_item = DesignGridItem(self.scene.sceneRect(), self.grid_spacing)
        self.grid_item.setVisible(False)
        self.scene.addItem(self.grid_item)
        self.view = ExperimentCanvasView(self.scene, self)
        self.view.zoom_changed.connect(self.update_zoom_label)
        self.scene.selectionChanged.connect(self.update_selection_actions)
        self.scene.selectionChanged.connect(self.update_selection_status)
        self.view.setFrameShape(QFrame.Shape.StyledPanel)
        main_layout.addWidget(self.view, 1)

        bottom = QHBoxLayout()
        self.status_label = QLabel(
            self.project_status_text(),
            self,
        )
        bottom.addWidget(self.status_label, 1)
        self.zoom_label = QLabel(self.tr("Zoom: 100 %", "Zoom: 100%"), self)
        bottom.addWidget(self.zoom_label)
        self.save_button = QPushButton(self.tr("Speichern", "Save"), self)
        self.save_button.clicked.connect(self.save_layout)
        bottom.addWidget(self.save_button)
        close_button = QPushButton(self.tr("Schließen", "Close"), self)
        close_button.clicked.connect(self.accept)
        bottom.addWidget(close_button)
        main_layout.addLayout(bottom)

        self.create_cards()
        self.create_input_array_card()
        self.create_network_view_card()
        self.populate_element_menus()
        if self.layout_file is None or not self.layout_file.exists():
            for proxy, _controls, _mapping in self.input_cards + self.output_cards:
                proxy.setVisible(False)
            if self.input_array_card is not None:
                self.input_array_card.setVisible(False)
            if self.network_view_card is not None:
                self.network_view_card.setVisible(False)
        self.default_history_state = self.capture_history_state()
        QApplication.clipboard().dataChanged.connect(self.update_selection_actions)
        self.save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self.save_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.save_shortcut.activated.connect(self.save_layout)
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.undo_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.undo_shortcut.activated.connect(self.undo_design_change)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.redo_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.redo_shortcut.activated.connect(self.redo_design_change)
        self.delete_image_shortcut = QShortcut(QKeySequence("Delete"), self)
        self.delete_image_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.delete_image_shortcut.activated.connect(self.delete_selected_image)
        self.nudge_timer = QTimer(self)
        self.nudge_timer.setSingleShot(True)
        self.nudge_timer.setInterval(1000)
        self.nudge_timer.timeout.connect(self.finish_nudge_history)
        self.nudge_shortcuts = []
        for key, dx, dy in (
            ("Left", -1.0, 0.0),
            ("Right", 1.0, 0.0),
            ("Up", 0.0, -1.0),
            ("Down", 0.0, 1.0),
            ("Shift+Left", -10.0, 0.0),
            ("Shift+Right", 10.0, 0.0),
            ("Shift+Up", 0.0, -10.0),
            ("Shift+Down", 0.0, 10.0),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(
                lambda horizontal=dx, vertical=dy:
                self.nudge_selected(horizontal, vertical)
            )
            self.nudge_shortcuts.append(shortcut)
        self.load_layout()
        experiment_index = self.mode_combo.findData("experiment")
        if experiment_index >= 0:
            self.mode_combo.setCurrentIndex(experiment_index)
        self.change_mode()
        self.restore_window_geometry()
        self.saved_state = self.layout_state()
        self.input_state_dirty = False
        self.update_save_button()

    def tr(self, german, english):
        language = str(getattr(self.language, "current_language", "de")).lower()
        return german if language.startswith("de") else english

    def show_view_information(self):
        show_yellow_information_dialog(
            self,
            self.tr(
                "Wozu dient die Anwendungsansicht?",
                "What is the application view for?",
            ),
            self.tr(
                "Im Modus Erproben verändern Sie Eingabewerte und beobachten "
                "unmittelbar die Ausgaben des trainierten Netzwerks. Gewichte "
                "und Bias-Werte bleiben dabei unverändert.\n\n"
                "Im Modus Bearbeiten gestalten Sie das Bedienbild. Elemente "
                "lassen sich auswählen, mit Strg mehrfach markieren, verschieben "
                "und in der Größe ändern. Bearbeiten bietet Rückgängig, "
                "Wiederholen, Kopieren, Einfügen und Kommentare. Unter Gestaltung "
                "fügen Sie Ein- und Ausgaben, ein binäres Eingabe-Array, die "
                "vereinfachte Netzwerkansicht, Grafiken und Formen hinzu und "
                "ändern Hintergrund, Kachelfarben und Raster. Unter Anordnen "
                "richten Sie mehrere markierte Elemente aus, verteilen sie "
                "gleichmäßig oder vereinheitlichen ihre Größe.\n\n"
                "Speichern übernimmt die Gestaltung in das Projekt. Die "
                "Beschreibung erläutert die Anwendung; Testauswertung öffnet "
                "die Auswertung der zugeordneten Daten.",
                "In Explore mode, change input values and immediately observe "
                "the trained network's outputs. Weights and bias values remain "
                "unchanged.\n\n"
                "In Edit mode, design the control panel. Elements can be selected, "
                "multi-selected with Ctrl, moved, and resized. Edit provides Undo, "
                "Redo, Copy, Paste, and comments. Design adds inputs and outputs, "
                "a binary input array, the simplified network view, images, and "
                "shapes, and changes the background, card colors, and grid. "
                "Arrange aligns several selected elements, distributes them "
                "evenly, or makes their sizes equal.\n\n"
                "Save stores the design with the project. Description explains "
                "the application; Test Evaluation opens the evaluation of the "
                "assigned data.",
            ),
            self.tr("Schließen", "Close"),
        )

    def parent_with_method(self, method_name):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, method_name):
                return parent
            parent = parent.parent()
        return None

    def open_project_description(self):
        target = self.parent_with_method("show_description")
        if target is not None:
            target.show_description()
            return
        target = self.parent_with_method("open_project_description_dialog")
        if target is not None:
            target.open_project_description_dialog()

    def open_test_results(self):
        target = self.parent_with_method("show_test_results")
        if target is not None:
            target.show_test_results()
            self.calculate()
            return
        target = self.parent_with_method("test_network_with_training_data")
        if target is not None:
            target.test_network_with_training_data()
            self.calculate()

    def determine_project_directory(self):
        if not self.file_path:
            return None
        path = Path(self.file_path).resolve()
        parent = path.parent
        if parent.name.casefold() in {
            "trainingsdaten", "trainingdata", "training_data", "testdaten", "testdata"
        }:
            return parent.parent
        return parent

    def value_range(self, mapping):
        index = mapping.get("column_index")
        values = []
        if isinstance(index, int):
            for record in self.records:
                if isinstance(record, (list, tuple)) and index < len(record):
                    value = record[index]
                    if isinstance(value, (int, float)) and math.isfinite(value):
                        values.append(float(value))
        if values:
            minimum, maximum = min(values), max(values)
            if minimum < maximum:
                return minimum, maximum
        return 0.0, 1.0

    def display_range(self, mapping):
        """Verwendet den Rohwertbereich der Skalierung, sonst den Trainingsbereich."""

        calibration = TrainingDataIO.normalize_calibration(
            mapping.get("calibration")
        )
        if calibration["mode"] in ("minmax_0_1", "minmax_minus1_1"):
            return calibration["source_min"], calibration["source_max"]
        return self.value_range(mapping)

    def create_cards(self):
        for index, mapping in enumerate(self.input_columns):
            proxy, controls = self.create_input_card(mapping)
            proxy.setPos(25.0, 35.0 + index * 88.0)
            self.input_cards.append((proxy, controls, mapping))

        for index, mapping in enumerate(self.output_columns):
            proxy, controls = self.create_output_card(mapping)
            proxy.setPos(930.0, 35.0 + index * 82.0)
            self.output_cards.append((proxy, controls, mapping))

    def create_input_array_card(self):
        definition = self.input_array
        if not isinstance(definition, dict):
            return
        rows = int(definition.get("rows", 0) or 0)
        columns = int(definition.get("columns", 0) or 0)
        order = definition.get("column_indices")
        if rows < 1 or columns < 1 or not isinstance(order, list):
            return
        by_column = {
            mapping.get("column_index"): controls
            for _proxy, controls, mapping in self.input_cards
            if mapping.get("data_type") == "binary"
        }
        ordered_controls = [by_column.get(index) for index in order]
        if len(ordered_controls) != rows * columns or any(
            controls is None for controls in ordered_controls
        ):
            return
        card = BinaryArrayCard(
            rows, columns, ordered_controls, self.input_state_changed,
            self.color_settings
        )
        card.set_title(self.tr("Eingabemuster", "Input pattern"))
        proxy = MovableCardProxy("input_array")
        proxy.setWidget(card)
        self.scene.addItem(proxy)
        proxy.setZValue(10.0)
        proxy.configure_card_size(
            max(140.0, columns * 34.0),
            max(145.0, rows * 34.0 + 28.0),
        )
        proxy.setPos(420.0, 80.0)
        self.input_array_card = proxy

    def create_network_view_card(self):
        if self.network is None or not self.network.get_neurons():
            return
        card = SimplifiedNetworkCard(
            self.network,
            self.tr,
            color_settings=self.color_settings,
            input_mappings=self.input_columns,
            output_mappings=self.output_columns,
        )
        proxy = MovableCardProxy("network_view")
        proxy.setWidget(card)
        self.scene.addItem(proxy)
        proxy.setZValue(10.0)
        proxy.configure_card_size(240.0, 170.0)
        proxy.set_card_size(430.0, 300.0)
        proxy.setPos(385.0, 180.0)
        self.network_view_card = proxy

    def populate_element_menus(self):
        self.input_element_actions = {}
        self.output_element_actions = {}
        for proxy, _controls, mapping in self.input_cards:
            name = str(mapping.get("name") or mapping["neuron"].name)
            action = self.input_elements_menu.addAction(name)
            action.setIcon(ToolbarIcons.icon("input"))
            action.triggered.connect(
                lambda _checked=False, target=proxy:
                self.request_existing_element_placement(target)
            )
            self.input_element_actions[proxy] = action
        for proxy, _controls, mapping in self.output_cards:
            name = str(mapping.get("name") or mapping["neuron"].name)
            action = self.output_elements_menu.addAction(name)
            action.setIcon(ToolbarIcons.icon("output"))
            action.triggered.connect(
                lambda _checked=False, target=proxy:
                self.request_existing_element_placement(target)
            )
            self.output_element_actions[proxy] = action
        self.update_element_actions()

    def update_element_actions(self):
        for proxy, action in {
            **getattr(self, "input_element_actions", {}),
            **getattr(self, "output_element_actions", {}),
        }.items():
            available = self.edit_mode and not proxy.isVisible()
            action.setEnabled(available)
            action.setToolTip(
                "" if available else self.tr(
                    "Dieses Element ist bereits sichtbar oder der Bearbeitungsmodus ist nicht aktiv.",
                    "This element is already visible or Edit mode is not active.",
                )
            )
        self.array_element_action.setEnabled(
            self.edit_mode
            and self.input_array_card is not None
            and not self.input_array_card.isVisible()
        )
        self.network_view_action.setEnabled(
            self.edit_mode
            and self.network_view_card is not None
            and not self.network_view_card.isVisible()
        )
        self.add_all_io_action.setEnabled(
            self.edit_mode
            and any(
                not proxy.isVisible()
                for proxy, _controls, _mapping
                in self.input_cards + self.output_cards
            )
        )
        special_actions = (
            (self.array_element_action, self.input_array_card is not None),
            (self.network_view_action, self.network_view_card is not None),
        )
        for action, exists in special_actions:
            if not action.isEnabled():
                action.setToolTip(self.tr(
                    "Das Element ist nicht verfügbar, bereits sichtbar oder der Bearbeitungsmodus ist nicht aktiv.",
                    "The element is unavailable, already visible, or Edit mode is not active.",
                ))
            else:
                action.setToolTip("")
        if not self.add_all_io_action.isEnabled():
            self.add_all_io_action.setToolTip(self.tr(
                "Alle verfügbaren Ein- und Ausgänge sind bereits sichtbar oder der Bearbeitungsmodus ist nicht aktiv.",
                "All available inputs and outputs are already visible or Edit mode is not active.",
            ))
        else:
            self.add_all_io_action.setToolTip("")

    def edit_status_text(self):
        return self.project_status_text()

    def project_status_text(self):
        project_path = ""
        if self.file_path:
            project_path = str(Path(self.file_path).expanduser().resolve())
        return self.tr("Projekt: ", "Project: ") + (project_path or "–")

    def update_selection_status(self):
        """Zeigt nur bei aktiver Mehrfachauswahl deren Umfang statt des Projekts."""

        selected_count = len(self.selected_movable_items())
        if self.edit_mode and selected_count >= 2:
            self.status_label.setText(self.tr(
                f"{selected_count} Elemente ausgewählt",
                f"{selected_count} elements selected",
            ))
        else:
            self.status_label.setText(self.project_status_text())

    def placement_status_text(self, repeat_available=False):
        text = self.tr(
            "Position wählen · Linksklick: platzieren · Esc/Rechtsklick: abbrechen",
            "Choose position · Left click: place · Esc/right click: cancel",
        )
        if repeat_available:
            text += self.tr(
                " · Strg: mehrfach platzieren",
                " · Ctrl: place repeatedly",
            )
        return text

    def current_cursor_scene_position(self):
        viewport_position = self.view.viewport().mapFromGlobal(QCursor.pos())
        return self.view.mapToScene(viewport_position)

    def snapped_placement_position(self, position):
        point = QPointF(position)
        if self.grid_snap_active():
            spacing = float(self.grid_spacing)
            point.setX(round(point.x() / spacing) * spacing)
            point.setY(round(point.y() / spacing) * spacing)
        return point

    def start_element_placement(
        self,
        items,
        repeat_factory=None,
        scene_position=None,
    ):
        """Zeigt neue Elemente transparent am Mauszeiger, ohne sie fest abzulegen."""

        items = [item for item in items if item is not None and item.scene() is self.scene]
        if not self.edit_mode or not items:
            if self.active_history_state is not None:
                self.active_history_state = None
            return False
        self.scene.clearSelection()
        self.placement_items = items
        self.placement_start_positions = {
            item: QPointF(item.pos()) for item in items
        }
        bounds = QRectF()
        for item in items:
            item.setSelected(False)
            item.setOpacity(0.55)
            item_bounds = item.sceneBoundingRect()
            bounds = item_bounds if bounds.isNull() else bounds.united(item_bounds)
        self.placement_origin = bounds.center()
        self.placement_repeat_factory = repeat_factory
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.status_label.setText(
            self.placement_status_text(repeat_factory is not None)
        )
        self.update_element_placement(
            self.current_cursor_scene_position()
            if scene_position is None
            else scene_position
        )
        return True

    def update_element_placement(self, scene_position):
        if not self.placement_items:
            return
        delta = QPointF(scene_position) - self.placement_origin
        anchor = self.placement_items[0]
        anchor_start = self.placement_start_positions.get(anchor)
        if anchor_start is not None:
            anchor_target = anchor_start + delta
            delta += self.snapped_placement_position(anchor_target) - anchor_target
        for item, start in self.placement_start_positions.items():
            if item.scene() is self.scene:
                item.setPos(start + delta)

    def clear_element_placement_state(self):
        self.placement_items = []
        self.placement_start_positions = {}
        self.placement_origin = QPointF()
        self.placement_repeat_factory = None
        self.view.setDragMode(
            QGraphicsView.DragMode.RubberBandDrag
            if self.edit_mode
            else QGraphicsView.DragMode.NoDrag
        )
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def finish_element_placement(self, scene_position, modifiers):
        if not self.placement_items:
            return
        self.update_element_placement(scene_position)
        placed_items = list(self.placement_items)
        repeat_factory = self.placement_repeat_factory
        repeat_requested = bool(
            repeat_factory is not None
            and modifiers & Qt.KeyboardModifier.ControlModifier
        )
        for item in placed_items:
            item.setOpacity(1.0)
        self.clear_element_placement_state()
        self.scene.clearSelection()
        for item in placed_items:
            if item.scene() is self.scene:
                item.setSelected(True)
        self.finish_history_action()
        self.update_element_actions()
        self.status_label.setText(self.edit_status_text())
        if repeat_requested:
            QTimer.singleShot(0, repeat_factory)

    def cancel_element_placement(self):
        if not self.placement_items:
            return
        previous_state = self.active_history_state
        self.active_history_state = None
        self.clear_element_placement_state()
        if previous_state is not None:
            self.apply_history_state(previous_state)
        self.update_element_actions()
        self.status_label.setText(self.edit_status_text())

    def request_existing_element_placement(self, proxy):
        if not self.edit_mode or proxy is None or proxy.isVisible():
            return
        self.begin_history_action()
        proxy.setVisible(True)
        saved_position = getattr(proxy, "saved_design_position", None)
        if saved_position is not None:
            proxy.setPos(saved_position)
        self.start_element_placement([proxy])

    def request_all_input_output_placement(self):
        missing_inputs = [
            proxy for proxy, _controls, _mapping in self.input_cards
            if not proxy.isVisible()
        ]
        missing_outputs = [
            proxy for proxy, _controls, _mapping in self.output_cards
            if not proxy.isVisible()
        ]
        missing = missing_inputs + missing_outputs
        if not self.edit_mode or not missing:
            return
        self.begin_history_action()
        for proxy in missing:
            proxy.setVisible(True)
        self.arrange_compact_input_output_block(
            missing_inputs,
            missing_outputs,
        )
        self.start_element_placement(missing)

    def arrange_compact_input_output_block(self, inputs, outputs):
        """Ordnet gemeinsam eingefügte Ein- und Ausgänge zoomgerecht an."""

        card_width, card_height, column_gap, row_gap, section_gap = (
            self.compact_input_output_metrics_for_zoom()
        )

        for proxy in inputs + outputs:
            proxy.set_card_size(card_width, card_height)

        def arrange_section(items, start_x):
            current_y = 0.0
            for proxy in items:
                proxy.setPos(start_x, current_y)
                current_y += proxy.sceneBoundingRect().height() + row_gap

        arrange_section(inputs, 0.0)
        input_width = max(
            (proxy.sceneBoundingRect().width() for proxy in inputs),
            default=0.0,
        )
        output_start_x = (
            input_width + column_gap + section_gap
            if inputs and outputs
            else 0.0
        )
        arrange_section(outputs, output_start_x)

    def compact_input_output_metrics_for_zoom(self):
        """Liefert Szenenmaße, die am Bildschirm bei jedem Zoom kompakt bleiben."""

        view_scale = max(0.01, abs(float(self.view.transform().m11())))
        return (
            self.COMPACT_IO_CARD_WIDTH / view_scale,
            self.COMPACT_IO_CARD_HEIGHT / view_scale,
            self.COMPACT_IO_COLUMN_GAP / view_scale,
            self.COMPACT_IO_ROW_GAP / view_scale,
            self.COMPACT_IO_SECTION_GAP / view_scale,
        )

    def resize_input_output_cards_for_zoom(self, proxies):
        """Passt neu eingeblendete Ein-/Ausgangskarten an die aktuelle Ansicht an."""

        card_width, card_height, _column_gap, _row_gap, _section_gap = (
            self.compact_input_output_metrics_for_zoom()
        )
        for proxy in proxies:
            proxy.set_card_size(card_width, card_height)

    def request_shape_placement(self, shape_type):
        if not self.edit_mode:
            return
        self.begin_history_action()
        item = self.add_shape(
            shape_type, QPointF(), record_history=False
        )
        if item is None:
            self.active_history_state = None
            return
        self.start_element_placement(
            [item],
            lambda target=str(shape_type): self.request_shape_placement(target),
        )

    def choose_standard_icon(self, position=None):
        """Öffnet die Symbolbibliothek und startet anschließend die Platzierung."""

        if not self.edit_mode:
            return
        dialog = StandardIconDialog(self.tr, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_icon:
            return
        if position is None:
            self.request_icon_placement(dialog.selected_icon)
        else:
            self.add_shape(
                "icon",
                QPointF(position),
                {"icon_name": dialog.selected_icon},
            )

    def request_icon_placement(self, icon_name):
        if not self.edit_mode:
            return
        self.begin_history_action()
        item = self.add_shape(
            "icon",
            QPointF(),
            {"icon_name": str(icon_name)},
            record_history=False,
        )
        if item is None:
            self.active_history_state = None
            return
        self.start_element_placement(
            [item],
            lambda name=str(icon_name): self.request_icon_placement(name),
        )

    def request_comment_placement(self, data=None):
        if not self.edit_mode:
            return
        comment_data = dict(data) if isinstance(data, dict) else None
        if comment_data is None:
            dialog = CommentEditDialog(self.default_comment_data(), self.tr, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            comment_data = dialog.comment_data()
            if not comment_data["text"].strip():
                return
        self.begin_history_action()
        proxy = self.create_comment_card(comment_data)
        self.start_element_placement(
            [proxy],
            lambda values=dict(comment_data): self.request_comment_placement(values),
        )

    def add_existing_element(self, proxy, position=None):
        if not self.edit_mode or proxy is None or proxy.isVisible():
            return
        self.begin_history_action()
        proxy.setVisible(True)
        explicit_position = position is not None
        if position is None:
            position = getattr(proxy, "saved_design_position", None)
        if position is None:
            position = self.view.mapToScene(self.view.viewport().rect().center())
            explicit_position = True
        if explicit_position:
            position = self.snap_scene_position(position)
        proxy.setPos(position)
        self.scene.clearSelection()
        proxy.setSelected(True)
        self.finish_history_action()
        self.update_element_actions()

    def add_input_array_at_visible_center(self):
        self.add_existing_element(self.input_array_card)

    def add_network_view_at_visible_center(self):
        self.add_existing_element(self.network_view_card)

    def add_all_input_output_elements(self):
        """Ergänzt alle noch nicht sichtbaren Ein- und Ausgangskacheln."""
        if not self.edit_mode:
            return
        missing = [
            proxy
            for proxy, _controls, _mapping
            in self.input_cards + self.output_cards
            if not proxy.isVisible()
        ]
        if not missing:
            return
        self.begin_history_action()
        self.scene.clearSelection()
        self.resize_input_output_cards_for_zoom(missing)
        for proxy in missing:
            saved_position = getattr(proxy, "saved_design_position", None)
            if saved_position is not None:
                proxy.setPos(saved_position)
            proxy.setVisible(True)
            proxy.setSelected(True)
        self.finish_history_action()
        self.update_element_actions()

    def remove_elements_from_design(self, proxies, confirm=True):
        targets = [
            proxy for proxy in proxies
            if proxy.card_role in ("input", "output", "input_array", "network_view", "characteristic")
            and not proxy.locked
        ]
        if not targets:
            return
        if confirm:
            answer = QMessageBox.question(
                self,
                self.windowTitle(),
                self.tr(
                    "Ausgewählte Elemente aus der Gestaltung entfernen?\n\n"
                    "Die Neuronen und das Netzwerk bleiben unverändert.",
                    "Remove the selected elements from the design?\n\n"
                    "The neurons and the network remain unchanged.",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.begin_history_action()
        for proxy in targets:
            proxy.saved_design_position = QPointF(proxy.pos())
            proxy.setVisible(False)
            proxy.setSelected(False)
        self.finish_history_action()
        self.update_element_actions()

    def add_shape_at_visible_center(self, shape_type):
        position = self.view.mapToScene(self.view.viewport().rect().center())
        self.add_shape(shape_type, position)

    def add_shape(self, shape_type, position, data=None, record_history=True):
        if not self.edit_mode:
            return None
        if record_history and not self.restoring_history:
            self.begin_history_action()
        defaults = {
            "line": (180.0, 60.0),
            "curve": (180.0, 70.0),
            "rectangle": (180.0, 110.0),
            "ellipse": (130.0, 130.0),
            "icon": (90.0, 90.0),
        }
        width, height = defaults.get(str(shape_type), defaults["rectangle"])
        item = DesignShapeItem(shape_type, width, height, data)
        self.scene.addItem(item)
        if not isinstance(data, dict) or "layer" not in data:
            item.setZValue(self.next_design_layer())
        item.setPos(
            self.snap_scene_position(position)
            if record_history and not self.restoring_history
            else position
        )
        item.set_editable(self.edit_mode)
        self.shape_items.append(item)
        if record_history and not self.restoring_history:
            self.scene.clearSelection()
            item.setSelected(True)
            self.finish_history_action()
        return item

    def clear_shapes(self):
        for item in list(self.shape_items):
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        self.shape_items.clear()

    def restore_shapes(self, shapes):
        self.clear_shapes()
        for data in shapes if isinstance(shapes, list) else []:
            if not isinstance(data, dict):
                continue
            item = self.add_shape(
                data.get("type", "rectangle"),
                QPointF(float(data.get("x", 0.0)), float(data.get("y", 0.0))),
                data,
                record_history=False,
            )
            if item is not None:
                item.setSelected(False)

    def design_elements(self, visible_only=False):
        elements = list(self.shape_items) + list(self.comment_cards)
        elements.extend(self.curves.proxies)
        elements.extend(proxy for proxy, _controls, _mapping in self.input_cards)
        elements.extend(proxy for proxy, _controls, _mapping in self.output_cards)
        if self.input_array_card is not None:
            elements.append(self.input_array_card)
        if self.network_view_card is not None:
            elements.append(self.network_view_card)
        return [
            item for item in elements
            if item.scene() is self.scene
            and (not visible_only or item.isVisible())
        ]

    def next_design_layer(self):
        elements = self.design_elements()
        return max((item.zValue() for item in elements), default=0.0) + 1.0

    def bring_elements_to_front(self, elements):
        """Setzt Gestaltungselemente vor alle anderen, außer dem Hintergrund."""

        available = self.design_elements(visible_only=True)
        targets = [item for item in available if item in elements]
        if not targets:
            return
        targets.sort(key=lambda item: (item.zValue(), available.index(item)))
        highest_other = max(
            (item.zValue() for item in available if item not in targets),
            default=-1.0,
        )
        if all(
            item.zValue() > highest_other
            for item in targets
        ):
            return
        self.begin_history_action()
        layer = max((item.zValue() for item in available), default=0.0) + 1.0
        for item in targets:
            item.setZValue(layer)
            layer += 1.0
        self.finish_history_action()

    def send_elements_to_back(self, elements):
        """Setzt Gestaltungselemente hinter alle anderen, aber vor den Hintergrund."""

        available = self.design_elements(visible_only=True)
        targets = [item for item in available if item in elements]
        if not targets:
            return
        order_index = {item: index for index, item in enumerate(available)}
        ordered = sorted(
            available,
            key=lambda item: (item.zValue(), order_index[item]),
        )
        target_set = set(targets)
        targets = [item for item in ordered if item in target_set]
        others = [item for item in ordered if item not in target_set]
        if ordered[:len(targets)] == targets:
            return
        self.begin_history_action()
        # Nichtnegative Ebenen halten jedes Gestaltungselement zuverlässig
        # vor Raster (-90) und Hintergrundbild (-100).
        for layer, item in enumerate(targets + others):
            item.setZValue(float(layer))
        self.finish_history_action()

    def show_shape_context_menu(self, item, global_position):
        if not self.edit_mode or item not in self.shape_items:
            return
        if not item.isSelected():
            self.scene.clearSelection()
            item.setSelected(True)
        self.update_selection_actions()
        menu = QMenu(self)
        menu.addAction(self.copy_shapes_action)
        front_action = menu.addAction(
            self.tr("In den Vordergrund", "Bring to front")
        )
        front_action.setIcon(ToolbarIcons.icon("layer_front"))
        back_action = menu.addAction(
            self.tr("In den Hintergrund", "Send to back")
        )
        back_action.setIcon(ToolbarIcons.icon("layer_back"))
        lock_action, unlock_action = self.add_lock_actions(menu)
        menu.addSeparator()
        is_icon = item.shape_type == "icon"
        change_icon_action = None
        if is_icon:
            change_icon_action = menu.addAction(
                self.tr("Symbol ändern…", "Change symbol…")
            )
            change_icon_action.setIcon(
                standard_design_icon_preview(item.icon_name, size=24)
            )
        line_color_action = menu.addAction(
            self.tr("Symbolfarbe…", "Symbol color…")
            if is_icon
            else self.tr("Linienfarbe…", "Line color…")
        )
        line_color_action.setIcon(ToolbarIcons.icon("color"))
        line_width_action = None
        if not is_icon:
            line_width_action = menu.addAction(
                self.tr("Linienstärke…", "Line width…")
            )
            line_width_action.setIcon(ToolbarIcons.icon("line_width"))
        arrow_action = reverse_arrow_action = None
        if item.is_connector():
            menu.addSeparator()
            arrow_action = menu.addAction(
                self.tr("Pfeilspitze anzeigen", "Show arrowhead")
            )
            arrow_action.setIcon(ToolbarIcons.icon("arrow"))
            arrow_action.setCheckable(True)
            arrow_action.setChecked(item.arrow_enabled)
            reverse_arrow_action = menu.addAction(
                self.tr("Pfeilrichtung umkehren", "Reverse arrow direction")
            )
            reverse_arrow_action.setIcon(ToolbarIcons.icon("reverse"))
            reverse_arrow_action.setEnabled(item.arrow_enabled)
        rotate_left_action = rotate_right_action = rotation_action = None
        if is_icon:
            menu.addSeparator()
            rotate_left_action = menu.addAction(
                self.tr("90° nach links", "Rotate 90° left")
            )
            rotate_right_action = menu.addAction(
                self.tr("90° nach rechts", "Rotate 90° right")
            )
            rotation_action = menu.addAction(
                self.tr("Drehwinkel…", "Rotation angle…")
            )
        fill_color_action = transparent_action = None
        if not item.is_connector() and not is_icon:
            menu.addSeparator()
            fill_color_action = menu.addAction(self.tr("Füllfarbe…", "Fill color…"))
            fill_color_action.setIcon(ToolbarIcons.icon("color"))
            transparent_action = menu.addAction(self.tr("Transparent", "Transparent"))
            transparent_action.setIcon(ToolbarIcons.icon("transparent"))
            transparent_action.setCheckable(True)
            transparent_action.setChecked(item.fill_color is None)
        menu.addSeparator()
        delete_action = menu.addAction(
            self.tr("Symbol entfernen", "Remove symbol")
            if is_icon
            else self.tr("Form entfernen", "Remove shape")
        )
        delete_action.setIcon(ToolbarIcons.icon("delete"))
        selected_shapes = [
            shape for shape in self.scene.selectedItems()
            if isinstance(shape, DesignShapeItem)
        ] or [item]
        delete_action.setEnabled(any(not shape.locked for shape in selected_shapes))
        selected = menu.exec(global_position)
        targets = [
            shape for shape in self.scene.selectedItems()
            if isinstance(shape, DesignShapeItem)
        ] or [item]
        if selected == front_action:
            selected_elements = [
                element for element in self.design_elements(visible_only=True)
                if element.isSelected()
            ]
            self.bring_elements_to_front(selected_elements or targets)
        elif selected == back_action:
            selected_elements = [
                element for element in self.design_elements(visible_only=True)
                if element.isSelected()
            ]
            self.send_elements_to_back(selected_elements or targets)
        elif lock_action is not None and selected == lock_action:
            self.set_elements_locked(self.selected_movable_items(), True)
        elif unlock_action is not None and selected == unlock_action:
            self.set_elements_locked(self.selected_movable_items(), False)
        elif change_icon_action is not None and selected == change_icon_action:
            dialog = StandardIconDialog(
                self.tr,
                self,
                current_icon=item.icon_name,
            )
            if (
                dialog.exec() == QDialog.DialogCode.Accepted
                and dialog.selected_icon
            ):
                self.begin_history_action()
                for shape in targets:
                    if shape.shape_type == "icon":
                        shape.icon_name = dialog.selected_icon
                        shape.update()
                self.finish_history_action()
        elif selected == line_color_action:
            color = choose_color(
                item.line_color,
                self,
                self.tr("Symbolfarbe", "Symbol color")
                if is_icon
                else self.tr("Linienfarbe", "Line color"),
            )
            if color.isValid():
                self.begin_history_action()
                for shape in targets:
                    if not is_icon or shape.shape_type == "icon":
                        shape.line_color = QColor(color)
                        shape.update()
                self.finish_history_action()

        elif line_width_action is not None and selected == line_width_action:
            value, accepted = QInputDialog.getDouble(
                self, self.tr("Linienstärke", "Line width"),
                self.tr("Linienstärke in Pixel:", "Line width in pixels:"),
                item.line_width, 1.0, 20.0, 1,
            )
            if accepted:
                self.begin_history_action()
                for shape in targets:
                    shape.prepareGeometryChange()
                    shape.line_width = float(value)
                    shape.update()
            self.finish_history_action()
        elif rotate_left_action is not None and selected == rotate_left_action:
            self.begin_history_action()
            for shape in targets:
                if shape.shape_type == "icon":
                    shape.setRotation((shape.rotation() - 90.0) % 360.0)
            self.finish_history_action()
        elif rotate_right_action is not None and selected == rotate_right_action:
            self.begin_history_action()
            for shape in targets:
                if shape.shape_type == "icon":
                    shape.setRotation((shape.rotation() + 90.0) % 360.0)
            self.finish_history_action()
        elif rotation_action is not None and selected == rotation_action:
            value, accepted = QInputDialog.getDouble(
                self,
                self.tr("Drehwinkel", "Rotation angle"),
                self.tr("Winkel in Grad:", "Angle in degrees:"),
                item.rotation() % 360.0,
                0.0,
                359.9,
                1,
            )
            if accepted:
                self.begin_history_action()
                for shape in targets:
                    if shape.shape_type == "icon":
                        shape.setRotation(float(value) % 360.0)
                self.finish_history_action()
        elif arrow_action is not None and selected == arrow_action:
            self.begin_history_action()
            for shape in targets:
                if shape.is_connector():
                    shape.prepareGeometryChange()
                    shape.arrow_enabled = arrow_action.isChecked()
                    shape.update()
            self.finish_history_action()
        elif reverse_arrow_action is not None and selected == reverse_arrow_action:
            self.begin_history_action()
            for shape in targets:
                if shape.is_connector():
                    shape.prepareGeometryChange()
                    shape.line_start, shape.line_end = (
                        QPointF(shape.line_end),
                        QPointF(shape.line_start),
                    )
                    if shape.shape_type == "curve":
                        shape.control_point_1, shape.control_point_2 = (
                            QPointF(shape.control_point_2),
                            QPointF(shape.control_point_1),
                        )
                    shape.update()
            self.finish_history_action()
        elif fill_color_action is not None and selected == fill_color_action:
            initial = item.fill_color or QColor("#ffffff")
            color = choose_color(initial, self, self.tr("Füllfarbe", "Fill color"))
            if color.isValid():
                self.begin_history_action()
                for shape in targets:
                    if not shape.is_connector():
                        shape.fill_color = QColor(color)
                        shape.update()
                self.finish_history_action()
        elif transparent_action is not None and selected == transparent_action:
            self.begin_history_action()
            for shape in targets:
                if not shape.is_connector():
                    shape.fill_color = None
                    shape.update()
            self.finish_history_action()
        elif selected == delete_action:
            self.remove_shapes(targets)

    def show_background_context_menu(self, item, global_position):
        if (
            not self.edit_mode
            or self.background_item is None
            or item is not self.background_item
        ):
            return
        if not item.isSelected():
            self.scene.clearSelection()
            item.setSelected(True)
        self.update_selection_actions()
        menu = QMenu(self)
        lock_action, unlock_action = self.add_lock_actions(menu)
        menu.addSeparator()
        remove_action = menu.addAction(
            self.tr("Aus der Gestaltung entfernen", "Remove from design")
        )
        remove_action.setIcon(ToolbarIcons.icon("delete"))
        remove_action.setEnabled(not item.locked)
        selected = menu.exec(global_position)
        if lock_action is not None and selected == lock_action:
            self.set_elements_locked(self.selected_movable_items(), True)
        elif unlock_action is not None and selected == unlock_action:
            self.set_elements_locked(self.selected_movable_items(), False)
        elif selected == remove_action:
            self.remove_background_image()

    def remove_shapes(self, shapes, confirm=True):
        targets = [
            item for item in shapes
            if item in self.shape_items and not item.locked
        ]
        if not targets:
            return
        if confirm:
            answer = QMessageBox.question(
                self, self.windowTitle(),
                self.tr(
                    "Ausgewählte grafische Formen entfernen?",
                    "Remove the selected graphic shapes?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.begin_history_action()
        for item in targets:
            self.scene.removeItem(item)
            self.shape_items.remove(item)
        self.finish_history_action()

    @staticmethod
    def default_comment_data():
        return {
            "text": "",
            "font_size": 11,
            "bold": False,
            "alignment": "left",
            "font_color": "#111111",
            "frame": True,
        }

    def add_comment_at_visible_center(self):
        position = self.view.mapToScene(self.view.viewport().rect().center())
        self.add_comment(position)

    def add_comment(self, position):
        if not self.edit_mode:
            return
        dialog = CommentEditDialog(self.default_comment_data(), self.tr, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.comment_data()
        if not data["text"].strip():
            return
        self.begin_history_action()
        proxy = self.create_comment_card(data)
        proxy.setPos(self.snap_scene_position(position))
        self.scene.clearSelection()
        proxy.setSelected(True)
        self.finish_history_action()

    def create_comment_card(self, data):
        card = CommentCard(data)
        if data.get("color"):
            card.set_card_color(data["color"])
        card.set_card_transparent(bool(data.get("transparent", False)))
        proxy = MovableCardProxy("comment")
        proxy.setWidget(card)
        self.scene.addItem(proxy)
        proxy.setZValue(
            float(data["layer"])
            if "layer" in data else self.next_design_layer()
        )
        proxy.configure_card_size(120.0, 52.0)
        if "width" in data and "height" in data:
            proxy.set_card_size(data["width"], data["height"])
        proxy.set_locked(bool(data.get("locked", False)))
        self.comment_cards.append(proxy)
        return proxy

    def comment_data_for_proxy(self, proxy):
        card = proxy.widget()
        data = dict(card.comment_data)
        data.update({
            "x": proxy.pos().x(),
            "y": proxy.pos().y(),
            "width": card.width(),
            "height": card.height(),
            "color": card.card_color.name(),
            "transparent": card.card_transparent,
            "layer": proxy.zValue(),
            "locked": proxy.locked,
        })
        return data

    def clear_comments(self):
        for proxy in list(self.comment_cards):
            if proxy.scene() is self.scene:
                self.scene.removeItem(proxy)
        self.comment_cards.clear()

    def restore_comments(self, comments):
        self.clear_comments()
        for data in comments if isinstance(comments, list) else []:
            if not isinstance(data, dict):
                continue
            proxy = self.create_comment_card(data)
            proxy.setPos(float(data.get("x", 0.0)), float(data.get("y", 0.0)))

    def edit_comment(self, proxy):
        if not self.edit_mode or proxy not in self.comment_cards:
            return
        card = proxy.widget()
        dialog = CommentEditDialog(card.comment_data, self.tr, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.begin_history_action()
        card.set_comment_data(dialog.comment_data())
        self.finish_history_action()

    def delete_comments(self, proxies, confirm=True):
        targets = [
            p for p in proxies
            if p in self.comment_cards and not p.locked
        ]
        if not targets:
            return
        if confirm:
            answer = QMessageBox.question(
                self,
                self.windowTitle(),
                self.tr(
                    "Möchten Sie die ausgewählten Kommentare wirklich löschen?",
                    "Do you really want to delete the selected comments?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.begin_history_action()
        for proxy in targets:
            self.scene.removeItem(proxy)
            self.comment_cards.remove(proxy)
        self.finish_history_action()

    def show_empty_context_menu(self, global_position, scene_position):
        """Bietet auf freier Fläche Gestaltung und zulässiges Einfügen an."""

        if not self.edit_mode:
            return
        self.update_selection_actions()
        menu = QMenu(self)
        menu.addAction(self.background_color_action)
        menu.addAction(self.grid_visible_action)
        menu.addAction(self.grid_snap_action)
        menu.addAction(self.grid_spacing_action)
        menu.addSeparator()
        menu.addAction(self.default_layout_action)
        paste_action = None
        if self.paste_clipboard_action.isEnabled():
            menu.addSeparator()
            paste_action = menu.addAction(self.paste_clipboard_action.text())
            paste_action.setIcon(ToolbarIcons.icon("paste"))
            paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        selected = menu.exec(global_position)
        if paste_action is not None and selected == paste_action:
            self.paste_clipboard_content(scene_position)

    def show_canvas_context_menu(self, global_position, scene_position):
        if not self.edit_mode:
            return
        menu = QMenu(self)
        element_menu = menu.addMenu(self.tr("Element hinzufügen", "Add element"))
        element_menu.setIcon(ToolbarIcons.icon("add_all"))
        input_menu = element_menu.addMenu(self.tr("Eingang", "Input"))
        input_menu.setIcon(ToolbarIcons.icon("input"))
        output_menu = element_menu.addMenu(self.tr("Ausgang", "Output"))
        output_menu.setIcon(ToolbarIcons.icon("output"))
        actions = {}
        for proxy, _controls, mapping in self.input_cards:
            action = input_menu.addAction(str(mapping.get("name") or mapping["neuron"].name))
            action.setIcon(ToolbarIcons.icon("input"))
            action.setEnabled(not proxy.isVisible())
            actions[action] = proxy
        for proxy, _controls, mapping in self.output_cards:
            action = output_menu.addAction(str(mapping.get("name") or mapping["neuron"].name))
            action.setIcon(ToolbarIcons.icon("output"))
            action.setEnabled(not proxy.isVisible())
            actions[action] = proxy
        all_io_action = element_menu.addAction(
            self.tr(
                "Alle Ein- und Ausgänge hinzufügen",
                "Add all inputs and outputs",
            )
        )
        all_io_action.setEnabled(
            any(
                not proxy.isVisible()
                for proxy, _controls, _mapping
                in self.input_cards + self.output_cards
            )
        )
        all_io_action.setIcon(ToolbarIcons.icon("add_all"))
        array_action = element_menu.addAction(
            self.tr("Binäres Eingabe-Array", "Binary input array")
        )
        array_action.setIcon(ToolbarIcons.icon("binary_array"))
        array_action.setEnabled(
            self.input_array_card is not None and not self.input_array_card.isVisible()
        )
        network_action = element_menu.addAction(
            self.tr("Vereinfachte Netzwerkansicht", "Simplified network view")
        )
        network_action.setIcon(ToolbarIcons.icon("network_layout"))
        network_action.setEnabled(
            self.network_view_card is not None
            and not self.network_view_card.isVisible()
        )
        element_menu.addSeparator()
        add_action = element_menu.addAction(
            self.tr("Kommentar", "Comment")
        )
        add_action.setIcon(ToolbarIcons.icon("comment"))
        image_action = element_menu.addAction(
            self.tr(
                "Grafik ersetzen…" if self.background_item is not None else "Grafik laden…",
                "Replace image…" if self.background_item is not None else "Load image…",
            )
        )
        image_action.setIcon(ToolbarIcons.icon("project_image"))
        icon_action = element_menu.addAction(
            self.tr("Symbol…", "Symbol…")
        )
        icon_action.setIcon(standard_design_icon_preview("arrow", size=24))
        shape_menu = element_menu.addMenu(
            self.tr("Grafische Form", "Graphic shape")
        )
        shape_menu.setIcon(ToolbarIcons.icon("rectangle"))
        line_action = shape_menu.addAction(self.tr("Linie", "Line"))
        line_action.setIcon(ToolbarIcons.icon("line"))
        curve_action = shape_menu.addAction(
            self.tr("Kurvenverbindung", "Curved connection")
        )
        curve_action.setIcon(ToolbarIcons.icon("curve"))
        rectangle_action = shape_menu.addAction(self.tr("Rechteck", "Rectangle"))
        rectangle_action.setIcon(ToolbarIcons.icon("rectangle"))
        ellipse_action = shape_menu.addAction(
            self.tr("Kreis / Ellipse", "Circle / ellipse")
        )
        ellipse_action.setIcon(ToolbarIcons.icon("ellipse"))
        menu.addSeparator()
        color_action = menu.addAction(
            self.tr("Hintergrundfarbe…", "Background color…")
        )
        color_action.setIcon(ToolbarIcons.icon("color"))
        selected = menu.exec(global_position)
        if selected in actions:
            self.add_existing_element(actions[selected], scene_position)
        elif selected == all_io_action:
            self.add_all_input_output_elements()
        elif selected == array_action:
            self.add_existing_element(self.input_array_card, scene_position)
        elif selected == network_action:
            self.add_existing_element(self.network_view_card, scene_position)
        elif selected == add_action:
            self.add_comment(scene_position)
        elif selected == icon_action:
            self.choose_standard_icon(scene_position)
        elif selected == line_action:
            self.add_shape("line", scene_position)
        elif selected == curve_action:
            self.add_shape("curve", scene_position)
        elif selected == rectangle_action:
            self.add_shape("rectangle", scene_position)
        elif selected == ellipse_action:
            self.add_shape("ellipse", scene_position)
        elif selected == image_action:
            self.load_background_image()
        elif selected == color_action:
            self.choose_background_color()

    def output_controls_for_proxy(self, proxy):
        for item, controls, _mapping in self.output_cards:
            if item is proxy:
                return controls
        return None

    def input_controls_for_proxy(self, proxy):
        for item, controls, _mapping in self.input_cards:
            if item is proxy:
                return controls
        return None

    def show_card_context_menu(self, proxy, global_position):
        if not self.edit_mode:
            return
        pending_selection = list(
            getattr(self, "pending_context_card_selection", []) or []
        )
        self.pending_context_card_selection = []
        if proxy in pending_selection:
            valid_targets = [
                item for item in pending_selection
                if item.scene() is self.scene
            ]
            self.scene.clearSelection()
            for item in valid_targets:
                item.setSelected(True)
        if not proxy.isSelected():
            self.scene.clearSelection()
            proxy.setSelected(True)
        self.last_selected_card = proxy
        color_targets = list(self.selected_card_proxies())
        self.update_selection_actions()
        menu = QMenu(self)
        front_action = menu.addAction(
            self.tr("In den Vordergrund", "Bring to front")
        )
        front_action.setIcon(ToolbarIcons.icon("layer_front"))
        back_action = menu.addAction(
            self.tr("In den Hintergrund", "Send to back")
        )
        back_action.setIcon(ToolbarIcons.icon("layer_back"))
        lock_action, unlock_action = self.add_lock_actions(menu)
        menu.addSeparator()
        choose_color = menu.addAction(self.tr("Kachelfarbe…", "Card color…"))
        choose_color.setIcon(ToolbarIcons.icon("color"))
        default_color = menu.addAction(
            self.tr("Standardfarbe (Weiß)", "Default color (white)")
        )
        default_color.setIcon(ToolbarIcons.icon("color"))
        transparent_action = menu.addAction(
            self.tr("Transparent", "Transparent")
        )
        transparent_action.setIcon(ToolbarIcons.icon("transparent"))
        transparent_action.setCheckable(True)
        transparent_action.setChecked(proxy.widget().card_transparent)
        edit_action = delete_action = remove_action = None
        bar_action = vertical_bar_action = pointer_action = None
        input_slider_action = input_vertical_slider_action = input_dial_action = None
        input_values_action = output_values_action = None
        binary_intermediate_action = None
        rename_array_action = None
        characteristic_settings_action = None
        if proxy.card_role == "characteristic":
            menu.addSeparator()
            menu.addAction(self.copy_shapes_action)
            characteristic_settings_action = menu.addAction(
                self.tr("Kennlinie einstellen…", "Configure characteristic…")
            )
            characteristic_settings_action.setEnabled(not proxy.locked)
        if proxy.card_role == "comment":
            menu.addSeparator()
            menu.addAction(self.copy_shapes_action)
            edit_action = menu.addAction(self.tr("Kommentar bearbeiten…", "Edit comment…"))
            edit_action.setIcon(ToolbarIcons.icon("edit"))
            delete_action = menu.addAction(self.tr("Kommentar löschen", "Delete comment"))
            delete_action.setIcon(ToolbarIcons.icon("delete"))
            delete_action.setEnabled(not proxy.locked)
        elif proxy.card_role in ("input", "output", "input_array", "network_view", "characteristic"):
            menu.addSeparator()
            if proxy.card_role == "input_array":
                rename_array_action = menu.addAction(
                    self.tr("Bezeichnung ändern…", "Change title…")
                )
                rename_array_action.setIcon(ToolbarIcons.icon("edit"))
            remove_action = menu.addAction(
                self.tr("Aus Gestaltung entfernen", "Remove from design")
            )
            remove_action.setIcon(ToolbarIcons.icon("delete"))
            remove_action.setEnabled(any(
                item.card_role in ("input", "output", "input_array", "network_view", "characteristic")
                and not item.locked
                for item in self.selected_card_proxies()
            ))
            if proxy.card_role == "network_view":
                input_values_action = menu.addAction(
                    self.tr("Eingabewerte anzeigen", "Show input values")
                )
                input_values_action.setIcon(ToolbarIcons.icon("input"))
                input_values_action.setCheckable(True)
                input_values_action.setChecked(
                    proxy.widget().show_input_values
                )
                output_values_action = menu.addAction(
                    self.tr("Ausgabewerte anzeigen", "Show output values")
                )
                output_values_action.setIcon(ToolbarIcons.icon("output"))
                output_values_action.setCheckable(True)
                output_values_action.setChecked(
                    proxy.widget().show_output_values
                )
        input_controls = self.input_controls_for_proxy(proxy)
        if input_controls is not None and not input_controls.get("binary"):
            menu.addSeparator()
            input_slider_action = menu.addAction(
                self.tr(
                    "Schieberegler horizontal",
                    "Horizontal slider",
                )
            )
            input_slider_action.setIcon(ToolbarIcons.icon("bar_display"))
            input_vertical_slider_action = menu.addAction(
                self.tr(
                    "Schieberegler vertikal",
                    "Vertical slider",
                )
            )
            input_vertical_slider_action.setIcon(
                ToolbarIcons.icon("bar_display")
            )
            input_dial_action = menu.addAction(
                self.tr("Drehregler", "Rotary control")
            )
            input_dial_action.setIcon(ToolbarIcons.icon("pointer_display"))
            input_slider_action.setCheckable(True)
            input_vertical_slider_action.setCheckable(True)
            input_dial_action.setCheckable(True)
            input_slider_action.setChecked(
                input_controls["display_mode"] == "slider"
            )
            input_vertical_slider_action.setChecked(
                input_controls["display_mode"] == "slider_vertical"
            )
            input_dial_action.setChecked(
                input_controls["display_mode"] == "dial"
            )

        controls = self.output_controls_for_proxy(proxy)
        if controls is not None and controls.get("binary"):
            intermediate_targets = [
                item for item in color_targets
                if (self.output_controls_for_proxy(item) or {}).get("binary")
            ]
            menu.addSeparator()
            binary_intermediate_action = menu.addAction(
                self.tr("Zwischenwerte anzeigen", "Show intermediate values")
                if len(intermediate_targets) > 1 else
                self.tr("Zwischenwert anzeigen", "Show intermediate value")
            )
            binary_intermediate_action.setIcon(
                ToolbarIcons.icon("output")
            )
            binary_intermediate_action.setCheckable(True)
            binary_intermediate_action.setChecked(
                all(self.output_controls_for_proxy(item)["card"].binary_intermediate_enabled
                    for item in intermediate_targets)
            )
        elif controls is not None and controls.get("display_mode") != "binary":
            menu.addSeparator()
            bar_action = menu.addAction(
                self.tr(
                    "Balkenanzeige horizontal",
                    "Horizontal bar display",
                )
            )
            bar_action.setIcon(ToolbarIcons.icon("bar_display"))
            vertical_bar_action = menu.addAction(
                self.tr(
                    "Balkenanzeige vertikal",
                    "Vertical bar display",
                )
            )
            vertical_bar_action.setIcon(ToolbarIcons.icon("bar_display"))
            pointer_action = menu.addAction(self.tr("Zeigeranzeige", "Pointer display"))
            pointer_action.setIcon(ToolbarIcons.icon("pointer_display"))
            bar_action.setCheckable(True)
            vertical_bar_action.setCheckable(True)
            pointer_action.setCheckable(True)
            bar_action.setChecked(controls["display_mode"] == "bar")
            vertical_bar_action.setChecked(
                controls["display_mode"] == "bar_vertical"
            )
            pointer_action.setChecked(controls["display_mode"] == "pointer")
        selected = menu.exec(global_position)
        if characteristic_settings_action is not None and selected == characteristic_settings_action:
            self.curves.configure(proxy)
        elif selected == front_action:
            selected_elements = [
                element for element in self.design_elements(visible_only=True)
                if element.isSelected()
            ]
            self.bring_elements_to_front(selected_elements or [proxy])
        elif selected == back_action:
            selected_elements = [
                element for element in self.design_elements(visible_only=True)
                if element.isSelected()
            ]
            self.send_elements_to_back(selected_elements or [proxy])
        elif lock_action is not None and selected == lock_action:
            self.set_elements_locked(self.selected_movable_items(), True)
        elif unlock_action is not None and selected == unlock_action:
            self.set_elements_locked(self.selected_movable_items(), False)
        elif selected == choose_color:
            self.choose_card_color(color_targets)
        elif selected == default_color:
            self.apply_card_color("#ffffff", color_targets)
        elif selected == transparent_action:
            self.apply_card_transparency(
                transparent_action.isChecked(), color_targets
            )
        elif edit_action is not None and selected == edit_action:
            self.edit_comment(proxy)
        elif delete_action is not None and selected == delete_action:
            self.delete_comments([proxy])
        elif rename_array_action is not None and selected == rename_array_action:
            card = proxy.widget()
            title, accepted = QInputDialog.getText(
                self,
                self.tr("Bezeichnung des Eingabemusters", "Input pattern title"),
                self.tr("Bezeichnung:", "Title:"),
                text=card.custom_title,
            )
            if accepted and title.strip():
                self.begin_history_action()
                card.set_title(title)
                self.finish_history_action()
        elif remove_action is not None and selected == remove_action:
            self.remove_elements_from_design(self.selected_card_proxies())
        elif (
            input_values_action is not None
            and selected == input_values_action
        ):
            self.begin_history_action()
            proxy.widget().set_show_input_values(
                input_values_action.isChecked()
            )
            self.finish_history_action()
        elif (
            output_values_action is not None
            and selected == output_values_action
        ):
            self.begin_history_action()
            proxy.widget().set_show_output_values(
                output_values_action.isChecked()
            )
            self.finish_history_action()
        elif (
            binary_intermediate_action is not None
            and selected == binary_intermediate_action
        ):
            self.begin_history_action()
            for item in intermediate_targets:
                self.set_binary_output_intermediate_value(
                    item, binary_intermediate_action.isChecked(), record_history=False,
                )
            self.finish_history_action()
        elif input_slider_action is not None and selected in (
            input_slider_action,
            input_vertical_slider_action,
            input_dial_action,
        ):
            self.begin_history_action()
            display_mode = "slider"
            if selected == input_vertical_slider_action:
                display_mode = "slider_vertical"
            elif selected == input_dial_action:
                display_mode = "dial"
            self.set_input_display_mode(
                input_controls,
                display_mode,
            )
            self.finish_history_action()
        elif bar_action is not None and selected in (
            bar_action,
            vertical_bar_action,
            pointer_action,
        ):
            self.begin_history_action()
            display_mode = "bar"
            if selected == vertical_bar_action:
                display_mode = "bar_vertical"
            elif selected == pointer_action:
                display_mode = "pointer"
            self.set_output_display_mode(
                controls, display_mode
            )
            self.finish_history_action()

    def selected_card_proxies(self):
        return [
            item for item in self.scene.selectedItems()
            if isinstance(item, MovableCardProxy)
        ]

    def selected_movable_items(self):
        return [
            item for item in self.scene.selectedItems()
            if isinstance(
                item,
                (MovableCardProxy, ResizableBackgroundItem, DesignShapeItem),
            )
        ]

    def add_lock_actions(self, menu):
        """Ergänzt passende Sperraktionen für die aktuelle Auswahl."""

        selected = self.selected_movable_items()
        lock_action = unlock_action = None
        if any(not item.locked for item in selected):
            lock_action = menu.addAction(
                self.tr("Auswahl sperren", "Lock selection")
            )
            lock_action.setIcon(ToolbarIcons.icon("lock"))
        if any(item.locked for item in selected):
            unlock_action = menu.addAction(
                self.tr("Auswahl entsperren", "Unlock selection")
            )
            unlock_action.setIcon(ToolbarIcons.icon("unlock"))
        return lock_action, unlock_action

    def set_elements_locked(self, elements, locked):
        targets = [
            item for item in elements
            if isinstance(
                item,
                (MovableCardProxy, ResizableBackgroundItem, DesignShapeItem),
            ) and item.scene() is self.scene and item.locked != bool(locked)
        ]
        if not self.edit_mode or not targets:
            return
        self.begin_history_action()
        for item in targets:
            item.set_locked(locked)
        self.finish_history_action()
        self.update_selection_actions()

    def update_selection_actions(self):
        selected = self.selected_card_proxies()
        count = len(selected)
        selected_shapes = [
            item for item in self.scene.selectedItems()
            if isinstance(item, DesignShapeItem)
        ]
        selected_comments = [
            item for item in self.scene.selectedItems()
            if isinstance(item, MovableCardProxy) and item.card_role == "comment"
        ]
        mime_data = QApplication.clipboard().mimeData()
        has_copied_elements = mime_data.hasFormat(self.SHAPE_CLIPBOARD_MIME)
        has_image = (
            mime_data.hasImage()
            or self.image_path_from_mime_data(mime_data) is not None
        )
        can_paste = has_copied_elements or has_image
        self.copy_shapes_action.setEnabled(
            self.edit_mode and bool(selected_shapes or selected_comments or
                                    any(p.card_role == "characteristic" for p in selected))
        )
        self.paste_clipboard_action.setEnabled(self.edit_mode and can_paste)
        if has_copied_elements:
            self.paste_clipboard_action.setText(self.tr(
                "Kopierte Elemente einfügen",
                "Paste copied elements",
            ))
        elif has_image:
            self.paste_clipboard_action.setText(self.tr(
                "Hintergrundbild aus Zwischenablage einfügen",
                "Paste background image from clipboard",
            ))
        else:
            self.paste_clipboard_action.setText(self.tr("Einfügen", "Paste"))
        if self.last_selected_card not in selected:
            self.last_selected_card = selected[-1] if selected else None
        roles = {item.card_role for item in selected}
        same_role = len(roles) == 1
        self.align_button.setEnabled(self.edit_mode and count >= 2)
        self.align_menu.menuAction().setEnabled(self.edit_mode and count >= 2)
        self.distribute_horizontal_action.setEnabled(count >= 3)
        self.distribute_vertical_action.setEnabled(count >= 3)
        self.size_button.setEnabled(self.edit_mode and count >= 1)
        self.size_menu.menuAction().setEnabled(self.edit_mode and count >= 1)
        self.card_color_button.setEnabled(self.edit_mode and count >= 1)
        self.card_color_menu.menuAction().setEnabled(self.edit_mode and count >= 1)
        self.arrange_grid_action.setEnabled(self.edit_mode and count >= 2)
        for action in (
            self.equal_width_action,
            self.equal_height_action,
            self.equal_size_action,
        ):
            action.setEnabled(count >= 2 and same_role)
        reference_role = (
            self.last_selected_card.card_role
            if self.last_selected_card is not None
            else ""
        )
        self.size_all_inputs_action.setEnabled(reference_role == "input")
        self.size_all_outputs_action.setEnabled(reference_role == "output")

    def choose_card_color(self, targets=None):
        selected = list(targets) if targets is not None else self.selected_card_proxies()
        if not self.edit_mode or not selected:
            return
        initial = selected[-1].widget().card_color
        self.restore_custom_card_colors()
        dialog = QColorDialog(initial, self)
        dialog.setWindowTitle(self.tr("Kachelfarbe", "Card color"))
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        color = dialog.selectedColor()
        self.save_custom_card_colors()
        if accepted and color.isValid():
            self.apply_card_color(color, selected)

    def apply_card_color(self, color, targets=None):
        selected = list(targets) if targets is not None else self.selected_card_proxies()
        if not self.edit_mode or not selected:
            return
        self.begin_history_action()
        for item in selected:
            item.widget().set_card_color(color)
        self.finish_history_action()

    def apply_card_transparency(self, transparent, targets=None):
        selected = list(targets or self.selected_card_proxies())
        if not selected:
            return
        self.begin_history_action()
        for item in selected:
            item.widget().set_card_transparent(transparent)
        self.finish_history_action()

    @staticmethod
    def restore_custom_card_colors():
        restore_custom_colors()

    @staticmethod
    def save_custom_card_colors():
        save_custom_colors()

    def equalize_selected_size(self, dimension):
        selected = [
            item for item in self.selected_card_proxies() if not item.locked
        ]
        if len(selected) < 2 or len({item.card_role for item in selected}) != 1:
            return
        reference = (
            self.last_selected_card
            if self.last_selected_card in selected
            else selected[-1]
        )
        width = reference.widget().width()
        height = reference.widget().height()
        self.begin_history_action()
        for item in selected:
            target_width = width if dimension in ("width", "both") else item.widget().width()
            target_height = height if dimension in ("height", "both") else item.widget().height()
            item.set_card_size(target_width, target_height)
        self.finish_history_action()

    def apply_reference_size_to_role(self, role):
        reference = self.last_selected_card
        if reference is None or reference.card_role != role:
            return
        width = reference.widget().width()
        height = reference.widget().height()
        items = self.input_cards if role == "input" else self.output_cards
        self.begin_history_action()
        for proxy, _controls, _mapping in items:
            if not proxy.locked:
                proxy.set_card_size(width, height)
        self.finish_history_action()

    def align_selected(self, direction):
        selected = [
            item for item in self.selected_card_proxies() if not item.locked
        ]
        if len(selected) < 2:
            return
        self.begin_history_action()
        if direction == "left":
            target = min(item.pos().x() for item in selected)
            for item in selected:
                item.setX(target)
        elif direction == "right":
            target = max(
                item.pos().x() + item.boundingRect().width() for item in selected
            )
            for item in selected:
                item.setX(target - item.boundingRect().width())
        elif direction == "top":
            target = min(item.pos().y() for item in selected)
            for item in selected:
                item.setY(target)
        elif direction == "bottom":
            target = max(
                item.pos().y() + item.boundingRect().height() for item in selected
            )
            for item in selected:
                item.setY(target - item.boundingRect().height())
        self.finish_history_action()

    def distribute_selected(self, orientation):
        selected = [
            item for item in self.selected_card_proxies() if not item.locked
        ]
        if len(selected) < 3:
            return
        self.begin_history_action()
        if orientation == "horizontal":
            selected.sort(key=lambda item: item.pos().x())
            left = selected[0].pos().x()
            right = selected[-1].pos().x() + selected[-1].boundingRect().width()
            total_width = sum(item.boundingRect().width() for item in selected)
            spacing = (right - left - total_width) / (len(selected) - 1)
            position = left
            for item in selected:
                item.setX(position)
                position += item.boundingRect().width() + spacing
        else:
            selected.sort(key=lambda item: item.pos().y())
            top = selected[0].pos().y()
            bottom = selected[-1].pos().y() + selected[-1].boundingRect().height()
            total_height = sum(item.boundingRect().height() for item in selected)
            spacing = (bottom - top - total_height) / (len(selected) - 1)
            position = top
            for item in selected:
                item.setY(position)
                position += item.boundingRect().height() + spacing
        self.finish_history_action()

    def arrange_selected_as_grid(self):
        selected = [
            item for item in self.selected_card_proxies() if not item.locked
        ]
        if len(selected) < 2:
            return
        selected.sort(key=lambda item: (item.sceneBoundingRect().center().y(), item.pos().x()))
        average_height = sum(item.boundingRect().height() for item in selected) / len(selected)
        tolerance = max(12.0, average_height * 0.55)
        rows = []
        for item in selected:
            center_y = item.sceneBoundingRect().center().y()
            if not rows or abs(center_y - rows[-1][0]) > tolerance:
                rows.append([center_y, [item]])
            else:
                rows[-1][1].append(item)
                rows[-1][0] = sum(
                    member.sceneBoundingRect().center().y() for member in rows[-1][1]
                ) / len(rows[-1][1])
        for _center, items in rows:
            items.sort(key=lambda item: item.pos().x())
        left = min(item.pos().x() for item in selected)
        top = min(item.pos().y() for item in selected)
        column_widths = []
        for column in range(max(len(items) for _center, items in rows)):
            widths = [
                items[column].boundingRect().width()
                for _center, items in rows if column < len(items)
            ]
            column_widths.append(max(widths))
        row_heights = [
            max(item.boundingRect().height() for item in items)
            for _center, items in rows
        ]
        horizontal_gap = 16.0
        vertical_gap = 12.0
        x_positions = []
        x = left
        for width in column_widths:
            x_positions.append(x)
            x += width + horizontal_gap
        self.begin_history_action()
        y = top
        for row_index, (_center, items) in enumerate(rows):
            for column, item in enumerate(items):
                item.setPos(x_positions[column], y)
            y += row_heights[row_index] + vertical_gap
        self.finish_history_action()

    def nudge_selected(self, dx, dy):
        selected = [
            item for item in self.selected_movable_items() if not item.locked
        ]
        if not self.edit_mode or not selected:
            return
        if not self.nudge_history_active:
            self.begin_history_action()
            self.nudge_history_active = True
        self.nudge_handles_hidden = True
        scene_rect = self.scene.sceneRect()
        minimum_dx = max(
            scene_rect.left() - item.sceneBoundingRect().left() for item in selected
        )
        maximum_dx = min(
            scene_rect.right() - item.sceneBoundingRect().right() for item in selected
        )
        minimum_dy = max(
            scene_rect.top() - item.sceneBoundingRect().top() for item in selected
        )
        maximum_dy = min(
            scene_rect.bottom() - item.sceneBoundingRect().bottom() for item in selected
        )
        applied_dx = max(minimum_dx, min(maximum_dx, float(dx)))
        applied_dy = max(minimum_dy, min(maximum_dy, float(dy)))
        for item in selected:
            item.moveBy(applied_dx, applied_dy)
        self.scene.update()
        self.nudge_timer.start()

    def finish_nudge_history(self):
        if not self.nudge_history_active:
            return
        self.nudge_history_active = False
        self.nudge_handles_hidden = False
        self.nudge_timer.stop()
        self.finish_history_action()
        self.scene.update()

    def card_widget(self):
        return ExperimentCard()

    def create_input_card(self, mapping):
        card = self.card_widget()
        card.maximum_content_scale = 3.50
        card.setFixedWidth(245)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 4, 5, 4)
        layout.setSpacing(2)
        top = QGridLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setHorizontalSpacing(4)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)
        name = ElidedLabel(str(mapping.get("name") or mapping["neuron"].name), card)
        name.setMinimumWidth(42)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(name, 0, 0)
        minimum, maximum = self.value_range(mapping)
        is_binary = mapping.get("data_type") == "binary"
        initial_value = float(
            self.initial_input_values.get(
                mapping["neuron"].id,
                (minimum + maximum) / 2.0,
            )
        )
        if is_binary:
            editor = CenteredCheckMarkBox(self.tr("Ein", "On"), card)
            def update_binary_input_color(state, widget=editor):
                border, background, foreground = state_palette(self.color_settings, state, ("", "", ""))
                widget.setStyleSheet(
                    f"QCheckBox {{ background:{background}; color:{foreground}; border:1px solid {border}; border-radius:4px; }}"
                    if background else ""
                )
            editor.toggled.connect(update_binary_input_color)
            editor.setChecked(initial_value > 0.5)
            update_binary_input_color(editor.isChecked())
            editor.toggled.connect(self.input_state_changed)
        else:
            editor = CompactInputSpinBox(card)
            editor.setButtonSymbols(
                QDoubleSpinBox.ButtonSymbols.NoButtons
            )
            editor.setRange(minimum, maximum)
            editor.setDecimals(5)
            editor.setMinimumWidth(64)
            editor.setMaximumWidth(90)
            editor.setProperty("nn_base_minimum_width", 64)
            editor.setProperty("nn_base_maximum_width", 90)
            editor.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            editor.setValue(max(minimum, min(maximum, initial_value)))
            if mapping.get("unit"):
                editor.setSuffix(" " + str(mapping["unit"]))
            editor.setToolTip(editor.text())
            editor.valueChanged.connect(
                lambda _value, target=editor: target.setToolTip(target.text())
            )
            editor.valueChanged.connect(
                lambda _value, target=card:
                target.resize_responsive_input_editor()
            )
            editor.valueChanged.connect(self.input_state_changed)
        top.addWidget(editor, 0, 1, Qt.AlignmentFlag.AlignCenter)
        card.responsive_input_grid = top
        card.responsive_input_name = name
        card.responsive_input_editor = editor
        card.responsive_input_stacked = False
        layout.addLayout(top)

        slider = CompactInputSlider(card)
        slider.setRange(0, 1000)
        slider.set_foreground_color(card.text_color)
        self.sync_slider(slider, initial_value, minimum, maximum)
        dial = CompactInputDial(
            minimum,
            maximum,
            str(mapping.get("unit") or ""),
            card,
        )
        dial.setRange(0, 1000)
        dial.set_foreground_color(card.text_color)
        self.sync_slider(dial, initial_value, minimum, maximum)
        vertical_page = CompactVerticalInputPage(
            minimum,
            maximum,
            str(mapping.get("unit") or ""),
            card,
        )
        vertical_slider = vertical_page.slider
        vertical_slider.setRange(0, 1000)
        vertical_slider.set_foreground_color(card.text_color)
        self.sync_slider(vertical_slider, initial_value, minimum, maximum)
        display_stack = QStackedWidget(card)
        display_stack.addWidget(slider)
        display_stack.addWidget(dial)
        display_stack.addWidget(vertical_page)
        display_stack.setFixedHeight(20)
        display_stack.setVisible(not is_binary)
        if not is_binary:
            for control in (slider, dial, vertical_slider):
                control.sliderPressed.connect(self.input_slider_pressed)
                control.sliderReleased.connect(self.input_slider_released)
                control.valueChanged.connect(
                    lambda position, target=editor, low=minimum, high=maximum:
                    target.setValue(low + position / 1000.0 * (high - low))
                )
            editor.valueChanged.connect(
                lambda value, target=slider, low=minimum, high=maximum:
                self.sync_slider(target, value, low, high)
            )
            editor.valueChanged.connect(
                lambda value, target=dial, low=minimum, high=maximum:
                self.sync_slider(target, value, low, high)
            )
            editor.valueChanged.connect(
                lambda value, target=vertical_slider, low=minimum, high=maximum:
                self.sync_slider(target, value, low, high)
            )
        layout.addWidget(display_stack)

        proxy = MovableCardProxy("input")
        proxy.setWidget(card)
        self.scene.addItem(proxy)
        proxy.setZValue(10.0)
        proxy.configure_card_size(115.0, 40.0 if is_binary else 44.0)
        controls = {
            "card": card,
            "editor": editor,
            "slider": slider,
            "dial": dial,
            "vertical_slider": vertical_slider,
            "vertical_page": vertical_page,
            "display_stack": display_stack,
            "display_mode": "binary" if is_binary else "slider",
            "binary": is_binary,
            "proxy": proxy,
            "mapping": mapping,
        }
        if not is_binary:
            self.set_input_display_mode(controls, "slider")
        return proxy, controls

    def create_output_card(self, mapping):
        card = self.card_widget()
        card.setFixedWidth(245)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 7)
        layout.setSpacing(4)
        top = QGridLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setHorizontalSpacing(4)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)
        name = ElidedLabel(str(mapping.get("name") or mapping["neuron"].name), card)
        value_label = ElidedLabel("–", card)
        value_label.setProperty(
            "nn_base_minimum_width",
            value_label.fontMetrics().horizontalAdvance("-0.000000") + 2,
        )
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(name, 0, 0)
        top.addWidget(value_label, 0, 1)
        layout.addLayout(top)
        display = QHBoxLayout()
        led = QLabel(card)
        led.setFixedSize(14, 14)
        led.setStyleSheet("background:#00c853; border:1px solid #008c3a; border-radius:7px;")
        led.setVisible(False)
        binary = mapping.get("data_type") == "binary"
        if binary:
            layout.setContentsMargins(4, 2, 4, 3)
            layout.setSpacing(1)
            value_label.setVisible(False)
            top.addWidget(name, 0, 0, 1, 2)
            led.setStyleSheet(
                "background:#a5abb0; border:1px solid #747a80; border-radius:7px;"
            )
            state_label = CenteredCheckMarkBox(self.tr("Ein", "On"), card)
            state_label.setChecked(False)
            state_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
            state_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            state_label.setMinimumHeight(16)
            off_border, off_background, off_foreground = state_palette(
                self.color_settings,
                False,
                ("", "", ""),
            )
            state_label.setStyleSheet(
                f"QCheckBox {{ background:{off_background}; "
                f"color:{off_foreground}; border:1px solid {off_border}; "
                "border-radius:4px; }}"
                if off_background else ""
            )
            state_label.setMinimumWidth(28)
            state_label.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            top.addWidget(name, 0, 0)
            top.addWidget(state_label, 0, 1, Qt.AlignmentFlag.AlignCenter)
            binary_bar = CompactOutputBar(card)
            binary_bar.setRange(0, 1000)
            binary_bar.setValue(0)
            binary_bar.set_foreground_color(card.text_color)
            binary_bar.setVisible(False)
            display.addWidget(led)
            display.setAlignment(led, Qt.AlignmentFlag.AlignVCenter)
            display.addWidget(binary_bar, 1)
            layout.addLayout(display)
            # Hohe binäre Ausgabekacheln nutzen die verfügbare Höhe bewusst:
            # Name oben, Status unten und symmetrische Außenabstände.
            layout.insertStretch(0, 1)
            layout.insertStretch(2, 2)
            layout.addStretch(1)
            card.maximum_content_scale = 3.50
            card.minimum_content_scale = 0.55
            card.responsive_binary_output = True
            card.responsive_binary_grid = top
            card.responsive_binary_name = name
            card.responsive_binary_value = value_label
            card.responsive_binary_state_label = state_label
            card.responsive_binary_main_layout = layout
            card.binary_intermediate_enabled = False
            card.responsive_binary_state = (False, False)
            proxy = MovableCardProxy("output")
            proxy.setWidget(card)
            self.scene.addItem(proxy)
            proxy.setZValue(10.0)
            proxy.configure_card_size(100.0, 38.0)
            proxy.set_card_size(proxy.widget().width(), 38.0)
            return proxy, {
                "card": card,
                "value": value_label,
                "bar": None,
                "binary_bar": binary_bar,
                "binary_stack": None,
                "led": led,
                "gauge": None,
                "state_label": state_label,
                "display_stack": None,
                "display_layout": display,
                "main_layout": layout,
                "header_layout": top,
                "name_label": name,
                "display_mode": "binary",
                "binary": True,
            }

        bar = CompactOutputBar(card)
        bar.setRange(0, 1000)
        bar.set_foreground_color(card.text_color)
        minimum, maximum = self.display_range(mapping)
        unit = str(mapping.get("unit") or "")
        bar_page = QWidget(card)
        bar_layout = QVBoxLayout(bar_page)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        bar_layout.addWidget(bar)
        range_layout = QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 0)
        minimum_label = QLabel("0 %", bar_page)
        maximum_label = QLabel("100 %", bar_page)
        minimum_label.setProperty("nn_max_font_size", 10.0)
        maximum_label.setProperty("nn_max_font_size", 10.0)
        range_layout.addWidget(minimum_label)
        range_layout.addStretch(1)
        range_layout.addWidget(maximum_label)
        bar_layout.addLayout(range_layout)
        bar_page.setFixedHeight(28)

        vertical_page = CompactVerticalOutputPage(
            minimum,
            maximum,
            unit,
            card,
            card,
        )
        vertical_bar = vertical_page.bar
        vertical_bar.setRange(0, 1000)
        vertical_bar.set_foreground_color(card.text_color)

        gauge = CompactOutputGauge(minimum, maximum, unit, card)
        display_stack = QStackedWidget(card)
        display_stack.addWidget(bar_page)
        display_stack.addWidget(gauge)
        display_stack.addWidget(vertical_page)
        display.addWidget(led)
        display.setAlignment(led, Qt.AlignmentFlag.AlignBottom)
        display.addWidget(display_stack, 1)
        layout.addLayout(display)
        proxy = MovableCardProxy("output")
        proxy.setWidget(card)
        self.scene.addItem(proxy)
        proxy.setZValue(10.0)
        controls = {
            "card": card,
            "value": value_label,
            "bar": bar,
            "binary_bar": None,
            "binary_stack": None,
            "led": led,
            "gauge": gauge,
            "vertical_bar": vertical_bar,
            "vertical_page": vertical_page,
            "state_label": None,
            "display_stack": display_stack,
            "display_layout": display,
            "display_mode": "bar",
            "binary": False,
            "proxy": proxy,
        }
        card.maximum_content_scale = 3.50
        card.responsive_output_grid = top
        card.responsive_output_name = name
        card.responsive_output_value = value_label
        card.responsive_output_bar_mode = True
        card.responsive_output_stacked = False
        self.set_output_display_mode(controls, "bar")
        proxy.configure_card_size(115.0, 44.0)
        proxy.set_card_size(proxy.widget().width(), 44.0)
        return proxy, controls

    def show_output_display_menu(self, controls, position):
        if not self.edit_mode or controls["display_mode"] == "binary":
            return
        menu = QMenu(self)
        bar_action = menu.addAction(
            self.tr(
                "Balkenanzeige horizontal",
                "Horizontal bar display",
            )
        )
        bar_action.setIcon(ToolbarIcons.icon("bar_display"))
        vertical_bar_action = menu.addAction(
            self.tr(
                "Balkenanzeige vertikal",
                "Vertical bar display",
            )
        )
        vertical_bar_action.setIcon(ToolbarIcons.icon("bar_display"))
        pointer_action = menu.addAction(self.tr("Zeigeranzeige", "Pointer display"))
        pointer_action.setIcon(ToolbarIcons.icon("pointer_display"))
        bar_action.setCheckable(True)
        vertical_bar_action.setCheckable(True)
        pointer_action.setCheckable(True)
        bar_action.setChecked(controls["display_mode"] == "bar")
        vertical_bar_action.setChecked(
            controls["display_mode"] == "bar_vertical"
        )
        pointer_action.setChecked(controls["display_mode"] == "pointer")
        selected = menu.exec(controls["card"].mapToGlobal(position))
        if selected == bar_action:
            self.begin_history_action()
            self.set_output_display_mode(controls, "bar")
            self.finish_history_action()
        elif selected == vertical_bar_action:
            self.begin_history_action()
            self.set_output_display_mode(controls, "bar_vertical")
            self.finish_history_action()
        elif selected == pointer_action:
            self.begin_history_action()
            self.set_output_display_mode(controls, "pointer")
            self.finish_history_action()

    @staticmethod
    def set_output_display_mode(controls, mode):
        if controls.get("display_mode") == "binary":
            return
        controls["display_mode"] = (
            mode
            if mode in ("bar_vertical", "pointer")
            else "bar"
        )
        pointer_mode = controls["display_mode"] == "pointer"
        vertical_mode = controls["display_mode"] == "bar_vertical"
        tall_mode = pointer_mode or vertical_mode
        card = controls.get("card")
        if isinstance(card, ExperimentCard):
            card.responsive_output_bar_mode = not tall_mode
            card.responsive_output_pointer_mode = pointer_mode
        controls["display_stack"].setCurrentIndex(
            2 if vertical_mode else (1 if pointer_mode else 0)
        )
        controls["vertical_bar"].setVisible(vertical_mode)
        if vertical_mode:
            controls["vertical_page"].update_positions()
        if tall_mode:
            controls["display_stack"].setMinimumHeight(64)
            controls["display_stack"].setMaximumHeight(16777215)
            controls["display_stack"].setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
        else:
            controls["display_stack"].setFixedHeight(28)
        controls["display_layout"].setAlignment(
            controls["led"],
            Qt.AlignmentFlag.AlignVCenter
            if tall_mode
            else Qt.AlignmentFlag.AlignBottom,
        )
        if isinstance(card, ExperimentCard):
            content_scale = card.content_scale_for_size(card.width(), card.height())
            card.apply_content_scale(content_scale)
        proxy = controls.get("proxy")
        desired_minimum_height = 96.0 if tall_mode else 44.0
        if proxy is not None:
            proxy.minimum_card_height = desired_minimum_height
            controls["card"].setMinimumHeight(round(desired_minimum_height))
            controls["card"].setMaximumHeight(16777215)
            if controls["card"].height() < desired_minimum_height:
                proxy.set_card_size(
                    controls["card"].width(), desired_minimum_height
                )
        else:
            controls["card"].adjustSize()
        controls["card"].updateGeometry()

    @staticmethod
    def set_input_display_mode(controls, mode):
        if controls.get("binary"):
            return
        controls["display_mode"] = (
            mode
            if mode in ("slider_vertical", "dial")
            else "slider"
        )
        dial_mode = controls["display_mode"] == "dial"
        vertical_mode = controls["display_mode"] == "slider_vertical"
        tall_mode = dial_mode or vertical_mode
        stack = controls["display_stack"]
        stack.setCurrentIndex(2 if vertical_mode else (1 if dial_mode else 0))
        if tall_mode:
            stack.setMinimumHeight(64)
            stack.setMaximumHeight(16777215)
            stack.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
        else:
            stack.setFixedHeight(20)
        proxy = controls.get("proxy")
        desired_minimum_height = (
            110.0 if vertical_mode else (96.0 if dial_mode else 44.0)
        )
        if proxy is not None:
            proxy.minimum_card_height = desired_minimum_height
            card = controls["card"]
            card.setMinimumHeight(round(desired_minimum_height))
            card.setMaximumHeight(16777215)
            if card.height() < desired_minimum_height:
                proxy.set_card_size(card.width(), desired_minimum_height)
        controls["card"].updateGeometry()

    @staticmethod
    def sync_slider(slider, value, minimum, maximum):
        if maximum <= minimum:
            return
        position = round((float(value) - minimum) / (maximum - minimum) * 1000.0)
        slider.blockSignals(True)
        slider.setValue(max(0, min(1000, position)))
        slider.blockSignals(False)

    def input_value(self, controls, mapping):
        if mapping.get("data_type") == "binary":
            return 1.0 if controls["editor"].isChecked() else 0.0
        return float(controls["editor"].value())

    def current_input_values(self):
        """Liefert sämtliche aktuellen Eingabewerte in Rohwerteinheiten."""

        return {
            mapping["neuron"].id: float(self.input_value(controls, mapping))
            for _proxy, controls, mapping in self.input_cards
        }

    def apply_saved_input_values(self, values):
        """Stellt die in der Anwendungsansicht gespeicherten Eingaben wieder her."""

        if not isinstance(values, dict):
            return
        for _proxy, controls, mapping in self.input_cards:
            key = str(mapping["neuron"].id)
            if key not in values:
                continue
            try:
                value = float(values[key])
            except (TypeError, ValueError):
                continue
            editor = controls["editor"]
            editor.blockSignals(True)
            if mapping.get("data_type") == "binary":
                editor.setChecked(value > 0.5)
            else:
                editor.setValue(value)
                minimum, maximum = self.value_range(mapping)
                self.sync_slider(controls["slider"], value, minimum, maximum)
                self.sync_slider(controls["dial"], value, minimum, maximum)
                self.sync_slider(
                    controls["vertical_slider"], value, minimum, maximum
                )
                editor.setToolTip(editor.text())
            editor.blockSignals(False)

    def set_binary_output_intermediate_value(
        self,
        proxy,
        enabled,
        record_history=True,
    ):
        """Schaltet den Zwischenwert genau eines binären Ausgangs um."""

        controls = self.output_controls_for_proxy(proxy)
        if controls is None or not controls.get("binary"):
            return
        card = controls["card"]
        enabled = bool(enabled)
        if bool(card.binary_intermediate_enabled) == enabled:
            return
        if record_history:
            self.begin_history_action()
        controls["value"].setVisible(enabled)
        controls["led"].setVisible(enabled)
        controls["binary_bar"].setVisible(enabled)
        controls["state_label"].setVisible(not enabled)
        card.binary_intermediate_enabled = enabled
        card.responsive_binary_state = None
        main_layout = controls.get("main_layout")
        if main_layout is not None:
            main_layout.setStretch(0, 1 if enabled else 0)
            main_layout.setStretch(2, 0)
            main_layout.setStretch(4, 1 if enabled else 0)
            main_layout.invalidate()
        proxy.set_card_size(card.width(), card.height())
        if record_history:
            self.finish_history_action()

    def restore_binary_output_intermediate_values(self, document):
        """Lädt Einzelwerte und übernimmt alte globale Layoutangaben."""

        cards = document.get("cards", {})
        legacy_enabled = bool(
            document.get("binary_intermediate_values", False)
        )
        for proxy, controls, mapping in self.output_cards:
            if not controls.get("binary"):
                continue
            geometry = cards.get(self.card_key("output", mapping))
            enabled = legacy_enabled
            if isinstance(geometry, dict):
                enabled = bool(
                    geometry.get("binary_intermediate", legacy_enabled)
                )
            self.set_binary_output_intermediate_value(
                proxy,
                enabled,
                record_history=False,
            )

    def input_state_changed(self, *_):
        """Markiert eine Eingabeänderung ohne teuren Gesamtvergleich."""

        self.input_state_dirty = True
        self.save_button.setEnabled(True)
        self.save_shortcut.setEnabled(True)
        self.calculate()

    def input_slider_pressed(self):
        """Merkt, dass ein analoger Eingaberegler gerade gezogen wird."""

        self.active_input_sliders += 1
        if not self.drag_calculation_timer.isActive():
            self.drag_calculation_timer.start()

    def input_slider_released(self):
        """Berechnet den endgültigen Reglerwert unmittelbar nach dem Loslassen."""

        self.active_input_sliders = max(0, self.active_input_sliders - 1)
        if self.active_input_sliders == 0 and not self.edit_mode:
            self.drag_calculation_timer.stop()
            self.drag_calculation_pending = False
            self.calculation_timer.stop()
            QTimer.singleShot(0, self.perform_calculation)

    def perform_pending_drag_calculation(self):
        """Berechnet während des Ziehens regelmäßig nur den neuesten Wert."""

        if not self.active_input_sliders:
            self.drag_calculation_timer.stop()
            return
        if not self.drag_calculation_pending:
            return
        self.drag_calculation_pending = False
        self.perform_calculation()

    def calculate(self, *_):
        """Fordert eine zusammengefasste Vorwärtsberechnung an."""

        if self.edit_mode:
            return
        if self.active_input_sliders:
            self.drag_calculation_pending = True
        elif not self.calculation_timer.isActive():
            self.calculation_timer.start()

    def perform_calculation(self):
        """Übergibt nur den neuesten Eingabezustand an die Hintergrundrechnung."""

        if self.edit_mode:
            return
        try:
            if self.input_array_card is not None:
                self.input_array_card.widget().sync_from_inputs()
            input_values = {}
            for _proxy, controls, mapping in self.input_cards:
                raw_value = self.input_value(controls, mapping)
                input_values[mapping["neuron"].id] = TrainingDataIO.scale_value(
                    raw_value, mapping["calibration"],
                    getattr(self.language, "text", None),
                )
            self.forward_request_number += 1
            request = (self.forward_request_number, input_values)
            if self.forward_calculation_running:
                self.pending_forward_request = request
                return
            self.start_forward_calculation(*request)
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))

    def create_forward_specification(self):
        """Erzeugt einmalig eine Qt-freie Beschreibung des aktuellen Netzes."""

        order = self.network.prepared_training_order()
        if order is None:
            validation = self.network.validate_network()
            if not validation["valid"]:
                raise ValueError("\n".join(validation["errors"]))
            order = self.network.get_topological_order()
        return tuple({
            "id": neuron.id,
            "name": neuron.name,
            "input": str(neuron.neuron_type.value).casefold() == "input",
            "bias": float(neuron.bias),
            "activation": str(neuron.activation_function),
            "incoming": tuple(
                (connection.source_neuron.id, float(connection.weight))
                for connection in neuron.incoming_connections
            ),
        } for neuron in order)

    def start_forward_calculation(self, request_number, input_values):
        """Startet genau eine Hintergrundrechnung."""

        if self.forward_executor is None:
            return
        self.forward_calculation_running = True
        future = self.forward_executor.submit(
            calculate_forward_snapshot,
            self.forward_specification,
            input_values,
        )

        def completed(done_future, number=request_number):
            try:
                result = done_future.result()
                error = None
            except Exception as exception:
                result = None
                error = str(exception)
            self.forward_bridge.completed.emit(number, result, error)

        future.add_done_callback(completed)

    def forward_calculation_finished(self, request_number, result, error):
        """Übernimmt nur ein aktuelles Ergebnis und startet danach den letzten Wunsch."""

        if self.forward_executor is None:
            return
        self.forward_calculation_running = False
        pending = self.pending_forward_request
        self.pending_forward_request = None
        if pending is not None:
            self.start_forward_calculation(*pending)
        if error is not None:
            self.status_label.setText(error)
            return
        # One worker completes requests in order. Display each finished result
        # even while a newer request is pending, so slow networks do not freeze
        # the outputs and working point until the slider is released.
        sums, values = result
        for neuron in self.network.get_neurons():
            if neuron.id not in values:
                continue
            neuron.sum_value = sums[neuron.id]
            neuron.output_value = values[neuron.id]
            if str(neuron.neuron_type.value).casefold() == "input":
                neuron.input_value = values[neuron.id]
        self.curves.update_outputs(values)
        self.update_forward_result_widgets()

    def update_forward_result_widgets(self):
        """Aktualisiert die sichtbaren Ausgaben mit dem fertigen Ergebnis."""

        try:
            for _proxy, controls, mapping in self.output_cards:
                raw_value = TrainingDataIO.unscale_value(
                    mapping["neuron"].output_value,
                    mapping["calibration"],
                    getattr(self.language, "text", None),
                )
                unit = str(mapping.get("unit") or "")
                display_value = (
                    mapping["neuron"].output_value
                    if controls.get("binary")
                    else raw_value
                )
                controls["value"].setText(
                    f"{format_number(display_value, 6)}"
                    if controls.get("binary")
                    else f"{format_application_output_value(raw_value)}"
                    f"{(' ' + unit) if unit else ''}"
                )
                card = controls.get("card")
                if isinstance(card, ExperimentCard) and not controls.get("binary"):
                    card.prepare_responsive_layout(card.width(), card.height())
                minimum, maximum = self.display_range(mapping)
                ratio = 0.0 if maximum <= minimum else (raw_value - minimum) / (maximum - minimum)
                binary = mapping.get("data_type") == "binary"
                active = mapping["neuron"].output_value > 0.5
                if controls["bar"] is not None:
                    controls["bar"].setValue(
                        round(max(0.0, min(1.0, ratio)) * 1000.0)
                    )
                if controls.get("vertical_bar") is not None:
                    controls["vertical_bar"].setValue(
                        round(max(0.0, min(1.0, ratio)) * 1000.0)
                    )
                if controls.get("binary_bar") is not None:
                    controls["binary_bar"].setValue(
                        round(max(0.0, min(1.0, mapping["neuron"].output_value)) * 1000.0)
                    )
                if controls["gauge"] is not None:
                    controls["gauge"].set_value(raw_value)
                color = "#00c853" if active else "#d91e18"
                border = "#008c3a" if active else "#9f1612"
                if binary:
                    border, color, _ = state_palette(self.color_settings, active, (border, color, ""))
                controls["led"].setStyleSheet(
                    f"background:{color}; border:1px solid {border}; border-radius:7px;"
                )
                if controls["state_label"] is not None:
                    controls["state_label"].setChecked(active)
                    controls["state_label"].setText(
                        self.tr("Ein", "On")
                    )
                    border, background, foreground = state_palette(
                        self.color_settings,
                        active,
                        ("", "", ""),
                    )
                    controls["state_label"].setStyleSheet(
                        f"QCheckBox {{ background:{background}; "
                        f"color:{foreground}; border:1px solid {border}; "
                        "border-radius:4px; }}"
                        if background else ""
                    )
                if binary:
                    uncertain = is_uncertain(mapping["neuron"].output_value, self.uncertainty_settings)
                    tooltip = warning_text(self.uncertainty_settings, self.language.current_language == "de")
                    controls["value"].setStyleSheet(warning_style(self.color_settings) if uncertain else "")
                    for widget in (controls["value"], controls["led"], controls["state_label"], controls["binary_bar"]):
                        widget.setToolTip(tooltip if uncertain else "")
                    if uncertain:
                        controls["state_label"].setText(
                            self.tr("⚠ Ein · Unklar", "⚠ On · Uncertain")
                        )
                        controls["state_label"].setStyleSheet(warning_style(self.color_settings))
                        controls["led"].setStyleSheet(warning_style(self.color_settings))
            if self.network_view_card is not None:
                self.network_view_card.widget().update_network_state()
            self.status_label.setText(self.project_status_text())
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))

    def change_mode(self, *_):
        if self.placement_items:
            self.cancel_element_placement()
        self.finish_nudge_history()
        self.edit_mode = self.mode_combo.currentData() == "edit"
        for proxy, controls, mapping in self.input_cards:
            proxy.set_editable(self.edit_mode)
            controls["card"].setEnabled(True)
            if mapping.get("data_type") == "binary":
                controls["editor"].setEnabled(not self.edit_mode)
        for proxy, controls, _mapping in self.output_cards:
            proxy.set_editable(self.edit_mode)
            controls["card"].setEnabled(True)
        for proxy in self.comment_cards:
            proxy.set_editable(self.edit_mode)
        for proxy in self.curves.proxies:
            proxy.set_editable(self.edit_mode)
        for item in self.shape_items:
            item.set_editable(self.edit_mode)
        if self.input_array_card is not None:
            self.input_array_card.set_editable(self.edit_mode)
            self.input_array_card.widget().set_input_enabled(not self.edit_mode)
        if self.network_view_card is not None:
            self.network_view_card.set_editable(self.edit_mode)
        self.view.setDragMode(
            QGraphicsView.DragMode.RubberBandDrag
            if self.edit_mode
            else QGraphicsView.DragMode.NoDrag
        )
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        if self.background_item is not None:
            self.background_item.set_editable(self.edit_mode)
        if not self.edit_mode:
            self.scene.clearSelection()
        for button in (
            self.load_image_button,
            self.background_color_button,
            self.add_comment_button,
            self.default_layout_button,
        ):
            button.setEnabled(self.edit_mode)
        self.add_comment_design_action.setEnabled(self.edit_mode)
        self.add_icon_action.setEnabled(self.edit_mode)
        self.load_image_action.setEnabled(self.edit_mode)
        self.background_color_action.setEnabled(self.edit_mode)
        self.grid_visible_action.setEnabled(self.edit_mode)
        self.grid_snap_action.setEnabled(self.edit_mode)
        self.grid_spacing_action.setEnabled(self.edit_mode)
        self.default_layout_action.setEnabled(self.edit_mode)
        for menu in (
            self.top_edit_menu,
            self.add_elements_menu,
            self.top_design_menu,
            self.top_arrange_menu,
        ):
            menu.menuAction().setEnabled(self.edit_mode)
        self.shape_elements_menu.menuAction().setEnabled(self.edit_mode)
        self.update_grid_visibility()
        self.update_element_actions()
        if self.edit_mode:
            self.update_selection_status()
        else:
            self.calculate()
            self.update_selection_status()
        self.update_selection_actions()
        self.update_history_buttons()

    def load_background_image(self):
        start_directory = self.initial_image_directory()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Grafik laden", "Load image"),
            start_directory,
            self.tr("Bilder (*.png *.jpg *.jpeg *.bmp)", "Images (*.png *.jpg *.jpeg *.bmp)"),
        )
        if not file_name:
            return
        if self.select_background_image(Path(file_name)):
            QSettings("NeuronNetz", "NeuronNetz").setValue(
                "graphical_experiment/last_image_directory",
                str(Path(file_name).resolve().parent),
            )

    def load_background_image_for_placement(self):
        """Lädt eine Grafik und übergibt sie zunächst an den Platzierungsmodus."""

        if not self.edit_mode:
            return
        start_directory = self.initial_image_directory()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Grafik laden", "Load image"),
            start_directory,
            self.tr(
                "Bilder (*.png *.jpg *.jpeg *.bmp)",
                "Images (*.png *.jpg *.jpeg *.bmp)",
            ),
        )
        if not file_name or not self.confirm_image_replacement():
            return
        image_path = Path(file_name)
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self.tr(
                    "Die Grafik konnte nicht geladen werden.",
                    "The image could not be loaded.",
                ),
            )
            return
        self.begin_history_action()
        self.background_relative_path = str(image_path.resolve())
        self.set_background_pixmap(pixmap)
        QSettings("NeuronNetz", "NeuronNetz").setValue(
            "graphical_experiment/last_image_directory",
            str(image_path.resolve().parent),
        )
        self.start_element_placement([self.background_item])

    def initial_image_directory(self):
        settings = QSettings("NeuronNetz", "NeuronNetz")
        remembered_value = str(settings.value(
            "graphical_experiment/last_image_directory", ""
        ) or "").strip()
        if remembered_value:
            remembered = Path(remembered_value)
            if remembered.is_dir():
                return str(remembered)
        if self.project_directory is not None:
            return str(self.project_directory)
        pictures = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.PicturesLocation
        )
        return pictures or ""

    @staticmethod
    def image_path_from_mime_data(mime_data):
        if not mime_data.hasUrls():
            return None
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".bmp"}:
                return path
        return None

    def confirm_image_replacement(self):
        if self.background_item is None:
            return True
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.tr(
                "Es ist bereits eine Hintergrundgrafik vorhanden. Möchten Sie sie ersetzen?",
                "A background image already exists. Do you want to replace it?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def select_background_image(self, image_path):
        if not self.confirm_image_replacement():
            return False
        image_path = Path(image_path)
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            QMessageBox.warning(
                self, self.windowTitle(), self.tr("Die Grafik konnte nicht geladen werden.", "The image could not be loaded.")
            )
            return False
        self.begin_history_action()
        self.background_relative_path = str(image_path.resolve())
        self.set_background_pixmap(pixmap)
        QSettings("NeuronNetz", "NeuronNetz").setValue(
            "graphical_experiment/last_image_directory",
            str(image_path.resolve().parent),
        )
        self.finish_history_action()
        return True

    def copy_selected_shapes(self):
        """Kopiert markierte Formen und Kommentare als Gestaltungselemente."""

        if not self.edit_mode:
            return
        shapes = [
            item for item in self.scene.selectedItems()
            if isinstance(item, DesignShapeItem)
        ]
        comments = [
            item for item in self.scene.selectedItems()
            if isinstance(item, MovableCardProxy) and item.card_role == "comment"
        ]
        curves = [p for p in self.selected_card_proxies() if p.card_role == "characteristic"]
        if not shapes and not comments and not curves:
            return
        payload = {
            "version": 1,
            "characteristics": [self.curves.data(p) for p in curves],
            "shapes": [item.to_data() for item in shapes],
            "comments": [
                self.comment_data_for_proxy(proxy) for proxy in comments
            ],
        }
        mime_data = QMimeData()
        mime_data.setData(
            self.SHAPE_CLIPBOARD_MIME,
            QByteArray(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
        )
        QApplication.clipboard().setMimeData(mime_data)

    def paste_clipboard_content(self, scene_position=None):
        """Fügt kopierte Elemente oder ein Bild über den Platzierungsmodus ein."""

        if not self.edit_mode:
            return
        mime_data = QApplication.clipboard().mimeData()
        if mime_data.hasFormat(self.SHAPE_CLIPBOARD_MIME):
            try:
                payload = json.loads(
                    bytes(mime_data.data(self.SHAPE_CLIPBOARD_MIME)).decode("utf-8")
                )
                shapes = payload.get("shapes", [])
                comments = payload.get("comments", [])
                curves = payload.get("characteristics", [])
            except (UnicodeDecodeError, ValueError, AttributeError):
                shapes = []
                comments = []
                curves = []
            valid_curves = [data for data in curves if isinstance(data, dict)] if isinstance(curves, list) else []
            valid_shapes = [data for data in shapes if isinstance(data, dict)]
            valid_comments = [
                data for data in comments if isinstance(data, dict)
            ]
            if valid_shapes or valid_comments or valid_curves:
                self.begin_history_action()
                self.scene.clearSelection()
                pasted_items = []
                for data in valid_curves:
                    pasted_items.append(self.curves.create(data))
                for data in valid_shapes:
                    copied = dict(data)
                    item = self.add_shape(
                        copied.get("type", "rectangle"),
                        QPointF(
                            float(copied.get("x", 0.0)),
                            float(copied.get("y", 0.0)),
                        ),
                        copied,
                        record_history=False,
                    )
                    if item is not None:
                        pasted_items.append(item)
                for data in valid_comments:
                    copied = dict(data)
                    proxy = self.create_comment_card(copied)
                    proxy.setPos(
                        float(copied.get("x", 0.0)),
                        float(copied.get("y", 0.0)),
                    )
                    pasted_items.append(proxy)
                if pasted_items:
                    self.start_element_placement(
                        pasted_items,
                        scene_position=scene_position,
                    )
                else:
                    self.active_history_state = None
                return
        self.paste_background_image(scene_position)

    def paste_background_image(self, scene_position=None):
        """Übernimmt Bilddaten oder eine kopierte Bilddatei aus der Zwischenablage."""

        if not self.edit_mode:
            return
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        image_path = self.image_path_from_mime_data(mime_data)
        if image_path is not None:
            pixmap = QPixmap(str(image_path))
        else:
            image = clipboard.image()
            if image.isNull():
                return
            pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return
        if not self.confirm_image_replacement():
            return
        self.begin_history_action()
        self.background_relative_path = (
            str(Path(image_path).resolve())
            if image_path is not None
            else "<clipboard>"
        )
        self.set_background_pixmap(pixmap)
        self.start_element_placement(
            [self.background_item],
            scene_position=scene_position,
        )

    def set_background_pixmap(self, pixmap):
        if self.background_item is not None:
            self.scene.removeItem(self.background_item)
        self.background_item = ResizableBackgroundItem(pixmap)
        self.scene.addItem(self.background_item)
        scale = min(600.0 / max(1, pixmap.width()), 500.0 / max(1, pixmap.height()), 1.0)
        self.background_item.setScale(scale)
        self.background_item.setPos(
            (self.CANVAS_WIDTH - pixmap.width() * scale) / 2.0,
            (self.CANVAS_HEIGHT - pixmap.height() * scale) / 2.0,
        )
        self.background_item.setSelected(True)
        self.background_item.set_editable(self.edit_mode)

    def delete_selected_image(self):
        if not self.edit_mode:
            return
        selected = [
            proxy for proxy in self.selected_card_proxies()
            if not proxy.locked
        ]
        selected_shapes = [
            item for item in self.scene.selectedItems()
            if isinstance(item, DesignShapeItem) and not item.locked
        ]
        background_selected = (
            self.background_item is not None
            and self.background_item.isSelected()
            and not self.background_item.locked
        )
        if not selected and not selected_shapes and not background_selected:
            return
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.tr(
                "Möchten Sie die ausgewählten Elemente aus der Gestaltung entfernen?",
                "Do you want to remove the selected elements from the design?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.begin_history_action()
        for proxy in list(selected):
            if proxy.card_role == "comment" and proxy in self.comment_cards:
                self.scene.removeItem(proxy)
                self.comment_cards.remove(proxy)
            elif proxy.card_role in ("input", "output", "input_array", "network_view", "characteristic"):
                proxy.saved_design_position = QPointF(proxy.pos())
                proxy.setVisible(False)
                proxy.setSelected(False)
        for item in list(selected_shapes):
            if item in self.shape_items:
                self.scene.removeItem(item)
                self.shape_items.remove(item)
        if background_selected and self.background_item is not None:
            self.scene.removeItem(self.background_item)
            self.background_item = None
            self.background_relative_path = ""
        self.finish_history_action()
        self.update_element_actions()

    def remove_background_image(self):
        if self.background_item is None or self.background_item.locked:
            return
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.tr(
                "Möchten Sie die Hintergrundgrafik wirklich aus der Gestaltung entfernen?",
                "Do you really want to remove the background image from the design?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.begin_history_action()
        if self.background_item is not None:
            self.scene.removeItem(self.background_item)
            self.background_item = None
        self.background_relative_path = ""
        self.finish_history_action()

    def choose_background_color(self):
        color = choose_color(
            QColor(self.background_color),
            self,
            self.tr("Hintergrundfarbe", "Background color"),
        )
        if not color.isValid():
            return
        self.begin_history_action()
        self.background_color = color.name()
        self.scene.setBackgroundBrush(color)
        self.finish_history_action()

    def update_grid_visibility(self):
        if self.grid_item is not None:
            self.grid_item.set_spacing(self.grid_spacing)
            self.grid_item.setVisible(self.grid_enabled and self.edit_mode)
            self.grid_item.update()
        if hasattr(self, "grid_snap_action"):
            self.grid_snap_action.setEnabled(self.edit_mode and self.grid_enabled)

    def grid_snap_active(self):
        return bool(
            self.edit_mode
            and self.grid_enabled
            and self.grid_snap_enabled
            and self.grid_spacing > 0
        )

    def snap_scene_position(self, position):
        point = QPointF(position)
        if not self.grid_snap_active():
            return point
        spacing = float(self.grid_spacing)
        return QPointF(
            round(point.x() / spacing) * spacing,
            round(point.y() / spacing) * spacing,
        )

    def set_grid_enabled(self, enabled, record=True):
        enabled = bool(enabled)
        if enabled == self.grid_enabled:
            self.update_grid_visibility()
            return
        if record:
            self.begin_history_action()
        self.grid_enabled = enabled
        self.update_grid_visibility()
        if record:
            self.finish_history_action()

    def set_grid_snap_enabled(self, enabled, record=True):
        enabled = bool(enabled)
        if enabled == self.grid_snap_enabled:
            return
        if record:
            self.begin_history_action()
        self.grid_snap_enabled = enabled
        if record:
            self.finish_history_action()

    def choose_grid_spacing(self):
        spacing, accepted = QInputDialog.getInt(
            self,
            self.tr("Rasterabstand", "Grid spacing"),
            self.tr("Abstand in Pixeln:", "Spacing in pixels:"),
            self.grid_spacing,
            5,
            200,
            1,
        )
        if not accepted or spacing == self.grid_spacing:
            return
        self.begin_history_action()
        self.grid_spacing = int(spacing)
        self.update_grid_visibility()
        self.finish_history_action()

    def view_show_all(self):
        self.view.show_all()

    def update_zoom_label(self, percent):
        value = max(1, int(round(float(percent))))
        self.zoom_label.setText(
            self.tr(f"Zoom: {value} %", f"Zoom: {value}%")
        )

    def reset_to_default_layout(self):
        if not self.edit_mode:
            return
        answer = QMessageBox.question(
            self,
            self.tr("Standardlayout", "Default layout"),
            self.tr(
                "Möchten Sie die Gestaltung wirklich auf das Standardlayout zurücksetzen?",
                "Do you really want to reset the design to the default layout?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.begin_history_action()
        current = self.capture_history_state()
        target = {
            "layout": json.loads(json.dumps(self.default_history_state["layout"])),
            "pixmap": (
                QPixmap(current["pixmap"])
                if current["pixmap"] is not None
                else None
            ),
            "pixmap_key": current["pixmap_key"],
        }
        target["layout"]["background"] = current["layout"].get("background")
        self.apply_history_state(target)
        self.finish_history_action()
        self.view.show_all()

    def card_key(self, role, mapping):
        return f"{role}:{mapping['neuron'].id}"

    def capture_history_state(self):
        pixmap = None
        pixmap_key = 0
        if self.background_item is not None:
            pixmap = QPixmap(self.background_item.pixmap())
            pixmap_key = int(self.background_item.pixmap().cacheKey())
        return {
            "layout": json.loads(json.dumps(self.layout_state())),
            "pixmap": pixmap,
            "pixmap_key": pixmap_key,
        }

    @staticmethod
    def history_states_equal(first, second):
        return (
            first["layout"] == second["layout"]
            and first["pixmap_key"] == second["pixmap_key"]
        )

    def begin_history_action(self):
        if self.nudge_history_active:
            self.finish_nudge_history()
        if self.restoring_history or self.active_history_state is not None:
            return
        self.active_history_state = self.capture_history_state()

    def finish_history_action(self):
        if self.restoring_history or self.active_history_state is None:
            return
        before = self.active_history_state
        self.active_history_state = None
        after = self.capture_history_state()
        if self.history_states_equal(before, after):
            return
        self.undo_stack.append(before)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_history_buttons()
        self.update_save_button()

    def update_history_buttons(self):
        self.undo_button.setEnabled(self.edit_mode and bool(self.undo_stack))
        self.redo_button.setEnabled(self.edit_mode and bool(self.redo_stack))
        self.undo_action.setEnabled(self.edit_mode and bool(self.undo_stack))
        self.redo_action.setEnabled(self.edit_mode and bool(self.redo_stack))

    def update_save_button(self):
        can_save = self.is_dirty()
        self.save_button.setEnabled(can_save)
        self.save_shortcut.setEnabled(can_save)

    @staticmethod
    def apply_card_geometry(proxy, geometry):
        if isinstance(geometry, list) and len(geometry) == 2:
            proxy.setPos(float(geometry[0]), float(geometry[1]))
            return
        if not isinstance(geometry, dict):
            return
        proxy.setVisible(bool(geometry.get("visible", True)))
        proxy.setPos(float(geometry.get("x", proxy.pos().x())),
                     float(geometry.get("y", proxy.pos().y())))
        if "width" in geometry and "height" in geometry:
            proxy.set_card_size(
                float(geometry["width"]), float(geometry["height"])
            )
        if "color" in geometry:
            proxy.widget().set_card_color(str(geometry["color"]))
        proxy.widget().set_card_transparent(
            bool(geometry.get("transparent", False))
        )
        if "layer" in geometry:
            proxy.setZValue(float(geometry["layer"]))
        proxy.set_locked(bool(geometry.get("locked", False)))
        if not proxy.isVisible():
            proxy.saved_design_position = QPointF(proxy.pos())

    def apply_history_state(self, snapshot):
        self.restoring_history = True
        try:
            document = snapshot["layout"]
            for _proxy, controls, mapping in self.input_cards:
                self.set_input_display_mode(
                    controls,
                    document.get("input_displays", {}).get(
                        self.card_key("input", mapping),
                        controls["display_mode"],
                    ),
                )
            for _proxy, controls, mapping in self.output_cards:
                self.set_output_display_mode(
                    controls,
                    document.get("output_displays", {}).get(
                        self.card_key("output", mapping), controls["display_mode"]
                    ),
                )

            cards = document.get("cards", {})
            for role, items in (("input", self.input_cards), ("output", self.output_cards)):
                for proxy, _controls, mapping in items:
                    self.apply_card_geometry(
                        proxy, cards.get(self.card_key(role, mapping))
                    )
            self.restore_comments(document.get("comments", []))
            self.curves.restore(document.get("characteristics", []))
            self.restore_shapes(document.get("shapes", []))
            if self.input_array_card is not None:
                self.apply_card_geometry(
                    self.input_array_card, document.get("input_array_element")
                )
                array_state = document.get("input_array_element")
                if isinstance(array_state, dict):
                    self.input_array_card.widget().set_title(
                        array_state.get(
                            "title", self.tr("Eingabemuster", "Input pattern")
                        )
                    )
            if self.network_view_card is not None:
                self.apply_card_geometry(
                    self.network_view_card, document.get("network_view_element")
                )
                network_state = document.get("network_view_element")
                if isinstance(network_state, dict):
                    self.network_view_card.widget().set_show_input_values(
                        bool(network_state.get("show_input_values", False))
                    )
                    self.network_view_card.widget().set_show_output_values(
                        bool(network_state.get("show_output_values", True))
                    )
            self.restore_binary_output_intermediate_values(document)
            self.apply_saved_input_values(document.get("input_values", {}))

            self.background_color = str(
                document.get("background_color", "#f5f5f5")
            )
            self.scene.setBackgroundBrush(QColor(self.background_color))
            self.grid_enabled = bool(document.get("grid_enabled", False))
            self.grid_snap_enabled = bool(
                document.get("grid_snap_enabled", self.grid_enabled)
            )
            self.grid_spacing = max(5, int(document.get("grid_spacing", 20)))
            self.grid_visible_action.blockSignals(True)
            self.grid_visible_action.setChecked(self.grid_enabled)
            self.grid_visible_action.blockSignals(False)
            self.grid_snap_action.blockSignals(True)
            self.grid_snap_action.setChecked(self.grid_snap_enabled)
            self.grid_snap_action.blockSignals(False)
            self.update_grid_visibility()
            background = document.get("background")
            if not isinstance(background, dict) or snapshot["pixmap"] is None:
                if self.background_item is not None:
                    self.scene.removeItem(self.background_item)
                    self.background_item = None
                self.background_relative_path = ""
            else:
                self.background_relative_path = str(background.get("path", ""))
                self.set_background_pixmap(QPixmap(snapshot["pixmap"]))
                self.background_item.setPos(
                    float(background.get("x", 0.0)),
                    float(background.get("y", 0.0)),
                )
                self.background_item.setScale(
                    max(0.05, float(background.get("scale", 1.0)))
                )
                self.background_item.set_locked(
                    bool(background.get("locked", False))
                )
                self.background_item.setSelected(False)
            self.scene.clearSelection()
            self.update_selection_actions()
            self.update_element_actions()
        finally:
            self.restoring_history = False

    def undo_design_change(self):
        self.finish_nudge_history()
        if not self.edit_mode or not self.undo_stack:
            return
        current = self.capture_history_state()
        target = self.undo_stack.pop()
        self.redo_stack.append(current)
        self.apply_history_state(target)
        self.update_history_buttons()
        self.update_save_button()

    def redo_design_change(self):
        self.finish_nudge_history()
        if not self.edit_mode or not self.redo_stack:
            return
        current = self.capture_history_state()
        target = self.redo_stack.pop()
        self.undo_stack.append(current)
        self.apply_history_state(target)
        self.update_history_buttons()
        self.update_save_button()

    def layout_state(self):
        """Liefert den vollständigen, vergleichbaren Gestaltungszustand."""

        cards = {}
        for role, items in (("input", self.input_cards), ("output", self.output_cards)):
            for proxy, controls, mapping in items:
                geometry = {
                    "x": proxy.pos().x(),
                    "y": proxy.pos().y(),
                    "width": proxy.widget().width(),
                    "height": proxy.widget().height(),
                    "color": proxy.widget().card_color.name(),
                    "transparent": proxy.widget().card_transparent,
                    "layer": proxy.zValue(),
                    "visible": proxy.isVisible(),
                    "locked": proxy.locked,
                }
                if role == "output" and controls.get("binary"):
                    geometry["binary_intermediate"] = bool(
                        controls["card"].binary_intermediate_enabled
                    )
                cards[self.card_key(role, mapping)] = geometry
        background = None
        if self.background_item is not None:
            background = {
                "path": self.background_relative_path,
                "x": self.background_item.pos().x(),
                "y": self.background_item.pos().y(),
                "scale": self.background_item.scale(),
                "locked": self.background_item.locked,
            }
        comments = []
        for proxy in self.comment_cards:
            card = proxy.widget()
            data = dict(card.comment_data)
            data.update({
                "x": proxy.pos().x(),
                "y": proxy.pos().y(),
                "width": card.width(),
                "height": card.height(),
                "color": card.card_color.name(),
                "transparent": card.card_transparent,
                "layer": proxy.zValue(),
                "locked": proxy.locked,
            })
            comments.append(data)
        input_array_element = None
        if self.input_array_card is not None:
            proxy = self.input_array_card
            input_array_element = {
                "x": proxy.pos().x(),
                "y": proxy.pos().y(),
                "width": proxy.widget().width(),
                "height": proxy.widget().height(),
                "color": proxy.widget().card_color.name(),
                "transparent": proxy.widget().card_transparent,
                "layer": proxy.zValue(),
                "visible": proxy.isVisible(),
                "title": proxy.widget().custom_title,
                "locked": proxy.locked,
            }
        network_view_element = None
        if self.network_view_card is not None:
            proxy = self.network_view_card
            network_view_element = {
                "x": proxy.pos().x(),
                "y": proxy.pos().y(),
                "width": proxy.widget().width(),
                "height": proxy.widget().height(),
                "color": proxy.widget().card_color.name(),
                "transparent": proxy.widget().card_transparent,
                "layer": proxy.zValue(),
                "visible": proxy.isVisible(),
                "show_input_values": proxy.widget().show_input_values,
                "show_output_values": proxy.widget().show_output_values,
                "locked": proxy.locked,
            }
        return {
            "version": 11,
            "characteristics": [self.curves.data(p) for p in self.curves.proxies if p.isVisible()],
            "cards": cards,
            "input_values": {
                str(mapping["neuron"].id): float(
                    self.input_value(controls, mapping)
                )
                for _proxy, controls, mapping in self.input_cards
            },
            "comments": comments,
            "shapes": [item.to_data() for item in self.shape_items],
            "input_array_element": input_array_element,
            "network_view_element": network_view_element,
            "background": background,
            "background_color": self.background_color,
            "grid_enabled": self.grid_enabled,
            "grid_snap_enabled": self.grid_snap_enabled,
            "grid_spacing": self.grid_spacing,
            "output_displays": {
                self.card_key("output", mapping): controls["display_mode"]
                for _proxy, controls, mapping in self.output_cards
            },
            "input_displays": {
                self.card_key("input", mapping): controls["display_mode"]
                for _proxy, controls, mapping in self.input_cards
                if not controls.get("binary")
            },
        }

    def is_dirty(self):
        if self.input_state_dirty:
            return True
        return self.saved_state is not None and self.layout_state() != self.saved_state

    def save_layout(self):
        self.finish_nudge_history()
        if self.layout_file is None:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self.tr(
                    "Die Gestaltung kann erst gespeichert werden, nachdem das Projekt gespeichert wurde.",
                    "The design can be saved after the project itself has been saved.",
                ),
            )
            return False
        if self.background_item is not None:
            target = self.project_directory / "Experimentbild.png"
            if not self.background_item.pixmap().save(str(target), "PNG"):
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    self.tr("Das Experimentbild konnte nicht gespeichert werden.", "The experiment image could not be saved."),
                )
                return False
            self.background_relative_path = "Experimentbild.png"
        document = self.layout_state()
        document["window_size"] = {
            "width": int(self.width()),
            "height": int(self.height()),
        }
        try:
            self.layout_file.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(self.layout_file, document)
        except OSError:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self.tr("Die Gestaltung konnte nicht gespeichert werden.", "The design could not be saved."),
            )
            return False
        self.saved_state = self.layout_state()
        self.input_state_dirty = False
        self.update_save_button()
        self.status_label.setText(
            self.tr("Die Gestaltung wurde gespeichert.", "The design was saved.")
        )
        return True

    def load_layout(self):
        if self.layout_file is None or not self.layout_file.exists():
            return
        try:
            document = json.loads(self.layout_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(document, dict):
            return
        window_size = document.get("window_size")
        if isinstance(window_size, dict):
            try:
                width = int(window_size.get("width", 0))
                height = int(window_size.get("height", 0))
            except (TypeError, ValueError):
                width = 0
                height = 0
            if width > 0 and height > 0:
                self.project_window_size = (width, height)
        self.background_color = str(document.get("background_color", "#f5f5f5"))
        self.scene.setBackgroundBrush(QColor(self.background_color))
        self.grid_enabled = bool(document.get("grid_enabled", False))
        self.grid_snap_enabled = bool(
            document.get("grid_snap_enabled", self.grid_enabled)
        )
        self.grid_spacing = max(5, int(document.get("grid_spacing", 20)))
        self.grid_visible_action.blockSignals(True)
        self.grid_visible_action.setChecked(self.grid_enabled)
        self.grid_visible_action.blockSignals(False)
        self.grid_snap_action.blockSignals(True)
        self.grid_snap_action.setChecked(self.grid_snap_enabled)
        self.grid_snap_action.blockSignals(False)
        self.update_grid_visibility()
        input_displays = document.get("input_displays", {})
        for _proxy, controls, mapping in self.input_cards:
            self.set_input_display_mode(
                controls,
                input_displays.get(self.card_key("input", mapping), "slider"),
            )
        output_displays = document.get("output_displays", {})
        for _proxy, controls, mapping in self.output_cards:
            self.set_output_display_mode(
                controls,
                output_displays.get(self.card_key("output", mapping), "bar"),
            )
        cards = document.get("cards", {})
        for role, items in (("input", self.input_cards), ("output", self.output_cards)):
            for proxy, _controls, mapping in items:
                self.apply_card_geometry(
                    proxy, cards.get(self.card_key(role, mapping))
                )
        self.restore_comments(document.get("comments", []))
        self.curves.restore(document.get("characteristics", []))
        self.restore_shapes(document.get("shapes", []))
        if self.input_array_card is not None:
            array_geometry = document.get("input_array_element")
            if isinstance(array_geometry, dict):
                self.apply_card_geometry(self.input_array_card, array_geometry)
                self.input_array_card.widget().set_title(
                    array_geometry.get(
                        "title", self.tr("Eingabemuster", "Input pattern")
                    )
                )
            else:
                self.input_array_card.setVisible(False)
        if self.network_view_card is not None:
            network_geometry = document.get("network_view_element")
            if isinstance(network_geometry, dict):
                self.apply_card_geometry(self.network_view_card, network_geometry)
                self.network_view_card.widget().set_show_input_values(
                    bool(network_geometry.get("show_input_values", False))
                )
                self.network_view_card.widget().set_show_output_values(
                    bool(network_geometry.get("show_output_values", True))
                )
            else:
                self.network_view_card.setVisible(False)
        self.restore_binary_output_intermediate_values(document)
        self.apply_saved_input_values(document.get("input_values", {}))
        background = document.get("background")
        if isinstance(background, dict) and background.get("path"):
            image_path = Path(background["path"])
            if not image_path.is_absolute() and self.project_directory is not None:
                image_path = self.project_directory / image_path
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                self.background_relative_path = str(background["path"])
                self.set_background_pixmap(pixmap)
                self.background_item.setPos(float(background.get("x", 0.0)), float(background.get("y", 0.0)))
                self.background_item.setScale(max(0.05, float(background.get("scale", 1.0))))
                self.background_item.set_locked(bool(background.get("locked", False)))
        self.update_element_actions()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.view_show_all)

    def restore_window_geometry(self):
        settings = QSettings("NeuronNetz", "NeuronNetz")
        geometry = settings.value("graphical_experiment/window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        desired_width, desired_height = self.project_window_size or (1100, 720)
        screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            desired_width = min(max(700, desired_width), available.width())
            desired_height = min(max(450, desired_height), available.height())
        self.resize(desired_width, desired_height)
        frame = self.frameGeometry()
        screens = QApplication.screens()
        if screens and not any(
            screen.availableGeometry().intersects(frame) for screen in screens
        ):
            available = QApplication.primaryScreen().availableGeometry()
            frame.moveCenter(available.center())
            self.move(frame.topLeft())

    def save_window_geometry(self):
        QSettings("NeuronNetz", "NeuronNetz").setValue(
            "graphical_experiment/window_geometry", self.saveGeometry()
        )
        if self.layout_file is None or not self.layout_file.exists():
            return
        try:
            document = json.loads(self.layout_file.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                return
            document["window_size"] = {
                "width": int(self.width()),
                "height": int(self.height()),
            }
            write_json_atomic(self.layout_file, document)
        except (OSError, ValueError):
            pass

    def closeEvent(self, event):
        if self.placement_items:
            self.cancel_element_placement()
        if self.confirm_close():
            self.save_window_geometry()
            self.stop_forward_executor()
            event.accept()
        else:
            event.ignore()

    def accept(self):
        if self.placement_items:
            self.cancel_element_placement()
        if self.confirm_close():
            self.save_window_geometry()
            self.stop_forward_executor()
            super().accept()

    def reject(self):
        if self.placement_items:
            self.cancel_element_placement()
        if self.confirm_close():
            self.save_window_geometry()
            self.stop_forward_executor()
            super().reject()

    def stop_forward_executor(self):
        """Beendet den Rechendienst beim Schließen des Fensters ohne Wartezeit."""

        self.curves.close()
        input_array_proxy = getattr(self, "input_array_card", None)
        input_array_card = (
            input_array_proxy.widget()
            if input_array_proxy is not None
            else None
        )
        paint_controller = getattr(
            input_array_card, "paint_controller", None
        )
        if paint_controller is not None:
            paint_controller.deactivate()

        executor = getattr(self, "forward_executor", None)
        if executor is None:
            return
        self.forward_executor = None
        self.pending_forward_request = None
        executor.shutdown(wait=False, cancel_futures=True)

    def confirm_close(self):
        if not self.is_dirty():
            return True
        box = QMessageBox(self)
        box.setWindowTitle(self.tr("Gestaltung geändert", "Design changed"))
        box.setText(self.tr(
            "Die Gestaltung wurde geändert. Möchten Sie die Änderungen speichern?",
            "The design has changed. Do you want to save the changes?",
        ))
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        if result == QMessageBox.StandardButton.Save:
            return self.save_layout()
        return result == QMessageBox.StandardButton.Discard
