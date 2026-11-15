"""Self-contained browser export of the calibrated network experiment."""

import json
from html import escape
from string import Template

from neurontype import NeuronType


def web_input_grid(grid):
    """Encode the desktop slider's decimal grid without float rounding."""
    if grid is None:
        return None
    exponent = min(0, grid.origin.as_tuple().exponent, grid.step.as_tuple().exponent)
    factor = 10 ** -exponent
    origin_num, origin_den = grid.origin.as_integer_ratio()
    step_num, step_den = grid.step.as_integer_ratio()
    return {
        "origin": str(origin_num * factor // origin_den),
        "step": str(step_num * factor // step_den),
        "exponent": exponent,
        "count": str(grid.count),
        "positions": grid.positions,
    }


def network_snapshot(network):
    """Keep the same node and incoming-connection order as the Python forward pass."""
    order = network.get_topological_order()
    slots = {neuron.id: index for index, neuron in enumerate(order)}
    nodes = [
        None if neuron.neuron_type == NeuronType.INPUT else {
            "activation": neuron.activation_function,
            "bias": neuron.bias,
            "incoming": [
                [slots[connection.source_neuron.id], connection.weight]
                for connection in neuron.incoming_connections
            ],
        }
        for neuron in order
    ]
    return slots, nodes


def render_forward_html(language, model):
    text = language.text
    data = json.dumps(model, ensure_ascii=False, allow_nan=False).replace("<", r"\u003c")
    return PAGE.substitute(
        language=escape(language.current_language),
        title=escape(text("forward.window.title")),
        inputs=escape(text("forward.inputs.group")),
        outputs=escape(text("forward.outputs.group")),
        data=data,
    )


PAGE = Template(r'''<!doctype html>
<html lang="$language">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; color: #171717; background: transparent; font: 12px "Segoe UI", sans-serif; }
.viewport { max-height: 100vh; overflow: auto; }
main { min-width: 722px; }
.content { padding: 10px 12px 12px; }
fieldset { min-width: 0; margin: 0 4px 12px; padding: 9px 9px 11px; border: 1px solid #777; border-radius: 5px; }
legend { padding: 0 2px; }
.grid {
    display: grid;
    grid-template-columns: 102px var(--raw-column, 135px) 111px 81px 101px minmax(140px, 1fr);
    row-gap: 7px;
    grid-template-rows: 16px;
    grid-auto-rows: minmax(22px, auto);
    align-items: center;
}
#outputs { row-gap: 6px; grid-auto-rows: minmax(20px, auto); }
.heading, .name, .value, .scaling { padding-right: 7px; }
.heading { white-space: nowrap; }
#input-list { min-inline-size: min-content; }
#inputs { --raw-column: max-content; }
#inputs > :nth-child(2) { min-width: 135px; }
.name { overflow: hidden; white-space: nowrap; }
.value, .range, input[type=number] { font: 11px "Courier New", monospace; }
.value, .scaling { overflow-wrap: anywhere; }
.range { display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1.6fr); padding-right: 5px; }
.range span { overflow-wrap: anywhere; }
.range span:nth-child(2), .no-slider { text-align: center; }
.number {
    display: flex; align-items: center; margin-right: 8px;
    height: 21px; background: #f9f9f9; border: 1px solid #dedede;
    border-bottom-color: #878787; border-radius: 4px;
}
.number:focus-within { outline: 1px solid #707070; }
.number input { flex: 1 1 0; width: 0; min-width: 68px; border: 0; padding: 0 4px; background: transparent; outline: none; }
.number input { appearance: textfield; }
.number input::-webkit-inner-spin-button,
.number input::-webkit-outer-spin-button { appearance: none; }
.spin {
    flex: 0 0 19px; height: 18px; padding: 0; border: 0; background: none; color: #363636;
}
.spin:hover { background: #e9e9e9; }
.spin::before {
    display: inline-block; width: 6px; height: 6px; content: "";
    border: solid currentColor; border-width: 1px 1px 0 0;
    transform: translateY(1px) rotate(-45deg);
}
.spin.down::before { transform: translateY(-2px) rotate(135deg); }
.unit { flex: none; margin-right: 4px; font: 11px "Courier New", monospace; white-space: nowrap; }
input[type=range] { appearance: none; width: 100%; height: 18px; margin: 0; background: transparent; }
input[type=range]::-webkit-slider-runnable-track { height: 4px; background: #878787; }
input[type=range]::-webkit-slider-thumb {
    appearance: none; width: 16px; height: 16px; margin-top: -6px; border: 1px solid #c8c8c8;
    border-radius: 50%; background: radial-gradient(circle, #bb2329 0 3px, white 3.5px);
}
input[type=range]::-moz-range-track { height: 4px; background: #878787; }
input[type=range]::-moz-range-thumb {
    width: 14px; height: 14px; border: 1px solid #c8c8c8; border-radius: 50%;
    background: radial-gradient(circle, #bb2329 0 3px, white 3.5px);
}
input[type=range]:disabled { opacity: .55; }
.bar { height: 18px; border: 2px solid #8c969f; border-radius: 4px; background: #eee; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 2px; background: #c51d24; }
.bar.outside { border-color: #c62828; }
.bar.outside span { background: #c62828; }
.binary { display: block; border: 1px solid; border-radius: 4px; text-align: center; font: inherit; font-weight: 600; }
button.binary { width: calc(100% - 8px); min-height: 20px; cursor: pointer; }
span.binary { min-height: 18px; }
.array-view-toggle {
    margin: 0 4px 8px; padding: 3px 9px;
    border: 1px solid #8c969f; border-radius: 5px;
    background: #f9f9f9; color: inherit; font: inherit; cursor: pointer;
}
.array-scroll { overflow-x: auto; }
.array-grid {
    display: grid; grid-auto-rows: 58px; gap: 6px;
    width: max-content; margin: 0 auto; padding: 2px;
    touch-action: none; user-select: none;
}
.array-cell {
    border: 1px solid #8c969f; border-radius: 5px;
    background: var(--array-off); cursor: pointer;
}
.array-cell[aria-pressed="true"] { background: var(--array-on); }
.array-cell:hover { border: 2px solid #4f788f; }
.characteristic-controls, .characteristic-key { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; }
.characteristic-controls select { max-width: 100%; font: inherit; }
.characteristic-value { margin: 7px 0 3px; padding: 4px; background: #edf4f9; }
input[type=range].characteristic-slider {
    --thumb-width: 16px;
    margin-left: calc(var(--slider-start, 8px) - var(--thumb-width) / 2);
    width: calc(var(--slider-span, 100% - 16px) + var(--thumb-width));
}
input[type=range].characteristic-slider::-webkit-slider-thumb {
    box-sizing: border-box; width: var(--thumb-width);
}
input[type=range].characteristic-slider::-moz-range-thumb {
    box-sizing: border-box; width: var(--thumb-width);
}
.characteristic-plot { position: relative; }
.characteristic-plot canvas { display: block; width: 100%; height: 190px; }
.characteristic-point { position: absolute; width: 10px; height: 10px; border: 1px solid #9c3a19;
    border-radius: 50%; transform: translate(-50%, -50%); pointer-events: none; }
.characteristic-caption { text-align: center; margin: 0 0 5px; }
.characteristic-key span { display: inline-flex; align-items: center; gap: 5px; }
.characteristic-key span[hidden] { display: none; }
.characteristic-key i { width: 8px; height: 8px; border-radius: 50%; }
.characteristic-key i.line { width: 13px; height: 2px; border-radius: 0; }
#status { margin: 3px 0 0; line-height: 1.45; }
#status:empty { display: none; }
</style>
</head>
<body>
<div class="viewport">
<main class="content">
<fieldset id="input-list"><legend>$inputs</legend><div class="grid" id="inputs"></div></fieldset>
<fieldset><legend>$outputs</legend><div class="grid" id="outputs"></div></fieldset>
<p id="status" role="status"></p>
</main>
</div>
<script type="application/json" id="model">$data</script>
<script>
"use strict";
const model = JSON.parse(document.getElementById("model").textContent);
const text = model.text;
const statusLine = document.getElementById("status");
const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

function element(tag, className, label) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (label !== undefined) node.textContent = label;
    return node;
}

function createGrid(id, headers) {
    const grid = document.getElementById(id);
    for (const label of headers) grid.append(element("div", "heading", label));
    return grid;
}

function rangeLabel(entry) {
    const range = element("div", "range");
    for (const label of [entry.minimumText, "…", entry.maximumText]) {
        range.append(element("span", "", label));
    }
    return range;
}

function nameLabel(name) {
    const label = element("div", "name", name);
    label.title = name;
    return label;
}

function displayNumber(value, digits) {
    if (value === 0) return "0";
    const magnitude = Math.abs(value);
    if (magnitude < 0.0001 || magnitude >= 10000000) {
        const [mantissa, exponent] = value.toExponential(digits - 1).split("e");
        return trimDecimal(mantissa) + "e" + exponent;
    }
    return trimDecimal(value.toFixed(Math.max(0, digits - 1 - Math.floor(Math.log10(magnitude)))));
}

function trimDecimal(value) {
    return value.includes(".") ? value.replace(/0+$$/, "").replace(/\.$$/, "") : value;
}

function scale(value, calibration) {
    const { mode, source_min: low, source_max: high, mean, stddev } = calibration;
    switch (mode) {
        case "none": return value;
        case "standard": return stddev > 0 ? (value - mean) / stddev : NaN;
        case "minmax_0_1": return high > low ? (value - low) / (high - low) : NaN;
        case "minmax_minus1_1": return high > low ? (value - low) / (high - low) * 2 - 1 : NaN;
    }
    return NaN;
}

function unscale(value, calibration) {
    const { mode, source_min: low, source_max: high, mean, stddev } = calibration;
    switch (mode) {
        case "none": return value;
        case "standard": return value * stddev + mean;
        case "minmax_0_1": return low + value * (high - low);
        case "minmax_minus1_1": return low + ((value + 1) / 2) * (high - low);
    }
    return NaN;
}

function activate(kind, value) {
    switch (kind) {
        case "Linear": return value;
        case "ReLU": return Math.max(0, value);
        case "Tanh": return Math.tanh(value);
        case "Sigmoid": {
            if (value >= 0) return 1 / (1 + Math.exp(-value));
            const exponential = Math.exp(value);
            return exponential / (1 + exponential);
        }
    }
    return NaN;
}

function roundRatio(numerator, denominator) {
    return (2n * numerator + denominator) / (2n * denominator);
}

// The desktop uses a decimal grid starting at the raw minimum.
function prepareGrid(grid) {
    if (!grid) return null;
    return { ...grid, origin: BigInt(grid.origin), step: BigInt(grid.step), count: BigInt(grid.count) };
}

function gridValue(grid, index) {
    return Number(String(grid.origin + index * grid.step) + "e" + grid.exponent);
}

function gridIndex(grid, value) {
    const [coefficient, exponent = "0"] = String(value).split("e");
    const fractional = (coefficient.split(".")[1] || "").length;
    const valueExponent = Number(exponent) - fractional;
    const common = Math.min(grid.exponent, valueExponent);
    const raw = BigInt(coefficient.replace(".", "")) * 10n ** BigInt(valueExponent - common);
    const factor = 10n ** BigInt(grid.exponent - common);
    const distance = raw - grid.origin * factor;
    if (distance <= 0n) return 0n;
    const index = roundRatio(distance, grid.step * factor);
    return index > grid.count ? grid.count : index;
}

function sliderPosition(entry, grid, value, positions) {
    if (grid) {
        return grid.count === 0n ? 0 : Number(roundRatio(gridIndex(grid, value) * BigInt(grid.positions), grid.count));
    }
    if (entry.minimum === entry.maximum) return 0;
    return Math.round((value - entry.minimum) / (entry.maximum - entry.minimum) * positions);
}

function sliderValue(entry, grid, position, positions) {
    if (grid) {
        const index = grid.positions ? roundRatio(BigInt(position) * grid.count, BigInt(grid.positions)) : 0n;
        return gridValue(grid, index);
    }
    return entry.minimum + position / positions * (entry.maximum - entry.minimum);
}

function setBinary(node, active, uncertain) {
    const [border, background, foreground] = model.binaryColors[active ? "on" : "off"];
    node.style.borderColor = border;
    node.style.background = background;
    node.style.color = foreground;
    node.textContent = (active ? "● " + text.on : "○ " + text.off);
    if (uncertain) {
        node.style.cssText = model.uncertainStyle;
        node.textContent = "⚠ " + (active ? text.on : text.off) + " · " + text.uncertain;
    }
}

function createInput(grid, entry) {
    const internal = element("div", "value", "–");
    const valueCell = element("div");
    let readValue;
    let setChecked;
    let sliderCell;
    let addSlider;
    if (entry.binary) {
        const button = element("button", "binary");
        button.type = "button";
        button.setAttribute("aria-label", entry.name);
        let checked = entry.value > 0.5;
        const update = () => {
            setBinary(button, checked, false);
            button.setAttribute("aria-pressed", String(checked));
        };
        setChecked = state => {
            checked = state;
            update();
        };
        button.addEventListener("click", () => {
            setChecked(!checked);
            calculate();
        });
        update();
        valueCell.append(button);
        sliderCell = element("div", "no-slider", "–");
        readValue = () => checked ? 1 : 0;
    } else {
        const number = element("input");
        number.type = "number";
        number.min = entry.minimum;
        number.max = entry.maximum;
        number.step = entry.step;
        number.value = entry.value;
        number.setAttribute("aria-label", entry.name);
        valueCell.className = "number";
        valueCell.append(number);
        if (entry.unit) valueCell.append(element("span", "unit", entry.unit));

        const stepGrid = prepareGrid(entry.grid);
        const sliders = [];
        let value = entry.value;
        addSlider = (label, fallbackPositions) => {
            const positions = stepGrid ? stepGrid.positions : fallbackPositions;
            const slider = element("input");
            slider.type = "range";
            slider.min = 0;
            slider.max = positions;
            slider.step = 1;
            slider.disabled = entry.maximum <= entry.minimum;
            slider.setAttribute("aria-label", label);
            slider.value = sliderPosition(entry, stepGrid, value, positions);
            slider.addEventListener("input", () => {
                update(sliderValue(entry, stepGrid, slider.valueAsNumber, positions), true);
            });
            sliders.push({ slider, positions });
            return slider;
        };
        sliderCell = addSlider(entry.name + " – " + model.inputHeaders[5], 1000);

        function update(candidate, commit) {
            if (Number.isFinite(candidate)) {
                const bounded = clamp(candidate, entry.minimum, entry.maximum);
                value = stepGrid ? gridValue(stepGrid, gridIndex(stepGrid, bounded)) : Number(bounded.toFixed(10));
                for (const { slider, positions } of sliders) {
                    slider.value = sliderPosition(entry, stepGrid, value, positions);
                }
                calculate();
            }
            if (commit) number.value = value;
        }
        function step(direction) {
            const next = stepGrid
                ? gridValue(stepGrid, gridIndex(stepGrid, value) + BigInt(direction))
                : value + direction * entry.step;
            update(next, true);
        }
        for (const direction of [1, -1]) {
            const stepButton = element("button", direction > 0 ? "spin" : "spin down");
            stepButton.type = "button";
            const action = direction > 0 ? text.increase : text.decrease;
            stepButton.setAttribute("aria-label", action + " – " + entry.name);
            stepButton.disabled = entry.maximum <= entry.minimum;
            stepButton.addEventListener("click", () => step(direction));
            valueCell.append(stepButton);
        }
        number.addEventListener("keydown", event => {
            if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                event.preventDefault();
                step(event.key === "ArrowUp" ? 1 : -1);
            }
        });
        number.addEventListener("input", () => update(number.valueAsNumber, false));
        number.addEventListener("change", () => update(number.valueAsNumber, true));
        number.addEventListener("blur", () => { number.value = value; });
        readValue = () => value;
    }
    grid.append(nameLabel(entry.name), valueCell, internal, element("div", "scaling", entry.scaling),
        rangeLabel(entry), sliderCell);
    return { entry, internal, readValue, setChecked, addSlider };
}

function createOutput(grid, entry) {
    const raw = element("div", "value", "–");
    const internal = element("div", "value", "–");
    const indicator = element("span", entry.binary ? "binary" : "bar");
    const fill = element("span");
    if (!entry.binary) {
        indicator.append(fill);
        indicator.setAttribute("role", "progressbar");
        indicator.setAttribute("aria-label", entry.name);
    }
    grid.append(nameLabel(entry.name), raw, internal, element("div", "scaling", entry.scaling),
        rangeLabel(entry), indicator);
    return { entry, raw, internal, indicator, fill };
}

function createArrayView(definition) {
    const list = document.getElementById("input-list");
    const toggle = element("button", "array-view-toggle", definition.showArray);
    toggle.type = "button";
    toggle.setAttribute("aria-controls", "input-list input-array");
    toggle.setAttribute("aria-expanded", "false");
    const array = element("fieldset");
    array.id = "input-array";
    array.hidden = true;
    const scroll = element("div", "array-scroll");
    const grid = element("div", "array-grid");
    grid.style.gridTemplateColumns = "repeat(" + definition.columns + ", 58px)";
    grid.style.setProperty("--array-on", definition.onColor);
    grid.style.setProperty("--array-off", definition.offColor);
    scroll.append(grid);
    array.append(element("legend", "", definition.title), scroll);
    list.before(toggle);
    list.after(array);

    const rowsBySlot = new Map(inputs.map(row => [row.entry.slot, row]));
    const rowsByButton = new Map();
    function updateButton(button, row) {
        button.setAttribute("aria-pressed", String(row.readValue() > 0.5));
    }
    function toggleCell(button) {
        const row = rowsByButton.get(button);
        row.setChecked(row.readValue() <= 0.5);
        updateButton(button, row);
        calculate();
    }
    for (const slot of definition.cells) {
        const row = rowsBySlot.get(slot);
        if (!row) {
            grid.append(element("span"));
            continue;
        }
        const button = element("button", "array-cell");
        button.type = "button";
        button.title = row.entry.name;
        button.setAttribute("aria-label", row.entry.name);
        updateButton(button, row);
        button.addEventListener("click", event => {
            // A pointer press has already switched this cell.
            if (event.detail === 0) toggleCell(button);
        });
        rowsByButton.set(button, row);
        grid.append(button);
    }

    let lastCell = null;
    function paint(target) {
        const cell = rowsByButton.has(target) ? target : null;
        if (cell && cell !== lastCell) toggleCell(cell);
        lastCell = cell;
    }
    function resetStroke() {
        lastCell = null;
    }
    grid.addEventListener("pointerdown", event => {
        if (event.isPrimary && event.button === 0) {
            resetStroke();
            paint(event.target);
        }
    });
    document.addEventListener("pointermove", event => {
        if (!event.isPrimary || array.hidden) return;
        if (event.buttons & 1) {
            paint(document.elementFromPoint(event.clientX, event.clientY));
        } else {
            resetStroke();
        }
    });
    document.addEventListener("pointerup", resetStroke);
    document.addEventListener("pointercancel", resetStroke);
    window.addEventListener("blur", resetStroke);

    toggle.addEventListener("click", () => {
        const showArray = array.hidden;
        list.hidden = showArray;
        array.hidden = !showArray;
        toggle.textContent = showArray ? definition.showList : definition.showArray;
        toggle.setAttribute("aria-expanded", String(showArray));
        resetStroke();
        if (showArray) {
            for (const [button, row] of rowsByButton) updateButton(button, row);
        }
    });
}

function createCharacteristic(definition, input) {
    const group = element("fieldset");
    group.id = "characteristic";
    const controls = element("div", "characteristic-controls");
    const outputLabel = element("label", "", definition.outputLabel + " ");
    const outputSelect = element("select");
    definition.curves.forEach((curve, index) => {
        const option = element("option", "", curve.name);
        option.value = index;
        outputSelect.append(option);
    });
    outputSelect.selectedIndex = Math.max(0, definition.curves.findIndex(
        curve => curve.output === definition.selectedOutput
    ));
    outputLabel.append(outputSelect);
    const targetsLabel = element("label");
    const showTargets = element("input");
    showTargets.type = "checkbox";
    showTargets.checked = true;
    targetsLabel.append(showTargets, " " + definition.trainingPoints);
    controls.append(outputLabel, targetsLabel);

    const value = element("div", "characteristic-value");
    const slider = input.addSlider(definition.inputLabel + " – " + input.entry.name, 10000);
    slider.classList.add("characteristic-slider");
    const stepGrid = prepareGrid(input.entry.grid);
    const positions = Number(slider.max);
    const sliderBounds = [0, positions].map(position => sliderValue(input.entry, stepGrid, position, positions));
    const chart = element("div", "characteristic-plot");
    const canvas = element("canvas");
    canvas.setAttribute("role", "img");
    const point = element("span", "characteristic-point");
    point.setAttribute("aria-hidden", "true");
    point.style.background = definition.colors.point;
    chart.append(canvas, point);
    const caption = element("div", "characteristic-caption");
    const key = element("div", "characteristic-key");
    function addKey(label, color, line = false) {
        const item = element("span");
        const symbol = element("i", line ? "line" : "");
        symbol.style.background = color;
        item.append(symbol, label);
        key.append(item);
        return item;
    }
    addKey(definition.title, definition.colors.curve, true);
    addKey(definition.actual, definition.colors.point);
    const targetsKey = addKey(definition.targets, "#f4c430");
    group.append(element("legend", "", definition.title), controls, value, slider, chart, caption, key);
    statusLine.before(group);

    const context = canvas.getContext("2d");
    const [xMin, xMax] = definition.xBounds;
    const tickFormat = new Intl.NumberFormat(document.documentElement.lang, { maximumSignificantDigits: 6 });
    let project = null;
    let rawOutputs = null;
    const selectedCurve = () => definition.curves[outputSelect.selectedIndex];

    function updatePoint() {
        const curve = selectedCurve();
        if (!rawOutputs) {
            value.textContent = "–";
            point.hidden = true;
            return;
        }

        const x = input.readValue();
        const y = rawOutputs[curve.output];
        value.textContent = definition.xAxis + " = " + tickFormat.format(x)
            + " | " + definition.actual + ": " + tickFormat.format(y);
        const [yMin, yMax] = curve.yBounds;
        point.hidden = !project || x < xMin || x > xMax || y < yMin || y > yMax;
        if (!point.hidden) {
            const [px, py] = project(x, y);
            point.style.left = px + "px";
            point.style.top = py + "px";
        }
    }

    function draw() {
        const curve = selectedCurve();
        const [yMin, yMax] = curve.yBounds;
        const axis = definition.xAxis + " (X) · " + curve.axis + " (Y)";
        caption.textContent = axis;
        canvas.setAttribute("aria-label", definition.title + " – " + axis);
        targetsKey.hidden = !showTargets.checked;
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        if (!context || width < 100 || height < 50) return;
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.font = '11px "Segoe UI", sans-serif';
        const left = Math.max(26, ...curve.yTicks.map(y => context.measureText(tickFormat.format(y)).width + 8));
        const right = width - 34;
        const top = 10;
        const bottom = height - 23;
        project = (x, y) => [
            left + (x - xMin) / (xMax - xMin) * (right - left),
            bottom - (y - yMin) / (yMax - yMin) * (bottom - top),
        ];

        const [sliderStart, sliderEnd] = sliderBounds.map(x => project(x, yMin)[0]);
        slider.style.setProperty("--slider-start", sliderStart + "px");
        slider.style.setProperty("--slider-span", sliderEnd - sliderStart + "px");

        context.strokeStyle = definition.colors.grid;
        context.fillStyle = definition.colors.axes;
        context.beginPath();
        context.textAlign = "center";
        context.textBaseline = "top";
        for (const x of definition.xTicks) {
            const [px] = project(x, yMin);
            context.moveTo(px, top);
            context.lineTo(px, bottom);
            context.fillText(tickFormat.format(x), px, bottom + 4);
        }
        context.textAlign = "right";
        context.textBaseline = "middle";
        for (const y of curve.yTicks) {
            const [, py] = project(xMin, y);
            context.moveTo(left, py);
            context.lineTo(right, py);
            context.fillText(tickFormat.format(y), left - 5, py);
        }
        context.stroke();
        context.strokeStyle = definition.colors.axes;
        context.strokeRect(left, top, right - left, bottom - top);

        if (showTargets.checked) {
            context.fillStyle = "#f4c430";
            for (const target of curve.targets) {
                const [px, py] = project(...target);
                context.beginPath();
                context.arc(px, py, 3, 0, 2 * Math.PI);
                context.fill();
            }
        }
        context.strokeStyle = definition.colors.curve;
        context.lineWidth = 2;
        context.beginPath();
        context.moveTo(...project(...curve.points[0]));
        for (const pair of curve.points.slice(1)) context.lineTo(...project(...pair));
        context.stroke();
        updatePoint();
    }

    outputSelect.addEventListener("change", draw);
    showTargets.addEventListener("change", draw);
    const resize = new ResizeObserver(draw);
    resize.observe(chart);
    draw();
    return values => {
        rawOutputs = values;
        updatePoint();
    };
}

const inputGrid = createGrid("inputs", model.inputHeaders);
const outputGrid = createGrid("outputs", model.outputHeaders);
const inputs = model.inputs.map(entry => createInput(inputGrid, entry));
const outputs = model.outputs.map(entry => createOutput(outputGrid, entry));
if (model.inputArray) createArrayView(model.inputArray);
const updateCharacteristic = model.characteristic
    ? createCharacteristic(model.characteristic, inputs[0])
    : null;

function showOutput(row, value, rawValue) {
    const { entry, raw, internal, indicator, fill } = row;
    internal.textContent = displayNumber(value, 4);
    raw.textContent = displayNumber(rawValue, 4) + (entry.unit ? " " + entry.unit : "");
    if (entry.binary) {
        const uncertain = model.uncertainty.lower < value && value < model.uncertainty.upper;
        setBinary(indicator, value > 0.5, uncertain);
        indicator.title = uncertain ? text.uncertaintyHint : "";
        for (const label of [raw, internal]) {
            label.style.cssText = uncertain ? model.uncertainStyle : "";
            label.title = indicator.title;
        }
        return;
    }
    const outside = rawValue < entry.minimum || rawValue > entry.maximum;
    const proportion = entry.maximum > entry.minimum
        ? (rawValue - entry.minimum) / (entry.maximum - entry.minimum)
        : 0;
    const percent = Math.round(clamp(proportion, 0, 1) * 1000) / 10;
    fill.style.width = percent + "%";
    indicator.classList.toggle("outside", outside);
    indicator.title = outside ? text.outside : text.within;
    indicator.setAttribute("aria-valuenow", percent);
}

function calculate() {
    const values = Array(model.nodes.length).fill(0);
    for (const row of inputs) {
        const value = scale(row.readValue(), row.entry.calibration);
        values[row.entry.slot] = value;
        row.internal.textContent = Number.isFinite(value) ? displayNumber(value, 7) : text.invalid;
    }
    for (const [index, node] of model.nodes.entries()) {
        if (!node) continue;
        let sum = 0;
        for (const [source, weight] of node.incoming) sum += values[source] * weight;
        sum += node.bias;
        values[index] = Number.isFinite(sum) ? activate(node.activation, sum) : NaN;
    }
    const rawValues = outputs.map(row => unscale(values[row.entry.slot], row.entry.calibration));
    if (!values.every(Number.isFinite) || !rawValues.every(Number.isFinite)) {
        for (const row of outputs) {
            row.raw.textContent = row.internal.textContent = "–";
            row.fill.style.width = "0%";
            row.indicator.removeAttribute("aria-valuenow");
            row.indicator.removeAttribute("title");
            if (row.entry.binary) row.indicator.textContent = "–";
        }
        if (updateCharacteristic) updateCharacteristic(null);
        statusLine.textContent = text.error;
        return;
    }
    outputs.forEach((row, index) => showOutput(row, values[row.entry.slot], rawValues[index]));
    if (updateCharacteristic) updateCharacteristic(rawValues);
    statusLine.textContent = "";
}

calculate();
</script>
</body>
</html>
''')

