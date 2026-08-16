# -------------------------------------------------------------------------------------------------
# Datei: startsplash.py
# Zweck: Zeigt das animierte Intro beim Start von NeuronNetz an.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QSplashScreen


class StartSplash(QSplashScreen):
    """Ruhiges Startbild, das ausschließlich die reale Ladezeit begleitet."""

    WIDTH = 680
    HEIGHT = 390

    def __init__(self, language_manager, program_version):
        self.language = language_manager
        self.program_version = program_version
        self.status_text = ""
        self.animation_step = 0
        pixmap = self.create_pixmap(program_version)
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(360)
        self.animation_timer.timeout.connect(self.advance_animation)
        self.animation_timer.start()

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

        self.draw_network(painter)

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
    def draw_network(painter):
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

    @staticmethod
    def draw_network_animation(painter, animation_step):
        layers = (
            ((205, 186), (205, 246)),
            ((340, 163), (340, 216), (340, 269)),
            ((475, 186), (475, 246)),
        )
        routes = (
            (0, 0, 0),
            (1, 2, 1),
            (0, 1, 1),
            (1, 1, 0),
            (0, 2, 0),
            (1, 0, 1),
        )
        route = routes[(animation_step // 4) % len(routes)]
        phase = animation_step % 4
        input_point = layers[0][route[0]]
        hidden_point = layers[1][route[1]]
        output_point = layers[2][route[2]]
        active_color = QColor("#df8b3a")

        if phase >= 1:
            painter.setPen(QPen(active_color, 3.0))
            painter.drawLine(QPointF(*input_point), QPointF(*hidden_point))
        if phase >= 2:
            painter.setPen(QPen(active_color, 3.0))
            painter.drawLine(QPointF(*hidden_point), QPointF(*output_point))

        active_points = {input_point}
        if phase >= 1:
            active_points.add(hidden_point)
        if phase >= 2:
            active_points.add(output_point)

        for x, y in active_points:
            painter.setBrush(QColor("#fff2cf"))
            painter.setPen(QPen(active_color, 4.0))
            painter.drawEllipse(QPointF(x, y), 11, 11)

    def drawContents(self, painter):
        """Zeichnet nur die veränderlichen Inhalte über das feste Grundbild."""

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_network_animation(painter, self.animation_step)

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

    def advance_animation(self):
        self.animation_step = (self.animation_step + 1) % 24
        self.update(188, 145, 300, 140)
