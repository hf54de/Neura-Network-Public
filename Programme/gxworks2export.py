# -------------------------------------------------------------------------------------------------
# Datei: gxworks2export.py
# Zweck: Erzeugt GX-Works2-Deklarationen und Structured Text aus einem trainierten Netzwerk.
# Letzte Änderung: 02.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math
import re
import unicodedata
from pathlib import Path

from neurontype import NeuronType
from trainingdataio import TrainingDataIO


class GxWorks2ExportGenerator:
    """Übersetzt ein NeuronNetz-Modell in einen Mitsubishi-GX-Works2-FB."""

    MAX_LABEL_LENGTH = 32
    RESERVED_WORDS = {
        "AND", "ARRAY", "BOOL", "BY", "CASE", "CONSTANT", "DINT", "DO",
        "ELSE", "ELSIF", "END_CASE", "END_FOR", "END_IF", "END_VAR",
        "END_WHILE", "EXIT", "FALSE", "FOR", "FUNCTION", "FUNCTION_BLOCK",
        "IF", "INT", "MOD", "NOT", "OF", "OR", "PROGRAM", "REAL", "REPEAT",
        "RETURN", "THEN", "TO", "TRUE", "UNTIL", "VAR", "VAR_CONSTANT",
        "VAR_INPUT", "VAR_IN_OUT", "VAR_OUTPUT", "VAR_RETAIN", "WHILE", "XOR",
    }

    def __init__(
        self,
        network,
        input_mappings,
        output_mappings,
        project_name="NeuronNetz",
        language_code="de",
    ):
        self.network = network
        self.input_mappings = list(input_mappings or [])
        self.output_mappings = list(output_mappings or [])
        self.project_name = str(project_name or "NeuronNetz")
        self.language_code = "de" if str(language_code).lower() == "de" else "en"
        self.used_labels = set()
        self.rows = []
        self.input_labels = {}
        self.output_labels = {}
        self.neuron_output_labels = {}
        self.neuron_sum_labels = {}
        self.bias_labels = {}
        self.weight_labels = {}
        self.calibration_labels = {}
        self.exp_result_label = None

    @property
    def german(self):
        return self.language_code == "de"

    def text(self, german, english):
        return german if self.german else english

    @staticmethod
    def float_literal(value):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Gewichte, Bias und Skalierungswerte müssen endlich sein.")
        if value == 0.0:
            return "0.0"
        result = format(value, ".9g").replace("e", "E")
        if "." not in result and "E" not in result:
            result += ".0"
        return result

    @classmethod
    def identifier_text(cls, value, fallback="Label"):
        text = str(value or "").strip()
        replacements = {
            "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ä": "ae", "ö": "oe",
            "ü": "ue", "ß": "ss", "µ": "u", "°": "Grad",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^A-Za-z0-9_]", "_", text)
        text = re.sub(r"_+", "_", text).strip("_") or fallback
        if text[0].isdigit():
            text = "N_" + text
        if text.upper() in cls.RESERVED_WORDS:
            text = "NN_" + text
        return text[:cls.MAX_LABEL_LENGTH]

    def unique_label(self, value, fallback="Label"):
        base = self.identifier_text(value, fallback)
        candidate = base
        number = 2
        while candidate.casefold() in self.used_labels:
            suffix = f"_{number}"
            candidate = base[: self.MAX_LABEL_LENGTH - len(suffix)] + suffix
            number += 1
        self.used_labels.add(candidate.casefold())
        return candidate

    def add_row(self, label_class, name, data_type, constant="", comment=""):
        self.rows.append([
            str(label_class), str(name), str(data_type), str(constant), str(comment)
        ])

    def calibration_constants(self, external_label, mapping, role):
        calibration = TrainingDataIO.normalize_calibration(mapping.get("calibration"))
        mode = calibration["mode"]
        labels = {"mode": mode}
        prefix = "In" if role == "input" else "Out"
        descriptions = {
            "source_min": self.text("Untergrenze der Rohwerte", "Raw-value lower limit"),
            "source_max": self.text("Obergrenze der Rohwerte", "Raw-value upper limit"),
            "mean": self.text("Mittelwert der Standardisierung", "Standardization mean"),
            "stddev": self.text("Standardabweichung", "Standard deviation"),
        }
        keys = ()
        if mode in ("minmax_0_1", "minmax_minus1_1"):
            keys = ("source_min", "source_max")
        elif mode == "standard":
            keys = ("mean", "stddev")
        for key in keys:
            suffix = {
                "source_min": "Min", "source_max": "Max", "mean": "Mean", "stddev": "Std"
            }[key]
            label = self.unique_label(f"K_{prefix}_{external_label}_{suffix}", "K_Wert")
            labels[key] = label
            self.add_row(
                "VAR_CONSTANT", label, "REAL", self.float_literal(calibration[key]),
                descriptions[key],
            )
        return labels

    def prepare_labels(self):
        input_by_id = {mapping["neuron"].id: mapping for mapping in self.input_mappings}
        output_by_id = {mapping["neuron"].id: mapping for mapping in self.output_mappings}
        inputs = self.network.get_input_neurons()
        outputs = self.network.get_output_neurons()
        if {neuron.id for neuron in inputs} != set(input_by_id):
            raise ValueError(self.text(
                "Nicht alle Eingangsneuronen sind Trainingsspalten zugeordnet.",
                "Not all input neurons are assigned to training columns.",
            ))
        if {neuron.id for neuron in outputs} != set(output_by_id):
            raise ValueError(self.text(
                "Nicht alle Ausgangsneuronen sind Trainingsspalten zugeordnet.",
                "Not all output neurons are assigned to training columns.",
            ))

        for neuron in inputs:
            mapping = input_by_id[neuron.id]
            label = self.unique_label(mapping.get("column_name") or neuron.name, "Eingang")
            self.input_labels[neuron.id] = label
            data_type = "BOOL" if mapping.get("data_type") == "binary" else "REAL"
            self.add_row(
                "VAR_INPUT", label, data_type, "",
                self.text("Eingang des neuronalen Netzes", "Neural-network input"),
            )

        for neuron in outputs:
            mapping = output_by_id[neuron.id]
            label = self.unique_label(mapping.get("column_name") or neuron.name, "Ausgang")
            self.output_labels[neuron.id] = label
            data_type = "BOOL" if mapping.get("data_type") == "binary" else "REAL"
            self.add_row(
                "VAR_OUTPUT", label, data_type, "",
                self.text("Ausgang des neuronalen Netzes", "Neural-network output"),
            )

        for neuron in inputs:
            mapping = input_by_id[neuron.id]
            external = self.input_labels[neuron.id]
            self.calibration_labels[("input", neuron.id)] = self.calibration_constants(
                external, mapping, "input"
            )
        for neuron in outputs:
            mapping = output_by_id[neuron.id]
            external = self.output_labels[neuron.id]
            self.calibration_labels[("output", neuron.id)] = self.calibration_constants(
                external, mapping, "output"
            )

        calculation_neurons = [
            neuron for neuron in self.network.get_topological_order()
            if neuron.neuron_type != NeuronType.INPUT
        ]
        for neuron in calculation_neurons:
            neuron_id = self.identifier_text(neuron.id, "Neuron")
            bias_label = self.unique_label(f"B_{neuron_id}", "Bias")
            self.bias_labels[neuron.id] = bias_label
            self.add_row(
                "VAR_CONSTANT", bias_label, "REAL", self.float_literal(neuron.bias),
                self.text(f"Bias von {neuron.name}", f"Bias of {neuron.name}"),
            )

        for connection in self.network.get_connections():
            source_id = self.identifier_text(connection.source_neuron.id, "Quelle")
            target_id = self.identifier_text(connection.target_neuron.id, "Ziel")
            label = self.unique_label(f"W_{source_id}_{target_id}", "Gewicht")
            self.weight_labels[connection.id] = label
            self.add_row(
                "VAR_CONSTANT", label, "REAL", self.float_literal(connection.weight),
                self.text(
                    f"Gewicht {connection.source_neuron.name} zu {connection.target_neuron.name}",
                    f"Weight {connection.source_neuron.name} to {connection.target_neuron.name}",
                ),
            )

        for neuron in self.network.get_topological_order():
            neuron_id = self.identifier_text(neuron.id, "Neuron")
            output_label = self.unique_label(f"N_{neuron_id}_Out", "Neuron_Out")
            self.neuron_output_labels[neuron.id] = output_label
            self.add_row(
                "VAR", output_label, "REAL", "",
                self.text(f"Interner Wert von {neuron.name}", f"Internal value of {neuron.name}"),
            )
            if neuron.neuron_type != NeuronType.INPUT:
                sum_label = self.unique_label(f"N_{neuron_id}_Sum", "Neuron_Sum")
                self.neuron_sum_labels[neuron.id] = sum_label
                self.add_row(
                    "VAR", sum_label, "REAL", "",
                    self.text(f"Gewichtete Summe von {neuron.name}", f"Weighted sum of {neuron.name}"),
                )

        if any(
            neuron.activation_function in ("Sigmoid", "Tanh")
            for neuron in calculation_neurons
        ):
            self.exp_result_label = self.unique_label("EXP_Ergebnis", "EXP_Result")
            self.add_row(
                "VAR", self.exp_result_label, "REAL", "",
                self.text("Hilfswert der Exponentialfunktion", "Exponential-function helper value"),
            )

    def scaling_lines(self, target, source, labels, binary=False, inverse=False):
        if binary:
            return [
                f"IF {source} THEN",
                f"    {target} := 1.0;",
                "ELSE",
                f"    {target} := 0.0;",
                "END_IF;",
            ]
        mode = labels["mode"]
        if mode == "none":
            return [f"{target} := {source};"]
        if mode == "minmax_0_1":
            if inverse:
                return [
                    f"{target} := {labels['source_min']}",
                    f"    + {source} * ({labels['source_max']} - {labels['source_min']});",
                ]
            return [
                f"{target} := ({source} - {labels['source_min']})",
                f"    / ({labels['source_max']} - {labels['source_min']});",
            ]
        if mode == "minmax_minus1_1":
            if inverse:
                return [
                    f"{target} := {labels['source_min']}",
                    f"    + (({source} + 1.0) / 2.0)",
                    f"    * ({labels['source_max']} - {labels['source_min']});",
                ]
            return [
                f"{target} := (({source} - {labels['source_min']})",
                f"    / ({labels['source_max']} - {labels['source_min']})) * 2.0 - 1.0;",
            ]
        if inverse:
            return [f"{target} := {source} * {labels['stddev']} + {labels['mean']};"]
        return [f"{target} := ({source} - {labels['mean']}) / {labels['stddev']};"]

    def activation_lines(self, activation, sum_label, output_label):
        if activation == "Linear":
            return [f"{output_label} := {sum_label};"]
        if activation == "ReLU":
            return [
                f"IF {sum_label} > 0.0 THEN",
                f"    {output_label} := {sum_label};",
                "ELSE",
                f"    {output_label} := 0.0;",
                "END_IF;",
            ]
        if activation == "Sigmoid":
            return [
                f"IF {sum_label} >= 0.0 THEN",
                f"    EXP(TRUE, -1.0 * {sum_label}, {self.exp_result_label});",
                f"    {output_label} := 1.0 / (1.0 + {self.exp_result_label});",
                "ELSE",
                f"    EXP(TRUE, {sum_label}, {self.exp_result_label});",
                f"    {output_label} := {self.exp_result_label}",
                f"        / (1.0 + {self.exp_result_label});",
                "END_IF;",
            ]
        if activation == "Tanh":
            return [
                f"IF {sum_label} >= 0.0 THEN",
                f"    EXP(TRUE, -2.0 * {sum_label}, {self.exp_result_label});",
                f"    {output_label} := (1.0 - {self.exp_result_label})",
                f"        / (1.0 + {self.exp_result_label});",
                "ELSE",
                f"    EXP(TRUE, 2.0 * {sum_label}, {self.exp_result_label});",
                f"    {output_label} := ({self.exp_result_label} - 1.0)",
                f"        / ({self.exp_result_label} + 1.0);",
                "END_IF;",
            ]
        raise ValueError(self.text(
            f"Aktivierungsfunktion '{activation}' wird von GX Works2 nicht unterstützt.",
            f"Activation function '{activation}' is not supported by GX Works2.",
        ))

    def generate_code(self):
        project = Path(self.project_name).stem
        lines = [
            "(*",
            self.text("    Automatisch erzeugt mit NeuronNetz", "    Automatically generated with NeuronNetz"),
            f"    {self.text('Projekt', 'Project')}: {project}",
            "    Zielsystem: Mitsubishi GX Works2",
            "",
            self.text(
                "    Der Baustein führt ausschließlich die Vorwärtsberechnung aus.",
                "    This function block performs forward calculation only.",
            ),
            "*)",
            "",
            "",
            "(* -------------------------------------------------- *)",
            self.text("(* 1. Eingangswerte vorbereiten                    *)", "(* 1. Prepare input values                         *)"),
            "(* -------------------------------------------------- *)",
            "",
        ]
        input_by_id = {mapping["neuron"].id: mapping for mapping in self.input_mappings}
        for neuron in self.network.get_input_neurons():
            mapping = input_by_id[neuron.id]
            lines.append(f"(* {mapping.get('column_name') or neuron.name} *)")
            lines.extend(self.scaling_lines(
                self.neuron_output_labels[neuron.id],
                self.input_labels[neuron.id],
                self.calibration_labels[("input", neuron.id)],
                binary=mapping.get("data_type") == "binary",
            ))
            lines.append("")

        layers = [
            [neuron for neuron in layer if neuron.neuron_type != NeuronType.INPUT]
            for layer in self.network.get_topological_layers()
        ]
        layers = [layer for layer in layers if layer]
        for layer_index, layer in enumerate(layers, start=1):
            lines.extend([
                "",
                "(* -------------------------------------------------- *)",
                self.text(
                    f"(* {layer_index + 1}. Netzwerkschicht {layer_index} berechnen              *)",
                    f"(* {layer_index + 1}. Calculate network layer {layer_index}                *)",
                ),
                "(* -------------------------------------------------- *)",
                "",
            ])
            for neuron in layer:
                sum_label = self.neuron_sum_labels[neuron.id]
                incoming = sorted(neuron.incoming_connections, key=lambda item: item.id)
                lines.append(f"(* {neuron.name} *)")
                lines.append(f"{sum_label} :=")
                for index, connection in enumerate(incoming):
                    operator = "      " if index == 0 else "    + "
                    source = self.neuron_output_labels[connection.source_neuron.id]
                    weight = self.weight_labels[connection.id]
                    lines.append(f"{operator}{source} * {weight}")
                lines.append(f"    + {self.bias_labels[neuron.id]};")
                lines.append("")
                lines.extend(self.activation_lines(
                    neuron.activation_function,
                    sum_label,
                    self.neuron_output_labels[neuron.id],
                ))
                lines.append("")

        lines.extend([
            "",
            "(* -------------------------------------------------- *)",
            self.text("(* Ausgangswerte ausgeben                            *)", "(* Write output values                              *)"),
            "(* -------------------------------------------------- *)",
            "",
        ])
        output_by_id = {mapping["neuron"].id: mapping for mapping in self.output_mappings}
        for neuron in self.network.get_output_neurons():
            mapping = output_by_id[neuron.id]
            external = self.output_labels[neuron.id]
            internal = self.neuron_output_labels[neuron.id]
            lines.append(f"(* {mapping.get('column_name') or neuron.name} *)")
            if mapping.get("data_type") == "binary":
                lines.extend([
                    f"IF {internal} >= 0.5 THEN",
                    f"    {external} := TRUE;",
                    "ELSE",
                    f"    {external} := FALSE;",
                    "END_IF;",
                ])
            else:
                lines.extend(self.scaling_lines(
                    external,
                    internal,
                    self.calibration_labels[("output", neuron.id)],
                    inverse=True,
                ))
            lines.append("")
        return "\r\n".join(lines).rstrip() + "\r\n"

    def generate(self):
        validation = self.network.validate_network()
        if not validation.get("valid"):
            raise ValueError("\n".join(validation.get("errors") or []))
        self.prepare_labels()
        return {
            "fb_name": self.identifier_text(f"FB_{Path(self.project_name).stem}", "FB_NeuronNetz"),
            "declarations": self.rows,
            "code": self.generate_code(),
        }
