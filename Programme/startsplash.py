# -------------------------------------------------------------------------------------------------
# Datei: startsplash.py
# Zweck: Zeigt das Startbild während des Ladens von NeuronNetz an.
# Letzte Änderung: 04.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QSplashScreen


SPLASH_IMAGE_NAME = "startup_neural_automation.png"


def splash_image_path():
    """Ermittelt das Startbild im Quellbaum und in der PyInstaller-EXE."""

    base_directory = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_directory / "assets" / SPLASH_IMAGE_NAME


class StartSplash(QSplashScreen):
    """Ruhiges Startbild, das ausschließlich die reale Ladezeit begleitet."""

    WIDTH = 680
    HEIGHT = 390

    def __init__(self, language_manager, program_version):
        self.language = language_manager
        self.program_version = program_version
        self.status_text = ""
        pixmap = self.create_pixmap(program_version)
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)

    def create_pixmap(self, program_version):
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setBrush(
            QApplication.palette().color(QPalette.ColorRole.Window)
        )
        painter.setPen(QPen(QColor("#9eb5c2"), 1.2))
        painter.drawRoundedRect(
            QRectF(1, 1, self.WIDTH - 2, self.HEIGHT - 2),
            12,
            12,
        )

        title_font = QFont(painter.font())
        title_font.setPointSize(28)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#203746"))
        painter.drawText(
            QRectF(30, 34, self.WIDTH - 60, 52),
            Qt.AlignmentFlag.AlignCenter,
            "NeuronNetz",
        )

        subtitle_font = QFont(painter.font())
        subtitle_font.setPointSize(12)
        subtitle_font.setBold(False)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#4c6574"))
        painter.drawText(
            QRectF(30, 88, self.WIDTH - 60, 48),
            Qt.AlignmentFlag.AlignCenter,
            self.language.text("startup.slogan"),
        )

        self.draw_startup_illustration(painter)

        copyright_font = QFont(painter.font())
        copyright_font.setPointSize(10)
        copyright_font.setBold(False)
        painter.setFont(copyright_font)
        painter.setPen(QColor("#526b79"))
        painter.drawText(
            QRectF(30, 298, self.WIDTH - 60, 24),
            Qt.AlignmentFlag.AlignCenter,
            "(c) 2026 Helwig Fülling",
        )

        version_font = QFont(painter.font())
        version_font.setPointSize(9)
        painter.setFont(version_font)
        painter.setPen(QColor("#718795"))
        painter.drawText(
            QRectF(14, self.HEIGHT - 29, self.WIDTH - 28, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self.language.text(
                "startup.version",
                version=program_version,
            ),
        )

        painter.end()
        return pixmap

    @staticmethod
    def draw_startup_illustration(painter):
        """Zeichnet das eingebettete Motiv; bei fehlender Ressource den Ersatz."""

        illustration = QPixmap(str(splash_image_path()))
        if illustration.isNull():
            StartSplash.draw_network_fallback(painter)
            return

        target = QRectF(82, 137, 516, 145)
        scaled = illustration.scaled(
            int(target.width()),
            int(target.height()),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        source_x = max(0, (scaled.width() - int(target.width())) // 2)
        source_y = max(0, (scaled.height() - int(target.height())) // 2)
        painter.drawPixmap(
            target,
            scaled,
            QRectF(source_x, source_y, target.width(), target.height()),
        )

    @staticmethod
    def draw_network_fallback(painter):
        layers = (
            ((205, 186), (205, 246)),
            ((340, 163), (340, 216), (340, 269)),
            ((475, 186), (475, 246)),
        )
        colors = (QColor("#4d91bb"), QColor("#c39a47"), QColor("#57936a"))

        painter.setPen(QPen(QColor("#a8bcc7"), 2.0))
        for left_layer, right_layer in zip(layers, layers[1:]):
            for left in left_layer:
                for right in right_layer:
                    painter.drawLine(QPointF(*left), QPointF(*right))

        for layer, color in zip(layers, colors):
            for x, y in layer:
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(color, 4.0))
                painter.drawEllipse(QPointF(x, y), 11, 11)

    def drawContents(self, painter):
        """Zeichnet nur die veränderlichen Inhalte über das feste Grundbild."""

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        status_font = QFont(painter.font())
        status_font.setPointSize(9)
        painter.setFont(status_font)
        painter.setPen(QColor("#405a69"))
        painter.drawText(
            QRectF(14, self.HEIGHT - 29, self.WIDTH - 28, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.status_text,
        )

    def show_status(self, message_key):
        self.status_text = self.language.text(message_key)
        self.update(10, self.HEIGHT - 34, self.WIDTH - 20, 26)
