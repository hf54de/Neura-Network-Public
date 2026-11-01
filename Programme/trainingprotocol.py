"""Editable project training protocol, independent of deletable training history."""
import json
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox, QMessageBox
from trainingvalidity import digest


def write_text_atomic(path, text):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows may temporarily deny replacement while another process has
        # the file open. Retry briefly; never truncate the existing protocol.
        delays = (0.05, 0.1, 0.2, 0.4)
        for attempt in range(len(delays) + 1):
            try:
                os.replace(temporary, path)
                break
            except OSError as error:
                if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == len(delays):
                    raise
                time.sleep(delays[attempt])
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class TrainingProtocol:
    def __init__(self, language, path=None):
        self.language = language
        self.path = Path(path) if path else None
        self.pending = ""
        self.baseline = None

    def text(self):
        existing = self.path.read_text(encoding="utf-8") if self.path and self.path.exists() else ""
        return existing + self.pending

    def add(self, title, lines, flush=True, highlighted=False):
        stamp = datetime.now().strftime("%d.%m.%Y · %H:%M:%S")
        body = "\n".join(lines)
        separator = ("=" if highlighted else "-") * 56
        self.pending += (separator + "\n" if highlighted else "")
        heading = f"{stamp}\n{title}\n" if highlighted else f"{stamp} — {title}\n"
        self.pending += heading + (body + "\n" if body else "") + separator + "\n\n"
        if flush:
            self.flush()

    def flush(self, path=None):
        target = Path(path) if path else self.path
        if target is None:
            return
        if target != self.path and self.path and not self.path.exists() and target.exists():
            self.path = target  # The project folder was renamed.
        if target != self.path:
            content = self.text()
            if target.exists() and target.read_text(encoding="utf-8") != content:
                raise OSError(self.language.text("protocol.destination_exists"))
            write_text_atomic(target, content)
        elif self.pending:
            write_text_atomic(target, self.text())
        self.path = target
        self.pending = ""

    def replace(self, original, edited):
        if self.text() != original:
            raise OSError(self.language.text("protocol.changed"))
        if self.path:
            write_text_atomic(self.path, edited)
            self.pending = ""
        else:
            self.pending = edited

    def format_value(self, value):
        if value is None:
            return "—"
        if isinstance(value, bool):
            return self.language.text("common.yes" if value else "common.no")
        if isinstance(value, float):
            text = f"{value:.5g}"
            return text.replace(".", ",") if self.language.current_language == "de" else text
        return str(value)

    def observe(self, state):
        old = self.baseline
        self.baseline = state
        t = self.language.text
        if old is None:
            return  # Keep an internal comparison state without writing a baseline.
        for section, values in state.items():
            before = old.get(section, {})
            changes = []
            for key in sorted(before.keys() | values.keys()):
                previous, current = before.get(key), values.get(key)
                if previous == current:
                    continue
                if key == t("protocol.content"):
                    if before.get(t("protocol.records")) == values.get(t("protocol.records")):
                        changes.append(t("protocol.values_changed"))
                elif key == t("protocol.file"):
                    changes.append(t("protocol.file_changed"))
                elif section == "structure" and key == t("protocol.connections"):
                    count = lambda value: 0 if value in (None, "—", "") else len(value.split(", "))
                    changes.append(f"{key}: {count(previous)} → {count(current)}")
                else:
                    changes.append(f"{key}: {self.format_value(previous)} → {self.format_value(current)}")
            if changes:
                if len(changes) > 6:
                    changes = changes[:5] + [t("protocol.more_changes", count=len(changes)-5)]
                self.add(t("protocol.change", section=t("protocol." + section)), changes, flush=False)
        self.flush()


class TrainingProtocolMixin:
    def protocol_state(self):
        t = self.language.text
        net = self.scene.network
        neurons = sorted(net.get_neurons(), key=lambda n: n.id)
        structure = {f"N{n.id} ({n.name})": n.neuron_type.value for n in neurons}
        structure[t("protocol.connections")] = ", ".join(
            f"N{c.source_neuron.id} → N{c.target_neuron.id}" for c in sorted(net.get_connections(), key=lambda c: c.id)) or "—"
        activations = {f"N{n.id} ({n.name})": n.activation_function for n in neurons
                       if str(n.neuron_type.value).lower() != "input"}
        doc = self.training_data_manager.document
        data = {t("protocol.file"): str(self.training_data_manager.file_path or "—"),
                t("protocol.records"): len(doc.get("records", [])) if doc else 0}
        if doc:
            data[t("protocol.content")] = digest(doc.get("records", []))
            for i, column in enumerate(doc.get("columns", []), 1):
                key = t("protocol.column", number=i, name=column.get("name", ""))
                for field, label in (("role", "role"), ("data_type", "type"),
                                     ("mapped_neuron_id", "neuron"), ("unit", "unit")):
                    data[key + " / " + t("protocol." + label)] = column.get(field, "—")
                calibration = column.get("calibration", {})
                mode = calibration.get("mode", "none")
                data[key + " / " + t("protocol.method")] = t("data.calibration." + mode)
                for field, label in (("source_min", "minimum"), ("source_max", "maximum"),
                                     ("mean", "mean"), ("stddev", "stddev")):
                    data[key + " / " + t("protocol." + label)] = calibration.get(field, "—")
        settings = {t("protocol.param." + key): self.training_settings.get(key) for key in
                    ("solver", "learning_rate", "momentum", "error_limit", "maximum_epochs", "initialize_network",
                     "weight_initialization", "bias_initialization", "training_section_epochs", "training_target_mode")}
        settings[t("protocol.param.solver")] = t("adam.solver." + self.training_settings.get("solver", "sgd"))
        if self.training_settings.get("solver", "sgd") == "adam":
            settings.pop(t("protocol.param.momentum"), None)
        return {"structure": structure, "activations": activations, "data": data, "parameters": settings}

    def initialize_training_protocol(self):
        path = Path(self.current_project_path).parent / "trainingsprotokoll.txt" if self.current_project_path else None
        self.training_protocol = TrainingProtocol(self.language, path)
        self._protocol_runs = list(self.training_history)
        try:
            content = self.training_protocol.text()
            numbers = [int(n) for n in re.findall(r"(?:Lauf|Run) (\d+)", content)]
            self.last_training_run_id = max(getattr(self, "last_training_run_id", 0), *numbers, 0)
            state = self.protocol_state()
            if content:
                self.training_protocol.baseline = state
            else:
                self.training_protocol.observe(state)
        except (OSError, UnicodeError) as error:
            self.protocol_error(error)

    def protocol_error(self, error):
        self.statusBar().showMessage(self.language.text("protocol.error", error=str(error)), 15000)
        if not getattr(self, "_protocol_error_shown", False):
            self._protocol_error_shown = True
            QMessageBox.warning(self, self.language.text("protocol.title"), self.language.text("protocol.error", error=str(error)))

    def protocol_checkpoint(self):
        if getattr(self, "_history_restoring", False):
            return
        journal = getattr(self, "training_protocol", None)
        if journal is None:
            return
        try:
            self.protocol_deleted_runs(getattr(self, "_protocol_runs", []), self.training_history)
            journal.observe(self.protocol_state())
            journal.flush()
            self._protocol_error_shown = False
        except (OSError, UnicodeError) as error:
            self.protocol_error(error)

    def protocol_add(self, title, lines, highlighted=False):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        try:
            self.training_protocol.add(title, lines, highlighted=highlighted)
        except (OSError, UnicodeError) as error:
            self.protocol_error(error)

    def reserve_training_run_id(self):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        self.last_training_run_id = max(getattr(self, "last_training_run_id", 0),
            max((r.get("run_id", 0) for r in self.training_history), default=0)) + 1
        self.project_modified = True
        return self.last_training_run_id

    def protocol_training_started(self, dialog, continuation):
        self.training_settings = dialog.get_training_settings()
        self.protocol_checkpoint()
        if not continuation:
            t = self.language.text
            settings = self.training_settings
            fmt = self.training_protocol.format_value
            weights = settings.get("weight_initialization", "auto")
            weights = t("training.initialization.auto_short") if weights == "auto" else {
                "xavier": "Xavier/Glorot", "he": "He", "zero": "0"}.get(weights, weights)
            bias = {"xavier": "Xavier/Glorot", "zero": "0"}.get(
                settings.get("bias_initialization"), settings.get("bias_initialization"))
            target = settings.get("training_target_mode", "one")
            lines = [
                t("training.initialization.weights") + " " + weights,
                t("training.initialization.bias") + " " + str(bias),
                t("protocol.run_reinitialize") + ": " + fmt(dialog.current_run_initialized),
                t("protocol.param.learning_rate") + ": " + fmt(settings.get("learning_rate")),
                t("protocol.param.momentum") + ": " + fmt(settings.get("momentum")),
                t("protocol.param.error_limit") + ": " + fmt(settings.get("error_limit")),
                t("protocol.param.maximum_epochs") + ": " + fmt(settings.get("maximum_epochs")),
                t("training.view.target_" + target, epochs=settings.get("training_section_epochs")),
            ]
            solver = settings.get("solver", "sgd")
            if solver == "adam":
                lines = [line for line in lines if not line.startswith(t("protocol.param.momentum") + ":")]
            lines = ([t("adam.solver.label") + " " + t("adam.solver." + solver)]
                     + dialog.workload_label.text().splitlines() + lines)
            title = t("protocol.new_run", run=dialog.current_run_id)
            parent_run = getattr(dialog, "current_run_parent_id", None)
            if parent_run is not None:
                lines.insert(0, t("protocol.parent_run_suffix", run=parent_run))
            self.protocol_add(title, lines, highlighted=True)

    def protocol_training_result(self, entry):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        journal = self.training_protocol
        t = self.language.text
        fmt = journal.format_value
        if entry.get("training_stopped"):
            status = t("protocol.result_stopped")
        elif entry.get("stop_at_error_limit") and entry["end_error"] <= entry["error_limit"]:
            status = t("protocol.result_limit")
        else:
            status = t("protocol.result_epochs_limit")
        elapsed = max(0.0, float(entry.get("elapsed_seconds", 0.0)))
        epochs = int(entry["completed_epochs"])
        epoch_time = fmt(elapsed * 1000.0 / epochs) + " ms" if epochs > 0 else "—"
        result_lines = [t("protocol.result") + ": " + status,
                        t("protocol.result_epochs") + ": " + str(epochs),
                        t("training.result.elapsed") + " " + fmt(elapsed) + " s",
                        t("protocol.result_epoch_time") + ": " + epoch_time,
                        "MSE: " + fmt(entry["end_error"]),
                        t("protocol.result_maximum") + ": " + fmt(entry["maximum_absolute_error"])]
        try:
            original = journal.text()
            # Support both the old single-line heading and the current layout.
            pattern = (r"(?m)^.*(?:NEUER TRAININGSLAUF|NEW TRAINING RUN|"
                       r"TRAININGSERGEBNIS|TRAINING RESULT).* · (?:Lauf|Run) "
                       + str(entry["run_id"]) + r"(?:[^\d].*)?$")
            headings = list(re.finditer(pattern, original))
            if not headings:
                self.protocol_add(t("protocol.result_run", run=entry["run_id"]), result_lines, highlighted=True)
                return
            heading = headings[-1]
            closing = re.search(r"(?m)^={56}\s*$", original[heading.end():])
            if closing is None:
                return  # Preserve a manually restructured section.
            end = heading.end() + closing.start()
            body = original[heading.end():end]
            labels = ("Ergebnis:", "Result:", "Epochen:", "Epochs:", "MSE:",
                      "Zeit seit Start:", "Time since start:", "Elapsed time:",
                      "Zeit / Epoche:", "Time / epoch:",
                      "Maximaler Fehler:", "Maximum error:")
            lines = [line for line in body.splitlines() if not line.startswith(labels + (t("training.result.elapsed"),))]
            body = "\n".join(lines).rstrip() + "\n" + "\n".join(result_lines) + "\n"
            journal.replace(original, original[:heading.end()] + body + original[end:])
        except (OSError, UnicodeError) as error:
            self.protocol_error(error)

    def protocol_run_loaded(self, run_id):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        # Restoring stored parameters is one load event, not a manual edit.
        if self.training_protocol.baseline is not None:
            self.training_protocol.baseline["parameters"] = self.protocol_state()["parameters"]
        self.protocol_add(self.language.text("protocol.loaded", run=run_id), [])

    def protocol_deleted_runs(self, before, after):
        self._protocol_runs = list(after)
        remaining = {r.get("run_id") for r in after}
        for run in before:
            if run.get("run_id") not in remaining:
                self.protocol_add(self.language.text("protocol.deleted", run=run["run_id"]),
                                  [])

    def open_training_protocol(self):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        self.protocol_checkpoint()
        t = self.language.text
        try:
            original = self.training_protocol.text()
        except (OSError, UnicodeError) as error:
            self.protocol_error(error)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(t("protocol.title"))
        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit(original, dialog)
        editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        editor.moveCursor(QTextCursor.MoveOperation.End)
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(t("common.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("common.cancel"))
        layout.addWidget(buttons)
        dialog.ensurePolished()
        editor.ensurePolished()
        metrics = editor.fontMetrics()
        # Legacy entries can contain long single-line headings. They should
        # wrap instead of keeping the compact protocol window unnecessarily wide.
        compact_width = metrics.horizontalAdvance("=" * 56)
        text_width = min(compact_width,
                         max((metrics.horizontalAdvance(line) for line in original.splitlines()),
                             default=compact_width))
        margins = layout.contentsMargins()
        editor_chrome = (2 * editor.frameWidth() + 2 * editor.document().documentMargin()
                         + editor.verticalScrollBar().sizeHint().width() + 2)
        width = max(text_width + editor_chrome, buttons.sizeHint().width())
        width += margins.left() + margins.right()
        available = self.screen().availableGeometry()
        dialog.resize(min(int(width), available.width() - 40), min(650, available.height() - 80))
        def save():
            try:
                self.training_protocol.replace(original, editor.toPlainText())
                self.project_modified = True
                self.update_window_title()
                dialog.accept()
            except (OSError, UnicodeError) as error:
                QMessageBox.warning(dialog, t("protocol.title"), str(error))
        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()
        dialog.deleteLater()
