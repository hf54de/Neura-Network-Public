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
body { margin: 0; color: #171717; background: #f0f0f0; font: 12px "Segoe UI", sans-serif; }
.viewport { max-height: 100vh; overflow: auto; }
main { min-width: 722px; }
.content { padding: 10px 12px 12px; }
fieldset { min-width: 0; margin: 0 4px 12px; padding: 9px 9px 11px; border: 1px solid #777; border-radius: 5px; }
legend { padding: 0 2px; }
.grid {
    display: grid;
    grid-template-columns: 102px 135px 111px 81px 101px minmax(140px, 1fr);
    row-gap: 7px;
    grid-template-rows: 16px;
    grid-auto-rows: minmax(22px, auto);
    align-items: center;
}
#outputs { row-gap: 6px; grid-auto-rows: minmax(20px, auto); }
.heading, .name, .value, .scaling { padding-right: 7px; }
.heading { white-space: nowrap; }
.name { overflow: hidden; white-space: nowrap; }
.value, .range, input[type=number] { font: 11px "Courier New", monospace; }
.value, .scaling { overflow-wrap: anywhere; }
.range { display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1.6fr); padding-right: 5px; }
.range span { overflow-wrap: anywhere; }
.range span:nth-child(2), .no-slider { text-align: center; }
.number {
    display: flex; align-items: center; min-width: 0; width: calc(100% - 8px);
    height: 21px; background: #f9f9f9; border: 1px solid #dedede;
    border-bottom-color: #878787; border-radius: 4px;
}
.number:focus-within { outline: 1px solid #707070; }
.number input { width: 100%; min-width: 0; border: 0; padding: 0 4px; background: transparent; outline: none; }
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
.unit { margin-right: 4px; font: 11px "Courier New", monospace; overflow-wrap: anywhere; }
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
#status { margin: 3px 0 0; line-height: 1.45; }
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

function sliderPosition(entry, grid, value) {
    if (grid) {
        return grid.count === 0n ? 0 : Number(roundRatio(gridIndex(grid, value) * BigInt(grid.positions), grid.count));
    }
    if (entry.minimum === entry.maximum) return 0;
    return Math.round((value - entry.minimum) / (entry.maximum - entry.minimum) * 1000);
}

function sliderValue(entry, grid, position) {
    if (grid) {
        const index = grid.positions ? roundRatio(BigInt(position) * grid.count, BigInt(grid.positions)) : 0n;
        return gridValue(grid, index);
    }
    return entry.minimum + position / 1000 * (entry.maximum - entry.minimum);
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
        const slider = element("input");
        slider.type = "range";
        slider.min = 0;
        slider.max = stepGrid ? stepGrid.positions : 1000;
        slider.step = 1;
        slider.disabled = entry.maximum <= entry.minimum;
        slider.setAttribute("aria-label", entry.name + " – " + model.inputHeaders[5]);
        slider.value = sliderPosition(entry, stepGrid, entry.value);
        sliderCell = slider;

        let value = entry.value;
        function update(candidate, commit) {
            if (Number.isFinite(candidate)) {
                const bounded = clamp(candidate, entry.minimum, entry.maximum);
                value = stepGrid ? gridValue(stepGrid, gridIndex(stepGrid, bounded)) : Number(bounded.toFixed(10));
                slider.value = sliderPosition(entry, stepGrid, value);
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
        slider.addEventListener("input", () => update(sliderValue(entry, stepGrid, slider.valueAsNumber), true));
        readValue = () => value;
    }
    grid.append(nameLabel(entry.name), valueCell, internal, element("div", "scaling", entry.scaling),
        rangeLabel(entry), sliderCell);
    return { entry, internal, readValue, setChecked };
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

const inputGrid = createGrid("inputs", model.inputHeaders);
const outputGrid = createGrid("outputs", model.outputHeaders);
const inputs = model.inputs.map(entry => createInput(inputGrid, entry));
const outputs = model.outputs.map(entry => createOutput(outputGrid, entry));
if (model.inputArray) createArrayView(model.inputArray);

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
        statusLine.textContent = text.error;
        return;
    }
    outputs.forEach((row, index) => showOutput(row, values[row.entry.slot], rawValues[index]));
    statusLine.textContent = text.completed;
}

calculate();
</script>
</body>
</html>
''')

