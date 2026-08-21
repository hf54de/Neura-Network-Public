# -------------------------------------------------------------------------------------------------
# Datei: trainingdialog.py
# Zweck: Steuert Trainingsläufe, Parameter, Status und Bedienung des Trainingsfensters.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math
import random
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget
)

from neurontype import NeuronType
from language import LanguageManager
from networktestdialog import NetworkTestDialog
from numberformat import format_number
from resultanalysisdialog import ResultAnalysisDialog
from trainingdebugdialog import TrainingDebugDialog
from trainingerrorchart import TrainingErrorChart
from trainingdataio import TrainingDataIO


class CompactDoubleSpinBox(QDoubleSpinBox):
    """Dezimalfeld ohne Endnullen und mit einfacher Werteingabe."""

    def normalized_input_text(self, text):
        """Akzeptiert bei manueller Eingabe Komma und Punkt."""

        decimal_point = self.locale().decimalPoint()
        other_point = "." if decimal_point == "," else ","
        return text.replace(other_point, decimal_point)

    def validate(self, text, position):
        state, _normalized, normalized_position = super().validate(
            self.normalized_input_text(text), position
        )
        return state, text, normalized_position

    def valueFromText(self, text):
        return super().valueFromText(self.normalized_input_text(text))

    def textFromValue(self, value):
        text = super().textFromValue(value)
        decimal_point = self.locale().decimalPoint()

        if decimal_point in text:
            text = text.rstrip("0").rstrip(decimal_point)

        return text

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(
            0,
            self.select_current_value
        )

    def select_current_value(self):
        if self.hasFocus():
            self.lineEdit().selectAll()


class FixedDoubleSpinBox(CompactDoubleSpinBox):
    """Dezimalfeld mit dauerhaft sichtbaren Nachkommastellen."""

    def textFromValue(self, value):
        return QDoubleSpinBox.textFromValue(self, value)


class TrainingDialog(QDialog):
    """
    Trainiert ein Netzwerk mit einer unabhängigen
    Trainingsdatendatei.

    Die Zuordnung der Tabellenspalten zu den Neuronen
    wird aus den Spalteneigenschaften der Trainingsdaten
    übernommen.

    Eine Epoche verarbeitet alle vorhandenen Datensätze
    genau einmal in ihrer aktuellen Reihenfolge.
    """

    training_completed = Signal(dict)
    training_progress = Signal(dict)

    # True: Netzwerk während des Trainings sichtbar aktualisieren.
    # False: Netzwerkdarstellung bis zum Trainingsende einfrieren.
    training_monitoring_changed = Signal(bool)

    def __init__(
        self,
        network,
        training_document,
        training_file_path=None,
        project_path=None,
        parent=None,
        training_settings=None,
        language_manager=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        text = self.language.text
        self.network = network
        self.training_document = training_document
        self.training_file_path = training_file_path
        self.project_path = project_path
        self.training_settings = self.normalize_training_settings(
            training_settings
        )
        # Ein neu geöffneter Trainingsdialog beginnt stets mit der
        # empfohlenen aktivierungsabhängigen Gewichtsinitialisierung.
        # Damit überschreiben ältere, im Projekt gespeicherte Xavier-
        # Vorgaben nicht den aktuellen Standard für einen neuen Lauf.
        self.training_settings["weight_initialization"] = "auto"
        self.is_training = False
        self.stop_requested = False
        self.network_test_dialog = None
        self.compact_mode = False
        self.minimal_mode = False
        self.full_view_geometry = None
        self.maximum_error_details = None
        self.group_info_buttons = {}

        # Begrenzte Ereignisverarbeitung hält die Stop-Taste
        # funktionsfähig, ohne in jedem Datensatz die komplette
        # Oberfläche neu zu zeichnen.
        self._last_event_processing_time = 0.0

        # Zeitmessung des aktuellen Trainingslaufes.
        self.training_start_time = None
        self.training_elapsed_base = 0.0
        self._last_elapsed_display_update = 0.0
        self.error_chart_start_value = None
        self.error_chart_current_value = None
        self.history_curve_points = []
        self.plateau_history = []
        self.plateau_warning_detected = False
        self.plateau_warning_dismissed = False
        self.next_training_run_id = 1
        self.current_run_id = None
        self.current_run_timestamp = ""
        self.current_run_completed_epochs = 0
        self.current_run_requested_epochs = 0
        self.current_run_elapsed_seconds = 0.0
        self.current_run_initialized = False
        self.current_run_learning_rate = None
        self.current_run_momentum = None
        self.current_run_shuffle_seed = None
        self.current_run_can_continue = False
        self.current_run_stopped = False
        self.current_run_initial_state = None

        self.input_columns = []
        self.output_columns = []
        self.records = []

        self.prepare_training_document()

        self.setWindowTitle(
            text("training.window.title")
        )

        # Nicht-modales Werkzeugfenster: Der grafische Editor bleibt
        # während des Trainings erreichbar, das Fenster bleibt aber
        # sichtbar über seinem zugehörigen Hauptfenster.
        self.setModal(False)
        self.setWindowFlag(
            Qt.WindowType.Tool,
            True
        )

        self.setMinimumWidth(
            540
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        self.main_layout.setSpacing(
            12
        )

        scaling_warnings = self.create_scaling_warning_lines()
        self.scaling_warning_label = QLabel()
        self.scaling_warning_label.setWordWrap(
            True
        )
        self.scaling_warning_label.setStyleSheet(
            "QLabel {"
            "background-color: #fff2be;"
            "color: #7a4700;"
            "border: 1px solid #d6a53a;"
            "border-radius: 4px;"
            "padding: 8px;"
            "}"
        )

        if scaling_warnings:
            self.scaling_warning_label.setText(
                text("training.scaling_warning.message")
            )
            self.main_layout.addWidget(
                self.scaling_warning_label
            )
        else:
            self.scaling_warning_label.setVisible(
                False
            )

        imbalance_warnings = self.create_binary_imbalance_warning_lines()
        self.imbalance_warning_present = bool(imbalance_warnings)
        self.imbalance_warning_label = QWidget()
        self.imbalance_warning_label.setStyleSheet(
            "QWidget { background-color: #fff2be; color: #7a4700; "
            "border: 1px solid #d6a53a; border-radius: 4px; }"
            "QPushButton { background: transparent; border: none; "
            "text-align: left; padding: 7px; font-weight: bold; }"
            "QLabel { background: transparent; border: none; "
            "padding: 0 8px 8px 8px; }"
        )
        if imbalance_warnings:
            imbalance_layout = QVBoxLayout(self.imbalance_warning_label)
            imbalance_layout.setContentsMargins(0, 0, 0, 0)
            imbalance_layout.setSpacing(0)
            self.imbalance_warning_toggle = QPushButton()
            self.imbalance_warning_toggle.setCheckable(True)
            self.imbalance_warning_toggle.setToolTip(
                text("training.imbalance_warning.toggle")
            )
            self.imbalance_warning_details = QLabel(
                "\n".join(f"• {line}" for line in imbalance_warnings)
                + "\n"
                + text("training.imbalance_warning.advice")
            )
            self.imbalance_warning_details.setWordWrap(True)
            imbalance_layout.addWidget(self.imbalance_warning_toggle)
            imbalance_layout.addWidget(self.imbalance_warning_details)
            self.imbalance_warning_count = len(imbalance_warnings)
            self.imbalance_warning_toggle.toggled.connect(
                self.update_imbalance_warning_expansion
            )
            self.imbalance_warning_toggle.setChecked(
                len(imbalance_warnings) == 1
            )
            self.update_imbalance_warning_expansion(
                self.imbalance_warning_toggle.isChecked()
            )
            self.main_layout.addWidget(self.imbalance_warning_label)
        else:
            self.imbalance_warning_label.setVisible(False)

        self.fixed_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )

        # Gruppe: verwendete Trainingsdaten
        self.data_group = QGroupBox(
            text("training.data.group")
        )

        data_group_font = self.data_group.font()
        data_group_font.setBold(
            True
        )
        self.data_group.setFont(
            data_group_font
        )

        self.data_layout = QFormLayout(
            self.data_group
        )
        self.data_layout.setContentsMargins(9, 8, 9, 8)
        self.data_layout.setVerticalSpacing(5)

        self.data_file = QLineEdit()
        self.data_file.setReadOnly(
            True
        )
        self.data_file.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.data_file.setFont(
            self.fixed_font
        )

        self.data_records = QLineEdit()
        self.data_records.setReadOnly(
            True
        )
        self.data_records.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.data_records.setFont(
            self.fixed_font
        )

        self.data_file.setText(self.project_directory_name())
        if self.training_file_path:
            self.data_file.setToolTip(str(self.training_file_path))

        self.data_records.setText(
            str(
                len(self.records)
            )
        )

        self.data_layout.addRow(
            text("training.data.project"),
            self.data_file
        )

        self.data_layout.addRow(
            text("training.data.records"),
            self.data_records
        )

        self.workload_label = QLabel(self.create_workload_summary())
        self.workload_label.setFont(self.fixed_font)
        self.workload_label.setWordWrap(True)
        self.workload_label.setToolTip(
            text("training.data.workload_tooltip")
        )

        self.total_workload_label = QLabel()
        self.total_workload_label.setFont(self.fixed_font)
        self.total_workload_label.setWordWrap(True)
        self.total_workload_label.setVisible(False)

        self.workload_container = QWidget()
        workload_layout = QVBoxLayout(self.workload_container)
        workload_layout.setContentsMargins(0, 0, 0, 0)
        workload_layout.setSpacing(3)
        workload_layout.addWidget(self.workload_label)
        workload_layout.addWidget(self.total_workload_label)
        self.workload_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.data_layout.addRow(self.workload_container)

        # Gruppe: Einstellungen, die ausschließlich einen neuen Lauf betreffen.
        self.parameter_group = QGroupBox(
            text("training.new_run_settings.group")
        )

        parameter_group_font = self.parameter_group.font()
        parameter_group_font.setBold(
            True
        )
        self.parameter_group.setFont(
            parameter_group_font
        )

        self.parameter_layout = QFormLayout(
            self.parameter_group
        )

        self.parameter_layout.setContentsMargins(9, 8, 9, 8)
        self.parameter_layout.setHorizontalSpacing(12)
        self.parameter_layout.setVerticalSpacing(5)

        self.initialization_info_button = self.create_group_info_button(
            self.parameter_group,
            "training.info.initialization.title",
            "training.info.initialization.text",
        )

        self.learning_rate = CompactDoubleSpinBox()
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
            self.training_settings[
                "learning_rate"
            ]
        )
        self.learning_rate.setFont(
            self.fixed_font
        )

        self.momentum = FixedDoubleSpinBox()
        self.momentum.setDecimals(2)
        self.momentum.setRange(0.0, 0.99)
        self.momentum.setSingleStep(0.05)
        self.momentum.setValue(self.training_settings.get("momentum", 0.0))
        self.momentum.setFont(self.fixed_font)
        self.momentum.setKeyboardTracking(False)

        self.error_limit = CompactDoubleSpinBox()
        self.error_limit.setDecimals(
            10
        )
        self.error_limit.setRange(
            0.0,
            1000000.0
        )
        self.error_limit.setSingleStep(
            0.001
        )
        self.error_limit.setValue(
            self.training_settings[
                "error_limit"
            ]
        )
        self.error_limit.setFont(
            self.fixed_font
        )
        self.error_limit.setKeyboardTracking(
            False
        )
        self.error_limit.editingFinished.connect(
            self.normalize_error_limit_input
        )

        self.maximum_epochs = QSpinBox()
        self.maximum_epochs.setRange(
            1,
            1000000
        )
        self.maximum_epochs.setSingleStep(
            100
        )
        self.maximum_epochs.setValue(
            self.training_settings[
                "maximum_epochs"
            ]
        )
        self.maximum_epochs.setFont(
            self.fixed_font
        )

        self.fast_mode = QCheckBox(
            text("training.parameters.fast_mode")
        )
        self.fast_mode.setChecked(
            self.training_settings["fast_mode"]
        )
        self.fast_mode.setToolTip(
            text("training.parameters.fast_mode_tooltip")
        )

        self.monitor_training_data = QCheckBox(
            text("training.parameters.monitor_network")
        )

        self.monitor_training_data.setChecked(
            self.training_settings[
                "monitor_training_data"
            ]
        )
        self.fast_mode.setChecked(
            not self.monitor_training_data.isChecked()
        )

        self.monitor_training_data.setToolTip(
            text("training.parameters.monitor_network_tooltip")
        )

        self.show_error_chart = QCheckBox(
            text("training.parameters.show_chart")
        )
        self.show_error_chart.setChecked(
            self.training_settings[
                "show_error_chart"
            ]
        )
        self.show_error_chart.setToolTip(
            text("training.parameters.show_chart_tooltip")
        )

        self.initialize_network = QCheckBox(
            text("training.parameters.initialize")
        )
        self.initialize_network.setChecked(
            self.training_settings[
                "initialize_network"
            ]
        )
        self.initialize_network.setToolTip(
            text("training.parameters.initialize_tooltip")
        )

        self.initialization_group = QWidget()

        self.initialization_layout = QFormLayout(
            self.initialization_group
        )

        self.initialization_layout.setContentsMargins(0, 0, 0, 0)
        self.initialization_layout.setHorizontalSpacing(12)
        self.initialization_layout.setVerticalSpacing(5)

        self.weights_label = QLabel(
            text("training.initialization.weights")
        )

        weights_label_font = self.weights_label.font()
        weights_label_font.setBold(
            True
        )
        self.weights_label.setFont(
            weights_label_font
        )

        self.weight_initialization_combo = QComboBox()
        self.weight_initialization_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.weight_initialization_combo.setMinimumContentsLength(
            18
        )
        self.weight_initialization_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.weight_initialization_combo.addItem(
            text("training.initialization.auto_recommended"),
            "auto"
        )
        self.weight_initialization_combo.addItem(
            text("training.initialization.xavier_all"),
            "xavier"
        )
        self.weight_initialization_combo.addItem(
            text("training.initialization.he_all"),
            "he"
        )
        self.weight_initialization_combo.addItem(
            text("training.initialization.weights_zero"),
            "zero"
        )
        self.weight_initialization_combo.view().setMinimumWidth(
            self.weight_initialization_combo.fontMetrics().horizontalAdvance(
                text("training.initialization.weights_zero")
            ) + 36
        )
        self.weight_initialization_combo.setCurrentIndex(
            max(
                0,
                self.weight_initialization_combo.findData(
                    self.training_settings[
                        "weight_initialization"
                    ]
                )
            )
        )

        self.bias_label = QLabel(
            text("training.initialization.bias")
        )

        bias_label_font = self.bias_label.font()
        bias_label_font.setBold(
            True
        )
        self.bias_label.setFont(
            bias_label_font
        )

        self.bias_initialization_combo = QComboBox()
        self.bias_initialization_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.bias_initialization_combo.setMinimumContentsLength(
            18
        )
        self.bias_initialization_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.bias_initialization_combo.addItem(
            text("training.initialization.bias_zero"),
            "zero"
        )
        self.bias_initialization_combo.addItem(
            text("training.initialization.xavier"),
            "xavier"
        )
        self.bias_initialization_combo.view().setMinimumWidth(
            self.bias_initialization_combo.fontMetrics().horizontalAdvance(
                text("training.initialization.bias_zero")
            ) + 36
        )
        self.bias_initialization_combo.setCurrentIndex(
            max(
                0,
                self.bias_initialization_combo.findData(
                    self.training_settings[
                        "bias_initialization"
                    ]
                )
            )
        )

        self.initialization_layout.addRow(
            self.weights_label,
            self.weight_initialization_combo
        )

        self.initialization_layout.addRow(
            self.bias_label,
            self.bias_initialization_combo
        )

        self.initialization_group.setEnabled(
            self.initialize_network.isChecked()
        )

        self.initialization_group.setVisible(
            self.initialize_network.isChecked()
        )

        self.initialize_network.toggled.connect(
            self.initialization_group.setEnabled
        )

        self.initialize_network.toggled.connect(
            self.initialization_group.setVisible
        )
        self.initialize_network.toggled.connect(
            lambda checked: QTimer.singleShot(0, self.sync_training_area_heights)
        )

        self.parameter_layout.addRow(
            "",
            self.initialize_network
        )

        self.parameter_layout.addRow(
            "",
            self.initialization_group
        )

        # Gruppe: fachliche Parameter des Trainings.
        self.training_values_group = QGroupBox(
            text("training.values.group")
        )
        training_values_font = self.training_values_group.font()
        training_values_font.setBold(True)
        self.training_values_group.setFont(training_values_font)
        self.training_values_layout = QFormLayout(self.training_values_group)
        self.training_values_layout.setContentsMargins(9, 8, 9, 8)
        self.training_values_layout.setHorizontalSpacing(12)
        self.training_values_layout.setVerticalSpacing(5)
        learning_rate_row = QWidget(self.training_values_group)
        learning_rate_row_layout = QHBoxLayout(learning_rate_row)
        learning_rate_row_layout.setContentsMargins(0, 0, 0, 0)
        learning_rate_row_layout.setSpacing(6)
        learning_rate_row_layout.addWidget(self.learning_rate, 1)
        self.training_values_info_button = QPushButton(
            "i", self.training_values_group
        )
        self.training_values_info_button.setFixedSize(26, 24)
        self.training_values_info_button.setToolTip(
            text("training.info.parameters.title")
        )
        self.training_values_info_button.clicked.connect(
            lambda: self.show_training_information(
                "training.info.parameters.title",
                "training.info.parameters.text",
            )
        )
        learning_rate_row_layout.addWidget(self.training_values_info_button)
        self.training_values_layout.addRow(
            text("training.parameters.learning_rate"), learning_rate_row
        )
        self.training_values_layout.addRow(
            text("training.parameters.momentum"), self.momentum
        )
        self.training_values_layout.addRow(
            text("training.parameters.error_limit"), self.error_limit
        )
        self.training_values_layout.addRow(
            text("training.parameters.maximum_epochs"), self.maximum_epochs
        )
        self.suggest_parameters_button = QPushButton(
            text("training.button.suggest_parameters")
        )
        self.suggest_parameters_button.setToolTip(
            text("training.button.suggest_parameters_tooltip")
        )
        self.suggest_parameters_button.clicked.connect(
            self.suggest_training_parameters
        )
        self.training_values_layout.addRow("", self.suggest_parameters_button)

        # Gruppe: reine Ausführungs- und Anzeigeoptionen.
        self.execution_group = QGroupBox(
            text("training.execution.group")
        )
        execution_font = self.execution_group.font()
        execution_font.setBold(True)
        self.execution_group.setFont(execution_font)
        self.execution_layout = QFormLayout(self.execution_group)
        self.execution_layout.setContentsMargins(9, 8, 9, 8)
        self.execution_layout.setHorizontalSpacing(12)
        self.execution_layout.setVerticalSpacing(5)
        self.execution_info_button = self.create_group_info_button(
            self.execution_group,
            "training.info.execution.title",
            "training.info.execution.text",
        )
        self.execution_layout.addRow(
            text("training.parameters.monitor_data"), self.monitor_training_data
        )
        self.execution_layout.addRow(
            text("training.parameters.error_chart"), self.show_error_chart
        )

        self.left_training_container = QWidget()
        self.left_training_layout = QVBoxLayout(self.left_training_container)
        self.left_training_layout.setContentsMargins(0, 0, 0, 0)
        self.left_training_layout.setSpacing(8)
        self.left_training_layout.addWidget(self.parameter_group)
        self.left_training_layout.addWidget(self.training_values_group)
        self.left_training_layout.addWidget(self.execution_group)
        self.left_training_container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        # Gruppe: Ergebnis
        self.result_group = QGroupBox(
            text("training.result.group")
        )

        result_group_font = self.result_group.font()
        result_group_font.setBold(
            True
        )
        self.result_group.setFont(
            result_group_font
        )

        self.result_layout = QFormLayout(
            self.result_group
        )
        self.result_layout.setContentsMargins(9, 8, 9, 8)
        self.result_layout.setVerticalSpacing(5)

        self.result_start_mse = QLineEdit()
        self.result_start_mse.setReadOnly(True)
        self.result_start_mse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_start_mse.setFont(self.fixed_font)
        self.result_start_mse.setToolTip(
            text("training.result.mean_error_tooltip")
        )

        self.result_mse = QLineEdit()
        self.result_mse.setReadOnly(
            True
        )
        self.result_mse.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.result_mse.setFont(
            self.fixed_font
        )
        self.result_mse.setToolTip(
            text("training.result.mean_error_tooltip")
        )
        self.result_mse_container = QWidget()
        result_mse_layout = QHBoxLayout(self.result_mse_container)
        result_mse_layout.setContentsMargins(0, 0, 0, 0)
        result_mse_layout.setSpacing(6)
        result_mse_layout.addWidget(self.result_start_mse, 1)
        result_mse_layout.addWidget(
            QLabel(text("training.result.mean_error_current"))
        )
        result_mse_layout.addWidget(self.result_mse, 1)

        self.result_epochs = QLineEdit()
        self.result_epochs.setReadOnly(
            True
        )
        self.result_epochs.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.result_epochs.setFont(
            self.fixed_font
        )

        self.result_max_error = QLineEdit()
        self.result_max_error.setReadOnly(
            True
        )
        self.result_max_error.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.result_max_error.setFont(
            self.fixed_font
        )
        self.result_max_error_info = QPushButton("i")
        self.result_max_error_info.setFixedSize(26, 24)
        self.result_max_error_info.setToolTip(
            text("training.result.maximum_error_info_tooltip")
        )
        self.result_max_error_info.setEnabled(False)
        self.result_max_error_info.clicked.connect(
            self.show_maximum_error_details
        )
        self.result_max_error_container = QWidget()
        maximum_error_layout = QHBoxLayout(
            self.result_max_error_container
        )
        maximum_error_layout.setContentsMargins(0, 0, 0, 0)
        maximum_error_layout.setSpacing(5)
        maximum_error_layout.addWidget(self.result_max_error, 1)
        maximum_error_layout.addWidget(self.result_max_error_info)

        self.result_elapsed_time = QLineEdit()
        self.result_elapsed_time.setReadOnly(
            True
        )
        self.result_elapsed_time.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.result_elapsed_time.setFont(
            self.fixed_font
        )
        self.result_elapsed_time.setText(
            "0.0 s"
        )

        self.result_status = QLineEdit()
        self.result_status.setReadOnly(
            True
        )
        self.result_status.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.result_status.setFont(
            self.fixed_font
        )

        self.compact_status_label = QLabel()
        self.compact_status_label.setFont(
            self.fixed_font
        )
        self.compact_status_label.setStyleSheet(
            "QLabel {"
            "background-color: #eef4f8;"
            "border: 1px solid #b9cbd8;"
            "border-radius: 4px;"
            "padding: 7px;"
            "}"
        )
        self.compact_status_label.setVisible(
            False
        )

        self.minimal_epoch_label = QLabel(
            text("training.compact.epoch", epoch="–")
        )
        self.minimal_epoch_label.setFont(
            self.fixed_font
        )
        self.minimal_epoch_label.setStyleSheet(
            "QLabel {"
            "background-color: #eef4f8;"
            "border: 1px solid #b9cbd8;"
            "border-radius: 4px;"
            "padding: 5px 10px;"
            "}"
        )
        self.minimal_epoch_label.setVisible(
            False
        )

        self.result_layout.addRow(
            text("training.result.mean_error"),
            self.result_mse_container
        )

        self.result_layout.addRow(
            text("training.result.epochs"),
            self.result_epochs
        )

        self.result_layout.addRow(
            text("training.result.maximum_error"),
            self.result_max_error_container
        )

        self.result_layout.addRow(
            text("training.result.elapsed"),
            self.result_elapsed_time
        )

        self.result_layout.addRow(
            text("training.result.status"),
            self.result_status
        )

        self.plateau_warning_container = QWidget()
        self.plateau_warning_layout = QHBoxLayout(
            self.plateau_warning_container
        )
        self.plateau_warning_layout.setContentsMargins(0, 0, 0, 0)
        self.plateau_warning_layout.setSpacing(4)
        self.plateau_warning_label = QLabel(
            text("training.plateau_warning.text")
        )
        self.plateau_warning_label.setWordWrap(True)
        self.plateau_warning_label.setStyleSheet(
            "QLabel {"
            "background-color: #fff2be;"
            "color: #7a4700;"
            "border: 1px solid #d6a53a;"
            "border-radius: 4px;"
            "padding: 7px;"
            "}"
        )
        self.plateau_warning_layout.addWidget(self.plateau_warning_label, 1)
        self.plateau_warning_close_button = QPushButton("×")
        self.plateau_warning_close_button.setToolTip(
            text("training.plateau_warning.close_tooltip")
        )
        self.plateau_warning_close_button.setFixedSize(24, 24)
        self.plateau_warning_close_button.setFlat(True)
        self.plateau_warning_close_button.clicked.connect(
            self.dismiss_plateau_warning
        )
        self.plateau_warning_layout.addWidget(
            self.plateau_warning_close_button,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        self.plateau_warning_container.setVisible(False)
        self.result_layout.addRow(self.plateau_warning_container)

        for result_field in (
            self.result_mse,
            self.result_epochs,
            self.result_elapsed_time,
            self.result_status
        ):
            result_field.textChanged.connect(
                self.update_compact_status
            )

        self.update_compact_status()

        # Gruppe: Fehlerverlauf
        self.error_chart_group = QGroupBox(
            text("training.chart.group")
        )
        error_chart_group_font = self.error_chart_group.font()
        error_chart_group_font.setBold(
            True
        )
        self.error_chart_group.setFont(
            error_chart_group_font
        )

        self.error_chart_layout = QVBoxLayout(
            self.error_chart_group
        )

        self.error_chart_controls_layout = QHBoxLayout()
        self.error_chart_controls_layout.addStretch(
            1
        )
        self.error_chart_info_button = QPushButton("i")
        self.error_chart_info_button.setFixedSize(26, 24)
        self.error_chart_info_button.setToolTip(
            text("training.info.error_chart.title")
        )
        self.error_chart_info_button.clicked.connect(
            lambda: self.show_training_information(
                "training.info.error_chart.title",
                "training.info.error_chart.text",
            )
        )
        self.error_chart_controls_layout.addWidget(
            self.error_chart_info_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.error_chart_y_axis_label = QLabel(
            text("training.chart.y_axis")
        )
        self.error_chart_controls_layout.addWidget(
            self.error_chart_y_axis_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.error_chart_scale = QComboBox()
        self.error_chart_scale.addItem(
            text("training.chart.linear"),
            "linear"
        )
        self.error_chart_scale.addItem(
            text("training.chart.logarithmic"),
            "logarithmic"
        )
        self.error_chart_scale.setMaximumWidth(
            150
        )
        self.error_chart_scale.setCurrentIndex(
            max(
                0,
                self.error_chart_scale.findData(
                    self.training_settings[
                        "error_chart_scale"
                    ]
                )
            )
        )
        self.error_chart_controls_layout.addWidget(
            self.error_chart_scale,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.error_chart_layout.addLayout(
            self.error_chart_controls_layout
        )

        self.error_chart = TrainingErrorChart(
            language_manager=self.language
        )
        self.error_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.error_chart.setMinimumHeight(190)
        self.error_chart.set_scale_mode(
            self.error_chart_scale.currentData()
        )
        self.error_chart_layout.addWidget(
            self.error_chart
        )
        self.error_chart_layout.setStretch(0, 0)
        self.error_chart_layout.setStretch(1, 1)

        self.error_chart_start = QLabel(
            text("training.chart.start_error", value="–"),
            self.error_chart_group,
        )
        self.error_chart_current = QLabel(
            text("training.chart.current_error", value="–"),
            self.error_chart_group,
        )
        for summary_label in (
            self.error_chart_start,
            self.error_chart_current,
        ):
            summary_label.setFont(
                self.fixed_font
            )
            # Die Texte dienen nur als interner Speicher für die kompakte
            # Statuszeile. Ohne Elternobjekt wurden sie beim Rückwechsel aus
            # der Kompakt- oder Minimalansicht zu eigenen Fenstern.
            summary_label.setVisible(False)

        self.error_chart_scale.currentIndexChanged.connect(
            self.update_error_chart_scale
        )
        self.error_chart_group.setVisible(
            self.show_error_chart.isChecked()
        )
        self.show_error_chart.toggled.connect(
            self.error_chart_group.setVisible
        )

        # Trainingsziel: Die Optionsfelder machen sichtbar, dass genau eine
        # der drei Laufarten ausgewählt wird.
        self.training_target_group = QGroupBox(
            text("training.group.target")
        )
        training_target_layout = QHBoxLayout(self.training_target_group)
        training_target_layout.setContentsMargins(8, 5, 8, 3)
        training_target_layout.setSpacing(8)

        self.epoch_1_button = QRadioButton(
            text("training.button.epoch_one")
        )
        self.epoch_count_button = QRadioButton(
            text("training.target.count")
        )
        self.epoch_count = QSpinBox()
        self.epoch_count.setRange(1, 1000000)
        self.epoch_count.setValue(
            int(self.training_settings.get("training_section_epochs", 1000))
        )
        self.epoch_count.setSingleStep(100)
        self.epoch_count.setMinimumWidth(100)
        self.epoch_count.installEventFilter(self)
        self.epoch_count.lineEdit().installEventFilter(self)
        self.epoch_count_suffix = QLabel(
            text("training.target.epochs_suffix")
        )

        self.start_epochs_button = QPushButton(
            text("training.button.start_new")
        )

        self.until_limit_button = QRadioButton(
            text("training.button.until_limit")
        )

        self.training_target_buttons = QButtonGroup(self)
        self.training_target_buttons.setExclusive(True)
        self.training_target_buttons.addButton(self.epoch_1_button)
        self.training_target_buttons.addButton(self.epoch_count_button)
        self.training_target_buttons.addButton(self.until_limit_button)

        training_target_layout.addWidget(self.epoch_1_button)
        training_target_layout.addWidget(self.epoch_count_button)
        training_target_layout.addWidget(self.epoch_count)
        training_target_layout.addWidget(self.epoch_count_suffix)
        training_target_layout.addWidget(self.until_limit_button)
        training_target_layout.addStretch(1)
        self.training_target_info = QPushButton("i")
        self.training_target_info.setFixedSize(26, 24)
        self.training_target_info.setToolTip(
            text("training.info.target.tooltip")
        )
        self.training_target_info.clicked.connect(
            lambda: self.show_training_information(
                "training.info.target.title",
                "training.info.target.text",
            )
        )
        training_target_layout.addWidget(self.training_target_info)

        self.stop_button = QPushButton(
            text("training.button.stop")
        )
        # Ausreichend Platz für den späteren Text „Fortsetzen“, damit
        # sich das Trainingsfenster beim Anhalten nicht verbreitert.
        self.stop_button.setMinimumWidth(
            90
        )
        self.stop_button.setEnabled(
            False
        )

        self.continue_button = QPushButton(
            text("training.button.resume")
        )
        self.continue_button.setMinimumWidth(
            90
        )
        self.continue_button.setEnabled(
            False
        )
        self.continue_button.setToolTip(
            text("training.button.resume_tooltip")
        )
        self.repeat_initialization_button = QPushButton(
            text("training.button.repeat_initialization")
        )
        self.repeat_initialization_button.setToolTip(
            text("training.button.repeat_initialization_tooltip")
        )
        self.repeat_initialization_button.setEnabled(False)
        self.test_network_button = QPushButton(
            text("training.button.test_network")
        )
        self.experiment_button = QPushButton(
            text("training.button.experiment")
        )
        self.experiment_button.setEnabled(False)

        self.debug_training_button = QPushButton(
            text("training.button.debug")
        )
        self.load_history_button = QPushButton(
            text("training.button.load_history")
        )

        self.training_buttons = [
            self.start_epochs_button,
            self.continue_button,
        ]
        self.new_run_controls = [
            self.epoch_1_button,
            self.epoch_count_button,
            self.epoch_count,
            self.until_limit_button,
            self.start_epochs_button,
        ]

        self.epoch_1_button.toggled.connect(
            lambda checked: checked and self.select_training_target("one")
        )
        self.epoch_count_button.toggled.connect(
            lambda checked: checked and self.select_training_target("epochs")
        )
        self.epoch_count.valueChanged.connect(
            lambda value: self.select_training_target("epochs")
        )
        self.until_limit_button.toggled.connect(
            lambda checked: checked and self.select_training_target("limit")
        )
        self.start_epochs_button.clicked.connect(
            self.start_selected_training
        )

        self.stop_button.clicked.connect(
            self.request_stop
        )

        self.continue_button.clicked.connect(
            self.continue_selected_training
        )
        self.repeat_initialization_button.clicked.connect(
            self.repeat_with_same_initialization
        )
        self.test_network_button.clicked.connect(
            self.test_network
        )
        self.experiment_button.clicked.connect(
            self.open_experiment
        )

        self.debug_training_button.clicked.connect(
            self.debug_training
        )

        self.load_history_button.clicked.connect(
            self.load_previous_training_run
        )
        self.training_target_mode = str(
            self.training_settings.get("training_target_mode", "epochs")
        )
        if self.training_target_mode not in {"one", "epochs", "limit"}:
            self.training_target_mode = "epochs"
        self.update_training_target_display()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )

        self.close_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        )
        self.close_button.setText(
            text("common.close")
        )

        self.button_box.rejected.connect(
            self.reject
        )
        self.training_control_group = QGroupBox(
            text("training.group.control")
        )
        training_control_layout = QHBoxLayout(self.training_control_group)
        training_control_layout.setContentsMargins(8, 5, 8, 3)
        training_control_layout.setSpacing(8)
        training_control_layout.addWidget(self.repeat_initialization_button)
        training_control_layout.addStretch(1)
        training_control_layout.addWidget(self.start_epochs_button)
        training_control_layout.addWidget(self.continue_button)
        training_control_layout.addWidget(self.stop_button)
        self.training_control_info = QPushButton("i")
        self.training_control_info.setFixedSize(26, 24)
        self.training_control_info.setToolTip(
            text("training.info.control.tooltip")
        )
        self.training_control_info.clicked.connect(
            lambda: self.show_training_information(
                "training.info.control.title",
                "training.info.control.text",
            )
        )
        training_control_layout.addWidget(self.training_control_info)

        self.training_control_widgets = [
            self.training_target_group,
            self.training_control_group,
        ]

        self.test_and_debug_layout = QHBoxLayout()
        self.test_and_debug_layout.setSpacing(10)
        self.experiment_button.setMinimumWidth(125)
        self.test_and_debug_layout.addWidget(self.experiment_button)
        self.test_and_debug_layout.addWidget(self.test_network_button)
        self.test_and_debug_layout.addWidget(self.debug_training_button, 1)
        self.test_and_debug_layout.addWidget(self.load_history_button)
        self.training_tools_info = QPushButton("i")
        self.training_tools_info.setFixedSize(26, 24)
        self.training_tools_info.setToolTip(
            text("training.info.tools.tooltip")
        )
        self.training_tools_info.clicked.connect(
            lambda: self.show_training_information(
                "training.info.tools.title",
                "training.info.tools.text",
            )
        )
        self.test_and_debug_layout.addWidget(self.training_tools_info)
        self.close_separator = QFrame()
        self.close_separator.setFrameShape(QFrame.Shape.VLine)
        self.close_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.test_and_debug_layout.addWidget(self.close_separator)
        self.test_and_debug_layout.addWidget(self.button_box)

        self.view_mode_layout = QHBoxLayout()
        self.view_mode_layout.setSpacing(6)
        self.training_run_label = QLabel(
            text("training.run.not_started")
        )
        self.view_mode_layout.addWidget(self.training_run_label)
        self.monitor_view_button = QPushButton()
        self.monitor_view_button.setCheckable(
            True
        )
        self.monitor_view_button.setToolTip(
            text("training.view.monitor_tooltip")
        )
        self.monitor_view_button.setStyleSheet(
            "QPushButton:checked {"
            "background-color: #dff2e3;"
            "border: 1px solid #5d9b68;"
            "}"
        )
        self.monitor_view_button.setVisible(
            False
        )
        self.monitor_view_button.toggled.connect(
            self.set_monitoring_from_compact_view
        )
        self.monitor_training_data.toggled.connect(
            self.monitoring_checkbox_changed
        )
        self.view_mode_layout.addWidget(
            self.monitor_view_button
        )
        self.minimal_run_label = QLabel()
        self.minimal_run_label.setFont(self.fixed_font)
        self.minimal_run_label.setVisible(False)
        self.view_mode_layout.addWidget(self.minimal_run_label)
        self.view_mode_layout.addWidget(
            self.minimal_epoch_label
        )
        self.minimal_time_label = QLabel()
        self.minimal_time_label.setFont(self.fixed_font)
        self.minimal_time_label.setStyleSheet(
            "QLabel {"
            "background-color: #eef4f8;"
            "border: 1px solid #b9cbd8;"
            "border-radius: 4px;"
            "padding: 5px 8px;"
            "}"
        )
        self.minimal_time_label.setVisible(False)
        self.view_mode_layout.addWidget(self.minimal_time_label)
        self.minimal_target_label = QLabel()
        self.minimal_target_label.setFont(self.fixed_font)
        self.minimal_target_label.setVisible(False)
        self.view_mode_layout.addWidget(self.minimal_target_label)

        self.minimal_monitor_checkbox = QCheckBox(
            text("training.view.minimal_monitor")
        )
        self.minimal_monitor_checkbox.setToolTip(
            text("training.view.monitor_tooltip")
        )
        self.minimal_monitor_checkbox.setVisible(False)
        self.minimal_monitor_checkbox.toggled.connect(
            self.set_monitoring_from_compact_view
        )
        self.view_mode_layout.addWidget(self.minimal_monitor_checkbox)

        self.minimal_start_button = QPushButton(
            text("training.view.minimal_start")
        )
        self.minimal_start_button.setFixedHeight(28)
        self.minimal_start_button.setToolTip(
            text("training.button.start_new")
        )
        self.minimal_start_button.clicked.connect(
            self.start_epochs_button.click
        )
        self.minimal_start_button.setVisible(False)
        self.view_mode_layout.addWidget(self.minimal_start_button)

        self.minimal_continue_button = QPushButton(
            text("training.button.resume")
        )
        self.minimal_continue_button.setFixedHeight(28)
        self.minimal_continue_button.setToolTip(
            text("training.button.resume_tooltip")
        )
        self.minimal_continue_button.clicked.connect(
            self.continue_button.click
        )
        self.minimal_continue_button.setVisible(False)
        self.view_mode_layout.addWidget(self.minimal_continue_button)

        self.minimal_stop_button = QPushButton(
            text("training.button.stop")
        )
        self.minimal_stop_button.setFixedHeight(28)
        self.minimal_stop_button.setToolTip(
            text("training.button.stop")
        )
        self.minimal_stop_button.clicked.connect(self.stop_button.click)
        self.minimal_stop_button.setVisible(False)
        self.view_mode_layout.addWidget(self.minimal_stop_button)
        self.view_mode_layout.addStretch(
            1
        )

        self.full_view_button = QPushButton(
            text("training.view.full")
        )
        self.full_view_button.setVisible(
            False
        )
        self.full_view_button.clicked.connect(
            self.show_full_view
        )
        self.view_mode_layout.addWidget(
            self.full_view_button
        )

        self.compact_view_button = QPushButton(
            text("training.view.compact")
        )
        self.compact_view_button.setToolTip(
            text("training.view.compact_tooltip")
        )
        self.compact_view_button.clicked.connect(
            self.show_compact_view
        )

        self.minimal_view_button = QPushButton(
            text("training.view.minimal")
        )
        self.minimal_view_button.setToolTip(
            text("training.view.minimal_tooltip")
        )
        self.minimal_view_button.clicked.connect(
            self.show_minimal_view
        )
        self.view_mode_layout.addWidget(
            self.minimal_view_button
        )
        self.view_mode_layout.addWidget(
            self.compact_view_button
        )

        self.content_layout = QGridLayout()
        self.content_layout.setSpacing(
            12
        )
        self.data_group.setMaximumWidth(
            540
        )
        self.parameter_group.setMaximumWidth(
            540
        )
        self.training_values_group.setMaximumWidth(540)
        self.execution_group.setMaximumWidth(540)
        self.training_target_group.setMaximumWidth(540)

        self.content_layout.addWidget(
            self.data_group,
            0,
            0
        )
        self.content_layout.addWidget(
            self.result_group,
            0,
            1
        )
        self.content_layout.addWidget(
            self.compact_status_label,
            0,
            1
        )
        self.content_layout.addWidget(
            self.left_training_container,
            1,
            0
        )
        self.content_layout.addWidget(
            self.error_chart_group,
            1,
            1
        )
        self.content_layout.addWidget(
            self.training_target_group,
            2,
            0
        )
        self.content_layout.addWidget(
            self.training_control_group,
            2,
            1
        )
        self.content_layout.addLayout(
            self.test_and_debug_layout,
            3,
            1
        )
        self.content_layout.setColumnStretch(
            0,
            0
        )
        self.content_layout.setColumnStretch(
            1,
            1
        )
        self.content_layout.setRowStretch(
            1,
            0
        )

        self.main_layout.addLayout(
            self.view_mode_layout
        )
        self.main_layout.addLayout(
            self.content_layout
        )

        # Die Vollansicht bleibt auch auf kleineren Notebookbildschirmen
        # vollständig innerhalb der verfügbaren Arbeitsfläche. Auf größeren
        # Monitoren erhält der Fehlerverlauf eine angenehm breite Darstellung.
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            initial_width = max(540, min(1184, available.width() - 40))
            initial_height = max(600, min(720, available.height() - 40))
            self.resize(initial_width, initial_height)
        QTimer.singleShot(0, self.sync_training_area_heights)

        self.sync_compact_monitor_button(
            self.monitor_training_data.isChecked()
        )

    def sync_training_area_heights(self):
        """Richtet die Unterkanten der linken Gruppen und der Kurve aus."""

        if not hasattr(self, "left_training_container"):
            return
        target_height = self.left_training_container.sizeHint().height()
        if target_height <= 0:
            return
        self.error_chart_group.setMinimumHeight(target_height)
        self.error_chart_group.setMaximumHeight(target_height)
        self.content_layout.invalidate()

    def format_workload_integer(self, value):
        """Formatiert große Zählwerte passend zur gewählten Sprache."""

        formatted = f"{int(value):,}"
        if self.language.current_language == "de":
            return formatted.replace(",", ".")
        return formatted

    def project_directory_name(self):
        """Liefert für die kompakte Anzeige nur den Projektordnernamen."""

        if self.project_path:
            path = Path(self.project_path)
            return path.parent.name if path.suffix else path.name
        if self.training_file_path:
            path = Path(self.training_file_path)
            parent = path.parent
            if parent.name.lower() == "trainingsdaten":
                parent = parent.parent
            return parent.name
        return self.language.text("training.data.new_project")

    def create_workload_summary(self):
        """Berechnet einmalig die didaktische Aufwandsschätzung je Epoche."""

        try:
            layers = self.network.get_topological_layers()
            layer_sizes = [len(layer) for layer in layers if layer]
        except ValueError:
            layer_sizes = []

        if not layer_sizes:
            input_count = len(self.network.get_input_neurons())
            hidden_count = len(self.network.get_hidden_neurons())
            output_count = len(self.network.get_output_neurons())
            layer_sizes = [input_count]
            if hidden_count:
                layer_sizes.append(hidden_count)
            layer_sizes.append(output_count)

        structure = " → ".join(str(size) for size in layer_sizes)
        weight_count = len(self.network.get_connections())
        bias_count = sum(
            1
            for neuron in self.network.get_neurons()
            if neuron.neuron_type != NeuronType.INPUT
        )
        parameter_count = weight_count + bias_count
        forward_operations = weight_count * len(self.records)
        training_operations = forward_operations * 3
        self.training_operations_per_record = weight_count * 3

        labels = (
            self.language.text("training.data.network_short"),
            self.language.text("training.data.parameters_short"),
            self.language.text("training.data.operations_short"),
        )
        label_width = max(len(label) for label in labels)
        values = (
            structure,
            self.language.text(
                "training.data.parameter_value",
                parameters=self.format_workload_integer(parameter_count),
                weights=self.format_workload_integer(weight_count),
                biases=self.format_workload_integer(bias_count),
            ),
            self.language.text(
                "training.data.operation_value",
                operations=self.format_workload_integer(training_operations),
            ),
        )
        return "\n".join(
            f"{label:<{label_width}} {value}"
            for label, value in zip(labels, values)
        )

    def reset_total_workload(self):
        """Blendet die Gesamtschätzung während eines neuen Laufs aus."""

        self.processed_training_records = 0
        self.total_workload_label.clear()
        self.total_workload_label.setVisible(False)

    def show_total_workload(self):
        """Zeigt den Aufwand der tatsächlich bearbeiteten Datensätze."""

        total_operations = (
            self.processed_training_records
            * self.training_operations_per_record
        )
        self.total_workload_label.setText(
            self.language.text(
                "training.data.total_operations",
                operations=self.format_workload_integer(total_operations)
            )
        )
        self.total_workload_label.setVisible(True)

    def sync_compact_monitor_button(self, enabled):
        """Hält Kompaktschalter und normalen Monitoring-Haken synchron."""

        enabled = bool(enabled)
        self.monitor_view_button.blockSignals(
            True
        )
        self.monitor_view_button.setChecked(
            enabled
        )
        self.monitor_view_button.setText(
            self.language.text("training.view.monitor_on")
            if enabled
            else self.language.text("training.view.monitor_off")
        )
        self.monitor_view_button.blockSignals(
            False
        )

    def monitoring_checkbox_changed(self, enabled):
        """Übernimmt den Monitoring-Haken auch während des Trainings sofort."""

        enabled = bool(enabled)
        self.fast_mode.setChecked(not enabled)
        self.sync_compact_monitor_button(
            enabled
        )
        self.minimal_monitor_checkbox.blockSignals(True)
        self.minimal_monitor_checkbox.setChecked(enabled)
        self.minimal_monitor_checkbox.blockSignals(False)

        if self.is_training:
            trainer = getattr(self.network, "trainer", None)
            if trainer is not None:
                trainer.capture_step_details = enabled
                trainer.visual_updates_enabled = enabled
        self.training_monitoring_changed.emit(enabled)

    def set_monitoring_from_compact_view(self, enabled):
        """Übernimmt den Monitoring-Schalter der Kompaktansicht sofort."""

        enabled = bool(enabled)
        self.monitor_training_data.setChecked(
            enabled
        )

    def update_compact_status(self, _text=None):
        """Aktualisiert die zweizeilige Zusammenfassung der Kompaktansicht."""

        epoch_text = self.result_epochs.text().strip() or "–"
        elapsed_text = self.result_elapsed_time.text().strip() or "0.0 s"
        status_text = (
            self.result_status.text().strip()
            or self.language.text("training.status.ready")
        )
        start_text = (
            self.error_chart_start.text()
            if hasattr(self, "error_chart_start")
            else self.language.text("training.chart.start_error", value="–")
        )
        current_text = (
            self.error_chart_current.text()
            if hasattr(self, "error_chart_current")
            else self.language.text("training.chart.current_error", value="–")
        )
        self.compact_status_label.setText(
            self.language.text(
                "training.compact.status",
                epoch=epoch_text,
                elapsed=elapsed_text,
                status=status_text,
                start=start_text,
                current=current_text
            )
        )
        self.minimal_epoch_label.setText(
            self.language.text(
                "training.compact.epoch",
                epoch=epoch_text
            )
        )
        if hasattr(self, "minimal_time_label"):
            self.minimal_time_label.setText(
                self.language.text(
                    "training.view.elapsed_short",
                    elapsed=elapsed_text,
                )
            )
        run_text = (
            str(self.current_run_id)
            if self.current_run_id is not None
            else "–"
        )
        if hasattr(self, "minimal_run_label"):
            self.minimal_run_label.setText(
                self.language.text("training.view.run_short", run=run_text)
            )
        target_mode = getattr(self, "training_target_mode", "epochs")
        if target_mode == "one":
            target_text = self.language.text("training.view.target_one")
        elif target_mode == "limit":
            target_text = self.language.text("training.view.target_limit")
        else:
            epoch_count = getattr(self, "epoch_count", None)
            epochs = epoch_count.value() if epoch_count is not None else "–"
            target_text = self.language.text(
                "training.view.target_epochs",
                epochs=epochs,
            )
        if hasattr(self, "minimal_target_label"):
            self.minimal_target_label.setText(target_text)

    def set_minimal_controls_visible(self, visible):
        """Blendet die schmale Trainingssteuerung gemeinsam ein oder aus."""

        for widget in (
            self.minimal_run_label,
            self.minimal_time_label,
            self.minimal_target_label,
            self.minimal_monitor_checkbox,
            self.minimal_start_button,
            self.minimal_continue_button,
            self.minimal_stop_button,
        ):
            widget.setVisible(bool(visible))

    def sync_minimal_training_buttons(self):
        """Spiegelt die Zustände der Trainingsknöpfe in der Minimalansicht."""

        self.minimal_start_button.setEnabled(
            self.start_epochs_button.isEnabled()
        )
        self.minimal_continue_button.setEnabled(
            self.continue_button.isEnabled()
        )
        self.minimal_stop_button.setEnabled(
            self.stop_button.isEnabled()
        )

    def toggle_compact_view(self):
        """Wechselt zwischen vollständigem Dialog und Trainingsmonitor."""

        if self.compact_mode or self.minimal_mode:
            self.show_full_view()
        else:
            self.show_compact_view()

    def show_compact_view(self):
        if self.compact_mode:
            return

        if not self.minimal_mode:
            self.full_view_geometry = self.geometry()

        self.compact_mode = True
        self.minimal_mode = False
        self.setWindowTitle(
            self.language.text("training.window.compact_title")
        )
        self.full_view_button.setVisible(
            True
        )
        self.full_view_button.setText(
            self.language.text("training.view.full")
        )
        self.compact_view_button.setVisible(
            False
        )
        self.compact_view_button.setText(
            self.language.text("training.view.compact")
        )
        self.minimal_view_button.setVisible(
            True
        )
        self.monitor_view_button.setVisible(
            True
        )
        self.minimal_epoch_label.setVisible(
            False
        )
        self.set_minimal_controls_visible(False)
        self.training_run_label.setVisible(True)

        self.scaling_warning_label.setVisible(
            False
        )
        self.imbalance_warning_label.setVisible(False)
        self.data_group.setVisible(
            False
        )
        self.left_training_container.setVisible(False)
        self.result_group.setVisible(
            False
        )
        self.compact_status_label.setVisible(
            True
        )
        self.error_chart_group.setVisible(
            True
        )
        self.content_layout.removeWidget(self.error_chart_group)
        self.content_layout.addWidget(
            self.error_chart_group,
            1,
            0,
            1,
            2
        )
        self.error_chart_group.setMaximumHeight(16777215)
        self.error_chart_start.setVisible(
            False
        )
        self.error_chart_current.setVisible(
            False
        )
        self.experiment_button.setVisible(False)
        self.test_network_button.setVisible(
            False
        )
        self.debug_training_button.setVisible(
            False
        )
        self.training_tools_info.setVisible(False)
        self.load_history_button.setVisible(False)
        self.close_separator.setVisible(False)
        self.button_box.setVisible(
            False
        )
        for control in self.training_control_widgets:
            control.setVisible(
                True
            )

        self.content_layout.invalidate()
        self.main_layout.invalidate()
        QTimer.singleShot(
            0,
            self.resize_compact_view
        )

    def resize_compact_view(self):
        if not self.compact_mode:
            return

        top_left = self.pos()

        # Nach dem Ausblenden der Vollansicht muss Qt zunächst die
        # Mindestgröße aller noch sichtbaren Layoutbestandteile berechnen.
        # Darin sind insbesondere die 40 Pixel unterhalb der Kurvenfläche
        # für Epochenwerte und Achsentitel enthalten. Eine feste Dialoghöhe
        # reicht bei unterschiedlichen Windows-Skalierungen nicht aus.
        self.error_chart_layout.activate()
        self.content_layout.activate()
        self.main_layout.activate()
        required_height = max(
            430,
            self.minimumSizeHint().height()
        )
        self.setMinimumSize(
            620,
            required_height
        )
        screen = QApplication.primaryScreen()
        available_width = (
            screen.availableGeometry().width() - 40
            if screen is not None
            else self.minimumSizeHint().width()
        )
        required_width = max(
            720,
            min(self.minimumSizeHint().width(), available_width)
        )
        self.resize(required_width, required_height)
        self.move(
            top_left
        )

    def show_minimal_view(self):
        """Zeigt eine schmale Trainingssteuerung über der Netzwerkansicht."""

        if self.minimal_mode:
            return

        if not self.compact_mode:
            self.full_view_geometry = self.geometry()

        top_left = self.pos()
        self.compact_mode = False
        self.minimal_mode = True
        self.setWindowTitle(
            self.language.text("training.window.minimal_title")
        )

        self.monitor_view_button.setVisible(
            False
        )
        self.minimal_epoch_label.setVisible(
            True
        )
        self.training_run_label.setVisible(False)
        self.update_compact_status()
        self.sync_minimal_training_buttons()
        self.minimal_monitor_checkbox.blockSignals(True)
        self.minimal_monitor_checkbox.setChecked(
            self.monitor_training_data.isChecked()
        )
        self.minimal_monitor_checkbox.blockSignals(False)
        self.set_minimal_controls_visible(True)
        self.full_view_button.setVisible(
            True
        )
        self.full_view_button.setText(
            self.language.text("training.view.full_short")
        )
        self.compact_view_button.setVisible(
            True
        )
        self.compact_view_button.setText(
            self.language.text("training.view.compact_short")
        )
        self.minimal_view_button.setVisible(
            False
        )

        self.scaling_warning_label.setVisible(
            False
        )
        self.imbalance_warning_label.setVisible(False)
        self.data_group.setVisible(
            False
        )
        self.left_training_container.setVisible(False)
        self.result_group.setVisible(
            False
        )
        self.compact_status_label.setVisible(
            False
        )
        self.error_chart_group.setVisible(
            False
        )
        self.experiment_button.setVisible(False)
        self.test_network_button.setVisible(
            False
        )
        self.debug_training_button.setVisible(
            False
        )
        self.training_tools_info.setVisible(False)
        self.load_history_button.setVisible(False)
        self.close_separator.setVisible(False)
        self.button_box.setVisible(
            False
        )
        for control in self.training_control_widgets:
            control.setVisible(
                False
            )

        self.content_layout.invalidate()
        self.main_layout.invalidate()
        QTimer.singleShot(
            0,
            lambda position=top_left:
            self.resize_minimal_view(position)
        )

    def resize_minimal_view(self, top_left=None):
        """Passt den kleinen Trainingsmonitor an seine einzige Zeile an."""

        if not self.minimal_mode:
            return

        if top_left is None:
            top_left = self.pos()

        self.view_mode_layout.activate()
        self.main_layout.activate()
        required_height = max(
            64,
            self.minimumSizeHint().height()
        )
        self.setMinimumSize(
            760,
            required_height
        )
        screen = QApplication.primaryScreen()
        available_width = (
            screen.availableGeometry().width() - 40
            if screen is not None
            else self.minimumSizeHint().width()
        )
        required_width = min(
            max(760, self.minimumSizeHint().width()),
            available_width,
        )
        self.resize(required_width, required_height)
        self.move(
            top_left
        )

    def show_full_view(self):
        if not self.compact_mode and not self.minimal_mode:
            return

        self.compact_mode = False
        self.minimal_mode = False
        self.setWindowTitle(
            self.language.text("training.window.title")
        )
        self.full_view_button.setVisible(
            False
        )
        self.full_view_button.setText(
            self.language.text("training.view.full")
        )
        self.compact_view_button.setVisible(
            True
        )
        self.compact_view_button.setText(
            self.language.text("training.view.compact")
        )
        self.minimal_view_button.setVisible(
            True
        )
        self.monitor_view_button.setVisible(
            False
        )
        self.minimal_epoch_label.setVisible(
            False
        )
        self.set_minimal_controls_visible(False)
        self.training_run_label.setVisible(True)

        self.scaling_warning_label.setVisible(
            bool(self.scaling_warning_label.text())
        )
        self.imbalance_warning_label.setVisible(
            self.imbalance_warning_present
        )
        self.data_group.setVisible(
            True
        )
        self.left_training_container.setVisible(True)
        self.result_group.setVisible(
            True
        )
        self.compact_status_label.setVisible(
            False
        )
        self.error_chart_group.setVisible(
            self.show_error_chart.isChecked()
        )
        self.content_layout.removeWidget(self.error_chart_group)
        self.content_layout.addWidget(
            self.error_chart_group,
            1,
            1
        )
        self.error_chart_start.setVisible(False)
        self.error_chart_current.setVisible(False)
        self.experiment_button.setVisible(True)
        self.test_network_button.setVisible(
            True
        )
        self.debug_training_button.setVisible(
            True
        )
        self.training_tools_info.setVisible(True)
        self.load_history_button.setVisible(True)
        self.close_separator.setVisible(True)
        self.button_box.setVisible(
            True
        )
        for control in self.training_control_widgets:
            control.setVisible(
                True
            )

        self.setMinimumSize(
            540,
            0
        )
        self.content_layout.invalidate()
        self.main_layout.invalidate()

        if self.full_view_geometry is not None:
            self.setGeometry(
                self.full_view_geometry
            )
        QTimer.singleShot(0, self.sync_training_area_heights)


    @staticmethod
    def default_training_settings():
        """
        Liefert die Standardwerte des Trainingsdialogs.
        """

        return {
            "initialize_network": False,
            "weight_initialization": "auto",
            "bias_initialization": "zero",
            "learning_rate": 0.01,
            "momentum": 0.0,
            "error_limit": 0.01,
            "maximum_epochs": 1000,
            "training_section_epochs": 1000,
            "fast_mode": False,
            "monitor_training_data": True,
            "show_error_chart": True,
            "error_chart_scale": "linear",
            "training_target_mode": "epochs"
        }

    @classmethod
    def normalize_training_settings(
        cls,
        training_settings
    ):
        """
        Ergänzt fehlende Einstellungen mit Standardwerten.
        """

        normalized = cls.default_training_settings()

        if isinstance(
            training_settings,
            dict
        ):
            for key in normalized:
                if key in training_settings:
                    normalized[key] = training_settings[key]

        return normalized

    def get_training_settings(self):
        """
        Liefert die aktuell im Dialog eingestellten
        Trainingsparameter für die Projektspeicherung.
        """

        return {
            "initialize_network": (
                self.initialize_network.isChecked()
            ),
            "weight_initialization": str(
                self.weight_initialization_combo.currentData()
            ),
            "bias_initialization": str(
                self.bias_initialization_combo.currentData()
            ),
            "learning_rate": float(
                self.learning_rate.value()
            ),
            "momentum": float(self.momentum.value()),
            "error_limit": float(
                max(
                    self.error_limit.value(),
                    0.0000000001
                )
            ),
            "maximum_epochs": int(
                self.maximum_epochs.value()
            ),
            "training_section_epochs": int(self.epoch_count.value()),
            "fast_mode": not self.monitor_training_data.isChecked(),
            "monitor_training_data": (
                self.monitor_training_data.isChecked()
            ),
            "show_error_chart": (
                self.show_error_chart.isChecked()
            ),
            "error_chart_scale": str(
                self.error_chart_scale.currentData()
            ),
            "training_target_mode": self.training_target_mode
        }

    def set_next_training_run_id(self, run_id):
        """Legt die Nummer des nächsten neu begonnenen Trainingslaufs fest."""

        try:
            normalized = int(run_id)
        except (TypeError, ValueError):
            normalized = 1
        self.next_training_run_id = max(1, normalized)

    def update_training_run_label(self):
        """Zeigt Nummer und ursprünglichen Startzeitpunkt des aktuellen Laufs."""

        if self.current_run_id is None or not self.current_run_timestamp:
            self.training_run_label.setText(
                self.language.text("training.run.not_started")
            )
            self.update_compact_status()
            return

        try:
            started = datetime.fromisoformat(self.current_run_timestamp)
            date_text = started.strftime("%d.%m.%Y")
            time_text = started.strftime("%H:%M:%S")
        except (TypeError, ValueError):
            date_text = str(self.current_run_timestamp).replace("T", " ")
            time_text = ""

        self.training_run_label.setText(
            self.language.text(
                "training.run.info",
                run=self.current_run_id,
                date=date_text,
                time=time_text,
            )
        )
        self.update_compact_status()

    def begin_new_training_run(self):
        """Vergibt Nummer und Startzeit für einen bewusst neuen Lauf."""

        self.current_run_id = self.next_training_run_id
        self.next_training_run_id += 1
        self.current_run_timestamp = datetime.now().isoformat(
            timespec="seconds"
        )
        self.current_run_completed_epochs = 0
        self.current_run_requested_epochs = 0
        self.current_run_elapsed_seconds = 0.0
        self.current_run_initialized = self.initialize_network.isChecked()
        self.current_run_learning_rate = float(self.learning_rate.value())
        self.current_run_momentum = float(self.momentum.value())
        self.current_run_can_continue = False
        self.current_run_stopped = False
        self.update_training_run_label()

    def select_training_target(self, mode):
        """Wählt ein gemeinsames Trainingsziel für Start und Fortsetzung."""

        if mode not in {"one", "epochs", "limit"}:
            mode = "epochs"
        self.training_target_mode = mode
        self.update_training_target_display()
        self.update_compact_status()

    def create_group_info_button(self, group, title_key, message_key):
        """Erzeugt ein dezentes Info-Symbol oben rechts in einer Gruppe."""

        button = QPushButton("i", group)
        button.setFixedSize(26, 24)
        button.setToolTip(self.language.text(title_key))
        button.clicked.connect(
            lambda: self.show_training_information(title_key, message_key)
        )
        self.group_info_buttons[group] = button
        group.installEventFilter(self)
        QTimer.singleShot(0, lambda: self.position_group_info_button(group))
        return button

    def position_group_info_button(self, group):
        """Hält ein Gruppen-Info-Symbol unabhängig von der Breite am Rand."""

        button = self.group_info_buttons.get(group)
        if button is None:
            return
        button.move(max(0, group.width() - button.width() - 12), 20)
        button.raise_()

    def show_training_information(self, title_key, message_key):
        """Zeigt eine schlanke, tonlose Bedienerklärung im Programmstil."""

        dialog = QDialog(self)
        dialog.setWindowTitle(self.language.text(title_key))
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        explanation = QLabel(self.language.text(message_key))
        explanation.setWordWrap(True)
        explanation.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        explanation.setStyleSheet(
            "QLabel { background: #fff8d8; border: 1px solid #d6c36a; "
            "border-radius: 4px; padding: 10px; }"
        )
        layout.addWidget(explanation)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.language.text("common.close")
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def eventFilter(self, watched, event):
        """Wählt das Epochenfeld auch bei einem Klick ohne Wertänderung."""

        if (
            watched in self.group_info_buttons
            and event.type() == QEvent.Type.Resize
        ):
            self.position_group_info_button(watched)

        epoch_count = getattr(self, "epoch_count", None)
        epoch_widgets = (
            {epoch_count, epoch_count.lineEdit()}
            if epoch_count is not None
            else set()
        )
        if (
            watched in epoch_widgets
            and event.type() in {
                QEvent.Type.FocusIn,
                QEvent.Type.MouseButtonPress,
            }
            and not self.is_training
        ):
            self.select_training_target("epochs")
        return super().eventFilter(watched, event)

    def update_training_target_display(self):
        """Synchronisiert Optionsfelder und zugehöriges Zahlenfeld."""

        one_selected = self.training_target_mode == "one"
        limit_selected = self.training_target_mode == "limit"
        epochs_selected = self.training_target_mode == "epochs"
        self.epoch_1_button.blockSignals(True)
        self.epoch_count_button.blockSignals(True)
        self.until_limit_button.blockSignals(True)
        self.epoch_1_button.setChecked(one_selected)
        self.epoch_count_button.setChecked(epochs_selected)
        self.until_limit_button.setChecked(limit_selected)
        self.epoch_1_button.blockSignals(False)
        self.epoch_count_button.blockSignals(False)
        self.until_limit_button.blockSignals(False)
        self.epoch_count.setEnabled(
            epochs_selected and not self.is_training
        )
        self.epoch_count_suffix.setEnabled(
            epochs_selected and not self.is_training
        )

    def start_selected_training(self):
        """Startet bewusst einen neuen Lauf mit dem gewählten Trainingsziel."""

        maximum_epochs, stop_at_limit = self.selected_training_target()
        self.execute_training(maximum_epochs, stop_at_limit)

    def selected_training_target(self):
        """Liefert Epochenzahl und Abbruchart der sichtbaren Zielauswahl."""

        if self.training_target_mode == "one":
            return 1, False
        elif self.training_target_mode == "limit":
            return self.maximum_epochs.value(), True
        return self.epoch_count.value(), False

    def repeat_with_same_initialization(self):
        """Beginnt einen neuen Lauf mit dem Ausgangszustand des aktiven Laufs."""

        if (
            self.is_training
            or not self.training_state_is_compatible(
                self.current_run_initial_state
            )
        ):
            return
        maximum_epochs, stop_at_limit = self.selected_training_target()
        self.execute_training(
            maximum_epochs,
            stop_at_limit,
            initial_state=deepcopy(self.current_run_initial_state),
            shuffle_seed=self.current_run_shuffle_seed,
        )

    def suggest_training_parameters(self):
        """Ermittelt einen konservativen Startvorschlag aus Netz und Daten."""

        hidden_neurons = [
            neuron for neuron in self.network.get_neurons()
            if neuron.neuron_type == NeuronType.HIDDEN
        ]
        connections = self.network.get_connections()
        activations = {
            str(neuron.activation_function).casefold()
            for neuron in self.network.get_neurons()
            if neuron.neuron_type != NeuronType.INPUT
        }
        all_binary_outputs = bool(self.output_columns) and all(
            mapping.get("data_type") == "binary"
            for mapping in self.output_columns
        )

        if any("relu" in activation for activation in activations):
            learning_rate = 0.01
            activation_reason = self.language.text(
                "training.suggestion.reason.relu"
            )
        elif len(hidden_neurons) > 20 or len(connections) > 200:
            learning_rate = 0.05
            activation_reason = self.language.text(
                "training.suggestion.reason.larger_network"
            )
        else:
            learning_rate = 0.1
            activation_reason = self.language.text(
                "training.suggestion.reason.small_network"
            )

        momentum = 0.0
        error_limit = 0.001 if all_binary_outputs else 0.0001
        if len(connections) <= 100 and len(self.records) <= 100:
            maximum_epochs = 100000
        elif len(connections) <= 1000 and len(self.records) <= 1000:
            maximum_epochs = 250000
        else:
            maximum_epochs = 1000000

        output_reason = self.language.text(
            "training.suggestion.reason.binary_outputs"
            if all_binary_outputs
            else "training.suggestion.reason.analog_outputs"
        )
        def display_number(value):
            number_text = format_number(value)
            return (
                number_text.replace(".", ",")
                if self.language.current_language == "de"
                else number_text
            )

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Information)
        message_box.setWindowTitle(
            self.language.text("training.suggestion.title")
        )
        message_box.setText(
            self.language.text(
                "training.suggestion.values",
                learning_rate=display_number(learning_rate),
                momentum="0,00" if self.language.current_language == "de" else "0.00",
                error_limit=display_number(error_limit),
                maximum_epochs=str(maximum_epochs),
            )
        )
        message_box.setInformativeText(
            self.language.text(
                "training.suggestion.explanation",
                network_reason=activation_reason,
                output_reason=output_reason,
            )
        )
        apply_button = message_box.addButton(
            self.language.text("training.suggestion.apply"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        message_box.addButton(
            self.language.text("common.cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        message_box.exec()
        if message_box.clickedButton() is not apply_button:
            return

        self.initialize_network.setChecked(True)
        self.weight_initialization_combo.setCurrentIndex(
            self.weight_initialization_combo.findData("auto")
        )
        self.bias_initialization_combo.setCurrentIndex(
            self.bias_initialization_combo.findData("zero")
        )
        self.learning_rate.setValue(learning_rate)
        self.momentum.setValue(momentum)
        self.error_limit.setValue(error_limit)
        self.maximum_epochs.setValue(maximum_epochs)

    def prepare_continuation_parameters(self):
        """Sichert für eine echte Fortsetzung Lernrate und Momentum."""

        if self.is_training or not self.current_run_can_continue:
            return False

        original_rate = self.current_run_learning_rate
        if original_rate is None:
            original_rate = float(self.learning_rate.value())
            self.current_run_learning_rate = original_rate

        original_momentum = self.current_run_momentum
        if original_momentum is None:
            original_momentum = float(self.momentum.value())
            self.current_run_momentum = original_momentum

        learning_rate_changed = not math.isclose(
            float(self.learning_rate.value()),
            float(original_rate),
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        momentum_changed = not math.isclose(
            float(self.momentum.value()),
            float(original_momentum),
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        if learning_rate_changed or momentum_changed:
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Icon.Question)
            message_box.setWindowTitle(
                self.language.text("training.resume.parameters_title")
            )
            message_box.setText(
                self.language.text(
                    "training.resume.parameters_changed",
                    learning_rate=format_number(original_rate),
                    momentum=format_number(original_momentum),
                )
            )
            restore_button = message_box.addButton(
                self.language.text("training.resume.restore_and_continue"),
                QMessageBox.ButtonRole.AcceptRole,
            )
            message_box.addButton(
                self.language.text("common.cancel"),
                QMessageBox.ButtonRole.RejectRole,
            )
            message_box.exec()
            if message_box.clickedButton() is not restore_button:
                return False
            self.learning_rate.setValue(original_rate)
            self.momentum.setValue(original_momentum)
        return True

    def continue_selected_training(self):
        """Setzt denselben Lauf mit dem gemeinsam gewählten Trainingsziel fort."""

        if not self.prepare_continuation_parameters():
            return

        total_epoch_limit = int(self.maximum_epochs.value())
        remaining_epochs = total_epoch_limit - self.current_run_completed_epochs
        if remaining_epochs <= 0:
            QMessageBox.information(
                self,
                self.language.text("training.message.title"),
                self.language.text(
                    "training.resume.maximum_reached",
                    epochs=self.current_run_completed_epochs,
                ),
            )
            return

        if self.training_target_mode == "one":
            section_epochs, stop_at_limit = 1, False
        elif self.training_target_mode == "limit":
            section_epochs, stop_at_limit = remaining_epochs, True
        else:
            section_epochs = min(self.epoch_count.value(), remaining_epochs)
            stop_at_limit = False
        self.execute_training(
            maximum_epochs=section_epochs,
            stop_at_error_limit=stop_at_limit,
            continue_existing=True,
        )

    def load_previous_training_run(self):
        """Nutzt die zentrale Historie zum Wiederherstellen eines Netzstandes."""

        parent = self.parent()
        if parent is None or not hasattr(parent, "open_training_history"):
            return
        restored_entry = parent.open_training_history()
        if not isinstance(restored_entry, dict):
            return
        settings = self.normalize_training_settings(
            getattr(parent, "training_settings", None)
        )
        self.initialize_network.setChecked(settings["initialize_network"])
        self.learning_rate.setValue(settings["learning_rate"])
        self.momentum.setValue(settings.get("momentum", 0.0))
        self.error_limit.setValue(settings["error_limit"])
        self.maximum_epochs.setValue(settings["maximum_epochs"])
        self.epoch_count.setValue(settings["training_section_epochs"])
        self.select_training_target(settings["training_target_mode"])
        self.monitor_training_data.setChecked(
            settings["monitor_training_data"]
        )
        self.fast_mode.setChecked(
            not self.monitor_training_data.isChecked()
        )
        self.weight_initialization_combo.setCurrentIndex(max(
            0, self.weight_initialization_combo.findData(
                settings["weight_initialization"]
            )
        ))
        self.bias_initialization_combo.setCurrentIndex(max(
            0, self.bias_initialization_combo.findData(
                settings["bias_initialization"]
            )
        ))
        self.network.reset_runtime_values()
        for neuron in self.network.get_neurons():
            neuron.update()
        self.show_restored_training_run(restored_entry)

    def show_restored_training_run(self, history_entry):
        """Zeigt Ergebnis und Fehlerkurve eines wiederhergestellten Laufs."""

        try:
            completed_epochs = int(history_entry.get("completed_epochs", 0))
            start_error = float(history_entry.get("start_error", 0.0))
            end_error = float(history_entry.get("end_error", 0.0))
            maximum_error = float(
                history_entry.get("maximum_absolute_error", 0.0)
            )
            elapsed_seconds = float(history_entry.get("elapsed_seconds", 0.0))
        except (TypeError, ValueError):
            return

        curve_points = []
        for point in history_entry.get("curve_points", []):
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            try:
                epoch = int(point[0])
                error_value = float(point[1])
            except (TypeError, ValueError):
                continue
            if epoch >= 1 and math.isfinite(error_value) and error_value >= 0.0:
                curve_points.append([epoch, error_value])

        # Sehr alte Historieneinträge besitzen eventuell noch keine
        # gespeicherte Kurve. Aus Start und Ende entsteht dann zumindest
        # eine nachvollziehbare Ersatzdarstellung.
        if not curve_points and completed_epochs >= 1:
            if completed_epochs > 1:
                curve_points.append([1, start_error])
            curve_points.append([max(1, completed_epochs), end_error])

        scale_mode = str(history_entry.get("error_chart_scale", "linear"))
        scale_index = self.error_chart_scale.findData(scale_mode)
        if scale_index >= 0:
            self.error_chart_scale.setCurrentIndex(scale_index)
        self.error_chart.set_scale_mode(
            self.error_chart_scale.currentData()
        )
        self.error_chart.clear(self.error_limit.value())
        for index, (epoch, error_value) in enumerate(curve_points):
            self.error_chart.add_point(
                epoch,
                error_value,
                force_update=index == len(curve_points) - 1
            )

        self.history_curve_points = [list(point) for point in curve_points]
        try:
            self.current_run_id = int(history_entry.get("run_id"))
        except (TypeError, ValueError):
            self.current_run_id = None
        self.current_run_timestamp = str(history_entry.get("timestamp", ""))
        self.current_run_completed_epochs = max(0, completed_epochs)
        try:
            requested_epochs = int(
                history_entry.get("requested_epochs", completed_epochs) or 0
            )
        except (TypeError, ValueError):
            requested_epochs = completed_epochs
        self.current_run_requested_epochs = max(
            self.current_run_completed_epochs,
            requested_epochs,
        )
        self.current_run_elapsed_seconds = max(0.0, elapsed_seconds)
        self.current_run_initialized = bool(
            history_entry.get("initialized", False)
        )
        try:
            self.current_run_learning_rate = float(
                history_entry.get("learning_rate", self.learning_rate.value())
            )
        except (TypeError, ValueError):
            self.current_run_learning_rate = float(self.learning_rate.value())
        self.learning_rate.setValue(self.current_run_learning_rate)
        try:
            self.current_run_momentum = float(history_entry.get("momentum", 0.0))
        except (TypeError, ValueError):
            self.current_run_momentum = 0.0
        self.momentum.setValue(self.current_run_momentum)
        try:
            stored_shuffle_seed = history_entry.get("shuffle_seed")
            self.current_run_shuffle_seed = (
                int(stored_shuffle_seed)
                if stored_shuffle_seed is not None
                else None
            )
        except (TypeError, ValueError):
            self.current_run_shuffle_seed = None
        self.current_run_can_continue = (
            self.current_run_id is not None
            and bool(history_entry.get("continuable", True))
        )
        self.current_run_stopped = (
            self.current_run_can_continue
            and bool(history_entry.get("training_stopped", False))
        )
        initial_state = history_entry.get("initial_network_state")
        self.current_run_initial_state = (
            deepcopy(initial_state)
            if self.training_state_is_compatible(initial_state)
            else None
        )
        self.next_training_run_id = max(
            self.next_training_run_id,
            (self.current_run_id or 0) + 1,
        )
        self.error_chart_start_value = start_error
        self.error_chart_current_value = end_error
        self.result_start_mse.setText(format_number(start_error))
        self.result_mse.setText(format_number(end_error))
        self.result_epochs.setText(str(completed_epochs))
        self.result_max_error.setText(format_number(maximum_error))
        self.result_elapsed_time.setText(f"{elapsed_seconds:.1f} s")
        self.result_status.setText(str(history_entry.get("status_text", "")))
        self.maximum_error_details = None
        try:
            metrics = self.calculate_dataset_metrics(update_display=False)
            self.maximum_error_details = metrics.get("maximum_error_details")
        except (TypeError, ValueError):
            self.maximum_error_details = None
        finally:
            self.network.reset_runtime_values()
        self.result_max_error_info.setEnabled(
            self.maximum_error_details is not None
        )
        self.update_error_chart_summary()
        self.update_training_run_label()
        self.set_training_controls_enabled(True)

    def clear_training_run_display(self):
        """Entfernt nach leerer Historie alle laufbezogenen Anzeigen."""

        if self.is_training:
            return

        self.current_run_id = None
        self.current_run_timestamp = ""
        self.current_run_completed_epochs = 0
        self.current_run_requested_epochs = 0
        self.current_run_elapsed_seconds = 0.0
        self.current_run_initialized = False
        self.current_run_learning_rate = None
        self.current_run_momentum = None
        self.current_run_shuffle_seed = None
        self.network.reset_momentum_state()
        self.current_run_can_continue = False
        self.current_run_stopped = False
        self.current_run_initial_state = None
        self.next_training_run_id = 1

        self.error_chart_start_value = None
        self.error_chart_current_value = None
        self.history_curve_points = []
        self.error_chart.clear(self.error_limit.value())
        self.reset_plateau_detection()

        self.maximum_error_details = None
        self.result_max_error_info.setEnabled(False)
        self.result_start_mse.setText("–")
        self.result_mse.setText("–")
        self.result_epochs.setText("–")
        self.result_max_error.setText("–")
        self.result_elapsed_time.setText("0.0 s")
        self.result_status.setText(
            self.language.text("training.status.not_started")
        )

        self.update_error_chart_summary()
        self.update_training_run_label()
        self.set_training_controls_enabled(True)

    def update_error_chart_scale(self, index=None):
        """Übernimmt die gewählte lineare oder logarithmische Y-Achse."""

        self.error_chart.set_scale_mode(
            self.error_chart_scale.currentData()
        )

    @staticmethod
    def format_error_summary_value(value):
        """Formatiert einen Fehlerwert für die Zusammenfassung."""

        if value is None:
            return "–"

        return format_number(value, significant_digits=4)

    def update_error_chart_summary(self):
        """Zeigt Startfehler und aktuellen Fehler an."""

        if (
            self.error_chart_start_value is None
            or self.error_chart_current_value is None
        ):
            self.error_chart_start.setText(
                self.language.text("training.chart.start_error", value="–")
            )
            self.error_chart_current.setText(
                self.language.text("training.chart.current_error", value="–")
            )
            self.result_start_mse.setText("–")
            self.update_compact_status()
            return

        start_error = self.error_chart_start_value
        current_error = self.error_chart_current_value
        self.result_start_mse.setText(format_number(start_error))

        self.error_chart_start.setText(
            self.language.text(
                "training.chart.start_error",
                value=self.format_error_summary_value(start_error)
            )
        )
        self.error_chart_current.setText(
            self.language.text(
                "training.chart.current_error",
                value=self.format_error_summary_value(current_error)
            )
        )

        self.update_compact_status()

    def add_history_curve_point(self, epoch, error_value, force=False):
        """Sammelt Kurvenpunkte in einer festen, stufenweisen Auflösung."""

        epoch = int(epoch)
        if epoch <= 500:
            recording_interval = 1
        else:
            # Pro zusätzlicher Zehnerpotenz bleiben ungefähr 900 Punkte
            # erhalten: bis 10.000 jede 10., bis 100.000 jede 100. Epoche
            # usw. Es findet keine spätere, sprunghafte Halbierung statt.
            recording_interval = 10 ** max(1, len(str(epoch - 1)) - 3)

        if not force and epoch % recording_interval != 0:
            return False

        point = [
            epoch,
            float(error_value)
        ]

        if (
            self.history_curve_points
            and self.history_curve_points[-1][0] == point[0]
        ):
            self.history_curve_points[-1] = point

        else:
            self.history_curve_points.append(
                point
            )

        return True

    @staticmethod
    def compress_history_curve(points, maximum_points=10000):
        """Verdichtet eine Kurve stabil anhand ihrer Epochennummern.

        Die logarithmische Grundverteilung bewahrt den meist besonders
        aussagekräftigen Trainingsbeginn. Zusätzliche Punkte teilen danach
        die größten noch vorhandenen Epochenlücken. Die Zielpositionen hängen
        ausschließlich vom Epochenbereich ab und nicht von der Anzahl der
        bereits gespeicherten Punkte. Dadurch wird eine geladene, fortgesetzte
        und erneut gespeicherte Kurve nicht bei jedem Durchlauf weiter an
        anderen Stellen ausgedünnt.
        """

        if len(points) <= maximum_points:
            return [
                list(point)
                for point in points
            ]

        maximum_points = max(2, int(maximum_points))
        source_points = sorted(
            (
                [int(point[0]), float(point[1])]
                for point in points
            ),
            key=lambda point: point[0],
        )

        # Doppelte Epochen können beim Zusammenführen eines fortgesetzten
        # Abschnitts entstehen. Der jeweils jüngste Messwert ist maßgeblich.
        unique_points = []
        for point in source_points:
            if unique_points and unique_points[-1][0] == point[0]:
                unique_points[-1] = point
            else:
                unique_points.append(point)

        if len(unique_points) <= maximum_points:
            return [list(point) for point in unique_points]

        first_epoch = unique_points[0][0]
        last_epoch = unique_points[-1][0]
        if first_epoch == last_epoch:
            return [list(unique_points[-1])]

        # Neue Läufe bewahren die ersten 500 Epochen lückenlos. Bei älteren,
        # bereits verdichteten Läufen bleiben zumindest alle dort noch
        # vorhandenen frühen Messwerte unverändert erhalten.
        early_epoch_limit = first_epoch + min(499, maximum_points - 2)
        early_points = [
            list(point)
            for point in unique_points
            if point[0] <= early_epoch_limit
        ][:maximum_points - 2]
        remaining_points = maximum_points - len(early_points)
        tail_source = [
            point
            for point in unique_points
            if not early_points or point[0] > early_points[-1][0]
        ]
        if not tail_source:
            return early_points
        if len(tail_source) <= remaining_points:
            return early_points + [list(point) for point in tail_source]
        if remaining_points <= 1:
            return early_points + [list(tail_source[-1])]

        first_epoch = tail_source[0][0]
        last_epoch = tail_source[-1][0]

        target_epochs = {first_epoch, last_epoch}
        log_first = math.log(max(1, first_epoch))
        log_last = math.log(max(1, last_epoch))

        # Logarithmische Positionen erhalten viele Messpunkte in den frühen
        # Epochen, in denen Fehlerkurven typischerweise am stärksten fallen.
        for index in range(remaining_points):
            fraction = index / (remaining_points - 1)
            epoch = round(
                math.exp(log_first + (log_last - log_first) * fraction)
            )
            target_epochs.add(
                min(last_epoch, max(first_epoch, epoch))
            )

        # Rundungen erzeugen im frühen Bereich gleiche Epochennummern. Die
        # freien Plätze werden in den größten Epochenlücken ergänzt, damit
        # weiterhin bis zu 10.000 aussagekräftige Punkte genutzt werden.
        maximum_available = last_epoch - first_epoch + 1
        target_count = min(remaining_points, maximum_available)
        while len(target_epochs) < target_count:
            ordered_epochs = sorted(target_epochs)
            largest_gap = max(
                (
                    (right - left, left, right)
                    for left, right in zip(
                        ordered_epochs,
                        ordered_epochs[1:],
                    )
                ),
                default=(0, first_epoch, last_epoch),
            )
            gap, left, right = largest_gap
            if gap <= 1:
                break
            target_epochs.add((left + right) // 2)

        # Für neu berechnete Zielpositionen wird die vorhandene Kurvenlinie
        # linear abgetastet. Bei erneutem Speichern mit demselben Endpunkt
        # entstehen dadurch exakt dieselben Punkte (idempotente Verdichtung).
        compressed = []
        source_index = 0
        for epoch in sorted(target_epochs):
            while (
                source_index + 1 < len(tail_source)
                and tail_source[source_index + 1][0] < epoch
            ):
                source_index += 1

            left_epoch, left_error = tail_source[source_index]
            if left_epoch == epoch or source_index + 1 >= len(tail_source):
                error_value = left_error
            else:
                right_epoch, right_error = tail_source[source_index + 1]
                if right_epoch == epoch:
                    error_value = right_error
                else:
                    fraction = (
                        (epoch - left_epoch)
                        / (right_epoch - left_epoch)
                    )
                    error_value = (
                        left_error
                        + (right_error - left_error) * fraction
                    )
            compressed.append([epoch, error_value])

        return early_points + compressed

    def normalize_error_limit_input(self):
        """Beendet eine manuelle Nulleingabe mit einem gültigen Minimum."""

        if self.error_limit.value() <= 0.0:
            self.error_limit.setValue(
                0.0000000001
            )

    def update_elapsed_time_display(
        self,
        force=False
    ):
        """
        Aktualisiert die seit Trainingsbeginn vergangene Zeit.

        Die Anzeige wird auf eine Nachkommastelle gerundet und
        höchstens etwa zehnmal pro Sekunde neu geschrieben.
        """

        if self.training_start_time is None:
            return

        current_time = time.monotonic()

        if (
            not force
            and (
                current_time
                - self._last_elapsed_display_update
            )
            < 0.1
        ):
            return

        elapsed_seconds = max(
            0.0,
            self.training_elapsed_base
            + current_time - self.training_start_time
        )

        self.result_elapsed_time.setText(
            f"{elapsed_seconds:.1f} s"
        )

        self._last_elapsed_display_update = current_time

    def process_training_events(
        self,
        force=False
    ):
        """
        Verarbeitet GUI-Ereignisse in begrenzten Abständen.

        Dadurch bleibt insbesondere die Stop-Schaltfläche
        bedienbar. Bei ausgeschaltetem Monitoring werden
        Ereignisse seltener verarbeitet, damit das Training
        möglichst wenig ausgebremst wird.
        """

        current_time = time.monotonic()

        minimum_interval = (
            1.0
            if self.fast_mode.isChecked()
            else (
                0.03
                if self.monitor_training_data.isChecked()
                else 0.10
            )
        )

        if (
            not force
            and (
                current_time
                - self._last_event_processing_time
            )
            < minimum_interval
        ):
            return

        self._last_event_processing_time = current_time

        self.update_elapsed_time_display(
            force=force
        )

        QApplication.processEvents()

    def request_stop(self):
        """
        Fordert das kontrollierte Beenden des laufenden
        Trainingsabschnitts nach dem aktuellen Datensatz an.
        """

        if not self.is_training:
            return

        self.stop_requested = True

        self.result_status.setText(
            self.language.text("training.status.stop_requested")
        )

        self.stop_button.setEnabled(
            False
        )

        self.process_training_events(
            force=True
        )

    def debug_training(self):
        """
        Öffnet den Trainings-Debugger für einzelne Datensätze.
        """

        if self.is_training:
            return

        dialog = TrainingDebugDialog(
            self.network,
            self.records,
            self.input_columns,
            self.output_columns,
            self,
            language_manager=self.language
        )

        dialog.exec()

    def test_network(self):
        """
        Öffnet die vollständige Test- und Analyseansicht mit dem aktuellen
        Netzwerk, ohne Gewichte oder Bias-Werte zu verändern.
        """

        if self.is_training:
            return

        if (
            self.network_test_dialog is not None
            and self.network_test_dialog.isVisible()
        ):
            self.network_test_dialog.raise_()
            self.network_test_dialog.activateWindow()
            return

        try:
            dialog = ResultAnalysisDialog(
                self.network,
                [{
                    "kind": "training",
                    "label": self.language.text("test.data.training"),
                    "records": self.records,
                    "inputs": self.input_columns,
                    "outputs": self.output_columns,
                    "file_path": self.training_file_path,
                }],
                parent=self,
                language_manager=self.language,
                initial_tab=0,
                initial_source_kind="training"
            )

        except (ArithmeticError, TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("training.message.title"),
                str(error)
            )
            return

        self.network_test_dialog = dialog
        self.test_network_button.setEnabled(False)
        dialog.finished.connect(
            lambda _result, current_dialog=dialog:
            self.network_test_finished(current_dialog)
        )

        # open() hält das Trainingsfenster reaktionsfähig.
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

    def open_experiment(self):
        """Öffnet nach einem Trainingslauf das zentrale Experimentierfenster."""

        if self.is_training or self.current_run_id is None:
            return

        parent = self.parent()

        if parent is not None and hasattr(parent, "forward_pass"):
            parent.forward_pass()

    def network_test_finished(self, dialog):
        """Gibt die Schaltfläche nach dem Netztest wieder frei."""

        if self.network_test_dialog is not dialog:
            return

        self.network_test_dialog = None
        dialog.deleteLater()

        if not self.is_training:
            self.test_network_button.setEnabled(True)

    def prepare_training_document(self):
        """
        Prüft Datensätze und Spaltenzuordnungen und
        bereitet die Zuordnungslisten für das Training vor.
        """

        if not isinstance(
            self.training_document,
            dict
        ):
            raise ValueError(
                self.language.text("training.validation.no_valid_data")
            )

        columns = self.training_document.get(
            "columns"
        )

        records = self.training_document.get(
            "records"
        )

        if not isinstance(columns, list) or not columns:
            raise ValueError(
                self.language.text("training.validation.no_columns")
            )

        if not isinstance(records, list) or not records:
            raise ValueError(
                self.language.text("training.validation.no_records")
            )

        input_mappings = []
        output_mappings = []
        used_neuron_ids = set()

        for column_index, column in enumerate(
            columns
        ):
            if not isinstance(column, dict):
                raise ValueError(
                    self.language.text(
                        "training.validation.invalid_column",
                        column=column_index + 1
                    )
                )

            role = column.get(
                "role"
            )

            neuron_id = column.get(
                "mapped_neuron_id"
            )

            column_name = str(
                column.get(
                    "name",
                    self.language.text(
                        "training.validation.column_fallback",
                        column=column_index + 1
                    )
                )
            )

            if role not in (
                "input",
                "output"
            ):
                raise ValueError(
                    self.language.text(
                        "training.validation.invalid_role",
                        column=column_name
                    )
                )

            if neuron_id is None:
                raise ValueError(
                    self.language.text(
                        "training.validation.unassigned",
                        column=column_name
                    )
                )

            neuron = self.network.get_neuron(
                neuron_id
            )

            if neuron is None:
                raise ValueError(
                    self.language.text(
                        "training.validation.neuron_missing",
                        column=column_name
                    )
                )

            expected_type = (
                NeuronType.INPUT
                if role == "input"
                else NeuronType.OUTPUT
            )

            if neuron.neuron_type != expected_type:
                raise ValueError(
                    self.language.text(
                        "training.validation.wrong_neuron_type",
                        column=column_name
                    )
                )

            if neuron.id in used_neuron_ids:
                raise ValueError(
                    self.language.text(
                        "training.validation.duplicate_neuron",
                        neuron=neuron.name
                    )
                )

            used_neuron_ids.add(
                neuron.id
            )

            mapping = {
                "column_index": column_index,
                "column_name": column_name,
                "unit": str(column.get("unit", "")).strip(),
                "data_type": column.get("data_type", "analog"),
                "neuron": neuron,
                "calibration": TrainingDataIO.normalize_calibration(
                    column.get("calibration")
                )
            }

            if role == "input":
                input_mappings.append(
                    mapping
                )
            else:
                output_mappings.append(
                    mapping
                )

        network_input_ids = {
            neuron.id
            for neuron in self.network.get_input_neurons()
        }

        mapped_input_ids = {
            mapping["neuron"].id
            for mapping in input_mappings
        }

        network_output_ids = {
            neuron.id
            for neuron in self.network.get_output_neurons()
        }

        mapped_output_ids = {
            mapping["neuron"].id
            for mapping in output_mappings
        }

        if mapped_input_ids != network_input_ids:
            raise ValueError(
                self.language.text("training.validation.inputs_incomplete")
            )

        if mapped_output_ids != network_output_ids:
            raise ValueError(
                self.language.text("training.validation.outputs_incomplete")
            )

        for record_index, record in enumerate(
            records,
            start=1
        ):
            if not isinstance(record, list):
                raise ValueError(
                    self.language.text(
                        "training.validation.invalid_record",
                        record=record_index
                    )
                )

            if len(record) != len(columns):
                raise ValueError(
                    self.language.text(
                        "training.validation.record_length",
                        record=record_index
                    )
                )

            try:
                records[record_index - 1] = [
                    float(value)
                    for value in record
                ]
            except (
                TypeError,
                ValueError
            ) as error:
                raise ValueError(
                    self.language.text(
                        "training.validation.record_number",
                        record=record_index
                    )
                ) from error

        self.input_columns = input_mappings
        self.output_columns = output_mappings
        self.records = records

    def create_scaling_warning_lines(self):
        """Beschreibt unskalierte Spalten mit Werten außerhalb −1 bis +1."""

        warnings = []

        for mapping in self.input_columns + self.output_columns:
            calibration = TrainingDataIO.normalize_calibration(
                mapping.get("calibration")
            )

            if calibration["mode"] != "none":
                continue

            column_index = mapping["column_index"]
            values = [
                record[column_index]
                for record in self.records
                if column_index < len(record)
            ]

            if not values:
                continue

            minimum = min(values)
            maximum = max(values)

            if minimum >= -1.0 and maximum <= 1.0:
                continue

            warnings.append(
                (
                    f"{mapping['column_name']} „{mapping['neuron'].name}“: "
                    f"{minimum:g} … {maximum:g}"
                )
            )

        return warnings

    def create_binary_imbalance_warning_lines(self):
        """Meldet stark ungleich verteilte binäre Sollwerte."""

        warnings = []
        for mapping in self.output_columns:
            if mapping.get("data_type") != "binary":
                continue

            column_index = mapping["column_index"]
            values = [
                record[column_index]
                for record in self.records
                if column_index < len(record)
            ]
            if not values:
                continue

            off_count = sum(1 for value in values if float(value) < 0.5)
            on_count = len(values) - off_count
            minority_share = min(off_count, on_count) / len(values)
            if minority_share >= 0.15:
                continue

            warnings.append(
                self.language.text(
                    "training.imbalance_warning.line",
                    output=mapping["neuron"].name,
                    off=off_count,
                    on=on_count
                )
            )

        return warnings

    def update_imbalance_warning_expansion(self, expanded):
        """Klappt die ausführliche Liste unausgeglichener Outputs ein oder aus."""

        if not hasattr(self, "imbalance_warning_details"):
            return
        self.imbalance_warning_details.setVisible(bool(expanded))
        arrow = "▾" if expanded else "›"
        self.imbalance_warning_toggle.setText(
            f"{arrow} "
            + self.language.text(
                "training.imbalance_warning.summary",
                count=self.imbalance_warning_count
            )
        )

    def reset_plateau_detection(self):
        """Startet die rein beobachtende Plateauprüfung neu."""

        self.plateau_history = []
        self.plateau_warning_detected = False
        self.plateau_warning_dismissed = False
        self.plateau_warning_container.setVisible(False)

    def dismiss_plateau_warning(self):
        """Schließt den Plateauhinweis für den aktuellen Trainingslauf."""

        self.plateau_warning_dismissed = True
        self.plateau_warning_container.setVisible(False)

    def update_plateau_detection(
        self,
        epoch,
        mean_squared_error,
        maximum_absolute_error
    ):
        """Zeigt einen Hinweis, wenn beide Fehlerwerte lange stagnieren."""

        self.plateau_history.append(
            (
                int(epoch),
                float(mean_squared_error),
                float(maximum_absolute_error)
            )
        )
        self.plateau_history = self.plateau_history[-300:]

        if self.plateau_warning_dismissed:
            self.plateau_warning_container.setVisible(False)
            return

        if self.plateau_warning_detected:
            self.plateau_warning_container.setVisible(True)
            return

        window = 250
        if len(self.plateau_history) < window:
            self.plateau_warning_container.setVisible(False)
            return

        _, old_mean, old_maximum = self.plateau_history[-window]
        _, current_mean, current_maximum = self.plateau_history[-1]

        mean_improvement = (old_mean - current_mean) / max(abs(old_mean), 1e-12)
        maximum_improvement = (
            (old_maximum - current_maximum)
            / max(abs(old_maximum), 1e-12)
        )
        meaningful_error_remains = (
            current_mean > self.error_limit.value()
            and current_maximum >= 0.25
        )
        plateau_detected = (
            meaningful_error_remains
            and mean_improvement <= 0.02
            and maximum_improvement <= 0.02
        )

        if plateau_detected:
            self.plateau_warning_detected = True
            self.plateau_warning_container.setVisible(True)

    def reject(self):
        """Verhindert ein unbeabsichtigtes Schließen während eines Laufes."""

        if self.is_training:
            self.result_status.setText(
                self.language.text("training.status.close_blocked")
            )
            self.raise_()
            return

        super().reject()

    def create_mapping_text(self):
        """
        Erstellt eine kompakte, sichtbare Übersicht
        der verwendeten Spaltenzuordnungen.
        """

        lines = []

        for mapping in self.input_columns:
            lines.append(
                f"{mapping['column_name']} → "
                f"{mapping['neuron'].name}.X"
            )

        for mapping in self.output_columns:
            lines.append(
                f"{mapping['column_name']} → "
                + self.language.text(
                    "training.data.target_of",
                    neuron=mapping['neuron'].name
                )
            )

        return "\n".join(
            lines
        )

    def set_training_controls_enabled(
        self,
        enabled
    ):
        """
        Sperrt die Bedienelemente während eines Trainingslaufes.
        """

        self.learning_rate.setEnabled(
            enabled
        )
        self.momentum.setEnabled(enabled)

        self.error_limit.setEnabled(
            enabled
        )

        self.maximum_epochs.setEnabled(
            enabled
        )

        # Die sichtbare Netzwerkaktualisierung darf während des Laufes
        # jederzeit ein- oder ausgeschaltet werden.
        self.monitor_training_data.setEnabled(
            True
        )

        # Die Sichtbarkeit der Kurve darf auch während eines laufenden
        # Trainings geändert werden. Die Messwerte werden unabhängig vom
        # Haken im Hintergrund weiter gesammelt.
        self.show_error_chart.setEnabled(
            True
        )

        self.error_chart_scale.setEnabled(
            enabled
        )

        self.initialize_network.setEnabled(
            enabled
        )

        self.initialization_group.setEnabled(
            enabled
            and self.initialize_network.isChecked()
        )

        for control in self.new_run_controls:
            control.setEnabled(
                enabled
            )
        self.epoch_count.setEnabled(
            enabled and self.training_target_mode == "epochs"
        )
        self.epoch_count_suffix.setEnabled(
            enabled and self.training_target_mode == "epochs"
        )
        self.test_network_button.setEnabled(
            enabled
        )
        self.experiment_button.setEnabled(
            enabled and self.current_run_id is not None
        )

        self.debug_training_button.setEnabled(
            enabled
        )

        self.load_history_button.setEnabled(enabled)

        self.stop_button.setEnabled(
            not enabled
        )

        self.stop_button.setText(
            self.language.text("training.button.stop")
        )

        self.continue_button.setEnabled(
            enabled and self.current_run_can_continue
        )
        self.repeat_initialization_button.setEnabled(
            enabled
            and self.current_run_id is not None
            and self.training_state_is_compatible(
                self.current_run_initial_state
            )
        )
        self.suggest_parameters_button.setEnabled(enabled)
        self.sync_minimal_training_buttons()
        if self.close_button is not None:
            self.close_button.setEnabled(
                enabled
            )

    def apply_record(self, record, update_display=True):
        """
        Legt die Eingangswerte eines Datensatzes an den
        zugeordneten Input-Neuronen an und erzeugt das
        Sollwert-Dictionary für die Output-Neuronen.
        """

        for mapping in self.input_columns:
            raw_value = record[mapping["column_index"]]
            mapping["neuron"].input_value = TrainingDataIO.scale_value(
                raw_value,
                mapping["calibration"],
                self.language.text
            )

            if update_display:
                mapping["neuron"].set_external_input_value(
                    raw_value,
                    mapping["calibration"]["mode"] != "none",
                    unit=mapping.get("unit", ""),
                    is_binary=mapping.get("data_type") == "binary"
                )
                mapping["neuron"].update()

        target_values = {}

        for mapping in self.output_columns:
            raw_target = record[mapping["column_index"]]
            target_values[
                mapping["neuron"].id
            ] = TrainingDataIO.scale_value(
                raw_target,
                mapping["calibration"],
                self.language.text
            )
            if update_display:
                mapping["neuron"].set_external_output_values(
                    target_value=raw_target,
                    is_raw=mapping["calibration"]["mode"] != "none",
                    unit=mapping.get("unit", ""),
                    is_binary=mapping.get("data_type") == "binary"
                )

        return target_values

    def update_external_output_values(self, record):
        for mapping in self.output_columns:
            neuron = mapping["neuron"]
            raw_output = TrainingDataIO.unscale_value(
                neuron.output_value,
                mapping["calibration"],
                self.language.text
            )
            neuron.set_external_output_values(
                actual_value=raw_output,
                target_value=record[mapping["column_index"]],
                is_raw=mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )

    def train_epoch(
        self,
        epoch_number,
        total_epochs
    ):
        """
        Verarbeitet alle Datensätze genau einmal.

        Die Reihenfolge wird in jeder Epoche neu gemischt,
        damit eine feste Sortierung der Trainingsdaten das
        Online-Training nicht systematisch beeinflusst.

        Der zurückgegebene Epochenfehler wird anschließend
        mit den nach der Epoche gültigen Gewichten separat
        über alle Datensätze berechnet.
        """

        fast = self.fast_mode.isChecked()
        record_count = len(
            self.records
        )

        shuffled_records = list(
            self.records
        )

        shuffle_seed = int(self.current_run_shuffle_seed or 0)
        epoch_seed = (
            shuffle_seed
            + int(epoch_number) * 0x9E3779B97F4A7C15
        ) & ((1 << 64) - 1)
        random.Random(epoch_seed).shuffle(shuffled_records)

        for record_index, record in enumerate(
            shuffled_records,
            start=1
        ):
            if self.monitor_training_data.isChecked() and not fast:
                self.result_status.setText(
                    self.language.text(
                        "training.status.progress",
                        epoch=epoch_number,
                        total_epochs=total_epochs,
                        record=record_index,
                        total_records=record_count
                    )
                )

            self.process_training_events()

            if not fast:
                self.network.reset_runtime_values()

            target_values = self.apply_record(
                record,
                update_display=not fast
            )

            self.network.train_step(
                target_values
            )
            self.processed_training_records += 1
            if not fast:
                self.update_external_output_values(record)

            if self.stop_requested:
                break

        return self.calculate_dataset_metrics(update_display=not fast)

    def calculate_dataset_metrics(self, update_display=True):
        """
        Berechnet den mittleren quadratischen Fehler und
        den maximalen absoluten Einzelfehler über alle
        Datensätze, ohne Gewichte oder Bias-Werte zu verändern.
        """

        squared_error_sum = 0.0
        output_value_count = 0
        maximum_absolute_error = 0.0
        maximum_error_details = None

        for record_index, record in enumerate(self.records, start=1):
            if update_display:
                self.network.reset_runtime_values()

            target_values = self.apply_record(record, update_display)

            self.network.forward_pass()
            if update_display:
                self.update_external_output_values(record)

            for mapping in self.output_columns:
                neuron = mapping["neuron"]
                error_value = (
                    target_values[neuron.id]
                    - neuron.output_value
                )

                squared_error_sum += (
                    error_value
                    * error_value
                )

                absolute_error = abs(error_value)

                if (
                    maximum_error_details is None
                    or absolute_error > maximum_absolute_error
                ):
                    raw_target = record[mapping["column_index"]]
                    raw_actual = TrainingDataIO.unscale_value(
                        neuron.output_value,
                        mapping["calibration"],
                        self.language.text
                    )
                    maximum_absolute_error = absolute_error
                    maximum_error_details = {
                        "record": record_index,
                        "output": mapping["column_name"],
                        "unit": mapping.get("unit", ""),
                        "data_type": mapping.get("data_type", "analog"),
                        "raw_target": raw_target,
                        "raw_actual": raw_actual,
                        "raw_error": abs(raw_target - raw_actual),
                        "internal_error": absolute_error,
                    }

                output_value_count += 1

        if output_value_count == 0:
            raise ValueError(
                self.language.text("training.validation.no_targets")
            )

        return {
            "mean_squared_error": (
                squared_error_sum
                / output_value_count
            ),
            "maximum_absolute_error": maximum_absolute_error,
            "maximum_error_details": maximum_error_details
        }

    def show_maximum_error_details(self):
        """Zeigt den Datensatz hinter dem maximalen internen Einzelfehler."""

        details = self.maximum_error_details
        if not details:
            return

        unit = str(details.get("unit") or "").strip()
        suffix = f" {unit}" if unit else ""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.language.text("training.maximum_error.title"))
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        explanation = QLabel(
            self.language.text("training.maximum_error.explanation")
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            "QLabel { background: #fff8d8; border: 1px solid #d6c36a; "
            "border-radius: 4px; padding: 9px; }"
        )
        layout.addWidget(explanation)

        group = QGroupBox(
            self.language.text("training.maximum_error.affected_group")
        )
        form = QFormLayout(group)
        form.addRow(
            self.language.text("training.maximum_error.record_label"),
            QLabel(str(details["record"]))
        )
        form.addRow(
            self.language.text("training.maximum_error.output_label"),
            QLabel(str(details["output"]))
        )
        form.addRow(
            self.language.text("training.maximum_error.target_label"),
            QLabel(f"{format_number(details['raw_target'])}{suffix}")
        )
        form.addRow(
            self.language.text("training.maximum_error.actual_label"),
            QLabel(f"{format_number(details['raw_actual'])}{suffix}")
        )
        deviation = QLabel(f"{format_number(details['raw_error'])}{suffix}")
        deviation.setStyleSheet("font-weight: bold; color: #b85c00;")
        form.addRow(
            self.language.text("training.maximum_error.deviation_label"),
            deviation
        )
        if details.get("data_type") == "binary":
            decision = self.language.text(
                "training.maximum_error.binary_decision",
                target=self.language.text(
                    "binary.on" if details["raw_target"] > 0.5 else "binary.off"
                ),
                actual=self.language.text(
                    "binary.on" if details["raw_actual"] > 0.5 else "binary.off"
                )
            )
            form.addRow(
                self.language.text("training.maximum_error.decision_label"),
                QLabel(decision)
            )
        layout.addWidget(group)

        technical_note = QLabel(
            self.language.text(
                "training.maximum_error.technical_note",
                value=format_number(details["internal_error"])
            )
        )
        technical_note.setWordWrap(True)
        technical_note.setStyleSheet("color: #666666;")
        layout.addWidget(technical_note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.language.text("common.close")
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def get_target_range_warnings(self):
        """
        Prüft, ob Sollwerte außerhalb des typischen
        Wertebereiches der jeweiligen Aktivierungsfunktion liegen.

        Linear besitzt keinen begrenzten Wertebereich.
        ReLU erwartet nichtnegative Sollwerte.
        Sigmoid liefert Werte zwischen 0 und 1.
        Tanh liefert Werte zwischen -1 und 1.
        """

        warnings = []

        for mapping in self.output_columns:
            neuron = mapping["neuron"]
            column_index = mapping["column_index"]
            values = [
                TrainingDataIO.scale_value(
                    record[column_index],
                    mapping["calibration"],
                    self.language.text
                )
                for record in self.records
            ]

            minimum_value = min(
                values
            )
            maximum_value = max(
                values
            )

            activation = neuron.activation_function
            invalid = False
            expected_range = ""

            if activation == "Sigmoid":
                invalid = (
                    minimum_value < 0.0
                    or maximum_value > 1.0
                )
                expected_range = self.language.text("training.range.zero_to_one")

            elif activation == "Tanh":
                invalid = (
                    minimum_value < -1.0
                    or maximum_value > 1.0
                )
                expected_range = self.language.text("training.range.minus_one_to_one")

            elif activation == "ReLU":
                invalid = minimum_value < 0.0
                expected_range = self.language.text("training.range.nonnegative")

            if invalid:
                warnings.append(
                    self.language.text(
                        "training.target_warning.line",
                        column=mapping['column_name'],
                        neuron=neuron.name,
                        minimum=format_number(minimum_value),
                        maximum=format_number(maximum_value),
                        activation=activation,
                        expected=expected_range
                    )
                )

        return warnings

    def confirm_target_ranges(self):
        """
        Warnt vor unpassenden Sollwertbereichen und
        lässt den Benutzer über den Trainingsstart entscheiden.
        """

        warnings = self.get_target_range_warnings()

        if not warnings:
            return True

        warning_text = "\n".join(
            warnings
        )

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle(
            self.language.text("training.target_warning.title")
        )
        message_box.setText(
            self.language.text(
                "training.target_warning.message",
                warnings=warning_text
            )
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.No)
        message_box.button(QMessageBox.StandardButton.Yes).setText(
            self.language.text("common.yes")
        )
        message_box.button(QMessageBox.StandardButton.No).setText(
            self.language.text("common.no")
        )
        result = message_box.exec()

        return (
            result
            == QMessageBox.StandardButton.Yes
        )

    def initialize_network_parameters(self):
        """
        Initialisiert das Netzwerk für einen vollständig
        neuen Trainingslauf.

        Gewichte:
            - Xavier/Glorot-Zufallswerte (empfohlen)
            - oder 0,0 ausschließlich für Testzwecke

        Bias:
            - 0,0 (empfohlen)
            - oder Xavier/Glorot-Zufallswerte

        Die Topologie bleibt unverändert.
        """

        weight_method = str(
            self.weight_initialization_combo.currentData() or "auto"
        )

        use_random_bias = (
            self.bias_initialization_combo.currentData()
            == "xavier"
        )

        for connection in self.network.get_connections():
            if weight_method != "zero":
                source_neuron = connection.source_neuron
                target_neuron = connection.target_neuron

                fan_in = max(
                    1,
                    len(
                        target_neuron.incoming_connections
                    )
                )

                fan_out = max(
                    1,
                    len(
                        source_neuron.outgoing_connections
                    )
                )

                use_he = (
                    weight_method == "he"
                    or (
                        weight_method == "auto"
                        and str(target_neuron.activation_function).casefold()
                        == "relu"
                    )
                )
                if use_he:
                    connection.weight = random.gauss(
                        0.0, math.sqrt(2.0 / fan_in)
                    )
                else:
                    limit = math.sqrt(6.0 / (fan_in + fan_out))
                    connection.weight = random.uniform(-limit, limit)

            else:
                connection.weight = 0.0

            # Aktualisiert die sichtbare Gewichtsanzeige
            # an der Verbindung unmittelbar.
            connection.update()

        for neuron in self.network.get_neurons():
            if neuron.neuron_type == NeuronType.INPUT:
                neuron.update()
                continue

            if use_random_bias:
                fan_in = max(
                    1,
                    len(
                        neuron.incoming_connections
                    )
                )

                fan_out = max(
                    1,
                    len(
                        neuron.outgoing_connections
                    )
                )

                limit = math.sqrt(
                    6.0
                    / (
                        fan_in
                        + fan_out
                    )
                )

                neuron.bias = random.uniform(
                    -limit,
                    limit
                )

            else:
                neuron.bias = 0.0

            neuron.update()

        self.network.reset_runtime_values()

        # Nur bei eingeschaltetem Monitoring wird die
        # Netzwerkdarstellung bereits während der
        # Initialisierung sichtbar aktualisiert.
        if self.monitor_training_data.isChecked():
            self.training_progress.emit(
                {
                    "initialization_completed": True,
                    "weight_initialization": (
                        weight_method
                    ),
                    "bias_initialization": (
                        "xavier"
                        if use_random_bias
                        else "zero"
                    )
                }
            )

        self.process_training_events(
            force=True
        )

    def capture_training_state(self):
        """Erfasst Gewichte und Biaswerte vor dem ersten Lernschritt."""

        return {
            "neurons": [
                {"id": int(neuron.id), "bias": float(neuron.bias)}
                for neuron in sorted(
                    self.network.get_neurons(), key=lambda item: item.id
                )
            ],
            "connections": [
                {
                    "id": int(connection.id),
                    "source": int(connection.source_neuron.id),
                    "target": int(connection.target_neuron.id),
                    "weight": float(connection.weight),
                }
                for connection in sorted(
                    self.network.get_connections(), key=lambda item: item.id
                )
            ],
        }

    def training_state_is_compatible(self, state):
        """Prüft, ob ein gespeicherter Ausgangszustand zum Netz gehört."""

        if not isinstance(state, dict):
            return False
        neurons = state.get("neurons")
        connections = state.get("connections")
        if not isinstance(neurons, list) or not isinstance(connections, list):
            return False
        try:
            saved_neurons = {int(item["id"]) for item in neurons}
            saved_connections = {int(item["id"]) for item in connections}
        except (KeyError, TypeError, ValueError):
            return False
        return (
            saved_neurons
            == {int(neuron.id) for neuron in self.network.get_neurons()}
            and saved_connections
            == {int(connection.id) for connection in self.network.get_connections()}
        )

    def restore_training_state(self, state):
        """Stellt einen kompatiblen Ausgangszustand ohne Momentum wieder her."""

        if not self.training_state_is_compatible(state):
            return False
        neurons = {
            int(neuron.id): neuron for neuron in self.network.get_neurons()
        }
        connections = {
            int(connection.id): connection
            for connection in self.network.get_connections()
        }
        try:
            for item in state["neurons"]:
                neurons[int(item["id"])].bias = float(item["bias"])
            for item in state["connections"]:
                connections[int(item["id"])].weight = float(item["weight"])
        except (KeyError, TypeError, ValueError):
            return False
        self.network.reset_momentum_state()
        self.network.reset_runtime_values()
        for connection in connections.values():
            connection.update()
        for neuron in neurons.values():
            neuron.update()
        return True

    def execute_fixed_epochs(
        self,
        epoch_count
    ):
        """
        Führt eine fest vorgegebene Anzahl Epochen aus.
        """

        self.execute_training(
            maximum_epochs=epoch_count,
            stop_at_error_limit=False
        )

    def execute_until_error_limit(self):
        """
        Trainiert bis zur Fehlergrenze oder bis zur
        maximalen Epochenzahl.
        """

        self.execute_training(
            maximum_epochs=self.maximum_epochs.value(),
            stop_at_error_limit=True
        )

    def execute_training(
        self,
        maximum_epochs,
        stop_at_error_limit,
        continue_existing=False,
        initial_state=None,
        shuffle_seed=None,
    ):
        """
        Führt den vollständigen Trainingslauf aus.
        """

        if self.is_training:
            return

        if continue_existing and not self.current_run_can_continue:
            return

        if not self.confirm_target_ranges():
            self.result_status.setText(
                self.language.text("training.status.not_started")
            )
            return

        try:
            self.network.set_learning_rate(
                self.learning_rate.value()
            )
            self.network.set_momentum(self.momentum.value())

        except (
            TypeError,
            ValueError
        ) as error:
            QMessageBox.warning(
                self,
                self.language.text("training.message.title"),
                str(
                    error
                )
            )
            return

        maximum_epochs = max(1, int(maximum_epochs))
        if not continue_existing:
            self.begin_new_training_run()
            self.network.reset_momentum_state()
            self.current_run_shuffle_seed = (
                int(shuffle_seed)
                if shuffle_seed is not None
                else random.SystemRandom().randrange(1, 1 << 63)
            )
        elif self.current_run_shuffle_seed is None:
            self.current_run_shuffle_seed = random.SystemRandom().randrange(
                1, 1 << 63
            )

        base_epochs = (
            self.current_run_completed_epochs
            if continue_existing else 0
        )
        self.training_elapsed_base = (
            self.current_run_elapsed_seconds
            if continue_existing else 0.0
        )
        if continue_existing:
            self.current_run_requested_epochs = max(
                self.current_run_requested_epochs,
                base_epochs + maximum_epochs,
            )
        else:
            self.current_run_requested_epochs = maximum_epochs
        self.training_start_time = time.monotonic()
        self._last_elapsed_display_update = 0.0
        self.reset_total_workload()

        self.result_elapsed_time.setText(
            f"{self.training_elapsed_base:.1f} s"
        )

        if not continue_existing:
            self.error_chart.clear(
                self.error_limit.value()
            )
            self.error_chart_start_value = None
            self.error_chart_current_value = None
            self.history_curve_points = []
            self.reset_plateau_detection()
            self.update_error_chart_summary()
        else:
            self.error_chart.error_limit = self.error_limit.value()
            self.error_chart.update()

        monitoring_enabled = (
            self.monitor_training_data.isChecked()
        )

        self.training_monitoring_changed.emit(
            monitoring_enabled
        )

        if not continue_existing and initial_state is not None:
            if not self.restore_training_state(initial_state):
                QMessageBox.warning(
                    self,
                    self.language.text("training.message.title"),
                    self.language.text(
                        "training.repeat_initialization.incompatible"
                    ),
                )
                return
            self.current_run_initialized = True
            self.result_status.setText(
                self.language.text("training.status.initialization_reused")
            )
            self.process_training_events(force=True)

        elif not continue_existing and self.initialize_network.isChecked():
            self.initialize_network_parameters()

            weight_method = str(
                self.weight_initialization_combo.currentData() or "auto"
            )
            weight_status_keys = {
                "auto": "training.status.auto_weights",
                "xavier": "training.status.xavier_weights",
                "he": "training.status.he_weights",
                "zero": "training.status.zero_weights",
            }
            weight_text = self.language.text(
                weight_status_keys.get(
                    weight_method, "training.status.auto_weights"
                )
            )

            bias_text = (
                self.language.text("training.status.random_bias")
                if self.bias_initialization_combo.currentData()
                == "xavier"
                else self.language.text("training.status.zero_bias")
            )

            self.result_status.setText(
                self.language.text(
                    "training.status.initialized",
                    weights=weight_text,
                    bias=bias_text
                )
            )

            self.process_training_events(
                force=True
            )

        if not continue_existing:
            self.current_run_initial_state = self.capture_training_state()

        self.is_training = True
        self.stop_requested = False
        self.current_run_can_continue = False
        self.current_run_stopped = False
        self.set_training_controls_enabled(
            False
        )

        self.result_status.setText(
            self.language.text("training.status.running")
        )

        self.process_training_events(
            force=True
        )

        fast_enabled = not self.monitor_training_data.isChecked()
        self.fast_mode.setChecked(fast_enabled)
        trainer = self.network.trainer
        previous_capture_details = trainer.capture_step_details
        previous_visual_updates = trainer.visual_updates_enabled
        previous_chart_interval = self.error_chart.minimum_update_interval
        if fast_enabled:
            trainer.capture_step_details = False
            trainer.visual_updates_enabled = False
            self.error_chart.minimum_update_interval = 1.0
        last_visible_refresh = time.monotonic()

        completed_epochs = base_epochs
        mean_squared_error = None
        maximum_absolute_error = None
        self.maximum_error_details = None
        self.result_max_error_info.setEnabled(False)
        error_limit_reached = False
        training_stopped = False
        elapsed_seconds = 0.0

        try:
            self.network.prepare_training_calculation()
            update_interval = max(
                1,
                min(
                    25,
                    maximum_epochs // 100
                    if maximum_epochs >= 100
                    else 1
                )
            )

            for epoch_index in range(
                maximum_epochs
            ):
                current_epoch = base_epochs + epoch_index + 1
                metrics = self.train_epoch(
                    current_epoch,
                    base_epochs + maximum_epochs
                )

                mean_squared_error = metrics[
                    "mean_squared_error"
                ]
                maximum_absolute_error = metrics[
                    "maximum_absolute_error"
                ]
                self.maximum_error_details = metrics.get(
                    "maximum_error_details"
                )

                completed_epochs = current_epoch
                self.update_plateau_detection(
                    completed_epochs,
                    mean_squared_error,
                    maximum_absolute_error
                )
                self.result_max_error_info.setEnabled(
                    self.maximum_error_details is not None
                )

                # Jede Epoche gehört zur Kurvenform. TrainingErrorChart
                # begrenzt die tatsächlichen Neuzeichnungen selbst auf
                # höchstens zehn pro Sekunde.
                curve_point_recorded = self.add_history_curve_point(
                    completed_epochs,
                    mean_squared_error
                )

                if curve_point_recorded:
                    self.error_chart.add_point(
                        completed_epochs,
                        mean_squared_error
                    )

                if completed_epochs == 1:
                    self.error_chart_start_value = mean_squared_error
                    self.error_chart_current_value = mean_squared_error

                    self.update_error_chart_summary()

                if self.stop_requested:
                    self.result_mse.setText(
                        format_number(mean_squared_error)
                    )
                    self.result_epochs.setText(
                        str(
                            completed_epochs
                        )
                    )
                    self.result_max_error.setText(
                        format_number(maximum_absolute_error)
                    )

                    stopped_curve_point_recorded = self.add_history_curve_point(
                        completed_epochs,
                        mean_squared_error,
                        force=True
                    )

                    if stopped_curve_point_recorded:
                        self.error_chart.add_point(
                            completed_epochs,
                            mean_squared_error,
                            force_update=True
                        )
                    else:
                        self.error_chart.update()
                    self.error_chart_current_value = mean_squared_error
                    self.update_error_chart_summary()

                    training_stopped = True
                    break

                if (
                    stop_at_error_limit
                    and mean_squared_error
                    <= self.error_limit.value()
                ):
                    error_limit_reached = True
                    break

                current_time = time.monotonic()
                visible_update_due = (
                    current_time - last_visible_refresh >= 1.0
                    if fast_enabled
                    else completed_epochs % update_interval == 0
                )

                if visible_update_due:
                    last_visible_refresh = current_time
                    # Die Ergebnisfelder werden immer aktualisiert,
                    # auch wenn die Netzwerkdarstellung während
                    # des Trainings nicht live überwacht wird.
                    self.result_mse.setText(
                        format_number(mean_squared_error)
                    )

                    self.result_epochs.setText(
                        str(
                            completed_epochs
                        )
                    )

                    self.result_max_error.setText(
                        format_number(maximum_absolute_error)
                    )

                    self.error_chart_current_value = mean_squared_error
                    self.update_error_chart_summary()

                    if self.monitor_training_data.isChecked():
                        # Nur die grafische Netzwerkdarstellung
                        # wird bei ausgeschaltetem Monitoring
                        # nicht laufend aktualisiert.
                        self.training_progress.emit(
                            {
                                "mean_squared_error": mean_squared_error,
                                "completed_epochs": completed_epochs
                            }
                        )

                    self.process_training_events()

        except (
            TypeError,
            ValueError
        ) as error:
            QMessageBox.warning(
                self,
                self.language.text("training.message.title"),
                str(
                    error
                )
            )

            self.result_status.setText(
                self.language.text("training.status.aborted")
            )

            return

        finally:
            self.network.clear_prepared_training_calculation()
            trainer.capture_step_details = previous_capture_details
            trainer.visual_updates_enabled = previous_visual_updates
            self.error_chart.minimum_update_interval = previous_chart_interval
            self.is_training = False
            self.set_training_controls_enabled(
                True
            )

            # Ohne Monitoring bleibt die Netzwerkansicht auch nach dem
            # Trainingsabschnitt eingefroren. Erst ein erneutes Einschalten
            # oder das Schließen des Dialogs zeigt den erreichten Zustand.
            self.training_monitoring_changed.emit(
                self.monitor_training_data.isChecked()
            )

            self.update_elapsed_time_display(
                force=True
            )

            if self.training_start_time is not None:
                elapsed_seconds = max(
                    0.0,
                    self.training_elapsed_base
                    + time.monotonic() - self.training_start_time
                )

            self.training_start_time = None

        if mean_squared_error is None:
            self.result_status.setText(
                self.language.text("training.status.no_epoch")
            )
            return

        self.current_run_completed_epochs = completed_epochs
        self.current_run_elapsed_seconds = elapsed_seconds
        self.current_run_can_continue = True
        self.current_run_stopped = training_stopped
        self.set_training_controls_enabled(True)

        if fast_enabled and self.monitor_training_data.isChecked():
            # Ein abschließender sichtbarer Durchlauf zeigt den tatsächlich
            # erreichten Zustand, ohne die Trainingsparameter zu verändern.
            self.calculate_dataset_metrics(update_display=True)
            for connection in self.network.get_connections():
                connection.update()
            for neuron in self.network.get_neurons():
                neuron.update()

        self.result_mse.setText(
            format_number(mean_squared_error)
        )

        self.result_epochs.setText(
            str(
                completed_epochs
            )
        )

        if maximum_absolute_error is not None:
            self.result_max_error.setText(
                format_number(maximum_absolute_error)
            )

        final_curve_point_recorded = self.add_history_curve_point(
            completed_epochs,
            mean_squared_error,
            force=True
        )
        if final_curve_point_recorded:
            self.error_chart.add_point(
                completed_epochs,
                mean_squared_error,
                force_update=True
            )
        else:
            self.error_chart.update()
        self.error_chart_current_value = mean_squared_error
        self.update_error_chart_summary()

        if training_stopped:
            status_text = self.language.text("training.status.user_aborted")

        elif stop_at_error_limit:
            if error_limit_reached:
                status_text = self.language.text("training.status.limit_reached")
            else:
                status_text = self.language.text("training.status.max_epochs")
        else:
            status_text = self.language.text("training.status.completed")

        self.result_status.setText(
            status_text
        )

        self.show_total_workload()


        self.training_completed.emit(
            {
                "mean_squared_error": mean_squared_error,
                "maximum_absolute_error": maximum_absolute_error,
                "completed_epochs": completed_epochs,
                "error_limit_reached": error_limit_reached,
                "training_stopped": training_stopped,
                "status_text": status_text,
                "start_error": self.error_chart_start_value,
                "end_error": mean_squared_error,
                "elapsed_seconds": elapsed_seconds,
                "initialized": self.current_run_initialized,
                "fast_mode": not self.monitor_training_data.isChecked(),
                "weight_initialization": str(
                    self.weight_initialization_combo.currentData()
                ),
                "bias_initialization": str(
                    self.bias_initialization_combo.currentData()
                ),
                "learning_rate": float(
                    self.current_run_learning_rate
                ),
                "momentum": float(self.current_run_momentum),
                "shuffle_seed": int(self.current_run_shuffle_seed),
                "error_limit": float(
                    self.error_limit.value()
                ),
                "requested_epochs": int(self.current_run_requested_epochs),
                "stop_at_error_limit": bool(stop_at_error_limit),
                "curve_points": self.compress_history_curve(
                    self.history_curve_points
                ),
                "error_chart_scale": str(
                    self.error_chart_scale.currentData()
                ),
                "run_id": self.current_run_id,
                "timestamp": self.current_run_timestamp,
                "continue_existing": bool(continue_existing),
                "continuable": True,
                "initial_network_state": deepcopy(
                    self.current_run_initial_state
                ),
            }
        )
