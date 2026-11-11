"""Structured project training protocol, independent of deletable training history."""
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
    """Structured, append-only facts; only entire blocks may be removed by the user."""
    def __init__(self, language, path=None):
        self.language = language
        self.path = Path(path) if path else None
        self.document = None
        self.baseline = None
        self.dirty = False

    def ensure_loaded(self):
        if self.document is not None:
            return
        data = {"version": 1, "last_run_id": 0, "blocks": []}
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(data,dict) or data.get("version") != 1
                    or not isinstance(data.get("blocks"),list)
                    or not isinstance(data.get("last_run_id"),int)):
                raise ValueError(self.language.text("protocol.table.invalid"))
            ids = set()
            for block in data["blocks"]:
                if (not isinstance(block,dict) or not isinstance(block.get("id"),str)
                        or block["id"] in ids or not isinstance(block.get("events"),list)
                        or not isinstance(block.get("title"),str)
                        or not isinstance(block.get("created"),str)
                        or (block.get("parameters") is not None and not isinstance(block["parameters"],dict))
                        or not isinstance(block.get("rows",[]),list)
                        or any(not isinstance(row,list) or len(row)!=2 for row in block.get("rows",[]))
                        or (block.get("result") is not None and not isinstance(block["result"],dict))
                        or any(not isinstance(e,dict) or not isinstance(e.get("time"),str)
                               or not isinstance(e.get("title"),str) or not isinstance(e.get("rows",[]),list)
                               or any(not isinstance(row,list) or len(row)!=2 for row in e.get("rows",[]))
                               for e in block["events"])):
                    raise ValueError(self.language.text("protocol.table.invalid"))
                ids.add(block["id"])
        self.document = data
        # Earlier table versions emitted a separate note immediately before a run.
        # Move only an adjacent note with the same timestamp; preserve ambiguous data.
        blocks = data["blocks"]
        retained = []
        for index,block in enumerate(blocks):
            following = blocks[index+1] if index+1<len(blocks) else None
            if (block.get("run_id") is None
                    and block["title"] in ("Trainingsparameter ge\u00e4ndert","Training parameters changed")
                    and following and following.get("run_id") is not None
                    and following.get("parameters") and block["created"] == following["created"]
                    and not block.get("events") and not block.get("result")):
                following["events"].insert(0,{"time":block["created"],"kind":"parameters",
                    "title":block["title"],"rows":block.get("rows",[])})
                self.dirty = True
            else:
                retained.append(block)
        data["blocks"] = retained
        for block in retained:
            events = block["events"]
            cleaned = [e for e in events if e.get("kind") not in ("started","resumed","result","parameters")]
            if cleaned != events:
                block["events"] = cleaned
                self.dirty = True

    @property
    def blocks(self):
        self.ensure_loaded()
        return self.document["blocks"]

    @staticmethod
    def stamp():
        return datetime.now().isoformat(timespec="seconds")

    def new_block(self, title, run_id=None):
        from uuid import uuid4
        block = {"id": str(uuid4()), "run_id": run_id, "title": title,
                 "created": self.stamp(), "parameters": None, "rows": [],
                 "result": None, "events": [], "deleted": False}
        self.blocks.append(block)
        if run_id is not None:
            self.document["last_run_id"] = max(self.document["last_run_id"],run_id)
        self.dirty = True
        return block

    @staticmethod
    def rows(lines):
        return [list(line.split(":",1)) if ":" in line else [str(line),""] for line in lines]

    def add(self, title, lines, flush=True, highlighted=False):
        block = self.new_block(title)
        block["rows"] = self.rows(lines)
        if flush:self.flush()

    def run_event(self, run_id, kind, title, lines=(), parameters=None, result=None):
        from copy import deepcopy
        block = next((b for b in self.blocks if b.get("run_id")==run_id),None)
        if block is None:
            block = self.new_block(self.language.text("history.chart.run",run=run_id),run_id)
        if parameters is not None and block["parameters"] is None:
            block["parameters"] = deepcopy(parameters)
            block["rows"] = self.rows(lines)
        event = {"time":self.stamp(),"kind":kind,"title":title,
                 "rows":self.rows(lines) if parameters is None else []}
        if kind not in ("started","resumed","result"):
            block["events"].append(event)
        if kind=="deleted":block["deleted"]=True
        if result is not None:block["result"]=deepcopy(result)
        self.dirty=True
        self.flush()

    def flush(self, path=None):
        self.ensure_loaded()
        target=Path(path) if path else self.path
        if target is None:return
        if target != self.path and self.path and not self.path.exists() and target.exists():
            self.path = target  # The project directory was renamed.
        content=json.dumps(self.document,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
        if target != self.path and target.exists():
            # A renamed project directory may already contain this same journal.
            if target.read_text(encoding="utf-8") != content:
                raise OSError(self.language.text("protocol.destination_exists"))
        if self.dirty or target != self.path or not target.exists():
            write_text_atomic(target,content)
        self.path=target
        self.dirty=False

    def reconstruct_runs(self, history):
        from copy import deepcopy
        self.ensure_loaded()
        old,old_dirty=deepcopy(self.document),self.dirty
        existing={b.get("run_id") for b in self.blocks}
        count=0
        try:
            for run in history:
                run_id=run.get("run_id")
                if type(run_id) is not int or run_id<1 or run_id in existing:continue
                block=self.new_block(self.language.text("history.chart.run",run=run_id),run_id)
                block["reconstructed"]=True
                block["created"]=str(run.get("timestamp") or "")
                keys=("solver","weight_initialization","bias_initialization","learning_rate","momentum",
                      "error_limit","maximum_epochs","training_target_mode","training_section_epochs")
                parameters={key:deepcopy(run[key]) for key in keys if key in run}
                if "initialized" in run:parameters["initialize_network"]=bool(run["initialized"])
                if "training_target_mode" not in parameters and run.get("stop_at_error_limit"):
                    parameters["training_target_mode"]="limit"
                block["parameters"]=parameters or None
                if run.get("parent_run_id") is not None:
                    block["rows"]=[[self.language.text("protocol.parent_run_suffix",run=run["parent_run_id"]),""]]
                if "requested_epochs" in run:
                    block["rows"].append([self.language.text("protocol.rebuild.requested"),str(run["requested_epochs"])])
                result={"status":str(run.get("status_text") or self.language.text("protocol.rebuild.unknown"))}
                for source,target in (("completed_epochs","epochs"),("elapsed_seconds","elapsed_seconds"),
                                      ("end_error","mse"),("maximum_absolute_error","maximum_error")):
                    if source in run:result[target]=run[source]
                block["result"]=result
                existing.add(run_id);count+=1
            if count:self.flush()
        except (OSError,ValueError,TypeError):
            self.document,self.dirty=old,old_dirty
            raise
        return count

    def delete_block(self, block_id):
        from copy import deepcopy
        self.ensure_loaded()
        old=self.document
        old_dirty=self.dirty
        candidate=deepcopy(old)
        candidate["blocks"]=[b for b in candidate["blocks"] if b["id"]!=block_id]
        self.document=candidate
        self.dirty=True
        try:self.flush()
        except (OSError,ValueError):
            self.document=old
            self.dirty=old_dirty
            raise

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
            if section == "parameters":
                continue  # A run documents its actual starting parameters directly.
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
        path = Path(self.current_project_path).parent / "trainingsprotokoll.json" if self.current_project_path else None
        self.training_protocol = TrainingProtocol(self.language,path)
        self._protocol_runs = list(self.training_history)
        try:
            self.training_protocol.ensure_loaded()
            self.last_training_run_id = max(getattr(self,"last_training_run_id",0),
                self.training_protocol.document["last_run_id"])
            self.training_protocol.baseline = self.protocol_state()
        except (OSError,UnicodeError,ValueError) as error:
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
            self.protocol_target_changes(journal)
            journal.observe(self.protocol_state())
            journal.flush()
            self._protocol_error_shown = False
        except (OSError, UnicodeError, ValueError) as error:
            self.protocol_error(error)

    def protocol_target_changes(self, journal):
        dialog = getattr(self,"training_dialog",None)
        run_id = getattr(dialog,"current_run_id",None) if dialog is not None else getattr(self,"active_training_run_id",None)
        block = next((b for b in journal.blocks if b.get("run_id")==run_id),None)
        if block is None or not block.get("parameters") or block.get("deleted"):
            return
        keys = ("training_target_mode","training_section_epochs","maximum_epochs","error_limit")
        previous = block.get("target_state",block["parameters"])
        current = {key:self.training_settings.get(key) for key in keys}
        changes = []
        t=self.language.text
        for key in keys:
            if previous.get(key) == current[key]:continue
            def display(value, state):
                if key == "training_target_mode":
                    return t("training.view.target_"+str(value),epochs=state.get("training_section_epochs"))
                return journal.format_value(value)
            changes.append(t("protocol.param."+key)+": "+display(previous.get(key),previous)
                           +" \u2192 "+display(current[key],current))
        if changes:
            block["target_state"]=current
            journal.run_event(run_id,"target",t("protocol.table.target_changed"),changes)

    def protocol_add(self, title, lines, highlighted=False):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        try:
            self.training_protocol.add(title, lines, highlighted=highlighted)
        except (OSError, UnicodeError, ValueError) as error:
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
        t = self.language.text
        parent_run = getattr(dialog,"current_run_parent_id",None)
        parameters = dict(self.training_settings,initialize_network=bool(dialog.current_run_initialized))
        lines = ([t("protocol.parent_run_suffix",run=parent_run)] if parent_run is not None else [])
        lines += dialog.workload_label.text().splitlines()
        try:
            self.training_protocol.run_event(dialog.current_run_id,
                "resumed" if continuation else "started",
                t("protocol.table.resumed") if continuation else t("protocol.new_run",run=dialog.current_run_id),
                lines,parameters=parameters)
        except (OSError,UnicodeError,ValueError) as error:self.protocol_error(error)

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
            result = {"status":status,"epochs":epochs,"elapsed_seconds":elapsed,
                      "mse":float(entry["end_error"]),"maximum_error":float(entry["maximum_absolute_error"])}
            journal.run_event(entry["run_id"],"result",status,result_lines,result=result)
        except (OSError,UnicodeError,ValueError) as error:self.protocol_error(error)

    def protocol_run_loaded(self, run_id):
        if getattr(self, "training_protocol", None) is None:
            self.initialize_training_protocol()
        # Restoring stored parameters is one load event, not a manual edit.
        if self.training_protocol.baseline is not None:
            self.training_protocol.baseline["parameters"] = self.protocol_state()["parameters"]
        block=next((b for b in self.training_protocol.blocks if b.get("run_id")==run_id),None)
        if block is not None:
            block["target_state"]={key:self.training_settings.get(key) for key in
                ("training_target_mode","training_section_epochs","maximum_epochs","error_limit")}
        try:self.training_protocol.run_event(run_id,"loaded",self.language.text("protocol.loaded",run=run_id))
        except (OSError,UnicodeError,ValueError) as error:self.protocol_error(error)

    def protocol_deleted_runs(self, before, after):
        self._protocol_runs = list(after)
        remaining = {r.get("run_id") for r in after}
        for run in before:
            if run.get("run_id") not in remaining:
                if getattr(self,"training_protocol",None) is None:self.initialize_training_protocol()
                try:self.training_protocol.run_event(run["run_id"],"deleted",self.language.text("protocol.deleted",run=run["run_id"]))
                except (OSError,UnicodeError,ValueError) as error:self.protocol_error(error)

    def open_training_protocol(self, *, training_dialog=None):
        if getattr(self,"training_protocol",None) is None:self.initialize_training_protocol()
        self.protocol_checkpoint()
        try:
            self.training_protocol.flush()
            if self.current_project_path:
                (Path(self.current_project_path).parent / "trainingsprotokoll.txt").unlink(missing_ok=True)
            from protocoltable import ProtocolTableDialog
            dialog=ProtocolTableDialog(self.training_protocol,self.language,self,training_dialog)
            dialog.exec()
            dialog.deleteLater()
        except (OSError,UnicodeError,ValueError) as error:self.protocol_error(error)
