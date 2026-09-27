# -------------------------------------------------------------------------------------------------
# Datei: plcexportsettings.py
# Zweck: Gemeinsame Einstellungen und optionale Anschlüsse des SPS-Exports.
# Letzte Änderung: 03.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import re

from PySide6.QtCore import QRegularExpression, Signal, Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QRegularExpressionValidator, QValidator
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from graphicalexperimentdialog import show_yellow_information_dialog


class PruningThresholdSpinBox(QDoubleSpinBox):
    """Keep input precision while omitting insignificant trailing zeroes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.input_timer = QTimer(self)
        self.input_timer.setSingleShot(True)
        self.input_timer.setInterval(300)
        self.input_timer.timeout.connect(self.update_preview)
        self.lineEdit().textEdited.connect(lambda: self.input_timer.start())

    def commit_input(self):
        self.input_timer.stop()
        if self.hasAcceptableInput():
            self.interpretText()

    def validate(self, text, position):
        # Treat both separators as decimal separators, never as grouping marks.
        if text in ("", ".", ","):
            return QValidator.State.Intermediate, text, position
        if not re.fullmatch(r"[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+", text):
            return QValidator.State.Invalid, text, position
        fractional = re.split(r"[.,]", text)
        if len(fractional) == 2 and len(fractional[1]) > self.decimals():
            return QValidator.State.Invalid, text, position
        value = self.valueFromText(text)
        state = (QValidator.State.Acceptable if self.minimum() <= value <= self.maximum()
                 else QValidator.State.Invalid)
        return state, text, position

    def valueFromText(self, text):
        return float(text.replace(",", "."))

    def update_preview(self):
        editor = self.lineEdit()
        text = editor.text()
        # A trailing separator is an unfinished edit, even though Enter can commit it.
        if text.endswith((",", ".")) or not self.hasAcceptableInput():
            return
        value = self.valueFromText(text)
        if value == self.value():
            return
        cursor = editor.cursorPosition()
        selection_start = editor.selectionStart()
        selection_length = len(editor.selectedText())
        with QSignalBlocker(self), QSignalBlocker(editor):
            self.setValue(value)
            editor.setText(text)
            editor.setCursorPosition(cursor)
            if selection_start >= 0:
                anchor = selection_start if cursor != selection_start else selection_start + selection_length
                editor.setSelection(anchor, cursor - anchor)
        self.valueChanged.emit(self.value())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.commit_input()
            event.accept()
            return
        super().keyPressEvent(event)

    def textFromValue(self, value):
        text = self.locale().toString(value, "f", self.decimals())
        text = text.replace(self.locale().groupSeparator(), "")
        return text.rstrip("0").rstrip(self.locale().decimalPoint()) if self.decimals() else text


class PlcExportSettingsPanel(QGroupBox):
    """Validierte Metadaten und logisch gekoppelte Exportoptionen."""

    optionsChanged = Signal(dict)
    connectionHelpRequested = Signal()

    DEFAULTS = {
        "enable": False,
        "enable_out": False,
        "binary_uncertainty": False,
        "uncertain_output_number": False,
        "uncertainty_lower": 0.3,
        "uncertainty_upper": 0.7,
        "network_active": False,
        "range_check": False,
        "range_tolerance_input": False,
        "range_error": False,
        "invalid_input_number": False,
        "fallback": False,
        "hold_last_output": False,
        "pruning_enabled": False,
        "pruning_threshold": 0.001,
    }

    def __init__(self, fb_name, model_version, german=True, parent=None, target_system=""):
        super().__init__("Bausteineinstellungen" if german else "Block settings", parent)
        self.german = german
        self._updating = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 5, 7, 5)
        outer.setSpacing(7)
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
            "Optionen und FB-Darstellung erklären" if german else
            "Explain options and FB representation"
        )
        self.connections_info_button.clicked.connect(self.connectionHelpRequested.emit)
        options_header.addWidget(self.connections_info_button)
        outer.addLayout(options_header)

        self.options_content = QWidget(self)
        option_body = QVBoxLayout(self.options_content)
        option_body.setContentsMargins(0, 0, 0, 0)
        option_body.setSpacing(1)
        outer.addWidget(self.options_content)
        self.options_widget = QWidget(self.options_content)
        options = QGridLayout(self.options_widget)
        options.setContentsMargins(15, 0, 15, 0)
        options.setHorizontalSpacing(12)
        options.setVerticalSpacing(1)
        self.enable = self._check("Enable", "enable")
        self.enable_out = self._check("Enable_Out", "enable_out")
        self.network_active = self._check("Network_Active", "network_active")
        self.range_check = self._check("Enable_Range_Check", "range_check")
        self.range_tolerance = self._check("Range_Tolerance_Percent", "range_tolerance_input")
        self.range_error = self._check("Input_Range_Error", "range_error")
        self.invalid_number = self._check("Invalid_Input_Number", "invalid_input_number")
        self.fallback = self._check("Fallback_<Ausgang>" if german else "Fallback_<output>", "fallback")
        self.hold_last = self._check("Hold_Last_Output", "hold_last_output")
        for widget, name, explanation in (
            (self.enable, "Enable", "Gibt die Netzberechnung frei."),
            (self.enable_out, "Enable_Out", "Gibt die Freigabe unverändert weiter."),
            (self.network_active, "Network_Active", "Optionaler Informationsausgang: TRUE bei ausgeführter Berechnung. Unabhängig von der Unklarheitsprüfung wählbar. Das Häkchen fügt den Anschluss hinzu, setzt aber nicht seinen SPS-Wert."),
            (self.range_check, "Enable_Range_Check", "Schaltet die Prüfung der Eingangsbereiche frei."),
            (self.range_tolerance, "Range_Tolerance_Percent", "Zusätzlicher Eingang für die zulässige Toleranz in Prozent."),
            (self.range_error, "Input_Range_Error", "Meldet eine Überschreitung des zulässigen Eingangsbereichs."),
            (self.invalid_number, "Invalid_Input_Number", "Gibt die Nummer des ersten ungültigen Eingangs aus."),
            (self.fallback, "Fallback_<Ausgang>", "Zusätzliche Eingänge für Ersatzwerte der Ausgänge."),
            (self.hold_last, "Hold_Last_Output", "Hält bei gesperrter Berechnung die zuletzt ausgegebenen Werte."),
        ):
            widget.setToolTip(f"{name}: {explanation}" if german else name)
        if not german:
            self.network_active.setToolTip("Network_Active: Optional calculation status output, independent of uncertainty checking. Selecting this option adds the output; it does not set its PLC value.")
        input_title = QLabel("Eingangsoptionen" if german else "Input options", self.options_widget)
        output_title = QLabel("Ausgangsoptionen" if german else "Output options", self.options_widget)
        title_style = "font-weight: 600; color: #394b59;"
        input_title.setStyleSheet(title_style)
        output_title.setStyleSheet(title_style)
        inputs = QGridLayout()
        outputs = QGridLayout()
        for grid in (inputs, outputs):
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(1)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
        inputs.addWidget(input_title, 0, 0, 1, 2)
        outputs.addWidget(output_title, 0, 0, 1, 2)
        inputs.addWidget(self.enable, 1, 0)
        inputs.addWidget(self.hold_last, 1, 1)
        inputs.addWidget(self.range_check, 2, 0)
        inputs.addWidget(self.fallback, 2, 1)
        inputs.addWidget(self.range_tolerance, 3, 0)
        outputs.addWidget(self.network_active, 1, 0)
        outputs.addWidget(self.range_error, 2, 0)
        outputs.addWidget(self.invalid_number, 3, 0)
        outputs.addWidget(self.enable_out, 1, 1)
        self.uncertainty_lower = 0.3
        self.uncertainty_upper = 0.7
        self.binary_uncertainty = self._check("Binary_Output_Uncertain", "binary_uncertainty")
        self.binary_uncertainty.setToolTip(
            "Prüft binäre Ausgänge auf Unklarheit. TRUE meldet mindestens einen Ausgang innerhalb der Projektgrenzen unter Einstellungen → SPS-Export → Binäre Ausgänge."
            if german else "Checks binary outputs for uncertainty. TRUE indicates at least one output within the project uncertainty limits in Settings → PLC Export → Binary outputs.")
        self.uncertain_output_number = self._check("Uncertain_Output_Number", "uncertain_output_number")
        self.uncertain_output_number.setToolTip(
            "Uncertain_Output_Number: Nummer des ersten unklaren Ausgangs; 0 bedeutet keiner."
            if german else "Uncertain_Output_Number: Number of the first uncertain output; 0 means none.")
        inputs.addWidget(self.binary_uncertainty, 4, 0, 1, 2)
        outputs.addWidget(self.uncertain_output_number, 2, 1)
        self.separator = QFrame(self.options_widget)
        self.separator.setFrameShape(QFrame.Shape.VLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator.setStyleSheet("color: #c7cdd3;")
        options.addLayout(inputs, 0, 0)
        options.addWidget(self.separator, 0, 1)
        options.addLayout(outputs, 0, 2)
        # Equal minima and stretch keep the divider centred at every width.
        half_width = max(inputs.minimumSize().width(), outputs.minimumSize().width())
        for column in (0, 2):
            options.setColumnMinimumWidth(column, half_width)
            options.setColumnStretch(column, 1)
        option_body.addWidget(self.options_widget)
        pruning_row = QHBoxLayout()
        pruning_row.setContentsMargins(15, 0, 0, 0)
        self.pruning = self._check(
            "Automatisches Pruning" if german else "Automatic pruning", "pruning_enabled"
        )
        pruning_row.addWidget(self.pruning)
        pruning_row.addWidget(QLabel("Schwellwert |Gewicht| ≤" if german else "Threshold |weight| ≤", self))
        self.pruning_threshold = PruningThresholdSpinBox(self)
        self.pruning_threshold.setToolTip(
            "Gewichte mit einem Betrag bis einschließlich dieses Wertes werden im Export entfernt. "
            "Bei 0 werden nur exakt nullwertige Gewichte entfernt."
            if german else
            "Weights with an absolute value up to and including this threshold are removed from the export. "
            "At 0, only exactly zero weights are removed."
        )
        self.pruning_threshold.setDecimals(9)
        self.pruning_threshold.setRange(0.0, 1000000.0)
        self.pruning_threshold.setSingleStep(0.001)
        self.pruning_threshold.setValue(self.DEFAULTS["pruning_threshold"])
        self.pruning_threshold.setKeyboardTracking(False)
        self.pruning_threshold.valueChanged.connect(self._apply_dependencies)
        pruning_row.addWidget(self.pruning_threshold)
        self.auto_prune_button = QPushButton("Auto-Prune…", self)
        self.auto_prune_button.setAutoDefault(False)
        self.auto_prune_button.setEnabled(False)
        self.auto_prune_button.setToolTip(
            "Schwellwert anhand der Trainingsdaten automatisch suchen"
            if german else "Find a threshold automatically using training data"
        )
        pruning_row.addWidget(self.auto_prune_button)
        pruning_row.addStretch(1)
        row_height = max(self.pruning_threshold.sizeHint().height(), self.auto_prune_button.sizeHint().height(), self.enable.sizeHint().height())
        for grid in (inputs, outputs):
            for row in range(1, 5):
                grid.setRowMinimumHeight(row, row_height)
        output_last_row = QWidget(self.options_widget)
        output_last_row.setFixedHeight(row_height)
        outputs.addWidget(output_last_row, 4, 0, 1, 2)
        for checkbox in (self.enable, self.enable_out, self.network_active,
                         self.range_check, self.range_tolerance, self.range_error,
                         self.invalid_number, self.fallback, self.hold_last,
                         self.binary_uncertainty, self.uncertain_output_number, self.pruning):
            checkbox.setFixedHeight(row_height)
        option_body.addLayout(pruning_row)
        pruning_hint = QLabel(
            "Entfernt kleine Gewichte nur im Export. Kann Ergebnisse verändern; "
            "das gespeicherte Netz bleibt unverändert."
            if german else
            "Removes small weights only from the export. May change results; "
            "the saved network remains unchanged.", self
        )
        pruning_hint.setWordWrap(True)
        option_body.addWidget(pruning_hint)
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
            "pruning_enabled": self.pruning.isChecked(),
            "pruning_threshold": self.pruning_threshold.value(),
            "enable": self.enable.isChecked(),
            "enable_out": self.enable.isChecked() and self.enable_out.isChecked(),
            "binary_uncertainty": self.binary_uncertainty.isChecked(),
            "uncertain_output_number": self.binary_uncertainty.isChecked() and self.uncertain_output_number.isChecked(),
            "uncertainty_lower": self.uncertainty_lower,
            "uncertainty_upper": self.uncertainty_upper,
            "network_active": self.network_active.isChecked(),
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
            (self.enable_out, "enable_out"),
            (self.binary_uncertainty, "binary_uncertainty"),
            (self.uncertain_output_number, "uncertain_output_number"),
            (self.range_check, "range_check"), (self.range_tolerance, "range_tolerance_input"),
            (self.range_error, "range_error"), (self.invalid_number, "invalid_input_number"),
            (self.fallback, "fallback"), (self.hold_last, "hold_last_output"),
            (self.pruning, "pruning_enabled"),
        ):
            widget.setChecked(bool(values[key]))
        self.pruning_threshold.setValue(float(values["pruning_threshold"]))
        self.uncertainty_lower = values["uncertainty_lower"]
        self.uncertainty_upper = values["uncertainty_upper"]
        self._updating = False
        self._apply_dependencies(emit=False)

    def _apply_dependencies(self, _checked=False, emit=True):
        if self._updating:
            return
        self.pruning_threshold.setEnabled(self.pruning.isChecked())
        trigger = self.enable.isChecked() or self.range_check.isChecked()
        self.network_active.setEnabled(True)
        self.uncertain_output_number.setEnabled(self.binary_uncertainty.isChecked())
        self.enable_out.setEnabled(self.enable.isChecked())
        self.range_tolerance.setEnabled(self.range_check.isChecked())
        self.range_error.setEnabled(self.range_check.isChecked())
        self.invalid_number.setEnabled(self.range_check.isChecked() and self.range_error.isChecked())
        self.fallback.setEnabled(trigger)
        self.hold_last.setEnabled(trigger and self.fallback.isChecked())
        self._update_options_caption()
        if emit and not self._updating:
            self.optionsChanged.emit(self.export_options())

    def _update_options_caption(self):
        self.options_toggle.setText("Optionen" if self.german else "Options")

    def set_options_expanded(self, expanded):
        self.options_toggle.setChecked(expanded)
        self.options_content.setVisible(expanded)
        self.options_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def operation_text(self, summary):
        return (
            "Aufwand: {multiplications} MUL · {additions} ADD · {exp_calls} EXP · "
            "Pruning: {pruned_connections} Verbindungen entfernt"
            if self.german else
            "Effort: {multiplications} MUL · {additions} ADD · {exp_calls} EXP · "
            "Pruning: {pruned_connections} connections removed"
        ).format(**{**dict.fromkeys(("multiplications", "additions", "exp_calls",
                                   "pruned_connections"), 0), **summary})

    def compact_information(self, variables, operations, current_text="", baseline=None,
                            baseline_text="", format_name="XML"):
        from plcfileexport import variable_summary
        def number(value):
            return f"{value:.1f}".replace(".", ",") if self.german else f"{value:.1f}"
        first = (
            "Anschlüsse: {io} · Skalierung: {scaling} · Bias: {biases} · Neuronen: {neurons}"
            if self.german else
            "Connections: {io} · Scaling: {scaling} · Biases: {biases} · Neurons: {neurons}"
        ).format(**variables)
        size = number(len(current_text.encode("utf-8")) / 1000)
        if baseline is not None:
            old = variable_summary(baseline["headers"], baseline["declarations"])
            before = baseline["operation_summary"]
            old_bytes = len(baseline_text.encode("utf-8"))
            new_bytes = len(current_text.encode("utf-8"))
            saving = number(100 * (old_bytes - new_bytes) / old_bytes if old_bytes else 0)
            second = (
                f"Vor → Nach: Variablen {old['total']} → {variables['total']} · "
                f"Gewichte {old['weights']} → {variables['weights']}"
                if self.german else
                f"Before → After: Variables {old['total']} → {variables['total']} · "
                f"Weights {old['weights']} → {variables['weights']}"
            )
            third = (f"MUL {before['multiplications']} → {operations['multiplications']} · "
                     f"ADD {before['additions']} → {operations['additions']} · "
                     f"{operations['exp_calls']} EXP · {format_name}: "
                     f"{number(old_bytes / 1000)} → {size} kB (−{saving} %)")
            if not operations.get("pruned_connections", 0):
                second += " · Keine Einsparung" if self.german else " · No savings"
        else:
            second = (
                f"Variablen: {variables['total']} · Gewichte: {variables['weights']} · Pruning: aus"
                if self.german else
                f"Variables: {variables['total']} · Weights: {variables['weights']} · Pruning: off"
            )
            third = (f"{operations.get('multiplications', 0)} MUL · "
                     f"{operations.get('additions', 0)} ADD · {operations.get('exp_calls', 0)} EXP · "
                     f"{format_name}: {size} kB")
            third = ("Aufwand: " if self.german else "Effort: ") + third
        return "\n".join((first, second, third))

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
