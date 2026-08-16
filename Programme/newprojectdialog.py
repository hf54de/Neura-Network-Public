# -------------------------------------------------------------------------------------------------
# Datei: newprojectdialog.py
# Zweck: Bietet die verschiedenen Einstiege zum Anlegen eines neuen Projekts an.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from language import LanguageManager


class NewProjectDialog(QDialog):
    """Bietet die vorhandenen Einstiegswege für ein neues Projekt an."""

    CHOICES = (
        ("empty", "new_project.empty", "new_project.empty.description"),
        (
            "automatic",
            "new_project.automatic",
            "new_project.automatic.description",
        ),
        (
            "from_data",
            "new_project.from_data",
            "new_project.from_data.description",
        ),
        (
            "assistant",
            "new_project.assistant",
            "new_project.assistant.description",
        ),
    )

    def __init__(
        self,
        language_manager=None,
        parent=None,
        show_assistant=True,
    ):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.selected_choice = None
        self.choice_buttons = {}

        self.setWindowTitle(self.language.text("new_project.title"))
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        introduction = QLabel(
            self.language.text("new_project.introduction")
        )
        introduction.setWordWrap(True)
        introduction.setStyleSheet(
            "QLabel { background: #eef5f8; border: 1px solid #cbdde6; "
            "border-radius: 5px; padding: 9px; color: #34495e; }"
        )
        layout.addWidget(introduction)

        choices = (
            self.CHOICES
            if show_assistant
            else tuple(item for item in self.CHOICES if item[0] != "assistant")
        )

        for choice, title_key, description_key in choices:
            panel = QFrame()
            panel.setFrameShape(QFrame.Shape.StyledPanel)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(8, 7, 8, 7)
            panel_layout.setSpacing(3)

            button = QPushButton(self.language.text(title_key))
            button.setMinimumHeight(32)
            button.setStyleSheet("QPushButton { text-align: left; padding: 5px 9px; }")
            button.clicked.connect(
                lambda _checked=False, value=choice: self.choose(value)
            )
            panel_layout.addWidget(button)
            self.choice_buttons[choice] = button

            description = QLabel(self.language.text(description_key))
            description.setWordWrap(True)
            description.setStyleSheet("color: #555; padding: 0 9px 2px 9px;")
            description.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            panel_layout.addWidget(description)
            layout.addWidget(panel)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self.language.text("common.cancel")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose(self, choice):
        self.selected_choice = choice
        self.accept()
