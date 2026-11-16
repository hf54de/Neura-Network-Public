"""Recompute author HTML clip data on detached networks."""

import math
import random
import time
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog

from rusttraining import RustTrainingSession, selected_backend
from trainingdataio import TrainingDataIO
from weighttrajectory import connection_label


def replay_source(run, provider, text):
    state = run.get("initial_network_state")
    if not state:
        raise ValueError(text("history.clip.characteristic_start_missing", run=run["run_id"]))
    source = provider(dict(run, network_state=state)) if provider else None
    if not source:
        raise ValueError(text("history.clip.characteristic_source_missing", run=run["run_id"]))
    return source


def characteristic_frames(parent, language, runs, provider, output_id):
    from resultanalysisdialog import ResultAnalysisDialog

    text = language.text
    jobs = []
    for run in runs:
        network, data = replay_source(run, provider, text)
        inputs = data["inputs"]
        output = next((m for m in data["outputs"] if m["neuron"].id == output_id
                       and m.get("data_type") != "binary"), None)
        if len(inputs) != 1 or inputs[0].get("data_type") == "binary" or output is None:
            raise ValueError(text("history.clip.characteristic_unavailable"))
        if not jobs:
            inp = inputs[0]
            minimum, maximum = ResultAnalysisDialog.characteristic_input_range(data, inp)
            xs = [minimum + (maximum - minimum) * index / 160 for index in range(161)]
            targets = ResultAnalysisDialog.limited_characteristic_points([
                (record[inp["column_index"]], record[output["column_index"]])
                for record in data["records"]
            ])
            axes = [ResultAnalysisDialog.characteristic_axis_label(m) for m in (inp, output)]

        inp = inputs[0]
        scaled_xs = [TrainingDataIO.scale_value(x, inp["calibration"], text) for x in xs]
        # Sample early changes densely, with a bounded number of frames per run.
        epochs = run["completed_epochs"]
        sample_epochs = {round(epochs * (index / 180) ** 2) for index in range(181)}
        sample = partial(sample_characteristic, network, inp["neuron"], output, scaled_xs, text)
        jobs.append((run, network, data, sample_epochs, sample))

    segments = replay_segments(parent, text, jobs)
    return None if segments is None else (segments, axes, {"xs": xs, "targets": targets})


def weight_replay_segments(parent, text, runs, provider, source_run_id, source, pair):
    jobs = []
    recorded = {}
    axes = [connection_label(source[0].get_connection(cid)) for cid in pair]
    for run in runs:
        trace = run.get("weight_trajectory")
        if trace and trace["points"]:
            ids = [c["id"] for c in trace["connections"]]
            if ids == pair:
                recorded[run["run_id"]] = trace["points"]
                continue
            if ids[::-1] == pair:
                recorded[run["run_id"]] = [(epoch, y, x, mse) for epoch, x, y, mse in trace["points"]]
                continue
        network, data = source if run["run_id"] == source_run_id else replay_source(run, provider, text)
        first, second = (network.get_connection(cid) for cid in pair)
        jobs.append((run, network, data, range(run["completed_epochs"] + 1),
                     partial(sample_weights, first, second)))

    replayed = replay_segments(parent, text, jobs)
    if replayed is None:
        return None
    recorded.update((job[0]["run_id"], points) for job, points in zip(jobs, replayed))
    return [recorded[run["run_id"]] for run in runs], axes


def replay_segments(parent, text, jobs):
    if not jobs:
        return []
    total = sum(run["completed_epochs"] for run, *_ in jobs)
    progress = QProgressDialog(parent)
    progress.setWindowTitle(text("history.clip.characteristic_progress_title"))
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumWidth(420)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.setCancelButtonText(text("common.cancel"))
    progress.setRange(0, min(max(1, total), 10000))
    progress.show()
    offset = 0
    last_update = -math.inf

    def canceled(run, epoch, force=False):
        nonlocal last_update
        now = time.monotonic()
        if force or now - last_update >= 0.05:
            progress.setLabelText(text(
                "history.clip.characteristic_progress", run=run["run_id"],
                epoch=epoch, epochs=run["completed_epochs"], total=total,
            ))
            progress.setValue((offset + epoch) * progress.maximum() // max(1, total))
            QApplication.processEvents()
            last_update = now
        return progress.wasCanceled()

    segments = []
    try:
        for run, network, data, sample_epochs, sample in jobs:
            if canceled(run, 0, force=True):
                return None
            frames = replay_run(network, data, run, text, sample_epochs, sample,
                                lambda epoch: canceled(run, epoch))
            if frames is None or canceled(run, run["completed_epochs"], force=True):
                return None
            segments.append(frames)
            offset += run["completed_epochs"]
        return segments
    finally:
        progress.close()
        progress.deleteLater()


def replay_run(network, data, run, text, sample_epochs, sample, canceled):
    trainer = network.trainer
    trainer.capture_step_details = False
    trainer.visual_updates_enabled = False
    network.set_solver(run.get("solver") or "sgd")
    network.reset_optimizer_state()
    network.set_learning_rate(run["learning_rate"])
    network.set_momentum(run.get("momentum") or 0.0)
    network.prepare_training_calculation()
    backend = selected_backend()
    session = None
    if backend is not None:
        session = RustTrainingSession(
            backend, network, data["records"], data["inputs"], data["outputs"], text
        )

    inputs = [(m["neuron"], m["column_index"], m["calibration"]) for m in data["inputs"]]
    outputs = [(m["neuron"], m["column_index"], m["calibration"]) for m in data["outputs"]]
    resolve = TrainingDataIO.scale_value
    records = [
        (tuple(resolve(record[column], calibration, text) for _, column, calibration in inputs),
         {neuron.id: resolve(record[column], calibration, text) for neuron, column, calibration in outputs})
        for record in data["records"]
    ]
    input_neurons = [neuron for neuron, _, _ in inputs]
    output_neurons = [neuron for neuron, _, _ in outputs]

    def apply_input(values):
        for neuron, value in zip(input_neurons, values):
            neuron.input_value = value

    seed = int(run.get("shuffle_seed") or 0)
    frames = []
    for epoch in range(run["completed_epochs"] + 1):
        if epoch:
            if session is not None:
                if canceled(epoch - 1):
                    return None
                session.advance_epoch(epoch, seed)
            else:
                ordered = list(records)
                epoch_seed = (seed + epoch * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
                random.Random(epoch_seed).shuffle(ordered)
                for values, targets in ordered:
                    if canceled(epoch - 1):
                        return None
                    apply_input(values)
                    network.train_step(targets)
        if epoch not in sample_epochs:
            continue

        if session is not None and epoch:
            # The clip only reads weights and biases at sampled epochs.
            session.synchronize_parameters()
            mse = session.metrics.mean_squared_error
            maximum_error = session.metrics.maximum_absolute_error
        else:
            squared_error = 0.0
            maximum_error = 0.0
            for values, targets in records:
                if canceled(epoch):
                    return None
                apply_input(values)
                network.forward_pass()
                for neuron in output_neurons:
                    error = abs(targets[neuron.id] - neuron.output_value)
                    squared_error += error * error
                    maximum_error = max(maximum_error, error)
            mse = squared_error / (len(records) * len(outputs))
        values = sample(mse, maximum_error, lambda: canceled(epoch))
        if values is None:
            return None
        frames.append([epoch, *values])
    return frames


def sample_weights(first, second, mse, _maximum_error, _canceled):
    return first.weight, second.weight, mse


def sample_characteristic(network, input_neuron, output, scaled_xs, text, mse, maximum_error, canceled):
    values = []
    for value in scaled_xs:
        if canceled():
            return None
        input_neuron.input_value = value
        network.forward_pass()
        values.append(TrainingDataIO.unscale_value(output["neuron"].output_value, output["calibration"], text))
    return mse, maximum_error, values
