"""Shared binary-state colors with compatible legacy presentation."""
from PySide6.QtGui import QColor

DEFAULT_ON = "#00c853"
DEFAULT_OFF = "#d91e18"


def state_palette(colors, state, legacy):
    """Return border/background/text; retain existing look for default colors."""
    default = DEFAULT_ON if state else DEFAULT_OFF
    color = QColor((colors or {}).get("binary_state_on" if state else "binary_state_off", default))
    if not color.isValid() or color.name() == default:
        return legacy
    luminance = .2126 * color.redF() + .7152 * color.greenF() + .0722 * color.blueF()
    return color.darker(135).name(), color.name(), "#111111" if luminance > .45 else "#ffffff"
