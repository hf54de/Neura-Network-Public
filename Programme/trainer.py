# -------------------------------------------------------------------------------------------------
# Datei: trainer.py
# Zweck: Trainiert neuronale Netzwerke durch Fehlerrückführung.
# Letzte Änderung: 08.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math

from neurontype import NeuronType


class BackpropagationTrainer:
    """
    Führt Backpropagation für ein vorhandenes
    neuronales Netzwerk aus.

    Zuständig für:
        - Sollwerte der Output-Neuronen
        - Fehlerberechnung
        - Delta-Berechnung
        - Aktualisierung von Gewichten
        - Aktualisierung von Bias-Werten
        - einen einzelnen Trainingsschritt

    Nicht zuständig:
        - Trainingsdatensätze
        - Epochensteuerung
        - grafische Darstellung
        - Speichern und Laden
    """

    def __init__(
        self,
        network,
        learning_rate=0.01,
        momentum=0.0
    ):

        self.network = network
        self.learning_rate = float(
            learning_rate
        )
        self.momentum = 0.0
        self.set_momentum(momentum)

        if (
            not math.isfinite(self.learning_rate)
            or self.learning_rate <= 0.0
        ):
            raise ValueError(
                "Die Lernrate muss größer als null sein."
            )

        self.target_values = {}
        self.error_values = {}
        self.delta_values = {}
        self.last_step_details = None
        self.capture_step_details = True
        self.visual_updates_enabled = True
        self.connection_velocities = {}
        self.bias_velocities = {}

    def set_learning_rate(
        self,
        learning_rate
    ):
        """
        Setzt die Lernrate.
        """

        learning_rate = float(
            learning_rate
        )

        if (
            not math.isfinite(learning_rate)
            or learning_rate <= 0.0
        ):
            raise ValueError(
                "Die Lernrate muss größer als null sein."
            )

        self.learning_rate = learning_rate

    def set_momentum(self, momentum):
        """Setzt den klassischen Momentumfaktor zwischen 0 und 0,99."""

        momentum = float(momentum)
        if not math.isfinite(momentum) or not 0.0 <= momentum <= 0.99:
            raise ValueError(
                "Das Momentum muss zwischen 0 und 0,99 liegen."
            )
        self.momentum = momentum

    def reset_momentum_state(self):
        """Beginnt einen neuen Trainingslauf ohne frühere Bewegungsanteile."""

        self.connection_velocities.clear()
        self.bias_velocities.clear()

    def normalize_momentum_state(self):
        """Entfernt Zustände, deren Netzparameter nicht mehr vorhanden sind."""

        connection_ids = {
            connection.id for connection in self.network.get_connections()
        }
        bias_ids = {
            neuron.id for neuron in self.network.get_neurons()
            if neuron.neuron_type != NeuronType.INPUT
        }
        self.connection_velocities = {
            connection_id: float(value)
            for connection_id, value in self.connection_velocities.items()
            if connection_id in connection_ids and math.isfinite(float(value))
        }
        self.bias_velocities = {
            neuron_id: float(value)
            for neuron_id, value in self.bias_velocities.items()
            if neuron_id in bias_ids and math.isfinite(float(value))
        }

    def get_momentum_state(self):
        """Liefert eine JSON-taugliche Kopie der aktuellen Momentumzustände."""

        self.normalize_momentum_state()
        return {
            "connections": {
                str(connection_id): float(value)
                for connection_id, value in self.connection_velocities.items()
            },
            "biases": {
                str(neuron_id): float(value)
                for neuron_id, value in self.bias_velocities.items()
            },
        }

    def restore_momentum_state(self, state):
        """Stellt kompatible Zustände wieder her; alte Daten bedeuten null."""

        self.reset_momentum_state()
        if not isinstance(state, dict):
            return
        connection_values = state.get("connections", {})
        if not isinstance(connection_values, dict):
            connection_values = {}
        bias_values = state.get("biases", {})
        if not isinstance(bias_values, dict):
            bias_values = {}
        for key, value in connection_values.items():
            try:
                self.connection_velocities[int(key)] = float(value)
            except (TypeError, ValueError):
                continue
        for key, value in bias_values.items():
            try:
                self.bias_velocities[int(key)] = float(value)
            except (TypeError, ValueError):
                continue
        self.normalize_momentum_state()

    def clear_runtime_values(self):
        """
        Löscht die vom Trainer verwalteten
        Soll-, Fehler- und Delta-Werte.
        """

        self.target_values.clear()
        self.error_values.clear()
        self.delta_values.clear()

        for neuron in self.network.get_neurons():
            neuron.error_value = 0.0

            if hasattr(
                neuron,
                "target_value"
            ):
                neuron.target_value = 0.0

            if hasattr(
                neuron,
                "delta_value"
            ):
                neuron.delta_value = 0.0

            if self.visual_updates_enabled:
                neuron.update()

    def _resolve_output_targets(
        self,
        target_values
    ):
        """
        Prüft und vereinheitlicht die Sollwerte.

        Erwartet wird ein Dictionary:

            {
                output_neuron_id: sollwert
            }
        """

        if not isinstance(
            target_values,
            dict
        ):
            raise TypeError(
                "Die Sollwerte müssen als Dictionary "
                "übergeben werden."
            )

        output_neurons = self.network.get_output_neurons()

        expected_output_ids = {
            neuron.id
            for neuron in output_neurons
        }

        received_output_ids = set(
            target_values.keys()
        )

        missing_output_ids = (
            expected_output_ids
            - received_output_ids
        )

        unknown_output_ids = (
            received_output_ids
            - expected_output_ids
        )

        if missing_output_ids:
            missing_text = ", ".join(
                str(neuron_id)
                for neuron_id in sorted(
                    missing_output_ids
                )
            )

            raise ValueError(
                "Für folgende Output-Neuronen fehlt "
                f"ein Sollwert: {missing_text}"
            )

        if unknown_output_ids:
            unknown_text = ", ".join(
                str(neuron_id)
                for neuron_id in sorted(
                    unknown_output_ids
                )
            )

            raise ValueError(
                "Sollwerte wurden für unbekannte oder "
                "nicht als Output definierte Neuronen "
                f"angegeben: {unknown_text}"
            )

        resolved_targets = {}

        for neuron in output_neurons:
            target_value = float(
                target_values[neuron.id]
            )

            if not math.isfinite(target_value):
                raise ValueError(
                    f"Der Sollwert für {neuron.name} ist keine "
                    "endliche Zahl."
                )

            resolved_targets[neuron.id] = target_value

        return resolved_targets

    def calculate_deltas(
        self,
        target_values
    ):
        """
        Berechnet Fehler und Deltas für alle
        Hidden- und Output-Neuronen.

        Voraussetzung:
            Der Forward Pass wurde bereits ausgeführt.
        """

        validation_result = (
            None
            if self.network.has_prepared_training_calculation()
            else self.network.validate_network()
        )

        if validation_result is not None and not validation_result["valid"]:
            error_text = "\n".join(
                validation_result["errors"]
            )

            raise ValueError(
                "Backpropagation ist nicht möglich:\n"
                f"{error_text}"
            )

        self.target_values = self._resolve_output_targets(
            target_values
        )

        self.error_values.clear()
        self.delta_values.clear()

        output_neurons = self.network.get_output_neurons()

        for neuron in output_neurons:
            target_value = self.target_values[
                neuron.id
            ]

            error_value = (
                target_value
                - neuron.output_value
            )

            derivative = (
                self.network.get_activation_derivative(
                    neuron.activation_function,
                    neuron.sum_value
                )
            )

            delta_value = (
                error_value
                * derivative
            )

            if not all(
                math.isfinite(value)
                for value in (
                    neuron.output_value,
                    error_value,
                    derivative,
                    delta_value
                )
            ):
                raise ValueError(
                    f"Das Training ist bei Output-Neuron {neuron.name} "
                    "numerisch instabil geworden. Prüfen Sie Skalierung "
                    "und Lernrate."
                )

            self.error_values[
                neuron.id
            ] = error_value

            self.delta_values[
                neuron.id
            ] = delta_value

            neuron.target_value = target_value
            neuron.error_value = error_value
            neuron.delta_value = delta_value
            if self.visual_updates_enabled:
                neuron.update()

        calculation_order = self.network.prepared_training_order()
        if calculation_order is None:
            calculation_order = self.network.get_topological_order()

        for neuron in reversed(
            calculation_order
        ):
            if neuron.neuron_type != NeuronType.HIDDEN:
                continue

            weighted_delta_sum = 0.0

            for connection in neuron.outgoing_connections:
                target_neuron = connection.target_neuron

                weighted_delta_sum += (
                    connection.weight
                    * self.delta_values[
                        target_neuron.id
                    ]
                )

            derivative = (
                self.network.get_activation_derivative(
                    neuron.activation_function,
                    neuron.sum_value
                )
            )

            delta_value = (
                weighted_delta_sum
                * derivative
            )

            if not all(
                math.isfinite(value)
                for value in (
                    weighted_delta_sum,
                    derivative,
                    delta_value
                )
            ):
                raise ValueError(
                    f"Das Training ist bei Hidden-Neuron {neuron.name} "
                    "numerisch instabil geworden. Prüfen Sie Skalierung "
                    "und Lernrate."
                )

            self.error_values[
                neuron.id
            ] = weighted_delta_sum

            self.delta_values[
                neuron.id
            ] = delta_value

            neuron.error_value = weighted_delta_sum
            neuron.delta_value = delta_value
            if self.visual_updates_enabled:
                neuron.update()

        return {
            "targets": dict(
                self.target_values
            ),
            "errors": dict(
                self.error_values
            ),
            "deltas": dict(
                self.delta_values
            )
        }

    def apply_gradients(self):
        """
        Aktualisiert alle Gewichte und Bias-Werte
        anhand der zuvor berechneten Deltas.
        """

        if not self.delta_values:
            raise ValueError(
                "Es wurden noch keine Deltas berechnet."
            )

        connection_updates = {}
        bias_updates = {}
        connection_gradient_updates = {}
        bias_gradient_updates = {}
        previous_connection_velocities = {}
        previous_bias_velocities = {}
        self.normalize_momentum_state()

        for connection in self.network.get_connections():
            target_neuron = connection.target_neuron
            source_neuron = connection.source_neuron

            delta_weight = (
                self.learning_rate
                * self.delta_values[
                    target_neuron.id
                ]
                * source_neuron.output_value
            )

            connection_gradient_updates[connection.id] = delta_weight
            previous_velocity = self.connection_velocities.get(
                connection.id, 0.0
            )
            previous_connection_velocities[connection.id] = previous_velocity
            # Momentum 0 behält bewusst exakt den bisherigen Rechenweg.
            if self.momentum == 0.0:
                connection_updates[connection.id] = delta_weight
            else:
                connection_updates[connection.id] = (
                    delta_weight + self.momentum * previous_velocity
                )

            if not all(
                math.isfinite(value)
                for value in (
                    connection_updates[connection.id],
                    connection.weight + connection_updates[connection.id]
                )
            ):
                raise ValueError(
                    "Das Training wurde abgebrochen, bevor ein ungültiges "
                    f"Gewicht für Verbindung {connection.id} übernommen "
                    "werden konnte. Prüfen Sie Skalierung und Lernrate."
                )

        for neuron in self.network.get_neurons():
            if neuron.neuron_type == NeuronType.INPUT:
                continue

            delta_bias = (
                self.learning_rate
                * self.delta_values[
                    neuron.id
                ]
            )

            bias_gradient_updates[neuron.id] = delta_bias
            previous_velocity = self.bias_velocities.get(neuron.id, 0.0)
            previous_bias_velocities[neuron.id] = previous_velocity
            if self.momentum == 0.0:
                bias_updates[neuron.id] = delta_bias
            else:
                bias_updates[neuron.id] = (
                    delta_bias + self.momentum * previous_velocity
                )

            if not all(
                math.isfinite(value)
                for value in (
                    bias_updates[neuron.id],
                    neuron.bias + bias_updates[neuron.id]
                )
            ):
                raise ValueError(
                    "Das Training wurde abgebrochen, bevor ein ungültiger "
                    f"Bias für Neuron {neuron.name} übernommen werden "
                    "konnte. Prüfen Sie Skalierung und Lernrate."
                )

        # Der Schnappschuss entsteht vor der Parameteränderung. Dadurch kann
        # die Oberfläche den letzten Lernschritt später mit exakt den damals
        # verwendeten Zahlen erklären.
        self.last_step_details = {
            "learning_rate": self.learning_rate,
            "momentum": self.momentum,
            "neurons": {
                neuron.id: {
                    "neuron_type": neuron.neuron_type,
                    "activation": neuron.activation_function,
                    "sum": neuron.sum_value,
                    "output": neuron.output_value,
                    "target": neuron.target_value,
                    "error": neuron.error_value,
                    "delta": neuron.delta_value,
                    "bias_before": neuron.bias,
                    "bias_update": bias_updates.get(neuron.id),
                    "bias_gradient_update": bias_gradient_updates.get(neuron.id),
                    "bias_previous_velocity": previous_bias_velocities.get(
                        neuron.id, 0.0
                    ),
                    "bias_momentum_term": (
                        self.momentum
                        * previous_bias_velocities.get(neuron.id, 0.0)
                    )
                }
                for neuron in self.network.get_neurons()
            },
            "connections": {
                connection.id: {
                    "source_id": connection.source_neuron.id,
                    "source_name": connection.source_neuron.name,
                    "target_id": connection.target_neuron.id,
                    "target_name": connection.target_neuron.name,
                    "weight_before": connection.weight,
                    "weight_update": connection_updates[connection.id],
                    "weight_gradient_update": connection_gradient_updates[
                        connection.id
                    ],
                    "weight_previous_velocity": previous_connection_velocities[
                        connection.id
                    ],
                    "weight_momentum_term": (
                        self.momentum
                        * previous_connection_velocities[connection.id]
                    ),
                    "source_output": connection.source_neuron.output_value,
                    "target_delta": connection.target_neuron.delta_value
                }
                for connection in self.network.get_connections()
            }
        } if self.capture_step_details else None

        for connection in self.network.get_connections():
            connection.weight = (
                connection.weight
                + connection_updates[
                    connection.id
                ]
            )
            self.connection_velocities[connection.id] = (
                0.0 if self.momentum == 0.0
                else connection_updates[connection.id]
            )

        for neuron in self.network.get_neurons():
            if neuron.neuron_type == NeuronType.INPUT:
                continue

            neuron.bias = (
                neuron.bias
                + bias_updates[
                    neuron.id
                ]
            )
            self.bias_velocities[neuron.id] = (
                0.0 if self.momentum == 0.0 else bias_updates[neuron.id]
            )

            if self.visual_updates_enabled:
                neuron.update()

        return {
            "connection_updates": connection_updates,
            "bias_updates": bias_updates,
            "connection_gradient_updates": connection_gradient_updates,
            "bias_gradient_updates": bias_gradient_updates,
            "momentum": self.momentum,
        }

    def train_step(
        self,
        target_values
    ):
        """
        Führt genau einen Trainingsschritt aus:

            1. Forward Pass
            2. Fehler und Deltas
            3. Gewichte und Bias aktualisieren

        Die neuen Gewichte wirken sich erst beim
        nächsten Forward Pass auf die Ausgänge aus.
        """

        output_neurons = (
            self.network.forward_pass()
        )

        delta_result = self.calculate_deltas(
            target_values
        )

        update_result = self.apply_gradients()

        squared_error_sum = 0.0

        for neuron in output_neurons:
            error_value = self.error_values[
                neuron.id
            ]

            squared_error_sum += (
                error_value
                * error_value
            )

        mean_squared_error = (
            squared_error_sum
            / len(output_neurons)
        )

        if not math.isfinite(mean_squared_error):
            raise ValueError(
                "Das Training hat keinen endlichen Fehlerwert ergeben. "
                "Prüfen Sie Skalierung und Lernrate."
            )

        return {
            "learning_rate": self.learning_rate,
            "momentum": self.momentum,
            "mean_squared_error": mean_squared_error,
            "targets": delta_result["targets"],
            "errors": delta_result["errors"],
            "deltas": delta_result["deltas"],
            "connection_updates": (
                update_result[
                    "connection_updates"
                ]
            ),
            "bias_updates": (
                update_result[
                    "bias_updates"
                ]
            )
        }
