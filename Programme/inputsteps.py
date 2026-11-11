"""Raw input grids for manual exploration; never applied to training records."""
import math
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from functools import reduce
from math import gcd
from PySide6.QtGui import QValidator


def input_step(mapping):
    value = mapping.get("input_step")
    if mapping.get("data_type") == "binary" or mapping.get("role", "input") != "input":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return float(value)
    return None


def infer_step(values):
    values = sorted({round(float(v), 10) for v in values
                     if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)})
    if len(values) < 2:
        return None
    integers = [int(Decimal(str(v)) * 10**10) for v in values]
    return reduce(gcd, (b-a for a, b in zip(integers, integers[1:]))) / 10**10


class InputGrid:
    def __init__(self, minimum, maximum, step):
        self.origin = Decimal(str(minimum))
        self.step = Decimal(str(step))
        self.count = max(0, int(((Decimal(str(maximum))-self.origin)/self.step).to_integral_value(rounding=ROUND_FLOOR)))
        self.minimum = float(self.origin)
        self.maximum = self.value(self.count)
        self.positions = min(self.count, 2_000_000_000)
        self.decimals = min(10, max(0, -self.origin.normalize().as_tuple().exponent,
                                    -self.step.normalize().as_tuple().exponent))

    def value(self, index):
        return float(self.origin + max(0, min(self.count, index))*self.step)

    def index(self, value):
        return max(0, min(self.count, int(((Decimal(str(value))-self.origin)/self.step).to_integral_value(rounding=ROUND_HALF_UP))))

    def snap(self, value):
        return self.value(self.index(value))

    def from_position(self, position):
        index = int((Decimal(position)*self.count/max(1, self.positions)).to_integral_value(rounding=ROUND_HALF_UP))
        return self.value(index)

    def position(self, value):
        return round(self.index(value)*self.positions/max(1, self.count))


class SteppedInputMixin:
    def setValue(self, value):
        grid = getattr(self, "_input_grid", None)
        super().setValue(grid.snap(value) if grid else value)

    def _raw_text_value(self, text):
        text = text.strip()
        if self.prefix() and text.startswith(self.prefix()):
            text = text[len(self.prefix()):]
        if self.suffix() and text.endswith(self.suffix()):
            text = text[:-len(self.suffix())]
        return self.locale().toDouble(text.strip())

    def validate(self, text, position):
        if getattr(self, "_input_grid", None):
            value, valid = self._raw_text_value(text)
            if valid and math.isfinite(value):
                return QValidator.State.Acceptable, text, position
        return super().validate(text, position)

    def valueFromText(self, text):
        grid = getattr(self, "_input_grid", None)
        if grid:
            value, valid = self._raw_text_value(text)
            if valid and math.isfinite(value):
                return grid.snap(value)
        return super().valueFromText(text)


def configure_editor(editor, mapping, minimum, maximum):
    step = input_step(mapping)
    if step is None:
        editor._input_grid = None
        return minimum, maximum
    calibration = mapping.get("calibration") or {}
    if calibration.get("mode") in ("minmax_0_1", "minmax_minus1_1"):
        minimum, maximum = calibration["source_min"], calibration["source_max"]
    grid = InputGrid(minimum, maximum, step)
    editor._input_grid = grid
    editor.setDecimals(max(2, grid.decimals))
    editor.setRange(grid.minimum, grid.maximum)
    editor.setSingleStep(step)
    editor.setKeyboardTracking(False)
    editor.setValue(editor.value())
    return grid.minimum, grid.maximum


def configure_slider(slider, grid):
    slider._input_grid = grid
    if grid:
        slider.setRange(0, grid.positions)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setEnabled(grid.positions > 0)


def slider_value(slider, position, minimum, maximum):
    grid = getattr(slider, "_input_grid", None)
    if grid:
        return grid.from_position(position)
    return minimum + position/max(1, slider.maximum())*(maximum-minimum)


def sync_slider(slider, value, minimum, maximum):
    grid = getattr(slider, "_input_grid", None)
    if maximum <= minimum:
        return
    position = grid.position(value) if grid else round((value-minimum)/(maximum-minimum)*slider.maximum())
    blocked = slider.blockSignals(True)
    slider.setValue(max(0, min(slider.maximum(), position)))
    slider.blockSignals(blocked)
