"""State-free characteristic slices and their application-view presentation."""
import math
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QLabel, QMessageBox, QToolTip,
    QPushButton, QSizePolicy, QSlider, QWidget)

from trainingdataio import TrainingDataIO
from colorpalette import choose_color


COLORS = dict(curve="#1676b8", point="#e05829", axes="#364655", grid="#dde4eb")


def nice_ticks(low, high, intervals, expand=False):
    """Round tick spacing without changing the sampled input domain."""
    raw = (high-low) / max(2, intervals)
    power = 10.0 ** math.floor(math.log10(raw))
    step = min((power*n for n in (1, 2, 5, 10)),
               key=lambda value: abs(math.log(value/raw)))
    start = math.floor(low/step + 1e-10) if expand else math.ceil(low/step - 1e-10)
    end = math.ceil(high/step - 1e-10) if expand else math.floor(high/step + 1e-10)
    ticks = [0.0 if i == 0 else i*step for i in range(start, end+1)]
    return (ticks[0], ticks[-1], ticks) if expand else (low, high, ticks)


def tick_label(value):
    return format(value, ".12g")


def clean_settings(data):
    data = data if isinstance(data, dict) else {}
    result = {key: data.get(key) for key in ("input_id", "output_id")}
    for key in ("input_id", "output_id"):
        if not isinstance(result[key], (str, int)):
            result[key] = None
    result["working_point"] = bool(data.get("working_point", True))
    # Old layouts may contain manual bounds. Display ranges are now always automatic.
    for key, default in COLORS.items():
        value = data.get(key, default)
        result[key] = value if isinstance(value, str) and QColor(value).isValid() else default
    return result


def sample_slice(forward, specification, inputs, output, raw_values, x_id,
                 bounds, binary_x, cancel, cached_points=None):
    """Only plain snapshots enter this worker; no live neuron or Qt access."""
    internal = {item["id"]: TrainingDataIO.scale_value(raw_values[item["id"]], item["calibration"])
                for item in inputs}
    x_calibration = next(item["calibration"] for item in inputs if item["id"] == x_id)

    def evaluate(x):
        if cancel.is_set():
            return None
        values = dict(internal)
        values[x_id] = TrainingDataIO.scale_value(x, x_calibration)
        _, outputs = forward(specification, values)
        return x, TrainingDataIO.unscale_value(outputs[output["id"]], output["calibration"])

    points = cached_points
    if points is None:
        low, high = bounds
        xs = (0., 1.) if binary_x else [low + (high - low) * i / 160 for i in range(161)]
        points = []
        for x in xs:
            point = evaluate(x)
            if point is None:
                return None
            points.append(point)
    point = evaluate(raw_values[x_id])
    return (points, point) if point is not None else None


class CurvePlot(QWidget):
    """Cache axes and curve; moving the working point only repaints its small area."""
    input_value_requested = Signal(float)

    def __init__(self, tr, settings, parent=None):
        super().__init__(parent)
        self.tr = tr
        self.settings = clean_settings(settings)
        self._points = []
        self._revision = 0
        self._background = None
        self._background_key = None
        self._box = QRectF()
        self._range = None
        self.point = None
        self.target_points = []
        self.target = None
        self.target_record = None
        self.context = ""
        self.target_source_key = None
        self.x_label = self.y_label = ""
        self.output_unit = ""
        self.input_name = tr("Eingang", "Input")
        self.input_unit = ""
        self.binary_x = False
        self.note = ""
        self.setMinimumSize(220, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.info_button = QPushButton("i", self)
        self.info_button.setAutoDefault(False)
        self.info_button.setFixedSize(18, 18)
        self.info_button.setToolTip(tr("Kennlinie und Arbeitspunkt erläutern", "Explain characteristic and working point"))
        self.info_button.clicked.connect(self.show_information)
        self.show_targets = QCheckBox(tr("Trainingspunkte anzeigen", "Show training points"), self)
        self.show_targets.setChecked(True)
        self.show_targets.toggled.connect(self.target_visibility_changed)
        self.show_targets.move(4, 2)
        self.input_bounds = None
        self.input_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.input_slider.setRange(0, 10000)
        self.input_slider.setEnabled(False)
        self.input_slider.setAccessibleName(tr("Eingangswert", "Input value"))
        self.input_slider.setGeometry(8, 50, max(1, self.width()-16), 22)
        self.input_slider.valueChanged.connect(self.input_slider_changed)

    def configure_input_slider(self, bounds, value=None, enabled=False):
        self.input_bounds = bounds
        self.input_slider.setEnabled(bool(enabled and bounds and bounds[1] > bounds[0]))
        if bounds is None or value is None or bounds[1] <= bounds[0]:
            return
        low, high = bounds
        position = round(max(0., min(1., (value-low)/(high-low))) * 10000)
        blocked = self.input_slider.blockSignals(True)
        self.input_slider.setValue(position)
        self.input_slider.blockSignals(blocked)
        self.input_slider.setToolTip(f"{self.x_label}: {value:.6g}")

    def input_slider_changed(self, position):
        if self.input_slider.isEnabled() and self.input_bounds is not None:
            low, high = self.input_bounds
            self.input_value_requested.emit(low + (high-low)*position/10000.)

    def target_visibility_changed(self):
        self._background_key = None
        self.update()

    def set_targets(self, points):
        if points != self.target_points:
            self.target_points = points
            self._background_key = None
            self.update()
        self.set_point(self.point)

    def comparison_at(self, raw_x):
        exact = [(y, number) for x, y, number in self.target_points
                 if math.isclose(x, raw_x, rel_tol=1e-10, abs_tol=1e-12)]
        if exact:
            return exact[0]
        groups = {}
        for x, y, _ in self.target_points:
            groups.setdefault(x, []).append(y)
        lower = [x for x in groups if x < raw_x]
        upper = [x for x in groups if x > raw_x]
        if not lower or not upper:
            return None, None
        left, right = max(lower), min(upper)
        if any(not all(math.isclose(y, groups[x][0], rel_tol=1e-10, abs_tol=1e-12)
                       for y in groups[x]) for x in (left, right)):
            return None, None
        fraction = (raw_x-left)/(right-left)
        return groups[left][0]*(1-fraction)+groups[right][0]*fraction, None

    def comparison_text(self):
        if self.point is None:
            return ""
        x, y = self.point
        fmt = lambda value: format(value, ".6g").replace(".", self.tr(",", "."))
        if self.target is None:
            return (f"{self.x_label}: {fmt(x)} → {self.y_label}: {fmt(y)} · "
                    + self.tr("Kein passender Sollwert verfügbar.", "No matching target available."))
        error = abs(self.target-y)
        percent = error/abs(self.target)*100 if self.target else None
        prefix = (self.tr("Sollwert geschätzt (linear interpoliert)", "Estimated target (linear interpolation)")
                  if self.target_record is None else self.tr("Datensatz", "Record") + f" {self.target_record}")
        percentage = (f" ({fmt(percent)} " + self.tr("% vom Sollwert", "% of target") + ")"
                      + self.tr("\nDer Prozentwert bezieht sich auf den Betrag des Sollwerts; nahe null kann er sehr groß werden.",
                                "\nThe percentage is relative to the absolute target value; near zero it can become very large.")
                      if percent is not None and math.isfinite(percent) else "")
        deviation = self.tr("Abweichung zur Schätzung", "Deviation from estimate") if self.target_record is None else self.tr("Abweichung", "Deviation")
        return (f"{prefix} · {self.x_label}: {fmt(x)} → {self.y_label}: "
                + self.tr("Soll", "Target") + f" {fmt(self.target)} | " + self.tr("Ist", "Actual")
                + f" {fmt(y)} | {deviation} {fmt(error)}{percentage}")

    def deviation_text(self):
        if self.point is None:
            return ""
        number = lambda value: format(value, ".2f").replace(".", self.tr(",", "."))
        input_unit = " " + self.input_unit if self.input_unit else ""
        prefix = f"{self.input_name} = {number(self.point[0])}{input_unit} | "
        unit = " " + self.output_unit if self.output_unit else ""
        fmt = lambda value: number(value) + unit
        actual = self.tr("Ist", "Actual") + " = " + fmt(self.point[1])
        if self.target is None:
            return prefix + actual + " | " + self.tr("Kein passender Sollwert verfügbar.", "No matching target available.")
        error = abs(self.target-self.point[1])
        estimate = " ≈" if self.target_record is None else ""
        target_sign = " ≈ " if self.target_record is None else " = "
        return (prefix + self.tr("Soll", "Target") + target_sign + fmt(self.target) + " | "
                + actual + " | " + self.tr("Abweichung", "Deviation") + f"{estimate} {fmt(error)}")

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, value):
        self._points = value
        self._revision += 1
        self._background_key = None
        self.update()

    def explanation(self):
        return self.tr(
            "Blau: Netzkennlinie. Orange: aktuelle Netzvorhersage. Gelb: Trainings-Sollpunkte und "
            "hervorgehobener Sollwert. Die gestrichelte senkrechte Strecke zeigt die Abweichung "
            "am aktuellen Eingangswert. Die Eingabe erfolgt über den Schieberegler oberhalb der Grafik oder die Eingangskachel.\n\n"
            "Zwischen benachbarten passenden analogen Sollpunkten wird linear interpoliert. "
            "Geschätzte Sollwerte werden ausdrücklich gekennzeichnet. Keine Extrapolation und keine "
            "Interpolation bei widersprüchlichen Grenzwerten. Ohne passenden Sollwert wird keine Fehlerstrecke gezeigt. "
            "Die Kennlinie setzt genau einen analogen Eingang und einen analogen Ausgang voraus; mehrere Ausgänge sind erlaubt.",
            "Blue: network characteristic. Orange: current network prediction. Yellow: training targets and "
            "highlighted target. The dashed vertical segment shows the deviation at the current input value. "
            "Change the input using the slider above the chart or the input card.\n\n"
            "Targets are linearly interpolated between neighboring matching analog target points. "
            "Estimated targets are explicitly labeled. No extrapolation or interpolation at conflicting "
            "boundary targets. Without a matching target, no error segment is shown. The characteristic requires "
            "exactly one analog input and a selected analog output; multiple outputs are allowed.")

    def show_information(self):
        # Parent the modal dialog to the real application window, not the
        # embedded card: Qt would otherwise embed the popup into the scene.
        from graphicalexperimentdialog import show_yellow_information_dialog

        parent = self.window()
        proxy = parent.graphicsProxyWidget()
        if proxy is not None and proxy.scene() is not None:
            views = proxy.scene().views()
            if views:
                parent = views[0].window()
        show_yellow_information_dialog(
            parent, self.tr("Zur Netzkennlinie", "About the characteristic"),
            self.explanation(), self.tr("Schließen", "Close"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.info_button.move(max(0, self.width()-20), max(0, self.height()-20))
        self.input_slider.setGeometry(8, 50, max(1, self.width()-16), 22)
        self._background_key = None

    def map_point(self, pair):
        if pair is None or self._range is None:
            return None
        xmin, xmax, ymin, ymax = self._range
        return QPointF(self._box.left() + (pair[0]-xmin)/(xmax-xmin)*self._box.width(),
                       self._box.bottom() - (pair[1]-ymin)/(ymax-ymin)*self._box.height())

    def set_point(self, point):
        old_point, old_target, old_context = self.point, self.target, self.context
        self.point = point
        self.target, self.target_record = self.comparison_at(point[0]) if point is not None else (None, None)
        self.context = self.comparison_text()
        self.setToolTip(self.context)
        if (point, self.target, self.context) == (old_point, old_target, old_context):
            return
        if self._background_key is None or self._range is None:
            self.update()
            return
        area = QRectF()
        for pair, target in ((old_point, old_target), (point, self.target)):
            if pair is not None:
                for value in (pair[1], target):
                    if value is not None:
                        pos = self.map_point((pair[0], value))
                        dot = QRectF(pos.x()-9, pos.y()-9, 18, 18)
                        area = area.united(dot) if not area.isNull() else dot
        if not area.isNull():
            self.update(area.toAlignedRect())
        self.update(0, 24, self.width(), 24)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            position = self.map_point(self.point)
            if (self.settings["working_point"] and position is not None
                    and self._box.contains(position)
                    and (position - QPointF(event.pos())).manhattanLength() <= 14):
                text = self.context
                QToolTip.showText(event.globalPos(), text, self)
            elif 26 <= event.pos().y() <= 48 and self.context:
                QToolTip.showText(event.globalPos(), self.context, self)
            else:
                QToolTip.hideText()
            event.accept()
            return True
        return super().event(event)

    def ensure_background(self, resolution=None):
        # A widget embedded in a graphics scene also inherits the view zoom.
        # Its own devicePixelRatioF() alone does not describe the target pixels.
        ratio = self.devicePixelRatioF() if resolution is None else resolution
        ratio = max(0.001, round(ratio, 6))
        key = (self.width(), self.height(), ratio, self.font().toString(),
               self._revision, self.x_label, self.y_label, self.binary_x, self.note,
               tuple(self.settings[k] for k in COLORS), self.show_targets.isChecked())
        if key == self._background_key:
            return
        self._background = QPixmap(max(1, math.ceil(self.width()*ratio)),
                                   max(1, math.ceil(self.height()*ratio)))
        self._background.setDevicePixelRatio(ratio)
        self._background.fill(Qt.GlobalColor.transparent)
        p = QPainter(self._background)
        p.setFont(self.font())
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._range = None
        s = self.settings
        p.setPen(QColor(s["axes"]))
        if not self.points:
            p.drawText(self.rect().adjusted(8, 8, -8, -24),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       self.note or self.tr("Kennlinie wird berechnet…", "Calculating characteristic…"))
        else:
            xmin, xmax = self.points[0][0], self.points[-1][0]
            ys = [y for _, y in self.points] + [y for _, y, _ in self.target_points]
            ymin, ymax = min(ys), max(ys)
            pad = max((ymax-ymin)*.05, abs(ymax)*.01, 1e-9)
            ymin, ymax = ymin-pad, ymax+pad
            if (all(math.isfinite(v) for v in (xmax-xmin, ymax-ymin))
                    and xmax > xmin and ymax > ymin):
                fm = p.fontMetrics()
                line = fm.height() + 2
                # Density follows available space; binary inputs keep only their two states.
                _, _, xticks = nice_ticks(xmin, xmax, max(2, (self.width()-60)//65))
                if self.binary_x:
                    xticks = [0., 1.]
                ymin, ymax, yticks = nice_ticks(ymin, ymax,
                    max(2, (self.height()-50)//max(40, line*2)), expand=True)
                self._range = xmin, xmax, ymin, ymax
                left = max(fm.horizontalAdvance(tick_label(v)) for v in yticks) + 7
                left = max(left, fm.horizontalAdvance(tick_label(xmin))/2+2)
                right = max(4, fm.horizontalAdvance(tick_label(xmax))/2+2)
                self._box = QRectF(left, 82, max(40, self.width()-left-right),
                                   max(40, self.height()-82-3*line-13))
                box = self._box
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                p.setPen(QPen(QColor(s["grid"]), 0))
                for x in xticks:
                    px = self.map_point((x, ymin)).x()
                    p.drawLine(QPointF(px, box.top()), QPointF(px, box.bottom()))
                for y in yticks:
                    py = self.map_point((xmin, y)).y()
                    p.drawLine(QPointF(box.left(), py), QPointF(box.right(), py))
                p.setPen(QColor(s["axes"]))
                for x in xticks:
                    px = self.map_point((x, ymin)).x()
                    width = fm.horizontalAdvance(tick_label(x))+4
                    p.drawText(QRectF(px-width/2, box.bottom()+2, width, line),
                               Qt.AlignmentFlag.AlignCenter, tick_label(x))
                for y in yticks:
                    py = self.map_point((xmin, y)).y()
                    p.drawText(QRectF(0, py-line/2, left-5, line),
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, tick_label(y))
                p.setPen(QPen(QColor(s["axes"]), 0))
                p.drawRect(box)
                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setClipRect(box.adjusted(-2, -2, 2, 2))
                if self.show_targets.isChecked():
                    p.setPen(QPen(QColor("#ab8735"), .7))
                    p.setBrush(QColor("#f4c430"))
                    for x, y, _ in self.target_points:
                        p.drawEllipse(self.map_point((x, y)), 3, 3)
                p.setPen(QPen(QColor(s["curve"]), 2))
                if self.binary_x:
                    p.setBrush(QColor(s["curve"]))
                    for pair in self.points:
                        p.drawEllipse(self.map_point(pair), 4, 4)
                else:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    path = QPainterPath()
                    path.moveTo(self.map_point(self.points[0]))
                    for pair in self.points[1:]:
                        path.lineTo(self.map_point(pair))
                    p.drawPath(path)
                p.restore()
        # One compact footer, no title and no separate axis-name margins.
        p.setPen(QColor(s["axes"]))
        caption = f"{self.x_label} (X) · {self.y_label} (Y)" if self.x_label else ""
        caption = p.fontMetrics().elidedText(caption, Qt.TextElideMode.ElideRight, max(1, self.width()-28))
        p.drawText(QRectF(2, self.height()-44, self.width()-28, 20), Qt.AlignmentFlag.AlignCenter, caption)
        items = [(s["curve"], self.tr("Netzkennlinie", "Network characteristic")),
                 (s["point"], self.tr("Istwert", "Actual"))]
        if self.show_targets.isChecked():
            items.append(("#f4c430", self.tr("Passende Sollwerte", "Matching targets")))
        cell = max(1, (self.width()-28)/len(items))
        for i, (color, text) in enumerate(items):
            x = 3+i*cell
            p.setPen(QPen(QColor(color), 2))
            p.setBrush(QColor(color))
            if i == 0:
                p.drawLine(QPointF(x, self.height()-11), QPointF(x+12, self.height()-11))
            else:
                p.drawEllipse(QPointF(x+6, self.height()-11), 3, 3)
            p.setPen(QColor(s["axes"]))
            text = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(1, int(cell)-19))
            p.drawText(QRectF(x+16, self.height()-22, cell-18, 20), Qt.AlignmentFlag.AlignVCenter, text)
        p.end()
        self._background_key = key

    def paintEvent(self, event):
        p = QPainter(self)
        transform = p.deviceTransform()
        resolution = max(math.hypot(transform.m11(), transform.m12()),
                         math.hypot(transform.m21(), transform.m22()))
        self.ensure_background(resolution)
        # The buffer is already rendered at the final pixel density. Avoid a
        # second smoothing pass when its origin falls between device pixels.
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawPixmap(0, 0, self._background)
        p.setPen(QColor(self.settings["axes"]))
        p.fillRect(QRectF(3, 26, self.width()-6, 22), QColor("#edf4f9"))
        context = p.fontMetrics().elidedText(self.deviation_text(), Qt.TextElideMode.ElideRight, max(1, self.width()-14))
        p.drawText(QRectF(7, 26, self.width()-14, 22), Qt.AlignmentFlag.AlignVCenter, context)
        position = self.map_point(self.point)
        if self.settings["working_point"] and position is not None:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setClipRect(self._box.adjusted(-2, -2, 2, 2))
            if self.target is not None:
                target_position = self.map_point((self.point[0], self.target))
                p.setPen(QPen(QColor(self.settings["point"]), 1.5, Qt.PenStyle.DashLine))
                p.drawLine(position, target_position)
                p.setPen(QPen(QColor("#735500"), 1.2))
                p.setBrush(QColor("#f4c430"))
                p.drawEllipse(target_position, 6.5, 6.5)
            p.setPen(QPen(QColor(self.settings["point"]), 2))
            p.setBrush(QColor(self.settings["point"]))
            p.drawEllipse(position, 4, 4)


class CurveSettings(QDialog):
    def __init__(self, host, settings):
        super().__init__(host)
        self.host, self.values = host, clean_settings(settings)
        tr = host.tr
        self.setWindowTitle(tr("Netzkennlinie einstellen", "Configure characteristic"))
        form = QFormLayout(self)
        self.inputs, self.outputs = QComboBox(), QComboBox()
        for combo, mappings, key in ((self.inputs, host.input_columns, "input_id"),
                                      (self.outputs, host.output_columns, "output_id")):
            for mapping in mappings:
                if mapping.get("data_type") == "binary":
                    continue
                n = mapping["neuron"]
                name = str(mapping.get("column_name") or "")
                combo.addItem(n.name + (f" – {name}" if name and name != n.name else ""), n.id)
            index = combo.findData(self.values[key])
            combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow(tr("X: Eingang", "X: Input"), self.inputs)
        form.addRow(tr("Y: Ausgang", "Y: Output"), self.outputs)
        self.working = QCheckBox(tr("Aktuellen Arbeitspunkt anzeigen", "Show current working point"))
        self.working.setChecked(self.values["working_point"])
        form.addRow(self.working)
        self.color_buttons = {}
        for key, de, en in (("curve", "Kennlinie", "Curve"), ("point", "Arbeitspunkt", "Working point"),
                            ("axes", "Achsen und Schrift", "Axes and text"), ("grid", "Gitternetz", "Grid")):
            button = QPushButton()
            self.color_buttons[key] = button
            self.update_color_button(button, self.values[key])
            button.clicked.connect(lambda checked=False, k=key, b=button: self.choose_color(k, b))
            form.addRow(tr(de, en), button)
        info = QLabel(tr("Die Kennlinie benötigt genau einen analogen Eingang und einen ausgewählten analogen Ausgang. "
                         "Sollwerte zwischen passenden Trainingspunkten werden linear interpoliert und als geschätzt gekennzeichnet. "
                         "Hintergrund: Kachelfarbe im Kontextmenü.",
                         "The characteristic requires exactly one analog input and a selected analog output. "
                         "Targets between matching training points are linearly interpolated and labeled as estimates. "
                         "Background: Card color in the context menu."))
        info.setWordWrap(True)
        form.addRow(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Abbrechen", "Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def choose_color(self, key, button):
        color = choose_color(self.values[key], self, self.host.tr("Farbe wählen", "Choose color"))
        if color.isValid():
            self.values[key] = color.name()
            self.update_color_button(button, color.name())

    @staticmethod
    def update_color_button(button, value):
        color = QColor(value)
        luminance = .2126*color.red() + .7152*color.green() + .0722*color.blue()
        text = "#000000" if luminance >= 145 else "#ffffff"
        button.setText(color.name())
        button.setStyleSheet(f"QPushButton {{ background-color: {color.name()}; color: {text}; "
                            "border: 1px solid #888; border-radius: 3px; padding: 4px; }")

    def accept(self):
        self.values.update(input_id=self.inputs.currentData(), output_id=self.outputs.currentData(),
                           working_point=self.working.isChecked())
        super().accept()


class CurveController(QObject):
    completed = Signal(int, object)

    def __init__(self, host, card_class, proxy_class, forward):
        super().__init__(host)
        self.host, self.card_class, self.proxy_class, self.forward = host, card_class, proxy_class, forward
        self.proxies = []
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="NeuronNetzCurve")
        self.cancel = Event()
        self.serial = 0
        self.busy = False
        self.pending = False
        self.closed = False
        self.cache = {}
        self.bounds_cache = {}
        self.request_signature = None
        self.latest_values = None
        self.latest_raw = {}
        self.jobs = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.start)
        self.completed.connect(self.finish)

    def available(self):
        return (len(self.host.input_columns) == 1
                and self.host.input_columns[0].get("data_type") != "binary"
                and any(m.get("data_type") != "binary" for m in self.host.output_columns))

    def unavailable_message(self):
        return self.host.tr(
            "Die Netzkennlinie ist nur für Netze mit genau einem Eingang verfügbar. "
            "Dieser Eingang und der ausgewählte Ausgang müssen analog sein.",
            "The network characteristic is only available for networks with exactly one input. "
            "This input and the selected output must be analog.")

    @staticmethod
    def stored_visible(proxy):
        return getattr(proxy, "characteristic_saved_visibility", proxy.isVisible())

    def create(self, data=None):
        data = data if isinstance(data, dict) else {}
        host = self.host
        settings = clean_settings(data.get("settings"))
        if not data.get("settings"):
            settings["input_id"] = host.input_columns[0]["neuron"].id if host.input_columns else None
            settings["output_id"] = next((m["neuron"].id for m in host.output_columns
                                          if m.get("data_type") != "binary"), None)
        card = self.card_class(host.tr, settings)
        proxy = self.proxy_class("characteristic")
        proxy.setWidget(card)
        host.scene.addItem(proxy)
        proxy.configure_card_size(260, 200)
        proxy.set_card_size(440, 300)
        proxy.setZValue(host.next_design_layer())
        geometry = dict(data)
        for key in ("x", "y", "width", "height", "layer"):
            if key in geometry:
                try:
                    number = float(geometry[key])
                    if not math.isfinite(number):
                        raise ValueError()
                    geometry[key] = number
                except (TypeError, ValueError, OverflowError):
                    geometry.pop(key)
        if "color" in geometry and not QColor(str(geometry["color"])).isValid():
            geometry.pop("color")
        host.apply_card_geometry(proxy, geometry)
        proxy.set_editable(host.edit_mode)
        self.proxies.append(proxy)
        card.plot.input_value_requested.connect(lambda value, target=proxy: self.set_input_value(target, value))
        card.plot.input_slider.sliderPressed.connect(host.input_slider_pressed)
        card.plot.input_slider.sliderReleased.connect(host.input_slider_released)
        self.refresh()
        return proxy

    def data(self, proxy):
        card = proxy.widget()
        return dict(settings=dict(card.plot.settings), x=proxy.x(), y=proxy.y(), width=card.width(),
                    height=card.height(), color=card.card_color.name(), transparent=card.card_transparent,
                    layer=proxy.zValue(), locked=proxy.locked, visible=self.stored_visible(proxy))

    def restore(self, items):
        self.refresh()
        for proxy in list(self.proxies):
            self.host.scene.removeItem(proxy)
            proxy.deleteLater()
        self.proxies.clear()
        self.cache.clear()
        self.request_signature = None
        for data in items if isinstance(items, list) else []:
            if isinstance(data, dict):
                self.create(data)

    def add(self):
        if not self.host.edit_mode:
            return
        if not self.available():
            QMessageBox.information(self.host,
                self.host.tr("Netzkennlinie", "Network characteristic"),
                self.unavailable_message())
            return
        self.host.begin_history_action()
        proxy = self.create()
        self.host.start_element_placement([proxy])

    def configure(self, proxy):
        if proxy.locked:
            return
        dialog = CurveSettings(self.host, proxy.widget().plot.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.host.begin_history_action()
            proxy.widget().plot.settings = clean_settings(dialog.values)
            proxy.widget().plot.update()
            self.host.finish_history_action()
            self.refresh()

    def update_outputs(self, values):
        """Reuse the exact accepted forward result; no extra forward pass for the dot."""
        if self.closed:
            return
        self.latest_values = dict(values)
        self.apply_points(values)
        try:
            raw = {m["neuron"].id: TrainingDataIO.unscale_value(values[m["neuron"].id], m["calibration"])
                   for m in self.host.input_columns}
        except (KeyError, TypeError, ValueError, OverflowError):
            return
        self.refresh(raw)

    def set_input_value(self, proxy, value):
        if (self.closed or self.host.edit_mode or proxy not in self.proxies
                or not proxy.isVisible() or not self.available() or not math.isfinite(value)):
            return
        identifier = proxy.widget().plot.settings["input_id"]
        for _card, controls, mapping in self.host.input_cards:
            if mapping["neuron"].id == identifier and mapping.get("data_type") != "binary":
                # The editor owns input state, saving and the normal forward calculation.
                controls["editor"].setValue(value)
                return

    def sync_input_sliders(self):
        if self.closed:
            return
        controls_by_id = {m["neuron"].id: (controls, m)
                          for _proxy, controls, m in self.host.input_cards}
        for proxy in self.proxies:
            plot = proxy.widget().plot
            item = controls_by_id.get(plot.settings["input_id"])
            if item is None or item[1].get("data_type") == "binary" or not proxy.isVisible() or not self.available():
                plot.configure_input_slider(None)
                continue
            editor = item[0]["editor"]
            plot.configure_input_slider((editor.minimum(), editor.maximum()), editor.value(),
                                        enabled=not self.host.edit_mode)

    def apply_points(self, values):
        outputs = {m["neuron"].id: m for m in self.host.output_columns}
        inputs = {m["neuron"].id: m for m in self.host.input_columns}
        for proxy in self.proxies:
            if not proxy.isVisible():
                continue
            plot = proxy.widget().plot
            try:
                x, y = inputs[plot.settings["input_id"]], outputs[plot.settings["output_id"]]
                if len(inputs) != 1 or x.get("data_type") == "binary" or y.get("data_type") == "binary":
                    plot.set_point(None)
                    continue
                point = (TrainingDataIO.unscale_value(values[x["neuron"].id], x["calibration"]),
                         TrainingDataIO.unscale_value(values[y["neuron"].id], y["calibration"]))
                plot.set_point(point)
            except (KeyError, TypeError, ValueError, OverflowError):
                plot.set_point(None)

    def refresh(self, raw=None):
        if self.closed:
            return
        host = self.host
        raw = host.current_input_values() if raw is None else raw
        jobs, signature = [], []
        mappings = {m["neuron"].id: m for m in host.input_columns + host.output_columns}
        for proxy in self.proxies:
            plot = proxy.widget().plot
            s = plot.settings
            x, y = mappings.get(s["input_id"]), mappings.get(s["output_id"])
            supported = (self.available() and x in host.input_columns
                         and y in host.output_columns and y.get("data_type") != "binary")
            if not supported:
                if not hasattr(proxy, "characteristic_saved_visibility"):
                    proxy.characteristic_saved_visibility = proxy.isVisible()
                proxy.hide()
                plot.points, plot.point = [], None
                self.cache.pop(proxy, None)
                continue
            if hasattr(proxy, "characteristic_saved_visibility"):
                proxy.setVisible(proxy.characteristic_saved_visibility)
                del proxy.characteristic_saved_visibility
            if not proxy.isVisible():
                continue
            if x not in host.input_columns or y not in host.output_columns:
                plot.points, plot.point = [], None
                plot.note = host.tr("Ein- oder Ausgang fehlt. Bitte Kennlinie einstellen.",
                                    "Input or output missing. Please configure the characteristic.")
                continue
            binary = x.get("data_type") == "binary"
            try:
                range_key = (s["input_id"], repr(x.get("calibration")), binary)
                if range_key not in self.bounds_cache:
                    self.bounds_cache[range_key] = (0., 1.) if binary else host.display_range(x)
                bounds = self.bounds_cache[range_key]
                if not all(math.isfinite(v) for v in bounds) or not 0 < bounds[1] - bounds[0] < math.inf:
                    raise ValueError()
            except (ValueError, TypeError, KeyError, OverflowError):
                plot.points, plot.point = [], None
                plot.note = host.tr("Ungültiger Eingabebereich in den Daten.", "Invalid input range in the data.")
                continue
            plot.binary_x = binary
            target_key = (s["input_id"], s["output_id"], id(host.records), len(host.records),
                          x["column_index"], y["column_index"])
            if target_key != plot.target_source_key:
                targets = []
                for number, record in enumerate(host.records, 1):
                    try:
                        tx, ty = float(record[x["column_index"]]), float(record[y["column_index"]])
                        if math.isfinite(tx) and math.isfinite(ty):
                            targets.append((tx, ty, number))
                    except (IndexError, KeyError, TypeError, ValueError, OverflowError):
                        continue
                plot.set_targets(targets)
                plot.target_source_key = target_key
            def label(mapping, role):
                name = mapping["neuron"].name
                extra = str(mapping.get("column_name") or "")
                unit = mapping.get("unit", "")
                return role + " " + name + (f" – {extra}" if extra and extra != name else "") + (f" [{unit}]" if unit else "")
            old_labels = plot.x_label, plot.y_label, plot.input_name, plot.input_unit
            plot.input_name = str(x.get("name") or x.get("column_name") or x["neuron"].name)
            plot.input_unit = str(x.get("unit") or "").strip()
            plot.output_unit = str(y.get("unit") or "").strip()
            plot.x_label = label(x, host.tr("Eingang", "Input"))
            plot.y_label = label(y, host.tr("Ausgang", "Output"))
            if y.get("data_type") == "binary":
                plot.y_label += host.tr(" (Rohwert)", " (raw value)")
            key = (s["input_id"], s["output_id"], tuple(bounds),
                   tuple(sorted((str(k), v) for k, v in raw.items() if k != s["input_id"])))
            signature.append((proxy, key))
            cached = self.cache.get(proxy)
            if cached and cached[0] == key:
                if plot.points is not cached[1]:
                    plot.points = cached[1]
            else:
                # Keep the last complete drawing until its replacement is ready.
                jobs.append((proxy, key, dict(id=y["neuron"].id, calibration=deepcopy(y["calibration"])),
                             s["input_id"], bounds, binary))
            plot.note = ""
            if old_labels != (plot.x_label, plot.y_label, plot.input_name, plot.input_unit):
                plot.set_point(plot.point)
                plot.update()
        self.sync_input_sliders()
        signature = tuple(signature)
        if signature == self.request_signature:
            return  # X alone changed: neither restart nor cancel a curve calculation.
        self.request_signature = signature
        self.serial += 1
        self.cancel.set()
        self.latest_raw = dict(raw)
        self.jobs = jobs
        self.pending = bool(jobs)
        if self.pending and not self.timer.isActive():
            self.timer.start()

    def start(self):
        if self.closed or self.busy or not self.pending:
            return
        self.pending = False
        jobs = list(self.jobs)
        raw = dict(self.latest_raw)
        inputs = [dict(id=m["neuron"].id, calibration=deepcopy(m["calibration"])) for m in self.host.input_columns]
        self.busy = True
        self.cancel = Event()
        cancel, number, forward, spec = self.cancel, self.serial, self.forward, self.host.forward_specification

        def work():
            results = []
            for proxy, key, output, x_id, bounds, binary in jobs:
                if cancel.is_set():
                    break
                try:
                    value = sample_slice(forward, spec, inputs, output, raw, x_id, bounds, binary, cancel)
                    results.append((proxy, key, value))
                except (ValueError, KeyError, TypeError, OverflowError):
                    results.append((proxy, key, None))
            return results

        future = self.executor.submit(work)
        def done(f):
            try:
                result = f.result()
            except Exception:
                result = [(proxy, key, None) for proxy, key, *_ in jobs]
            try:
                self.completed.emit(number, result)
            except RuntimeError:
                pass  # Closing the dialog cancels the work; no UI state to restore.
        future.add_done_callback(done)

    def finish(self, number, results):
        self.busy = False
        if self.closed:
            return
        if number == self.serial:
            for proxy, key, value in results:
                if proxy not in self.proxies:
                    continue
                plot = proxy.widget().plot
                if value is None:
                    plot.points, plot.point = [], None
                    plot.note = self.host.tr("Kennlinie nicht berechenbar. Zuordnung und Eingabedaten prüfen.",
                                             "Cannot calculate characteristic. Check mappings and input data.")
                else:
                    plot.points = value[0]
                    self.cache[proxy] = key, plot.points
                    if self.latest_values is None:
                        plot.set_point(value[1])
                plot.update()
            if self.latest_values is not None:
                self.apply_points(self.latest_values)
        if self.pending:
            self.timer.start()

    def close(self):
        self.closed = True
        self.timer.stop()
        self.cancel.set()
        self.executor.shutdown(wait=False, cancel_futures=True)
