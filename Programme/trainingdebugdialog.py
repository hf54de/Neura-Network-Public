# -------------------------------------------------------------------------------------------------
# Datei: trainingdebugdialog.py
# Zweck: Zeigt einen einzelnen Lernschritt mit allen Zwischenrechnungen.
# Letzte Änderung: 08.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout
)

from numberformat import format_number
from trainingdataio import TrainingDataIO
from language import LanguageManager


def format_debug_number(value):
    """Kompakte, für Rechenschritte ausreichend genaue Darstellung."""

    return format_number(value, 7)


def format_signed_debug_number(value):
    number = float(value)
    sign = "+" if number >= 0.0 else "-"
    return sign + format_debug_number(abs(number))


class TrainingDebugDialog(QDialog):
    """
    Untersucht einen einzelnen Trainingsdatensatz.

    Angezeigt werden:
        - Eingabewerte
        - Vorwärtswerte aller Neuronen
        - Sollwerte, Fehler und Deltas
        - Gewichtsänderungen
        - Bias-Änderungen
        - Ausgabe vor und nach der Parameteränderung

    Der beim Öffnen vorhandene Zustand von Gewichten
    und Bias-Werten kann wiederhergestellt werden.
    """

    def __init__(
        self,
        network,
        records,
        input_columns,
        output_columns,
        parent=None,
        language_manager=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.network = network
        self.records = records
        self.input_columns = input_columns
        self.output_columns = output_columns

        self.initial_weights = {
            connection.id: connection.weight
            for connection in self.network.get_connections()
        }

        self.initial_biases = {
            neuron.id: neuron.bias
            for neuron in self.network.get_neurons()
        }
        self.initial_momentum_state = self.network.get_momentum_state()

        self.setWindowTitle(
            self.t("debug.window.title")
        )

        self.resize(
            920,
            720
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.fixed_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )

        self.selection_group = QGroupBox(
            self.t("debug.record.group")
        )

        self.selection_layout = QFormLayout(
            self.selection_group
        )

        self.record_combo = QComboBox()

        for record_index, record in enumerate(
            self.records,
            start=1
        ):
            input_text = ", ".join(
                f"{mapping['column_name']}="
                f"{format_debug_number(record[mapping['column_index']])}"
                for mapping in self.input_columns
            )

            target_text = ", ".join(
                f"{mapping['column_name']}="
                f"{format_debug_number(record[mapping['column_index']])}"
                for mapping in self.output_columns
            )

            self.record_combo.addItem(
                f"{record_index}: {input_text} → {target_text}"
            )

        self.learning_rate = QDoubleSpinBox()
        self.learning_rate.setDecimals(
            6
        )
        self.learning_rate.setRange(
            0.000001,
            1000.0
        )
        self.learning_rate.setSingleStep(
            0.001
        )
        self.learning_rate.setValue(
            self.network.get_learning_rate()
        )

        self.momentum = QDoubleSpinBox()
        self.momentum.setDecimals(2)
        self.momentum.setRange(0.0, 0.99)
        self.momentum.setSingleStep(0.05)
        self.momentum.setValue(self.network.get_momentum())

        self.selection_layout.addRow(
            self.t("debug.record"),
            self.record_combo
        )

        self.selection_layout.addRow(
            self.t("debug.learning_rate"),
            self.learning_rate
        )
        self.selection_layout.addRow(
            self.t("debug.momentum"),
            self.momentum
        )

        self.button_layout = QHBoxLayout()

        self.forward_button = QPushButton(
            self.t("debug.button.forward_only")
        )

        self.step_button = QPushButton(
            self.t("debug.button.one_step")
        )

        self.ten_steps_button = QPushButton(
            self.t("debug.button.ten_steps")
        )

        self.restore_button = QPushButton(
            self.t("debug.button.restore")
        )

        self.button_layout.addWidget(
            self.forward_button
        )

        self.button_layout.addWidget(
            self.step_button
        )

        self.button_layout.addWidget(
            self.ten_steps_button
        )

        self.button_layout.addStretch()

        self.button_layout.addWidget(
            self.restore_button
        )

        self.report_label = QLabel(
            self.t("debug.report.info")
        )

        self.report_label.setWordWrap(
            True
        )

        self.report = QPlainTextEdit()
        self.report.setReadOnly(
            True
        )
        self.report.setFont(
            self.fixed_font
        )
        self.report.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.t("common.close"))

        self.button_box.rejected.connect(
            self.reject
        )

        self.forward_button.clicked.connect(
            self.calculate_forward_only
        )

        self.step_button.clicked.connect(
            lambda: self.execute_steps(1)
        )

        self.ten_steps_button.clicked.connect(
            lambda: self.execute_steps(10)
        )

        self.restore_button.clicked.connect(
            self.restore_initial_parameters
        )

        self.record_combo.currentIndexChanged.connect(
            self.calculate_forward_only
        )

        self.main_layout.addWidget(
            self.selection_group
        )

        self.main_layout.addLayout(
            self.button_layout
        )

        self.main_layout.addWidget(
            self.report_label
        )

        self.main_layout.addWidget(
            self.report,
            1
        )

        self.main_layout.addWidget(
            self.button_box
        )

        self.calculate_forward_only()

    def get_selected_record(self):
        """
        Liefert den aktuell ausgewählten Datensatz.
        """

        record_index = self.record_combo.currentIndex()

        if (
            record_index < 0
            or record_index >= len(self.records)
        ):
            raise ValueError(
                self.t("debug.validation.no_record")
            )

        return self.records[
            record_index
        ]

    def apply_record(
        self,
        record
    ):
        """
        Legt den ausgewählten Datensatz am Netzwerk an.
        """

        for mapping in self.input_columns:
            neuron = mapping["neuron"]

            neuron.input_value = TrainingDataIO.scale_value(
                record[mapping["column_index"]],
                mapping["calibration"],
                self.t
            )

            neuron.update()

        target_values = {}

        for mapping in self.output_columns:
            neuron = mapping["neuron"]

            target_values[
                neuron.id
            ] = TrainingDataIO.scale_value(
                record[mapping["column_index"]],
                mapping["calibration"],
                self.t
            )

        return target_values

    def format_neuron_values(
        self,
        title
    ):
        """
        Formatiert die aktuellen Laufzeitwerte aller Neuronen.
        """

        lines = [
            title,
            "-" * len(title)
        ]

        for neuron in self.network.get_topological_order():
            lines.append(
                self.t(
                    "debug.report.neuron_values",
                    neuron=f"{neuron.name:<16}",
                    sum=f"{format_debug_number(neuron.sum_value):>12}",
                    output=f"{format_debug_number(neuron.output_value):>12}",
                    error=f"{format_debug_number(neuron.error_value):>12}",
                    delta=f"{format_debug_number(neuron.delta_value):>12}"
                )
            )

        return lines

    def calculate_forward_only(self):
        """
        Berechnet den ausgewählten Datensatz ohne Lernen.
        """

        try:
            record = self.get_selected_record()

            self.network.reset_runtime_values()

            target_values = self.apply_record(
                record
            )

            self.network.forward_pass()

            lines = [
                self.t("debug.report.forward_only"),
                "=" * 34,
                ""
            ]

            for mapping in self.input_columns:
                neuron = mapping["neuron"]

                lines.append(
                    f"Input  {mapping['column_name']}: "
                    f"{format_debug_number(neuron.input_value)} "
                    f"→ {neuron.name}.X"
                )

            lines.append(
                ""
            )

            lines.extend(
                self.format_neuron_values(
                    self.t("debug.report.runtime_values")
                )
            )

            lines.append(
                ""
            )

            lines.append(
                self.t("debug.report.output_comparison")
            )

            lines.append(
                "---------------"
            )

            squared_error_sum = 0.0

            for mapping in self.output_columns:
                neuron = mapping["neuron"]
                target_value = target_values[
                    neuron.id
                ]
                error_value = (
                    target_value
                    - neuron.output_value
                )

                squared_error_sum += (
                    error_value
                    * error_value
                )

                lines.append(
                    self.t(
                        "debug.report.output_values",
                        column=f"{mapping['column_name']:<16}",
                        target=f"{format_debug_number(target_value):>12}",
                        actual=f"{format_debug_number(neuron.output_value):>12}",
                        error=f"{format_debug_number(error_value):>12}"
                    )
                )

            mse = (
                squared_error_sum
                / len(self.output_columns)
            )

            lines.append(
                ""
            )

            lines.append(
                f"MSE: {format_debug_number(mse)}"
            )

            self.report.setPlainText(
                "\n".join(
                    lines
                )
            )

        except (
            TypeError,
            ValueError
        ) as error:
            QMessageBox.warning(
                self,
                self.t("debug.window.title"),
                str(
                    error
                )
            )

    def execute_steps(
        self,
        step_count
    ):
        """
        Führt einen oder mehrere Trainingsschritte
        ausschließlich mit dem ausgewählten Datensatz aus.
        """

        try:
            self.network.set_learning_rate(
                self.learning_rate.value()
            )
            self.network.set_momentum(self.momentum.value())

            all_reports = []

            for step_number in range(
                1,
                step_count + 1
            ):
                all_reports.extend(
                    self.execute_single_step(
                        step_number
                    )
                )

                if step_number < step_count:
                    all_reports.extend(
                        [
                            "",
                            "=" * 90,
                            ""
                        ]
                    )

            self.report.setPlainText(
                "\n".join(
                    all_reports
                )
            )

            self.report.moveCursor(
                self.report.textCursor().MoveOperation.Start
            )

        except (
            TypeError,
            ValueError
        ) as error:
            QMessageBox.warning(
                self,
                self.t("debug.window.title"),
                str(
                    error
                )
            )

    def execute_single_step(
        self,
        step_number
    ):
        """
        Führt genau einen vollständigen Trainingsschritt
        aus und liefert einen ausführlichen Bericht.
        """

        record = self.get_selected_record()

        self.network.reset_runtime_values()
        self.network.restore_momentum_state(self.initial_momentum_state)

        target_values = self.apply_record(
            record
        )

        weights_before = {
            connection.id: connection.weight
            for connection in self.network.get_connections()
        }

        biases_before = {
            neuron.id: neuron.bias
            for neuron in self.network.get_neurons()
        }

        self.network.forward_pass()

        output_values_before = {
            neuron.id: neuron.output_value
            for neuron in self.network.get_output_neurons()
        }

        self.network.calculate_training_deltas(
            target_values
        )

        neuron_values_before_update = {}

        for neuron in self.network.get_neurons():
            derivative = 0.0
            weighted_delta_sum = None
            outgoing_details = []

            if neuron.neuron_type.name != "INPUT":
                derivative = (
                    self.network.get_activation_derivative(
                        neuron.activation_function,
                        neuron.sum_value
                    )
                )

            if neuron.neuron_type.name == "HIDDEN":
                weighted_delta_sum = 0.0

                for connection in neuron.outgoing_connections:
                    target_neuron = connection.target_neuron
                    target_delta = target_neuron.delta_value
                    contribution = (
                        connection.weight
                        * target_delta
                    )

                    weighted_delta_sum += contribution

                    outgoing_details.append(
                        {
                            "connection_id": connection.id,
                            "target_name": target_neuron.name,
                            "weight": connection.weight,
                            "target_delta": target_delta,
                            "contribution": contribution
                        }
                    )

            neuron_values_before_update[
                neuron.id
            ] = {
                "sum": neuron.sum_value,
                "output": neuron.output_value,
                "error": neuron.error_value,
                "delta": neuron.delta_value,
                "derivative": derivative,
                "weighted_delta_sum": weighted_delta_sum,
                "outgoing_details": outgoing_details
            }

        update_result = (
            self.network.apply_training_gradients()
        )

        weights_after = {
            connection.id: connection.weight
            for connection in self.network.get_connections()
        }

        biases_after = {
            neuron.id: neuron.bias
            for neuron in self.network.get_neurons()
        }

        self.network.reset_runtime_values()

        self.apply_record(
            record
        )

        self.network.forward_pass()

        lines = [
            self.t("debug.report.training_step", step=step_number),
            "=" * 30,
            ""
        ]

        lines.append(
            self.t("debug.report.inputs")
        )

        lines.append(
            "--------"
        )

        for mapping in self.input_columns:
            value = record[
                mapping["column_index"]
            ]

            lines.append(
                f"{mapping['column_name']:<16} "
                f"{format_debug_number(value):>12} "
                f"→ {mapping['neuron'].name}.X"
            )

        lines.append(
            ""
        )

        lines.append(
            self.t("debug.report.before_update")
        )

        lines.append(
            "------------------------------------------"
        )

        for neuron in self.network.get_topological_order():
            values = neuron_values_before_update[
                neuron.id
            ]

            lines.append(
                self.t(
                    "debug.report.neuron_values",
                    neuron=f"{neuron.name:<16}",
                    sum=f"{format_debug_number(values['sum']):>12}",
                    output=f"{format_debug_number(values['output']):>12}",
                    error=f"{format_debug_number(values['error']):>12}",
                    delta=f"{format_debug_number(values['delta']):>12}"
                )
            )

        lines.append(
            ""
        )

        lines.append(
            self.t("debug.report.hidden_backward_analysis")
        )

        lines.append(
            "-----------------------------------"
        )

        blocked_hidden_neurons = []

        for neuron in self.network.get_topological_order():
            if neuron.neuron_type.name != "HIDDEN":
                continue

            values = neuron_values_before_update[
                neuron.id
            ]

            lines.append(
                f"{neuron.name}:"
            )

            outgoing_details = values[
                "outgoing_details"
            ]

            if not outgoing_details:
                lines.append(
                    self.t("debug.report.no_outgoing_connection")
                )

            else:
                for detail in outgoing_details:
                    lines.append(
                        self.t(
                            "debug.report.backward_contribution",
                            connection=detail["connection_id"],
                            target=detail["target_name"],
                            weight=format_debug_number(detail["weight"]),
                            delta=format_debug_number(detail["target_delta"]),
                            contribution=format_debug_number(detail["contribution"])
                        )
                    )

            weighted_delta_sum = values[
                "weighted_delta_sum"
            ]

            derivative = values[
                "derivative"
            ]

            lines.append(
                self.t(
                    "debug.report.backward_sum",
                    value=format_debug_number(weighted_delta_sum)
                )
            )

            lines.append(
                self.t(
                    "debug.report.derivative",
                    activation=neuron.activation_function,
                    value=format_debug_number(derivative)
                )
            )

            lines.append(
                self.t(
                    "debug.report.hidden_delta",
                    backward_sum=format_debug_number(weighted_delta_sum),
                    derivative=format_debug_number(derivative),
                    delta=format_debug_number(values["delta"])
                )
            )

            all_outgoing_weights_zero = (
                bool(outgoing_details)
                and all(
                    abs(detail["weight"]) < 1e-15
                    for detail in outgoing_details
                )
            )

            if (
                all_outgoing_weights_zero
                and abs(values["delta"]) < 1e-15
            ):
                blocked_hidden_neurons.append(
                    neuron.name
                )

                lines.append(
                    self.t("debug.report.zero_weights_note")
                )

            lines.append(
                ""
            )

        if blocked_hidden_neurons:
            lines.append(
                self.t("debug.report.important")
            )

            lines.append(
                self.t("debug.report.gradient_blocked")
            )

            lines.append(
                self.t(
                    "debug.report.affected",
                    neurons=", ".join(blocked_hidden_neurons)
                )
            )

            lines.append(
                self.t("debug.report.xavier_recommendation")
            )

            lines.append(
                ""
            )

        lines.append(
            self.t("debug.report.weight_changes")
        )

        lines.append(
            "------------------"
        )

        for connection in self.network.get_connections():
            update_value = update_result[
                "connection_updates"
            ][
                connection.id
            ]

            lines.append(
                f"W{connection.id:<4} "
                f"{connection.source_neuron.name} → "
                f"{connection.target_neuron.name}: "
                f"{format_debug_number(weights_before[connection.id]):>12} "
                f"{format_signed_debug_number(update_value):>12} = "
                f"{format_debug_number(weights_after[connection.id]):>12}"
            )
            detail = (self.network.trainer.last_step_details or {}).get(
                "connections", {}
            ).get(connection.id, {})
            lines.append(" " * 8 + self.t(
                "debug.report.momentum_update",
                gradient=format_signed_debug_number(
                    detail.get("weight_gradient_update", update_value)
                ),
                previous=format_signed_debug_number(
                    detail.get("weight_previous_velocity", 0.0)
                ),
                contribution=format_signed_debug_number(
                    detail.get("weight_momentum_term", 0.0)
                ),
                velocity=format_signed_debug_number(update_value),
            ))

        lines.append(
            ""
        )

        lines.append(
            self.t("debug.report.bias_changes")
        )

        lines.append(
            "---------------"
        )

        for neuron in self.network.get_neurons():
            if neuron.id not in update_result[
                "bias_updates"
            ]:
                continue

            update_value = update_result[
                "bias_updates"
            ][
                neuron.id
            ]

            lines.append(
                f"{neuron.name:<16} "
                f"{format_debug_number(biases_before[neuron.id]):>12} "
                f"{format_signed_debug_number(update_value):>12} = "
                f"{format_debug_number(biases_after[neuron.id]):>12}"
            )
            detail = (self.network.trainer.last_step_details or {}).get(
                "neurons", {}
            ).get(neuron.id, {})
            lines.append(" " * 8 + self.t(
                "debug.report.momentum_update",
                gradient=format_signed_debug_number(
                    detail.get("bias_gradient_update", update_value)
                ),
                previous=format_signed_debug_number(
                    detail.get("bias_previous_velocity", 0.0)
                ),
                contribution=format_signed_debug_number(
                    detail.get("bias_momentum_term", 0.0)
                ),
                velocity=format_signed_debug_number(update_value),
            ))

        lines.append(
            ""
        )

        lines.append(
            self.t("debug.report.output_before_after")
        )

        lines.append(
            "-------------------------------"
        )

        squared_error_sum = 0.0

        for mapping in self.output_columns:
            neuron = mapping["neuron"]
            target_value = target_values[
                neuron.id
            ]
            before_value = output_values_before[
                neuron.id
            ]
            after_value = neuron.output_value
            after_error = (
                target_value
                - after_value
            )

            squared_error_sum += (
                after_error
                * after_error
            )

            lines.append(
                self.t(
                    "debug.report.output_before_after_values",
                    column=f"{mapping['column_name']:<16}",
                    target=f"{format_debug_number(target_value):>12}",
                    before=f"{format_debug_number(before_value):>12}",
                    after=f"{format_debug_number(after_value):>12}",
                    error=f"{format_debug_number(after_error):>12}"
                )
            )

        mse_after = (
            squared_error_sum
            / len(self.output_columns)
        )

        lines.append(
            ""
        )

        lines.append(
            self.t(
                "debug.report.mse_after",
                error=format_debug_number(mse_after)
            )
        )

        return lines

    def restore_initial_parameters(self):
        """
        Stellt Gewichte und Bias-Werte auf den Zustand
        beim Öffnen des Debuggers zurück.
        """

        for connection in self.network.get_connections():
            if connection.id in self.initial_weights:
                connection.weight = self.initial_weights[
                    connection.id
                ]

        for neuron in self.network.get_neurons():
            if neuron.id in self.initial_biases:
                neuron.bias = self.initial_biases[
                    neuron.id
                ]

                neuron.update()

        self.network.reset_runtime_values()

        self.calculate_forward_only()

        QMessageBox.information(
            self,
            self.t("debug.window.title"),
            self.t("debug.message.restored")
        )
