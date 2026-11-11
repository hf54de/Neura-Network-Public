from chartcolors import ChartColors
"""Optional two-weight trajectory: recording data, selection and read-only plot."""
import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QVBoxLayout, QWidget, QSizePolicy)
from neurontype import NeuronType
from numberformat import linear_axis_ticks, linear_axis_label


def valid_pair(pair):
    return (isinstance(pair, (list, tuple)) and len(pair) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in pair)
            and pair[0] != pair[1])


def connection_label(connection):
    source, target = connection.source_neuron, connection.target_neuron
    return f"W{connection.id}: {source.name} (N{source.id}) → {target.name} (N{target.id})"


def default_pair(network):
    connections = sorted(network.get_connections(), key=lambda c: c.id)
    for kind in (NeuronType.OUTPUT, NeuronType.HIDDEN):
        for neuron in sorted(network.get_neurons(), key=lambda n: n.id):
            incoming = [c.id for c in connections if c.target_neuron is neuron]
            if neuron.neuron_type == kind and len(incoming) >= 2:
                return incoming[:2]
    return [c.id for c in connections[:2]]


def new_trajectory(network, pair):
    connections = {c.id: c for c in network.get_connections()}
    if not valid_pair(pair) or any(cid not in connections for cid in pair):
        raise ValueError("Invalid weight pair.")
    return {"version": 1, "connections": [
        {"id": cid, "source": connections[cid].source_neuron.id,
         "target": connections[cid].target_neuron.id, "label": connection_label(connections[cid])}
        for cid in pair], "points": [[0, connections[pair[0]].weight, connections[pair[1]].weight, None]]}


def append_trajectory(data, network, epoch, mse):
    if data is None:
        return
    connections = {c.id: c for c in network.get_connections()}
    first, second = (connections[c["id"]] for c in data["connections"])
    data["points"].append([int(epoch), float(first.weight), float(second.weight), float(mse)])


def validate_trajectory(data, completed_epochs, initial_state=None):
    """Reject malformed history before replacing the current project."""
    if data is None:
        return
    def number(value):
        return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Invalid trajectory.")
    connections, points = data.get("connections"), data.get("points")
    if not isinstance(connections, list) or len(connections) != 2:
        raise ValueError("Invalid trajectory connections.")
    for c in connections:
        if (not isinstance(c, dict) or not isinstance(c.get("label"), str)
                or any(not isinstance(c.get(k), int) or isinstance(c[k], bool) or c[k] < 1
                       for k in ("id", "source", "target")) or c["source"] == c["target"]):
            raise ValueError("Invalid trajectory connection.")
    if not valid_pair([c["id"] for c in connections]):
        raise ValueError("Duplicate trajectory connections.")
    if not isinstance(points, list) or len(points) != completed_epochs + 1:
        raise ValueError("Incomplete trajectory.")
    for epoch, point in enumerate(points):
        if (not isinstance(point, list) or len(point) != 4
                or type(point[0]) is not int or point[0] != epoch
                or not number(point[1]) or not number(point[2])
                or (point[3] is None and epoch != 0)
                or (point[3] is not None and (not number(point[3]) or point[3] < 0))):
            raise ValueError("Invalid trajectory point.")
    if initial_state is not None:
        saved = {c["id"]: c for c in initial_state["connections"]}
        for axis, connection in enumerate(connections, 1):
            c = saved.get(connection["id"])
            if (c is None or any(c[k] != connection[k] for k in ("source", "target"))
                    or c["weight"] != points[0][axis]):
                raise ValueError("Trajectory does not match initial network.")


class WeightSelectionDialog(QDialog):
    def __init__(self, network, language, pair=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(language.text("trajectory.select_title"))
        layout = QVBoxLayout(self)
        note = QLabel(language.text("trajectory.select_help")); note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout(); layout.addLayout(form)
        self.x_combo, self.y_combo = QComboBox(), QComboBox()
        connections = sorted(network.get_connections(), key=lambda c: c.id)
        for combo in (self.x_combo, self.y_combo):
            for c in connections:combo.addItem(connection_label(c), c.id)
            combo.setMinimumContentsLength(28)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        selected = pair if valid_pair(pair) and all(c in {v.id for v in connections} for c in pair) else default_pair(network)
        if len(selected) == 2:
            self.x_combo.setCurrentIndex(self.x_combo.findData(selected[0]))
            self.y_combo.setCurrentIndex(self.y_combo.findData(selected[1]))
        form.addRow(language.text("trajectory.x"), self.x_combo)
        form.addRow(language.text("trajectory.y"), self.y_combo)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(language.text("common.ok"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(language.text("common.cancel"))
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for combo in (self.x_combo,self.y_combo):combo.currentIndexChanged.connect(self.update_validity)
        self.update_validity()

    def pair(self):
        return [self.x_combo.currentData(), self.y_combo.currentData()]

    def update_validity(self, _index=None):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid_pair(self.pair()))


class WeightTrajectoryPlot(ChartColors, QWidget):
    def __init__(self, language, parent=None, *, end_label=None):
        super().__init__(parent)
        self.language = language
        self.end_label = end_label or language.text("trajectory.current")
        self.data = None
        self.comparison = []
        self.joined_comparison = False
        self.title = language.text("trajectory.title")
        self.message = language.text("trajectory.no_data")
        self._count, self._bounds = 0, None
        self.interactive = False
        self.view_bounds = None
        self._drag_position = None
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_trajectory(self, data, title=None, message=None):
        if self.comparison:
            self._count, self._bounds = 0, None
            self.reset_view()
        self.comparison = []
        self.joined_comparison = False
        if data is not self.data or (data and len(data["points"]) < self._count):
            self._count, self._bounds = 0, None
            self.reset_view()
        self.data = data
        self.title = title or self.language.text("trajectory.title")
        self.message = message or self.language.text("trajectory.no_data")
        if data:
            for _, x, y, _ in data["points"][self._count:]:
                if self._bounds is None:self._bounds = [x,x,y,y]
                else:
                    self._bounds[0] = min(self._bounds[0],x);self._bounds[1] = max(self._bounds[1],x)
                    self._bounds[2] = min(self._bounds[2],y);self._bounds[3] = max(self._bounds[3],y)
            self._count = len(data["points"])
        self.update()

    def set_comparison(self, series, joined=False):
        """Show two immutable historical traces on shared axes."""
        self.set_trajectory(series[0][1])
        self.comparison = list(series)
        end = series[0][1]["points"][-1]
        start = series[1][1]["points"][0]
        self.joined_comparison = bool(joined) and all(
            math.isclose(end[i],start[i],rel_tol=1e-12,abs_tol=1e-12) for i in (1,2))
        self.reset_view()
        self._bounds = None
        for _,data in series:
            for _,x,y,_ in data["points"]:
                if self._bounds is None:self._bounds = [x,x,y,y]
                else:
                    self._bounds = [min(self._bounds[0],x),max(self._bounds[1],x),
                                    min(self._bounds[2],y),max(self._bounds[3],y)]
        self.update()

    def number(self, value):
        return linear_axis_label(value, self.language.current_language)

    def plot_area(self):
        return QRectF(84,59 if self.comparison else 39,max(30,self.width()-108),
                      max(30,self.height()-(111 if self.comparison else 91)))

    def full_bounds(self):
        if self._bounds is None:
            return None
        xmin,xmax,ymin,ymax = self._bounds
        dx = max(xmax-xmin,abs(xmin)*.02,1e-5)
        dy = max(ymax-ymin,abs(ymin)*.02,1e-5)
        return xmin-dx*.1,xmax+dx*.1,ymin-dy*.1,ymax+dy*.1

    def reset_view(self):
        self.view_bounds = None
        self._drag_position = None
        self.unsetCursor()
        self.update()

    @staticmethod
    def clamp_interval(low, high, full_low, full_high):
        span = min(high-low, full_high-full_low)
        low = max(full_low,min(low,full_high-span))
        return low,low+span

    def wheelEvent(self, event):
        area = self.plot_area()
        full = self.full_bounds()
        delta = event.angleDelta().y()
        if not self.interactive or full is None or not area.contains(event.position()) or not delta:
            event.ignore()
            return
        current = self.view_bounds or full
        factor = .8 if delta > 0 else 1.25
        fractions = ((event.position().x()-area.left())/area.width(),
                     (area.bottom()-event.position().y())/area.height())
        bounds = []
        for index,fraction in zip((0,2),fractions):
            low,high = current[index:index+2]
            full_low,full_high = full[index:index+2]
            span = high-low
            new_span = min(full_high-full_low,max((full_high-full_low)/4096,span*factor))
            anchor = low+fraction*span
            bounds.extend(self.clamp_interval(anchor-fraction*new_span,
                          anchor+(1-fraction)*new_span,full_low,full_high))
        self.view_bounds = tuple(bounds)
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if (self.interactive and event.button() == Qt.MouseButton.LeftButton
                and self.view_bounds is not None and self.plot_area().contains(event.position())):
            self._drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_position is not None and self.view_bounds is not None:
            area = self.plot_area()
            delta = event.position()-self._drag_position
            xmin,xmax,ymin,ymax = self.view_bounds
            full = self.full_bounds()
            dx = -delta.x()/area.width()*(xmax-xmin)
            dy = delta.y()/area.height()*(ymax-ymin)
            self.view_bounds = (*self.clamp_interval(xmin+dx,xmax+dx,*full[:2]),
                                *self.clamp_interval(ymin+dy,ymax+dy,*full[2:]))
            self._drag_position = event.position()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_position is not None:
            self._drag_position = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.chart_color('#c9d6e4')));painter.setBrush(self.chart_color('white'))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),5,5)
        painter.setPen(self.chart_color('#244563'))
        if not self.data or not self.data['points']:
            painter.drawText(QRectF(12,8,self.width()-24,24),Qt.AlignmentFlag.AlignCenter,self.title)
            painter.drawText(QRectF(22,40,self.width()-44,self.height()-60),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,self.message)
            return
        fm = painter.fontMetrics()
        if self.comparison:
            width = max(1,(self.width()-108)//2)
            for index,(label,_) in enumerate(self.comparison):
                color = ('#167bc1','#ef7528')[index]
                painter.setPen(QPen(self.chart_color(color),1.7))
                left = 84+index*width
                painter.drawLine(QPointF(left,20),QPointF(left+16,20))
                painter.drawText(QRectF(left+22,8,width-25,24),Qt.AlignmentFlag.AlignVCenter,
                                 fm.elidedText(label,Qt.TextElideMode.ElideRight,width-25))
            painter.save()
            painter.translate(0,20)
        x = 90
        for color, key in (('#25844b', 'trajectory.start'), ('#ef7528', 'trajectory.current')):
            label = self.language.text(key) if key == "trajectory.start" else self.end_label
            painter.setPen(QPen(self.chart_color('#244563'),1) if self.comparison else Qt.PenStyle.NoPen)
            painter.setBrush(self.chart_color('white' if key == 'trajectory.start' else '#244563') if self.comparison else self.chart_color(color))
            painter.drawEllipse(QPointF(x,20),3,3)
            painter.setPen(self.chart_color('#244563'))
            painter.drawText(QRectF(x+9,8,fm.horizontalAdvance(label)+2,24),
                             Qt.AlignmentFlag.AlignVCenter,label)
            x += 9 + fm.horizontalAdvance(label) + 24
        title_width = max(0, self.width()-24-x)
        title = fm.elidedText("" if self.comparison else self.title,Qt.TextElideMode.ElideRight,title_width)
        painter.drawText(QRectF(x,8,title_width,24),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,title)
        if self.comparison:painter.restore()
        area = self.plot_area()
        xmin,xmax,ymin,ymax = self.view_bounds or self.full_bounds()
        def x_position(value):
            return area.left() + (value - xmin) / (xmax - xmin) * area.width()

        def y_position(value):
            return area.bottom() - (value - ymin) / (ymax - ymin) * area.height()

        def position(point):
            return QPointF(x_position(point[1]), y_position(point[2]))

        grid_pen = QPen(self.chart_color('#e0e8f0'))
        label_color = self.chart_color('#496178')
        for value in linear_axis_ticks(xmin, xmax):
            x = x_position(value)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
            painter.setPen(label_color)
            painter.drawText(
                QRectF(x - 36, area.bottom() + 5, 72, 18),
                Qt.AlignmentFlag.AlignCenter, self.number(value),
            )
        for value in linear_axis_ticks(ymin, ymax):
            y = y_position(value)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(label_color)
            painter.drawText(
                QRectF(22, y - 10, 55, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.number(value),
            )
        painter.setPen(QPen(self.chart_color('#91a4b8')));painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRect(area)
        painter.save();painter.setClipRect(area.adjusted(-5,-5,5,5))
        series = self.comparison or [(self.title,self.data)]
        for index,(_,data) in enumerate(series):
            points=data['points'];path=QPainterPath(position(points[0]))
            count=min(len(points),3000)
            for i in range(1,count):path.lineTo(position(points[round(i*(len(points)-1)/(count-1))]))
            color = ('#167bc1','#ef7528')[index]
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.chart_color(color),1.7));painter.drawPath(path)
            for end,point in enumerate((points[0],points[-1])):
                # In a continuation chain, mark only the overall start and end.
                if self.joined_comparison and ((index == 0 and end == 1) or (index == 1 and end == 0)):
                    continue
                if self.comparison:
                    painter.setPen(QPen(self.chart_color(color),1.5))
                    painter.setBrush(self.chart_color(color if end else 'white'))
                else:
                    painter.setPen(QPen(self.chart_color('white'),1))
                    painter.setBrush(self.chart_color('#ef7528' if end else '#25844b'))
                painter.drawEllipse(position(point),4.5,4.5)
        painter.restore();painter.setPen(self.chart_color('#244563'))
        fm=painter.fontMetrics()
        x_label=fm.elidedText(self.data['connections'][0]['label'],Qt.TextElideMode.ElideMiddle,int(area.width()))
        painter.drawText(QRectF(area.left(),area.bottom()+25,area.width(),20),Qt.AlignmentFlag.AlignCenter,x_label)
        painter.save();painter.translate(16,area.center().y());painter.rotate(-90)
        y_label=fm.elidedText(self.data['connections'][1]['label'],Qt.TextElideMode.ElideMiddle,int(area.height()))
        painter.drawText(QRectF(-area.height()/2,-10,area.height(),20),Qt.AlignmentFlag.AlignCenter,y_label);painter.restore()
