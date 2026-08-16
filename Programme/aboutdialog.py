# -------------------------------------------------------------------------------------------------
# Datei: aboutdialog.py
# Zweck: Zeigt Programmversion, Systeminformationen und Copyright-Hinweise an.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import platform
import sys
from pathlib import Path

import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QVBoxLayout
)

from language import LanguageManager


# ---------------------------------------------------------------------
# Diese Angaben können später direkt hier angepasst werden.
# ---------------------------------------------------------------------
PROGRAM_NAME = "NeuronNetz"
DEVELOPER_NAME = "Helwig Fülling"
COPYRIGHT_TEXT = "© 2026 Helwig Fülling"
VERSION_FILE_NAME = "VERSION.txt"


def program_version(language_manager):
    """Liest die zentrale, bei der EXE-Erstellung eingebettete Version."""

    directories = []
    temporary_directory = getattr(sys, "_MEIPASS", None)
    if temporary_directory:
        directories.append(Path(temporary_directory))
    directories.extend((Path(__file__).resolve().parent, Path.cwd()))

    for directory in directories:
        candidate = directory / VERSION_FILE_NAME
        try:
            version = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if version:
            return version

    return language_manager.text("about.development_version")


class AboutDialog(QDialog):
    """
    Zeigt Informationen über das Programm an.
    """

    def __init__(
        self,
        language_manager=None,
        parent=None
    ):
        super().__init__(
            parent
        )

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        self.setWindowTitle(
            self.t("about.title", program=PROGRAM_NAME)
        )

        self.setMinimumWidth(
            520
        )

        self.setModal(
            True
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            28,
            24,
            28,
            22
        )

        self.main_layout.setSpacing(
            12
        )

        self.program_name_label = QLabel(
            PROGRAM_NAME
        )

        title_font = QFont(
            self.program_name_label.font()
        )

        title_font.setPointSize(
            22
        )

        title_font.setBold(
            True
        )

        self.program_name_label.setFont(
            title_font
        )

        self.program_name_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.subtitle_label = QLabel(
            self.t("about.subtitle")
        )

        subtitle_font = QFont(
            self.subtitle_label.font()
        )

        subtitle_font.setPointSize(
            11
        )

        self.subtitle_label.setFont(
            subtitle_font
        )

        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.subtitle_label.setWordWrap(
            True
        )

        self.separator_top = QFrame()
        self.separator_top.setFrameShape(
            QFrame.Shape.HLine
        )

        self.separator_top.setFrameShadow(
            QFrame.Shadow.Sunken
        )

        self.description_label = QLabel(
            self.t("about.description")
        )

        self.description_label.setWordWrap(
            True
        )

        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )

        technical_text = self.t(
            "about.technical",
            program_version=program_version(self.language),
            python_version=platform.python_version(),
            pyside_version=PySide6.__version__,
            developer=DEVELOPER_NAME
        )

        self.technical_label = QLabel(
            technical_text
        )

        self.technical_label.setTextFormat(
            Qt.TextFormat.RichText
        )

        self.technical_label.setWordWrap(
            True
        )

        self.separator_bottom = QFrame()
        self.separator_bottom.setFrameShape(
            QFrame.Shape.HLine
        )

        self.separator_bottom.setFrameShadow(
            QFrame.Shadow.Sunken
        )

        self.copyright_label = QLabel(
            COPYRIGHT_TEXT
        )

        self.copyright_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.t("common.close"))

        self.button_box.rejected.connect(
            self.reject
        )

        self.main_layout.addWidget(
            self.program_name_label
        )

        self.main_layout.addWidget(
            self.subtitle_label
        )

        self.main_layout.addWidget(
            self.separator_top
        )

        self.main_layout.addWidget(
            self.description_label
        )

        self.main_layout.addSpacing(
            6
        )

        self.main_layout.addWidget(
            self.technical_label
        )

        self.main_layout.addWidget(
            self.separator_bottom
        )

        self.main_layout.addWidget(
            self.copyright_label
        )

        self.main_layout.addSpacing(
            4
        )

        self.main_layout.addWidget(
            self.button_box
        )
