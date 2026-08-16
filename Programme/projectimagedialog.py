# -------------------------------------------------------------------------------------------------
# Datei: projectimagedialog.py
# Zweck: Zeigt und verwaltet das einem Projekt zugeordnete Bild.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


class ProjectImageDialog(QDialog):
    """Zeigt das zum Projektordner gehörende Projektbild an."""

    def __init__(self, image_path, language_manager, parent=None):
        super().__init__(parent)

        self.language = language_manager
        self.original_pixmap = QPixmap(str(image_path))

        self.setWindowTitle(
            self.language.text("project_image.title")
        )
        self.resize(900, 650)
        self.setMinimumSize(420, 300)

        layout = QVBoxLayout(self)

        self.image_label = QLabel()
        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.image_label.setMinimumSize(1, 1)
        layout.addWidget(self.image_label, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(self.reject)
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.language.text("common.close"))
        layout.addWidget(buttons)

        self.update_scaled_image()

    @property
    def image_is_valid(self):
        return not self.original_pixmap.isNull()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "image_label"):
            self.update_scaled_image()

    def update_scaled_image(self):
        if self.original_pixmap.isNull():
            self.image_label.clear()
            return

        available_size = self.image_label.size()
        if available_size.width() < 2 or available_size.height() < 2:
            return

        self.image_label.setPixmap(
            self.original_pixmap.scaled(
                available_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
