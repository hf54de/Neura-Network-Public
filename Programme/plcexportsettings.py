# -------------------------------------------------------------------------------------------------
# Datei: plcexportsettings.py
# Zweck: Gemeinsame Einstellungen und optionale Anschlüsse des SPS-Exports.
# Letzte Änderung: 03.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QRegularExpression, Signal, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from graphicalexperimentdialog import show_yellow_information_dialog


class PlcExportSettingsPanel(QGroupBox):
    """Validierte Metadaten und logisch gekoppelte Exportoptionen."""

    optionsChanged = Signal(dict)
    connectionHelpRequested = Signal()

    DEFAULTS = {
        "enable": True,
        "network_active": True,
        "range_check": True,
        "range_tolerance_input": True,
        "range_error": True,
        "invalid_input_number": True,
        "fallback": True,
        "hold_last_output": True,
    }

    def __init__(self, fb_name, model_version, german=True, parent=None, target_system=""):
        super().__init__("Bausteineinstellungen" if german else "Block settings", parent)
        self.german = german
        self._updating = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 5, 7, 5)
        outer.setSpacing(2)
        fields = QGridLayout()
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setHorizontalSpacing(6)
        fields.setVerticalSpacing(0)
        column = 0
        if target_system:
            fields.addWidget(QLabel("Ziel:" if german else "Target:", self), 0, column)
            column += 1
            self.target_system_edit = QLineEdit(str(target_system), self)
            self.target_system_edit.setReadOnly(True)
            self.target_system_edit.setMinimumWidth(165)
            self.target_system_edit.setMaximumWidth(220)
            fields.addWidget(self.target_system_edit, 0, column)
            column += 1
        fields.addWidget(QLabel("FB-Name:" if german else "FB name:", self), 0, column)
        column += 1
        self.fb_name_edit = QLineEdit(str(fb_name), self)
        validator = QRegularExpressionValidator(
            QRegularExpression(r"[A-Za-z_][A-Za-z0-9_]{0,31}"), self.fb_name_edit
        )
        self.fb_name_edit.setValidator(validator)
        self.fb_name_edit.setMaxLength(32)
        self.fb_name_edit.setMinimumWidth(160)
        self.fb_name_edit.setToolTip(
            "Maximal 32 Zeichen: Buchstaben, Ziffern und Unterstrich; keine Leerzeichen. "
            "Das erste Zeichen muss ein Buchstabe oder Unterstrich sein."
            if german else
            "Up to 32 characters: letters, digits, and underscore; no spaces. "
            "The first character must be a letter or underscore."
        )
        fields.addWidget(self.fb_name_edit, 0, column)
        fields.setColumnStretch(column, 1)
        column += 1
        fields.addWidget(QLabel("Version:", self), 0, column)
        column += 1
        self.model_version_edit = QLineEdit(str(model_version), self)
        self.model_version_edit.setMaximumWidth(110)
        self.model_version_edit.setMinimumWidth(70)
        fields.addWidget(self.model_version_edit, 0, column)
        column += 1
        info = QPushButton("i", self)
        self.info_button = info
        info.setFixedSize(23, 23)
        info.setStyleSheet(
            "QPushButton { border: 1px solid #333333; border-radius: 4px; background: #ffffff; }"
            "QPushButton:hover { background: #f0f2f4; }"
        )
        info.clicked.connect(self.show_settings_help)
        fields.addWidget(info, 0, column)
        outer.addLayout(fields)

        self.options_toggle = QToolButton(self)
        self.options_toggle.setCheckable(True)
        self.options_toggle.setChecked(True)
        self.options_toggle.setArrowType(Qt.ArrowType.DownArrow)
        self.options_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.options_toggle.clicked.connect(self.set_options_expanded)
        options_header = QHBoxLayout()
        options_header.setContentsMargins(0, 0, 0, 0)
        options_header.setSpacing(4)
        options_header.addWidget(self.options_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        options_header.addStretch(1)
        self.connections_info_button = QPushButton("i", self)
        self.connections_info_button.setFixedSize(23, 23)
        self.connections_info_button.setStyleSheet(
            "QPushButton { border: 1px solid #333333; border-radius: 4px; background: #ffffff; }"
            "QPushButton:hover { background: #f0f2f4; }"
        )
        self.connections_info_button.setToolTip(
            "Zusatzanschlüsse und FB-Darstellung erklären" if german else
            "Explain additional connections and FB representation"
        )
        self.connections_info_button.clicked.connect(self.connectionHelpRequested.emit)
        options_header.addWidget(self.connections_info_button)
        outer.addLayout(options_header)

        self.options_widget = QWidget(self)
        options = QGridLayout(self.options_widget)
        options.setContentsMargins(15, 0, 0, 0)
        options.setHorizontalSpacing(12)
        options.setVerticalSpacing(5)
        self.enable = self._check("Enable", "enable")
        self.network_active = self._check("Network_Active", "network_active")
        self.range_check = self._check("Enable_Range_Check", "range_check")
        self.range_tolerance = self._check("Range_Tolerance_Percent", "range_tolerance_input")
        self.range_error = self._check("Input_Range_Error", "range_error")
        self.invalid_number = self._check("Invalid_Input_Number", "invalid_input_number")
        self.fallback = self._check("Fallback_<Ausgang>" if german else "Fallback_<output>", "fallback")
        self.hold_last = self._check("Hold_Last_Output", "hold_last_output")
        input_title = QLabel("Eingangsoptionen" if german else "Input options", self.options_widget)
        output_title = QLabel("Ausgangsoptionen" if german else "Output options", self.options_widget)
        title_style = "font-weight: 600; color: #394b59;"
        input_title.setStyleSheet(title_style)
        output_title.setStyleSheet(title_style)
        options.addWidget(input_title, 0, 0, 1, 2)
        options.addWidget(output_title, 0, 3)

        options.addWidget(self.enable, 1, 0)
        options.addWidget(self.hold_last, 1, 1)
        options.addWidget(self.range_check, 2, 0)
        options.addWidget(self.fallback, 2, 1)
        options.addWidget(self.range_tolerance, 3, 0)

        separator = QFrame(self.options_widget)
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #c7cdd3;")
        options.addWidget(separator, 0, 2, 4, 1)
        options.setColumnMinimumWidth(2, 55)

        options.addWidget(self.network_active, 1, 3)
        options.addWidget(self.range_error, 2, 3)
        options.addWidget(self.invalid_number, 3, 3)
        options.setColumnStretch(0, 1)
        options.setColumnStretch(1, 1)
        options.setColumnStretch(3, 1)
        outer.addWidget(self.options_widget)
        self.options_widget.setVisible(True)
        self._apply_dependencies(emit=False)

    def _check(self, text, key):
        checkbox = QCheckBox(text, self)
        checkbox.setStyleSheet("QCheckBox { spacing: 5px; }")
        checkbox.setChecked(self.DEFAULTS[key])
        checkbox.toggled.connect(self._apply_dependencies)
        return checkbox

    def export_options(self):
        trigger = self.enable.isChecked() or self.range_check.isChecked()
        return {
            "enable": self.enable.isChecked(),
            "network_active": trigger and self.network_active.isChecked(),
            "range_check": self.range_check.isChecked(),
            "range_tolerance_input": self.range_check.isChecked() and self.range_tolerance.isChecked(),
            "range_error": self.range_check.isChecked() and self.range_error.isChecked(),
            "invalid_input_number": self.range_check.isChecked() and self.range_error.isChecked()
            and self.invalid_number.isChecked(),
            "fallback": trigger and self.fallback.isChecked(),
            "hold_last_output": trigger and self.fallback.isChecked() and self.hold_last.isChecked(),
        }

    def set_export_options(self, values):
        values = {**self.DEFAULTS, **dict(values or {})}
        self._updating = True
        for widget, key in (
            (self.enable, "enable"), (self.network_active, "network_active"),
            (self.range_check, "range_check"), (self.range_tolerance, "range_tolerance_input"),
            (self.range_error, "range_error"), (self.invalid_number, "invalid_input_number"),
            (self.fallback, "fallback"), (self.hold_last, "hold_last_output"),
        ):
            widget.setChecked(bool(values[key]))
        self._updating = False
        self._apply_dependencies(emit=False)

    def _apply_dependencies(self, _checked=False, emit=True):
        trigger = self.enable.isChecked() or self.range_check.isChecked()
        self.network_active.setEnabled(trigger)
        self.range_tolerance.setEnabled(self.range_check.isChecked())
        self.range_error.setEnabled(self.range_check.isChecked())
        self.invalid_number.setEnabled(self.range_check.isChecked() and self.range_error.isChecked())
        self.fallback.setEnabled(trigger)
        self.hold_last.setEnabled(trigger and self.fallback.isChecked())
        self._update_options_caption()
        if emit and not self._updating:
            self.optionsChanged.emit(self.export_options())

    def _update_options_caption(self):
        selected = sum(bool(value) for value in self.export_options().values())
        self.options_toggle.setText(
            (f"Zusatzanschlüsse ({selected} von 8 ausgewählt)" if self.german else
             f"Additional connections ({selected} of 8 selected)")
        )

    def set_options_expanded(self, expanded):
        self.options_widget.setVisible(expanded)
        self.options_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def show_settings_help(self):
        if self.german:
            title = "Bausteineinstellungen"
            text = (
                "FB-NAME\nBestimmt den Namen des Funktionsbausteins in ASC/XML und den "
                "vorgeschlagenen Dateinamen. Erlaubt sind höchstens 32 Zeichen: Buchstaben, "
                "Ziffern und Unterstrich. Das erste Zeichen darf keine Ziffer sein.\n\n"
                "MODELLVERSION\nFrei wählbare Kennzeichnung des Trainingsstands. Sie beeinflusst "
                "die Berechnung nicht. Model_Signature kennzeichnet das konkrete Netz zusätzlich "
                "automatisch."
            )
        else:
            title = "Block settings"
            text = (
                "FB NAME\nDetermines the function-block name in ASC/XML and the suggested file "
                "name. Up to 32 characters are allowed: letters, digits, and underscore. The "
                "first character cannot be a digit.\n\n"
                "MODEL VERSION\nA freely chosen identifier for the training state. It does not "
                "affect calculation. Model_Signature additionally identifies the concrete network "
                "automatically."
            )
        show_yellow_information_dialog(
            self, title, text, "Schließen" if self.german else "Close"
        )
