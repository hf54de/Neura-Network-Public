# -------------------------------------------------------------------------------------------------
# Datei: numberformat.py
# Zweck: Formatiert Zahlen einheitlich für Anzeigen und Eingabefelder.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math


def format_number(
    value,
    significant_digits=6,
    scientific_lower=0.0001,
    scientific_upper=10000000.0
):
    """Formatiert Zahlen kompakt, ohne die interne Genauigkeit zu ändern."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if not math.isfinite(number):
        return str(number)

    if number == 0.0:
        return "0"

    digits = max(1, int(significant_digits))
    magnitude = abs(number)

    if magnitude < scientific_lower or magnitude >= scientific_upper:
        mantissa, exponent = f"{number:.{digits - 1}e}".split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        exponent_value = int(exponent)
        return f"{mantissa}e{exponent_value:+d}"

    decimal_places = max(
        0,
        digits - 1 - int(math.floor(math.log10(magnitude)))
    )
    text = f"{number:.{decimal_places}f}"

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text
