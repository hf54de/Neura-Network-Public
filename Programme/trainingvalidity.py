"""Prüft die fachliche Gültigkeit gespeicherter Trainingsläufe."""
import hashlib
import json

from trainingdataio import TrainingDataIO


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def data_signature(document):
    if document is None:
        return None
    columns = []
    for column in document["columns"]:
        calibration = TrainingDataIO.normalize_calibration(column.get("calibration"))
        mode = calibration["mode"]
        keys = ("source_min", "source_max") if mode.startswith("minmax_") else (
            ("mean", "stddev") if mode == "standard" else ()
        )
        columns.append({
            "role": column["role"],
            "data_type": column.get("data_type", "analog"),
            "neuron": column.get("mapped_neuron_id"),
            "calibration": [mode, *[float(calibration[key]) for key in keys]],
        })
    return digest({"columns": columns, "records": [
        [0.0 if float(value) == 0.0 else float(value) for value in record]
        for record in document["records"]
    ]})


def training_context(network, signature):
    return {
        "activations": [[int(n.id), n.neuron_type.value, n.activation_function]
                        for n in sorted(network.get_neurons(), key=lambda n: n.id)],
        "data": signature,
    }


def run_key(entry):
    # Bleibt auch beim Umnummerieren sowie Verschieben eines Projekts stabil.
    return entry.setdefault("validity_id", digest([
        entry.get("timestamp"), entry.get("run_id"), entry.get("initial_network_state")
    ]))


def invalidate_history(history, context, invalidated_runs):
    """Sperren bleiben auch beim Zurücksetzen einer Änderung erhalten."""
    changed = False
    for entry in history:
        key = run_key(entry)
        reason = entry.get("invalidated_reason") or invalidated_runs.get(key)
        previous = entry.get("training_context")
        if previous is None:
            # Alteinträge enthalten keinen historischen Inhaltsnachweis.
            # Der erste geladene Zustand dient als Basis für spätere Änderungen.
            entry["training_context"] = json.loads(json.dumps(context))
        elif previous != context and not reason:
            reason = ("activation" if previous.get("activations") != context["activations"]
                      else "data")
        if reason:
            invalidated_runs[key] = reason
            if entry.get("invalidated_reason") != reason or entry.get("continuable", True):
                changed = True
            entry["invalidated_reason"] = reason
            entry["continuable"] = False
    return changed
