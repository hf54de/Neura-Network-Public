# -------------------------------------------------------------------------------------------------
# Datei: traininghistorydialog.py
# Zweck: Verwaltet, vergleicht und lädt gespeicherte Trainingsläufe.
# Letzte Änderung: 08.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import csv
import math
from copy import deepcopy

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget
)

from numberformat import format_number as format_display_number
from language import LanguageManager


class CleanTableSelectionDelegate(QStyledItemDelegate):
    """Zeichnet Tabellenzellen ohne den nativen roten Fokusrahmen."""

    def paint(self, painter, option, index):
        clean_option = QStyleOptionViewItem(option)
        clean_option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(
            painter,
            clean_option,
            index
        )


class TrainingHistoryChart(QWidget):
    """Zeigt die Fehlerkurven mehrerer ausgewählter Trainingsläufe."""

    COLORS = (
        QColor(34, 113, 165),
        QColor(210, 92, 62),
        QColor(56, 142, 60),
        QColor(132, 88, 170),
        QColor(220, 150, 35),
        QColor(40, 150, 145)
    )

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.runs = []
        self.scale_mode = "linear"
        self.view_bounds = None
        self.data_bounds = None
        self.plot_rect = QRectF()
        self.dragging = False
        self.last_mouse_position = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_runs(self, runs):
        self.runs = list(runs)
        self.reset_view()

    def set_scale_mode(self, scale_mode):
        if scale_mode not in {"linear", "logarithmic"}:
            scale_mode = "linear"

        self.scale_mode = scale_mode
        self.reset_view()

    def reset_view(self):
        """Zeigt wieder den vollständigen Epochenbereich."""

        self.view_bounds = None
        self.update()

    @staticmethod
    def clamp_interval(minimum, maximum, full_minimum, full_maximum):
        """Hält einen verschobenen Ausschnitt innerhalb der Datenbegrenzung."""

        full_span = full_maximum - full_minimum
        span = maximum - minimum
        if span >= full_span:
            return full_minimum, full_maximum
        if minimum < full_minimum:
            maximum += full_minimum - minimum
            minimum = full_minimum
        if maximum > full_maximum:
            minimum -= maximum - full_maximum
            maximum = full_maximum
        return minimum, maximum

    def wheelEvent(self, event):
        """Zoomt die Epochenachse um den Punkt unter dem Mauszeiger."""

        if (
            self.view_bounds is None
            or self.data_bounds is None
            or not self.plot_rect.contains(event.position())
        ):
            event.ignore()
            return

        wheel_delta = event.angleDelta().y()
        if wheel_delta == 0:
            event.ignore()
            return

        zoom_factor = 0.8 if wheel_delta > 0 else 1.25
        x_minimum, x_maximum, y_minimum, y_maximum = self.view_bounds
        data_x_min, data_x_max, _, _ = self.data_bounds
        x_span = x_maximum - x_minimum
        full_x_span = data_x_max - data_x_min
        new_x_span = min(
            full_x_span,
            max(max(1.0, full_x_span / 4096.0), x_span * zoom_factor)
        )
        x_fraction = (
            (event.position().x() - self.plot_rect.left())
            / self.plot_rect.width()
        )
        x_anchor = x_minimum + x_fraction * x_span
        new_x_min = x_anchor - x_fraction * new_x_span
        new_x_max = new_x_min + new_x_span
        new_x_min, new_x_max = self.clamp_interval(
            new_x_min, new_x_max, data_x_min, data_x_max
        )
        self.view_bounds = (new_x_min, new_x_max, y_minimum, y_maximum)
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.view_bounds is not None
            and self.plot_rect.contains(event.position())
        ):
            self.dragging = True
            self.last_mouse_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self.dragging
            and self.last_mouse_position is not None
            and self.data_bounds is not None
            and self.plot_rect.width() > 0.0
            and self.plot_rect.height() > 0.0
        ):
            delta = event.position() - self.last_mouse_position
            x_minimum, x_maximum, y_minimum, y_maximum = self.view_bounds
            data_x_min, data_x_max, _, _ = self.data_bounds
            x_span = x_maximum - x_minimum
            x_shift = -delta.x() * x_span / self.plot_rect.width()
            x_minimum, x_maximum = self.clamp_interval(
                x_minimum + x_shift,
                x_maximum + x_shift,
                data_x_min,
                data_x_max
            )
            self.view_bounds = (
                x_minimum, x_maximum, y_minimum, y_maximum
            )
            self.last_mouse_position = event.position()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            self.last_mouse_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    @staticmethod
    def format_value(value):
        if value == 0.0:
            return "0"

        if abs(value) < 0.001 or abs(value) >= 10000.0:
            return f"{value:.2e}"

        if abs(value) < 1.0:
            return f"{value:.4f}".rstrip("0").rstrip(".")

        return f"{value:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def integer_ticks(minimum, maximum, maximum_count=6):
        """Liefert gut lesbare ganzzahlige Teilstriche der Epochenachse."""

        first_integer = math.ceil(minimum)
        last_integer = math.floor(maximum)
        if first_integer > last_integer:
            return [round((minimum + maximum) / 2.0)]

        integer_span = max(0, last_integer - first_integer)
        raw_step = max(1.0, integer_span / max(1, maximum_count - 1))
        magnitude = 10 ** math.floor(math.log10(raw_step))
        normalized = raw_step / magnitude
        if normalized <= 1.0:
            multiplier = 1
        elif normalized <= 2.0:
            multiplier = 2
        elif normalized <= 3.0:
            multiplier = 3
        elif normalized <= 5.0:
            multiplier = 5
        else:
            multiplier = 10
        step = max(1, int(multiplier * magnitude))
        first_tick = math.ceil(first_integer / step) * step
        ticks = list(range(first_tick, last_integer + 1, step))
        return ticks or [first_integer]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillRect(outer_rect, QColor(255, 255, 255))
        painter.setPen(QPen(QColor(185, 195, 205), 1.0))
        painter.drawRoundedRect(outer_rect, 4.0, 4.0)

        plot_rect = outer_rect.adjusted(72.0, 46.0, -20.0, -42.0)
        self.plot_rect = QRectF(plot_rect)

        if plot_rect.width() <= 20.0 or plot_rect.height() <= 20.0:
            return

        valid_runs = [
            run
            for run in self.runs
            if isinstance(run.get("curve_points"), list)
            and run["curve_points"]
        ]

        painter.setPen(QColor(38, 52, 66))
        painter.drawText(
            QRectF(plot_rect.left(), 5.0, plot_rect.width(), 20.0),
            Qt.AlignmentFlag.AlignCenter,
            (
                self.t("history.chart.title_log")
                if self.scale_mode == "logarithmic"
                else self.t("history.chart.title")
            )
        )

        if not valid_runs:
            self.data_bounds = None
            self.view_bounds = None
            painter.setPen(QColor(105, 115, 125))
            painter.drawText(
                plot_rect,
                Qt.AlignmentFlag.AlignCenter,
                self.t("history.chart.none_selected")
            )
            return

        all_points = [
            point
            for run in valid_runs
            for point in (
                list(run["curve_points"])
            )
        ]
        maximum_epoch = max(1.0, max(float(point[0]) for point in all_points))
        maximum_error = max(point[1] for point in all_points)
        positive_errors = [
            point[1]
            for point in all_points
            if point[1] > 0.0
        ]
        logarithmic = (
            self.scale_mode == "logarithmic"
            and bool(positive_errors)
        )

        if logarithmic:
            data_y_minimum = float(math.floor(
                math.log10(min(positive_errors))
            ))
            data_y_maximum = float(math.ceil(
                math.log10(max(maximum_error, max(positive_errors)))
            ))
            if data_y_maximum <= data_y_minimum:
                data_y_maximum = data_y_minimum + 1.0

            def transformed_error(error_value):
                return (
                    math.log10(error_value)
                    if error_value > 0.0
                    else None
                )

        else:
            if maximum_error <= 0.0:
                maximum_error = 1.0
            else:
                maximum_error *= 1.05
            data_y_minimum = 0.0
            data_y_maximum = maximum_error

            def transformed_error(error_value):
                return float(error_value)

        self.data_bounds = (
            0.0, maximum_epoch, data_y_minimum, data_y_maximum
        )
        if self.view_bounds is None:
            self.view_bounds = self.data_bounds
        else:
            x_minimum, x_maximum, y_minimum, y_maximum = self.view_bounds
            x_minimum, x_maximum = self.clamp_interval(
                x_minimum, x_maximum, 0.0, maximum_epoch
            )
            y_minimum, y_maximum = self.clamp_interval(
                y_minimum,
                y_maximum,
                data_y_minimum,
                data_y_maximum
            )
            self.view_bounds = (
                x_minimum, x_maximum, y_minimum, y_maximum
            )

        x_minimum, x_maximum, y_minimum, y_maximum = self.view_bounds
        x_span = max(1e-12, x_maximum - x_minimum)
        y_span = max(1e-12, y_maximum - y_minimum)
        y_ticks = [
            (
                index / 5,
                10.0 ** (y_minimum + (index / 5) * y_span)
                if logarithmic
                else y_minimum + (index / 5) * y_span
            )
            for index in range(6)
        ]

        grid_pen = QPen(QColor(225, 230, 235), 1.0)

        for fraction, error_value in y_ticks:
            y_position = plot_rect.bottom() - fraction * plot_rect.height()
            painter.setPen(grid_pen)
            painter.drawLine(
                QPointF(plot_rect.left(), y_position),
                QPointF(plot_rect.right(), y_position)
            )
            painter.setPen(QColor(70, 80, 90))
            painter.drawText(
                QRectF(
                    4.0,
                    y_position - 9.0,
                    plot_rect.left() - 10.0,
                    18.0
                ),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self.format_value(error_value)
            )

        for epoch_value in self.integer_ticks(x_minimum, x_maximum):
            fraction = (epoch_value - x_minimum) / x_span
            x_position = plot_rect.left() + fraction * plot_rect.width()
            painter.setPen(QColor(70, 80, 90))
            painter.drawText(
                QRectF(
                    x_position - 34.0,
                    plot_rect.bottom() + 6.0,
                    68.0,
                    18.0
                ),
                Qt.AlignmentFlag.AlignCenter,
                str(epoch_value)
            )

        painter.setPen(QPen(QColor(80, 90, 100), 1.0))
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.topLeft())
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
        painter.drawText(
            QRectF(
                plot_rect.right() - 90.0,
                plot_rect.bottom() + 22.0,
                90.0,
                16.0
            ),
            Qt.AlignmentFlag.AlignRight,
            self.t("history.chart.epoch")
        )

        legend_x = plot_rect.left()

        for run_index, run in enumerate(valid_runs[:6]):
            color = self.COLORS[run_index % len(self.COLORS)]
            painter.setPen(QPen(color, 2.0))
            painter.drawLine(
                QPointF(legend_x, 34.0),
                QPointF(legend_x + 18.0, 34.0)
            )
            painter.setPen(QColor(55, 65, 75))
            label = self.t("history.chart.run", run=run["run_id"])
            label_width = painter.fontMetrics().horizontalAdvance(label) + 28
            painter.drawText(
                QRectF(legend_x + 22.0, 25.0, label_width, 18.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label
            )
            legend_x += label_width + 22.0

        if len(valid_runs) > 6:
            painter.setPen(QColor(80, 90, 100))
            painter.drawText(
                QRectF(legend_x, 25.0, 90.0, 18.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.t("history.chart.more", count=len(valid_runs) - 6)
            )

        painter.save()
        painter.setClipRect(plot_rect)

        for run_index, run in enumerate(valid_runs):
            color = self.COLORS[run_index % len(self.COLORS)]
            path = QPainterPath()
            last_chart_point = None
            path_started = False

            for point_index, (epoch, error_value) in enumerate(
                run["curve_points"]
            ):
                transformed_value = transformed_error(error_value)
                if transformed_value is None:
                    last_chart_point = None
                    path_started = False
                    continue
                chart_point = QPointF(
                    plot_rect.left()
                    + ((epoch - x_minimum) / x_span) * plot_rect.width(),
                    plot_rect.bottom()
                    - (
                        (
                            transformed_value - y_minimum
                        ) / y_span
                    ) * plot_rect.height()
                )
                last_chart_point = chart_point

                if not path_started:
                    path.moveTo(chart_point)
                    path_started = True
                else:
                    path.lineTo(chart_point)

            painter.setBrush(
                Qt.BrushStyle.NoBrush
            )
            painter.setPen(QPen(color, 2.0))
            painter.drawPath(path)

            if last_chart_point is not None:
                painter.setBrush(color)
                painter.drawEllipse(last_chart_point, 3.0, 3.0)

        painter.restore()


class TrainingHistoryDialog(QDialog):
    """Zeigt und verwaltet die projektbezogene Trainingshistorie."""

    def __init__(
        self,
        training_history,
        parent=None,
        language_manager=None,
        restorable_run_ids=None,
        active_run_id=None,
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.training_history = deepcopy(training_history)
        self.restorable_run_ids = set(restorable_run_ids or ())
        self.active_run_id = active_run_id
        self.restore_run_id = None
        self.renumber_runs()

        self.setWindowTitle(self.t("history.title"))
        self.resize(980, 720)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(
            QLabel(
                self.t("history.introduction")
            )
        )

        self.table = QTableWidget()
        columns = [
            self.t("history.column.run"),
            self.t("history.column.time"),
            self.t("history.column.initialization"),
            self.t("history.column.mode"),
            self.t("history.column.learning_rate"),
            self.t("history.column.momentum"),
            self.t("history.column.epochs"),
            self.t("history.column.first_epoch_error"),
            self.t("history.column.end_error"),
            self.t("history.column.maximum_error"),
            self.t("history.column.duration")
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setItemDelegate(
            CleanTableSelectionDelegate(self.table)
        )
        self.table.setStyleSheet(
            "QTableWidget {"
            "  gridline-color: #d7dde3;"
            "  selection-background-color: #dceeff;"
            "  selection-color: #1f2d3d;"
            "}"
            "QTableWidget::item:selected {"
            "  background-color: #dceeff;"
            "  color: #1f2d3d;"
            "  border: none;"
            "}"
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive
        )
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 290)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.itemSelectionChanged.connect(
            self.update_chart_selection
        )
        main_layout.addWidget(self.table, 1)

        chart_controls = QHBoxLayout()
        chart_controls.addWidget(QLabel(self.t("history.comparison_view")))
        self.scale_combo = QComboBox()
        self.scale_combo.addItem(self.t("common.linear"), "linear")
        self.scale_combo.addItem(self.t("common.logarithmic"), "logarithmic")
        chart_controls.addWidget(self.scale_combo)
        chart_controls.addSpacing(18)
        chart_controls.addWidget(QLabel(self.t("history.chart.mouse_help")))
        self.full_range_button = QPushButton(self.t("history.full_range"))
        chart_controls.addWidget(self.full_range_button)
        chart_controls.addStretch(1)
        main_layout.addLayout(chart_controls)

        self.chart = TrainingHistoryChart(language_manager=self.language)
        self.scale_combo.currentIndexChanged.connect(
            self.update_chart_scale
        )
        self.full_range_button.clicked.connect(
            self.show_full_range
        )
        main_layout.addWidget(self.chart, 2)

        button_layout = QHBoxLayout()
        self.export_button = QPushButton(self.t("history.export"))
        self.delete_button = QPushButton(self.t("history.delete"))
        self.restore_button = QPushButton(self.t("history.restore"))
        self.restore_button.setToolTip(
            self.t("history.restore_tooltip")
        )
        self.close_button = QPushButton(self.t("common.close"))
        self.export_button.clicked.connect(self.export_csv)
        self.delete_button.clicked.connect(self.delete_selected_runs)
        self.restore_button.clicked.connect(
            self.request_restore_selected_run
        )
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.restore_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

        self.populate_table()
        QTimer.singleShot(0, self.resize_to_table_width)

    def renumber_runs(self):
        """Nummeriert die verbliebenen Läufe chronologisch und lückenlos."""

        old_active_run_id = self.active_run_id
        old_restore_run_id = self.restore_run_id
        old_to_new = {}
        for new_run_id, entry in enumerate(self.training_history, start=1):
            old_run_id = entry.get("run_id")
            old_to_new[old_run_id] = new_run_id
            entry["run_id"] = new_run_id
        self.restorable_run_ids = {
            old_to_new[run_id]
            for run_id in self.restorable_run_ids
            if run_id in old_to_new
        }
        self.active_run_id = old_to_new.get(old_active_run_id)
        self.restore_run_id = old_to_new.get(old_restore_run_id)

    @staticmethod
    def format_number(value):
        return format_display_number(value)

    @staticmethod
    def format_error_number(value):
        return format_display_number(value, significant_digits=4)

    def initialization_text(self, entry, repeated_from=None):
        """Beschreibt verständlich, woher die Startparameter des Laufs stammen."""

        if repeated_from is not None:
            return self.t(
                "history.initialization.repeated", run=repeated_from
            )
        if not entry.get("initialized", False):
            return self.t("history.initialization.continued")

        weights = str(entry.get("weight_initialization", "") or "").lower()
        bias = str(entry.get("bias_initialization", "") or "").lower()
        weight_text = (
            "Xavier/Glorot" if weights == "xavier"
            else "0" if weights == "zero"
            else self.t("history.initialization.unknown")
        )
        bias_text = (
            "Xavier/Glorot" if bias == "xavier"
            else "0" if bias == "zero"
            else self.t("history.initialization.unknown")
        )
        return self.t(
            "history.initialization.new",
            weights=weight_text,
            bias=bias_text,
        )

    def populate_table(self):
        self.table.setRowCount(0)

        repeated_from = {}
        first_run_for_state = []
        for entry in self.training_history:
            state = entry.get("initial_network_state")
            source_run = None
            if isinstance(state, dict):
                for saved_state, run_id in first_run_for_state:
                    if state == saved_state:
                        source_run = run_id
                        break
                if source_run is None:
                    first_run_for_state.append((state, entry.get("run_id")))
            repeated_from[entry.get("run_id")] = source_run

        for entry in reversed(self.training_history):
            row = self.table.rowCount()
            self.table.insertRow(row)
            is_active = entry["run_id"] == self.active_run_id
            run_text = str(entry["run_id"])
            if is_active:
                run_text += f" – {self.t('history.active')}"
            values = (
                run_text,
                entry["timestamp"].replace("T", " "),
                self.initialization_text(
                    entry, repeated_from.get(entry.get("run_id"))
                ),
                self.training_mode_text(entry),
                self.format_number(entry["learning_rate"]),
                self.format_number(entry.get("momentum", 0.0)),
                str(entry["completed_epochs"]),
                self.format_error_number(entry["start_error"]),
                self.format_error_number(entry["end_error"]),
                self.format_error_number(entry["maximum_absolute_error"]),
                f"{entry['elapsed_seconds']:.1f} s"
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_active:
                    active_font = item.font()
                    active_font.setBold(True)
                    item.setFont(active_font)

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        entry["run_id"]
                    )

                self.table.setItem(row, column, item)

        has_entries = bool(self.training_history)
        self.export_button.setEnabled(has_entries)
        self.delete_button.setEnabled(has_entries)
        self.restore_button.setEnabled(False)

        if has_entries:
            self.table.selectRow(0)
        else:
            self.chart.set_runs([])

    def resize_to_table_width(self):
        """Passt die Startbreite exakt an die sichtbaren Tabellenspalten an."""

        self.table.resizeColumnsToContents()
        # Zeitpunkt und Initialisierung bleiben direkt lesbar.
        self.table.setColumnWidth(1, max(170, self.table.columnWidth(1)))
        self.table.setColumnWidth(2, max(260, self.table.columnWidth(2)))
        table_width = sum(
            self.table.columnWidth(column)
            for column in range(self.table.columnCount())
        )
        table_width += (
            self.table.frameWidth() * 2
            + self.table.verticalScrollBar().sizeHint().width()
            + 8
        )
        margins = self.layout().contentsMargins()
        desired_width = table_width + margins.left() + margins.right()
        screen = QApplication.primaryScreen()
        if screen is not None:
            available_width = screen.availableGeometry().width() - 40
            desired_width = min(
                desired_width,
                available_width,
            )
            self.setMaximumWidth(max(640, available_width))
        self.resize(max(760, desired_width), self.height())

    def training_mode_text(self, entry):
        """Liefert den gespeicherten Modus oder einen Altprojekt-Hinweis."""

        fast_mode = entry.get("fast_mode")
        if fast_mode is True:
            return self.t("history.mode.fast")
        if fast_mode is False:
            return self.t("history.mode.normal")
        return self.t("history.mode.unknown")

    def selected_run_ids(self):
        return {
            self.table.item(index.row(), 0).data(
                Qt.ItemDataRole.UserRole
            )
            for index in self.table.selectionModel().selectedRows()
        }

    def update_chart_selection(self):
        selected_ids = self.selected_run_ids()
        selected_runs = [
            entry
            for entry in self.training_history
            if entry["run_id"] in selected_ids
        ]
        self.chart.set_runs(selected_runs)
        self.delete_button.setEnabled(bool(selected_ids))
        self.restore_button.setEnabled(
            len(selected_ids) == 1
            and next(iter(selected_ids), None) in self.restorable_run_ids
        )

    def update_chart_scale(self, index=None):
        self.chart.set_scale_mode(
            self.scale_combo.currentData()
        )

    def show_full_range(self):
        """Setzt den vollständigen Epochenbereich wieder her."""

        self.chart.reset_view()

    def delete_selected_runs(self):
        selected_ids = self.selected_run_ids()

        if not selected_ids:
            return

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle(self.t("history.delete_title"))
        message_box.setText(self.t("history.delete_question", count=len(selected_ids)))
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.No)
        message_box.button(QMessageBox.StandardButton.Yes).setText(self.t("common.yes"))
        message_box.button(QMessageBox.StandardButton.No).setText(self.t("common.no"))
        answer = message_box.exec()

        if answer != QMessageBox.StandardButton.Yes:
            return

        active_run_deleted = self.active_run_id in selected_ids
        self.training_history = [
            entry
            for entry in self.training_history
            if entry["run_id"] not in selected_ids
        ]
        self.renumber_runs()
        if active_run_deleted:
            if self.training_history:
                self.active_run_id = self.training_history[-1]["run_id"]
                self.restore_run_id = self.active_run_id
            else:
                self.active_run_id = None
                self.restore_run_id = None
        self.populate_table()

    def request_restore_selected_run(self):
        """Schließt den Dialog mit dem gewählten Netzwerkzustand."""

        selected_ids = self.selected_run_ids()

        if len(selected_ids) != 1:
            return

        run_id = next(iter(selected_ids))

        if run_id not in self.restorable_run_ids:
            return

        self.active_run_id = run_id
        self.restore_run_id = run_id
        self.accept()

    def export_csv(self):
        if not self.training_history:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.t("history.export_title"),
            self.t("history.export_filename"),
            self.t("dialog.filter.csv")
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            with open(file_path, "w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(
                    (
                        self.t("history.csv.run"),
                        self.t("history.csv.time"),
                        self.t("history.csv.training_data"),
                        self.t("history.csv.initialized"),
                        self.t("history.csv.mode"),
                        self.t("history.csv.weight_initialization"),
                        self.t("history.csv.bias_initialization"),
                        self.t("history.csv.learning_rate"),
                        self.t("history.csv.momentum"),
                        self.t("history.csv.error_limit"),
                        self.t("history.csv.requested_epochs"),
                        self.t("history.csv.completed_epochs"),
                        self.t("history.csv.start_error"),
                        self.t("history.csv.end_error"),
                        self.t("history.csv.maximum_error"),
                        self.t("history.csv.duration_seconds"),
                        self.t("history.csv.status")
                    )
                )

                for entry in self.training_history:
                    writer.writerow(
                        (
                            entry["run_id"],
                            entry["timestamp"],
                            entry["training_data"],
                            self.t("common.yes") if entry["initialized"] else self.t("common.no"),
                            self.training_mode_text(entry),
                            entry["weight_initialization"],
                            entry["bias_initialization"],
                            entry["learning_rate"],
                            entry.get("momentum", 0.0),
                            entry["error_limit"],
                            entry["requested_epochs"],
                            entry["completed_epochs"],
                            entry["start_error"],
                            entry["end_error"],
                            entry["maximum_absolute_error"],
                            entry["elapsed_seconds"],
                            entry["status_text"]
                        )
                    )

        except OSError as error:
            QMessageBox.critical(
                self,
                self.t("history.export_error_title"),
                str(error)
            )
            return

        QMessageBox.information(
            self,
            self.t("history.export_success_title"),
            self.t("history.export_success")
        )

    def get_training_history(self):
        return deepcopy(self.training_history)

    def get_restore_run_id(self):
        return self.restore_run_id
