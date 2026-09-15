# -------------------------------------------------------------------------------------------------
# Datei: xmlexportdialog.py
# Zweck: Zeigt den vollständigen IEC-61131-10-XML-Export schreibgeschützt an.
# Letzte Änderung: 03.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from pathlib import Path
import re

from PySide6.QtCore import QRegularExpression, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from plcfileexport import GxWorks3XmlExporter, Iec61131XmlExporter, variable_summary
from toolbaricons import ToolbarIcons
from fbpreview import FunctionBlockPreviewPanel
from graphicalexperimentdialog import show_yellow_information_dialog
from plcexportsettings import PlcExportSettingsPanel
from plcquality import PruningQualityPanel, ExportCopyGuard


class XmlHighlighter(QSyntaxHighlighter):
    """Kleine XML-Syntaxfärbung für den vollständigen Exporttext."""

    def __init__(self, document):
        super().__init__(document)
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#0057a8"))
        tag_format.setFontWeight(700)
        attribute_format = QTextCharFormat()
        attribute_format.setForeground(QColor("#9b2c7c"))
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#16833b"))
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#777777"))
        self.rules = (
            (QRegularExpression(r"</?[A-Za-z_:][A-Za-z0-9_.:-]*"), tag_format),
            (QRegularExpression(r"\b[A-Za-z_:][A-Za-z0-9_.:-]*(?=\s*=)"), attribute_format),
            (QRegularExpression(r'"[^"\n]*"'), value_format),
            (QRegularExpression(r"<!--.*?-->"), comment_format),
        )

    def highlightBlock(self, text):
        for expression, text_format in self.rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)


class XmlExportDialog(QDialog):
    """Schreibgeschützte Ansicht einer vollständigen IEC-61131-10-XML-Datei."""

    def __init__(self, export_data, language_code="de", parent=None):
        super().__init__(parent)
        self.german = str(language_code).lower() == "de"
        self.xml_profile = str(export_data.get("xml_profile", "iec"))
        self.gxworks3_profile = self.xml_profile == "gxworks3"
        self.regenerate_callback = export_data.get("regenerate_export")
        self._last_export_options = dict(export_data.get("export_options", {}) or {})
        self.declaration_headers = tuple(export_data.get("headers", ()))
        self.declaration_rows = [list(row) for row in export_data.get("declarations", [])]
        self.st_code = str(export_data.get("code", ""))
        self.operation_summary = dict(export_data.get("operation_summary", {}))

        self.setWindowTitle(self.tr_text(
            "SPS-Export – Mitsubishi GX Works3 XML"
            if self.gxworks3_profile else "SPS-Export – IEC 61131-10 XML",
            "PLC Export – Mitsubishi GX Works3 XML"
            if self.gxworks3_profile else "PLC Export – IEC 61131-10 XML",
        ))
        self.resize(820, 820)
        self.setMinimumSize(680, 600)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        self.settings_panel = PlcExportSettingsPanel(
            export_data.get("fb_name", "FB_NeuronNetz"),
            export_data.get("model_version", "1.0"),
            self.german,
            self,
            target_system=(
                "Mitsubishi GX Works3 XML"
                if self.gxworks3_profile else "IEC 61131-10 XML"
            ),
        )
        self.settings_panel.set_export_options(self._last_export_options)
        self.fb_name_edit = self.settings_panel.fb_name_edit
        self.model_version_edit = self.settings_panel.model_version_edit
        self.fb_name_edit.textChanged.connect(self.fb_name_changed)
        self.model_version_edit.textChanged.connect(self.model_version_changed)
        layout.addWidget(self.settings_panel)

        self.fb_preview_panel = FunctionBlockPreviewPanel(
            self.declaration_headers,
            self.declaration_rows,
            self.fb_name_edit.text(),
            self.german,
            self,
        )
        self.fb_preview = self.fb_preview_panel.preview
        layout.addWidget(self.fb_preview_panel)
        self.fb_name_edit.textChanged.connect(self.fb_preview_panel.set_fb_name)
        self.settings_panel.connectionHelpRequested.connect(
            self.fb_preview_panel.show_connection_help
        )

        variables = variable_summary(self.declaration_headers, self.declaration_rows)
        operations = dict(export_data.get("operation_summary", {}) or {})
        self.operation_info_text = self.settings_panel.operation_text(operations)

        technical_frame = QFrame(self)
        technical_frame.setObjectName("technicalFrame")
        technical_frame.setStyleSheet(
            "QFrame#technicalFrame { border: 1px solid #333333; border-radius: 5px; "
            "background: #f7f8fa; }"
        )
        technical_layout = QVBoxLayout(technical_frame)
        technical_layout.setContentsMargins(9, 5, 9, 5)
        self.technical_info_label = QLabel(technical_frame)
        self.technical_info_label.setWordWrap(True)
        technical_layout.addWidget(self.technical_info_label, 1)
        technical_layout.setSpacing(0)
        self.quality_panel = PruningQualityPanel(
            export_data.get("quality_snapshot"), self.german, self
        )
        technical_layout.addWidget(self.quality_panel)
        self.quality_panel.refresh(self.settings_panel.export_options())
        self.quality_panel.connect_auto_prune(self.settings_panel)
        layout.addWidget(technical_frame)
        self.update_technical_information(variables)

        safety_frame = QFrame(self)
        safety_frame.setObjectName("safetyFrame")
        safety_frame.setStyleSheet(
            "QFrame#safetyFrame { border: 1px solid #e0b85c; border-radius: 5px; "
            "background: #fff4d6; }"
        )
        safety_row = QHBoxLayout()
        safety_row.setContentsMargins(9, 4, 9, 4)
        safety_label = QLabel(self.tr_text(
            "⚠ Der erzeugte SPS-Code muss vor dem produktiven Einsatz fachgerecht "
            "geprüft und validiert werden.",
            "⚠ The generated PLC code must be professionally reviewed and validated "
            "before production use.",
        ), safety_frame)
        safety_label.setWordWrap(True)
        safety_label.setStyleSheet("color: #7a4100; border: none; background: transparent;")
        safety_row.addWidget(safety_label, 1)
        info_button = QPushButton("i", safety_frame)
        self.safety_info_button = info_button
        info_button.setFixedSize(23, 23)
        info_button.setStyleSheet(
            "QPushButton { border: 1px solid #333333; border-radius: 4px; background: #ffffff; }"
            "QPushButton:hover { background: #f0f2f4; }"
        )
        info_button.clicked.connect(self.show_safety_notice)
        safety_row.addWidget(info_button)
        safety_frame.setLayout(safety_row)
        layout.addWidget(safety_frame)

        xml_group = QGroupBox(self.tr_text(
            "Vollständiger XML-Code (schreibgeschützt)",
            "Complete XML code (read-only)",
        ), self)
        xml_group.setStyleSheet(
            "QGroupBox { border: 1px solid #333333; border-radius: 5px; "
            "margin-top: 7px; padding-top: 4px; }"
        )
        xml_layout = QVBoxLayout(xml_group)
        xml_layout.setContentsMargins(7, 10, 7, 7)
        xml_layout.setSpacing(0)
        self.xml_editor = QPlainTextEdit(xml_group)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(10)
        self.xml_editor.setFont(fixed_font)
        self.xml_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.xml_editor.setTabStopDistance(
            self.xml_editor.fontMetrics().horizontalAdvance(" ") * 4
        )
        self.xml_editor.setReadOnly(True)
        self.highlighter = XmlHighlighter(self.xml_editor.document())
        xml_layout.addWidget(self.xml_editor, 1)
        layout.addWidget(xml_group, 1)

        button_frame = QFrame(self)
        button_frame.setObjectName("buttonFrame")
        button_frame.setStyleSheet(
            "QFrame#buttonFrame { border: 1px solid #c6cbd1; border-radius: 5px; "
            "background: #f5f6f7; }"
        )
        button_row = QHBoxLayout(button_frame)
        button_row.setContentsMargins(7, 4, 7, 4)
        button_row.setSpacing(6)
        self.copy_button = QPushButton(self.tr_text("XML kopieren", "Copy XML"), button_frame)
        self.copy_button.setIcon(ToolbarIcons.icon("copy"))
        self.copy_button.clicked.connect(self.copy_xml)
        button_row.addWidget(self.copy_button)
        self.save_button = QPushButton(
            self.tr_text("XML-Datei speichern…", "Save XML file…"), button_frame
        )
        self.save_button.setIcon(ToolbarIcons.icon("save"))
        self.save_button.clicked.connect(self.save_xml)
        button_row.addWidget(self.save_button)
        button_row.addStretch(1)
        close_button = QPushButton(self.tr_text("Schließen", "Close"), button_frame)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addWidget(button_frame)
        self.quality_panel.previewChanged.connect(self.regenerate_xml)
        self.regenerate_xml()
        self.settings_panel.optionsChanged.connect(self.export_options_changed)
        self.copy_guard = ExportCopyGuard(self.xml_editor, self.copy_xml, self.settings_panel.pruning.isChecked)

    def tr_text(self, german, english):
        return german if self.german else english

    def valid_fb_name(self):
        return bool(re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]{0,31}", self.fb_name_edit.text().strip()
        ))

    def update_technical_information(self, variables):
        self.technical_info_label.setText(self.operation_info_text)

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
        self.declaration_headers = tuple(data.get("headers", self.declaration_headers))
        self.declaration_rows[:] = [list(row) for row in data.get("declarations", [])]
        self.st_code = str(data.get("code", ""))
        self._last_export_options = dict(options)
        self.operation_summary = dict(data.get("operation_summary", {}))
        self.quality_panel.refresh(options)
        self.operation_info_text = self.settings_panel.operation_text(
            data.get("operation_summary", {})
        )
        variables = variable_summary(self.declaration_headers, self.declaration_rows)
        self.update_technical_information(variables)
        self.fb_preview_panel.refresh_declarations()
        self.regenerate_xml()

    def regenerate_xml(self):
        if not self.valid_fb_name():
            return
        exporter = GxWorks3XmlExporter if self.gxworks3_profile else Iec61131XmlExporter
        xml_text = exporter.build(
            self.fb_name_edit.text().strip(),
            self.declaration_headers,
            self.declaration_rows,
            self.quality_panel.export_comment(self.settings_panel, preview=True) + self.st_code,
        )
        self.xml_editor.setPlainText(xml_text)
        baseline = None
        baseline_text = ""
        if self.settings_panel.pruning.isChecked() and callable(self.regenerate_callback):
            baseline = self.regenerate_callback(
                {**self.settings_panel.export_options(), "pruning_enabled": False},
                self.model_version_edit.text(),
            )
            baseline_text = exporter.build(
                self.fb_name_edit.text().strip(), baseline["headers"],
                baseline["declarations"], baseline["code"],
            )
            # QPlainTextEdit normalizes line endings; measure exactly what save_xml writes.
            baseline_text = baseline_text.replace("\r\n", "\n").replace("\r", "\n")
        self.operation_info_text = self.settings_panel.compact_information(
            variable_summary(self.declaration_headers, self.declaration_rows),
            self.operation_summary, self.xml_editor.toPlainText(), baseline, baseline_text,
        )
        self.update_technical_information(
            variable_summary(self.declaration_headers, self.declaration_rows)
        )

    def fb_name_changed(self):
        self.regenerate_xml()

    def model_version_changed(self, value):
        label = self.tr_text("Modellversion", "Model version")
        self.st_code = re.sub(
            r"(?m)^\s*(?:Modellversion|Model version):.*$",
            f"    {label}: {value.strip() or '-'}",
            self.st_code,
            count=1,
        )
        name_index = next((i for i, header in enumerate(self.declaration_headers)
                           if str(header).casefold() == "label name"), None)
        constant_index = next((i for i, header in enumerate(self.declaration_headers)
                               if str(header).casefold() == "constant"), None)
        if name_index is not None and constant_index is not None:
            for row in self.declaration_rows:
                if name_index < len(row) and str(row[name_index]) == "Model_Version":
                    row[constant_index] = "'" + value.replace("'", "''")[:48] + "'"
                    break
        self.regenerate_xml()

    def checked_export_xml(self):
        comment = self.quality_panel.export_comment(self.settings_panel)
        if comment is None:
            return None
        if not comment:
            return self.xml_editor.toPlainText()
        exporter = GxWorks3XmlExporter if self.gxworks3_profile else Iec61131XmlExporter
        return exporter.build(self.fb_name_edit.text().strip(), self.declaration_headers,
                              self.declaration_rows, comment + self.st_code)

    def copy_xml(self):
        content = self.checked_export_xml()
        if content is None:
            return
        QApplication.clipboard().setText(content)
        normal = self.tr_text("XML kopieren", "Copy XML")
        self.copy_button.setText(self.tr_text("Kopiert ✓", "Copied ✓"))
        QTimer.singleShot(1400, lambda: self.copy_button.setText(normal))

    def save_xml(self):
        content = self.checked_export_xml()
        if content is None:
            return
        if not self.valid_fb_name():
            QMessageBox.warning(
                self,
                self.tr_text("Ungültiger FB-Name", "Invalid FB name"),
                self.tr_text(
                    "Bitte einen gültigen SPS-Bezeichner mit höchstens 32 Zeichen eingeben.",
                    "Enter a valid PLC identifier with no more than 32 characters.",
                ),
            )
            return
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr_text("XML-Datei speichern", "Save XML file"),
            (
                f"{self.fb_name_edit.text().strip()}_GXWorks3.xml"
                if self.gxworks3_profile
                else f"{self.fb_name_edit.text().strip()}.xml"
            ),
            self.tr_text(
                "Mitsubishi-GX-Works3-XML-Datei (*.xml)"
                if self.gxworks3_profile else "IEC-61131-10-XML-Datei (*.xml)",
                "Mitsubishi GX Works3 XML file (*.xml)"
                if self.gxworks3_profile else "IEC 61131-10 XML file (*.xml)",
            ),
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xml"):
            file_path += ".xml"
        try:
            Path(file_path).write_text(
                content, encoding="utf-8", newline=""
            )
        except OSError as error:
            QMessageBox.critical(self, self.tr_text("Export fehlgeschlagen", "Export failed"), str(error))
            return
        QMessageBox.information(
            self,
            self.tr_text("Export abgeschlossen", "Export complete"),
            self.tr_text(
                f"Die XML-Datei wurde gespeichert:\n{file_path}",
                f"The XML file was saved:\n{file_path}",
            ),
        )

    def show_safety_notice(self):
        show_yellow_information_dialog(
            self,
            self.tr_text("Sicherheits- und Verantwortungshinweis", "Safety and responsibility notice"),
            self.tr_text(
                "Der erzeugte SPS-Code muss vor dem produktiven Einsatz durch eine qualifizierte "
                "Fachkraft geprüft, getestet und für die konkrete Anlage freigegeben werden. "
                "Der Anwender ist für Integration, Validierung, Risikobeurteilung und alle "
                "geltenden Sicherheitsvorschriften verantwortlich. Der Code ist keine "
                "Sicherheits- oder Not-Aus-Funktion.",
                "The generated PLC code must be reviewed, tested, and approved for the specific "
                "installation by a qualified professional before production use. The user is "
                "responsible for integration, validation, risk assessment, and all applicable "
                "safety requirements. The code is not a safety or emergency-stop function.",
            ),
            self.tr_text("Schließen", "Close"),
        )
