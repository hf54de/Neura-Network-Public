# -------------------------------------------------------------------------------------------------
# Datei: connectionpreview.py
# Zweck: Zeigt beim Erstellen einer Verbindung die temporäre Vorschau an.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QGraphicsLineItem


class ConnectionPreview(QGraphicsLineItem):
    """
    Temporäre Verbindungslinie beim Erstellen
    einer neuen Verbindung mit der Maus.
    """

    def __init__(self, start_position):

        super().__init__()

        self.start_position = QPointF(start_position)

        preview_pen = QPen(
            Qt.blue,
            2,
            Qt.PenStyle.DashLine
        )

        self.setPen(preview_pen)
        self.setZValue(-0.5)

        self.update_end_position(start_position)

    def update_end_position(self, end_position):
        """
        Aktualisiert das freie Ende
        der temporären Verbindung.
        """

        self.setLine(
            QLineF(
                self.start_position,
                end_position
            )
        )