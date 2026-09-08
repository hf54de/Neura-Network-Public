# -------------------------------------------------------------------------------------------------
# Datei: trainingerrorchart.py
# Zweck: Zeichnet und aktualisiert den Fehlerverlauf eines Trainingslaufs.
# Letzte Änderung: 05.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from language import LanguageManager
from trainingcomparison import (
    clipped_curve, comparison_color, normalized_curve, metric_curve_key, metric_chart_title,
)


class TrainingErrorChart(QWidget):
    """
    Zeigt wahlweise den mittleren Epochenfehler oder maximalen Einzelfehler.

    Das Diagramm verwendet ausschließlich PySide6 und begrenzt
    sowohl die gespeicherte Punktzahl als auch die Häufigkeit der
    sichtbaren Aktualisierungen.
    """

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.points = []
        self.comparison_runs = []
        self.maximum_points = []
        self.error_metric = "mse"
        self.error_limit = None
        self.scale_mode = "linear"
        self.maximum_stored_points = 10000
        self.minimum_update_interval = 0.10
        self._last_visible_update = 0.0

        self.setMinimumHeight(
            250
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

    def set_comparison_runs(self, runs):
        """Speichert nur die ausgewählten Referenzkurven, ohne Trainingswerte zu ändern."""

        self.comparison_runs = [
            (run["run_id"], normalized_curve(run.get(metric_curve_key(self.error_metric))))
            for run in runs
        ]
        self.update()

    def set_scale_mode(self, scale_mode):
        """Stellt die Y-Achse auf lineare oder logarithmische Anzeige."""

        if scale_mode not in {
            "linear",
            "logarithmic"
        }:
            scale_mode = "linear"

        self.scale_mode = scale_mode
        self.update()

    def clear(self, error_limit=None):
        """
        Beginnt einen neuen Kurvenverlauf.
        """

        self.points = []
        self.maximum_points = []
        self.error_limit = (
            float(error_limit)
            if error_limit is not None
            else None
        )
        self._last_visible_update = 0.0
        self.update()

    def add_point(
        self,
        epoch,
        error_value,
        force_update=False
    ):
        """
        Fügt einen Messpunkt hinzu und zeichnet höchstens
        zehnmal pro Sekunde neu.
        """

        epoch = int(epoch)
        error_value = float(error_value)

        if (
            epoch < 1
            or not math.isfinite(error_value)
            or error_value < 0.0
        ):
            return

        point = (
            epoch,
            error_value
        )

        if self.points and self.points[-1][0] == epoch:
            self.points[-1] = point

        else:
            self.points.append(
                point
            )

        if len(self.points) > self.maximum_stored_points:
            self.points = (
                self.points[::2]
            )

            if self.points[-1] != point:
                self.points.append(
                    point
                )

        current_time = time.monotonic()

        if (
            force_update
            or current_time - self._last_visible_update
            >= self.minimum_update_interval
        ):
            self._last_visible_update = current_time
            self.update()

    def add_maximum_point(self, epoch, error_value):
        point = (int(epoch), float(error_value))
        if point[0] < 1 or not math.isfinite(point[1]) or point[1] < 0:
            return
        if self.maximum_points and self.maximum_points[-1][0] == point[0]:
            self.maximum_points[-1] = point
        else:
            self.maximum_points.append(point)
        if len(self.maximum_points) > self.maximum_stored_points:
            self.maximum_points = self.maximum_points[::2]
            if self.maximum_points[-1] != point:
                self.maximum_points.append(point)

    @staticmethod
    def format_axis_value(value):
        """
        Formatiert einen Achsenwert kompakt und lesbar.
        """

        value = float(value)

        if value == 0.0:
            return "0"

        if abs(value) < 0.001 or abs(value) >= 10000.0:
            return f"{value:.2e}"

        if abs(value) < 1.0:
            return f"{value:.4f}".rstrip("0").rstrip(".")

        return f"{value:.3f}".rstrip("0").rstrip(".")

    def paintEvent(self, event):
        """
        Zeichnet Achsen, Fehlergrenze und Fehlerkurve.
        """

        active_points = self.maximum_points if self.error_metric == "maximum" else self.points
        error_limit = self.error_limit if self.error_metric == "mse" else None
        painter = QPainter(
            self
        )
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True
        )

        outer_rect = QRectF(
            self.rect()
        ).adjusted(
            0.5,
            0.5,
            -0.5,
            -0.5
        )

        painter.fillRect(
            outer_rect,
            QColor(255, 255, 255)
        )
        painter.setPen(
            QPen(
                QColor(185, 195, 205),
                1.0
            )
        )
        painter.drawRoundedRect(
            outer_rect,
            4.0,
            4.0
        )

        plot_rect = outer_rect.adjusted(
            70.0,
            28.0,
            -20.0,
            -40.0
        )

        if plot_rect.width() <= 20.0 or plot_rect.height() <= 20.0:
            return

        if not active_points:
            painter.setPen(
                QColor(38, 52, 66)
            )
            painter.drawText(
                QRectF(
                    plot_rect.left(),
                    5.0,
                    plot_rect.width(),
                    20.0
                ),
                Qt.AlignmentFlag.AlignCenter,
                metric_chart_title(self.language, self.error_metric)
            )
            painter.setPen(
                QColor(105, 115, 125)
            )
            painter.drawText(
                plot_rect,
                Qt.AlignmentFlag.AlignCenter,
                self.language.text("training.metric.unavailable") if self.error_metric == "maximum" else self.language.text("training.chart.no_data")
            )
            return

        maximum_epoch = max(
            1,
            active_points[-1][0]
        )
        comparison_curves = [
            (run_id, clipped_curve(points, maximum_epoch, self.scale_mode == "logarithmic"))
            for run_id, points in self.comparison_runs
        ]
        scale_points = list(active_points) + [
            point for _run_id, points in comparison_curves for point in points
        ]
        maximum_error = max(
            point[1]
            for point in scale_points
        )

        positive_scale_values = [
            point[1]
            for point in scale_points
            if point[1] > 0.0
        ]

        if (
            error_limit is not None
            and math.isfinite(error_limit)
            and error_limit >= 0.0
        ):
            maximum_error = max(
                maximum_error,
                error_limit
            )

            if error_limit > 0.0:
                positive_scale_values.append(
                    error_limit
                )

        if maximum_error <= 0.0:
            maximum_error = 1.0

        minimum_positive_error = (
            min(positive_scale_values)
            if positive_scale_values
            else maximum_error
        )
        logarithmic_scale = (
            self.scale_mode == "logarithmic"
            and bool(positive_scale_values)
            and minimum_positive_error > 0.0
        )

        if logarithmic_scale:
            logarithmic_minimum = math.floor(
                math.log10(minimum_positive_error)
            )
            logarithmic_maximum = math.ceil(
                math.log10(maximum_error)
            )

            if logarithmic_maximum <= logarithmic_minimum:
                logarithmic_maximum = logarithmic_minimum + 1

            logarithmic_span = (
                logarithmic_maximum - logarithmic_minimum
            )

            def scale_error(error_value):
                if error_value <= 0.0:
                    return 0.0

                return max(
                    0.0,
                    min(
                        1.0,
                        (
                            math.log10(error_value)
                            - logarithmic_minimum
                        ) / logarithmic_span
                    )
                )

        else:
            maximum_error *= 1.05

            def scale_error(error_value):
                return max(
                    0.0,
                    min(
                        1.0,
                        error_value / maximum_error
                    )
                )

        painter.setPen(
            QColor(38, 52, 66)
        )
        painter.drawText(
            QRectF(
                plot_rect.left(),
                5.0,
                plot_rect.width(),
                20.0
            ),
            Qt.AlignmentFlag.AlignCenter,
            (
                metric_chart_title(self.language, self.error_metric, logarithmic_scale)
            )
        )

        grid_pen = QPen(
            QColor(225, 230, 235),
            1.0
        )
        axis_pen = QPen(
            QColor(80, 90, 100),
            1.0
        )

        if logarithmic_scale:
            exponent_step = max(
                1,
                math.ceil(logarithmic_span / 5)
            )
            tick_exponents = list(
                range(
                    logarithmic_minimum,
                    logarithmic_maximum + 1,
                    exponent_step
                )
            )

            if tick_exponents[-1] != logarithmic_maximum:
                tick_exponents.append(
                    logarithmic_maximum
                )

            y_ticks = [
                (
                    (
                        exponent - logarithmic_minimum
                    ) / logarithmic_span,
                    10.0 ** exponent
                )
                for exponent in tick_exponents
            ]

        else:
            tick_count = 5
            y_ticks = [
                (
                    tick_index / tick_count,
                    (tick_index / tick_count) * maximum_error
                )
                for tick_index in range(tick_count + 1)
            ]

        for fraction, error_value in y_ticks:
            y_position = (
                plot_rect.bottom()
                - fraction * plot_rect.height()
            )

            painter.setPen(
                grid_pen
            )
            painter.drawLine(
                QPointF(
                    plot_rect.left(),
                    y_position
                ),
                QPointF(
                    plot_rect.right(),
                    y_position
                )
            )

            painter.setPen(
                QColor(70, 80, 90)
            )
            painter.drawText(
                QRectF(
                    4.0,
                    y_position - 9.0,
                    plot_rect.left() - 10.0,
                    18.0
                ),
                (
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                ),
                self.format_axis_value(
                    error_value
                )
            )

        tick_count = 5

        for tick_index in range(
            tick_count + 1
        ):
            fraction = tick_index / tick_count
            x_position = (
                plot_rect.left()
                + fraction * plot_rect.width()
            )
            epoch_value = round(
                fraction * maximum_epoch
            )

            painter.setPen(
                QColor(70, 80, 90)
            )
            painter.drawText(
                QRectF(
                    x_position - 34.0,
                    plot_rect.bottom() + 6.0,
                    68.0,
                    18.0
                ),
                Qt.AlignmentFlag.AlignCenter,
                str(
                    epoch_value
                )
            )

        painter.setPen(
            axis_pen
        )
        painter.drawLine(
            plot_rect.bottomLeft(),
            plot_rect.topLeft()
        )
        painter.drawLine(
            plot_rect.bottomLeft(),
            plot_rect.bottomRight()
        )

        painter.drawText(
            QRectF(
                plot_rect.right() - 90.0,
                plot_rect.bottom() + 22.0,
                90.0,
                16.0
            ),
            Qt.AlignmentFlag.AlignRight,
            self.language.text("training.chart.epoch_axis")
        )

        if (
            error_limit is not None
            and error_limit >= 0.0
            and (
                not logarithmic_scale
                or error_limit > 0.0
            )
        ):
            limit_y = (
                plot_rect.bottom()
                - scale_error(error_limit) * plot_rect.height()
            )
            limit_pen = QPen(
                QColor(190, 95, 55),
                1.5,
                Qt.PenStyle.DashLine
            )
            painter.setPen(
                limit_pen
            )
            painter.drawLine(
                QPointF(
                    plot_rect.left(),
                    limit_y
                ),
                QPointF(
                    plot_rect.right(),
                    limit_y
                )
            )
            painter.drawText(
                QRectF(
                    plot_rect.left() + 6.0,
                    max(
                        plot_rect.top() + 2.0,
                        limit_y - 19.0
                    ),
                    plot_rect.width() - 12.0,
                    18.0
                ),
                Qt.AlignmentFlag.AlignLeft,
                (
                    self.language.text(
                        "training.chart.error_limit",
                        value=self.format_axis_value(error_limit)
                    )
                )
            )

        # Referenzen zuerst zeichnen; die kräftige aktuelle Kurve bleibt darüber sichtbar.
        painter.save()
        painter.setClipRect(plot_rect.adjusted(-2, -2, 2, 2))
        for run_id, points in comparison_curves:
            reference_path = QPainterPath()
            for index, (epoch, error_value) in enumerate(points):
                point = QPointF(
                    plot_rect.left() + epoch / maximum_epoch * plot_rect.width(),
                    plot_rect.bottom() - scale_error(error_value) * plot_rect.height(),
                )
                if index == 0:
                    reference_path.moveTo(point)
                else:
                    reference_path.lineTo(point)
            painter.setPen(QPen(QColor(comparison_color(run_id)), 1.3))
            painter.drawPath(reference_path)
            if len(points) == 1:
                painter.drawPoint(point)
        painter.restore()

        curve_path = QPainterPath()

        for point_index, (epoch, error_value) in enumerate(
            active_points
        ):
            x_position = (
                plot_rect.left()
                + (epoch / maximum_epoch)
                * plot_rect.width()
            )
            y_position = (
                plot_rect.bottom()
                - scale_error(error_value) * plot_rect.height()
            )
            chart_point = QPointF(
                x_position,
                y_position
            )

            if point_index == 0:
                curve_path.moveTo(
                    chart_point
                )

            else:
                curve_path.lineTo(
                    chart_point
                )

        painter.setPen(
            QPen(
                QColor(34, 113, 165),
                2.0
            )
        )
        painter.drawPath(
            curve_path
        )

        last_epoch, last_error = active_points[-1]
        last_x = (
            plot_rect.left()
            + (last_epoch / maximum_epoch)
            * plot_rect.width()
        )
        last_y = (
            plot_rect.bottom()
            - scale_error(last_error) * plot_rect.height()
        )
        painter.setBrush(
            QColor(34, 113, 165)
        )
        painter.drawEllipse(
            QPointF(
                last_x,
                last_y
            ),
            3.5,
            3.5
        )
