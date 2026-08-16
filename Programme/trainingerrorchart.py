# -------------------------------------------------------------------------------------------------
# Datei: trainingerrorchart.py
# Zweck: Zeichnet und aktualisiert den Fehlerverlauf eines Trainingslaufs.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from language import LanguageManager


class TrainingErrorChart(QWidget):
    """
    Zeigt den mittleren Epochenfehler eines Trainingslaufes.

    Das Diagramm verwendet ausschließlich PySide6 und begrenzt
    sowohl die gespeicherte Punktzahl als auch die Häufigkeit der
    sichtbaren Aktualisierungen.
    """

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.points = []
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

        if not self.points:
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
                self.language.text("training.chart.title")
            )
            painter.setPen(
                QColor(105, 115, 125)
            )
            painter.drawText(
                plot_rect,
                Qt.AlignmentFlag.AlignCenter,
                self.language.text("training.chart.no_data")
            )
            return

        maximum_epoch = max(
            1,
            self.points[-1][0]
        )
        maximum_error = max(
            point[1]
            for point in self.points
        )

        positive_scale_values = [
            point[1]
            for point in self.points
            if point[1] > 0.0
        ]

        if (
            self.error_limit is not None
            and math.isfinite(self.error_limit)
            and self.error_limit >= 0.0
        ):
            maximum_error = max(
                maximum_error,
                self.error_limit
            )

            if self.error_limit > 0.0:
                positive_scale_values.append(
                    self.error_limit
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
                self.language.text("training.chart.title_logarithmic")
                if logarithmic_scale
                else self.language.text("training.chart.title")
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
            self.error_limit is not None
            and self.error_limit >= 0.0
            and (
                not logarithmic_scale
                or self.error_limit > 0.0
            )
        ):
            limit_y = (
                plot_rect.bottom()
                - scale_error(self.error_limit) * plot_rect.height()
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
                        value=self.format_axis_value(self.error_limit)
                    )
                )
            )

        curve_path = QPainterPath()

        for point_index, (epoch, error_value) in enumerate(
            self.points
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

        last_epoch, last_error = self.points[-1]
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
