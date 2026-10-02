# -------------------------------------------------------------------------------------------------
# Datei: analysisplot.py
# Zweck: Erstellt Diagramme für Test-, Analyse- und Vergleichsergebnisse.
# Letzte Änderung: 04.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
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
        self.tolerance_percent = False
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

    def set_tolerance(self, value, visible=False, percent=False):
        self.tolerance = max(0.0, float(value or 0.0))
        self.tolerance_percent = bool(percent)
        self.show_tolerance = bool(visible) and not self.binary
        self.update()

    def tolerance_at(self, target):
        return abs(float(target)) * self.tolerance / 100 if self.tolerance_percent else self.tolerance

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
    def axis_ticks(minimum, maximum):
        """Wählt runde Schritte unabhängig vom Rand und vom Zoomausschnitt."""

        span = maximum - minimum
        if not math.isfinite(span) or span <= 0.0:
            return ()
        raw_step = span / 5.0
        if raw_step <= 0.0:
            return ()
        magnitude = 10.0 ** math.floor(math.log10(raw_step))
        if magnitude == 0.0:
            return ()
        fraction = raw_step / magnitude
        factor = min((1.0, 2.0, 5.0, 10.0), key=lambda value: abs(math.log(fraction / value)))
        step = factor * magnitude
        first = math.ceil(minimum / step)
        last = math.floor(maximum / step)
        return tuple(index * step for index in range(first, last + 1))

    def axis_tick_label(self, value):
        """Vermeidet Rechenartefakte und nutzt das Dezimalzeichen der UI-Sprache."""

        text = "0" if value == 0.0 else f"{value:.12g}"
        if self.language.current_language == "de":
            text = text.replace(".", ",")
        return text

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
            x_ticks = self.axis_ticks(x_minimum, x_maximum)
            y_ticks = self.axis_ticks(y_minimum, y_maximum)

        for x_value in x_ticks:
            x = self.map_point(
                x_value, y_minimum, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            ).x()
            painter.setPen(QPen(QColor("#e3e8ec"), 1))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.setPen(QColor("#4f5962"))
            painter.drawText(QRectF(x - 35, rect.bottom() + 5, 70, 20), Qt.AlignmentFlag.AlignHCenter, self.axis_tick_label(x_value))

        for y_value in y_ticks:
            y = self.map_point(
                x_minimum, y_value, rect,
                x_minimum, x_maximum, y_minimum, y_maximum
            ).y()
            painter.setPen(QPen(QColor("#e3e8ec"), 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QColor("#4f5962"))
            painter.drawText(QRectF(2, y - 10, 54, 20), Qt.AlignmentFlag.AlignRight, self.axis_tick_label(y_value))

        if self.show_tolerance and self.tolerance > 0.0:
            painter.save()
            painter.setClipRect(rect)
            xs = [x_minimum, x_maximum]
            if x_minimum < 0 < x_maximum:
                xs.insert(1, 0.0)
            def boundary(sign):
                return [self.map_point(x, x + sign * self.tolerance_at(x), rect,
                                       x_minimum, x_maximum, y_minimum, y_maximum) for x in xs]
            upper, lower = boundary(1), boundary(-1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(67, 160, 105, 38))
            painter.drawPolygon(QPolygonF(upper + list(reversed(lower))))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(67, 145, 96, 150), 1))
            painter.drawPolyline(QPolygonF(upper))
            painter.drawPolyline(QPolygonF(lower))
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
                > self.tolerance_at(row["target"])
            )
            if row.get("plot_color"):
                color = QColor(row["plot_color"])
            elif outside_tolerance or row.get("binary_error"):
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
                if row_key + (row.get('neuron_id'),) == self.hovered_record:
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

            unit = hovered_row.get('unit', self.unit)
            suffix = f" {unit}" if unit else ""
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
        row_key = (str(row.get("source_kind") or ""), int(row["record"]), row.get('neuron_id'))
        if row_key != self.hovered_record:
            self.hovered_record = row_key
            self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        unit = row.get('unit', self.unit)
        suffix = f" {unit}" if unit else ""
        QToolTip.showText(
            event.globalPosition().toPoint(),
            self.t(
                "analysis.plot.tooltip",
                record=row["record"],
                source=(row.get("source_label", "") + ' · ' + str(row.get('output', ''))
                        if row.get('plot_color') else row.get("source_label", "")),
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


class CharacteristicPlot(QWidget):
    """Zeigt eine aus echten Vorwärtsläufen berechnete Netzkennlinie."""

    recordActivated = Signal(str, int)
    viewChanged = Signal(bool)

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.curve_points = []
        self.background_points = []
        self.data_points = []
        self.data_point_strengths = []
        self.reference_point = None
        self.data_point_records = []
        self.background_point_records = []
        self.reference_record = None
        self.source_kind = ""
        self.x_label = ""
        self.y_label = ""
        self.x_unit = ""
        self.y_unit = ""
        self.point_legend = ""
        self.background_legend = ""
        self.reference_legend = ""
        self.compact_footer = False
        self.view_range = None
        self.dragging_plot = False
        self.last_drag_position = None
        self.hovered_record = None
        self.screen_points = []
        self.setMouseTracking(True)
        self.setMinimumHeight(330)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_data(
        self,
        curve_points,
        data_points,
        x_label="",
        y_label="",
        point_legend="",
        reference_point=None,
        reference_legend="",
        data_point_strengths=None,
        background_points=None,
        background_legend="",
        data_point_records=None,
        background_point_records=None,
        reference_record=None,
        source_kind="",
        x_unit="",
        y_unit="",
    ):
        self.curve_points = [
            (float(x_value), float(y_value))
            for x_value, y_value in curve_points
            if math.isfinite(float(x_value))
            and math.isfinite(float(y_value))
        ]
        self.data_points = [
            (float(x_value), float(y_value))
            for x_value, y_value in data_points
            if math.isfinite(float(x_value))
            and math.isfinite(float(y_value))
        ]
        self.background_points = [
            (float(x_value), float(y_value))
            for x_value, y_value in (background_points or [])
            if math.isfinite(float(x_value))
            and math.isfinite(float(y_value))
        ]
        strengths = list(data_point_strengths or [])
        self.data_point_strengths = [
            max(0.0, min(1.0, float(strengths[index])))
            if index < len(strengths) else 1.0
            for index in range(len(self.data_points))
        ]
        records = list(data_point_records or [])
        self.data_point_records = [
            int(records[index]) if index < len(records) else None
            for index in range(len(self.data_points))
        ]
        background_records = list(background_point_records or [])
        self.background_point_records = [
            int(background_records[index])
            if index < len(background_records) else None
            for index in range(len(self.background_points))
        ]
        self.reference_point = None
        if reference_point is not None:
            x_value, y_value = reference_point
            if math.isfinite(float(x_value)) and math.isfinite(float(y_value)):
                self.reference_point = (float(x_value), float(y_value))
        self.reference_record = (
            int(reference_record) if reference_record is not None else None
        )
        self.source_kind = str(source_kind or "")
        self.x_label = str(x_label or "")
        self.y_label = str(y_label or "")
        self.x_unit = str(x_unit or "").strip()
        self.y_unit = str(y_unit or "").strip()
        self.point_legend = str(point_legend or "")
        self.background_legend = str(background_legend or "")
        self.reference_legend = str(reference_legend or "")
        self.reset_view()

    def legend_items(self):
        items = [
            ("curve", self.t("analysis.characteristic.legend_curve"))
        ]
        if self.background_points and self.background_legend:
            items.append(("background", self.background_legend))
        if self.data_points and self.point_legend:
            items.append(("similar", self.point_legend))
        if self.reference_point is not None and self.reference_legend:
            items.append(("reference", self.reference_legend))
        return items

    def compact_footer_active(self):
        if not self.compact_footer:
            return False
        metrics = self.fontMetrics()
        items = self.legend_items()
        legend_width = sum(
            32 + metrics.horizontalAdvance(label)
            for _kind, label in items
        ) + 18 * max(0, len(items) - 1)
        axis_width = min(
            220,
            max(80, metrics.horizontalAdvance(self.x_label) + 16),
        )
        return axis_width + legend_width + 24 <= max(80, self.width() - 32)

    def set_compact_footer(self, enabled):
        self.compact_footer = bool(enabled)
        self.update()

    def plot_rect(self):
        bottom_margin = 92 if self.compact_footer_active() else 112
        return QRectF(
            76,
            36,
            max(80, self.width() - 108),
            max(80, self.height() - bottom_margin),
        )

    @staticmethod
    def padded_range(values):
        if not values:
            return 0.0, 1.0
        minimum = min(values)
        maximum = max(values)
        if math.isclose(minimum, maximum):
            padding = max(1.0, abs(minimum) * 0.1)
        else:
            padding = (maximum - minimum) * 0.08
        return minimum - padding, maximum + padding

    def base_view_range(self):
        points = (
            list(self.curve_points)
            + list(self.background_points)
            + list(self.data_points)
        )
        if self.reference_point is not None:
            points.append(self.reference_point)
        if not points:
            return 0.0, 1.0, 0.0, 1.0
        x_minimum, x_maximum = self.padded_range(
            [point[0] for point in points]
        )
        y_minimum, y_maximum = self.padded_range(
            [point[1] for point in points]
        )
        return x_minimum, x_maximum, y_minimum, y_maximum

    def current_view_range(self):
        return self.view_range or self.base_view_range()

    def reset_view(self):
        self.view_range = None
        self.dragging_plot = False
        self.last_drag_position = None
        self.hovered_record = None
        self.unsetCursor()
        QToolTip.hideText()
        self.viewChanged.emit(False)
        self.update()

    @staticmethod
    def map_point(
        x_value,
        y_value,
        rect,
        x_minimum,
        x_maximum,
        y_minimum,
        y_maximum,
    ):
        x_span = max(1e-12, x_maximum - x_minimum)
        y_span = max(1e-12, y_maximum - y_minimum)
        return QPointF(
            rect.left() + (x_value - x_minimum) / x_span * rect.width(),
            rect.bottom() - (y_value - y_minimum) / y_span * rect.height(),
        )

    def axis_tick_label(self, value):
        text = "0" if value == 0.0 else f"{value:.12g}"
        return (
            text.replace(".", ",")
            if self.language.current_language == "de"
            else text
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(
            self.rect(),
            self.palette().window().color(),
        )
        outer_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#c2ccd6"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(outer_rect, 7, 7)
        rect = self.plot_rect()
        painter.setPen(QPen(QColor("#c9d2dc"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        if not self.curve_points:
            painter.setPen(QColor("#5b6570"))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                self.t("analysis.characteristic.no_data"),
            )
            return

        x_minimum, x_maximum, y_minimum, y_maximum = (
            self.current_view_range()
        )

        painter.setPen(QPen(QColor("#e1e7ec"), 1))
        for value in SollIstPlot.axis_ticks(x_minimum, x_maximum):
            point = self.map_point(
                value, y_minimum, rect,
                x_minimum, x_maximum, y_minimum, y_maximum,
            )
            painter.drawLine(
                QPointF(point.x(), rect.top()),
                QPointF(point.x(), rect.bottom()),
            )
            painter.setPen(QColor("#44515c"))
            painter.drawText(
                QRectF(point.x() - 45, rect.bottom() + 5, 90, 20),
                Qt.AlignmentFlag.AlignCenter,
                self.axis_tick_label(value),
            )
            painter.setPen(QPen(QColor("#e1e7ec"), 1))
        for value in SollIstPlot.axis_ticks(y_minimum, y_maximum):
            point = self.map_point(
                x_minimum, value, rect,
                x_minimum, x_maximum, y_minimum, y_maximum,
            )
            painter.drawLine(
                QPointF(rect.left(), point.y()),
                QPointF(rect.right(), point.y()),
            )
            painter.setPen(QColor("#44515c"))
            painter.drawText(
                QRectF(2, point.y() - 10, 68, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self.axis_tick_label(value),
            )
            painter.setPen(QPen(QColor("#e1e7ec"), 1))

        legend_items = self.legend_items()
        metrics = painter.fontMetrics()
        item_widths = [
            32 + metrics.horizontalAdvance(label)
            for _kind, label in legend_items
        ]
        legend_spacing = 18
        legend_width = sum(item_widths) + legend_spacing * (
            len(legend_items) - 1
        )
        compact_footer = self.compact_footer_active()
        if compact_footer:
            axis_width = min(
                220,
                max(80, metrics.horizontalAdvance(self.x_label) + 16),
            )
            footer_center = outer_rect.center().x()
            center_offset = (axis_width + legend_width) / 4 + 6
            axis_center = footer_center - center_offset
            legend_center = footer_center + center_offset
            legend_x = legend_center - legend_width / 2
            legend_y = rect.bottom() + 43
            x_label_rect = QRectF(
                axis_center - axis_width / 2,
                rect.bottom() + 31,
                axis_width,
                24,
            )
            x_label = metrics.elidedText(
                self.x_label,
                Qt.TextElideMode.ElideRight,
                max(1, int(x_label_rect.width() - 8)),
            )
        else:
            legend_x = rect.center().x() - legend_width / 2
            legend_y = rect.bottom() + 68
            x_label_rect = QRectF(
                rect.left(), rect.bottom() + 31, rect.width(), 24
            )
            x_label = self.x_label

        painter.setPen(QColor("#243746"))
        painter.drawText(
            x_label_rect,
            Qt.AlignmentFlag.AlignCenter,
            x_label,
        )
        painter.save()
        painter.translate(19, rect.center().y())
        painter.rotate(-90)
        painter.drawText(
            QRectF(-rect.height() / 2, -12, rect.height(), 24),
            Qt.AlignmentFlag.AlignCenter,
            self.y_label,
        )
        painter.restore()

        painter.save()
        painter.setClipRect(rect.adjusted(-2, -2, 2, 2))
        self.screen_points = []
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(117, 129, 139, 62))
        for index, (x_value, y_value) in enumerate(self.background_points):
            point = self.map_point(
                x_value, y_value, rect,
                x_minimum, x_maximum, y_minimum, y_maximum,
            )
            painter.drawEllipse(point, 1.45, 1.45)
            if rect.adjusted(-8, -8, 8, 8).contains(point):
                self.screen_points.append({
                    "point": point,
                    "record": self.background_point_records[index],
                    "x": x_value,
                    "y": y_value,
                    "priority": 0,
                })

        paint_order = sorted(
            range(len(self.data_points)),
            key=lambda index: self.data_point_strengths[index],
        )
        for index in paint_order:
            x_value, y_value = self.data_points[index]
            strength = self.data_point_strengths[index]
            alpha = round(65 + 150 * strength)
            outline = QColor(141, 105, 0, min(255, alpha + 25))
            fill = QColor(244, 196, 48, alpha)
            painter.setPen(QPen(outline, 0.8))
            painter.setBrush(fill)
            point = self.map_point(
                x_value, y_value, rect,
                x_minimum, x_maximum, y_minimum, y_maximum,
            )
            painter.drawEllipse(point, 3.2, 3.2)
            if rect.adjusted(-8, -8, 8, 8).contains(point):
                self.screen_points.append({
                    "point": point,
                    "record": self.data_point_records[index],
                    "x": x_value,
                    "y": y_value,
                    "priority": 1,
                })

        if self.reference_point is not None:
            point = self.map_point(
                self.reference_point[0], self.reference_point[1], rect,
                x_minimum, x_maximum, y_minimum, y_maximum,
            )
            painter.setPen(QPen(QColor("#735500"), 1.2))
            painter.setBrush(QColor("#f4c430"))
            painter.drawEllipse(point, 5.5, 5.5)
            if rect.adjusted(-10, -10, 10, 10).contains(point):
                self.screen_points.append({
                    "point": point,
                    "record": self.reference_record,
                    "x": self.reference_point[0],
                    "y": self.reference_point[1],
                    "priority": 2,
                })

        path = QPainterPath()
        for index, (x_value, y_value) in enumerate(self.curve_points):
            point = self.map_point(
                x_value, y_value, rect,
                x_minimum, x_maximum, y_minimum, y_maximum,
            )
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#1676b8"), 2.2))
        painter.drawPath(path)
        painter.restore()

        hovered_entry = self.hovered_screen_entry()
        if hovered_entry is not None:
            point = hovered_entry["point"]
            painter.save()
            painter.setClipRect(rect)
            painter.setPen(
                QPen(QColor("#4f788f"), 1, Qt.PenStyle.DashLine)
            )
            painter.drawLine(QPointF(rect.left(), point.y()), point)
            painter.drawLine(point, QPointF(point.x(), rect.bottom()))
            painter.restore()

            x_suffix = f" {self.x_unit}" if self.x_unit else ""
            y_suffix = f" {self.y_unit}" if self.y_unit else ""
            x_text = (
                f"{self.axis_tick_label(hovered_entry['x'])}{x_suffix}"
            )
            y_text = (
                f"{self.axis_tick_label(hovered_entry['y'])}{y_suffix}"
            )
            painter.setPen(QPen(QColor("#4f788f"), 1))
            painter.setBrush(QColor("#eef5f8"))
            x_value_label = QRectF(
                point.x() - 48, rect.bottom() + 4, 96, 22
            )
            y_value_label = QRectF(
                1, point.y() - 11, 70, 22
            )
            painter.drawRoundedRect(x_value_label, 3, 3)
            painter.drawRoundedRect(y_value_label, 3, 3)
            painter.drawText(
                x_value_label, Qt.AlignmentFlag.AlignCenter, x_text
            )
            painter.drawText(
                y_value_label, Qt.AlignmentFlag.AlignCenter, y_text
            )

        item_x = legend_x
        for index, (kind, label) in enumerate(legend_items):
            if kind == "curve":
                painter.setPen(QPen(QColor("#1676b8"), 2.2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(
                    QPointF(item_x, legend_y),
                    QPointF(item_x + 24, legend_y),
                )
            elif kind == "background":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(117, 129, 139, 90))
                painter.drawEllipse(
                    QPointF(item_x + 12, legend_y), 2.2, 2.2
                )
            elif kind == "similar":
                painter.setPen(QPen(QColor(141, 105, 0, 150), 1))
                painter.setBrush(QColor(244, 196, 48, 135))
                painter.drawEllipse(
                    QPointF(item_x + 12, legend_y), 3.5, 3.5
                )
            else:
                painter.setPen(QPen(QColor("#735500"), 1.2))
                painter.setBrush(QColor("#f4c430"))
                painter.drawEllipse(
                    QPointF(item_x + 12, legend_y), 5.0, 5.0
                )
            painter.setPen(QColor("#243746"))
            painter.drawText(
                QPointF(item_x + 32, legend_y + 5), label
            )
            item_x += item_widths[index] + legend_spacing

    def nearest_record(self, position, maximum_distance=10.0):
        candidates = []
        for entry in self.screen_points:
            if entry["record"] is None:
                continue
            point = entry["point"]
            distance = math.hypot(
                position.x() - point.x(), position.y() - point.y()
            )
            if distance <= maximum_distance:
                candidates.append((entry["priority"], -distance, entry))
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda candidate: (candidate[0], candidate[1]),
        )[2]

    def hovered_screen_entry(self):
        if self.hovered_record is None:
            return None
        entries = [
            entry for entry in self.screen_points
            if entry["record"] == self.hovered_record
        ]
        return max(
            entries,
            key=lambda entry: entry["priority"],
            default=None,
        )

    def mouseMoveEvent(self, event):
        if self.dragging_plot and self.last_drag_position is not None:
            rect = self.plot_rect()
            position = event.position()
            delta = position - self.last_drag_position
            x_minimum, x_maximum, y_minimum, y_maximum = (
                self.current_view_range()
            )
            base_x_minimum, base_x_maximum, base_y_minimum, base_y_maximum = (
                self.base_view_range()
            )
            x_shift = (
                delta.x() / max(1.0, rect.width())
                * (x_maximum - x_minimum)
            )
            y_shift = (
                delta.y() / max(1.0, rect.height())
                * (y_maximum - y_minimum)
            )
            new_x_minimum, new_x_maximum = SollIstPlot.bounded_interval(
                x_minimum - x_shift,
                x_maximum - x_shift,
                base_x_minimum,
                base_x_maximum,
            )
            new_y_minimum, new_y_maximum = SollIstPlot.bounded_interval(
                y_minimum + y_shift,
                y_maximum + y_shift,
                base_y_minimum,
                base_y_maximum,
            )
            self.view_range = (
                new_x_minimum,
                new_x_maximum,
                new_y_minimum,
                new_y_maximum,
            )
            self.last_drag_position = position
            self.hovered_record = None
            self.viewChanged.emit(True)
            QToolTip.hideText()
            self.update()
            return

        entry = self.nearest_record(event.position())
        if entry is None:
            if self.hovered_record is not None:
                self.hovered_record = None
                self.update()
            QToolTip.hideText()
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.plot_rect().contains(event.position())
                else Qt.CursorShape.ArrowCursor
            )
            return

        record = int(entry["record"])
        if record != self.hovered_record:
            self.hovered_record = record
            self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        QToolTip.showText(
            event.globalPosition().toPoint(),
            self.t(
                "analysis.characteristic.tooltip",
                record=entry["record"],
                x_label=self.x_label,
                x=self.axis_tick_label(entry["x"]),
                y_label=self.y_label,
                y=self.axis_tick_label(entry["y"]),
            ),
            self,
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        entry = self.nearest_record(event.position())
        if entry is not None:
            self.recordActivated.emit(
                self.source_kind, int(entry["record"])
            )
            event.accept()
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

        x_minimum, x_maximum, y_minimum, y_maximum = (
            self.current_view_range()
        )
        base_x_minimum, base_x_maximum, base_y_minimum, base_y_maximum = (
            self.base_view_range()
        )
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        if factor > 1.0 and self.view_range is None:
            event.accept()
            return
        if factor < 1.0:
            x_base_span = max(1e-12, base_x_maximum - base_x_minimum)
            y_base_span = max(1e-12, base_y_maximum - base_y_minimum)
            if (
                x_maximum - x_minimum <= x_base_span * 1e-6
                or y_maximum - y_minimum <= y_base_span * 1e-6
            ):
                event.accept()
                return

        x_fraction = (
            (position.x() - rect.left()) / max(1.0, rect.width())
        )
        y_fraction = (
            (rect.bottom() - position.y()) / max(1.0, rect.height())
        )
        x_span = x_maximum - x_minimum
        y_span = y_maximum - y_minimum
        x_center = x_minimum + x_fraction * x_span
        y_center = y_minimum + y_fraction * y_span
        new_x_minimum = x_center - (x_center - x_minimum) * factor
        new_x_maximum = x_center + (x_maximum - x_center) * factor
        new_y_minimum = y_center - (y_center - y_minimum) * factor
        new_y_maximum = y_center + (y_maximum - y_center) * factor
        if factor > 1.0:
            new_x_minimum, new_x_maximum = SollIstPlot.bounded_interval(
                new_x_minimum,
                new_x_maximum,
                base_x_minimum,
                base_x_maximum,
            )
            new_y_minimum, new_y_maximum = SollIstPlot.bounded_interval(
                new_y_minimum,
                new_y_maximum,
                base_y_minimum,
                base_y_maximum,
            )
            at_base = all((
                math.isclose(new_x_minimum, base_x_minimum),
                math.isclose(new_x_maximum, base_x_maximum),
                math.isclose(new_y_minimum, base_y_minimum),
                math.isclose(new_y_maximum, base_y_maximum),
            ))
            self.view_range = None if at_base else (
                new_x_minimum,
                new_x_maximum,
                new_y_minimum,
                new_y_maximum,
            )
        else:
            self.view_range = (
                new_x_minimum,
                new_x_maximum,
                new_y_minimum,
                new_y_maximum,
            )
        self.hovered_record = None
        self.viewChanged.emit(self.view_range is not None)
        QToolTip.hideText()
        self.update()
        event.accept()

    def leaveEvent(self, event):
        if not self.dragging_plot:
            self.hovered_record = None
            QToolTip.hideText()
            self.unsetCursor()
        super().leaveEvent(event)


class FeatureImportancePlot(QWidget):
    """Horizontale Balken für die relative lokale Eingangssensitivität."""

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.values = []
        self.compact = False
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_values(self, values):
        self.values = list(values)
        if self.values:
            longest_name = max(
                self.fontMetrics().horizontalAdvance(str(name))
                for name, _value in self.values
            )
            self.setMinimumWidth(260 if self.compact else max(360, longest_name + 300))
        if self.compact:
            self.setMinimumHeight(40 + len(self.values) * 36)
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
        left = 8.0 if self.compact else float(max(78, longest_name + 24))
        top = 14.0
        bottom = 20.0
        row_height = 36.0 if self.compact else max(28.0, min(46.0, (self.height() - top - bottom) / len(self.values)))
        chart_width = max(100.0, self.width() - left - 76.0)
        maximum = 100.0 if self.compact else (max((value for _name, value in self.values), default=1.0) or 1.0)
        if self.compact:
            painter.setPen(QColor("#5b6570"))
            painter.drawText(QRectF(left, self.height() - 20, chart_width, 20),
                             Qt.AlignmentFlag.AlignRight, "0–100 %")
        for index, (name, value) in enumerate(self.values):
            y = top + index * row_height
            painter.setPen(QColor("#263746"))
            if self.compact:
                painter.drawText(QRectF(left, y, self.width() - 16, 18),
                                 Qt.AlignmentFlag.AlignLeft,
                                 self.fontMetrics().elidedText(str(name), Qt.TextElideMode.ElideRight, self.width() - 16))
            else:
                painter.drawText(QRectF(6, y, left - 16, row_height),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(name))
            bar_rect = QRectF(left, y + (21 if self.compact else (row_height - 10) / 2), chart_width * value / maximum,
                              8.0 if self.compact else 10.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2f83b8"))
            painter.drawRoundedRect(bar_rect, 5, 5)
            painter.setPen(QColor("#263746"))
            painter.drawText(QRectF(left + chart_width + 8, y, 62, row_height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:.1f} %")
