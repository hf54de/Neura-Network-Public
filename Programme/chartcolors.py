"""Shared display-only colors for the explicitly enabled diagrams."""
from functools import lru_cache
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

_background = "#ffffff"


def luminance(color):
    values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
              for v in (color.redF(), color.greenF(), color.blueF())]
    return sum(v * w for v, w in zip(values, (.2126, .7152, .0722)))


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def blend(a, b, amount):
    return QColor.fromRgbF(*[x + (y-x)*amount for x,y in
                            zip(a.getRgbF()[:3], b.getRgbF()[:3])])


@lru_cache(maxsize=512)
def adapted(rgba, background):
    original = QColor.fromRgba(rgba)
    bg = QColor(background)
    if original.red() == original.green() == original.blue() == 255:
        return bg.rgba()
    white, black = QColor("white"), QColor("black")
    ink = white if contrast(white, bg) > contrast(black, bg) else black
    # Pale neutral colors are grid lines, borders or tooltip panels.
    if original.saturationF() < .25 and original.lightnessF() > .7:
        amount = .10 if original.lightnessF() > .94 else (.22 if original.lightnessF() > .84 else .4)
        return blend(bg, ink, amount).rgba()
    result = QColor(original)
    result.setAlpha(255)
    required = min(7.0 if original.saturationF() < .5 else 4.5, contrast(ink, bg))
    if contrast(result, bg) < required:
        # Find the smallest change towards the more readable endpoint.
        low, high = 0.0, 1.0
        for _ in range(16):
            mid = (low + high) / 2
            if contrast(blend(original, ink, mid), bg) >= required: high = mid
            else: low = mid
        result = blend(original, ink, high)
    # Semi-transparent data dots should remain readable on a colored background.
    result.setAlpha(max(original.alpha(), 230))
    return result.rgba()


def set_chart_background(value):
    global _background
    color = QColor(value)
    _background = color.name() if color.isValid() else "#ffffff"
    app = QApplication.instance()
    if app:
        for widget in app.allWidgets():
            if getattr(widget, "chart_colors_enabled", False):widget.update()


class ChartColors:
    chart_colors_enabled = False

    def chart_color(self, *args):
        color = QColor(*args)
        if not self.chart_colors_enabled or _background == "#ffffff":
            return color
        return QColor.fromRgba(adapted(color.rgba(), _background))
