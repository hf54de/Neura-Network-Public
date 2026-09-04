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
import hashlib
import json
from datetime import datetime
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
        application_version="",
        training_entry=None,
        model_version="",
        export_options=None,
    ):
        self.network = network
        self.input_mappings = list(input_mappings or [])
        self.output_mappings = list(output_mappings or [])
        self.project_name = str(project_name or "NeuronNetz")
        self.language_code = "de" if str(language_code).lower() == "de" else "en"
        self.application_version = str(application_version or "").strip()
        self.training_entry = dict(training_entry or {})
        self.model_version = str(model_version or "").strip() or (
            f"Run-{self.training_entry.get('run_id')}"
            if self.training_entry.get("run_id") is not None else "1.0"
        )
        defaults = {
            "enable": True,
            "network_active": True,
            "range_check": True,
            "range_tolerance_input": True,
            "range_error": True,
            "invalid_input_number": True,
            "fallback": True,
            "hold_last_output": True,
        }
        defaults.update(dict(export_options or {}))
        self.export_options = defaults
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
        self.fallback_labels = {}

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

        self.used_labels.update(name.casefold() for name in (
            "Enable", "Enable_Range_Check", "Range_Tolerance_Percent", "Hold_Last_Output",
            "Network_Active", "Input_Range_Error", "Invalid_Input_Number", "Model_Version", "Model_Signature",
            "Input_Range_Error_Internal",
        ))
        options = self.export_options
        trigger_available = options["enable"] or options["range_check"]
        if options["enable"]:
            self.add_row("VAR_INPUT", "Enable", "BOOL", "TRUE", self.text(
            "Netzberechnung freigeben (keine Sicherheitsfunktion)",
            "Enable network calculation (not a safety function)",
            ))
        if options["range_check"]:
            self.add_row("VAR_INPUT", "Enable_Range_Check", "BOOL", "FALSE", self.text(
            "Plausibilitätsprüfung aktivieren", "Enable plausibility checking",
            ))
            tolerance_class = "VAR_INPUT" if options["range_tolerance_input"] else "VAR_CONSTANT"
            self.add_row(tolerance_class, "Range_Tolerance_Percent", "REAL", "10.0", self.text(
            "Toleranz außerhalb des Trainingsbereichs in Prozent", "Tolerance outside training range in percent",
            ))
        if options["fallback"] and options["hold_last_output"] and trigger_available:
            self.add_row("VAR_INPUT", "Hold_Last_Output", "BOOL", "FALSE", self.text(
            "Letzten Ausgang bei Sperre oder Fehler halten", "Hold last output when disabled or invalid",
            ))
        if options["network_active"] and trigger_available:
            self.add_row("VAR_OUTPUT", "Network_Active", "BOOL", "", self.text(
            "Netzberechnung aktiv", "Network calculation active",
            ))
        if options["range_check"] and options["range_error"]:
            self.add_row("VAR_OUTPUT", "Input_Range_Error", "BOOL", "", self.text(
            "Eingang außerhalb des zulässigen Bereichs", "Input outside the permitted range",
            ))
        elif options["range_check"]:
            self.add_row("VAR", "Input_Range_Error_Internal", "BOOL", "", self.text(
                "Interner Status der Eingangsprüfung", "Internal input-check status",
            ))
        if options["range_check"] and options["range_error"] and options["invalid_input_number"]:
            self.add_row("VAR_OUTPUT", "Invalid_Input_Number", "INT", "", self.text(
            "Index des ersten unplausiblen Eingangs", "Index of first implausible input",
            ))
        safe_version = self.model_version.replace("'", "''")[:48]
        self.add_row("VAR_CONSTANT", "Model_Version", "STRING", f"'{safe_version}'", self.text(
            "Vom Anwender vergebene Modellversion", "User-assigned model version",
        ))
        self.add_row("VAR_CONSTANT", "Model_Signature", "STRING", f"'{self.model_signature()}'", self.text(
            "Automatische Kennung von Struktur und Parametern",
            "Automatic signature of structure and parameters",
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
            if options["fallback"] and trigger_available:
                fallback = self.unique_label(f"Fallback_{label}", "Fallback_Output")
                self.fallback_labels[neuron.id] = fallback
                self.add_row(
                    "VAR_INPUT", fallback, data_type,
                    "FALSE" if data_type == "BOOL" else "0.0",
                    self.text(f"Ersatzwert für {label}", f"Fallback value for {label}"),
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
        architecture = "-".join(
            str(len(layer)) for layer in self.network.get_topological_layers()
        )
        activations = sorted({
            neuron.activation_function
            for neuron in self.network.get_neurons()
            if neuron.neuron_type != NeuronType.INPUT
        })
        lines = [
            "(*",
            self.text("    Automatisch erzeugt mit NeuronNetz", "    Automatically generated with NeuronNetz"),
            f"    {self.text('Projekt', 'Project')}: {project}",
            "    Zielsystem: Mitsubishi GX Works2",
            f"    {self.text('Exportdatum', 'Export date')}: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"    NeuronNetz: {self.application_version or '-'}",
            f"    {self.text('Modellversion', 'Model version')}: {self.model_version}",
            f"    {self.text('Modellkennung', 'Model signature')}: {self.model_signature()}",
            f"    {self.text('Netzarchitektur', 'Network architecture')}: {architecture}",
            f"    {self.text('Aktivierungen', 'Activations')}: {', '.join(activations)}",
            f"    {self.text('Trainingslauf', 'Training run')}: {self.training_entry.get('run_id', '-')}",
            f"    {self.text('Epochen', 'Epochs')}: {self.training_entry.get('completed_epochs', '-')}",
            f"    {self.text('Endfehler', 'Final error')}: {self.training_entry.get('end_error', '-')}",
            "",
            self.text(
                "    Der Baustein führt ausschließlich die Vorwärtsberechnung aus.",
                "    This function block performs forward calculation only.",
            ),
            self.text(
                "    Sicherheit: Vor produktivem Einsatz durch eine qualifizierte Fachkraft",
                "    Safety: Review, test, and approve the code for the specific installation",
            ),
            self.text(
                "    für die konkrete Anlage prüfen, testen und freigeben lassen.",
                "    by a qualified professional before production use.",
            ),
            self.text(
                "    Keine Sicherheits- oder Not-Aus-Funktion; der Anwender trägt die",
                "    Not a safety or emergency-stop function; the user is responsible for",
            ),
            self.text(
                "    Verantwortung für Integration, Validierung und Risikobeurteilung.",
                "    integration, validation, and risk assessment.",
            ),
            "*)",
            "",
        ]
        options = self.export_options
        error_label = "Input_Range_Error" if options["range_error"] else "Input_Range_Error_Internal"
        input_by_id = {mapping["neuron"].id: mapping for mapping in self.input_mappings}
        guarded_input_count = 0
        if options["range_check"]:
            lines.append(f"{error_label} := FALSE;")
            if options["range_error"] and options["invalid_input_number"]:
                lines.append("Invalid_Input_Number := 0;")
            lines.append("IF Enable_Range_Check THEN")
            for input_index, neuron in enumerate(self.network.get_input_neurons(), start=1):
                mapping = input_by_id[neuron.id]
                calibration = TrainingDataIO.normalize_calibration(mapping.get("calibration"))
                if mapping.get("data_type") == "binary" or calibration["mode"] not in (
                    "minmax_0_1", "minmax_minus1_1"
                ):
                    continue
                guarded_input_count += 1
                source = self.input_labels[neuron.id]
                labels = self.calibration_labels[("input", neuron.id)]
                minimum, maximum = labels["source_min"], labels["source_max"]
                lines.extend([
                    f"    IF ({source} < ({minimum} - (Range_Tolerance_Percent / 100.0) * ({maximum} - {minimum})))",
                    f"        OR ({source} > ({maximum} + (Range_Tolerance_Percent / 100.0) * ({maximum} - {minimum}))) THEN",
                    f"        {error_label} := TRUE;",
                ])
                if options["range_error"] and options["invalid_input_number"]:
                    lines.extend([
                        "        IF Invalid_Input_Number = 0 THEN",
                        f"            Invalid_Input_Number := {input_index};",
                        "        END_IF;",
                    ])
                lines.append("    END_IF;")
            if guarded_input_count:
                lines.extend(["END_IF;", ""])
            else:
                lines.pop()

        conditions = []
        if options["enable"]:
            conditions.append("Enable")
        if options["range_check"]:
            conditions.append(f"NOT {error_label}")
        if conditions:
            lines.append(f"IF {' AND '.join(conditions)} THEN")
        if options["network_active"] and conditions:
            lines.extend(["Network_Active := TRUE;", ""])
        lines.extend([
            "(* -------------------------------------------------- *)",
            self.text("(* 1. Eingangswerte vorbereiten                    *)", "(* 1. Prepare input values                         *)"),
            "(* -------------------------------------------------- *)",
            "",
        ])
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
        if conditions:
            lines.append("ELSE")
            if options["network_active"]:
                lines.append("    Network_Active := FALSE;")
            if options["fallback"]:
                if options["hold_last_output"]:
                    lines.append("    IF NOT Hold_Last_Output THEN")
                    assignment_indent = "        "
                else:
                    assignment_indent = "    "
                for neuron in self.network.get_output_neurons():
                    lines.append(
                        f"{assignment_indent}{self.output_labels[neuron.id]} := {self.fallback_labels[neuron.id]};"
                    )
                if options["hold_last_output"]:
                    lines.append("    END_IF;")
            lines.extend(["END_IF;", ""])
        return "\r\n".join(lines).rstrip() + "\r\n"

    def model_signature(self):
        payload = {
            "neurons": [(n.id, n.bias, n.activation_function) for n in self.network.get_neurons()],
            "connections": [
                (c.id, c.source_neuron.id, c.target_neuron.id, c.weight)
                for c in self.network.get_connections()
            ],
            "inputs": [mapping.get("calibration") for mapping in self.input_mappings],
            "outputs": [mapping.get("calibration") for mapping in self.output_mappings],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16].upper()

    def operation_summary(self):
        calculated = [
            neuron for neuron in self.network.get_neurons()
            if neuron.neuron_type != NeuronType.INPUT
        ]
        connections = len(self.network.get_connections())
        exp_calls = sum(
            neuron.activation_function in ("Sigmoid", "Tanh")
            for neuron in calculated
        )
        return {
            "multiplications": connections,
            "additions": connections + len(calculated),
            "exp_calls": exp_calls,
            "estimated_operations": connections * 2 + len(calculated) + exp_calls * 20,
        }

    def generate(self):
        validation = self.network.validate_network()
        if not validation.get("valid"):
            raise ValueError("\n".join(validation.get("errors") or []))
        self.prepare_labels()
        return {
            "fb_name": self.identifier_text(f"FB_{Path(self.project_name).stem}", "FB_NeuronNetz"),
            "target_system": "Mitsubishi GX Works2",
            "headers": ("Class", "Label Name", "Data Type", "Constant", "Comment"),
            "declarations": self.rows,
            "code": self.generate_code(),
            "model_version": self.model_version,
            "model_signature": self.model_signature(),
            "operation_summary": self.operation_summary(),
            "complete_export_format": "gxworks2_asc",
            "complete_export_label_de": "Vollständige ASC-Datei speichern…",
            "complete_export_label_en": "Save complete ASC file…",
        }
