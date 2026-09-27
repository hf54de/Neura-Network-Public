# -------------------------------------------------------------------------------------------------
# Datei: fbpreview.py
# Zweck: Kompakte grafische Vorschau eines SPS-Funktionsbausteins.
# Letzte Änderung: 03.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from html import escape

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from graphicalexperimentdialog import show_yellow_information_dialog


class FunctionBlockPreview(QWidget):
    """Zeigt Ein- und Ausgänge einer Deklaration als IEC-nahe FB-Skizze."""

    def __init__(self, headers, rows, fb_name="FB_NeuronNetz", parent=None):
        super().__init__(parent)
        self.headers = tuple(headers)
        self.rows = rows
        self.fb_name = str(fb_name)
        self.setMinimumHeight(105)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self):
        pin_count = max(len(self._pins("VAR_INPUT")), len(self._pins("VAR_OUTPUT")), 3)
        return QSize(760, 50 + pin_count * 18)

    def set_fb_name(self, name):
        self.fb_name = str(name).strip() or "?"
        self.update()

    def refresh_declarations(self):
        self.updateGeometry()
        self.update()

    def _column(self, name):
        wanted = name.casefold()
        return next((index for index, header in enumerate(self.headers)
                     if str(header).casefold() == wanted), None)

    def _pins(self, variable_class):
        class_column = self._column("Class")
        name_column = self._column("Label Name")
        type_column = self._column("Data Type")
        if class_column is None or name_column is None:
            return []
        pins = []
        rows = self.rows() if callable(self.rows) else self.rows
        for row in rows:
            if class_column >= len(row) or str(row[class_column]).strip().upper() != variable_class:
                continue
            name = str(row[name_column]).strip() if name_column < len(row) else ""
            data_type = str(row[type_column]).strip() if type_column is not None and type_column < len(row) else ""
            if name:
                pins.append((name, data_type))
        return pins

    @staticmethod
    def _pin_color(data_type):
        value = str(data_type).upper()
        if "BOOL" in value or value == "BIT":
            return QColor("#2457c5")
        if any(token in value for token in ("REAL", "FLOAT", "LREAL")):
            return QColor("#149447")
        return QColor("#8a4fa3")

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f7f9fc"))

        scale = min(1.0, self.height() / self.sizeHint().height())
        painter.scale(scale, scale)
        draw_width = self.width() / scale
        draw_height = self.height() / scale
        inputs = self._pins("VAR_INPUT")
        outputs = self._pins("VAR_OUTPUT")
        count = max(len(inputs), len(outputs), 1)
        top = 29.0
        bottom = max(top + 35.0, float(draw_height - 11))
        step = (bottom - top) / max(count, 1)
        title_width = painter.fontMetrics().horizontalAdvance(self.fb_name)
        block_width = min(300.0, max(220.0, float(title_width + 50)))
        block_left = (draw_width - block_width) / 2.0
        block = QRectF(block_left, 8.0, block_width, max(65.0, bottom - 8.0))

        painter.setPen(QPen(QColor("#486581"), 1.5))
        painter.setBrush(QColor("#fff3cd"))
        painter.drawRoundedRect(block, 5, 5)
        title_font = QFont(self.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#1f2933"))
        painter.drawText(QRectF(block.left() + 8, block.top() + 5, block.width() - 16, 24),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                         self.fb_name)

        pin_font = QFont(self.font())
        pin_font.setPointSize(max(8, pin_font.pointSize() - 1))
        painter.setFont(pin_font)
        line_length = min(42.0, max(24.0, (draw_width - block.width()) * 0.09))
        label_width = max(90.0, block.left() - line_length - 12.0)

        for index, (name, data_type) in enumerate(inputs):
            y = top + (index + 0.5) * step
            color = self._pin_color(data_type)
            painter.setPen(QPen(color, 2))
            painter.drawLine(int(block.left() - line_length), int(y), int(block.left()), int(y))
            painter.setPen(color)
            painter.drawText(QRectF(4, y - 10, label_width, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, name)

        right_start = block.right() + line_length
        for index, (name, data_type) in enumerate(outputs):
            y = top + (index + 0.5) * step
            color = self._pin_color(data_type)
            painter.setPen(QPen(color, 2))
            painter.drawLine(int(block.right()), int(y), int(right_start), int(y))
            painter.setPen(color)
            painter.drawText(QRectF(right_start + 8, y - 10,
                                    max(80.0, draw_width - right_start - 12), 20),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)


class FunctionBlockPreviewPanel(QFrame):
    """Aufklappbare Vorschau mit Anschlusshilfe."""

    def __init__(self, headers, rows, fb_name, german=True, parent=None):
        super().__init__(parent)
        self.headers = tuple(headers)
        self.rows = rows
        self.fb_name = str(fb_name)
        self.german = german
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "FunctionBlockPreviewPanel { border: 1px solid #333333; "
            "border-radius: 5px; background: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 3, 9, 4)
        layout.setSpacing(1)
        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 0, 0)
        header.setSpacing(3)
        self.toggle = QToolButton(self)
        self.toggle.setText("FB-Vorschau" if german else "FB preview")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle.clicked.connect(self.set_expanded)
        header.addWidget(self.toggle)
        header.addStretch(1)
        layout.addLayout(header)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.preview = FunctionBlockPreview(headers, rows, fb_name, self.scroll)
        self.scroll.setWidget(self.preview)
        self._adjust_preview_height()
        self.scroll.setVisible(True)
        layout.addWidget(self.scroll)

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        if expanded:
            self._adjust_preview_height()
        self.scroll.setVisible(expanded)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def set_fb_name(self, name):
        self.fb_name = str(name).strip() or "?"
        self.preview.set_fb_name(self.fb_name)

    def refresh_declarations(self):
        self.preview.refresh_declarations()
        self._adjust_preview_height()
        self.updateGeometry()

    def _adjust_preview_height(self):
        """Passt Zeichenfläche und sichtbaren Bereich an die aktuelle Pin-Anzahl an."""
        content_height = self.preview.sizeHint().height()
        # Fit even large blocks completely; scale their drawing if the screen is small.
        visible_height = min(content_height, max(160, int(self.screen().availableGeometry().height() * 0.45)))
        self.preview.setFixedHeight(visible_height)
        self.preview.setMinimumWidth(700)
        self.preview.resize(max(self.preview.width(), 700), visible_height)
        frame = self.scroll.frameWidth() * 2
        self.scroll.setFixedHeight(visible_height + frame)

    def show_connection_help(self):
        if self.german:
            title = "Zusatzanschlüsse des Funktionsbausteins"
            text = (
                "Enable\nTRUE führt die Netzberechnung aus. Bei FALSE wird das Netz nicht "
                "berechnet und Network_Active wird FALSE. Enable ist keine Sicherheits- oder "
                "Not-Aus-Funktion.\n\n"
                "Hold_Last_Output\nTRUE behält bei gesperrter oder fehlerhafter Berechnung die "
                "zuletzt ausgegebenen Werte. Bei FALSE werden die Fallback_...-Ersatzwerte "
                "ausgegeben.\n\n"
                "Enable_Range_Check\nSchaltet die Prüfung der analogen Eingänge gegen die beim "
                "Training gespeicherten Min-/Max-Grenzen ein.\n\n"
                "Range_Tolerance_Percent\nErlaubte Überschreitung der Trainingsgrenzen in Prozent "
                "der jeweiligen Wertebandbreite. Beispiel: 10.0 bedeutet 10 %.\n\n"
                "Binary_Output_Uncertain\nPrüft die internen Ausgangswerte mit den gemeinsamen "
                "Projektgrenzen unter Einstellungen → SPS-Export → Binäre Ausgänge (Standard: 0,3 < Wert < 0,7). "
                "Die Grenzen selbst zählen nicht zum Unklarheitsbereich. "
                "TRUE, sobald mindestens ein binärer Netzausgang im "
                "Unklarheitsbereich liegt.\n\n"
                "Uncertain_Output_Number\nNennt optional den ersten "
                "betroffenen Ausgang, ab 1 in der Reihenfolge aller Netzausgänge einschließlich "
                "analoger Ausgänge; 0 bedeutet keiner. Analoge Ausgänge werden nicht geprüft.\n\n"
                "Beide Diagnoseausgänge werden bei jedem Aufruf zurückgesetzt und nur bei "
                "ausgeführter Netzberechnung ausgewertet. FALSE allein bestätigt keine Prüfung: "
                "optional kann Network_Active die ausgeführte Berechnung bestätigen. Der BOOL-Ausgang bleibt TRUE bei > 0,5, "
                "sonst FALSE; Enable_Out bleibt unverändert. Die Warnung bewertet die Nähe zur "
                "Schaltschwelle, nicht die Richtigkeit der Vorhersage.\n\n"
                "Network_Active\nOptionaler Informationsausgang. TRUE bedeutet, dass das Netz in diesem SPS-Zyklus berechnet wurde, sonst FALSE. Das Häkchen fügt nur den Anschluss hinzu und setzt nicht dessen Wert. Die Unklarheitsprüfung funktioniert unabhängig davon; der Anschluss kann abgewählt werden. Ohne Berechnung wird die Unklarheitsmeldung zurückgesetzt.\n\n"
                "Enable_Out\nOptionaler BOOL-Ausgang, nur mit Enable verfügbar. Gibt Enable bei "
                "jedem Aufruf unverändert weiter, auch bei Eingangsfehlern. Zum Verketten mit Enable "
                "des nächsten Bausteins verbinden. Anders als Network_Active bestätigt Enable_Out "
                "nicht, dass die Netzberechnung ausgeführt wurde.\n\n"
                "Input_Range_Error\nTRUE, wenn bei eingeschalteter Prüfung mindestens ein Eingang "
                "außerhalb des erlaubten Bereichs liegt.\n\n"
                "Invalid_Input_Number\nNummer des ersten ungültigen Eingangs; 0 bedeutet kein Fehler.\n\n"
                "Fallback_<Ausgang>\nSicher festzulegender Ersatzwert für den jeweiligen Ausgang. "
                "Er wird bei Enable = FALSE oder Input_Range_Error = TRUE verwendet, sofern "
                "Hold_Last_Output = FALSE ist.\n\n"
                "Ohne Fallback-Anschlüsse bleiben die letzten Ausgänge erhalten. Mit Fallback, "
                "aber ohne Hold_Last_Output werden Ersatzwerte immer ausgegeben. Sind beide "
                "vorhanden, entscheidet Hold_Last_Output zur Laufzeit. Nicht erzeugte Anschlüsse "
                "und ihre Codeabschnitte entfallen vollständig.\n\n"
                "Pruning\n"
                "Entfernt im SPS-Export Verbindungen, deren Gewicht im Betrag kleiner oder gleich "
                "dem eingestellten Schwellwert ist. Dadurch können Codegröße und Rechenaufwand "
                "sinken. Das gespeicherte Netz bleibt unverändert.\n\n"
                "Qualitätsprüfung: Vergleicht den mittleren quadratischen Fehler (MSE) des "
                "ursprünglichen und des beschnittenen Netzes anhand derselben Daten. Ein positiver "
                "Fehleranstieg bedeutet eine Verschlechterung. Bei Trainingsdaten ist dies keine "
                "Garantie für neue Eingaben.\n\n"
                "Auto-Prune: Sucht einen Schwellwert innerhalb der gewählten Fehlergrenze. Kann "
                "keine Verbindung innerhalb dieser Grenze entfernt werden, erscheint "
                "‚Kein sinnvolles Pruning möglich‘.\n\n"
                "Bei aktivem Pruning warnt der Export bei gelber Bewertung; bei roter Bewertung "
                "wird er blockiert."
            )
        else:
            title = "Additional function-block connections"
            text = (
                "Enable\nTRUE executes the network calculation. If FALSE, the network is not "
                "calculated and Network_Active becomes FALSE. Enable is not a safety or emergency-"
                "stop function.\n\n"
                "Hold_Last_Output\nTRUE retains the last outputs when calculation is disabled or "
                "invalid. If FALSE, the Fallback_... values are written.\n\n"
                "Enable_Range_Check\nEnables checking of analog inputs against the minimum and "
                "maximum limits stored during training.\n\n"
                "Range_Tolerance_Percent\nPermitted limit overrun as a percentage of the respective "
                "value span. Example: 10.0 means 10%.\n\n"
                "Binary_Output_Uncertain\nChecks internal output values using the shared "
                "project limits in Settings → PLC Export → Binary outputs (default: 0.3 < value < 0.7). "
                "The boundaries themselves are not uncertain. "
                "TRUE if any binary network output is inside the "
                "uncertainty range.\n\n"
                "Uncertain_Output_Number\nOptionally identifies the first affected "
                "output, numbered from 1 across all network outputs, including analog outputs; "
                "0 means none. Analog outputs are not checked.\n\n"
                "Both diagnostic outputs are reset on every call and evaluated only when the "
                "network calculation runs. FALSE alone does not confirm evaluation: also check "
                "the optional Network_Active output to confirm calculation. BOOL remains TRUE above 0.5, otherwise FALSE; Enable_Out is "
                "unchanged. This warning indicates proximity to the switching threshold, not "
                "whether the prediction is correct.\n\n"
                "Network_Active\nOptional information output. TRUE when the network was calculated in this PLC cycle, otherwise FALSE. The checkbox adds the output; it does not set its value. Uncertainty checking works independently and does not require this output. Without calculation, the uncertainty flag is reset.\n\n"
                "Enable_Out\nOptional BOOL output, available only with Enable. Passes Enable through "
                "unchanged on every call, including on input errors. Connect it to Enable of the next "
                "block to chain blocks. Unlike Network_Active, Enable_Out does not confirm that "
                "the network calculation was executed.\n\n"
                "Input_Range_Error\nTRUE when checking is enabled and at least one input is outside "
                "the permitted range.\n\n"
                "Invalid_Input_Number\nNumber of the first invalid input; 0 means no error.\n\n"
                "Fallback_<output>\nA safe substitute value to be defined for each output. It is "
                "used when Enable = FALSE or Input_Range_Error = TRUE, provided "
                "Hold_Last_Output = FALSE.\n\n"
                "Without fallback connections, the last outputs are retained. With fallback but "
                "without Hold_Last_Output, substitute values are always written. When both are "
                "present, Hold_Last_Output selects the behavior at runtime. Connections that are "
                "not generated and their code sections are omitted completely.\n\n"
                "Pruning\n"
                "Removes connections from the PLC export whose absolute weight is less than or "
                "equal to the selected threshold. This can reduce code size and computation. "
                "The saved network remains unchanged.\n\n"
                "Quality check: Compares the mean squared error (MSE) of the original and pruned "
                "networks using the same data. A positive error increase means worse performance. "
                "Evaluation on training data is no guarantee for new inputs.\n\n"
                "Auto-Prune: Searches for a threshold within the selected error limit. If no "
                "connection can be removed within that limit, it reports that no useful pruning "
                "is possible.\n\n"
                "With pruning enabled, export warns for a yellow rating and is blocked for a red rating."
            )
        paragraphs = []
        for paragraph in text.split("\n\n"):
            heading, separator, explanation = paragraph.partition("\n")
            if separator:
                paragraphs.append(f"<p><b>{escape(heading)}</b><br>{escape(explanation)}</p>")
            else:
                paragraphs.append(f"<p>{escape(paragraph)}</p>")
        show_yellow_information_dialog(
            self, title, "".join(paragraphs), "Schließen" if self.german else "Close",
            scrollable=True, rich_text=True
        )
