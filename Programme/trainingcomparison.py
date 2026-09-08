# -------------------------------------------------------------------------------------------------
# Datei: trainingcomparison.py
# Zweck: Bietet eine kompakte, nicht blockierende Auswahl älterer Trainingskurven.
# Letzte Änderung: 05.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


COMPARISON_COLORS = ("#a34c97", "#27804c", "#b87817", "#7164b5", "#387f85", "#b64c53")
MAX_COMPARISON_RUNS = 3


def metric_curve_key(metric):
    return "maximum_error_curve_points" if metric == "maximum" else "curve_points"


def metric_chart_title(language, metric, logarithmic=False):
    if metric == "maximum":
        return language.text("training.metric.maximum_log" if logarithmic else "training.metric.maximum")
    return language.text("training.chart.title_logarithmic" if logarithmic else "training.chart.title")


def comparison_color(run_id):
    return COMPARISON_COLORS[(int(run_id) - 1) % len(COMPARISON_COLORS)]


def normalized_curve(points):
    """Übernimmt ausschließlich echte, endliche Messpunkte aus der Historie."""

    valid = {}
    for point in points or []:
        try:
            epoch, error = point
            epoch, error = int(epoch), float(error)
        except (TypeError, ValueError, OverflowError):
            continue
        if epoch >= 1 and math.isfinite(error) and error >= 0:
            valid[epoch] = error
    return sorted(valid.items())


def clipped_curve(points, maximum_epoch, logarithmic=False):
    """Begrenzt die Referenzkurve auf den sichtbaren Fortschritt des aktuellen Laufs."""

    visible = []
    for epoch, error in points:
        if epoch <= maximum_epoch:
            visible.append((epoch, error))
            continue
        if visible and visible[-1][0] < maximum_epoch:
            previous_epoch, previous_error = visible[-1]
            fraction = (maximum_epoch - previous_epoch) / (epoch - previous_epoch)
            if logarithmic and previous_error > 0 and error > 0:
                boundary_error = math.exp(
                    math.log(previous_error)
                    + fraction * (math.log(error) - math.log(previous_error))
                )
            else:
                boundary_error = previous_error + fraction * (error - previous_error)
            visible.append((maximum_epoch, boundary_error))
        break
    return visible


class TrainingComparisonPopup(QFrame):
    """Popup ohne exec(): Die Trainingsschleife läuft nach dem Öffnen weiter."""

    selection_changed = Signal(object)

    def __init__(self, language, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.language = language
        self.selected_ids = set()
        self.error_metric = "mse"
        self.setWindowTitle(language.text("training.comparison.title"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            "", language.text("training.comparison.run"),
            language.text("training.comparison.date"),
            language.text("training.comparison.epochs"),
            language.text("training.comparison.max_error"),
        ])
        self.table.horizontalHeaderItem(4).setToolTip(
            language.text("training.comparison.max_error_tip")
        )
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.itemChanged.connect(self._selection_changed)
        layout.addWidget(self.table)
        self.empty_label = QLabel(language.text("training.comparison.empty"), self)
        layout.addWidget(self.empty_label)
        self.setToolTip(language.text("training.comparison.hint"))

    def set_runs(self, runs, selected_ids):
        self.selected_ids = {run["run_id"] for run in runs if run["run_id"] in selected_ids}
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(runs))
            german = self.language.current_language == "de"
            for row, run in enumerate(runs):
                run_id = run["run_id"]
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                check.setData(Qt.ItemDataRole.UserRole, run_id)
                check.setCheckState(Qt.CheckState.Checked if run_id in selected_ids else Qt.CheckState.Unchecked)
                self.table.setItem(row, 0, check)
                timestamp = str(run.get("timestamp", ""))
                try:
                    date = datetime.fromisoformat(timestamp).strftime("%d.%m.%y")
                except ValueError:
                    date = "–"
                epochs = f"{int(run.get('completed_epochs', 0)):,}"
                if german:
                    epochs = epochs.replace(",", ".")
                error = run.get("maximum_absolute_error")
                error_text = "–"
                if isinstance(error, (int, float)) and math.isfinite(error):
                    error_text = f"{error:.4g}"
                    if german:
                        error_text = error_text.replace(".", ",")
                for column, value in enumerate((str(run_id), date, epochs, error_text), start=1):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                    if column == 1:
                        item.setForeground(QColor(comparison_color(run_id)))
                        if self.error_metric == "maximum" and not run.get("maximum_error_curve_points"):
                            item.setText(value + " –")
                            item.setToolTip(self.language.text("training.metric.unavailable"))
                    if column == 2:
                        item.setToolTip(timestamp.replace("T", " "))
                    if column == 4:
                        item.setToolTip(self.language.text("training.comparison.max_error_tip") + f": {error}")
                    self.table.setItem(row, column, item)
        finally:
            self.table.blockSignals(False)
        self.update_available_choices()
        self.table.setVisible(bool(runs))
        self.empty_label.setVisible(not runs)
        self.table.resizeColumnsToContents()
        width = sum(self.table.columnWidth(i) for i in range(5))
        scrollbar_width = self.table.verticalScrollBar().sizeHint().width() if len(runs) > 8 else 0
        self.table.setFixedSize(
            width + scrollbar_width + 2 * self.table.frameWidth() + 2,
            self.table.horizontalHeader().height() + min(8, len(runs)) * 25 + 2 * self.table.frameWidth(),
        )
        self.adjustSize()

    def _selection_changed(self, item):
        if item.column() != 0:
            return
        run_id = item.data(Qt.ItemDataRole.UserRole)
        if (item.checkState() == Qt.CheckState.Checked
                and run_id not in self.selected_ids
                and len(self.selected_ids) >= MAX_COMPARISON_RUNS):
            self.table.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.table.blockSignals(False)
            return
        selected = {
            self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(self.table.rowCount())
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        }
        self.selected_ids = selected
        self.update_available_choices()
        self.selection_changed.emit(selected)

    def update_available_choices(self):
        """Nach drei Kurven bleiben nur die gewählten Häkchen zum Abwählen aktiv."""

        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                check = self.table.item(row, 0)
                available = (
                    check.checkState() == Qt.CheckState.Checked
                    or len(self.selected_ids) < MAX_COMPARISON_RUNS
                )
                flags = Qt.ItemFlag.ItemIsUserCheckable
                if available:
                    flags |= Qt.ItemFlag.ItemIsEnabled
                check.setFlags(flags)
                check.setToolTip("" if available else self.language.text("training.comparison.limit"))
        finally:
            self.table.blockSignals(False)
