# -------------------------------------------------------------------------------------------------
# Datei: colorpalette.py
# Zweck: Speichert benutzerdefinierte Farben projektübergreifend für alle Farbdialoge.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QDialog


SETTINGS_KEY = "program/custom_colors"


def restore_custom_colors():
    settings = QSettings("NeuronNetz", "NeuronNetz")
    stored = settings.value(SETTINGS_KEY, [])
    if isinstance(stored, str):
        stored = [stored]
    for index, value in enumerate(list(stored or [])):
        if index >= QColorDialog.customCount():
            break
        color = QColor(str(value))
        if color.isValid():
            QColorDialog.setCustomColor(index, color)


def save_custom_colors():
    colors = []
    for index in range(QColorDialog.customCount()):
        color = QColor(QColorDialog.customColor(index))
        colors.append(color.name() if color.isValid() else "")
    QSettings("NeuronNetz", "NeuronNetz").setValue(SETTINGS_KEY, colors)


def choose_color(initial, parent=None, title=""):
    restore_custom_colors()
    dialog = QColorDialog(QColor(initial), parent)
    if title:
        dialog.setWindowTitle(title)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    color = dialog.selectedColor()
    save_custom_colors()
    return color if accepted else QColor()
