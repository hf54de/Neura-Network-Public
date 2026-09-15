"""Bounded, cancellable search for a tested export-only pruning threshold."""
import math
import time
from decimal import Decimal, ROUND_CEILING

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDoubleSpinBox


def search_threshold(snapshot, limit, maximum=1000000.0):
    if not math.isfinite(limit) or limit < 0:
        raise ValueError("Invalid error limit")
    scale = 10 ** 9
    maximum_tick = int(maximum * scale)
    weights = [abs(weight) for _, _, _, edges in snapshot.nodes for _, weight in edges]
    if not all(math.isfinite(w) for w in weights):
        raise ValueError("Non-finite weight")
    # Export controls support nine decimals. Use the first representable threshold
    # that removes each weight; never round a candidate across a pruning boundary.
    boundaries = sorted({int((Decimal(str(w)) * scale).to_integral_value(rounding=ROUND_CEILING))
                         for w in weights if w <= maximum})

    def useful_result(tick, quality):
        threshold = tick / scale
        if not any(weight <= threshold for weight in weights):
            return None
        return dict(threshold=threshold, quality=quality)

    def evaluate(tick):
        job = snapshot.compare(tick / scale)
        while True:
            try:
                next(job)
                yield tick / scale
            except StopIteration as done:
                r = done.value
                if r["original"] == 0:
                    allowed = r["pruned"] == 0
                else:
                    allowed = r["percent"] is not None and math.isfinite(r["percent"]) and r["percent"] <= limit
                return allowed, r

    allowed, result = yield from evaluate(0)
    if not allowed:
        return None
    low = 0
    step = 10 ** 7  # 0.01; skip steps that remove no additional connections.
    coarse = sorted({min(maximum_tick, ((tick + step - 1) // step) * step)
                     for tick in boundaries if tick > 0})
    for high in coarse:
        allowed, candidate = yield from evaluate(high)
        if allowed:
            low, result = high, candidate
            continue
        # Scan the actual changes in ascending order; do not assume monotonic MSE.
        for tick in boundaries:
            if not low < tick <= high:
                continue
            allowed, candidate = yield from evaluate(tick)
            if not allowed:
                final_tick = tick - 1
                allowed, candidate = yield from evaluate(final_tick)
                if not allowed:
                    return useful_result(low, result)
                return useful_result(final_tick, candidate)
            low, result = tick, candidate
        return useful_result(low, result)
    return useful_result(low, result)


class AutoPruneDialog(QDialog):
    def __init__(self, snapshot, german=True, parent=None):
        super().__init__(parent)
        self.snapshot, self.german = snapshot, german
        self.result = None
        self.job = None
        self.setWindowTitle("Auto-Prune")
        self.layout_timer = QTimer(self)
        self.layout_timer.setSingleShot(True)
        self.layout_timer.timeout.connect(self.fit_text)
        layout = QVBoxLayout(self)
        hint = QLabel(self.text(
            "Sucht ab 0 in 0,01-Schritten bis zum ersten gefundenen Grenzübertritt "
            "und verfeinert dort die Suche. Gleiche Netze werden übersprungen. "
            "Bewertung anhand der Trainingsdaten; keine Garantie für neue Eingaben. "
            "Bei ursprünglichem MSE = 0 ist nur MSE = 0 zulässig.",
            "Searches from 0 in 0.01 steps to the first detected limit crossing, then refines "
            "that interval. Identical networks are skipped. Uses training data, without a "
            "guarantee for new inputs. An original MSE of zero permits only MSE = 0.",
        ), self)
        hint.setWordWrap(True)
        hint.setMinimumWidth(420)
        self.hint = hint
        layout.addWidget(hint)
        row = QHBoxLayout()
        row.addWidget(QLabel(self.text("Maximaler Fehleranstieg:", "Maximum error increase:")))
        self.limit = QDoubleSpinBox(self)
        self.limit.setRange(0, 1000000)
        self.limit.setDecimals(2)
        self.limit.setValue(1)
        self.limit.setSuffix(" %")
        row.addWidget(self.limit)
        layout.addLayout(row)
        self.status = QLabel(self.text("Bereit · Trainingsdaten", "Ready · Training data"), self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.start = QPushButton(self.text("Starten", "Start"), self)
        self.start.setAutoDefault(False)
        self.start.clicked.connect(self.begin)
        buttons.addWidget(self.start)
        self.cancel = QPushButton(self.text("Abbrechen", "Cancel"), self)
        self.cancel.clicked.connect(self.reject)
        buttons.addWidget(self.cancel)
        layout.addLayout(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)

    def fit_text(self):
        """Reserve each wrapped label's actual height at the current dialog width."""
        self.layout().activate()
        for label in (self.hint, self.status):
            bounds = label.fontMetrics().boundingRect(
                0, 0, label.contentsRect().width(), 100000,
                Qt.TextFlag.TextWordWrap, label.text(),
            )
            label.setMinimumHeight(bounds.height() + 4)
        self.layout().invalidate()
        self.layout().activate()
        self.setMinimumHeight(self.layout().minimumSize().height())

    def showEvent(self, event):
        super().showEvent(event)
        self.layout_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout_timer.start(0)

    def set_status(self, text):
        self.status.setText(text)
        self.layout_timer.start(0)

    def text(self, de, en):
        return de if self.german else en

    def begin(self):
        self.result = None
        self.job = search_threshold(self.snapshot, self.limit.value())
        self.limit.setEnabled(False)
        self.start.setEnabled(False)
        self.timer.start(0)

    def advance(self):
        deadline = time.monotonic() + 0.008
        try:
            while time.monotonic() < deadline:
                threshold = next(self.job)
                value = f"{threshold:.9f}".rstrip("0").rstrip(".")
                if self.german:
                    value = value.replace(".", ",")
                self.set_status(self.text("Auto-Prune prüft ", "Auto-Prune checking ") + value + " …")
        except StopIteration as done:
            self.timer.stop()
            self.job = None
            self.result = done.value
            if self.result is not None:
                self.accept()
            else:
                self.set_status(self.text(
                    "Kein sinnvolles Pruning möglich.\n"
                    "Keine Verbindung kann innerhalb der gewählten Fehlergrenze entfernt werden. "
                    "Die bisherigen Einstellungen bleiben unverändert.",
                    "No useful pruning possible.\n"
                    "No connection can be removed within the selected error limit. "
                    "The existing settings remain unchanged.",
                ))
                self.start.setEnabled(True)
                self.limit.setEnabled(True)
        except (ValueError, TypeError, IndexError, KeyError, OverflowError) as error:
            self.timer.stop()
            self.job = None
            self.set_status(self.text("Prüfung fehlgeschlagen: ", "Check failed: ") + str(error))
            self.start.setEnabled(True)
            self.limit.setEnabled(True)

    def done(self, result):
        self.timer.stop()
        self.job = None
        super().done(result)


def run_auto_prune(settings, quality):
    if quality.snapshot is None:
        return
    dialog = AutoPruneDialog(quality.snapshot, settings.german, settings)
    if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result is not None:
        settings.pruning_threshold.input_timer.stop()
        options = {**settings.export_options(), "pruning_enabled": True,
                   "pruning_threshold": dialog.result["threshold"]}
        settings.set_export_options(options)
        settings.optionsChanged.emit(options)
