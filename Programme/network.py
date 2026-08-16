# -------------------------------------------------------------------------------------------------
# Datei: network.py
# Zweck: Verwaltet das neuronale Netzwerk und führt Vorwärtsberechnungen aus.
# Letzte Änderung: 08.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math

from PySide6.QtCore import QObject, Signal

from activationfunctions import ActivationFunctions
from connection import Connection
from neuron import Neuron
from neurontype import NeuronType
from numberformat import format_number
from topology import NetworkTopology
from trainer import BackpropagationTrainer


class NeuralNetwork(QObject):
    """
    Verwaltet die Neuronen und Verbindungen
    eines neuronalen Netzwerkes.

    Zuständig für:
        - Verwaltung der Neuronen
        - Verwaltung der Verbindungen
        - Prüfung der Netzwerkstruktur
        - Vorwärtsberechnung
        - Schnittstelle zum Training

    Die Analyse der Graphstruktur übernimmt
    NetworkTopology.

    Die mathematischen Aktivierungsfunktionen
    übernimmt ActivationFunctions.

    Backpropagation und einzelne Trainingsschritte
    übernimmt BackpropagationTrainer.

    Noch nicht zuständig für:
        - grafische Darstellung
        - Trainingsdatensätze und Epochensteuerung
        - SPS-Export
    """

    neuron_added = Signal(object)
    neuron_removed = Signal(object)

    connection_added = Signal(object)
    connection_removed = Signal(object)

    network_cleared = Signal()

    def __init__(self):

        super().__init__()

        self.neurons = {}
        self.connections = {}

        self.topology = NetworkTopology(
            self
        )

        self.trainer = BackpropagationTrainer(
            self
        )
        self._prepared_training_order = None

    def prepare_training_calculation(self):
        """Prüft die feste Struktur einmal und merkt ihre Rechenreihenfolge."""

        validation_result = self.validate_network()
        if not validation_result["valid"]:
            error_text = "\n".join(validation_result["errors"])
            raise ValueError(
                "Das Netzwerk kann nicht trainiert werden:\n"
                f"{error_text}"
            )
        self._prepared_training_order = tuple(self.get_topological_order())

    def clear_prepared_training_calculation(self):
        """Verwirft den ausschließlich für einen Trainingsabschnitt gültigen Plan."""

        self._prepared_training_order = None

    def has_prepared_training_calculation(self):
        return self._prepared_training_order is not None

    def prepared_training_order(self):
        return self._prepared_training_order

    def add_neuron(self, neuron):
        """
        Fügt ein Neuron zum Netzwerk hinzu.
        """

        self.clear_prepared_training_calculation()
        if not isinstance(neuron, Neuron):
            raise TypeError(
                "Es können nur Objekte vom Typ Neuron hinzugefügt werden."
            )

        if neuron.id in self.neurons:
            raise ValueError(
                f"Die Neuronen-ID {neuron.id} ist bereits vorhanden."
            )

        self.neurons[neuron.id] = neuron

        self.neuron_added.emit(neuron)

    def remove_neuron(self, neuron):
        """
        Entfernt ein Neuron sowie alle damit
        verbundenen Verbindungen aus dem Netzwerk.
        """

        self.clear_prepared_training_calculation()
        if not isinstance(neuron, Neuron):
            raise TypeError(
                "Es können nur Objekte vom Typ Neuron entfernt werden."
            )

        if neuron.id not in self.neurons:
            return

        connected_items = list(
            dict.fromkeys(
                neuron.incoming_connections
                + neuron.outgoing_connections
            )
        )

        for connection in connected_items:
            self.remove_connection(connection)

        del self.neurons[neuron.id]
        self.trainer.normalize_momentum_state()

        self.neuron_removed.emit(neuron)

    def add_connection(self, connection):
        """
        Fügt eine Verbindung zum Netzwerk hinzu.
        """

        self.clear_prepared_training_calculation()
        if not isinstance(connection, Connection):
            raise TypeError(
                "Es können nur Objekte vom Typ Connection "
                "hinzugefügt werden."
            )

        if connection.id in self.connections:
            raise ValueError(
                f"Die Verbindungs-ID {connection.id} "
                "ist bereits vorhanden."
            )

        if connection.source_neuron.id not in self.neurons:
            raise ValueError(
                "Das Startneuron ist nicht Bestandteil "
                "des Netzwerkes."
            )

        if connection.target_neuron.id not in self.neurons:
            raise ValueError(
                "Das Zielneuron ist nicht Bestandteil "
                "des Netzwerkes."
            )

        if self.connection_exists(
            connection.source_neuron,
            connection.target_neuron
        ):
            raise ValueError(
                "Zwischen diesen Neuronen besteht bereits "
                "eine Verbindung in derselben Richtung."
            )

        self.connections[connection.id] = connection

        self.connection_added.emit(connection)

    def remove_connection(self, connection):
        """
        Entfernt eine Verbindung aus dem Netzwerk.
        """

        self.clear_prepared_training_calculation()
        if not isinstance(connection, Connection):
            raise TypeError(
                "Es können nur Objekte vom Typ Connection "
                "entfernt werden."
            )

        if connection.id not in self.connections:
            return

        connection.disconnect()

        del self.connections[connection.id]
        self.trainer.normalize_momentum_state()

        self.connection_removed.emit(connection)

    def get_neuron(self, neuron_id):
        """
        Liefert ein Neuron anhand seiner ID.
        """

        return self.neurons.get(neuron_id)

    def get_connection(self, connection_id):
        """
        Liefert eine Verbindung anhand ihrer ID.
        """

        return self.connections.get(connection_id)

    def get_neurons(self):
        """
        Liefert alle Neuronen nach ID sortiert.
        """

        return [
            self.neurons[neuron_id]
            for neuron_id in sorted(self.neurons)
        ]

    def get_connections(self):
        """
        Liefert alle Verbindungen nach ID sortiert.
        """

        return [
            self.connections[connection_id]
            for connection_id in sorted(self.connections)
        ]

    def get_input_neurons(self):
        """
        Liefert alle Input-Neuronen nach ID sortiert.
        """

        return self.topology.get_input_neurons()

    def get_hidden_neurons(self):
        """
        Liefert alle Hidden-Neuronen nach ID sortiert.
        """

        return self.topology.get_hidden_neurons()

    def get_output_neurons(self):
        """
        Liefert alle Output-Neuronen nach ID sortiert.
        """

        return self.topology.get_output_neurons()

    def get_isolated_neurons(self):
        """
        Liefert alle Neuronen ohne eingehende
        und ohne ausgehende Verbindung.
        """

        return [
            neuron
            for neuron in self.get_neurons()
            if (
                not neuron.incoming_connections
                and not neuron.outgoing_connections
            )
        ]

    def connection_exists(
        self,
        source_neuron,
        target_neuron
    ):
        """
        Prüft, ob bereits eine gerichtete Verbindung
        zwischen zwei Neuronen vorhanden ist.
        """

        for connection in self.connections.values():
            if (
                connection.source_neuron is source_neuron
                and connection.target_neuron is target_neuron
            ):
                return True

        return False

    def get_reachable_neurons_from_inputs(self):
        """
        Liefert alle Neuronen, die von mindestens
        einem Input-Neuron aus erreichbar sind.
        """

        return self.topology.get_reachable_neurons()

    def has_complete_input_output_path(self):
        """
        Prüft, ob mindestens ein vollständiger gerichteter
        Pfad von einem Input-Neuron zu einem Output-Neuron besteht.
        """

        return self.topology.has_complete_input_output_path()

    def get_topological_order(self):
        """
        Liefert die Neuronen in einer gültigen
        topologischen Berechnungsreihenfolge.
        """

        return self.topology.get_topological_order()

    def get_topological_layers(self):
        """
        Liefert die Neuronen gruppiert nach
        topologischen Ebenen.
        """

        return self.topology.get_topological_layers()

    def has_cycles(self):
        """
        Prüft, ob das Netzwerk eine gerichtete Schleife enthält.
        """

        return self.topology.has_cycles()

    def apply_activation(
        self,
        activation_function,
        value
    ):
        """
        Wendet die angegebene Aktivierungsfunktion
        auf einen Wert an.

        Diese Methode bleibt als Schnittstelle des
        Netzwerkes erhalten und delegiert die Berechnung
        an ActivationFunctions.
        """

        return ActivationFunctions.apply(
            activation_function,
            value
        )

    def get_activation_derivative(
        self,
        activation_function,
        value
    ):
        """
        Liefert die Ableitung einer Aktivierungsfunktion.

        Der übergebene Wert ist der Summenwert Σ
        vor Anwendung der Aktivierungsfunktion.
        """

        return ActivationFunctions.derivative(
            activation_function,
            value
        )

    def set_learning_rate(
        self,
        learning_rate
    ):
        """
        Setzt die Lernrate des Trainers.
        """

        self.trainer.set_learning_rate(
            learning_rate
        )

    def get_learning_rate(self):
        """
        Liefert die aktuelle Lernrate.
        """

        return self.trainer.learning_rate

    def set_momentum(self, momentum):
        """Setzt den Momentumfaktor des Trainers."""
        self.trainer.set_momentum(momentum)

    def get_momentum(self):
        """Liefert den Momentumfaktor des Trainers."""
        return self.trainer.momentum

    def reset_momentum_state(self):
        """Löscht die Bewegungszustände für einen neuen Trainingslauf."""
        self.trainer.reset_momentum_state()

    def get_momentum_state(self):
        """Liefert die gespeicherten Bewegungszustände."""
        return self.trainer.get_momentum_state()

    def restore_momentum_state(self, state):
        """Stellt kompatible Bewegungszustände wieder her."""
        self.trainer.restore_momentum_state(state)

    def calculate_training_deltas(
        self,
        target_values
    ):
        """
        Berechnet Fehler und Deltas für die
        angegebenen Sollwerte.

        Voraussetzung:
            Der Forward Pass wurde bereits ausgeführt.
        """

        return self.trainer.calculate_deltas(
            target_values
        )

    def apply_training_gradients(self):
        """
        Aktualisiert Gewichte und Bias-Werte anhand
        der zuletzt berechneten Deltas.
        """

        return self.trainer.apply_gradients()

    def train_step(
        self,
        target_values
    ):
        """
        Führt genau einen vollständigen
        Trainingsschritt aus.
        """

        return self.trainer.train_step(
            target_values
        )

    def reset_training_values(self):
        """
        Setzt die vom Trainer verwalteten
        Laufzeitwerte zurück.
        """

        self.trainer.clear_runtime_values()

    def get_calculation_details(self, neuron, translator=None):
        """
        Liefert die Mathematik des letzten Rechenzustands eines Neurons.
        """

        def text(key, default, **values):
            if callable(translator):
                return translator(key, **values)
            return default.format(**values)

        if not isinstance(neuron, Neuron):
            raise TypeError(
                text(
                    "math.details.invalid_neuron",
                    "Der Rechenweg kann nur für ein Neuron erzeugt werden."
                )
            )

        if neuron.neuron_type == NeuronType.INPUT:
            return (
                text("math.details.input", "EINGANG") + "\n"
                "=======\n\n"
                f"X = {format_number(neuron.input_value)}\n\n"
                + text(
                    "math.details.input_direct",
                    "Ein Input-Neuron übernimmt den Eingang direkt:"
                ) + "\n"
                "Y = X\n"
                f"Y = {format_number(neuron.output_value)}"
            )

        incoming_connections = sorted(
            neuron.incoming_connections,
            key=lambda connection: connection.id
        )

        calculation_lines = [
            text("math.report.weighted_sum", "GEWICHTETE SUMME"),
            "=================",
            "",
            text(
                "math.formula.weighted_sum",
                "Σ = Summe(YQuelle × Gewicht) + Bias"
            ),
            ""
        ]

        for connection in incoming_connections:
            source_neuron = connection.source_neuron
            contribution = (
                source_neuron.output_value
                * connection.weight
            )

            calculation_lines.append(
                f"{source_neuron.name}.Y × W{connection.id}"
            )
            calculation_lines.append(
                f"= {format_number(source_neuron.output_value)} × "
                f"{format_number(connection.weight)}"
            )
            calculation_lines.append(
                f"= {format_number(contribution)}"
            )
            calculation_lines.append("")

        calculation_lines.append(
            f"Bias = {format_number(neuron.bias)}"
        )
        calculation_lines.append(
            f"Σ = {format_number(neuron.sum_value)}"
        )
        calculation_lines.append(
            ""
        )
        calculation_lines.extend(
            [
                text("math.report.activation", "AKTIVIERUNG"),
                "===========",
                ""
            ]
        )

        activation_formulas = {
            "Linear": "Y = Σ",
            "ReLU": "Y = max(0, Σ)",
            "Sigmoid": "Y = 1 / (1 + e^(-Σ))",
            "Tanh": "Y = tanh(Σ)"
        }
        calculation_lines.append(
            activation_formulas.get(
                neuron.activation_function,
                f"Y = {neuron.activation_function}(Σ)"
            )
        )
        calculation_lines.append(
            f"Σ = {format_number(neuron.sum_value)}"
        )
        calculation_lines.append(
            f"Y = {format_number(neuron.output_value)}"
        )

        calculation_lines.extend(
            [
                "",
                text("math.details.last_step", "LETZTER LERNSCHRITT"),
                "====================",
                ""
            ]
        )

        last_step = self.trainer.last_step_details or {}
        neuron_step = last_step.get(
            "neurons",
            {}
        ).get(
            neuron.id
        )

        if neuron_step is None:
            calculation_lines.extend(
                [
                    text(
                        "math.details.no_step",
                        "Noch kein Lernschritt vorhanden."
                    ),
                    text(
                        "math.details.no_step_hint_1",
                        "Nach einem Trainings- oder Debugschritt erscheinen"
                    ),
                    text(
                        "math.details.no_step_hint_2",
                        "hier Fehler, Ableitung und Delta."
                    )
                ]
            )

            return "\n".join(calculation_lines)

        derivative = self.get_activation_derivative(
            neuron_step["activation"],
            neuron_step["sum"]
        )
        derivative_formulas = {
            "Linear": "f'(Σ) = 1",
            "ReLU": text(
                "math.formula.relu_derivative",
                "f'(Σ) = 1 für Σ > 0, sonst 0"
            ),
            "Sigmoid": "f'(Σ) = Y × (1 - Y)",
            "Tanh": "f'(Σ) = 1 - Y²"
        }
        calculation_lines.extend(
            [
                derivative_formulas.get(
                    neuron_step["activation"],
                    "f'(Σ)"
                ),
                f"f'(Σ) = {format_number(derivative)}"
            ]
        )

        if neuron_step["neuron_type"] == NeuronType.OUTPUT:
            calculation_lines.extend(
                [
                    "",
                    text(
                        "math.formula.output_error",
                        "Fehler = Sollwert - Istwert"
                    ),
                    f"= {format_number(neuron_step['target'])} - "
                    f"{format_number(neuron_step['output'])}",
                    f"= {format_number(neuron_step['error'])}",
                    "",
                    text(
                        "math.formula.output_delta",
                        "δ = Fehler × f'(Σ)"
                    ),
                    f"= {format_number(neuron_step['error'])} × "
                    f"{format_number(derivative)}",
                    f"= {format_number(neuron_step['delta'])}"
                ]
            )

        else:
            weighted_delta_sum = 0.0
            calculation_lines.extend(
                [
                    "",
                    text(
                        "math.formula.backward_sum",
                        "Rückwärtssumme = Summe(W × δZiel)"
                    ),
                    ""
                ]
            )

            connection_steps = last_step.get(
                "connections",
                {}
            )

            for connection_id, connection_step in sorted(
                connection_steps.items()
            ):
                if connection_step["source_id"] != neuron.id:
                    continue

                contribution = (
                    connection_step["weight_before"]
                    * connection_step["target_delta"]
                )
                weighted_delta_sum += contribution
                calculation_lines.append(
                    f"W{connection_id} × "
                    f"δ({connection_step['target_name']})"
                )
                calculation_lines.append(
                    f"= {format_number(connection_step['weight_before'])} × "
                    f"{format_number(connection_step['target_delta'])}"
                )
                calculation_lines.append(
                    f"= {format_number(contribution)}"
                )
                calculation_lines.append("")

            calculation_lines.extend(
                [
                    text(
                        "math.formula.hidden_delta",
                        "δ = Rückwärtssumme × f'(Σ)"
                    ),
                    f"= {format_number(weighted_delta_sum)} × "
                    f"{format_number(derivative)}",
                    f"= {format_number(neuron_step['delta'])}"
                ]
            )

        learning_rate = last_step["learning_rate"]
        bias_change = neuron_step["bias_update"]
        bias_gradient = neuron_step.get("bias_gradient_update", bias_change)
        bias_previous_velocity = neuron_step.get("bias_previous_velocity", 0.0)
        bias_momentum_term = neuron_step.get("bias_momentum_term", 0.0)
        calculation_lines.extend(
            [
                "",
                text("math.details.bias_rule", "BIAS-LERNREGEL"),
                "==============",
                "",
                text(
                    "math.formula.bias_update",
                    "ΔB = Lernrate × δ"
                ),
                f"= {format_number(learning_rate)} × "
                f"{format_number(neuron_step['delta'])}",
                text("math.momentum.gradient", "Gradient = {value}", value=format_number(bias_gradient)),
                text("math.momentum.previous", "v vorher = {value}", value=format_number(bias_previous_velocity)),
                text("math.momentum.contribution", "Momentumanteil = {value}", value=format_number(bias_momentum_term)),
                text("math.momentum.new_velocity", "v neu = {value}", value=format_number(bias_change)),
                "",
                "Bneu = B + ΔB",
                f"= {format_number(neuron_step['bias_before'])} + "
                f"{format_number(bias_change)}",
                f"= {format_number(neuron_step['bias_before'] + bias_change)}"
            ]
        )

        return "\n".join(
            calculation_lines
        )

    def get_connection_calculation_details(self, connection, translator=None):
        """Liefert Vorwärtsbeitrag und Lernregel einer Verbindung."""

        def text(key, default, **values):
            if callable(translator):
                return translator(key, **values)
            return default.format(**values)

        if not isinstance(connection, Connection):
            raise TypeError(
                text(
                    "math.details.invalid_connection",
                    "Der Rechenweg kann nur für eine Verbindung erzeugt werden."
                )
            )

        source = connection.source_neuron
        target = connection.target_neuron
        contribution = source.output_value * connection.weight
        last_step = self.trainer.last_step_details or {}

        lines = [
            text("math.details.forward_contribution", "VORWÄRTSBEITRAG"),
            "===============",
            "",
            f"{source.name}.Y × W{connection.id}",
            f"= {format_number(source.output_value)} × "
            f"{format_number(connection.weight)}",
            f"= {format_number(contribution)}",
            "",
            text(
                "math.details.contribution_target",
                "Dieser Wert fließt in Σ von {target} ein.",
                target=target.name
            ),
            "",
            text("math.details.last_step", "LETZTER LERNSCHRITT"),
            "====================",
            "",
            text(
                "math.formula.weight_update",
                "ΔW = Lernrate × δZiel × YQuelle"
            )
        ]

        connection_step = last_step.get(
            "connections",
            {}
        ).get(
            connection.id
        )

        if connection_step is None:
            lines.extend(
                [
                    "",
                    text(
                        "math.details.no_connection_step",
                        "Noch kein Lernschritt für diese Verbindung vorhanden."
                    ),
                    text(
                        "math.details.no_connection_step_hint_1",
                        "Nach einem Trainings- oder Debugschritt werden"
                    ),
                    text(
                        "math.details.no_connection_step_hint_2",
                        "die Zahlen in die Lernregel eingesetzt."
                    )
                ]
            )

            return "\n".join(lines)

        learning_rate = last_step["learning_rate"]
        weight_change = connection_step["weight_update"]
        weight_gradient = connection_step.get(
            "weight_gradient_update", weight_change
        )
        previous_velocity = connection_step.get(
            "weight_previous_velocity", 0.0
        )
        momentum_term = connection_step.get("weight_momentum_term", 0.0)
        lines.extend(
            [
                f"= {format_number(learning_rate)} × "
                f"{format_number(connection_step['target_delta'])} × "
                f"{format_number(connection_step['source_output'])}",
                text("math.momentum.gradient", "Gradient = {value}", value=format_number(weight_gradient)),
                text("math.momentum.previous", "v vorher = {value}", value=format_number(previous_velocity)),
                text("math.momentum.contribution", "Momentumanteil = {value}", value=format_number(momentum_term)),
                text("math.momentum.new_velocity", "v neu = {value}", value=format_number(weight_change)),
                "",
                "Wneu = W + ΔW",
                f"= {format_number(connection_step['weight_before'])} + "
                f"{format_number(weight_change)}",
                f"= {format_number(connection_step['weight_before'] + weight_change)}"
            ]
        )

        return "\n".join(lines)

    def forward_pass(self):
        """
        Führt eine vollständige Vorwärtsberechnung durch.

        Input-Neuronen:
            Y = Eingabewert

        Hidden- und Output-Neuronen:
            Summe = Summe(Y_vorher * Gewicht) + Bias
            Y = Aktivierungsfunktion(Summe)

        Rückgabewert:
            Liste aller Output-Neuronen nach ID sortiert.
        """

        calculation_order = self.prepared_training_order()
        if calculation_order is None:
            validation_result = self.validate_network()

            if not validation_result["valid"]:
                error_text = "\n".join(
                    validation_result["errors"]
                )

                raise ValueError(
                    "Das Netzwerk kann nicht berechnet werden:\n"
                    f"{error_text}"
                )

            calculation_order = self.get_topological_order()

        for neuron in calculation_order:
            if neuron.neuron_type == NeuronType.INPUT:
                if not math.isfinite(neuron.input_value):
                    raise ValueError(
                        f"Input-Neuron {neuron.name} enthält keinen "
                        "endlichen Eingangswert."
                    )

                neuron.sum_value = 0.0
                neuron.output_value = neuron.input_value
                neuron.error_value = 0.0
                if self.trainer.visual_updates_enabled:
                    neuron.update()
                continue

            weighted_sum = 0.0

            for connection in neuron.incoming_connections:
                source_output = (
                    connection.source_neuron.output_value
                )

                weighted_sum += (
                    source_output
                    * connection.weight
                )

            neuron.sum_value = (
                weighted_sum
                + neuron.bias
            )

            if not math.isfinite(neuron.sum_value):
                raise ValueError(
                    f"Die Berechnung von Neuron {neuron.name} ist "
                    "numerisch instabil geworden. Prüfen Sie Skalierung "
                    "und Lernrate."
                )

            neuron.output_value = self.apply_activation(
                neuron.activation_function,
                neuron.sum_value
            )

            if not math.isfinite(neuron.output_value):
                raise ValueError(
                    f"Neuron {neuron.name} hat keinen endlichen "
                    "Ausgabewert erzeugt."
                )

            neuron.error_value = 0.0
            if self.trainer.visual_updates_enabled:
                neuron.update()

        return self.get_output_neurons()

    def reset_runtime_values(self):
        """
        Setzt die Laufzeitwerte aller Neuronen zurück.
        """

        for neuron in self.get_neurons():
            neuron.reset_runtime_values()

    def validate_network(
        self,
        check_parameters=True,
        translator=None
    ):
        """
        Prüft die grundlegende Struktur des Netzwerkes.

        Die Fehlermeldungen werden in folgender
        Reihenfolge aufgebaut:

            1. Grundstruktur
            2. Anschlüsse einzelner Neuronen
            3. Erreichbarkeit
            4. Gesamtnetz und Schleifen

        Rückgabewert:
            Dictionary mit:
                - valid
                - errors
                - input_count
                - hidden_count
                - output_count
                - connection_count
        """

        def text(key, default, **values):
            if callable(translator):
                return translator(key, **values)
            return default.format(**values)

        errors = []

        input_neurons = self.get_input_neurons()
        hidden_neurons = self.get_hidden_neurons()
        output_neurons = self.get_output_neurons()

        if check_parameters:
            for neuron in hidden_neurons + output_neurons:
                if not math.isfinite(neuron.bias):
                    errors.append(text(
                        "network.validation.invalid_bias",
                        "Neuron {neuron} besitzt einen ungültigen Bias-Wert (NaN oder unendlich).",
                        neuron=neuron.name
                    ))

        # 1. Grundstruktur
        if not self.neurons:
            errors.append(text("network.validation.no_neurons", "Das Netzwerk enthält keine Neuronen."))

        if not input_neurons:
            errors.append(text("network.validation.no_input", "Das Netzwerk enthält kein Input-Neuron."))

        if not output_neurons:
            errors.append(text("network.validation.no_output", "Das Netzwerk enthält kein Output-Neuron."))

        # 2. Anschlüsse einzelner Neuronen
        for neuron in input_neurons:
            if neuron.incoming_connections:
                errors.append(text("network.validation.input_incoming", "Input-Neuron {neuron} besitzt mindestens eine eingehende Verbindung.", neuron=neuron.name))

        for neuron in hidden_neurons:
            if not neuron.incoming_connections:
                errors.append(text("network.validation.hidden_no_incoming", "Hidden-Neuron {neuron} besitzt keine eingehende Verbindung.", neuron=neuron.name))

            if not neuron.outgoing_connections:
                errors.append(text("network.validation.hidden_no_outgoing", "Hidden-Neuron {neuron} besitzt keine ausgehende Verbindung.", neuron=neuron.name))

        for neuron in output_neurons:
            if not neuron.incoming_connections:
                errors.append(text("network.validation.output_no_incoming", "Output-Neuron {neuron} besitzt keine eingehende Verbindung.", neuron=neuron.name))

            if neuron.outgoing_connections:
                errors.append(text("network.validation.output_outgoing", "Output-Neuron {neuron} besitzt mindestens eine ausgehende Verbindung.", neuron=neuron.name))

        # Verbindungen auf interne Konsistenz prüfen
        existing_neurons = set(
            self.neurons.values()
        )

        connection_pairs = set()

        for connection in self.get_connections():
            if (
                check_parameters
                and not math.isfinite(connection.weight)
            ):
                errors.append(text("network.validation.invalid_weight", "Verbindung {connection} von {source} nach {target} besitzt ein ungültiges Gewicht (NaN oder unendlich).", connection=connection.id, source=connection.source_neuron.name, target=connection.target_neuron.name))

            if connection.source_neuron not in existing_neurons:
                errors.append(text("network.validation.missing_source", "Verbindung {connection} verweist auf ein nicht vorhandenes Startneuron.", connection=connection.id))

            if connection.target_neuron not in existing_neurons:
                errors.append(text("network.validation.missing_target", "Verbindung {connection} verweist auf ein nicht vorhandenes Zielneuron.", connection=connection.id))

            connection_pair = (
                connection.source_neuron.id,
                connection.target_neuron.id
            )

            if connection_pair in connection_pairs:
                errors.append(text("network.validation.duplicate_connection", "Die Verbindung von {source} nach {target} ist mehrfach vorhanden.", source=connection.source_neuron.name, target=connection.target_neuron.name))

            else:
                connection_pairs.add(
                    connection_pair
                )

        # 3. Erreichbarkeit
        if input_neurons:
            reachable_neurons = (
                self.get_reachable_neurons_from_inputs()
            )

            for neuron in self.get_neurons():
                if (
                    neuron.neuron_type != NeuronType.INPUT
                    and neuron not in reachable_neurons
                ):
                    errors.append(text("network.validation.unreachable", "Neuron {neuron} ist von keinem Input-Neuron aus erreichbar.", neuron=neuron.name))

        # 4. Gesamtnetz
        if (
            input_neurons
            and output_neurons
            and not self.has_complete_input_output_path()
        ):
            errors.append(text("network.validation.no_complete_path", "Es besteht kein vollständiger Pfad von einem Input-Neuron zu einem Output-Neuron."))

        if self.neurons and self.has_cycles():
            errors.append(text("network.validation.cycle", "Das Netzwerk enthält mindestens eine gerichtete Schleife."))

        return {
            "valid": not errors,
            "errors": errors,
            "input_count": len(input_neurons),
            "hidden_count": len(hidden_neurons),
            "output_count": len(output_neurons),
            "connection_count": len(self.connections)
        }

    def clear(self):
        """
        Entfernt alle Neuronen und Verbindungen
        aus dem Netzwerk.
        """

        self.clear_prepared_training_calculation()
        self.trainer.clear_runtime_values()

        for connection in list(
            self.connections.values()
        ):
            connection.disconnect()

        self.connections.clear()
        self.neurons.clear()
        self.trainer.reset_momentum_state()

        self.network_cleared.emit()

    def neuron_count(self):
        """
        Liefert die Anzahl der Neuronen.
        """

        return len(self.neurons)

    def connection_count(self):
        """
        Liefert die Anzahl der Verbindungen.
        """

        return len(self.connections)
