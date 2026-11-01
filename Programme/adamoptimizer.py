"""Isolated Adam update rule. Forward pass and backpropagation stay in the trainer."""
import math

BETA1 = 0.9
BETA2 = 0.999
EPSILON = 1e-8


def validate_optimizer_state(state):
    if state is None:
        return
    if not isinstance(state, dict) or state.get("solver") not in ("sgd", "adam"):
        raise ValueError("Invalid optimizer state.")
    if state["solver"] == "sgd":
        return
    step = state.get("step")
    if isinstance(step, bool) or not isinstance(step, int) or not 0 <= step <= 2**53:
        raise ValueError("Invalid Adam step counter.")
    for kind in ("connections", "biases"):
        values = state.get(kind)
        if not isinstance(values, dict):
            raise ValueError("Invalid Adam parameter states.")
        for key, moments in values.items():
            if not isinstance(key, str) or not key.isdecimal() or int(key) < 1 or str(int(key)) != key:
                raise ValueError("Invalid Adam parameter identifier.")
            if not isinstance(moments, dict) or set(moments) != {"m", "v"}:
                raise ValueError("Invalid Adam moments.")
            for name, value in moments.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Invalid Adam moment value.")
                if name == "v" and value < 0:
                    raise ValueError("Invalid Adam squared moment.")
                if step == 0 and value != 0:
                    raise ValueError("Nonzero Adam moments at step zero.")


class AdamOptimizer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.step = 0
        self.connections = {}
        self.biases = {}

    def state(self):
        return {"solver": "adam", "step": self.step,
                "connections": {str(k): dict(v) for k, v in self.connections.items()},
                "biases": {str(k): dict(v) for k, v in self.biases.items()}}

    def restore(self, state, connection_ids, bias_ids):
        validate_optimizer_state(state)
        if state is None or state["solver"] != "adam":
            raise ValueError("Missing Adam state.")
        connections = {int(k): dict(v) for k, v in state["connections"].items()}
        biases = {int(k): dict(v) for k, v in state["biases"].items()}
        if state["step"] > 0:
            if set(connections) != set(connection_ids) or set(biases) != set(bias_ids):
                raise ValueError("Adam state does not match the network.")
        elif (connections and set(connections) != set(connection_ids)) or (biases and set(biases) != set(bias_ids)):
            raise ValueError("Adam state does not match the network.")
        self.step, self.connections, self.biases = state["step"], connections, biases

    def propose(self, connection_gradients, bias_gradients, learning_rate):
        step = self.step + 1
        if step > 2**53:
            raise ValueError("Adam step counter exceeded.")
        updates, moments, details = {}, {}, {}
        for kind, gradients, previous in (("connections", connection_gradients, self.connections),
                                           ("biases", bias_gradients, self.biases)):
            updates[kind], moments[kind], details[kind] = {}, {}, {}
            for key, gradient in gradients.items():
                old = previous.get(key, {"m": 0.0, "v": 0.0})
                m = BETA1 * old["m"] + (1.0 - BETA1) * gradient
                v = BETA2 * old["v"] + (1.0 - BETA2) * gradient * gradient
                m_hat = m / (1.0 - BETA1**step)
                v_hat = v / (1.0 - BETA2**step)
                change = -learning_rate * m_hat / (math.sqrt(v_hat) + EPSILON)
                if not all(math.isfinite(value) for value in (gradient, m, v, m_hat, v_hat, change)):
                    raise ValueError("Nonfinite Adam update.")
                moments[kind][key] = {"m": m, "v": v}
                updates[kind][key] = change
                details[kind][key] = {"gradient": gradient, "m_before": old["m"], "v_before": old["v"],
                                      "m": m, "v": v, "m_hat": m_hat, "v_hat": v_hat,
                                      "step": step, "change": change}
        return step, updates, moments, details

    def commit(self, step, moments):
        self.step, self.connections, self.biases = step, moments["connections"], moments["biases"]


def adam_calculation_lines(detail, learning_rate, before, text, number):
    """Exact values from the last update, shared by Mathematics and Debug Training."""
    translator = text
    def text(key, **values):
        fallback = {"adam.math.heading": "ADAM · Schritt {step}",
                    "adam.math.parameter": "Parameter neu = {before} + ({change}) = {after}"}
        return translator(key, **values) if callable(translator) else fallback[key].format(**values)
    return [
        text("adam.math.heading", step=detail["step"]),
        f"g = {number(detail['gradient'])}",
        "β₁ = 0.9; β₂ = 0.999; ε = 1e-8",
        "m = β₁ × m_previous + (1 − β₁) × g",
        f"  = 0.9 × {number(detail['m_before'])} + 0.1 × {number(detail['gradient'])} = {number(detail['m'])}",
        "v = β₂ × v_previous + (1 − β₂) × g²",
        f"  = 0.999 × {number(detail['v_before'])} + 0.001 × ({number(detail['gradient'])})² = {number(detail['v'])}",
        "m_hat = m / (1 − β₁^t)",
        f"  = {number(detail['m'])} / (1 − 0.9^{detail['step']}) = {number(detail['m_hat'])}",
        "v_hat = v / (1 − β₂^t)",
        f"  = {number(detail['v'])} / (1 − 0.999^{detail['step']}) = {number(detail['v_hat'])}",
        "Δθ = −η × m_hat / (√v_hat + ε)",
        f"  = −{number(learning_rate)} × {number(detail['m_hat'])} / (√{number(detail['v_hat'])} + 1e-8) = {number(detail['change'])}",
        text("adam.math.parameter", before=number(before), change=number(detail["change"]),
             after=number(before + detail["change"])),
    ]
