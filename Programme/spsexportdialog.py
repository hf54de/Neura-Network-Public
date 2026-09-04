# -------------------------------------------------------------------------------------------------
# Datei: spsexportdialog.py
# Zweck: Zeigt generierte Deklarationen und Structured Text schreibgeschützt an.
# Letzte Änderung: 02.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from html import escape
from pathlib import Path
import re

from PySide6.QtCore import QByteArray, QMimeData, QRegularExpression, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from toolbaricons import ToolbarIcons
from plcfileexport import GxWorks2AscExporter, Iec61131XmlExporter, variable_summary
from fbpreview import FunctionBlockPreviewPanel
from graphicalexperimentdialog import show_yellow_information_dialog
from plcexportsettings import PlcExportSettingsPanel


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
    """Schreibgeschützte zweistufige Übergabe an ein SPS-Zielsystem."""

    HEADERS_DE = ("Class", "Label Name", "Data Type", "Constant", "Comment")
    HEADERS_EN = HEADERS_DE

    def __init__(self, export_data, language_code="de", parent=None):
        super().__init__(parent)
        self.german = str(language_code).lower() == "de"
        self.regenerate_callback = export_data.get("regenerate_export")
        self._last_export_options = dict(export_data.get("export_options", {}) or {})
        target_system = str(export_data.get("target_system", "Mitsubishi GX Works2"))
        self.declaration_headers = tuple(export_data.get("headers", self.HEADERS_DE))
        self.initial_declaration_rows = [
            list(row) for row in export_data.get("declarations", [])
        ]
        self.declaration_clipboard_format = str(
            export_data.get("declaration_clipboard_format", "plain_text")
        )
        self.complete_export_format = str(export_data.get("complete_export_format", ""))
        self.complete_export_label = str(export_data.get(
            "complete_export_label_de" if self.german else "complete_export_label_en",
            "",
        ))
        self.setWindowTitle(
            f"{self.tr_text('SPS-Export', 'PLC Export')} – {target_system}"
        )
        self.resize(820, 820)
        self.setMinimumSize(680, 620)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(3)
        main_layout.setContentsMargins(7, 7, 7, 7)

        self.settings_panel = PlcExportSettingsPanel(
            export_data.get("fb_name", "FB_NeuronNetz"),
            export_data.get("model_version", "1.0"),
            self.german,
            self,
            target_system=target_system,
        )
        self.settings_panel.set_export_options(self._last_export_options)
        self.fb_name_edit = self.settings_panel.fb_name_edit
        self.model_version_edit = self.settings_panel.model_version_edit
        main_layout.addWidget(self.settings_panel)

        self.fb_preview_panel = FunctionBlockPreviewPanel(
            self.declaration_headers,
            lambda: self.declaration_rows() if hasattr(self, "declaration_table")
            else self.initial_declaration_rows,
            self.fb_name_edit.text(),
            self.german,
            self,
        )
        self.fb_preview = self.fb_preview_panel.preview
        main_layout.addWidget(self.fb_preview_panel)
        self.fb_name_edit.textChanged.connect(self.fb_preview_panel.set_fb_name)
        self.settings_panel.connectionHelpRequested.connect(
            self.fb_preview_panel.show_connection_help
        )

        self.variable_info_label = QLabel(self)
        main_layout.addWidget(self.variable_info_label)
        summary = dict(export_data.get("operation_summary", {}) or {})
        main_layout.addWidget(QLabel(self.tr_text(
            "Aufwand: {mul} MUL · {add} ADD · {exp} EXP",
            "Effort: {mul} MUL · {add} ADD · {exp} EXP",
        ).format(mul=summary.get("multiplications", 0),
                 add=summary.get("additions", 0), exp=summary.get("exp_calls", 0)), self))

        explanation = QLabel(self.tr_text(
            "Schritt 1: Deklarationen in die erste freie Local-Label-Zeile einfügen. "
            "Schritt 2: Den Structured Text in den leeren FB-Programmkörper einfügen.",
            "Step 1: Paste declarations into the first free Local Label row. "
            "Step 2: Paste Structured Text into the empty FB program body.",
        ), self)
        explanation.setWordWrap(True)
        main_layout.addWidget(explanation)

        safety_row = QHBoxLayout()
        safety_row.setContentsMargins(0, 0, 10, 0)
        safety_label = QLabel(self.tr_text(
            "⚠ Der erzeugte SPS-Code muss vor dem produktiven Einsatz fachgerecht "
            "geprüft und validiert werden.",
            "⚠ The generated PLC code must be professionally reviewed and validated "
            "before production use.",
        ), self)
        safety_label.setWordWrap(True)
        safety_label.setStyleSheet(
            "color: #7a4100; background: #fff4d6; border: 1px solid #e0b85c; "
            "border-radius: 4px; padding: 7px;"
        )
        safety_row.addWidget(safety_label, 1)
        safety_info = QPushButton("i", self)
        self.safety_info_button = safety_info
        safety_info.setFixedSize(23, 23)
        safety_info.setStyleSheet(
            "QPushButton { border: 1px solid #333333; border-radius: 4px; background: #ffffff; }"
            "QPushButton:hover { background: #f0f2f4; }"
        )
        safety_info.setToolTip(self.tr_text(
            "Vollständigen Sicherheits- und Verantwortungshinweis anzeigen",
            "Show the full safety and responsibility notice",
        ))
        safety_info.clicked.connect(self.show_safety_notice)
        safety_row.addWidget(safety_info)
        main_layout.addLayout(safety_row)

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
        splitter.addWidget(self.create_declaration_area(self.initial_declaration_rows))
        splitter.addWidget(self.create_code_area(str(export_data.get("code", ""))))
        splitter.setSizes([330, 430])
        main_layout.addWidget(splitter, 1)
        self.model_version_edit.textChanged.connect(self.model_version_changed)
        self.settings_panel.optionsChanged.connect(self.export_options_changed)
        bottom = QHBoxLayout()
        if self.complete_export_format:
            self.save_complete_button = QPushButton(self.complete_export_label, self)
            self.save_complete_button.setIcon(ToolbarIcons.icon("save"))
            self.save_complete_button.clicked.connect(self.save_complete_file)
            bottom.addWidget(self.save_complete_button)
        bottom.addStretch(1)
        close_button = QPushButton(self.tr_text("Schließen", "Close"), self)
        close_button.clicked.connect(self.accept)
        bottom.addWidget(close_button)
        main_layout.addLayout(bottom)

    def tr_text(self, german, english):
        return german if self.german else english

    def export_options_changed(self, options):
        if not callable(self.regenerate_callback):
            return
        previous = dict(self._last_export_options)
        try:
            data = self.regenerate_callback(
                options, self.model_version_edit.text()
            )
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(self, self.tr_text("Export fehlgeschlagen", "Export failed"), str(error))
            self.settings_panel.set_export_options(previous)
            return
        self.declaration_table.setRowCount(len(data.get("declarations", [])))
        for row_index, values in enumerate(data.get("declarations", [])):
            for column_index in range(self.declaration_table.columnCount()):
                value = values[column_index] if column_index < len(values) else ""
                self.declaration_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
        self.code_editor.setPlainText(str(data.get("code", "")))
        self._last_export_options = dict(options)
        self.update_variable_summary()

    def update_variable_summary(self):
        if not hasattr(self, "declaration_table"):
            return
        summary = variable_summary(self.declaration_headers, self.declaration_rows())
        self.variable_info_label.setText(self.tr_text(
            "Variablen: {total} · Anschlüsse: {io} · Skalierung: {scaling} Werte für "
            "{scaling_inputs} Eingänge und {scaling_outputs} Ausgänge · Gewichte: {weights} · "
            "Bias: {biases} · Neuronen: {neurons} · Hilfswerte: {helpers}",
            "Variables: {total} · Connections: {io} · Scaling: {scaling} values for "
            "{scaling_inputs} inputs and {scaling_outputs} outputs · Weights: {weights} · "
            "Biases: {biases} · Neurons: {neurons} · Helpers: {helpers}",
        ).format(**summary))
        if hasattr(self, "fb_preview_panel"):
            self.fb_preview_panel.refresh_declarations()

    def model_version_changed(self, value):
        if not hasattr(self, "code_editor"):
            return
        code = self.code_editor.toPlainText()
        label = self.tr_text("Modellversion", "Model version")
        updated = re.sub(
            r"(?m)^\s*(?:Modellversion|Model version):.*$",
            f"    {label}: {value.strip() or '-'}",
            code,
            count=1,
        )
        if updated != code:
            cursor = self.code_editor.textCursor()
            position = cursor.position()
            self.code_editor.setPlainText(updated)
            cursor = self.code_editor.textCursor()
            cursor.setPosition(min(position, len(updated)))
            self.code_editor.setTextCursor(cursor)
        name_column = next((i for i, header in enumerate(self.declaration_headers)
                            if str(header).casefold() == "label name"), None)
        constant_column = next((i for i, header in enumerate(self.declaration_headers)
                                if str(header).casefold() == "constant"), None)
        if name_column is not None and constant_column is not None:
            for row in range(self.declaration_table.rowCount()):
                name_item = self.declaration_table.item(row, name_column)
                if name_item is not None and name_item.text() == "Model_Version":
                    item = self.declaration_table.item(row, constant_column)
                    if item is not None:
                        item.setText("'" + value.replace("'", "''")[:48] + "'")
                    break

    def show_safety_notice(self):
        show_yellow_information_dialog(
            self,
            self.tr_text(
                "Sicherheits- und Verantwortungshinweis",
                "Safety and responsibility notice",
            ),
            self.tr_text(
                "Der erzeugte SPS-Code dient als technische Unterstützung und muss vor dem "
                "produktiven Einsatz durch eine qualifizierte Fachkraft geprüft, getestet "
                "und für die konkrete Anlage freigegeben werden. Der Anwender ist für die "
                "korrekte Integration, Validierung, Risikobeurteilung und Einhaltung aller "
                "geltenden Sicherheitsvorschriften verantwortlich. Der Code ist nicht als "
                "Sicherheitsfunktion, Not-Aus-Funktion oder Ersatz für zertifizierte "
                "Schutzmaßnahmen vorgesehen. NeuronNetz übernimmt keine Verantwortung für "
                "Schäden, Betriebsunterbrechungen oder Fehlfunktionen, die aus der ungeprüften "
                "oder unsachgemäßen Verwendung des erzeugten Codes entstehen.",
                "The generated PLC code is provided as technical assistance and must be "
                "reviewed, tested, and approved for the specific installation by a qualified "
                "professional before production use. The user is responsible for correct "
                "integration, validation, risk assessment, and compliance with all applicable "
                "safety requirements. The code is not intended as a safety function, emergency-"
                "stop function, or replacement for certified protective measures. NeuronNetz "
                "assumes no responsibility for damage, operational interruptions, or "
                "malfunctions resulting from unreviewed or improper use of the generated code.",
            ),
            self.tr_text("Schließen", "Close"),
        )

    def create_declaration_area(self, rows):
        group = QGroupBox(self.tr_text("1. Deklaration", "1. Declarations"), self)
        layout = QVBoxLayout(group)
        column_count = len(self.declaration_headers)
        self.declaration_table = QTableWidget(0, column_count, group)
        self.declaration_table.setHorizontalHeaderLabels(self.declaration_headers)
        self.declaration_table.setAlternatingRowColors(True)
        self.declaration_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.declaration_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
        self.update_variable_summary()
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
        self.code_editor.setReadOnly(True)
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

    def declaration_rows(self):
        rows = []
        for row in range(self.declaration_table.rowCount()):
            values = []
            for column in range(self.declaration_table.columnCount()):
                item = self.declaration_table.item(row, column)
                values.append(item.text() if item is not None else "")
            rows.append(values)
        return rows

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

    def save_complete_file(self):
        fb_name = self.fb_name_edit.text().strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}", fb_name):
            QMessageBox.warning(
                self,
                self.tr_text("Ungültiger FB-Name", "Invalid FB name"),
                self.tr_text(
                    "Der FB-Name muss mit einem Buchstaben oder Unterstrich beginnen und darf "
                    "höchstens 32 Zeichen aus Buchstaben, Ziffern und Unterstrichen enthalten.",
                    "The FB name must start with a letter or underscore and contain no more than "
                    "32 letters, digits, and underscores.",
                ),
            )
            return

        exporters = {
            "gxworks2_asc": (
                GxWorks2AscExporter,
                ".asc",
                self.tr_text("GX-Works2-ASC-Datei (*.asc)", "GX Works2 ASC file (*.asc)"),
            ),
            "iec61131_10_xml": (
                Iec61131XmlExporter,
                ".xml",
                self.tr_text("IEC-61131-10-XML-Datei (*.xml)", "IEC 61131-10 XML file (*.xml)"),
            ),
        }
        exporter_data = exporters.get(self.complete_export_format)
        if exporter_data is None:
            return
        exporter, extension, file_filter = exporter_data
        try:
            content = exporter.build(
                fb_name,
                self.declaration_headers,
                self.declaration_rows(),
                self.code_editor.toPlainText(),
            )
        except (TypeError, ValueError) as error:
            QMessageBox.critical(
                self, self.tr_text("Export fehlgeschlagen", "Export failed"), str(error)
            )
            return
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr_text("Vollständige Datei speichern", "Save complete file"),
            f"{fb_name}{extension}",
            file_filter,
        )
        if not file_path:
            return
        if not file_path.lower().endswith(extension):
            file_path += extension
        try:
            Path(file_path).write_text(content, encoding="utf-8", newline="")
        except (OSError, TypeError, ValueError) as error:
            QMessageBox.critical(
                self,
                self.tr_text("Export fehlgeschlagen", "Export failed"),
                str(error),
            )
            return
        QMessageBox.information(
            self,
            self.tr_text("Export abgeschlossen", "Export complete"),
            self.tr_text(
                f"Die vollständige Datei wurde gespeichert:\n{file_path}",
                f"The complete file was saved:\n{file_path}",
            ),
        )
