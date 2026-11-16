"""Standalone HTML playback of selected training runs for the author edition."""

import json
import math
from html import escape
from pathlib import Path
from string import Template

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QSpinBox,
)

from characteristicclipexport import characteristic_frames, replay_source, weight_replay_segments
from numberformat import linear_axis_ticks, logarithmic_axis_exponents
from trainingcomparison import metric_chart_title, metric_curve_key
from weighttrajectory import WeightSelectionDialog


CLIP_BACKGROUND = "#2c2c2c"


def ordered_runs(history, selected_ids):
    selected = {run["run_id"]: run for run in history if run["run_id"] in selected_ids}
    if not selected:
        return []
    roots = [run for run in selected.values() if run.get("parent_run_id") not in selected]
    children = {run.get("parent_run_id"): run for run in selected.values()
                if run.get("parent_run_id") in selected}
    if len(roots) != 1 or len(children) != len(selected) - 1:
        return []
    chain = [roots[0]]
    while chain[-1]["run_id"] in children:
        chain.append(children[chain[-1]["run_id"]])
    return chain if len(chain) == len(selected) else []


def weight_segments(runs, text):
    segments = []
    axes = None
    for run in runs:
        trace = run.get("weight_trajectory")
        if not trace or not trace["points"]:
            return None, (), text("history.clip.weight_missing", run=run["run_id"])

        connections = trace["connections"]
        pair = tuple((c["id"], c["source"], c["target"]) for c in connections)
        if axes is None:
            axes = pair
            labels = [c["label"] for c in connections]
        if pair == axes:
            points = trace["points"]
        elif pair[::-1] == axes:
            points = [(epoch, y, x, mse) for epoch, x, y, mse in trace["points"]]
        else:
            return None, (), text("history.clip.weight_pair", run=run["run_id"])
        if segments and not all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
                                for a, b in zip(segments[-1][-1][1:3], points[0][1:3])):
            return None, (), text("history.clip.weight_transition", run=run["run_id"])
        segments.append(points)
    return segments, labels, ""


def clip_data(runs, segments, mode, labels, text, duration, hold, scale_mode="linear", run_colors=None,
              characteristic=None):
    weight = mode == "weight"
    offset = 0
    sections = []
    run_colors = run_colors or {}
    for run, points in zip(runs, segments):
        continuation = run.get("parent_run_id") is not None
        label_key = "history.clip.continuation" if continuation else "history.clip.training_run"
        solver = run.get("solver") or "sgd"
        sections.append({
            "label": text(label_key, run=run["run_id"]),
            "parameters": {
                "solver": text("adam.solver." + solver),
                "learning_rate": run.get("learning_rate"),
                "momentum": run.get("momentum") if solver == "sgd" else None,
                "error_limit": run.get("error_limit"),
                "requested_epochs": run.get("requested_epochs"),
            },
            "status": run.get("status_text", ""),
            "end": offset + run["completed_epochs"],
            "points": [[offset + epoch, *values] for epoch, *values in points],
        })
        sections[-1]["color"] = "#75b9dd" if weight else run_colors.get(run["run_id"], "#75b9dd")
        if not weight:
            if mode == "maximum":
                sections[-1]["mse"] = [[offset + epoch, value] for epoch, value in run.get("curve_points") or []]
            maximum = [(p[0], p[2]) for p in points] if characteristic else run.get("maximum_error_curve_points") or []
            sections[-1]["maximum"] = [[offset + epoch, value] for epoch, value in maximum]
            final_maximum = run.get("maximum_absolute_error")
            if not characteristic and final_maximum is not None and (not maximum or maximum[-1][0] < run["completed_epochs"]):
                sections[-1]["maximum"].append([sections[-1]["end"], final_maximum])
        offset = sections[-1]["end"]
    points = [p for section in sections for p in section["points"]]
    if characteristic:
        xs = characteristic["xs"] + [x for x, _ in characteristic["targets"]]
        ys = [y for p in points for y in p[3]] + [y for _, y in characteristic["targets"]]
    else:
        xs = [p[1] for p in points] if weight else [0, offset]
        ys = [p[2 if weight else 1] for p in points]
    positive = [value for value in ys if value > 0]
    logarithmic = not weight and not characteristic and scale_mode == "logarithmic" and bool(positive)
    bounds, ticks = [], []
    for values, pad in ((xs, weight), (ys, weight or characteristic is not None)):
        low, high = min(values), max(values)
        margin = (high - low) * .06 if pad else 0
        if low == high:
            margin = max(abs(low) * .06, .01)
        low, high = low - margin, high + margin
        bounds.append([low, high])
        ticks.append(linear_axis_ticks(low, high))
    if logarithmic:
        low = math.floor(math.log10(min(positive)))
        high = max(low + 1, math.ceil(math.log10(max(positive))))
        bounds[1] = [low, high]
        ticks[1] = logarithmic_axis_exponents(low, high)
    elif not weight and not characteristic:
        high = max(ys)
        bounds[1] = [0, (high * 1.05 if high else 1)]
        ticks[1] = linear_axis_ticks(*bounds[1])

    initial = runs[0].get("start_error")
    first_mse = runs[0].get("curve_points") or []
    if characteristic:
        initial = segments[0][0][1]
        for section in sections:
            section["status"] = ""
        characteristic["targetsLabel"] = text("analysis.characteristic.legend_points")
    elif initial is None and first_mse:
        initial = first_mse[0][1]
    return {
        "sections": sections, "epochs": offset, "weight": weight,
        "logarithmic": logarithmic, "characteristic": characteristic,
        "initial": initial,
        "bounds": bounds, "ticks": ticks, "axes": labels,
        "duration": duration * 1000, "hold": hold * 1000,
        "text": {key: text("history.clip." + key)
                 for key in ("pause", "play", "running", "finished", "unavailable")},
        "parameterLabels": {
            "solver": text("adam.solver.label").rstrip(": "),
            "learning_rate": text("training.parameters.learning_rate").rstrip(": "),
            "momentum": text("history.column.momentum"),
            "error_limit": text("training.parameters.error_limit").rstrip(": "),
            "requested_epochs": text("history.clip.maximum_epochs"),
        },
        "start": text("trajectory.start"), "current": text("trajectory.current"),
    }


def export_clip(parent, language, history, selected_ids, project_path, choose_path, write_file,
                *, metric, scale_mode="linear", offer_open=None, run_colors=None,
                characteristic_provider=None, characteristic_output=None):
    text = language.text
    title = text("history.clip.title")
    runs = ordered_runs(history, selected_ids)
    if not runs:
        QMessageBox.information(parent, title, text("history.clip.chain"))
        return

    replay_weights = False
    if metric == "characteristic":
        if characteristic_provider is None or characteristic_output is None:
            QMessageBox.information(parent, title, text("history.clip.characteristic_unavailable"))
            return
        mode = metric
        filename_metric = text("history.clip.characteristic_filename")
    elif metric == "trajectory":
        mode = "weight"
        segments, axes, reason = weight_segments(runs, text)
        missing_weights = next((run for run in runs if not (run.get("weight_trajectory") or {}).get("points")), None)
        replay_weights = segments is None and missing_weights is not None and characteristic_provider is not None
        if segments is None and not replay_weights:
            QMessageBox.information(parent, title, reason)
            return
        filename_metric = text("history.clip.weight_filename")
    else:
        mode = metric
        segments = [run.get(metric_curve_key(metric)) or [] for run in runs]
        if not any(segments):
            QMessageBox.information(parent, title, text(f"history.clip.{metric}_missing"))
            return
        axes = [text("history.clip.epoch"), text("training.metric.maximum") if metric == "maximum" else "MSE"]
        filename_metric = text("history.clip.maximum_filename") if metric == "maximum" else "MSE"

    if replay_weights:
        try:
            source = replay_source(missing_weights, characteristic_provider, text)
        except ValueError as error:
            QMessageBox.information(parent, title, str(error))
            return
        network, _ = source
        if len(network.get_connections()) < 2:
            QMessageBox.information(parent, title, text("trajectory.need_two"))
            return
        existing_pair = next(([c["id"] for c in run["weight_trajectory"]["connections"]]
                              for run in runs if (run.get("weight_trajectory") or {}).get("points")), None)
        selection = WeightSelectionDialog(
            network, language, existing_pair, parent, help_key="history.clip.weight_replay_help"
        )
        if selection.exec() != QDialog.DialogCode.Accepted:
            return
        pair = selection.pair()

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QFormLayout(dialog)

    duration = QSpinBox(dialog)
    duration.setRange(1, 300)
    duration.setValue(10)
    layout.addRow(text("history.clip.duration"), duration)
    hold = QSpinBox(dialog)
    hold.setRange(0, 60)
    hold.setValue(3)
    layout.addRow(text("history.clip.hold"), hold)
    for spin in (duration, hold):
        spin.setSuffix(" s")
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(text("common.ok"))
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(text("common.cancel"))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    project = Path(project_path) if project_path else None
    name = project.stem if project else "NeuronNet"
    directory = project.resolve().parent if project else ""
    if project and (directory / "exporte").is_dir():
        directory = directory / "exporte"
    run_ids = str(runs[0]["run_id"])
    if len(runs) > 1:
        run_ids += "-" + str(runs[-1]["run_id"])
    filename = f"{name}_{filename_metric}_{run_ids}.htm"
    try:
        path = choose_path(parent, title, directory, text("forward.html.filter"), filename)
        if path:
            characteristic = None
            if replay_weights:
                result = weight_replay_segments(
                    parent, text, runs, characteristic_provider, missing_weights["run_id"], source, pair
                )
                if result is None:
                    return
                segments, axes = result
            if mode == "characteristic":
                frames = characteristic_frames(parent, language, runs, characteristic_provider, characteristic_output)
                if frames is None:
                    return
                segments, axes, characteristic = frames
            data = clip_data(runs, segments, mode, axes, text, duration.value(), hold.value(),
                             scale_mode, run_colors, characteristic)
            if mode == "characteristic":
                curve_title = text("analysis.characteristic.legend_curve")
            elif mode == "weight":
                curve_title = text("trajectory.title")
            else:
                curve_title = metric_chart_title(language, metric, data["logarithmic"])
            write_file(path, render_clip(language, name, curve_title, data))
            if offer_open is not None:
                offer_open(parent, text, path)
    except (OSError, ValueError, OverflowError) as error:
        QMessageBox.critical(parent, title, text(error.message_key) if hasattr(error, "message_key") else str(error))


def render_clip(language, name, metric, data):
    text = language.text

    def field(label, element_id="", css_class="", cell_class=""):
        div = f'<div class="{cell_class}">' if cell_class else "<div>"
        field_id = f' id="{element_id}"' if element_id else ""
        field_class = f' class="scroll-line {css_class}"' if css_class else ' class="scroll-line"'
        label = escape(label)
        return (
            f'{div}<dt title="{label}">{label}</dt>'
            f'<dd{field_id}{field_class} tabindex="0"></dd></div>'
        )

    epoch = field(text("history.clip.executed_epochs"), "epoch")
    current = field(text("history.clip.current_mse"), "mse")
    if data["weight"]:
        fields = [epoch, current, *(field(label, "", "weight") for label in data["axes"])]
    else:
        fields = [field(text("history.clip.start_mse"), "initial-error"), current, epoch,
                  field(text("history.clip.maximum_error"), "max-error")]

    labels = data["parameterLabels"]
    fields = [
        *fields[:2], field(labels["solver"], "optimizer"),
        *fields[2:], field(labels["learning_rate"], "rates"),
        field(text("history.clip.status"), "status", cell_class="status-cell"),
        field(f'{labels["error_limit"]} · {labels["requested_epochs"]}', "limits"),
    ]

    return Template(PAGE).substitute(
        lang=escape(language.current_language, quote=True), name=escape(name), metric=escape(metric),
        play=escape(text("history.clip.play")), fields="\n".join(fields), background=CLIP_BACKGROUND,
        result=escape(text("history.clip.result")),
        chart=escape(metric if data["weight"] or data["characteristic"] else text("history.clip.error_chart")),
        data=json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", r"\u003c"),
    )


PAGE = """<!doctype html>
<html lang="$lang">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$name – $metric</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; background: transparent; color: #182532; font: 14px "Segoe UI", sans-serif; }
main { max-width: 920px; margin: auto; padding: 8px; container-type: inline-size; }
header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; margin-bottom: 12px; }
h1 { font-size: 17px; margin: 0 0 2px; }
.run-list { display: flex; align-items: center; gap: 8px; margin: 0; padding: 0; list-style: none; }
header > div { min-width: 0; }
.scroll-line { white-space: nowrap; overflow-x: auto; scrollbar-width: none; }
.run-list li { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.run-list [aria-current="step"] { font-weight: 700; }
.run-swatch { width: 9px; height: 9px; border: 1px solid #18253266; border-radius: 50%; }
button { font: inherit; color: inherit; background: #f8fafb; border: 1px solid #b8c2cb; border-radius: 4px; padding: 5px 12px; cursor: pointer; }
button:focus-visible { outline: 2px solid #1976b5; outline-offset: 2px; }
fieldset { min-width: 0; border: 1px solid #9ba7b2; border-radius: 5px; padding: 10px; margin: 0 0 10px; }
legend { padding: 0 4px; font-weight: 600; }
dl { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr) minmax(0, 1.6fr); gap: 9px; margin: 0; }
.status-cell { grid-column: span 2; }
@container (max-width: 404px) {
    dl { grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr) minmax(0, 2.2fr); }
}
dt { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
dd { padding: 4px 6px; margin: 3px 0 0; background: #f8fafb; border: 1px solid #d7dfe6; border-radius: 3px; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
dl > div { min-width: 0; }
canvas { display: block; width: 100%; height: clamp(218px, 45vw, 360px); background: $background; border-radius: 5px; }
</style>
</head>
<body>
<main>
<header><div><h1>$name</h1><ul id="run-list" class="run-list scroll-line" tabindex="0"></ul></div><button id="playback" type="button">$play</button></header>
<fieldset><legend>$result</legend><dl>
$fields
</dl></fieldset>
<fieldset><legend>$chart</legend><canvas role="img" aria-label="$metric"></canvas></fieldset>
</main>
<script id="clip-data" type="application/json">$data</script>
<script>
"use strict";

const clip = JSON.parse(document.querySelector("#clip-data").textContent);
const canvas = document.querySelector("canvas");
const ctx = canvas.getContext("2d");
const button = document.querySelector("#playback");
const runList = document.querySelector("#run-list");
const runItems = clip.sections.map((section, index) => {
    const item = document.createElement("li");
    if (index > 0) {
        const arrow = document.createElement("span");
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "→";
        item.append(arrow);
    }
    const swatch = document.createElement("span");
    swatch.className = "run-swatch";
    swatch.setAttribute("aria-hidden", "true");
    swatch.style.backgroundColor = section.color;
    item.append(swatch, section.label);
    runList.append(item);
    return item;
});
let activeRunItem;
const epoch = document.querySelector("#epoch");
const mse = document.querySelector("#mse");
const status = document.querySelector("#status");
const optimizer = document.querySelector("#optimizer");
const rates = document.querySelector("#rates");
const rateLabel = rates.previousElementSibling;
const limits = document.querySelector("#limits");
let displayedSection;
const weights = document.querySelectorAll("dd.weight");
const maximumError = document.querySelector("#max-error");
const motion = matchMedia("(prefers-reduced-motion: reduce)");
const waitsForGroup = window.parent !== window && new URLSearchParams(location.search).get("sync") === "1";
const numbers = new Intl.NumberFormat(document.documentElement.lang, { maximumSignificantDigits: 7 });
const integer = new Intl.NumberFormat(document.documentElement.lang);
const last = clip.sections.at(-1);
const characteristic = clip.characteristic;
let playbackLength = 0;
let startEpoch = 0;
const playbackSections = clip.sections.map(section => {
    const start = playbackLength;
    playbackLength += Math.sqrt(section.end - startEpoch);
    const part = { start, end: playbackLength, epoch: startEpoch, section };
    startEpoch = section.end;
    return part;
});
const readout = value => value == null ? "–" : numbers.format(value);
if (!clip.weight) document.querySelector("#initial-error").textContent = readout(clip.initial);
let width, height, axes, scale;
let paths = [];
let time = !waitsForGroup && motion.matches ? clip.duration : 0;
let previous = null;
let frame = 0;
let playing = !waitsForGroup && !motion.matches;
let requestGroupToggle;
let visible = !("IntersectionObserver" in window);

function countAt(points, at) {
    let low = 0;
    let high = points.length;
    while (low < high) {
        const middle = Math.floor((low + high) / 2);
        if (points[middle][0] <= at) low = middle + 1;
        else high = middle;
    }
    return low;
}

function dot(x, y, color, radius) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
}

function trace(path, locations, count) {
    let connected = false;
    for (let index = 0; index < count; index++) {
        const point = locations[index];
        if (point === null) connected = false;
        else {
            if (connected) path.lineTo(...point);
            else path.moveTo(...point);
            connected = true;
        }
    }
}

function resize() {
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    scale = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    const left = clip.weight ? 64 : 61;
    const right = width - 24;
    const top = 32;
    const bottom = height - 39;
    const [[xMin, xMax], [yMin, yMax]] = clip.bounds;
    const x = value => left + (value - xMin) / (xMax - xMin) * (right - left);
    const y = value => bottom - (value - yMin) / (yMax - yMin) * (bottom - top);
    axes = { left, right, top, bottom, x, y };
    paths = characteristic ? [] : clip.sections.map(({ points }) => {
        const locations = points.map(p => {
            if (clip.weight) return [x(p[1]), y(p[2])];
            if (clip.logarithmic && p[1] <= 0) return null;
            return [x(p[0]), y(clip.logarithmic ? Math.log10(p[1]) : p[1])];
        });
        const path = new Path2D();
        trace(path, locations, locations.length);
        return { locations, path };
    });
    paint(time);
}

function drawAxes() {
    const { left, right, top, bottom, x, y } = axes;
    ctx.clearRect(0, 0, width, height);
    ctx.font = '11px "Segoe UI", sans-serif';
    ctx.fillStyle = "#d2dfe9";
    ctx.strokeStyle = "#545b60";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.textAlign = "right";
    for (const value of clip.ticks[1]) {
        const py = y(value);
        ctx.moveTo(left, py);
        ctx.lineTo(right, py);
        const label = clip.logarithmic ? "1e" + value : numbers.format(value);
        ctx.fillText(label, left - 7, py + 4);
    }
    ctx.textAlign = "center";
    for (const value of clip.ticks[0]) {
        const px = x(value);
        ctx.moveTo(px, top);
        ctx.lineTo(px, bottom);
        ctx.fillText(clip.weight ? numbers.format(value) : integer.format(value), px, bottom + 15);
    }
    ctx.stroke();
    ctx.strokeStyle = "#a7b2b8";
    ctx.strokeRect(left, top, right - left, bottom - top);
    ctx.fillText(clip.axes[0], (left + right) / 2, height - 7, right - left);
    ctx.save();
    ctx.translate(12, (top + bottom) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(clip.axes[1], 0, 0, bottom - top);
    ctx.restore();

    if (clip.weight) {
        dot(left + 4, 16, "#59a280", 3.5);
        dot(left + 62, 16, "#f68d41", 3.5);
        ctx.textAlign = "left";
        ctx.fillStyle = "#d2dfe9";
        ctx.fillText(clip.start, left + 12, 20);
        ctx.fillText(clip.current, left + 70, 20);
    } else if (!characteristic) {
        ctx.fillText(canvas.getAttribute("aria-label"), (left + right) / 2, 20, right - left);
        ctx.save();
        ctx.strokeStyle = "#ec8f51";
        ctx.setLineDash([4, 4]);
        for (const section of clip.sections.slice(0, -1)) {
            const px = x(section.end);
            ctx.beginPath();
            ctx.moveTo(px, top);
            ctx.lineTo(px, bottom);
            ctx.stroke();
        }
        ctx.restore();
    }
}

function drawCharacteristic(section, sampleIndex, at) {
    const sample = section.points[sampleIndex];
    const next = section.points[sampleIndex + 1];
    const blend = next ? (at - sample[0]) / (next[0] - sample[0]) : 0;
    const { left, right, top, bottom, x, y } = axes;
    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top, right - left, bottom - top);
    ctx.clip();
    for (const [px, py] of characteristic.targets) dot(x(px), y(py), "#f5c343", 2.5);
    ctx.strokeStyle = section.color;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    characteristic.xs.forEach((px, index) => {
        const value = sample[3][index];
        const py = y(next ? value + (next[3][index] - value) * blend : value);
        if (index === 0) ctx.moveTo(x(px), py);
        else ctx.lineTo(x(px), py);
    });
    ctx.stroke();
    ctx.restore();
    dot(left + 4, 16, "#f5c343", 3);
    ctx.textAlign = "left";
    ctx.fillStyle = "#d2dfe9";
    ctx.fillText(characteristic.targetsLabel, left + 13, 20, right - left - 13);
}

function paint(elapsed) {
    const fraction = Math.min(1, elapsed / clip.duration);
    const position = fraction * playbackLength;
    const part = playbackSections.find(item => position < item.end);
    // Each run starts slowly so early epochs remain visible longer.
    const progress = part ? (position - part.start) / (part.end - part.start) : 1;
    const at = part ? part.epoch + (part.section.end - part.epoch) * progress ** 2 : clip.epochs;
    const current = clip.sections.find(section => at < section.end) ?? last;
    if (current !== displayedSection) {
        const { solver, learning_rate, momentum, error_limit, requested_epochs } = current.parameters;
        const rateLabels = [clip.parameterLabels.learning_rate];
        const rateValues = [readout(learning_rate)];
        if (momentum != null) {
            rateLabels.push(clip.parameterLabels.momentum);
            rateValues.push(readout(momentum));
        }
        rateLabel.textContent = rateLabel.title = rateLabels.join(" · ");
        const maxEpochs = requested_epochs == null ? "–" : integer.format(requested_epochs);
        for (const [field, value] of [
            [optimizer, solver],
            [rates, rateValues.join(" · ")],
            [limits, readout(error_limit) + " · " + maxEpochs],
        ]) {
            field.textContent = field.title = value;
            field.scrollLeft = 0;
        }
        displayedSection = current;
    }
    const sampleIndex = countAt(current.points, at) - 1;
    const sample = current.points[sampleIndex];
    const error = current.mse
        ? current.mse[countAt(current.mse, at) - 1]?.[1]
        : sample?.[clip.weight ? 3 : 1];
    const item = runItems[clip.sections.indexOf(current)];
    if (item !== activeRunItem) {
        activeRunItem?.removeAttribute("aria-current");
        item.setAttribute("aria-current", "step");
        activeRunItem = item;
    }
    epoch.textContent = integer.format(Math.floor(at));
    mse.textContent = readout(error);
    if (maximumError) {
        const maximum = current.maximum[countAt(current.maximum, at) - 1];
        maximumError.textContent = readout(maximum?.[1]);
    }
    weights.forEach((field, index) => {
        field.textContent = sample ? numbers.format(sample[index + 1]) : "–";
    });
    status.textContent = at >= clip.epochs
        ? last.status || clip.text.finished
        : current.points.length ? clip.text.running : clip.text.unavailable;

    if (!axes) return;
    drawAxes();
    if (characteristic) {
        drawCharacteristic(current, sampleIndex, at);
        return;
    }
    ctx.lineWidth = 1.45;
    let marker;
    for (const [index, section] of clip.sections.entries()) {
        const { locations, path } = paths[index];
        const count = countAt(section.points, at);
        if (!count) {
            if (section === current) {
                marker = undefined;
                break;
            }
            continue;
        }
        ctx.strokeStyle = clip.weight ? "#75b9dd" : section.color;
        if (count === locations.length) {
            ctx.stroke(path);
            marker = locations[count - 1];
        } else {
            ctx.beginPath();
            trace(ctx, locations, count);
            marker = locations[count - 1];
            const next = locations[count];
            if (marker && next) {
                const progress = (at - section.points[count - 1][0])
                    / (section.points[count][0] - section.points[count - 1][0]);
                marker = marker.map((value, axis) => value + (next[axis] - value) * progress);
                ctx.lineTo(...marker);
            }
            ctx.stroke();
        }
        if (section === current) break;
    }
    if (clip.weight) dot(...paths[0].locations[0], "#59a280", 4);
    if (marker && (!clip.weight || at > 0)) dot(...marker, clip.weight ? "#f68d41" : current.color, 4);
}

function tick(now) {
    if (previous !== null) {
        const next = time + now - previous;
        if (time < clip.duration && next >= clip.duration) {
            time = Math.min(next, clip.duration + clip.hold);
        } else {
            time = next % (clip.duration + clip.hold);
        }
    }
    previous = now;
    paint(time);
    frame = requestAnimationFrame(tick);
}

function sync() {
    cancelAnimationFrame(frame);
    previous = null;
    button.textContent = playing ? clip.text.pause : clip.text.play;
    if (!requestGroupToggle && playing && visible) frame = requestAnimationFrame(tick);
}

button.disabled = waitsForGroup;
button.addEventListener("click", () => {
    if (requestGroupToggle) {
        requestGroupToggle();
        return;
    }
    playing = !playing;
    if (playing && motion.matches && time >= clip.duration) time = 0;
    sync();
});
motion.addEventListener("change", () => {
    if (waitsForGroup || requestGroupToggle) return;
    playing = !motion.matches;
    if (!playing) time = clip.duration;
    paint(time);
    sync();
});
if (!visible && !waitsForGroup) {
    const observer = new IntersectionObserver(entries => {
        visible = entries.some(entry => entry.isIntersecting);
        sync();
    });
    observer.observe(document.querySelector("main"));
}
if (ctx) {
    window.addEventListener("resize", resize);
    resize();
} else {
    paint(time);
}
sync();

window.neuronNetTrainingClip = Object.freeze({
    duration: clip.duration,
    hold: clip.hold,
    connect(toggle) {
        requestGroupToggle = toggle;
        playing = false;
        sync();
        return (elapsed, active) => {
            time = elapsed;
            button.disabled = false;
            if (playing !== active) {
                playing = active;
                sync();
            }
            paint(time);
        };
    }
});
</script>
</body>
</html>"""
