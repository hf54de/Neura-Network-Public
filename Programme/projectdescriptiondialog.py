# -------------------------------------------------------------------------------------------------
# Datei: projectdescriptiondialog.py
# Zweck: Bearbeitet und formatiert die Beschreibung eines Projekts.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtGui import QAction, QFont, QFontDatabase, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QToolBar,
    QVBoxLayout
)


class ProjectDescriptionDialog(QDialog):
    """Freier Rich-Text-Editor für die projektbezogene Beschreibung."""

    FONT_SIZES = (
        8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36
    )

    def __init__(
        self,
        description_html="",
        example_project=False,
        example_difficulty=None,
        language_manager=None,
        parent=None
    ):
        super().__init__(parent)

        self.language = language_manager
        text = self._text

        self.setWindowTitle(
            text("project_description.title")
        )
        self.resize(780, 560)

        layout = QVBoxLayout(self)

        explanation = QLabel(
            text("project_description.explanation")
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        toolbar = QToolBar(self)
        toolbar.setFloatable(False)
        toolbar.setMovable(False)

        self.action_bold = QAction(
            text("project_description.bold"),
            self
        )
        self.action_bold.setCheckable(True)
        self.action_bold.setShortcut("Ctrl+B")
        self.action_bold.triggered.connect(
            self.set_bold
        )
        toolbar.addAction(self.action_bold)

        self.action_italic = QAction(
            text("project_description.italic"),
            self
        )
        self.action_italic.setCheckable(True)
        self.action_italic.setShortcut("Ctrl+I")
        self.action_italic.triggered.connect(
            self.set_italic
        )
        toolbar.addAction(self.action_italic)

        self.action_underline = QAction(
            text("project_description.underline"),
            self
        )
        self.action_underline.setCheckable(True)
        self.action_underline.setShortcut("Ctrl+U")
        self.action_underline.triggered.connect(
            self.set_underline
        )
        toolbar.addAction(self.action_underline)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(text("project_description.font_family")))
        self.font_family_combo = QComboBox(self)
        self.font_family_combo.setMinimumWidth(150)
        self.font_family_combo.addItems(
            sorted(QFontDatabase.families(), key=str.casefold)
        )
        toolbar.addWidget(self.font_family_combo)

        toolbar.addSeparator()
        toolbar.addWidget(
            QLabel(
                text("project_description.font_size")
            )
        )

        self.font_size_combo = QComboBox(self)
        self.font_size_combo.setEditable(True)
        self.font_size_combo.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
        )

        for font_size in self.FONT_SIZES:
            self.font_size_combo.addItem(
                str(font_size),
                font_size
            )

        self.font_size_combo.setCurrentText("11")
        self.font_size_combo.setFixedWidth(72)
        self.font_size_combo.activated.connect(
            self.apply_selected_font_size
        )
        self.font_size_combo.lineEdit().editingFinished.connect(
            self.apply_selected_font_size
        )
        toolbar.addWidget(self.font_size_combo)
        layout.addWidget(toolbar)

        self.editor = QTextEdit(self)
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText(
            text("project_description.placeholder")
        )

        if description_html:
            self.editor.setHtml(
                str(description_html)
            )

        self.editor.currentCharFormatChanged.connect(
            self.update_format_controls
        )
        self.editor.cursorPositionChanged.connect(
            self.update_controls_from_cursor
        )
        self.font_family_combo.currentTextChanged.connect(
            self.apply_selected_font_family
        )
        layout.addWidget(self.editor, 1)

        example_layout = QHBoxLayout()
        self.example_checkbox = QCheckBox(
            text("project_description.example.show_in_menu"),
            self
        )
        example_layout.addWidget(self.example_checkbox)
        example_layout.addStretch(1)
        self.difficulty_label = QLabel(
            text("project_description.example.difficulty"),
            self
        )
        example_layout.addWidget(self.difficulty_label)
        self.difficulty_combo = QComboBox(self)
        for difficulty in range(1, 5):
            self.difficulty_combo.addItem("★" * difficulty, difficulty)
        normalized_difficulty = (
            int(example_difficulty)
            if isinstance(example_difficulty, int)
            and not isinstance(example_difficulty, bool)
            and 1 <= example_difficulty <= 4
            else 1
        )
        self.difficulty_combo.setCurrentIndex(normalized_difficulty - 1)
        example_layout.addWidget(self.difficulty_combo)
        layout.addLayout(example_layout)

        self.example_checkbox.toggled.connect(
            self.update_example_controls
        )
        self.example_checkbox.setChecked(bool(example_project))
        self.update_example_controls(self.example_checkbox.isChecked())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.update_controls_from_cursor()
        self.editor.setFocus()

    def _text(self, key):
        if self.language is None:
            return key

        return self.language.text(key)

    def merge_character_format(self, character_format):
        cursor = self.editor.textCursor()
        cursor.mergeCharFormat(character_format)
        self.editor.mergeCurrentCharFormat(character_format)

    def set_bold(self, enabled):
        character_format = QTextCharFormat()
        character_format.setFontWeight(
            QFont.Weight.Bold
            if enabled
            else QFont.Weight.Normal
        )
        self.merge_character_format(character_format)

    def set_italic(self, enabled):
        character_format = QTextCharFormat()
        character_format.setFontItalic(bool(enabled))
        self.merge_character_format(character_format)

    def set_underline(self, enabled):
        character_format = QTextCharFormat()
        character_format.setFontUnderline(bool(enabled))
        self.merge_character_format(character_format)

    def apply_selected_font_size(self, *_args):
        try:
            font_size = float(
                self.font_size_combo.currentText().replace(",", ".")
            )
        except ValueError:
            self.update_controls_from_cursor()
            return

        font_size = max(6.0, min(96.0, font_size))
        character_format = QTextCharFormat()
        character_format.setFontPointSize(font_size)
        self.merge_character_format(character_format)

    def apply_selected_font_family(self, font_family):
        if not isinstance(font_family, str) or not font_family.strip():
            return
        character_format = QTextCharFormat()
        character_format.setFontFamilies([font_family.strip()])
        self.merge_character_format(character_format)

    def update_format_controls(self, character_format):
        self.action_bold.blockSignals(True)
        self.action_italic.blockSignals(True)
        self.action_underline.blockSignals(True)

        self.action_bold.setChecked(
            character_format.fontWeight() >= QFont.Weight.Bold
        )
        self.action_italic.setChecked(
            character_format.fontItalic()
        )
        self.action_underline.setChecked(
            character_format.fontUnderline()
        )

        self.action_bold.blockSignals(False)
        self.action_italic.blockSignals(False)
        self.action_underline.blockSignals(False)

        font_size = character_format.fontPointSize()

        font_families = character_format.fontFamilies()
        font_family = font_families[0] if font_families else ""
        if not font_family:
            font_family = self.editor.currentFont().family()
        if font_family:
            self.font_family_combo.blockSignals(True)
            self.font_family_combo.setCurrentText(font_family)
            self.font_family_combo.blockSignals(False)

        if font_size > 0:
            self.font_size_combo.blockSignals(True)
            self.font_size_combo.setCurrentText(
                f"{font_size:g}"
            )
            self.font_size_combo.blockSignals(False)

    def update_controls_from_cursor(self):
        self.update_format_controls(
            self.editor.currentCharFormat()
        )

    def description_html(self):
        if not self.editor.toPlainText().strip():
            return ""

        return self.editor.toHtml()

    def update_example_controls(self, enabled):
        """Aktiviert die Bewertung nur für gekennzeichnete Beispiele."""

        self.difficulty_label.setEnabled(bool(enabled))
        self.difficulty_combo.setEnabled(bool(enabled))

    def is_example_project(self):
        return self.example_checkbox.isChecked()

    def example_difficulty(self):
        if not self.is_example_project():
            return None
        return int(self.difficulty_combo.currentData())
