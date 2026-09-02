# -------------------------------------------------------------------------------------------------
# Datei: spsexportdialog.py
# Zweck: Zeigt Deklarationen und Structured Text für den SPS-Export editierbar an.
# Letzte Änderung: 02.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from html import escape

from PySide6.QtCore import QByteArray, QMimeData, QRegularExpression, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from toolbaricons import ToolbarIcons


class StructuredTextHighlighter(QSyntaxHighlighter):
    """Kompakte Mitsubishi-nahe Syntaxfärbung für Structured Text."""

    def __init__(self, document):
        super().__init__(document)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0057a8"))
        keyword_format.setFontWeight(700)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#9b2c7c"))
        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#7b3fb3"))
        boolean_format.setFontWeight(700)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#16833b"))
        self.comment_format = comment_format
        keywords = (
            "IF", "THEN", "ELSE", "ELSIF", "END_IF", "FOR", "TO", "BY", "DO",
            "END_FOR", "WHILE", "END_WHILE", "CASE", "OF", "END_CASE", "RETURN",
            "AND", "OR", "XOR", "NOT", "MOD",
        )
        self.rules = [
            (
                QRegularExpression(r"\b(?:" + "|".join(keywords) + r")\b",
                                   QRegularExpression.PatternOption.CaseInsensitiveOption),
                keyword_format,
            ),
            (QRegularExpression(r"\b(?:TRUE|FALSE)\b",
                                QRegularExpression.PatternOption.CaseInsensitiveOption), boolean_format),
            (QRegularExpression(r"(?<![A-Za-z_])[-+]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:E[-+]?\d+)?"), number_format),
        ]
        self.comment_start = QRegularExpression(r"\(\*")
        self.comment_end = QRegularExpression(r"\*\)")

    def highlightBlock(self, text):
        for expression, text_format in self.rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)

        self.setCurrentBlockState(0)
        start = 0 if self.previousBlockState() == 1 else self.comment_start.match(text).capturedStart()
        while start >= 0:
            end_match = self.comment_end.match(text, start + 2)
            if end_match.hasMatch():
                length = end_match.capturedEnd() - start
            else:
                self.setCurrentBlockState(1)
                length = len(text) - start
            self.setFormat(start, length, self.comment_format)
            if not end_match.hasMatch():
                break
            start = self.comment_start.match(text, start + length).capturedStart()


class SpsExportDialog(QDialog):
    """Editierbare zweistufige Übergabe an ein SPS-Zielsystem."""

    HEADERS_DE = ("Class", "Label Name", "Data Type", "Constant", "Comment")
    HEADERS_EN = HEADERS_DE

    def __init__(self, export_data, language_code="de", parent=None):
        super().__init__(parent)
        self.german = str(language_code).lower() == "de"
        target_system = str(export_data.get("target_system", "Mitsubishi GX Works2"))
        self.declaration_headers = tuple(export_data.get("headers", self.HEADERS_DE))
        self.declaration_clipboard_format = str(
            export_data.get("declaration_clipboard_format", "plain_text")
        )
        self.setWindowTitle(
            f"{self.tr_text('SPS-Export', 'PLC Export')} – {target_system}"
        )
        self.resize(1120, 820)
        self.setMinimumSize(820, 620)

        main_layout = QVBoxLayout(self)
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(self.tr_text("Zielsystem:", "Target system:"), self))
        target = QLineEdit(target_system, self)
        target.setReadOnly(True)
        target.setMaximumWidth(220)
        info_layout.addWidget(target)
        info_layout.addSpacing(16)
        info_layout.addWidget(QLabel(self.tr_text("FB-Name:", "FB name:"), self))
        self.fb_name_edit = QLineEdit(str(export_data.get("fb_name", "FB_NeuronNetz")), self)
        self.fb_name_edit.setMaxLength(32)
        info_layout.addWidget(self.fb_name_edit, 1)
        main_layout.addLayout(info_layout)

        explanation = QLabel(self.tr_text(
            "Schritt 1: Deklarationen in die erste freie Local-Label-Zeile einfügen. "
            "Schritt 2: Den Structured Text in den leeren FB-Programmkörper einfügen.",
            "Step 1: Paste declarations into the first free Local Label row. "
            "Step 2: Paste Structured Text into the empty FB program body.",
        ), self)
        explanation.setWordWrap(True)
        main_layout.addWidget(explanation)

        declaration_hint = str(export_data.get(
            "declaration_hint_de" if self.german else "declaration_hint_en",
            "",
        )).strip()
        if declaration_hint:
            hint_label = QLabel(declaration_hint, self)
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet(
                "color: #8a4f00; background: #fff4d6; "
                "border: 1px solid #e4bd63; border-radius: 4px; padding: 7px;"
            )
            main_layout.addWidget(hint_label)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.create_declaration_area(export_data.get("declarations", [])))
        splitter.addWidget(self.create_code_area(str(export_data.get("code", ""))))
        splitter.setSizes([330, 430])
        main_layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close_button = QPushButton(self.tr_text("Schließen", "Close"), self)
        close_button.clicked.connect(self.accept)
        bottom.addWidget(close_button)
        main_layout.addLayout(bottom)

    def tr_text(self, german, english):
        return german if self.german else english

    def create_declaration_area(self, rows):
        group = QGroupBox(self.tr_text("1. Deklaration", "1. Declarations"), self)
        layout = QVBoxLayout(group)
        column_count = len(self.declaration_headers)
        self.declaration_table = QTableWidget(0, column_count, group)
        self.declaration_table.setHorizontalHeaderLabels(self.declaration_headers)
        self.declaration_table.setAlternatingRowColors(True)
        self.declaration_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.declaration_table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index in range(column_count):
                value = values[column_index] if column_index < len(values) else ""
                self.declaration_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
        header = self.declaration_table.horizontalHeader()
        for column in range(max(0, column_count - 1)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(column_count - 1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.declaration_table, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.copy_declaration_button = QPushButton(
            self.tr_text("Deklaration kopieren", "Copy declarations"), group
        )
        self.copy_declaration_button.setIcon(ToolbarIcons.icon("copy"))
        self.copy_declaration_button.clicked.connect(self.copy_declarations)
        button_row.addWidget(self.copy_declaration_button)
        layout.addLayout(button_row)
        return group

    def create_code_area(self, code):
        group = QGroupBox(self.tr_text("2. Structured Text", "2. Structured Text"), self)
        layout = QVBoxLayout(group)
        self.code_editor = QPlainTextEdit(group)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(10)
        self.code_editor.setFont(fixed_font)
        self.code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_editor.setTabStopDistance(self.code_editor.fontMetrics().horizontalAdvance(" ") * 4)
        self.code_editor.setPlainText(code)
        self.highlighter = StructuredTextHighlighter(self.code_editor.document())
        layout.addWidget(self.code_editor, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.copy_code_button = QPushButton(self.tr_text("ST-Code kopieren", "Copy ST code"), group)
        self.copy_code_button.setIcon(ToolbarIcons.icon("copy"))
        self.copy_code_button.clicked.connect(self.copy_code)
        button_row.addWidget(self.copy_code_button)
        layout.addLayout(button_row)
        return group

    def declarations_text(self):
        lines = []
        for row in range(self.declaration_table.rowCount()):
            values = []
            for column in range(self.declaration_table.columnCount()):
                item = self.declaration_table.item(row, column)
                values.append(item.text() if item is not None else "")
            lines.append("\t".join(values))
        return "\r\n".join(lines)

    def declarations_html(self):
        """Erzeugt eine Excel-ähnliche Tabelle mit ausdrücklich leeren Zellen."""

        rows = []
        for row in range(self.declaration_table.rowCount()):
            cells = []
            for column in range(self.declaration_table.columnCount()):
                item = self.declaration_table.item(row, column)
                value = item.text() if item is not None else ""
                cells.append(f"<td>{escape(value)}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return (
            "<html><head><meta charset=\"utf-8\"></head><body>"
            "<table>" + "".join(rows) + "</table></body></html>"
        )

    def show_copied_state(self, button, normal_text):
        button.setText(self.tr_text("Kopiert ✓", "Copied ✓"))
        QTimer.singleShot(1400, lambda: button.setText(normal_text))

    def copy_declarations(self):
        declaration_text = self.declarations_text()
        if self.declaration_clipboard_format == "html_table":
            mime_data = QMimeData()
            mime_data.setText(declaration_text)
            mime_data.setHtml(self.declarations_html())
            mime_data.setData(
                "text/tab-separated-values",
                QByteArray(declaration_text.encode("utf-8")),
            )
            QApplication.clipboard().setMimeData(mime_data)
        else:
            QApplication.clipboard().setText(declaration_text)
        normal = self.tr_text("Deklaration kopieren", "Copy declarations")
        self.show_copied_state(self.copy_declaration_button, normal)

    def copy_code(self):
        QApplication.clipboard().setText(self.code_editor.toPlainText())
        normal = self.tr_text("ST-Code kopieren", "Copy ST code")
        self.show_copied_state(self.copy_code_button, normal)
