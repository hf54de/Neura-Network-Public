# -------------------------------------------------------------------------------------------------
# Datei: mathematicsdialog.py
# Zweck: Erklärt Lernschritte und Berechnungen im geführten Mathematikmodus.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import html
import math
import random
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontDatabase, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget
)

from connection import Connection
from neuron import Neuron
from networktestdialog import NetworkTestDialog
from neurontype import NeuronType
from numberformat import format_number
from trainingdataio import TrainingDataIO
from language import LanguageManager
from network import NeuralNetwork


class CompactDoubleSpinBox(QDoubleSpinBox):
    """Dezimalfeld ohne unnötige Endnullen."""

    def textFromValue(self, value):
        text = super().textFromValue(value)
        decimal_point = self.locale().decimalPoint()

        if decimal_point in text:
            text = text.rstrip("0").rstrip(decimal_point)

        return text


class MathematicsNetworkView(QGraphicsView):
    """Schreibgeschützte Neuron-Lupe im vertrauten Netzwerkdesign."""

    def __init__(self, translator, parent=None):
        self.preview_scene = QGraphicsScene(parent)
        super().__init__(self.preview_scene, parent)
        self.translator = translator
        self.setMinimumHeight(255)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.minimum_scale = 0.35
        self.maximum_scale = 3.5
        self.setStyleSheet("QGraphicsView { background: #fafafa; border: 1px solid #c8c8c8; }")

    def clone_neuron(self, original, x, y, decimals=4):
        clone = Neuron(
            original.id,
            x,
            y,
            original.name,
            translator=self.translator
        )
        for attribute in (
            "neuron_type", "bias", "activation_function", "input_value",
            "sum_value", "output_value", "target_value", "error_value",
            "delta_value", "values_visible", "activation_chart_visible",
            "external_input_is_binary", "external_output_is_binary",
            "ports_visible", "name_visible", "background_brush",
            "input_header_brush", "hidden_header_brush", "output_header_brush",
            "input_port_brush", "output_port_brush"
        ):
            setattr(clone, attribute, copy.copy(getattr(original, attribute)))
        clone.io_fields_visible = False
        clone.display_decimals = decimals
        clone.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        clone.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.preview_scene.addItem(clone)
        return clone

    def refresh(
        self, selected_neuron, step=None, show_values=True,
        preserve_view=True, phase="start", decimals=4, raw_inputs=None,
        post_state=None
    ):
        if selected_neuron is None:
            self.preview_scene.clear()
            self.setSceneRect(QRectF())
            return
        keep_view = preserve_view and bool(self.preview_scene.items())
        if keep_view:
            saved_transform = self.transform()
            saved_horizontal = self.horizontalScrollBar().value()
            saved_vertical = self.verticalScrollBar().value()
        self.preview_scene.clear()
        incoming = sorted(selected_neuron.incoming_connections, key=lambda item: item.id)
        outgoing = sorted(selected_neuron.outgoing_connections, key=lambda item: item.id)
        left_count = max(1, len(incoming))
        right_count = max(1, len(outgoing))
        selected_y = max(left_count, right_count) * 105.0 - 92.5
        selected_clone = self.clone_neuron(selected_neuron, 300.0, selected_y, decimals)
        selected_clone.values_visible = show_values and (
            phase in {"sum", "activation", "error", "complete"}
            or (phase == "inputs" and selected_neuron.neuron_type == NeuronType.INPUT)
        )
        selected_clone.preview_show_bias = show_values and phase in {"start", "sum", "activation", "error", "updates", "complete"}
        selected_clone.preview_show_first_value = phase in {"sum", "activation", "error", "updates", "complete"}
        selected_clone.preview_show_output = phase in {"activation", "error", "updates", "complete"}
        if phase == "inputs" and selected_neuron.neuron_type != NeuronType.INPUT:
            selected_clone.preview_message = self.translator(
                "math.preview.not_calculated"
            )
        neuron_step = (step or {}).get("neurons", {}).get(selected_neuron.id)
        if neuron_step:
            selected_clone.bias = neuron_step["bias_before"]
            selected_clone.sum_value = neuron_step["sum"]
            selected_clone.output_value = neuron_step["output"]
            if selected_neuron.neuron_type == NeuronType.INPUT:
                selected_clone.input_value = neuron_step["output"]
            selected_clone.target_value = neuron_step["target"]
            selected_clone.error_value = neuron_step["error"]
            selected_clone.delta_value = neuron_step["delta"]
        if (
            phase in {"updates", "complete"}
            and neuron_step
            and neuron_step["neuron_type"] != NeuronType.INPUT
            and neuron_step.get("bias_update") is not None
        ):
            selected_clone.bias = (
                neuron_step["bias_before"] + neuron_step["bias_update"]
            )
        if phase == "complete" and post_state:
            post_neuron = post_state["neurons"].get(selected_neuron.id, {})
            selected_clone.input_value = post_neuron.get(
                "input", selected_clone.input_value
            )
            selected_clone.sum_value = post_neuron.get(
                "sum", selected_clone.sum_value
            )
            selected_clone.output_value = post_neuron.get(
                "output", selected_clone.output_value
            )
        raw_inputs = raw_inputs or {}
        if selected_neuron.id in raw_inputs:
            raw = raw_inputs[selected_neuron.id]
            selected_clone.io_fields_visible = phase in {"inputs", "sum", "activation", "error", "updates", "complete"}
            selected_clone.set_external_input_value(
                raw["value"], raw["scaled"], unit=raw["unit"],
                is_binary=raw["binary"]
            )

        connection_steps = (step or {}).get("connections", {})
        for index, original_connection in enumerate(incoming):
            source = self.clone_neuron(original_connection.source_neuron, 0.0, index * 210.0, decimals)
            source.values_visible = show_values and phase in {"inputs", "sum", "activation", "error", "updates", "complete"}
            source.preview_show_bias = False
            source.preview_show_first_value = phase in {"inputs", "sum", "activation", "error", "updates", "complete"}
            source.preview_show_output = phase in {"inputs", "sum", "activation", "error", "updates", "complete"}
            details = connection_steps.get(original_connection.id)
            if details:
                source.output_value = details["source_output"]
                if source.neuron_type == NeuronType.INPUT:
                    source.input_value = details["source_output"]
            if phase == "complete" and post_state:
                post_source = post_state["neurons"].get(source.id, {})
                source.input_value = post_source.get("input", source.input_value)
                source.sum_value = post_source.get("sum", source.sum_value)
                source.output_value = post_source.get("output", source.output_value)
            if original_connection.source_neuron.id in raw_inputs:
                raw = raw_inputs[original_connection.source_neuron.id]
                source.io_fields_visible = phase in {"inputs", "sum", "activation", "error", "updates", "complete"}
                source.set_external_input_value(
                    raw["value"], raw["scaled"], unit=raw["unit"],
                    is_binary=raw["binary"]
                )
            shown_weight = (
                details["weight_before"] + details["weight_update"]
                if details and phase in {"updates", "complete"}
                else details["weight_before"] if details
                else original_connection.weight
            )
            connection = Connection(
                original_connection.id, source, selected_clone,
                shown_weight,
                translator=self.translator
            )
            connection.display_decimals = decimals
            connection.update_weight_text()
            connection.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.preview_scene.addItem(connection)

        for index, original_connection in enumerate(outgoing):
            target = self.clone_neuron(original_connection.target_neuron, 600.0, index * 210.0, decimals)
            target.values_visible = show_values and phase in {"error", "updates", "complete"}
            target.preview_show_bias = False
            if phase == "complete" and post_state:
                post_target = post_state["neurons"].get(target.id, {})
                target.input_value = post_target.get("input", target.input_value)
                target.sum_value = post_target.get("sum", target.sum_value)
                target.output_value = post_target.get("output", target.output_value)
            details = connection_steps.get(original_connection.id)
            shown_weight = (
                details["weight_before"] + details["weight_update"]
                if details and phase in {"updates", "complete"}
                else details["weight_before"] if details
                else original_connection.weight
            )
            connection = Connection(
                original_connection.id, selected_clone, target,
                shown_weight,
                translator=self.translator
            )
            connection.display_decimals = decimals
            connection.update_weight_text()
            connection.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.preview_scene.addItem(connection)

        bounds = self.preview_scene.itemsBoundingRect().adjusted(-25, -25, 25, 25)
        self.preview_scene.setSceneRect(bounds)
        if keep_view:
            self.setTransform(saved_transform)
            self.horizontalScrollBar().setValue(saved_horizontal)
            self.verticalScrollBar().setValue(saved_vertical)
        else:
            self.fit_content()

    def current_scale(self):
        return abs(self.transform().m11())

    def zoom_by(self, factor):
        current = self.current_scale()
        target = max(self.minimum_scale, min(self.maximum_scale, current * factor))
        if current > 0:
            self.scale(target / current, target / current)

    def zoom_in(self):
        self.zoom_by(1.2)

    def zoom_out(self):
        self.zoom_by(1.0 / 1.2)

    def reset_zoom(self):
        self.resetTransform()
        self.centerOn(self.preview_scene.sceneRect().center())

    def fit_content(self):
        bounds = self.preview_scene.sceneRect()
        if bounds.isEmpty():
            return
        self.resetTransform()
        self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        if self.current_scale() < self.minimum_scale:
            self.resetTransform()
            self.scale(self.minimum_scale, self.minimum_scale)
            self.centerOn(bounds.center())

    def wheelEvent(self, event):
        self.zoom_by(1.2 if event.angleDelta().y() > 0 else 1.0 / 1.2)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        bounds = self.preview_scene.sceneRect()
        if not bounds.isEmpty():
            if self.current_scale() < self.minimum_scale:
                self.fit_content()


class MathematicsDialog(QDialog):
    """Datensatzweiser Lernmodus für ein ausgewähltes Neuron."""

    def __init__(
        self,
        network,
        selected_neuron,
        training_document,
        file_path=None,
        learning_rate=0.01,
        parent=None,
        language_manager=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        # Work exclusively on a deep experimental copy.  The project network
        # is never trained or initialized by this dialog.
        self.project_network = network
        self.network = self.clone_network(network)
        self.selected_neuron = (
            self.network.get_neuron(selected_neuron.id)
            if selected_neuron is not None
            else None
        )
        self.file_path = file_path
        self.records, self.input_columns, self.output_columns = (
            NetworkTestDialog.prepare_document(
                self.network,
                training_document,
                data_label=self.t("math.data.training"),
                translator=self.t
            )
        )
        self.columns = training_document.get("columns", [])
        self.epoch_number = 1
        self.record_index = 0
        self.epoch_complete = False
        self.epoch_reports = {}
        self.epoch_details = {}
        self.epoch_errors = []
        self.history = []
        self.applied = False
        self._closing_without_question = False

        self.update_window_title()
        self.setModal(True)
        self.resize(1180, 760)

        self.create_interface(float(learning_rate))
        self.project_state = self.capture_session_state()
        self.initial_state = copy.deepcopy(self.project_state)
        self.start_conditions_text = self.t("math.start.current")
        self.experiment_started = False
        self.update_interface()

    @staticmethod
    def clone_network(source_network):
        """Build a detached calculation model without copying Qt objects."""
        clone = NeuralNetwork()
        neuron_attributes = (
            "neuron_type", "bias", "activation_function", "input_value",
            "sum_value", "output_value", "target_value", "error_value",
            "delta_value", "external_input_is_binary",
            "external_output_is_binary"
        )
        for original in source_network.get_neurons():
            neuron = Neuron(
                original.id, original.x(), original.y(), original.name,
                translator=original.translator
            )
            for attribute in neuron_attributes:
                setattr(neuron, attribute, copy.copy(getattr(original, attribute)))
            clone.add_neuron(neuron)
        for original in source_network.get_connections():
            connection = Connection(
                original.id,
                clone.get_neuron(original.source_neuron.id),
                clone.get_neuron(original.target_neuron.id),
                original.weight,
                translator=original.translator
            )
            clone.add_connection(connection)
        clone.trainer.learning_rate = source_network.trainer.learning_rate
        clone.trainer.momentum = source_network.trainer.momentum
        clone.trainer.restore_momentum_state(
            source_network.trainer.get_momentum_state()
        )
        return clone

    def update_window_title(self):
        if self.selected_neuron is None:
            self.setWindowTitle(self.t("math.window.title_no_neuron"))
        else:
            self.setWindowTitle(
                self.t(
                    "math.window.title",
                    neuron=self.selected_neuron.name
                )
            )

    def create_interface(self, learning_rate):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        self.information_group = QGroupBox(self.t("math.source.group"))
        information_layout = QGridLayout(self.information_group)

        self.neuron_combo = QComboBox()
        self.neuron_combo.setMaximumWidth(350)
        self.neuron_combo.addItem(
            self.t("math.neuron.none_selected"), None
        )
        type_order = {
            NeuronType.INPUT: 0,
            NeuronType.HIDDEN: 1,
            NeuronType.OUTPUT: 2
        }
        for neuron in sorted(
            self.network.get_neurons(),
            key=lambda item: (
                type_order.get(item.neuron_type, 99),
                item.id
            )
        ):
            self.neuron_combo.addItem(
                f"{neuron.neuron_type.value} – "
                f"{neuron.activation_function} – {neuron.name}",
                neuron.id
            )
        if self.selected_neuron is not None:
            selected_index = self.neuron_combo.findData(
                self.selected_neuron.id
            )
            self.neuron_combo.setCurrentIndex(
                selected_index if selected_index >= 0 else 0
            )
        else:
            self.neuron_combo.setCurrentIndex(0)
        self.selected_neuron = self.network.get_neuron(
            self.neuron_combo.currentData()
        )
        self.neuron_combo.currentIndexChanged.connect(self.change_selected_neuron)

        self.learning_rate = CompactDoubleSpinBox()
        self.learning_rate.setMaximumWidth(150)
        self.learning_rate.setDecimals(10)
        self.learning_rate.setRange(0.000000001, 1000.0)
        self.learning_rate.setSingleStep(0.001)
        self.learning_rate.setValue(learning_rate)

        self.momentum = CompactDoubleSpinBox()
        self.momentum.setMaximumWidth(150)
        self.momentum.setDecimals(2)
        self.momentum.setRange(0.0, 0.99)
        self.momentum.setSingleStep(0.05)
        self.momentum.setValue(self.network.get_momentum())

        self.continue_radio = QRadioButton(self.t("math.start.continue"))
        self.initialize_radio = QRadioButton(self.t("math.start.new_experiment"))
        self.initialize_radio.setChecked(True)
        self.weight_initialization_combo = QComboBox()
        self.weight_initialization_combo.setMaximumWidth(250)
        self.weight_initialization_combo.addItem(
            self.t("training.initialization.auto_recommended"), "auto"
        )
        self.weight_initialization_combo.addItem(
            self.t("training.initialization.xavier_all"), "xavier"
        )
        self.weight_initialization_combo.addItem(
            self.t("training.initialization.he_all"), "he"
        )
        self.weight_initialization_combo.addItem(
            self.t("training.initialization.weights_zero"), "zero"
        )
        self.bias_initialization_combo = QComboBox()
        self.bias_initialization_combo.setMaximumWidth(220)
        self.bias_initialization_combo.addItem(
            self.t("training.initialization.bias_zero"), "zero"
        )
        self.bias_initialization_combo.addItem(
            self.t("training.initialization.xavier"), "xavier"
        )
        self.continue_radio.toggled.connect(self.start_option_changed)
        self.initialize_radio.toggled.connect(self.start_option_changed)
        self.start_conditions_label = QLabel(self.t("math.start.current"))
        self.start_conditions_label.setWordWrap(True)

        self.precision_combo = QComboBox()
        self.precision_combo.setMaximumWidth(190)
        for decimals in (2, 4, 6, 10):
            self.precision_combo.addItem(
                self.t("math.precision.decimals", count=decimals), decimals
            )
        self.precision_combo.setCurrentIndex(1)
        self.precision_combo.currentIndexChanged.connect(self.refresh_presentations)

        information_layout.addWidget(QLabel(self.t("math.neuron")), 0, 0)
        information_layout.addWidget(self.neuron_combo, 0, 1, 1, 3)
        information_layout.addWidget(QLabel(self.t("math.learning_rate")), 1, 0)
        information_layout.addWidget(self.learning_rate, 1, 1)
        information_layout.addWidget(QLabel(self.t("math.precision.label")), 1, 2)
        information_layout.addWidget(self.precision_combo, 1, 3)
        information_layout.addWidget(QLabel(self.t("math.momentum")), 2, 0)
        information_layout.addWidget(self.momentum, 2, 1)
        information_layout.addWidget(self.continue_radio, 3, 0, 1, 4)
        information_layout.addWidget(self.initialize_radio, 4, 0, 1, 4)
        self.initialization_widget = QWidget()
        initialization_layout = QHBoxLayout(self.initialization_widget)
        initialization_layout.setContentsMargins(20, 0, 0, 0)
        initialization_layout.addWidget(QLabel(self.t("training.initialization.weights")))
        initialization_layout.addWidget(self.weight_initialization_combo)
        initialization_layout.addWidget(QLabel(self.t("training.initialization.bias")))
        initialization_layout.addWidget(self.bias_initialization_combo)
        information_layout.addWidget(self.initialization_widget, 5, 0, 1, 4)
        information_layout.addWidget(self.start_conditions_label, 6, 0, 1, 4)
        self.collapse_source_button = QPushButton(
            self.t("math.source.collapse")
        )
        self.collapse_source_button.clicked.connect(
            self.collapse_source_panel
        )
        information_layout.addWidget(
            self.collapse_source_button, 6, 3, 1, 1,
            Qt.AlignmentFlag.AlignRight
        )

        self.source_summary_widget = QWidget()
        source_summary_layout = QHBoxLayout(self.source_summary_widget)
        source_summary_layout.setContentsMargins(8, 4, 4, 4)
        self.source_summary_widget.setStyleSheet(
            "QWidget { background: #f3f3f3; border: 1px solid #b8b8b8; } "
            "QLabel, QPushButton { border: none; background: transparent; }"
        )
        self.source_summary_label = QLabel()
        self.source_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.expand_source_button = QPushButton(
            self.t("math.source.expand")
        )
        self.expand_source_button.clicked.connect(
            self.expand_source_panel
        )
        source_summary_layout.addWidget(self.source_summary_label, 1)
        source_summary_layout.addWidget(self.expand_source_button)
        self.source_summary_widget.hide()

        self.status_label = QLabel()
        self.status_label.setStyleSheet(
            "QLabel { background: #eaf4fb; border: 1px solid #9fc6df; "
            "padding: 6px; }"
        )
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.source_summary_widget)
        left_layout.addWidget(self.information_group)
        left_layout.addWidget(self.status_label)
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.records_caption = QLabel(
            self.t("math.records.caption_count", count=len(self.records))
        )
        table_layout.addWidget(self.records_caption)

        self.table = QTableWidget()
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.setFont(
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        )
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(
            self.show_selected_report
        )
        table_layout.addWidget(self.table, 1)
        left_splitter.addWidget(table_container)

        explanation_container = QWidget()
        explanation_layout = QVBoxLayout(explanation_container)
        explanation_layout.setContentsMargins(0, 0, 0, 0)
        explanation_layout.addWidget(QLabel(self.t("math.guide.explanation")))
        self.guided_report = QTextBrowser()
        self.guided_report.setOpenExternalLinks(False)
        explanation_layout.addWidget(self.guided_report, 1)
        left_splitter.addWidget(explanation_container)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.setSizes([280, 280])
        left_layout.addWidget(left_splitter, 1)
        splitter.addWidget(left_container)

        report_container = QTabWidget()
        guided_container = QWidget()
        guided_layout = QVBoxLayout(guided_container)
        guided_layout.setContentsMargins(6, 6, 6, 6)
        self.network_preview = MathematicsNetworkView(self.t)
        guided_layout.addWidget(self.network_preview, 1)
        zoom_layout = QHBoxLayout()
        self.zoom_out_button = QPushButton("−")
        self.zoom_reset_button = QPushButton(self.t("math.zoom.actual"))
        self.zoom_fit_button = QPushButton(self.t("math.zoom.fit"))
        self.zoom_in_button = QPushButton("+")
        self.zoom_out_button.clicked.connect(self.network_preview.zoom_out)
        self.zoom_reset_button.clicked.connect(self.network_preview.reset_zoom)
        self.zoom_fit_button.clicked.connect(self.network_preview.fit_content)
        self.zoom_in_button.clicked.connect(self.network_preview.zoom_in)
        zoom_layout.addStretch(1)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.zoom_reset_button)
        zoom_layout.addWidget(self.zoom_fit_button)
        zoom_layout.addWidget(self.zoom_in_button)
        guided_layout.addLayout(zoom_layout)
        report_container.addTab(guided_container, self.t("math.guide.tab"))

        protocol_container = QWidget()
        report_layout = QVBoxLayout(protocol_container)
        report_layout.setContentsMargins(6, 6, 6, 6)

        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.report.setFont(
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        )
        report_layout.addWidget(self.report, 1)
        report_container.addTab(protocol_container, self.t("math.protocol.tab"))
        splitter.addWidget(report_container)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([590, 590])
        main_layout.addWidget(splitter, 1)

        workflow_layout = QVBoxLayout()
        step_layout = QHBoxLayout()
        self.previous_phase_button = QPushButton(self.t("math.guide.previous"))
        self.phase_combo = QComboBox()
        for key in (
            "start", "inputs", "sum", "activation", "error", "updates",
            "complete"
        ):
            self.phase_combo.addItem(self.t(f"math.guide.{key}"), key)
        self.next_phase_button = QPushButton(self.t("math.guide.next"))
        self.previous_phase_button.clicked.connect(lambda: self.move_phase(-1))
        self.next_phase_button.clicked.connect(self.advance_workflow)
        self.phase_combo.currentIndexChanged.connect(self.show_guided_phase)
        step_layout.addWidget(self.previous_phase_button)
        step_layout.addWidget(self.phase_combo, 1)
        step_layout.addWidget(self.next_phase_button)
        workflow_layout.addLayout(step_layout)

        navigation_layout = QHBoxLayout()
        self.start_button = QPushButton(self.t("math.button.start_experiment"))
        self.back_button = QPushButton(self.t("math.button.undo_record"))
        self.epoch_back_button = QPushButton(self.t("math.button.undo_epoch"))
        self.finish_epoch_button = QPushButton(self.t("math.button.finish_epoch"))
        self.copy_button = QPushButton(self.t("math.button.copy_report"))
        self.close_button = QPushButton(self.t("common.close"))

        self.start_button.clicked.connect(self.toggle_experiment)
        self.back_button.clicked.connect(self.step_back)
        self.epoch_back_button.clicked.connect(self.restore_previous_epoch)
        self.finish_epoch_button.clicked.connect(self.finish_epoch)
        self.copy_button.clicked.connect(self.copy_report)
        self.close_button.clicked.connect(self.request_close)

        navigation_layout.addWidget(self.start_button)
        navigation_layout.addWidget(self.back_button)
        navigation_layout.addWidget(self.epoch_back_button)
        navigation_layout.addWidget(self.finish_epoch_button)
        navigation_layout.addStretch(1)
        navigation_layout.addWidget(self.copy_button)
        navigation_layout.addWidget(self.close_button)
        workflow_layout.addLayout(navigation_layout)
        main_layout.addLayout(workflow_layout)

        self.populate_table()
        self.update_phase_labels()
        self.start_option_changed()

    def update_phase_labels(self):
        """Use honest step names for input neurons."""
        input_titles = {
            "sum": "math.guide.sum_input",
            "activation": "math.guide.activation_input",
            "error": "math.guide.error_input",
        }
        for index in range(self.phase_combo.count()):
            key = self.phase_combo.itemData(index)
            title_key = (
                input_titles.get(key, f"math.guide.{key}")
                if (
                    self.selected_neuron is not None
                    and self.selected_neuron.neuron_type == NeuronType.INPUT
                )
                else f"math.guide.{key}"
            )
            self.phase_combo.setItemText(index, self.t(title_key))

    def update_source_summary(self):
        if self.selected_neuron is None:
            self.source_summary_label.setText(
                self.t("math.neuron.none_selected")
            )
            return
        if self.initialize_radio.isChecked():
            weight_method = str(
                self.weight_initialization_combo.currentData() or "auto"
            )
            weight_texts = {
                "auto": self.t("training.initialization.auto_short"),
                "xavier": "Xavier/Glorot",
                "he": "He",
                "zero": self.t("math.source.zero_weights"),
            }
            start = self.t(
                "math.source.initialization_summary",
                weights=weight_texts.get(weight_method, weight_texts["auto"]),
                bias=(
                    "Xavier/Glorot"
                    if self.bias_initialization_combo.currentData() == "xavier"
                    else self.t("math.source.zero_bias")
                )
            )
        else:
            start = self.t("math.source.current_state")
        self.source_summary_label.setText(self.t(
            "math.source.summary",
            neuron=self.selected_neuron.name,
            learning_rate=self.learning_rate.text(),
            momentum=self.momentum.text(),
            start=start,
            precision=self.precision_combo.currentData()
        ))

    def collapse_source_panel(self):
        self.update_source_summary()
        self.information_group.hide()
        self.source_summary_widget.show()

    def expand_source_panel(self):
        self.source_summary_widget.hide()
        self.information_group.show()

    def format_column_heading(self, column, index):
        name = str(column.get(
            "name",
            self.t("math.column.fallback", column=index + 1)
        ))
        unit = str(column.get("unit", "")).strip()
        return f"{name} [{unit}]" if unit else name

    def populate_table(self):
        headers = [self.t("math.table.status"), self.t("math.table.number")] + [
            self.format_column_heading(column, index)
            for index, column in enumerate(self.columns)
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.records))

        for row, record in enumerate(self.records):
            number_item = QTableWidgetItem(str(row + 1))
            number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, number_item)

            for column, value in enumerate(record, start=2):
                value_item = QTableWidgetItem(format_number(value, 7))
                value_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, column, value_item)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 58)

    def display_number(self, value):
        decimals = int(self.precision_combo.currentData() or 4)
        return self.format_decimal(value, decimals)

    def display_change_number(self, value):
        """Zeigt kleine Parameteränderungen mit mindestens 8 Stellen."""
        decimals = max(
            8,
            int(self.precision_combo.currentData() or 4)
        )
        return self.format_decimal(value, decimals)

    def format_decimal(self, value, decimals):
        """Formatiert Dezimalzahlen und unterdrückt ein gerundetes -0."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if not math.isfinite(number):
            return str(number)
        if abs(number) < 0.5 * (10.0 ** -decimals):
            number = 0.0
        text = f"{number:.{decimals}f}"
        decimal_point = self.locale().decimalPoint()
        if decimal_point != ".":
            text = text.replace(".", decimal_point)
        return text

    def is_binary_output(self, neuron):
        return any(
            mapping["neuron"].id == neuron.id
            and mapping.get("data_type") == "binary"
            for mapping in self.output_columns
        )

    def binary_decision_text(self, value):
        state = float(value) > 0.5
        return (
            ("● " if state else "○ ")
            + self.t("binary.on" if state else "binary.off")
        )

    def start_option_changed(self, *_):
        self.initialization_widget.setVisible(self.initialize_radio.isChecked())
        if hasattr(self, "project_state") and not self.experiment_started:
            self.start_conditions_label.setText(
                self.t("math.start.pending_new")
                if self.initialize_radio.isChecked()
                else self.t("math.start.pending_current")
            )

    def initialize_parameters(self):
        weight_method = str(self.weight_initialization_combo.currentData() or "auto")
        random_bias = self.bias_initialization_combo.currentData() == "xavier"
        for connection in self.network.get_connections():
            if weight_method != "zero":
                fan_in = max(1, len(connection.target_neuron.incoming_connections))
                fan_out = max(1, len(connection.source_neuron.outgoing_connections))
                use_he = (
                    weight_method == "he"
                    or (
                        weight_method == "auto"
                        and str(connection.target_neuron.activation_function).casefold()
                        == "relu"
                    )
                )
                if use_he:
                    connection.weight = random.gauss(0.0, math.sqrt(2.0 / fan_in))
                else:
                    limit = math.sqrt(6.0 / (fan_in + fan_out))
                    connection.weight = random.uniform(-limit, limit)
            else:
                connection.weight = 0.0
        for neuron in self.network.get_neurons():
            if neuron.neuron_type == NeuronType.INPUT:
                continue
            if random_bias:
                fan_in = max(1, len(neuron.incoming_connections))
                fan_out = max(1, len(neuron.outgoing_connections))
                limit = math.sqrt(6.0 / (fan_in + fan_out))
                neuron.bias = random.uniform(-limit, limit)
            else:
                neuron.bias = 0.0
            neuron.update()
        self.network.reset_runtime_values()
        self.network.reset_training_values()

    def start_experiment(self):
        # Die sichtbare Listenauswahl ist die verbindliche Quelle. Dadurch
        # können Anzeige und Freigabestatus nicht auseinanderlaufen.
        self.selected_neuron = self.network.get_neuron(
            self.neuron_combo.currentData()
        )
        if self.selected_neuron is None:
            self.update_interface()
            return
        self.restore_network_state(self.project_state["network"])
        self.epoch_number = 1
        self.record_index = 0
        self.epoch_complete = False
        self.epoch_reports = {}
        self.epoch_details = {}
        self.epoch_errors = []
        self.history.clear()
        if self.initialize_radio.isChecked():
            self.initialize_parameters()
            self.network.reset_momentum_state()
            self.start_conditions_text = self.t(
                "math.start.initialized",
                weights=self.weight_initialization_combo.currentText(),
                bias=self.bias_initialization_combo.currentText()
            )
        else:
            self.start_conditions_text = self.t("math.start.current")
            self.network.reset_runtime_values()
            self.network.reset_training_values()
        self.start_conditions_label.setText(self.start_conditions_text)
        self.initial_state = self.capture_session_state()
        self.experiment_started = True
        self.phase_combo.setCurrentIndex(0)
        self.update_interface()
        self.refresh_presentations(preserve_view=False)
        self.collapse_source_panel()

    def prepare_experiment(self):
        self.restore_session_state(self.project_state)
        self.history.clear()
        self.experiment_started = False
        self.phase_combo.setCurrentIndex(0)
        self.report.clear()
        self.expand_source_panel()
        self.start_option_changed()
        self.update_interface()
        self.refresh_presentations(preserve_view=False)

    def toggle_experiment(self):
        if self.experiment_started:
            self.prepare_experiment()
        else:
            self.start_experiment()

    def change_selected_neuron(self, *_):
        neuron = self.network.get_neuron(self.neuron_combo.currentData())
        if neuron is None:
            self.selected_neuron = None
            self.update_phase_labels()
            self.update_window_title()
            self.update_interface()
            self.refresh_presentations(preserve_view=False)
            return
        self.selected_neuron = neuron
        self.update_phase_labels()
        if self.source_summary_widget.isVisible():
            self.update_source_summary()
        self.update_window_title()
        self.update_interface()
        self.refresh_presentations(preserve_view=False)

    def move_phase(self, offset):
        self.phase_combo.setCurrentIndex(
            max(0, min(self.phase_combo.count() - 1, self.phase_combo.currentIndex() + offset))
        )

    def advance_workflow(self):
        if not self.experiment_started:
            return
        detail = self.current_detail()
        if detail is None:
            if self.execute_next_record():
                self.phase_combo.setCurrentIndex(0)
            return
        if self.phase_combo.currentIndex() < self.phase_combo.count() - 1:
            self.move_phase(1)
            return
        if self.execute_next_record():
            self.phase_combo.setCurrentIndex(0)

    def current_detail(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self.epoch_details.get(selected_rows[0].row())

    def refresh_presentations(self, *_, preserve_view=True):
        if not hasattr(self, "network_preview"):
            return
        detail = self.current_detail()
        step = detail["step"] if detail else None
        raw_inputs = self.raw_inputs_for_detail(detail)
        self.network_preview.refresh(
            self.selected_neuron,
            step,
            show_values=self.experiment_started,
            preserve_view=preserve_view,
            phase=self.phase_combo.currentData() or "start",
            decimals=int(self.precision_combo.currentData() or 4),
            raw_inputs=raw_inputs,
            post_state=detail.get("post_state") if detail else None
        )
        self.show_selected_report(
            preserve_view=preserve_view,
            refresh_preview=False
        )
        self.show_guided_phase()

    def show_guided_phase(self, *_):
        detail = self.current_detail()
        phase_index = self.phase_combo.currentIndex()
        self.phase_combo.setEnabled(self.experiment_started and detail is not None)
        self.previous_phase_button.setEnabled(detail is not None and phase_index > 0)
        if not self.experiment_started:
            self.next_phase_button.setEnabled(False)
            self.next_phase_button.setText(self.t("math.guide.next"))
            self.guided_report.setHtml(
                f"<h3>{html.escape(self.t('math.guide.setup_title'))}</h3>"
                f"<p>{html.escape(self.t('math.guide.setup_text'))}</p>"
            )
            return
        if detail is None:
            self.next_phase_button.setEnabled(True)
            self.next_phase_button.setText(self.t("math.button.calculate_next"))
            self.guided_report.setHtml(
                f"<h3>{html.escape(self.t('math.guide.ready_title'))}</h3>"
                f"<p>{html.escape(self.start_conditions_text)}</p>"
                f"<p>{html.escape(self.t('math.guide.ready_text'))}</p>"
            )
            return
        if phase_index < self.phase_combo.count() - 2:
            self.next_phase_button.setText(self.t("math.guide.next"))
        elif phase_index == self.phase_combo.count() - 2:
            self.next_phase_button.setText(self.t("math.guide.to_summary"))
        elif detail["record_index"] >= len(self.records) - 1:
            self.next_phase_button.setText(self.t("math.button.next_epoch"))
        else:
            self.next_phase_button.setText(self.t("math.button.calculate_next"))
        self.next_phase_button.setEnabled(True)
        self.guided_report.setHtml(
            self.create_guided_html(self.phase_combo.currentData(), detail)
        )
        self.network_preview.refresh(
            self.selected_neuron, detail["step"],
            show_values=True, preserve_view=True,
            phase=self.phase_combo.currentData() or "start",
            decimals=int(self.precision_combo.currentData() or 4),
            raw_inputs=self.raw_inputs_for_detail(detail),
            post_state=detail.get("post_state")
        )

    def raw_inputs_for_detail(self, detail):
        if detail is None:
            return {}
        return {
            mapping["neuron"].id: {
                "value": detail["record"][mapping["column_index"]],
                "unit": mapping.get("unit", ""),
                "binary": mapping.get("data_type") == "binary",
                "scaled": mapping["calibration"].get("mode") != "none"
            }
            for mapping in self.input_columns
        }

    def create_guided_html(self, phase, detail):
        step = detail["step"]
        neuron_step = step["neurons"][self.selected_neuron.id]
        connections = step["connections"]
        esc = lambda value: html.escape(str(value))
        number = self.display_number
        title_key = f"math.guide.{phase}"
        if neuron_step["neuron_type"] == NeuronType.INPUT and phase in {"sum", "activation", "error"}:
            title_key += "_input"
        title = self.t(title_key)
        neuron_type = neuron_step["neuron_type"]
        intro_key = f"math.guide.{phase}_explanation"
        if phase in {"start", "activation", "error"} or (
            neuron_type == NeuronType.INPUT and phase in {"sum", "updates"}
        ):
            intro_key = (
                f"math.guide.{phase}_"
                f"{neuron_type.value.lower()}_explanation"
            )
        intro = self.t(intro_key, neuron=self.selected_neuron.name)
        guide_style = """
            <style>
                h2 { margin: 2px 0 6px 0; }
                h3 { margin: 7px 0 3px 0; }
                p { margin: 3px 0 5px 0; }
                table.guide {
                    border-collapse: collapse; margin: 3px 0 6px 0;
                }
                table.guide th {
                    text-align: left; padding: 2px 12px 3px 0;
                    border-bottom: 1px solid #b8b8b8;
                }
                table.guide td {
                    text-align: left; vertical-align: top;
                    padding: 2px 12px 2px 0;
                }
                table.guide td.number { text-align: right; white-space: nowrap; }
                table.guide th.number { text-align: right; white-space: nowrap; }
                .note { color: #666; margin-top: 6px; }
            </style>
        """
        column_widths = {
            2: (210, 150),
            3: (210, 150, 130),
            4: (210, 95, 120, 95),
            5: (80, 130, 130, 120, 120),
            7: (190, 80, 90, 80, 95, 80, 90),
        }

        def table_start(column_count):
            columns = "".join(
                f"<col width='{width}'>"
                for width in column_widths[column_count]
            )
            return f"<table class='guide'><colgroup>{columns}</colgroup>"

        body = [
            guide_style,
            f"<h2>{esc(title)}</h2>",
            f"<p>{esc(intro)}</p>"
        ]
        if phase == "start":
            body.append(f"<p><b>{esc(self.t('math.start.conditions'))}:</b> {esc(self.start_conditions_text)}</p>")
            body.append(table_start(2) + "<tr><th>Parameter</th><th class='number'>" + esc(self.t("math.value.before")) + "</th></tr>")
            for connection_id, values in sorted(connections.items()):
                relevant = (
                    values["source_id"] == self.selected_neuron.id
                    if neuron_type == NeuronType.INPUT
                    else values["target_id"] == self.selected_neuron.id
                )
                if relevant:
                    label = f"W{connection_id}: {values['source_name']} → {values['target_name']}"
                    body.append(f"<tr><td>{esc(label)}</td><td class='number'>{esc(number(values['weight_before']))}</td></tr>")
                    body.append(f"<tr><td>{esc(self.t('math.momentum_previous_velocity'))}</td><td class='number'>{esc(number(values.get('weight_previous_velocity', 0.0)))}</td></tr>")
            if neuron_type != NeuronType.INPUT:
                body.append(f"<tr><td>{esc(self.t('math.report.bias'))}</td><td class='number'>{esc(number(neuron_step['bias_before']))}</td></tr>")
                body.append(f"<tr><td>{esc(self.t('math.momentum_previous_bias_velocity'))}</td><td class='number'>{esc(number(neuron_step.get('bias_previous_velocity', 0.0)))}</td></tr>")
            body.append("</table>")
            if neuron_type == NeuronType.INPUT:
                body.append(
                    f"<p>{esc(self.t('math.guide.input_no_bias'))}</p>"
                )
        elif phase == "inputs":
            body.append(
                table_start(5)
                + "<tr><th>" + esc(self.t("math.value.kind"))
                + "</th><th>" + esc(self.t("math.value.column"))
                + "</th><th>" + esc(self.t("math.neuron"))
                + "</th><th class='number'>" + esc(self.t("math.value.raw"))
                + "</th><th class='number'>" + esc(self.t("math.value.internal"))
                + "</th></tr>"
            )
            for mapping in self.input_columns:
                raw = detail["record"][mapping["column_index"]]
                scaled = TrainingDataIO.scale_value(
                    raw, mapping["calibration"], self.t
                )
                unit = str(mapping.get("unit", "")).strip()
                raw_text = f"{number(raw)} {unit}" if unit else number(raw)
                if mapping.get("data_type") == "binary":
                    raw_text = self.binary_decision_text(raw)
                body.append(
                    f"<tr><td>{esc(self.t('math.value.input'))}</td>"
                    f"<td>{esc(mapping['column_name'])}</td>"
                    f"<td>{esc(mapping['neuron'].name)}</td>"
                    f"<td class='number'>{esc(raw_text)}</td>"
                    f"<td class='number'>{esc(number(scaled))}</td></tr>"
                )
            for mapping in self.output_columns:
                raw = detail["record"][mapping["column_index"]]
                scaled = TrainingDataIO.scale_value(
                    raw, mapping["calibration"], self.t
                )
                unit = str(mapping.get("unit", "")).strip()
                raw_text = f"{number(raw)} {unit}" if unit else number(raw)
                if mapping.get("data_type") == "binary":
                    raw_text = self.binary_decision_text(raw)
                body.append(
                    f"<tr><td>{esc(self.t('math.value.target'))}</td>"
                    f"<td>{esc(mapping['column_name'])}</td>"
                    f"<td>{esc(mapping['neuron'].name)}</td>"
                    f"<td class='number'>{esc(raw_text)}</td>"
                    f"<td class='number'>{esc(number(scaled))}</td></tr>"
                )
            body.append("</table>")
        elif phase == "sum":
            if neuron_step["neuron_type"] == NeuronType.INPUT:
                mapping = next((m for m in self.input_columns if m["neuron"].id == self.selected_neuron.id), None)
                if mapping is not None:
                    raw = detail["record"][mapping["column_index"]]
                    calibration = mapping["calibration"]
                    unit = str(mapping.get("unit", "")).strip()
                    raw_text = f"{number(raw)} {unit}" if unit else number(raw)
                    body.append(f"<p>{esc(self.t('math.guide.raw_value'))}: <b>{esc(raw_text)}</b><br>")
                    if calibration.get("mode") == "minmax_0_1":
                        minimum = number(calibration["source_min"])
                        maximum = number(calibration["source_max"])
                        body.append(f"X = ({esc(number(raw))} − {esc(minimum)}) / ({esc(maximum)} − {esc(minimum)})<br>")
                    elif calibration.get("mode") == "none":
                        body.append(f"{esc(self.t('math.guide.direct_input'))}<br>")
                    body.append(f"<b>X = {esc(number(neuron_step['output']))}</b></p>")
            else:
                body.append(
                    table_start(3)
                    + "<tr><th>"
                    + esc(self.t("math.value.connection"))
                    + "</th><th class='number'>Y × W</th><th class='number'>"
                    + esc(self.t("math.value.contribution"))
                    + "</th></tr>"
                )
                for connection_id, values in sorted(connections.items()):
                    if values["target_id"] != self.selected_neuron.id:
                        continue
                    contribution = values["source_output"] * values["weight_before"]
                    label = f"W{connection_id}: {values['source_name']} → {values['target_name']}"
                    formula = f"{number(values['source_output'])} × {number(values['weight_before'])}"
                    body.append(f"<tr><td>{esc(label)}</td><td class='number'>{esc(formula)}</td><td class='number'>{esc(number(contribution))}</td></tr>")
                body.append(f"<tr><td>{esc(self.t('math.report.bias'))}</td><td></td><td class='number'>{esc(number(neuron_step['bias_before']))}</td></tr></table>")
                body.append(f"<p><b>Σ = {esc(number(neuron_step['sum']))}</b></p>")
        elif phase == "activation":
            sum_text = esc(number(neuron_step["sum"]))
            output_text = esc(number(neuron_step["output"]))
            body.append(
                table_start(3)
                + "<tr><th>" + esc(self.t("math.value.parameter"))
                + "</th><th class='number'>" + esc(self.t("math.value.calculation"))
                + "</th><th class='number'>" + esc(self.t("math.value.result"))
                + "</th></tr>"
            )
            if neuron_type == NeuronType.INPUT:
                body.append(
                    f"<tr><td>X</td><td class='number'>{output_text}</td>"
                    f"<td class='number'>{output_text}</td></tr>"
                    f"<tr><td>Y</td><td class='number'>Y = X</td>"
                    f"<td class='number'><b>{output_text}</b></td></tr>"
                )
            else:
                activation = neuron_step["activation"]
                formulas = {
                    "Linear": ("Y = Σ", f"Y = {sum_text}"),
                    "ReLU": (
                        "Y = max(0, Σ)",
                        f"Y = max(0, {sum_text})"
                    ),
                    "Sigmoid": (
                        "Y = 1 / (1 + exp(−Σ))",
                        f"Y = 1 / (1 + exp(−({sum_text})))"
                    ),
                    "Tanh": ("Y = tanh(Σ)", f"Y = tanh({sum_text})")
                }
                general, inserted = formulas.get(
                    activation,
                    (f"Y = {esc(activation)}(Σ)", f"Y = {esc(activation)}({sum_text})")
                )
                body.append(
                    f"<tr><td>{esc(self.t('math.value.function'))}</td>"
                    f"<td class='number'>{esc(activation)}</td><td></td></tr>"
                    f"<tr><td>{esc(self.t('math.value.formula'))}</td>"
                    f"<td class='number'>{general}</td><td></td></tr>"
                    f"<tr><td>{esc(self.t('math.value.inserted'))}</td>"
                    f"<td class='number'>{inserted}</td>"
                    f"<td class='number'><b>{output_text}</b></td></tr>"
                )
            if self.is_binary_output(self.selected_neuron):
                body.append(
                    f"<tr><td>{esc(self.t('math.value.decision'))}</td>"
                    f"<td class='number'>{esc(self.t('binary.rule'))}</td>"
                    f"<td><b>{esc(self.binary_decision_text(neuron_step['output']))}</b></td></tr>"
                )
            body.append("</table>")
        elif phase == "error":
            if neuron_type == NeuronType.INPUT:
                body.append(table_start(2) + "<tr><th>" + esc(self.t("math.value.connection")) + "</th><th class='number'>δ</th></tr>")
                for connection_id, values in sorted(connections.items()):
                    if values["source_id"] == self.selected_neuron.id:
                        label = f"W{connection_id}: {values['source_name']} → {values['target_name']}"
                        body.append(f"<tr><td>{esc(label)}</td><td class='number'>{esc(number(values['target_delta']))}</td></tr>")
                body.append("</table>")
            else:
                derivative = self.network.get_activation_derivative(
                    neuron_step["activation"], neuron_step["sum"]
                )
                if neuron_type == NeuronType.OUTPUT:
                    body.append(
                        table_start(3)
                        + "<tr><th>" + esc(self.t("math.value.parameter"))
                        + "</th><th class='number'>" + esc(self.t("math.value.calculation"))
                        + "</th><th class='number'>" + esc(self.t("math.value.result"))
                        + "</th></tr>"
                        + f"<tr><td>{esc(self.t('math.value.target'))}</td><td></td><td class='number'>{esc(number(neuron_step['target']))}</td></tr>"
                        + f"<tr><td>{esc(self.t('math.value.actual'))}</td><td></td><td class='number'>{esc(number(neuron_step['output']))}</td></tr>"
                        + f"<tr><td>{esc(self.t('math.value.error'))}</td><td>{esc(number(neuron_step['target']))} − {esc(number(neuron_step['output']))}</td><td class='number'><b>{esc(number(neuron_step['error']))}</b></td></tr>"
                        + f"<tr><td>f′(Σ)</td><td></td><td class='number'>{esc(number(derivative))}</td></tr>"
                        + f"<tr><td>δ</td><td>{esc(number(neuron_step['error']))} × {esc(number(derivative))}</td><td class='number'><b>{esc(number(neuron_step['delta']))}</b></td></tr></table>"
                    )
                else:
                    weighted_sum = 0.0
                    body.append(
                        table_start(3) + "<tr><th>"
                        + esc(self.t("math.value.connection"))
                        + "</th><th class='number'>W × δ</th><th class='number'>"
                        + esc(self.t("math.value.contribution"))
                        + "</th></tr>"
                    )
                    for connection_id, values in sorted(connections.items()):
                        if values["source_id"] != self.selected_neuron.id:
                            continue
                        contribution = (
                            values["weight_before"] * values["target_delta"]
                        )
                        weighted_sum += contribution
                        label = (
                            f"W{connection_id}: {values['source_name']} → "
                            f"{values['target_name']}"
                        )
                        formula = (
                            f"{number(values['weight_before'])} × "
                            f"{number(values['target_delta'])}"
                        )
                        body.append(
                            f"<tr><td>{esc(label)}</td><td class='number'>{esc(formula)}</td>"
                            f"<td class='number'>{esc(number(contribution))}</td></tr>"
                        )
                    body.append("</table>")
                    calculated_delta = weighted_sum * derivative
                    body.append(
                        table_start(3)
                        + "<tr><th>" + esc(self.t("math.value.parameter"))
                        + "</th><th class='number'>" + esc(self.t("math.value.calculation"))
                        + "</th><th class='number'>" + esc(self.t("math.value.result"))
                        + "</th></tr>"
                        + f"<tr><td>{esc(self.t('math.value.weighted_following_sum'))}</td><td></td><td class='number'>{esc(number(weighted_sum))}</td></tr>"
                        + f"<tr><td>f′(Σ)</td><td></td><td class='number'>{esc(number(derivative))}</td></tr>"
                        + f"<tr><td>δ</td><td>{esc(number(weighted_sum))} × {esc(number(derivative))}</td><td class='number'><b>{esc(number(calculated_delta))}</b></td></tr></table>"
                    )
        elif phase == "updates":
            change_number = self.display_change_number
            def append_connection_group(title_key, predicate):
                rows = [
                    (connection_id, values)
                    for connection_id, values in sorted(connections.items())
                    if predicate(values)
                ]
                if not rows:
                    return
                body.append(f"<h3>{esc(self.t(title_key))}</h3>")
                body.append(
                    table_start(7)
                    + "<tr><th>Parameter</th><th class='number'>"
                    + esc(self.t("math.value.before"))
                    + "</th><th class='number'>" + esc(self.t("math.momentum.gradient_header")) + "</th>"
                    + "<th class='number'>" + esc(self.t("math.momentum.previous_header")) + "</th>"
                    + "<th class='number'>" + esc(self.t("math.momentum.contribution_header")) + "</th>"
                    + "<th class='number'>" + esc(self.t("math.momentum.new_header")) + "</th><th class='number'>"
                    + esc(self.t("math.value.after"))
                    + "</th></tr>"
                )
                for connection_id, values in rows:
                    before = values["weight_before"]
                    change = values["weight_update"]
                    gradient = values.get("weight_gradient_update", change)
                    previous_velocity = values.get(
                        "weight_previous_velocity", 0.0
                    )
                    momentum_term = values.get("weight_momentum_term", 0.0)
                    label = f"W{connection_id}: {values['source_name']} → {values['target_name']}"
                    body.append(f"<tr><td>{esc(label)}</td><td class='number'>{esc(number(before))}</td><td class='number'>{esc(change_number(gradient))}</td><td class='number'>{esc(change_number(previous_velocity))}</td><td class='number'>{esc(change_number(momentum_term))}</td><td class='number'>{esc(change_number(change))}</td><td class='number'><b>{esc(number(before + change))}</b></td></tr>")
                body.append("</table>")

            append_connection_group(
                "math.guide.incoming_weights",
                lambda values: values["target_id"] == self.selected_neuron.id
            )
            append_connection_group(
                "math.guide.outgoing_weights",
                lambda values: values["source_id"] == self.selected_neuron.id
            )
            if neuron_step["neuron_type"] != NeuronType.INPUT:
                before = neuron_step["bias_before"]
                change = neuron_step["bias_update"]
                body.append(
                    f"<h3>{esc(self.t('math.report.bias'))}</h3>{table_start(7)}"
                    f"<tr><th>Parameter</th>"
                    f"<th class='number'>{esc(self.t('math.value.before'))}</th>"
                    f"<th class='number'>{esc(self.t('math.momentum.gradient_header'))}</th>"
                    f"<th class='number'>{esc(self.t('math.momentum.previous_header'))}</th>"
                    f"<th class='number'>{esc(self.t('math.momentum.contribution_header'))}</th>"
                    f"<th class='number'>{esc(self.t('math.momentum.new_header'))}</th>"
                    f"<th class='number'>{esc(self.t('math.value.after'))}</th></tr>"
                )
                gradient = neuron_step.get("bias_gradient_update", change)
                previous_velocity = neuron_step.get("bias_previous_velocity", 0.0)
                momentum_term = neuron_step.get("bias_momentum_term", 0.0)
                body.append(f"<tr><td>{esc(self.t('math.report.bias'))}</td><td class='number'>{esc(number(before))}</td><td class='number'>{esc(change_number(gradient))}</td><td class='number'>{esc(change_number(previous_velocity))}</td><td class='number'>{esc(change_number(momentum_term))}</td><td class='number'>{esc(change_number(change))}</td><td class='number'><b>{esc(number(before + change))}</b></td></tr></table>")
        elif phase == "complete":
            is_epoch_end = detail["record_index"] >= len(self.records) - 1
            heading_key = (
                "math.guide.epoch_complete_title"
                if is_epoch_end
                else "math.guide.record_complete_title"
            )
            text_key = (
                "math.guide.epoch_complete_text"
                if is_epoch_end
                else "math.guide.record_complete_text"
            )
            body = [
                guide_style,
                f"<h2>{esc(self.t(heading_key, epoch=detail['epoch']))}</h2>",
                f"<p>{esc(self.t(text_key, record=detail['record_index'] + 1))}</p>",
                table_start(2)
                + "<tr><th>" + esc(self.t("math.value.parameter"))
                + "</th><th class='number'>" + esc(self.t("math.value.result"))
                + "</th></tr>",
                f"<tr><td>{esc(self.t('math.value.training_error'))}</td><td class='number'><b>{esc(number(detail.get('epoch_mean_squared_error', detail['result']['mean_squared_error'])))}</b></td></tr>"
            ]
            post_neuron = detail.get("post_state", {}).get(
                "neurons", {}
            ).get(self.selected_neuron.id)
            if post_neuron:
                if neuron_type == NeuronType.INPUT:
                    control_values = (
                        f"X = Y = {number(post_neuron['output'])}"
                    )
                else:
                    control_values = (
                        f"Σ = {number(post_neuron['sum'])}; "
                        f"Y = {number(post_neuron['output'])}"
                    )
                body.append(
                    f"<tr><td>{esc(self.t('math.guide.post_update_control'))}</td>"
                    f"<td class='number'><b>{esc(control_values)}</b></td></tr>"
                )
            for connection_id, values in sorted(connections.items()):
                relevant = (
                    values["source_id"] == self.selected_neuron.id
                    if neuron_type == NeuronType.INPUT
                    else values["target_id"] == self.selected_neuron.id
                )
                if relevant:
                    gradient = values.get(
                        "weight_gradient_update", values["weight_update"]
                    )
                    previous_velocity = values.get(
                        "weight_previous_velocity", 0.0
                    )
                    momentum_term = values.get("weight_momentum_term", 0.0)
                    new_velocity = values["weight_update"]
                    parameter = f"W{connection_id}"
                    for label_key, value in (
                        ("math.momentum.summary_gradient", gradient),
                        ("math.momentum.summary_previous", previous_velocity),
                        ("math.momentum.summary_contribution", momentum_term),
                        ("math.momentum.summary_new_velocity", new_velocity),
                    ):
                        body.append(
                            f"<tr><td>{esc(parameter)} – {esc(self.t(label_key))}</td>"
                            f"<td class='number'><b>{esc(number(value))}</b></td></tr>"
                        )
            if neuron_type != NeuronType.INPUT:
                bias_gradient = neuron_step.get(
                    "bias_gradient_update", neuron_step["bias_update"]
                )
                bias_previous_velocity = neuron_step.get(
                    "bias_previous_velocity", 0.0
                )
                bias_momentum_term = neuron_step.get("bias_momentum_term", 0.0)
                bias_new_velocity = neuron_step["bias_update"]
                for label_key, value in (
                    ("math.momentum.summary_gradient", bias_gradient),
                    ("math.momentum.summary_previous", bias_previous_velocity),
                    ("math.momentum.summary_contribution", bias_momentum_term),
                    ("math.momentum.summary_new_velocity", bias_new_velocity),
                ):
                    body.append(
                        f"<tr><td>{esc(self.t('math.report.bias'))} – "
                        f"{esc(self.t(label_key))}</td>"
                        f"<td class='number'><b>{esc(number(value))}</b></td></tr>"
                    )
            body.extend([
                "</table>",
                f"<p>{esc(self.t('math.guide.inspect_other_neuron'))}</p>"
            ])
        body.append(f"<p class='note'>{esc(self.t('math.precision.note'))}</p>")
        return "".join(body)

    def apply_record(self, record):
        for mapping in self.input_columns:
            raw_value = record[mapping["column_index"]]
            mapping["neuron"].input_value = TrainingDataIO.scale_value(
                raw_value,
                mapping["calibration"],
                self.t
            )
            mapping["neuron"].set_external_input_value(
                raw_value,
                mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )
            mapping["neuron"].update()

        targets = {}
        for mapping in self.output_columns:
            raw_target = record[mapping["column_index"]]
            targets[mapping["neuron"].id] = TrainingDataIO.scale_value(
                raw_target,
                mapping["calibration"],
                self.t
            )
            mapping["neuron"].set_external_output_values(
                target_value=raw_target,
                is_raw=mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )
        return targets

    def update_external_output_values(self, record):
        for mapping in self.output_columns:
            neuron = mapping["neuron"]
            raw_output = TrainingDataIO.unscale_value(
                neuron.output_value,
                mapping["calibration"],
                self.t
            )
            neuron.set_external_output_values(
                actual_value=raw_output,
                target_value=record[mapping["column_index"]],
                is_raw=mapping["calibration"]["mode"] != "none",
                unit=mapping.get("unit", ""),
                is_binary=mapping.get("data_type") == "binary"
            )

    def capture_network_state(self):
        trainer = self.network.trainer
        return {
            "learning_rate": trainer.learning_rate,
            "momentum": trainer.momentum,
            "momentum_state": trainer.get_momentum_state(),
            "weights": {
                connection.id: connection.weight
                for connection in self.network.get_connections()
            },
            "neurons": {
                neuron.id: {
                    "bias": neuron.bias,
                    "input": neuron.input_value,
                    "sum": neuron.sum_value,
                    "output": neuron.output_value,
                    "target": neuron.target_value,
                    "error": neuron.error_value,
                    "delta": neuron.delta_value,
                    "external_input": neuron.external_input_value,
                    "external_input_is_raw": neuron.external_input_is_raw,
                    "external_input_is_binary": neuron.external_input_is_binary,
                    "external_output": neuron.external_output_value,
                    "external_target": neuron.external_target_value,
                    "external_output_is_raw": neuron.external_output_is_raw,
                    "external_output_is_binary": neuron.external_output_is_binary
                }
                for neuron in self.network.get_neurons()
            },
            "trainer_targets": copy.deepcopy(trainer.target_values),
            "trainer_errors": copy.deepcopy(trainer.error_values),
            "trainer_deltas": copy.deepcopy(trainer.delta_values),
            "last_step_details": copy.deepcopy(trainer.last_step_details)
        }

    def restore_network_state(self, state):
        self.network.set_learning_rate(state["learning_rate"])
        self.network.set_momentum(state.get("momentum", 0.0))
        self.network.restore_momentum_state(state.get("momentum_state"))

        for connection in self.network.get_connections():
            if connection.id in state["weights"]:
                connection.weight = state["weights"][connection.id]
                connection.update()

        for neuron in self.network.get_neurons():
            values = state["neurons"].get(neuron.id)
            if values is None:
                continue
            neuron.bias = values["bias"]
            neuron.input_value = values["input"]
            neuron.sum_value = values["sum"]
            neuron.output_value = values["output"]
            neuron.target_value = values["target"]
            neuron.error_value = values["error"]
            neuron.delta_value = values["delta"]
            neuron.external_input_value = values["external_input"]
            neuron.external_input_is_raw = values[
                "external_input_is_raw"
            ]
            neuron.external_input_is_binary = values.get(
                "external_input_is_binary", False
            )
            neuron.external_output_value = values["external_output"]
            neuron.external_target_value = values["external_target"]
            neuron.external_output_is_raw = values[
                "external_output_is_raw"
            ]
            neuron.external_output_is_binary = values.get(
                "external_output_is_binary", False
            )
            neuron.update()

        trainer = self.network.trainer
        trainer.target_values = copy.deepcopy(state["trainer_targets"])
        trainer.error_values = copy.deepcopy(state["trainer_errors"])
        trainer.delta_values = copy.deepcopy(state["trainer_deltas"])
        trainer.last_step_details = copy.deepcopy(
            state["last_step_details"]
        )

    def capture_session_state(self):
        return {
            "network": self.capture_network_state(),
            "epoch_number": self.epoch_number,
            "record_index": self.record_index,
            "epoch_complete": self.epoch_complete,
            "epoch_reports": copy.deepcopy(self.epoch_reports),
            "epoch_details": copy.deepcopy(self.epoch_details),
            "epoch_errors": list(self.epoch_errors),
            "learning_rate_field": self.learning_rate.value()
            ,"momentum_field": self.momentum.value()
        }

    def restore_session_state(self, state):
        self.restore_network_state(state["network"])
        self.epoch_number = state["epoch_number"]
        self.record_index = state["record_index"]
        self.epoch_complete = state["epoch_complete"]
        self.epoch_reports = copy.deepcopy(state["epoch_reports"])
        self.epoch_details = copy.deepcopy(state.get("epoch_details", {}))
        self.epoch_errors = list(state["epoch_errors"])
        self.learning_rate.setValue(state["learning_rate_field"])
        self.momentum.setValue(state.get("momentum_field", 0.0))
        self.update_interface()

    def begin_next_epoch(self):
        self.epoch_number += 1
        self.record_index = 0
        self.epoch_complete = False
        self.epoch_reports = {}
        self.epoch_details = {}
        self.epoch_errors = []

    def execute_next_record(self):
        if not self.experiment_started:
            return False
        try:
            if self.epoch_complete:
                self.begin_next_epoch()

            previous_state = self.capture_session_state()
            self.history.append(previous_state)

            current_index = self.record_index
            record = self.records[current_index]
            self.network.set_learning_rate(self.learning_rate.value())
            self.network.set_momentum(self.momentum.value())
            self.network.reset_runtime_values()
            self.network.reset_training_values()
            targets = self.apply_record(record)
            result = self.network.train_step(targets)
            self.update_external_output_values(record)
            step = copy.deepcopy(self.network.trainer.last_step_details)
            # A read-only control pass with the already updated parameters.
            # It does not perform another learning step and is stored solely
            # so the final view represents one consistent point in time.
            self.network.forward_pass()
            post_state = {
                "weights": {
                    connection.id: connection.weight
                    for connection in self.network.get_connections()
                },
                "neurons": {
                    neuron.id: {
                        "input": neuron.input_value,
                        "sum": neuron.sum_value,
                        "output": neuron.output_value,
                        "bias": neuron.bias
                    }
                    for neuron in self.network.get_neurons()
                }
            }
            report = self.create_report(
                self.epoch_number,
                current_index,
                record,
                result,
                step=step
            )
            self.epoch_reports[current_index] = report
            self.epoch_details[current_index] = {
                "epoch": self.epoch_number,
                "record_index": current_index,
                "record": copy.deepcopy(record),
                "result": copy.deepcopy(result),
                "step": step,
                "post_state": post_state
            }
            self.epoch_errors.append(result["mean_squared_error"])
            self.record_index += 1

            if self.record_index >= len(self.records):
                self.epoch_complete = True
                self.epoch_details[current_index][
                    "epoch_mean_squared_error"
                ] = sum(self.epoch_errors) / len(self.epoch_errors)

            self.update_interface(select_row=current_index)
            return True

        except (TypeError, ValueError) as error:
            self.history.pop()
            self.restore_session_state(previous_state)
            QMessageBox.warning(
                self,
                self.t("math.message.title"),
                str(error)
            )
            return False

    def finish_epoch(self):
        if not self.experiment_started or self.epoch_complete:
            return

        while not self.epoch_complete:
            if not self.execute_next_record():
                break
            QApplication.processEvents()
        if self.epoch_complete:
            self.phase_combo.setCurrentIndex(self.phase_combo.count() - 1)

    def step_back(self):
        if not self.experiment_started or not self.history:
            return

        state = self.history.pop()
        self.restore_session_state(state)

        if self.epoch_reports:
            self.table.selectRow(max(self.epoch_reports))
            self.phase_combo.setCurrentIndex(self.phase_combo.count() - 1)
        else:
            self.phase_combo.setCurrentIndex(0)

    def epoch_rollback_target(self):
        target_epoch = self.epoch_number
        if self.record_index == 0 and not self.epoch_complete:
            target_epoch -= 1
        if target_epoch < 1:
            return None
        for index, state in enumerate(self.history):
            if (
                state["epoch_number"] == target_epoch
                and state["record_index"] == 0
                and not state["epoch_complete"]
            ):
                return index, target_epoch, state
        return None

    def restore_previous_epoch(self, checked=False, confirm=True):
        if not self.experiment_started:
            return
        target = self.epoch_rollback_target()
        if target is None:
            return
        index, target_epoch, state = target
        if confirm:
            answer = QMessageBox.question(
                self,
                self.t("math.epoch_back.title"),
                self.t("math.epoch_back.question", epoch=target_epoch),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.history = self.history[:index]
        self.restore_session_state(state)
        self.phase_combo.setCurrentIndex(0)
        self.report.setPlainText(
            self.t("math.epoch_back.restored", epoch=target_epoch)
        )

    def update_interface(self, select_row=None):
        selected_from_list = self.network.get_neuron(
            self.neuron_combo.currentData()
        )
        if not self.experiment_started:
            self.selected_neuron = selected_from_list
        has_selected_neuron = self.selected_neuron is not None

        for row in range(len(self.records)):
            if row in self.epoch_reports:
                status = "✓"
                color = QColor(220, 245, 226)
            elif self.experiment_started and not self.epoch_complete and row == self.record_index:
                status = "→"
                color = QColor(230, 242, 252)
            else:
                status = ""
                color = QColor(Qt.GlobalColor.transparent)

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setBackground(color)
            self.table.setItem(row, 0, status_item)

        if not self.experiment_started:
            self.status_label.setText(
                self.t(
                    "math.status.select_neuron"
                    if not has_selected_neuron
                    else "math.status.not_started"
                )
            )
        elif self.epoch_complete:
            mean_error = sum(self.epoch_errors) / len(self.epoch_errors)
            self.status_label.setText(
                self.t(
                    "math.status.epoch_completed",
                    epoch=self.epoch_number,
                    records=len(self.records),
                    error=format_number(mean_error)
                )
            )
        else:
            selected = self.table.selectionModel().selectedRows()
            selected_row = selected[0].row() if selected else None
            if selected_row in self.epoch_details:
                self.status_label.setText(self.t(
                    "math.status.display_and_next", epoch=self.epoch_number,
                    displayed=selected_row + 1, next=self.record_index + 1,
                    total=len(self.records)
                ))
            else:
                self.status_label.setText(self.t(
                    "math.status.next_record", epoch=self.epoch_number,
                    record=self.record_index + 1, total=len(self.records)
                ))

        self.back_button.setEnabled(self.experiment_started and bool(self.history))
        self.epoch_back_button.setEnabled(
            self.experiment_started and self.epoch_rollback_target() is not None
        )
        self.finish_epoch_button.setEnabled(
            self.experiment_started and not self.epoch_complete
        )
        self.start_button.setText(
            self.t("math.button.prepare_experiment")
            if self.experiment_started
            else self.t("math.button.start_experiment")
        )
        self.start_button.setEnabled(
            self.experiment_started
            or has_selected_neuron
        )
        controls_enabled = not self.experiment_started
        self.neuron_combo.setEnabled(controls_enabled)
        self.learning_rate.setEnabled(controls_enabled)
        self.momentum.setEnabled(controls_enabled)
        self.continue_radio.setEnabled(controls_enabled)
        self.initialize_radio.setEnabled(controls_enabled)
        self.weight_initialization_combo.setEnabled(controls_enabled)
        self.bias_initialization_combo.setEnabled(controls_enabled)

        if select_row is not None:
            self.table.selectRow(select_row)
            self.show_selected_report()
        elif self.experiment_started and not self.epoch_reports:
            self.table.selectRow(self.record_index)
            self.report.setPlainText(
                self.t("math.report.none_calculated")
            )
            self.refresh_presentations()
        elif not self.experiment_started:
            self.table.clearSelection()
            self.report.setPlainText(self.t("math.report.not_started"))
            self.refresh_presentations()

    def show_selected_report(
        self, *_, preserve_view=True, refresh_preview=True
    ):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        report = self.epoch_reports.get(row)
        detail = self.epoch_details.get(row)

        if detail is None:
            self.report.setPlainText(
                self.t(
                    "math.report.record_not_processed",
                    record=row + 1,
                    epoch=self.epoch_number
                )
            )
        else:
            report = self.create_report(
                detail["epoch"],
                detail["record_index"],
                detail["record"],
                detail["result"],
                step=detail["step"]
            )
            self.epoch_reports[row] = report
            self.report.setPlainText(report)
        if refresh_preview and hasattr(self, "network_preview"):
            self.network_preview.refresh(
                self.selected_neuron,
                detail["step"] if detail else None,
                show_values=self.experiment_started,
                preserve_view=preserve_view,
                phase=self.phase_combo.currentData() or "start",
                decimals=int(self.precision_combo.currentData() or 4),
                raw_inputs=self.raw_inputs_for_detail(detail),
                post_state=detail.get("post_state") if detail else None
            )
            self.show_guided_phase()
        if self.experiment_started and not self.epoch_complete and detail is not None:
            self.status_label.setText(self.t(
                "math.status.display_and_next", epoch=self.epoch_number,
                displayed=row + 1, next=self.record_index + 1,
                total=len(self.records)
            ))

    def create_report(self, epoch, record_index, record, result, step=None):
        format_number = self.display_number
        step = step or self.network.trainer.last_step_details
        neuron_step = step["neurons"][self.selected_neuron.id]
        connections = step["connections"]
        lines = [
            self.t(
                "math.report.epoch_record",
                epoch=epoch,
                record=record_index + 1
            ),
            "=" * 42,
            "",
            self.t(
                "math.report.selected_neuron",
                neuron=self.selected_neuron.name
            ),
            ""
        ]

        lines.append(self.t("math.report.input_targets"))
        lines.append("======================")
        lines.append("")
        for mapping in self.input_columns:
            raw = record[mapping["column_index"]]
            scaled = TrainingDataIO.scale_value(
                raw, mapping["calibration"], self.t
            )
            lines.append(
                self.t(
                    "math.report.input_value",
                    column=mapping["column_name"],
                    neuron=mapping["neuron"].name,
                    raw=format_number(raw),
                    network=format_number(scaled)
                )
            )
        for mapping in self.output_columns:
            raw = record[mapping["column_index"]]
            scaled = TrainingDataIO.scale_value(
                raw, mapping["calibration"], self.t
            )
            lines.append(
                self.t(
                    "math.report.target_value",
                    column=mapping["column_name"],
                    neuron=mapping["neuron"].name,
                    raw=format_number(raw),
                    network=format_number(scaled)
                )
            )

        if neuron_step["neuron_type"] == NeuronType.INPUT:
            lines.extend(
                [
                    "",
                    self.t("math.report.forward"),
                    "=================",
                    "",
                    "Y = X",
                    f"Y = {format_number(neuron_step['output'])}"
                ]
            )
            if self.is_binary_output(self.selected_neuron):
                lines.append(
                    self.t(
                        "math.report.binary_decision",
                        decision=self.binary_decision_text(
                            neuron_step["output"]
                        )
                    )
                )
        else:
            lines.extend(
                [
                    "",
                    self.t("math.report.weighted_sum"),
                    "=================",
                    "",
                    self.t("math.formula.weighted_sum"),
                    ""
                ]
            )
            for connection_id, details in sorted(connections.items()):
                if details["target_id"] != self.selected_neuron.id:
                    continue
                contribution = (
                    details["source_output"] * details["weight_before"]
                )
                lines.append(
                    f"W{connection_id}: {details['source_name']} → "
                    f"{details['target_name']}"
                )
                lines.append(f"{details['source_name']}.Y × W{connection_id}")
                lines.append(
                    f"= {format_number(details['source_output'])} × "
                    f"{format_number(details['weight_before'])}"
                )
                lines.append(f"= {format_number(contribution)}")
                lines.append("")
            lines.append(
                f"Bias = {format_number(neuron_step['bias_before'])}"
            )
            lines.append(f"Σ = {format_number(neuron_step['sum'])}")

            activation_formulas = {
                "Linear": "Y = Σ",
                "ReLU": "Y = max(0, Σ)",
                "Sigmoid": "Y = 1 / (1 + e^(-Σ))",
                "Tanh": "Y = tanh(Σ)"
            }
            lines.extend(
                [
                    "",
                    self.t("math.report.activation"),
                    "===========",
                    "",
                    activation_formulas[neuron_step["activation"]],
                    f"Σ = {format_number(neuron_step['sum'])}",
                    f"Y = {format_number(neuron_step['output'])}"
                ]
            )

            if self.is_binary_output(self.selected_neuron):
                lines.append(
                    self.t(
                        "math.report.binary_decision",
                        decision=self.binary_decision_text(
                            neuron_step["output"]
                        )
                    )
                )

            derivative = self.network.get_activation_derivative(
                neuron_step["activation"],
                neuron_step["sum"]
            )
            derivative_formulas = {
                "Linear": "f'(Σ) = 1",
                "ReLU": self.t("math.formula.relu_derivative"),
                "Sigmoid": "f'(Σ) = Y × (1 - Y)",
                "Tanh": "f'(Σ) = 1 - Y²"
            }
            lines.extend(
                [
                    "",
                    self.t("math.report.backward"),
                    "=================",
                    "",
                    derivative_formulas[neuron_step["activation"]],
                    f"f'(Σ) = {format_number(derivative)}"
                ]
            )

            if neuron_step["neuron_type"] == NeuronType.OUTPUT:
                lines.extend(
                    [
                        "",
                        self.t("math.formula.output_error"),
                        f"= {format_number(neuron_step['target'])} - "
                        f"{format_number(neuron_step['output'])}",
                        f"= {format_number(neuron_step['error'])}",
                        "",
                        self.t("math.formula.output_delta"),
                        f"= {format_number(neuron_step['error'])} × "
                        f"{format_number(derivative)}",
                        f"= {format_number(neuron_step['delta'])}"
                    ]
                )
            else:
                backward_sum = 0.0
                lines.extend(
                    [
                        "",
                        self.t("math.formula.backward_sum"),
                        ""
                    ]
                )
                for connection_id, details in sorted(connections.items()):
                    if details["source_id"] != self.selected_neuron.id:
                        continue
                    contribution = (
                        details["weight_before"] * details["target_delta"]
                    )
                    backward_sum += contribution
                    lines.append(
                        f"W{connection_id} × δ({details['target_name']})"
                    )
                    lines.append(
                        f"= {format_number(details['weight_before'])} × "
                        f"{format_number(details['target_delta'])}"
                    )
                    lines.append(f"= {format_number(contribution)}")
                    lines.append("")
                lines.extend(
                    [
                        self.t("math.formula.hidden_delta"),
                        f"= {format_number(backward_sum)} × "
                        f"{format_number(derivative)}",
                        f"= {format_number(neuron_step['delta'])}"
                    ]
                )

        lines.extend(
            [
                "",
                self.t("math.report.parameter_changes"),
                "===================",
                ""
            ]
        )
        relevant_connection_found = False
        for connection_id, details in sorted(connections.items()):
            if neuron_step["neuron_type"] == NeuronType.INPUT:
                relevant = details["source_id"] == self.selected_neuron.id
            else:
                relevant = details["target_id"] == self.selected_neuron.id
            if not relevant:
                continue
            relevant_connection_found = True
            new_weight = details["weight_before"] + details["weight_update"]
            lines.extend(
                [
                    f"W{connection_id}: {details['source_name']} → "
                    f"{details['target_name']}",
                    self.t("math.formula.weight_update"),
                    f"= {format_number(step['learning_rate'])} × "
                    f"{format_number(details['target_delta'])} × "
                    f"{format_number(details['source_output'])}",
                    self.t("math.momentum.gradient", value=format_number(details.get('weight_gradient_update', details['weight_update']))),
                    self.t("math.momentum.previous", value=format_number(details.get('weight_previous_velocity', 0.0))),
                    self.t("math.momentum.contribution", value=format_number(details.get('weight_momentum_term', 0.0))),
                    self.t("math.momentum.new_velocity", value=format_number(details['weight_update'])),
                    f"Wneu = {format_number(details['weight_before'])} + "
                    f"{format_number(details['weight_update'])}",
                    f"Wneu = {format_number(new_weight)}",
                    ""
                ]
            )

        if not relevant_connection_found:
            lines.append(self.t("math.report.no_weight_change"))

        if neuron_step["neuron_type"] != NeuronType.INPUT:
            bias_update = neuron_step["bias_update"]
            lines.extend(
                [
                    self.t("math.report.bias"),
                    self.t("math.formula.bias_update"),
                    f"= {format_number(step['learning_rate'])} × "
                    f"{format_number(neuron_step['delta'])}",
                    self.t("math.momentum.gradient", value=format_number(neuron_step.get('bias_gradient_update', bias_update))),
                    self.t("math.momentum.previous", value=format_number(neuron_step.get('bias_previous_velocity', 0.0))),
                    self.t("math.momentum.contribution", value=format_number(neuron_step.get('bias_momentum_term', 0.0))),
                    self.t("math.momentum.new_velocity", value=format_number(bias_update)),
                    f"Bneu = {format_number(neuron_step['bias_before'])} + "
                    f"{format_number(bias_update)}",
                    f"Bneu = "
                    f"{format_number(neuron_step['bias_before'] + bias_update)}"
                ]
            )

        lines.extend(
            [
                "",
                self.t("math.report.step_result"),
                "==========================",
                "",
                self.t(
                    "math.report.mean_squared_error",
                    error=format_number(result["mean_squared_error"])
                )
            ]
        )
        return "\n".join(lines)

    def copy_report(self):
        QApplication.clipboard().setText(self.report.toPlainText())

    def request_close(self):
        # Der Mathematikmodus ist ein reiner Experimentierbereich.
        # Beim Verlassen wird daher immer exakt der Netzwerkzustand
        # vom Öffnen des Dialogs wiederhergestellt.
        self.restore_session_state(self.project_state)
        self.history.clear()
        self.applied = False
        self._closing_without_question = True
        self.accept()

    def reject(self):
        if self._closing_without_question:
            super().reject()
        else:
            self.request_close()

    @property
    def learning_rate_value(self):
        return self.learning_rate.value()
