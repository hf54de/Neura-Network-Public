"""Shared binary-output diagnostic; independent of training and BOOL conversion."""
import math
from PySide6.QtGui import QColor


def normalize_limits(values=None):
    values = {} if values is None else values
    if not isinstance(values, dict):
        raise ValueError("Invalid binary uncertainty limits / Ungültige Unklarheitsgrenzen")
    low, high = values.get("lower", 0.3), values.get("upper", 0.7)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (low, high)):
        raise ValueError("Invalid binary uncertainty limits / Ungültige Unklarheitsgrenzen")
    if not 0 <= low < 0.5 < high <= 1:
        raise ValueError("Required / Erforderlich: 0 ≤ untere Grenze < 0,5 < obere Grenze ≤ 1")
    return {"lower": float(low), "upper": float(high)}


def is_uncertain(value, limits=None):
    limits = normalize_limits(limits)
    return limits["lower"] < value < limits["upper"]


def warning_style(colors):
    color = QColor((colors or {}).get("binary_state_uncertain", "#ffd966"))
    luminance = .2126 * color.redF() + .7152 * color.greenF() + .0722 * color.blueF()
    return f"background:{color.name()}; color:{'#111111' if luminance > .45 else '#ffffff'}; border:1px solid {color.darker(135).name()}; border-radius:4px;"


def warning_text(limits, german=True):
    low, high = limits["lower"], limits["upper"]
    if german:
        return f"Unklar: {low:g} < Ausgangswert < {high:g}. BOOL ist Ein bei > 0,5. Dies ist keine Aussage über die Richtigkeit der Vorhersage."
    return f"Uncertain: {low:g} < output value < {high:g}. BOOL is On above 0.5. This does not establish whether the prediction is correct."
