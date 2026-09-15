"""Non-mutating pruning comparison, evaluated in small GUI event-loop batches."""
import math
import time
from copy import deepcopy

from PySide6.QtCore import QTimer, QObject, QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QDialog,
    QDoubleSpinBox, QFormLayout, QMessageBox, QMenu,
)
from activationfunctions import ActivationFunctions
from neurontype import NeuronType
from trainingdataio import TrainingDataIO


class ExportCopyGuard(QObject):
    """Route keyboard/context-menu copying through the same checked transfer."""
    def __init__(self, widget, callback, active=lambda: True):
        super().__init__(widget)
        self.callback = callback
        self.active = active
        widget.installEventFilter(self)
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(self.context_menu)

    def eventFilter(self, watched, event):
        if self.active() and event.type() == QEvent.Type.KeyPress and event.matches(QKeySequence.StandardKey.Copy):
            self.callback()
            return True
        return False

    def context_menu(self, position):
        if not self.active() and hasattr(self.parent(), "createStandardContextMenu"):
            menu = self.parent().createStandardContextMenu()
            menu.exec(self.parent().mapToGlobal(position))
            return
        menu = QMenu(self.parent())
        action = menu.addAction("Copy / Kopieren")
        action.triggered.connect(self.callback)
        menu.exec(self.parent().mapToGlobal(position))


class PruningQualitySnapshot:
    def __init__(self, network, records, inputs, outputs):
        self.records = tuple(tuple(row) for row in records)
        self.inputs = tuple((m["neuron"].id, m["column_index"],
                             deepcopy(m.get("calibration"))) for m in inputs)
        self.outputs = tuple((m["neuron"].id, m["column_index"],
                              deepcopy(m.get("calibration"))) for m in outputs)
        self.nodes = tuple(
            (n.id, float(n.bias), n.activation_function,
             tuple((c.source_neuron.id, float(c.weight))
                   for c in sorted(n.incoming_connections, key=lambda c: c.id)))
            for n in network.get_topological_order() if n.neuron_type != NeuronType.INPUT
        )

    def compare(self, threshold):
        """Yield progress per record and finally return MSE in external output units."""
        if not self.records or not self.outputs:
            raise ValueError("No data with targets")
        totals = [0.0, 0.0]
        count = 0
        for record in self.records:
            initial = {nid: TrainingDataIO.scale_value(record[col], calibration)
                       for nid, col, calibration in self.inputs}
            if not all(math.isfinite(v) for v in initial.values()):
                raise ValueError("Non-finite input")
            for mode in (0, 1):
                values = dict(initial)
                for nid, bias, activation, incoming in self.nodes:
                    summed = sum(values[source] * weight for source, weight in incoming
                                 if not mode or abs(weight) > threshold) + bias
                    if not math.isfinite(summed):
                        raise ValueError("Non-finite neuron value")
                    values[nid] = ActivationFunctions.apply(activation, summed)
                for nid, col, calibration in self.outputs:
                    actual = TrainingDataIO.unscale_value(values[nid], calibration)
                    squared = (actual - record[col]) ** 2
                    if not math.isfinite(squared):
                        raise ValueError("Non-finite error")
                    totals[mode] += squared
            count += len(self.outputs)
            yield None
        original, pruned = (total / count for total in totals)
        if not all(math.isfinite(v) for v in (original, pruned)):
            raise ValueError("Non-finite MSE")
        percent = 100 * (pruned - original) / original if original > 0 else None
        return dict(original=original, pruned=pruned, percent=percent,
                    records=len(self.records), outputs=len(self.outputs))


class PruningQualityPanel(QWidget):
    previewChanged = Signal()

    def __init__(self, snapshot=None, german=True, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.german = german
        self.result = None
        self.low_limit, self.high_limit = 1.0, 5.0
        self.details = ""
        self.job = None
        self.timer = QTimer(self)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.advance)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        row.addWidget(self.label, 1)
        self.info = QPushButton("i", self)
        self.info.setFixedSize(23, 23)
        self.info.setStyleSheet(
            "QPushButton { border: 1px solid #333333; border-radius: 4px; background: #ffffff; }"
            "QPushButton:hover { background: #f0f2f4; }"
        )
        self.info.setAutoDefault(False)
        self.info.clicked.connect(self.show_details)
        row.addWidget(self.info)
        self.refresh({})

    def connect_auto_prune(self, settings):
        from plcautoprune import run_auto_prune
        settings.auto_prune_button.setEnabled(self.snapshot is not None)
        settings.auto_prune_button.clicked.connect(lambda: run_auto_prune(settings, self))

    def text(self, de, en):
        return de if self.german else en

    def refresh(self, options):
        self.checked_options = dict(options)
        self.timer.stop()
        self.job = None
        self.result = None
        self.label.setStyleSheet("")
        if not options.get("pruning_enabled"):
            message = self.text("Qualitätsvergleich: Pruning ausgeschaltet",
                                "Quality comparison: pruning disabled")
        elif self.snapshot is None:
            message = self.text("Qualität nicht geprüft · Keine Daten mit Sollwerten",
                                "Quality not checked · No data with targets")
        else:
            message = self.text("Qualität wird geprüft … · Trainingsdaten",
                                "Checking quality … · Training data")
            self.job = self.snapshot.compare(float(options.get("pruning_threshold", 0.001)))
            self.timer.start()
        self.label.setText(message)
        self.details = message
        self.previewChanged.emit()

    def export_comment(self, settings, preview=False):
        """Authorize one transfer and return its ST comment; None blocks transfer."""
        if not settings.pruning.isChecked():
            return ""
        if preview and (self.result is None or self.job is not None):
            status = self.text("Qualität wird geprüft" if self.job is not None else "Qualität nicht geprüft",
                               "Checking quality" if self.job is not None else "Quality not checked")
            return "(*\nPruning: " + self.text("aktiviert", "enabled") + "\n" + self.text("Schwellwert", "Threshold") + f": {settings.pruning_threshold.value():.9g}\n" + status + "\n*)\n"
        if not preview and not settings.pruning_threshold.hasAcceptableInput():
            QMessageBox.warning(self, "Pruning", self.text(
                "Export blockiert: Bitte einen gültigen Schwellwert eingeben.",
                "Export blocked: enter a valid threshold.",
            ))
            return None
        if not preview:
            settings.pruning_threshold.commit_input()
        title = self.text("Pruning-Exportprüfung", "Pruning export check")
        if not preview and (self.result is None or self.job is not None
                or self.checked_options != settings.export_options()):
            QMessageBox.warning(self, title, self.text(
                "Export blockiert: Die Qualitätsprüfung fehlt oder läuft noch. Bitte Prüfung abwarten.",
                "Export blocked: quality check missing or still running. Please wait for the check.",
            ))
            return None
        r = self.result
        percent = r["percent"]
        level = (0 if r["pruned"] == 0 else 2) if percent is None else (
            2 if not math.isfinite(percent) else
            0 if percent <= self.low_limit else 1 if percent <= self.high_limit else 2
        )
        if level == 2 and not preview:
            QMessageBox.warning(self, title, self.text(
                "Export blockiert: Fehleranstieg zu hoch. Schwellwert reduzieren oder Pruning ausschalten.",
                "Export blocked: error increase too high. Reduce the threshold or disable pruning.",
            ))
            return None
        if level == 1 and not preview:
            box = QMessageBox(self)
            box.setWindowTitle(title)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(self.text(
                f"GELB: Fehleranstieg {percent:+.2f} % auf Trainingsdaten. Trotzdem exportieren?",
                f"YELLOW: error increase {percent:+.2f}% on training data. Export anyway?",
            ))
            proceed = box.addButton(self.text("Trotzdem exportieren", "Export anyway"), QMessageBox.ButtonRole.AcceptRole)
            cancel = box.addButton(self.text("Abbrechen", "Cancel"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not proceed:
                return None
        rating = self.text("GELB – Warnung, Export ausdrücklich bestätigt", "YELLOW – warning, export explicitly confirmed") if level else self.text("GRÜN", "GREEN")
        if preview and level == 1:
            rating = self.text("GELB – Warnung, Exportbestätigung erforderlich", "YELLOW – warning, export confirmation required")
        elif preview and level == 2:
            rating = self.text("ROT – Export blockiert", "RED – export blocked")
        change = (self.text("MSE-Änderung", "MSE change") + f": {r['pruned'] - r['original']:+.9g}"
                  if percent is None else
                  self.text("Fehlerreduktion", "Error reduction") + f": {abs(percent):.2f} %"
                  if percent < 0 else self.text("Fehleranstieg", "Error increase") + f": {percent:+.2f} %")
        return ("(*\nPruning: " + self.text("aktiviert", "enabled") + "\n"
                + self.text("Schwellwert", "Threshold") + f": {settings.pruning_threshold.value():.9g}\n"
                + self.text("Qualitätsprüfung: Trainingsdaten", "Quality check: training data") + "\n"
                + f"MSE before: {r['original']:.9g} | MSE after: {r['pruned']:.9g}\n"
                + change + "\n" + self.text("Bewertung", "Rating") + ": " + rating + "\n"
                + self.text("Ampelgrenzen", "Rating limits") + f": {self.low_limit:g} % / {self.high_limit:g} %\n*)\n")

    def advance(self):
        deadline = time.monotonic() + 0.008
        try:
            while time.monotonic() < deadline:
                next(self.job)
        except StopIteration as finished:
            self.timer.stop()
            self.job = None
            self.result = finished.value
            self.display_result()
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
            self.timer.stop()
            self.job = None
            self.details = self.text("Qualität nicht geprüft: ", "Quality not checked: ") + str(error)
            self.label.setText(self.text("Qualität nicht geprüft · Daten/Berechnung prüfen",
                                         "Quality not checked · Check data/calculation"))
            self.previewChanged.emit()

    def display_result(self):
        r = self.result
        percent = r["percent"]
        def num(value, spec=".2f"):
            result = format(value, spec)
            return result.replace(".", ",") if self.german else result
        if percent is None or not math.isfinite(percent):
            message = self.text("MSE-Änderung: ", "MSE change: ") + num(r["pruned"] - r["original"], "+.6g")
            color = "#21833b" if r["pruned"] == 0 else "#be2525"
        else:
            level = 0 if percent <= self.low_limit else 1 if percent <= self.high_limit else 2
            color = ("#21833b", "#a36b00", "#be2525")[level]
            message = self.text("● Fehleranstieg: ", "● Error increase: ") + num(percent, "+.2f") + " %"
        self.label.setText(message + self.text(" · Trainingsdaten", " · Training data"))
        self.label.setStyleSheet(f"color: {color};")
        self.details = self.text(
            f"MSE vorher: {num(r['original'], '.9g')}\nMSE nachher: {num(r['pruned'], '.9g')}\n"
            f"Trainingsdatensätze: {r['records']} · Ausgänge: {r['outputs']}\n\n"
            "MSE über alle Datensätze und Ausgänge nach Rückskalierung, vor binärer Schwellwertbildung. "
            "Bei verschiedenen Einheiten können große Zahlenbereiche den Gesamtfehler dominieren.\n"
            "Fehleranstieg = (MSE nachher − MSE vorher) / MSE vorher × 100. "
            "Bei MSE vorher = 0 wird die absolute Änderung angezeigt.\n"
            "Trainingsdaten bewerten bekannte Fälle; keine Aussagegarantie für neue Eingaben. "
            "Verglichen wird das mathematische Netz, nicht die Rundung oder Ausführung auf der SPS.\n\n"
            "Ampel: Grün bis zur ersten Grenze, Gelb bis zur zweiten, darüber Rot. "
            "Die Grenzen sind Orientierungshilfen, keine Freigabe für den Einsatz.",
            f"MSE before: {num(r['original'], '.9g')}\nMSE after: {num(r['pruned'], '.9g')}\n"
            f"Training records: {r['records']} · Outputs: {r['outputs']}\n\n"
            "MSE across all records and outputs after inverse scaling, before binary thresholding. "
            "Large numeric ranges can dominate when output units differ.\n"
            "Error increase = (MSE after − MSE before) / MSE before × 100. "
            "An original MSE of zero uses absolute change.\n"
            "Training data covers known cases, not guaranteed performance on new inputs. "
            "This compares the mathematical model, not PLC rounding or execution.\n\n"
            "Green up to the first limit, yellow up to the second, red above. "
            "Limits are guidance, not approval for use.",
        )
        self.previewChanged.emit()

    def show_details(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.text("Pruning-Qualitätsvergleich", "Pruning quality comparison"))
        layout = QVBoxLayout(dialog)
        label = QLabel(self.details, dialog)
        label.setWordWrap(True)
        label.setMinimumWidth(450)
        layout.addWidget(label)
        form = QFormLayout()
        low, high = QDoubleSpinBox(dialog), QDoubleSpinBox(dialog)
        for field, value in ((low, self.low_limit), (high, self.high_limit)):
            field.setRange(0, 1000000)
            field.setSuffix(" %")
            field.setValue(value)
        low.valueChanged.connect(lambda v: high.setMinimum(v))
        high.valueChanged.connect(lambda v: low.setMaximum(v))
        low.setMaximum(high.value())
        high.setMinimum(low.value())
        form.addRow(self.text("Grün bis:", "Green up to:"), low)
        form.addRow(self.text("Gelb bis:", "Yellow up to:"), high)
        layout.addLayout(form)
        close = QPushButton(self.text("Übernehmen / Schließen", "Apply / Close"), dialog)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.low_limit, self.high_limit = low.value(), high.value()
            if self.result:
                self.display_result()
