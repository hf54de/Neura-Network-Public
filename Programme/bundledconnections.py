"""Cached schematic connections between topological layers, without changing the network."""
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor,QPainterPath,QPen,QPainter


class BundledConnections:
    def __init__(self, scene):
        self.scene = scene
        self.dirty = True
        self.path = QPainterPath()
        self.group_count = 0

    def invalidate(self, *args):
        self.dirty = True
        self.scene.update()

    def rebuild(self):
        net = self.scene.network
        self.path = QPainterPath()
        try:
            layers = net.get_topological_layers()
        except ValueError:
            # A temporarily cyclic editor graph still has a safe visual fallback.
            xs = sorted({n.x() for n in net.get_neurons()})
            layers = [[n for n in net.get_neurons() if n.x()==x] for x in xs]
        level = {n.id:i for i,layer in enumerate(layers) for n in layer}
        groups = {}
        for c in net.get_connections():
            pair = (level[c.source_neuron.id],level[c.target_neuron.id])
            sources,targets = groups.setdefault(pair,({},{}))
            sources[c.source_neuron.id] = c.source_neuron
            targets[c.target_neuron.id] = c.target_neuron
        self.group_count = len(groups)
        def line(a,b):
            self.path.moveTo(a);self.path.lineTo(b)
        for sources,targets in groups.values():
            starts = [n.get_output_port_position() for n in sources.values()]
            ends = [n.get_input_port_position() for n in targets.values()]
            right = max(p.x() for p in starts)
            left = min(p.x() for p in ends)
            margin = min(35,max(8,(left-right)/4))
            sx,tx = right+margin,left-margin
            sy = (min(p.y() for p in starts)+max(p.y() for p in starts))/2
            ty = (min(p.y() for p in ends)+max(p.y() for p in ends))/2
            for p in starts:line(p,QPointF(sx,p.y()))
            for p in ends:line(QPointF(tx,p.y()),p)
            line(QPointF(sx,min(p.y() for p in starts)),QPointF(sx,max(p.y() for p in starts)))
            line(QPointF(tx,min(p.y() for p in ends)),QPointF(tx,max(p.y() for p in ends)))
            middle = (sx+tx)/2
            self.path.moveTo(sx,sy);self.path.lineTo(middle,sy)
            self.path.lineTo(middle,ty);self.path.lineTo(tx,ty)
        self.dirty = False

    def paint(self, painter):
        if self.dirty:self.rebuild()
        background = QColor(self.scene.color_settings.get("canvas_background","#ffffff"))
        color = QColor("#a8c5d8" if background.lightness()<128 else "#526b7a")
        pen = QPen(color,1.0);pen.setCosmetic(True)
        # Align cosmetic strokes to pixel centers at every zoom level.
        transform = painter.deviceTransform()
        inverse, valid = transform.inverted()
        path = self.path
        if valid:
            device_path = transform.map(path)
            snapped = QPainterPath()
            for index in range(device_path.elementCount()):
                element = device_path.elementAt(index)
                point = QPointF(round(element.x-.5)+.5,round(element.y-.5)+.5)
                if element.isMoveTo():snapped.moveTo(point)
                else:snapped.lineTo(point)
            path = inverse.map(snapped)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.restore()
