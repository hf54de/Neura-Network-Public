# -------------------------------------------------------------------------------------------------
# Datei: analysisplot.py
# Zweck: Erstellt Diagramme für Test-, Analyse- und Vergleichsergebnisse.
# Letzte Änderung: 04.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from language import LanguageManager


class SollIstPlot(QWidget):
    """Kompaktes interaktives Soll-Ist-Diagramm ohne externe Abhängigkeiten."""

    recordActivated = Signal(str, int)

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.rows = []
        self.binary = False
        self.unit = ""
        self.tolerance = 0.0
        self.show_tolerance = False
        self.highlighted_record = None
        self.hovered_record = None
        self.screen_points = []
        self.view_range = None
        self.dragging_plot = False
        self.last_drag_position = None
        self.setMouseTracking(True)
        self.setMinimumHeight(330)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_rows(self, rows, binary=False, unit=""):
        self.rows = list(rows)
        self.binary = bool(binary)
        self.unit = str(unit or "")
        self.highlighted_record = None
        self.hovered_record = None
        self.reset_view()
        self.update()

    def highlight_record(self, record, source_kind=None):
        self.highlighted_record = (
            (str(source_kind or ""), int(record))
            if record is not None else None
        )
        self.update()

    def set_tolerance(self, value, visible=False):
        self.tolerance = max(0.0, float(value or 0.0))
        self.show_tolerance = bool(visible) and not self.binary
        self.update()

    def plot_rect(self):
        return QRectF(62, 28, max(80, self.width() - 92), max(80, self.height() - 82))

    def value_range(self):
        if self.binary:
            return -0.08, 1.08
        values = [float(row[key]) for row in self.rows for key in ("target", "actual")]
        if not values:
            return 0.0, 1.0
        minimum, maximum = min(values), max(values)
        if math.isclose(minimum, maximum):
            padding = max(1.0, abs(minimum) * 0.1)
        else:
            padding = (maximum - minimum) * 0.08
        return minimum - padding, maximum + padding

    def current_view_range(self):
        if self.view_range is not None:
            return self.view_range
        minimum, maximum = self.value_range()
        return minimum, maximum, minimum, maximum

    @staticmethod
    def bounded_interval(minimum, maximum, base_minimum, base_maximum):
        """Hält einen vergrößerten Ausschnitt innerhalb des Gesamtbereichs."""

        span = maximum - minimum
        base_span = base_maximum - base_minimum
        if span >= base_span:
            return base_minimum, base_maximum
        if minimum < base_minimum:
            maximum += base_minimum - minimum
            minimum = base_minimum
        if maximum > base_maximum:
            minimum -= maximum - base_maximum
            maximum = base_maximum
        return minimum, maximum

    def reset_view(self):
        """Zeigt wieder den vollständigen Wertebereich aller Punkte."""

        self.view_range = None
        self.dragging_plot = False
        self.last_drag_position = None
        self.hovered_record = None
        self.unsetCursor()
        QToolTip.hideText()
        self.update()

    def map_point(self, target, actual, rect, x_minimum, x_maximum,
                  y_minimum=None, y_maximum=None):
        y_minimum = x_minimum if y_minimum is None else y_minimum
        y_maximum = x_maximum if y_maximum is None else y_maximum
        x_span = max(1e-12, x_maximum - x_minimum)
        y_span = max(1e-12, y_maximum - y_minimum)
        x = rect.left() + (float(target) - x_minimum) / x_span * rect.width()
        y = rect.bottom() - (float(actual) - y_minimum) / y_span * rect.height()
        return QPointF(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        rect = self.plot_rect()
        x_minimum, x_maximum, y_minimum, y_maximum = self.current_view_range()
        painter.setPen(QPen(QColor("#9aa7b2"), 1))
        painter.drawRect(rect)

        if self.binary and self.view_range is None:
            x_ticks = y_ticks = (0.0, 0.5, 1.0)
        else:
            x_ticks = tuple(
                x_minimum + (x_maximum - x_minimum) * index / 5
                for index in range(6)
            )
            y_ticks = tuple(
                y_minimum + (y_maximum - y_minimum) * index / 5
                for index in range(6)
            )

        for x_value in x_ticks:
            x = self.map_point(
                x_value, y_minimum, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            ).x()
            painter.setPen(QPen(QColor("#e3e8ec"), 1))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.setPen(QColor("#4f5962"))
            painter.drawText(QRectF(x - 35, rect.bottom() + 5, 70, 20), Qt.AlignmentFlag.AlignHCenter, f"{x_value:.4g}")

        for y_value in y_ticks:
            y = self.map_point(
                x_minimum, y_value, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            ).y()
            painter.setPen(QPen(QColor("#e3e8ec"), 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QColor("#4f5962"))
            painter.drawText(QRectF(2, y - 10, 54, 20), Qt.AlignmentFlag.AlignRight, f"{y_value:.4g}")

        if self.show_tolerance and self.tolerance > 0.0:
            painter.save()
            painter.setClipRect(rect)
            upper_start = self.map_point(
                x_minimum, x_minimum + self.tolerance, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            )
            upper_end = self.map_point(
                x_maximum, x_maximum + self.tolerance, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            )
            lower_start = self.map_point(
                x_minimum, x_minimum - self.tolerance, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            )
            lower_end = self.map_point(
                x_maximum, x_maximum - self.tolerance, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(67, 160, 105, 38))
            painter.drawPolygon(
                QPolygonF([upper_start, upper_end, lower_end, lower_start])
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(67, 145, 96, 150), 1))
            painter.drawLine(upper_start, upper_end)
            painter.drawLine(lower_start, lower_end)
            painter.restore()

        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor("#68737d"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(
            self.map_point(x_minimum, x_minimum, rect, x_minimum, x_maximum,
                           y_minimum, y_maximum),
            self.map_point(x_maximum, x_maximum, rect, x_minimum, x_maximum,
                           y_minimum, y_maximum),
        )

        if self.binary:
            decision_x = self.map_point(0.5, y_minimum, rect, x_minimum,
                                        x_maximum, y_minimum, y_maximum).x()
            decision_y = self.map_point(x_minimum, 0.5, rect, x_minimum,
                                        x_maximum, y_minimum, y_maximum).y()
            painter.setPen(QPen(QColor("#8a949d"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(
                QPointF(decision_x, rect.top()),
                QPointF(decision_x, rect.bottom()),
            )
            painter.drawLine(
                QPointF(rect.left(), decision_y),
                QPointF(rect.right(), decision_y),
            )
        painter.restore()

        painter.setPen(QColor("#243746"))
        painter.drawText(QRectF(rect.left(), rect.bottom() + 29, rect.width(), 22), Qt.AlignmentFlag.AlignCenter, self.t("analysis.plot.target_axis"))
        painter.save()
        painter.translate(18, rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-rect.height() / 2, -12, rect.height(), 24), Qt.AlignmentFlag.AlignCenter, self.t("analysis.plot.actual_axis"))
        painter.restore()

        if self.binary:
            painter.setPen(QColor("#5b6570"))
            threshold = 0.5
            quadrants = (
                (self.t("analysis.binary.true_off"),
                 x_minimum, min(x_maximum, threshold),
                 y_minimum, min(y_maximum, threshold)),
                (self.t("analysis.binary.false_on"),
                 x_minimum, min(x_maximum, threshold),
                 max(y_minimum, threshold), y_maximum),
                (self.t("analysis.binary.false_off"),
                 max(x_minimum, threshold), x_maximum,
                 y_minimum, min(y_maximum, threshold)),
                (self.t("analysis.binary.true_on"),
                 max(x_minimum, threshold), x_maximum,
                 max(y_minimum, threshold), y_maximum),
            )
            painter.save()
            painter.setClipRect(rect)
            for label, left, right, bottom, top in quadrants:
                if right <= left or top <= bottom:
                    continue
                center = self.map_point(
                    (left + right) / 2,
                    (bottom + top) / 2,
                    rect,
                    x_minimum,
                    x_maximum,
                    y_minimum,
                    y_maximum,
                )
                painter.drawText(
                    QRectF(center.x() - 65, center.y() - 10, 130, 20),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
            painter.restore()

        source_kinds = {str(row.get("source_kind") or "") for row in self.rows}
        if len(source_kinds) > 1:
            legend_x = rect.right() - 185
            for offset, (kind, color, label_key) in enumerate((
                ("training", "#1676b8", "analysis.plot.legend.training"),
                ("test", "#e07a16", "analysis.plot.legend.test"),
            )):
                if kind not in source_kinds:
                    continue
                y = rect.top() + 13 + offset * 22
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color))
                painter.drawEllipse(QPointF(legend_x, y), 5, 5)
                painter.setPen(QColor("#243746"))
                painter.drawText(QPointF(legend_x + 11, y + 5), self.t(label_key))

        self.screen_points = []
        hovered_point = None
        hovered_row = None
        painter.save()
        painter.setClipRect(rect.adjusted(-6, -6, 6, 6))
        for row in self.rows:
            point = self.map_point(
                row["target"], row["actual"], rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            )
            row_key = (str(row.get("source_kind") or ""), int(row["record"]))
            highlighted = row_key == self.highlighted_record
            outside_tolerance = (
                self.show_tolerance
                and not self.binary
                and abs(float(row["actual"]) - float(row["target"]))
                > self.tolerance
            )
            if outside_tolerance or row.get("binary_error"):
                color = QColor("#d02020")
            elif row.get("source_kind") == "test":
                color = QColor("#e07a16")
            else:
                color = QColor("#1676b8")
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(color)
            radius = 7 if highlighted else 4.5
            painter.drawEllipse(point, radius, radius)
            if highlighted:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#f0a000"), 2))
                painter.drawEllipse(point, 10, 10)
            if rect.adjusted(-11, -11, 11, 11).contains(point):
                self.screen_points.append((point, row))
                row_key = (str(row.get("source_kind") or ""), int(row["record"]))
                if row_key == self.hovered_record:
                    hovered_point = point
                    hovered_row = row
        painter.restore()

        if hovered_point is not None and hovered_row is not None:
            painter.save()
            painter.setClipRect(rect)
            painter.setPen(QPen(QColor("#4f788f"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(
                QPointF(rect.left(), hovered_point.y()),
                hovered_point,
            )
            painter.drawLine(
                hovered_point,
                QPointF(hovered_point.x(), rect.bottom()),
            )
            painter.restore()

            suffix = f" {self.unit}" if self.unit else ""
            x_text = f"{hovered_row['target']:.6g}{suffix}"
            y_text = f"{hovered_row['actual']:.6g}{suffix}"
            painter.setPen(QPen(QColor("#4f788f"), 1))
            painter.setBrush(QColor("#eef5f8"))
            x_label = QRectF(
                hovered_point.x() - 43,
                rect.bottom() + 4,
                86,
                20,
            )
            y_label = QRectF(1, hovered_point.y() - 10, 58, 20)
            painter.drawRoundedRect(x_label, 3, 3)
            painter.drawRoundedRect(y_label, 3, 3)
            painter.drawText(x_label, Qt.AlignmentFlag.AlignCenter, x_text)
            painter.drawText(y_label, Qt.AlignmentFlag.AlignCenter, y_text)

    def nearest_row(self, position, maximum_distance=11.0):
        nearest = None
        best = maximum_distance
        for point, row in self.screen_points:
            distance = math.hypot(position.x() - point.x(), position.y() - point.y())
            if distance <= best:
                best = distance
                nearest = row
        return nearest

    def mouseMoveEvent(self, event):
        if self.dragging_plot and self.last_drag_position is not None:
            if self.hovered_record is not None:
                self.hovered_record = None
            rect = self.plot_rect()
            position = event.position()
            delta = position - self.last_drag_position
            x_minimum, x_maximum, y_minimum, y_maximum = self.current_view_range()
            x_shift = delta.x() / max(1.0, rect.width()) * (x_maximum - x_minimum)
            y_shift = delta.y() / max(1.0, rect.height()) * (y_maximum - y_minimum)
            base_minimum, base_maximum = self.value_range()
            new_x_minimum, new_x_maximum = self.bounded_interval(
                x_minimum - x_shift,
                x_maximum - x_shift,
                base_minimum,
                base_maximum,
            )
            new_y_minimum, new_y_maximum = self.bounded_interval(
                y_minimum + y_shift,
                y_maximum + y_shift,
                base_minimum,
                base_maximum,
            )
            self.view_range = (
                new_x_minimum,
                new_x_maximum,
                new_y_minimum,
                new_y_maximum,
            )
            self.last_drag_position = position
            QToolTip.hideText()
            self.update()
            return

        row = self.nearest_row(event.position())
        if row is None:
            QToolTip.hideText()
            if self.hovered_record is not None:
                self.hovered_record = None
                self.update()
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.plot_rect().contains(event.position())
                else Qt.CursorShape.ArrowCursor
            )
            return
        row_key = (str(row.get("source_kind") or ""), int(row["record"]))
        if row_key != self.hovered_record:
            self.hovered_record = row_key
            self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        suffix = f" {self.unit}" if self.unit else ""
        QToolTip.showText(
            event.globalPosition().toPoint(),
            self.t(
                "analysis.plot.tooltip",
                record=row["record"],
                source=row.get("source_label", ""),
                target=f"{row['target']:.6g}{suffix}",
                actual=f"{row['actual']:.6g}{suffix}",
            ),
            self,
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        row = self.nearest_row(event.position())
        if row is not None and not self.binary:
            source_kind = str(row.get("source_kind") or "")
            self.highlight_record(row["record"], source_kind)
            self.recordActivated.emit(source_kind, int(row["record"]))
            return
        if self.plot_rect().contains(event.position()):
            self.dragging_plot = True
            self.last_drag_position = event.position()
            self.hovered_record = None
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            QToolTip.hideText()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_plot:
            self.dragging_plot = False
            self.last_drag_position = None
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.plot_rect().contains(event.position())
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()

    def wheelEvent(self, event):
        rect = self.plot_rect()
        position = event.position()
        if not rect.contains(position) or event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return

        x_minimum, x_maximum, y_minimum, y_maximum = self.current_view_range()
        self.hovered_record = None
        x_span = x_maximum - x_minimum
        y_span = y_maximum - y_minimum
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        base_minimum, base_maximum = self.value_range()
        base_span = max(1e-12, base_maximum - base_minimum)
        if factor < 1.0 and min(x_span, y_span) <= base_span * 1e-6:
            event.accept()
            return
        if factor > 1.0 and self.view_range is None:
            event.accept()
            return

        x_fraction = (position.x() - rect.left()) / max(1.0, rect.width())
        y_fraction = (rect.bottom() - position.y()) / max(1.0, rect.height())
        x_center = x_minimum + x_fraction * x_span
        y_center = y_minimum + y_fraction * y_span
        new_x_minimum = x_center - (x_center - x_minimum) * factor
        new_x_maximum = x_center + (x_maximum - x_center) * factor
        new_y_minimum = y_center - (y_center - y_minimum) * factor
        new_y_maximum = y_center + (y_maximum - y_center) * factor
        if factor > 1.0:
            new_x_minimum, new_x_maximum = self.bounded_interval(
                new_x_minimum, new_x_maximum, base_minimum, base_maximum
            )
            new_y_minimum, new_y_maximum = self.bounded_interval(
                new_y_minimum, new_y_maximum, base_minimum, base_maximum
            )
            if (
                math.isclose(new_x_minimum, base_minimum)
                and math.isclose(new_x_maximum, base_maximum)
                and math.isclose(new_y_minimum, base_minimum)
                and math.isclose(new_y_maximum, base_maximum)
            ):
                self.view_range = None
            else:
                self.view_range = (
                    new_x_minimum, new_x_maximum,
                    new_y_minimum, new_y_maximum,
                )
        else:
            self.view_range = (
                new_x_minimum, new_x_maximum,
                new_y_minimum, new_y_maximum,
            )
        QToolTip.hideText()
        self.update()
        event.accept()

    def leaveEvent(self, event):
        if not self.dragging_plot and self.hovered_record is not None:
            self.hovered_record = None
            QToolTip.hideText()
            self.unsetCursor()
            self.update()
        super().leaveEvent(event)


class FeatureImportancePlot(QWidget):
    """Horizontale Balken für die relative lokale Eingangssensitivität."""

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.values = []
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_values(self, values):
        self.values = list(values)
        if self.values:
            longest_name = max(
                self.fontMetrics().horizontalAdvance(str(name))
                for name, _value in self.values
            )
            self.setMinimumWidth(max(360, longest_name + 300))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        if not self.values:
            painter.setPen(QColor("#5b6570"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             self.t("analysis.sensitivity.no_data"))
            return
        longest_name = max(
            self.fontMetrics().horizontalAdvance(str(name))
            for name, _value in self.values
        )
        left = float(max(78, longest_name + 24))
        top = 14.0
        bottom = 20.0
        row_height = max(28.0, min(46.0, (self.height() - top - bottom) / len(self.values)))
        chart_width = max(100.0, self.width() - left - 76.0)
        maximum = max((value for _name, value in self.values), default=1.0) or 1.0
        for index, (name, value) in enumerate(self.values):
            y = top + index * row_height
            painter.setPen(QColor("#263746"))
            painter.drawText(QRectF(6, y, left - 16, row_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(name))
            bar_rect = QRectF(left, y + 6, chart_width * value / maximum,
                              max(10.0, row_height - 12))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2f83b8"))
            painter.drawRoundedRect(bar_rect, 3, 3)
            painter.setPen(QColor("#263746"))
            painter.drawText(QRectF(left + chart_width + 8, y, 62, row_height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:.1f} %")
