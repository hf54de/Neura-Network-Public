# -------------------------------------------------------------------------------------------------
# Datei: projectdescriptiondialog.py
# Zweck: Bearbeitet und formatiert die Beschreibung eines Projekts.
# Letzte Änderung: 01.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import html
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction,
    QFont,
    QFontDatabase,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
)
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


class ProjectDescriptionTextEdit(QTextEdit):
    """Rich-Text-Editor mit einem eindeutig links beginnenden neuen Absatz."""

    TAB_SPACE_WIDTH = 4

    _SUPERSCRIPT_CHARACTERS = str.maketrans(
        "0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ"
    )
    _SUBSCRIPT_CHARACTERS = str.maketrans(
        "0123456789+-=()aeoxhklmnpst", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ"
    )
    _LATEX_SYMBOLS = {
        "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
        "Delta": "Δ", "lambda": "λ", "mu": "μ", "pi": "π",
        "sigma": "σ", "Sigma": "Σ", "theta": "θ", "approx": "≈",
        "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "neq": "≠",
        "pm": "±", "infty": "∞",
    }

    def setHtml(self, text):
        super().setHtml(self._normalize_editable_html(str(text)))

    def insertFromMimeData(self, source):
        cursor = self.textCursor()
        insertion_start = min(cursor.position(), cursor.anchor())
        cursor.beginEditBlock()
        if source.hasHtml() and any(
            marker in source.html().lower()
            for marker in ("<table", "<ol", "<ul")
        ):
            cursor.insertHtml(self._normalize_editable_html(source.html()))
            self.setTextCursor(cursor)
        else:
            super().insertFromMimeData(source)
        insertion_end = self.textCursor().position()
        self._convert_latex_in_range(insertion_start, insertion_end)
        cursor.endEditBlock()

    def _convert_latex_in_range(self, start, end):
        """Wandelt eingefügte, begrenzte LaTeX-Formeln in Unicode-Text um."""

        if end <= start:
            return
        selected_cursor = QTextCursor(self.document())
        selected_cursor.setPosition(start)
        selected_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        inserted_text = selected_cursor.selectedText()
        formula_pattern = re.compile(
            r"\\\((.+?)\\\)|\\\[(.+?)\\\]", re.DOTALL
        )
        matches = list(formula_pattern.finditer(inserted_text))
        if not matches:
            return

        final_position = self.textCursor().position()
        for match in reversed(matches):
            formula = match.group(1) if match.group(1) is not None else match.group(2)
            replacement = self._latex_expression_to_unicode(formula)
            formula_cursor = QTextCursor(self.document())
            formula_cursor.setPosition(start + match.start())
            formula_cursor.setPosition(
                start + match.end(), QTextCursor.MoveMode.KeepAnchor
            )
            formula_cursor.insertText(replacement)
            final_position += len(replacement) - (match.end() - match.start())

        final_cursor = self.textCursor()
        final_cursor.setPosition(max(start, final_position))
        self.setTextCursor(final_cursor)

    @classmethod
    def _latex_expression_to_unicode(cls, expression):
        """Übersetzt häufiges Formel-LaTeX in direkt bearbeitbaren Text."""

        def braced_content(value, opening_index):
            if opening_index >= len(value) or value[opening_index] != "{":
                return None, opening_index
            depth = 0
            for index in range(opening_index, len(value)):
                if value[index] == "{":
                    depth += 1
                elif value[index] == "}":
                    depth -= 1
                    if depth == 0:
                        return value[opening_index + 1:index], index + 1
            return None, opening_index

        def translated(value):
            output = []
            index = 0
            while index < len(value):
                if value.startswith("\\frac", index):
                    command_end = index + len("\\frac")
                    while command_end < len(value) and value[command_end].isspace():
                        command_end += 1
                    numerator, after_numerator = braced_content(value, command_end)
                    denominator, after_denominator = braced_content(value, after_numerator)
                    if numerator is not None and denominator is not None:
                        output.append(
                            f"({translated(numerator).strip()}) / "
                            f"({translated(denominator).strip()})"
                        )
                        index = after_denominator
                        continue
                if value.startswith("\\sqrt", index):
                    command_end = index + len("\\sqrt")
                    while command_end < len(value) and value[command_end].isspace():
                        command_end += 1
                    radicand, after_radicand = braced_content(value, command_end)
                    if radicand is not None:
                        converted = translated(radicand).strip()
                        output.append(
                            f"√{converted}"
                            if re.fullmatch(r"[\w.,]+", converted, re.UNICODE)
                            else f"√({converted})"
                        )
                        index = after_radicand
                        continue
                if value.startswith("\\cdot", index):
                    output.append(" × ")
                    index += len("\\cdot")
                    continue
                if value.startswith("\\times", index):
                    output.append(" × ")
                    index += len("\\times")
                    continue
                if value[index] in "^_":
                    is_superscript = value[index] == "^"
                    group, after_group = braced_content(value, index + 1)
                    if group is not None:
                        table = (
                            cls._SUPERSCRIPT_CHARACTERS
                            if is_superscript
                            else cls._SUBSCRIPT_CHARACTERS
                        )
                        converted = translated(group).strip()
                        styled = converted.translate(table)
                        output.append(
                            styled
                            if all(ord(character) in table for character in converted)
                            else f"{'^' if is_superscript else '_'}({converted})"
                        )
                        index = after_group
                        continue
                if value[index] == "\\":
                    command_match = re.match(r"\\([A-Za-z]+)", value[index:])
                    if command_match:
                        command = command_match.group(1)
                        output.append(
                            "" if command in ("left", "right")
                            else cls._LATEX_SYMBOLS.get(command, command)
                        )
                        index += len(command_match.group(0))
                        continue
                if value[index] == "{":
                    group, after_group = braced_content(value, index)
                    if group is not None:
                        output.append(translated(group))
                        index = after_group
                        continue
                output.append(value[index])
                index += 1
            return "".join(output)

        result = translated(str(expression).strip())
        result = re.sub(r"\s*([=+])\s*", r" \1 ", result)
        result = re.sub(r"\s*×\s*", " × ", result)
        result = re.sub(r"[ \t]+", " ", result)
        return result.strip()

    @classmethod
    def _normalize_editable_html(cls, source_html):
        normalized = cls._tables_to_tabbed_text(source_html)
        return cls._lists_to_plain_text(normalized)

    @staticmethod
    def _lists_to_plain_text(source_html):
        """Ersetzt HTML-Listen durch normale, nicht eingerückte Textzeilen."""

        list_pattern = re.compile(
            r"<(ol|ul)\b([^>]*)>(.*?)</\1>",
            re.IGNORECASE | re.DOTALL,
        )
        item_pattern = re.compile(
            r"<li\b[^>]*>(.*?)</li>",
            re.IGNORECASE | re.DOTALL,
        )

        def replace_list(match):
            list_kind = match.group(1).lower()
            start_match = re.search(
                r'\bstart\s*=\s*["\']?(\d+)',
                match.group(2),
                re.IGNORECASE,
            )
            start_number = int(start_match.group(1)) if start_match else 1
            output_items = []
            for item_index, item_match in enumerate(
                item_pattern.finditer(match.group(3))
            ):
                document = QTextDocument()
                document.setHtml(item_match.group(1))
                item_text = " ".join(
                    part.strip()
                    for part in document.toPlainText().splitlines()
                    if part.strip()
                )
                prefix = (
                    f"{start_number + item_index}. "
                    if list_kind == "ol"
                    else "• "
                )
                output_items.append(
                    f'<p style="margin:0; -qt-block-indent:0; '
                    f'text-indent:0px;">'
                    f'{html.escape(prefix + item_text)}</p>'
                )
            return "".join(output_items)

        previous_html = None
        normalized_html = source_html
        while previous_html != normalized_html:
            previous_html = normalized_html
            normalized_html = list_pattern.sub(replace_list, normalized_html)
        return normalized_html

    @staticmethod
    def _tables_to_tabbed_text(source_html):
        """Ersetzt HTML-Tabellen durch frei editierbare Tabulatorzeilen."""

        table_pattern = re.compile(
            r"<table\b[^>]*>.*?</table>",
            re.IGNORECASE | re.DOTALL,
        )
        row_pattern = re.compile(
            r"<tr\b[^>]*>(.*?)</tr>",
            re.IGNORECASE | re.DOTALL,
        )
        cell_pattern = re.compile(
            r"<(td|th)\b[^>]*>(.*?)</\1>",
            re.IGNORECASE | re.DOTALL,
        )

        def plain_lines(cell_html):
            document = QTextDocument()
            document.setHtml(cell_html)
            return [
                line.strip()
                for line in document.toPlainText().splitlines()
                if line.strip()
            ]

        def replace_table(match):
            table_html = match.group(0)
            output_rows = []
            trailing_paragraphs = []
            for row_index, row_match in enumerate(
                row_pattern.finditer(table_html)
            ):
                cells = []
                for cell_match in cell_pattern.finditer(row_match.group(1)):
                    lines = plain_lines(cell_match.group(2))
                    cells.append(lines[0] if lines else "")
                    trailing_paragraphs.extend(lines[1:])
                if not cells:
                    continue
                row_text = "&#9;".join(html.escape(value) for value in cells)
                if row_index == 0:
                    row_text = f"<b>{row_text}</b>"
                output_rows.append(
                    f'<p style="margin:0; -qt-block-indent:0; '
                    f'text-indent:0px;">{row_text}</p>'
                )
            output_rows.extend(
                f'<p style="margin:0; -qt-block-indent:0; '
                f'text-indent:0px;">{html.escape(value)}</p>'
                for value in trailing_paragraphs
            )
            return "".join(output_rows)

        return table_pattern.sub(replace_table, source_html)

    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() in (
                Qt.KeyboardModifier.NoModifier,
                Qt.KeyboardModifier.KeypadModifier,
            )
        ):
            cursor = self.textCursor()
            if self._leave_table_after_last_cell(cursor):
                event.accept()
                return
            cursor.insertBlock(QTextBlockFormat(), cursor.charFormat())
            self.setTextCursor(cursor)
            event.accept()
            return
        if (
            event.key() == Qt.Key.Key_Backspace
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            if (
                self._move_last_table_cell_paragraph_outside()
                or self.move_current_line_one_tab_left()
            ):
                event.accept()
                return
        super().keyPressEvent(event)

    def _leave_table_after_last_cell(self, cursor):
        """Setzt den Cursor nach der letzten Tabellenzelle an den linken Rand."""

        table = cursor.currentTable()
        if table is None or not cursor.atBlockEnd():
            return False

        cell = table.cellAt(cursor)
        if (
            not cell.isValid()
            or cell.row() != table.rows() - 1
            or cell.column() != table.columns() - 1
        ):
            return False

        character_format = cursor.charFormat()
        outside_cursor = QTextCursor(cursor)
        while outside_cursor.currentTable() is table:
            if not outside_cursor.movePosition(
                QTextCursor.MoveOperation.NextBlock
            ):
                return False

        outside_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        if outside_cursor.block().text():
            outside_cursor.insertBlock(QTextBlockFormat(), character_format)
            outside_cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
            outside_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        else:
            outside_cursor.setBlockFormat(QTextBlockFormat())
            outside_cursor.setCharFormat(character_format)

        self.setTextCursor(outside_cursor)
        return True

    def _move_last_table_cell_paragraph_outside(self):
        """Verschiebt einen Absatz aus der letzten Tabellenzelle nach außen."""

        cursor = self.textCursor()
        if cursor.hasSelection() or cursor.positionInBlock() != 0:
            return False

        table = cursor.currentTable()
        if table is None:
            return False
        cell = table.cellAt(cursor)
        if (
            not cell.isValid()
            or cell.row() != table.rows() - 1
            or cell.column() != table.columns() - 1
            or not cursor.block().text()
        ):
            return False

        paragraph_cursor = QTextCursor(cursor)
        paragraph_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        paragraph_cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        paragraph = QTextDocumentFragment(paragraph_cursor)
        paragraph_cursor.removeSelectedText()

        outside_cursor = QTextCursor(cursor)
        while outside_cursor.currentTable() is table:
            if not outside_cursor.movePosition(
                QTextCursor.MoveOperation.NextBlock
            ):
                return False

        outside_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        if outside_cursor.block().text():
            outside_cursor.insertBlock(QTextBlockFormat())
            outside_cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
        outside_cursor.setBlockFormat(QTextBlockFormat())
        outside_cursor.insertFragment(paragraph)
        outside_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        self.setTextCursor(outside_cursor)
        return True

    def move_current_line_one_tab_left(self):
        """Entfernt vor dem ersten Text genau eine vorhandene Einrückungsstufe."""

        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        block = cursor.block()
        block_text = block.text()
        leading_length = len(block_text) - len(block_text.lstrip(" \t"))
        if cursor.positionInBlock() != leading_length:
            return False

        leading_text = block_text[:leading_length]
        if leading_text:
            if leading_text.endswith("\t"):
                remove_count = 1
            else:
                spaces_after_tab = len(leading_text.rsplit("\t", 1)[-1])
                remove_count = spaces_after_tab % self.TAB_SPACE_WIDTH
                if remove_count == 0:
                    remove_count = min(
                        self.TAB_SPACE_WIDTH,
                        spaces_after_tab,
                    )
            if remove_count:
                cursor.movePosition(
                    QTextCursor.MoveOperation.PreviousCharacter,
                    QTextCursor.MoveMode.KeepAnchor,
                    remove_count,
                )
                cursor.removeSelectedText()
                self.setTextCursor(cursor)
                return True

        block_format = cursor.blockFormat()
        if block_format.indent() > 0:
            block_format.setIndent(block_format.indent() - 1)
            cursor.setBlockFormat(block_format)
            self.setTextCursor(cursor)
            return True

        left_margin = block_format.leftMargin()
        text_indent = block_format.textIndent()
        if left_margin <= 0.0 and text_indent <= 0.0:
            return False
        tab_distance = max(1.0, float(self.tabStopDistance()))
        block_format.setLeftMargin(max(0.0, left_margin - tab_distance))
        block_format.setTextIndent(max(0.0, text_indent - tab_distance))
        cursor.setBlockFormat(block_format)
        self.setTextCursor(cursor)
        return True


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

        self.editor = ProjectDescriptionTextEdit(self)
        self.editor.setAcceptRichText(True)
        self.editor.setTabStopDistance(30.0)
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
        selection_start = min(cursor.position(), cursor.anchor())
        selection_length = abs(cursor.position() - cursor.anchor())
        cursor.mergeCharFormat(character_format)
        self.editor.setTextCursor(cursor)
        self.editor.mergeCurrentCharFormat(character_format)
        document = self.editor.document()
        if selection_length:
            document.markContentsDirty(
                selection_start,
                selection_length,
            )
        document.markContentsDirty(0, document.characterCount())
        self.editor.updateGeometry()
        self.editor.viewport().repaint()

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

        selected_styles = self.selected_character_styles()
        if selected_styles:
            self.action_bold.setChecked(selected_styles["bold"] == {True})
            self.action_italic.setChecked(
                selected_styles["italic"] == {True}
            )
            self.action_underline.setChecked(
                selected_styles["underline"] == {True}
            )
        else:
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

        selected_font_sizes = self.selected_font_sizes()
        mixed_font_sizes = len(selected_font_sizes) > 1
        font_size = character_format.fontPointSize()

        font_families = character_format.fontFamilies()
        font_family = font_families[0] if font_families else ""
        if not font_family:
            font_family = self.editor.currentFont().family()
        if font_family:
            self.font_family_combo.blockSignals(True)
            self.font_family_combo.setCurrentText(font_family)
            self.font_family_combo.blockSignals(False)

        self.font_size_combo.blockSignals(True)
        if mixed_font_sizes:
            self.font_size_combo.setCurrentText("")
        elif selected_font_sizes:
            self.font_size_combo.setCurrentText(
                f"{next(iter(selected_font_sizes)):g}"
            )
        elif font_size > 0:
            self.font_size_combo.setCurrentText(
                f"{font_size:g}"
            )
        self.font_size_combo.blockSignals(False)

    def selected_character_styles(self):
        """Ermittelt Fett, Kursiv und Unterstrichen über die ganze Auswahl."""

        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return {}

        selection_start = min(cursor.position(), cursor.anchor())
        selection_end = max(cursor.position(), cursor.anchor())
        styles = {
            "bold": set(),
            "italic": set(),
            "underline": set(),
        }
        block = self.editor.document().findBlock(selection_start)
        while block.isValid() and block.position() < selection_end:
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                fragment_start = fragment.position()
                fragment_end = fragment_start + fragment.length()
                if (
                    fragment.isValid()
                    and fragment_end > selection_start
                    and fragment_start < selection_end
                ):
                    font = fragment.charFormat().font()
                    styles["bold"].add(font.bold())
                    styles["italic"].add(font.italic())
                    styles["underline"].add(font.underline())
                iterator += 1
            block = block.next()
        return styles

    def selected_font_sizes(self):
        """Liefert die effektiven Schriftgrößen der aktuellen Auswahl."""

        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return set()

        selection_start = min(cursor.position(), cursor.anchor())
        selection_end = max(cursor.position(), cursor.anchor())
        default_size = self.editor.document().defaultFont().pointSizeF()
        font_sizes = set()
        block = self.editor.document().findBlock(selection_start)
        while block.isValid() and block.position() < selection_end:
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                fragment_start = fragment.position()
                fragment_end = fragment_start + fragment.length()
                if (
                    fragment.isValid()
                    and fragment_end > selection_start
                    and fragment_start < selection_end
                ):
                    character_format = fragment.charFormat()
                    font_size = character_format.font().pointSizeF()
                    if font_size <= 0:
                        font_size = character_format.fontPointSize()
                    if font_size <= 0:
                        font_size = default_size
                    if font_size > 0:
                        font_sizes.add(round(float(font_size), 4))
                iterator += 1
            block = block.next()
        return font_sizes

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
