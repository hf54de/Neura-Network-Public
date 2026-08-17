# -------------------------------------------------------------------------------------------------
# Datei: forwardcalibrationdialog.py
# Zweck: Ermöglicht interaktive Experimente und Vorwärtsberechnungen mit Rohwerten.
# Letzte Änderung: 14.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import math

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSizePolicy,
    QStackedWidget,
    QHBoxLayout,
    QVBoxLayout,
    QWidget
)

from trainingdataio import TrainingDataIO
from graphicalexperimentdialog import GraphicalExperimentDialog
from numberformat import format_number
from language import LanguageManager
from settings import Settings


class CompactDoubleSpinBox(QDoubleSpinBox):
    """Dezimalfeld ohne überflüssige Endnullen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)

    def textFromValue(self, value):
        text = super().textFromValue(value)
        decimal_point = self.locale().decimalPoint()

        if decimal_point in text:
            integer, fraction = text.split(decimal_point, 1)
            fraction = fraction[:2].rstrip("0")
            text = (
                integer + decimal_point + fraction
                if fraction
                else integer
            )

        return text


class BinaryToggleButton(QPushButton):
    """Ruhiger, eindeutig beschrifteter Ein-/Aus-Schalter."""

    def __init__(self, language, checked=False, parent=None):
        super().__init__(parent)
        self.language = language
        self.setCheckable(True)
        self.setFixedHeight(20)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.toggled.connect(self.update_presentation)
        self.setChecked(bool(checked))
        self.update_presentation(self.isChecked())

    def update_presentation(self, checked):
        self.setText(
            ("● " if checked else "○ ")
            + self.language.text("binary.on" if checked else "binary.off")
        )
        self.setStyleSheet(
            "QPushButton { padding: 2px 10px; border-radius: 5px; "
            "border: 1px solid %s; background: %s; color: %s; "
            "font-weight: 600; } QPushButton:hover { border-color: #4f788f; }"
            % (
                "#31834a" if checked else "#8c969f",
                "#dff3e4" if checked else "#eef1f3",
                "#185f30" if checked else "#46515a"
            )
        )

    def numeric_value(self):
        return 1.0 if self.isChecked() else 0.0


class BinaryStateLabel(QLabel):
    """Nicht bedienbare binäre Ergebnisanzeige."""

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.setMinimumWidth(105)
        self.setFixedHeight(18)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(False)

    def set_state(self, state):
        state = bool(state)
        self.setText(
            ("● " if state else "○ ")
            + self.language.text("binary.on" if state else "binary.off")
        )
        self.setStyleSheet(
            "QLabel { padding: 1px 6px; border-radius: 4px; "
            "border: 1px solid %s; background: %s; color: %s; "
            "font-weight: 600; }"
            % (
                "#31834a" if state else "#8c969f",
                "#dff3e4" if state else "#eef1f3",
                "#185f30" if state else "#46515a"
            )
        )


class BinaryArrayPaintController(QObject):
    """Schaltet jedes mit gedrückter Maustaste neu betretene Rasterfeld um."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = set()
        self.last_button = None
        self.press_started_on_button = False
        self.application = QApplication.instance()
        self.filter_installed = False
        if self.application is not None:
            self.application.installEventFilter(self)
            self.filter_installed = True

    def deactivate(self):
        """Meldet den globalen Mausfilter beim Schließen wieder ab."""

        if self.filter_installed and self.application is not None:
            self.application.removeEventFilter(self)
        self.filter_installed = False
        self.buttons.clear()
        self.last_button = None
        self.press_started_on_button = False

    def set_buttons(self, buttons):
        self.buttons = set(buttons)
        self.last_button = None

    def button_at(self, event):
        position = event.globalPosition().toPoint()
        widget = QApplication.widgetAt(position)
        return widget if widget in self.buttons else None

    def eventFilter(self, watched, event):
        event_type = event.type()
        if (
            event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            button = self.button_at(event)
            self.last_button = button
            self.press_started_on_button = button is not None
            if button is not None:
                button.setChecked(not button.isChecked())
                return True
        elif event_type == QEvent.Type.MouseMove:
            if not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                self.last_button = None
                return False
            button = self.button_at(event)
            if button is not self.last_button:
                self.last_button = button
                if button is not None:
                    button.setChecked(not button.isChecked())
        elif (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            suppress_release = self.press_started_on_button
            self.last_button = None
            self.press_started_on_button = False
            return suppress_release
        return False

class AnalogOutputBar(QProgressBar):
    """Gefüllte, nicht bedienbare analoge Ergebnisanzeige."""

    def __init__(self, language, minimum, maximum, parent=None):
        super().__init__(parent)
        self.language = language
        self.raw_minimum = float(minimum)
        self.raw_maximum = float(maximum)
        self.setRange(0, 1000)
        self.setMinimumWidth(130)
        self.setFixedHeight(18)
        self.setTextVisible(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_result(self, value):
        value = float(value)
        outside = (
            value < self.raw_minimum
            or value > self.raw_maximum
        )
        if self.raw_maximum > self.raw_minimum:
            position = round(
                (value - self.raw_minimum)
                / (self.raw_maximum - self.raw_minimum)
                * self.maximum()
            )
        else:
            position = self.minimum()
        self.setValue(max(self.minimum(), min(self.maximum(), position)))
        self.setToolTip(
            self.language.text(
                "forward.output.outside_range"
                if outside
                else "forward.output.within_range"
            )
        )
        self.setStyleSheet(
            "QProgressBar { border: 2px solid %s; border-radius: 4px; "
            "background: #eeeeee; } "
            "QProgressBar::chunk { background: %s; border-radius: 2px; }"
            % (
                "#c62828" if outside else "#8c969f",
                "#c62828" if outside else "#c51d24"
            )
        )


class ForwardCalibrationDialog(QDialog):
    """Manuelle Vorwärtsberechnung mit kalibrierten Rohwerten."""

    calculation_updated = Signal()

    SHARED_COLUMN_WIDTHS = (95, 130, 105, 75, 115)
    VALUE_COLUMN_MINIMUM = 130

    def __init__(
        self,
        network,
        input_columns,
        output_columns,
        records=None,
        file_path=None,
        input_array=None,
        training_document=None,
        parent=None,
        language_manager=None,
        color_settings=None,
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.color_settings = dict(color_settings or {})
        self.network = network
        self.input_columns = input_columns
        self.output_columns = output_columns
        self.records = list(records or [])
        self.file_path = file_path
        self.input_array = input_array if isinstance(input_array, dict) else None
        self.training_document = (
            copy.deepcopy(training_document)
            if isinstance(training_document, dict)
            else None
        )
        self.training_document_modified = False
        self.array_view_active = False
        self.array_buttons = {}
        self.input_widgets = []
        self.output_widgets = []
        self.calculation_performed = False
        self.experimental_binary_mode = False
        self.has_binary_columns = any(
            mapping.get("data_type") == "binary"
            for mapping in self.output_columns
        )

        self.setWindowTitle(
            self.language.text("forward.window.title")
        )
        self.setModal(True)
        self.ui_settings = Settings.get_ui_settings()
        self.resize(
            self.ui_settings["forward_dialog_width"],
            420
        )

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        self.info_label = QLabel(self.language.text("forward.info"))
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumWidth(0)
        self.info_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed
        )
        self.main_layout.addWidget(self.info_label)

        self.calibration_source_label = None
        if self.file_path:
            self.calibration_source_label = QLabel()
            self.calibration_source_label.setMinimumWidth(0)
            self.calibration_source_label.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed
            )
            self.calibration_source_label.setToolTip(
                self.language.text(
                    "forward.calibration_source",
                    file_path=self.file_path
                )
            )
            self.main_layout.addWidget(self.calibration_source_label)
            self.update_calibration_source_label()

        self.fixed_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )

        self.input_group = QGroupBox(
            self.language.text("forward.inputs.group")
        )
        self.input_layout = QGridLayout(self.input_group)
        self.input_layout.setVerticalSpacing(7)
        self.input_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.input_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.input_layout.addWidget(
            QLabel(self.language.text("forward.column.neuron")), 0, 0
        )
        self.input_layout.addWidget(
            QLabel(self.language.text("forward.column.raw_value")), 0, 1
        )
        self.input_layout.addWidget(
            QLabel(self.language.text("forward.column.internal_x")), 0, 2
        )
        self.input_layout.addWidget(
            QLabel(self.language.text("forward.column.scaling")), 0, 3
        )
        self.input_layout.addWidget(
            QLabel(self.language.text("forward.column.allowed_range")), 0, 4
        )
        self.input_layout.addWidget(
            QLabel(self.language.text("forward.column.slider")), 0, 5
        )

        for row, mapping in enumerate(self.input_columns, start=1):
            self.input_layout.setRowMinimumHeight(row, 22)
            is_binary = mapping.get("data_type") == "binary"
            unit = str(mapping.get("unit", "")).strip()

            try:
                raw_value = TrainingDataIO.unscale_value(
                    mapping["neuron"].input_value,
                    mapping["calibration"],
                    self.language.text
                )
            except (TypeError, ValueError):
                raw_value = 0.0

            if is_binary:
                input_widget = BinaryToggleButton(
                    self.language, raw_value > 0.5
                )
                minimum, maximum = 0.0, 1.0
                experimental_widget = CompactDoubleSpinBox()
                experimental_widget.setRange(0.0, 1.0)
                experimental_widget.setDecimals(4)
                experimental_widget.setSingleStep(0.01)
                experimental_widget.setKeyboardTracking(False)
                experimental_widget.setFont(self.fixed_font)
                experimental_widget.setValue(max(0.0, min(1.0, raw_value)))
                raw_stack = QStackedWidget()
                raw_stack.setFixedHeight(20)
                raw_stack.addWidget(input_widget)
                raw_stack.addWidget(experimental_widget)

                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setMinimumWidth(150)
                slider.setRange(0, 1000)
                slider_stack = QStackedWidget()
                slider_stack.setFixedHeight(20)
                empty_slider_label = QLabel("–")
                empty_slider_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                slider_stack.addWidget(empty_slider_label)
                slider_stack.addWidget(slider)
                raw_display_widget = raw_stack
                slider_display_widget = slider_stack
            else:
                experimental_widget = None
                raw_stack = None
                slider_stack = None
                input_widget = CompactDoubleSpinBox()
                minimum, maximum = self.training_range(
                    mapping["column_index"]
                )
                input_widget.setRange(minimum, maximum)
                input_widget.setDecimals(10)
                input_widget.setKeyboardTracking(False)
                input_widget.setSingleStep(
                    self.training_step(mapping["column_index"])
                )
                input_widget.setFont(self.fixed_font)
                if unit:
                    input_widget.setSuffix(f" {unit}")
                input_widget.setValue(raw_value)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setMinimumWidth(150)
                slider_steps = 1000 if maximum > minimum else 0
                slider.setRange(0, slider_steps)
                slider.setEnabled(slider_steps > 0)
                raw_display_widget = input_widget
                slider_display_widget = slider

            internal_label = QLabel()
            internal_label.setFont(self.fixed_font)
            calibration_label = QLabel(
                self.format_calibration(mapping["calibration"])
            )
            range_label = QLabel(
                self.language.text(
                    "forward.allowed_range",
                    minimum=format_number(minimum, 7) if not is_binary else "0",
                    maximum=format_number(maximum, 7) if not is_binary else "1"
                )
            )
            range_label.setFont(self.fixed_font)

            self.input_layout.addWidget(
                QLabel(mapping["neuron"].name), row, 0
            )
            self.input_layout.addWidget(raw_display_widget, row, 1)
            self.input_layout.addWidget(internal_label, row, 2)
            self.input_layout.addWidget(calibration_label, row, 3)
            self.input_layout.addWidget(range_label, row, 4)
            self.input_layout.addWidget(slider_display_widget, row, 5)

            widget_data = {
                    "mapping": mapping,
                    "input_widget": input_widget,
                    "is_binary": is_binary,
                    "internal_label": internal_label,
                    "slider": slider,
                    "experimental_widget": experimental_widget,
                    "raw_stack": raw_stack,
                    "slider_stack": slider_stack,
                    "minimum": minimum,
                    "maximum": maximum
                }
            self.input_widgets.append(widget_data)

            if is_binary:
                input_widget.toggled.connect(self.inputs_changed)
                experimental_widget.valueChanged.connect(self.inputs_changed)
                experimental_widget.editingFinished.connect(self.inputs_changed)
                experimental_widget.valueChanged.connect(
                    lambda value, data=widget_data:
                    self.sync_slider_from_value(data, value)
                )
                slider.valueChanged.connect(
                    lambda value, data=widget_data:
                    self.slider_value_changed(data, value)
                )
                self.sync_slider_from_value(widget_data, raw_value)
            else:
                input_widget.valueChanged.connect(self.inputs_changed)
                input_widget.editingFinished.connect(self.inputs_changed)
                input_widget.valueChanged.connect(
                    lambda value, data=widget_data:
                    self.sync_slider_from_value(data, value)
                )
                slider.valueChanged.connect(
                    lambda value, data=widget_data:
                    self.slider_value_changed(data, value)
                )
                self.sync_slider_from_value(widget_data, raw_value)

        self.main_layout.addWidget(self.input_group)

        self.array_group = QGroupBox(
            self.language.text("forward.array.group")
        )
        self.array_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.array_layout = QGridLayout(self.array_group)
        self.array_layout.setSpacing(6)
        self.array_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.array_group.setVisible(False)
        self.main_layout.addWidget(self.array_group)

        self.output_group = QGroupBox(
            self.language.text("forward.outputs.group")
        )
        self.output_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.output_layout = QGridLayout(self.output_group)
        self.output_layout.setVerticalSpacing(6)
        self.output_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.output_layout.addWidget(
            QLabel(self.language.text("forward.column.neuron")), 0, 0
        )
        self.output_layout.addWidget(
            QLabel(self.language.text("forward.column.raw_result")), 0, 1
        )
        self.output_layout.addWidget(
            QLabel(self.language.text("forward.column.internal_y")), 0, 2
        )
        self.output_layout.addWidget(
            QLabel(self.language.text("forward.column.scaling")), 0, 3
        )
        self.output_layout.addWidget(
            QLabel(self.language.text("forward.column.allowed_range")), 0, 4
        )
        self.output_layout.addWidget(
            self.create_quality_header(), 0, 5
        )

        for row, mapping in enumerate(self.output_columns, start=1):
            self.output_layout.setRowMinimumHeight(row, 20)
            is_binary = mapping.get("data_type") == "binary"
            minimum, maximum = (
                (0.0, 1.0)
                if is_binary
                else self.training_range(mapping["column_index"])
            )
            internal_label = QLabel("–")
            internal_label.setFont(self.fixed_font)
            raw_label = QLabel("–")
            raw_label.setFont(self.fixed_font)
            calibration_label = QLabel(
                self.format_calibration(mapping["calibration"])
            )
            state_label = BinaryStateLabel(self.language) if is_binary else None
            output_bar = AnalogOutputBar(
                self.language, minimum, maximum
            )
            if is_binary:
                display_stack = QStackedWidget()
                display_stack.setFixedHeight(18)
                display_stack.addWidget(state_label)
                display_stack.addWidget(output_bar)
                display_widget = display_stack
            else:
                display_stack = None
                display_widget = output_bar
            quality_led = QLabel()
            quality_led.setFixedSize(14, 14)
            quality_led.setToolTip(
                self.language.text("forward.quality.unavailable")
            )
            quality_led.setStyleSheet(
                "QLabel { background:#a5abb0; border:1px solid #747a80; "
                "border-radius:7px; }"
            )
            quality_led.setVisible(False)
            display_container = QWidget()
            display_container_layout = QHBoxLayout(display_container)
            display_container_layout.setContentsMargins(0, 0, 0, 0)
            display_container_layout.setSpacing(6)
            display_container_layout.addWidget(quality_led)
            display_container_layout.addWidget(display_widget, 1)
            range_label = QLabel(
                self.language.text(
                    "forward.allowed_range",
                    minimum=format_number(minimum, 4),
                    maximum=format_number(maximum, 4)
                )
            )
            range_label.setFont(self.fixed_font)

            self.output_layout.addWidget(
                QLabel(mapping["neuron"].name), row, 0
            )
            self.output_layout.addWidget(raw_label, row, 1)
            self.output_layout.addWidget(internal_label, row, 2)
            self.output_layout.addWidget(calibration_label, row, 3)
            self.output_layout.addWidget(range_label, row, 4)
            self.output_layout.addWidget(display_container, row, 5)

            self.output_widgets.append(
                {
                    "mapping": mapping,
                    "internal_label": internal_label,
                    "raw_label": raw_label,
                    "display_widget": display_widget,
                    "display_stack": display_stack,
                    "state_label": state_label,
                    "output_bar": output_bar,
                    "quality_led": quality_led,
                    "is_binary": is_binary
                }
            )

        self.apply_shared_column_layout(self.input_layout)
        self.apply_shared_column_layout(self.output_layout)

        self.main_layout.addWidget(self.output_group)

        self.status_label = QLabel(
            self.language.text("forward.status.not_calculated")
        )
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed
        )
        self.main_layout.addWidget(self.status_label)

        self.experimental_info = QLabel(
            self.language.text("forward.experimental.info")
        )
        self.experimental_info.setWordWrap(True)
        self.experimental_info.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed
        )
        self.experimental_info.setStyleSheet(
            "QLabel { background: #fff3cd; border: 1px solid #d6b656; "
            "border-radius: 5px; padding: 6px; }"
        )
        self.experimental_info.setVisible(False)
        self.main_layout.addWidget(self.experimental_info)

        self.bottom_layout = QHBoxLayout()
        self.description_button = QPushButton(
            self.language.text("forward.button.description")
        )
        self.test_data_button = QPushButton(
            self.language.text("forward.button.test_data")
        )
        self.description_button.clicked.connect(self.show_description)
        self.test_data_button.clicked.connect(self.show_test_results)
        self.binary_view_button = QPushButton()
        self.binary_view_button.clicked.connect(
            self.toggle_binary_view
        )
        self.binary_view_button.setVisible(self.has_binary_columns)
        self.update_binary_view_button()
        self.array_view_button = QPushButton(
            self.language.text("forward.button.show_array")
        )
        self.array_view_button.setVisible(bool(self.array_buttons))
        self.array_view_button.clicked.connect(self.toggle_array_view)
        self.graphical_experiment_button = QPushButton(
            self.language.text("forward.button.graphical_experiment")
        )
        self.graphical_experiment_button.clicked.connect(
            self.open_graphical_experiment
        )
        self.bottom_layout.addWidget(self.description_button)
        self.bottom_layout.addWidget(self.test_data_button)
        self.bottom_layout.addWidget(self.binary_view_button)
        self.bottom_layout.addWidget(self.array_view_button)
        self.bottom_layout.addWidget(self.graphical_experiment_button)
        self.bottom_layout.addStretch(1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.language.text("common.close"))
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setAutoDefault(False)
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setDefault(False)
        self.button_box.rejected.connect(self.reject)
        self.bottom_layout.addWidget(self.button_box)
        self.main_layout.addLayout(self.bottom_layout)

        self.quality_reference = None
        self.rebuild_array_group()
        self.update_input_previews()
        self.calculate()
        self.schedule_fit_window()

    def create_quality_header(self):
        """Ergänzt die bestehende Anzeigespalte um die LED-Erklärung."""

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(self.language.text("forward.column.display")))
        self.binary_led_info_button = QPushButton("i")
        self.binary_led_info_button.setFixedSize(20, 20)
        self.binary_led_info_button.setVisible(False)
        self.binary_led_info_button.clicked.connect(self.show_quality_information)
        layout.addWidget(self.binary_led_info_button)
        layout.addStretch(1)
        return widget

    def show_quality_information(self):
        german = str(getattr(self.language, "current_language", "de")).lower().startswith("de")
        QMessageBox.information(
            self,
            "LED bei binären Ausgängen" if german else "LED for binary outputs",
            (
                "Die LED wird nur in der Zwischenwertansicht angezeigt.\n\n"
                "Rot: Der Ausgang wird als 0 (Aus) interpretiert.\n"
                "Grün: Der Ausgang wird als 1 (Ein) interpretiert.\n"
                "Die Umschaltung erfolgt bei einem internen Wert von 0,5.\n\n"
                "Die LED bewertet nicht, ob das Ergebnis richtig oder falsch ist."
                if german else
                "The LED is shown only in the intermediate-value view.\n\n"
                "Red: The output is interpreted as 0 (Off).\n"
                "Green: The output is interpreted as 1 (On).\n"
                "The threshold is an internal value of 0.5.\n\n"
                "The LED does not indicate whether the result is correct or incorrect."
            ),
        )

    def build_quality_reference(self):
        """Bereitet normierte Trainingspunkte für die LED-Einordnung vor."""

        if len(self.records) < 3 or not self.input_columns:
            return None
        try:
            ranges = []
            for mapping in self.input_columns:
                values = [
                    float(record[mapping["column_index"]])
                    for record in self.records
                ]
                ranges.append((min(values), max(values)))
            vectors = []
            for record in self.records:
                vector = []
                for mapping, (minimum, maximum) in zip(
                    self.input_columns, ranges
                ):
                    value = float(record[mapping["column_index"]])
                    span = maximum - minimum
                    vector.append(
                        (value - minimum) / span if span > 1e-12 else 0.0
                    )
                vectors.append(vector)
        except (IndexError, KeyError, TypeError, ValueError):
            return None

        nearest_spacings = []
        for index, vector in enumerate(vectors):
            distances = [
                math.sqrt(
                    sum((left - right) ** 2 for left, right in zip(vector, other))
                    / max(1, len(vector))
                )
                for other_index, other in enumerate(vectors)
                if other_index != index
            ]
            positive = [distance for distance in distances if distance > 1e-12]
            if positive:
                nearest_spacings.append(min(positive))
        nearest_spacings.sort()
        typical_spacing = (
            nearest_spacings[len(nearest_spacings) // 2]
            if nearest_spacings else 0.05
        )
        return {
            "ranges": ranges,
            "vectors": vectors,
            "typical_spacing": max(0.02, typical_spacing),
        }

    def current_quality_context(self):
        reference = self.quality_reference
        if reference is None:
            return None
        try:
            current_vector = []
            for widget_data, (minimum, maximum) in zip(
                self.input_widgets, reference["ranges"]
            ):
                value = float(self.input_value(widget_data))
                span = maximum - minimum
                current_vector.append(
                    (value - minimum) / span if span > 1e-12 else 0.0
                )
            distances = []
            for index, vector in enumerate(reference["vectors"]):
                distance = math.sqrt(
                    sum(
                        (left - right) ** 2
                        for left, right in zip(current_vector, vector)
                    ) / max(1, len(vector))
                )
                distances.append((distance, index))
            distances.sort()
            return distances
        except (TypeError, ValueError):
            return None

    def update_output_quality(self, widget_data, raw_value, distances):
        """Bewertet die Datenstützung eines einzelnen Outputs kompakt."""

        led = widget_data["quality_led"]
        state = "gray"
        record_number = "–"
        if distances and self.quality_reference is not None:
            mapping = widget_data["mapping"]
            try:
                output_values = [
                    float(record[mapping["column_index"]])
                    for record in self.records
                ]
                nearest_distance, nearest_index = distances[0]
                record_number = str(nearest_index + 1)
                neighbors = distances[:min(5, len(distances))]
                if nearest_distance <= 1e-12:
                    exact = [item for item in neighbors if item[0] <= 1e-12]
                    weights = [(1.0, index) for _distance, index in exact]
                else:
                    weights = [
                        (1.0 / (distance + 0.02), index)
                        for distance, index in neighbors
                    ]
                weight_sum = sum(weight for weight, _index in weights)
                local_value = sum(
                    weight * output_values[index]
                    for weight, index in weights
                ) / max(1e-12, weight_sum)
                local_values = [output_values[index] for _weight, index in weights]
                output_minimum = min(output_values)
                output_maximum = max(output_values)
                output_span = output_maximum - output_minimum
                output_scale = max(
                    output_span,
                    max(abs(output_minimum), abs(output_maximum), 1.0) * 0.1,
                )
                local_spread = (
                    max(local_values) - min(local_values)
                ) / output_scale
                agreement = abs(float(raw_value) - local_value) / output_scale
                typical = self.quality_reference["typical_spacing"]
                green_distance = max(0.08, typical * 1.5)
                yellow_distance = max(0.25, typical * 3.0)
                within_known_range = (
                    output_minimum - output_scale * 0.1
                    <= float(raw_value)
                    <= output_maximum + output_scale * 0.1
                )
                if (
                    nearest_distance <= green_distance
                    and agreement <= max(0.12, local_spread * 1.5)
                    and within_known_range
                ):
                    state = "green"
                elif (
                    nearest_distance <= yellow_distance
                    and agreement <= max(0.30, local_spread * 2.5 + 0.05)
                    and within_known_range
                ):
                    state = "yellow"
                else:
                    state = "red"
            except (IndexError, KeyError, TypeError, ValueError):
                state = "gray"

        colors = {
            "green": ("#00c853", "#008c3a"),
            "yellow": ("#ffd600", "#b39600"),
            "red": ("#ff1744", "#b21030"),
            "gray": ("#a5abb0", "#747a80"),
        }
        background, border = colors[state]
        led.setStyleSheet(
            "QLabel { "
            f"background:{background}; border:1px solid {border}; "
            "border-radius:7px; }"
        )
        led.setToolTip(
            self.language.text(
                f"forward.quality.{state}",
                record=record_number,
            )
        )

    def update_calibration_source_label(self):
        """Kürzt einen langen Datenpfad mittig auf die sichtbare Breite."""

        if self.calibration_source_label is None:
            return

        full_text = self.language.text(
            "forward.calibration_source",
            file_path=self.file_path
        )
        available_width = max(200, self.width() - 36)
        self.calibration_source_label.setText(
            self.calibration_source_label.fontMetrics().elidedText(
                full_text,
                Qt.TextElideMode.ElideMiddle,
                available_width
            )
        )

    def update_compact_text_heights(self):
        """Begrenzt Hinweiszeilen auf ihre bei aktueller Breite nötige Höhe."""

        available_width = max(200, self.width() - 24)
        for label in (
            getattr(self, "info_label", None),
            getattr(self, "status_label", None),
            getattr(self, "experimental_info", None),
        ):
            if label is None or not label.isVisible():
                continue
            margins = label.contentsMargins()
            text_width = max(
                1,
                available_width - margins.left() - margins.right()
            )
            required_height = label.fontMetrics().boundingRect(
                0,
                0,
                text_width,
                10000,
                Qt.TextFlag.TextWordWrap,
                label.text()
            ).height() + margins.top() + margins.bottom()
            if label is getattr(self, "experimental_info", None):
                required_height += 14
            label.setFixedHeight(
                max(label.fontMetrics().height(), required_height)
            )

        calibration_label = getattr(
            self,
            "calibration_source_label",
            None
        )
        if calibration_label is not None:
            calibration_label.setFixedHeight(
                calibration_label.sizeHint().height()
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_calibration_source_label()
        self.update_compact_text_heights()

    def done(self, result):
        """Merkt sich die Breite; die Höhe folgt stets dem Inhalt."""

        if not self.isMaximized() and not self.isFullScreen():
            self.ui_settings["forward_dialog_width"] = self.width()
            try:
                Settings.save_ui_settings(self.ui_settings)
            except OSError:
                pass
        controller = getattr(self, "array_paint_controller", None)
        if controller is not None:
            controller.deactivate()
        super().done(result)

    def rebuild_array_group(self):
        """Baut die Rasterfelder aus der aktuellen Definition neu auf."""

        while self.array_layout.count():
            item = self.array_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.array_buttons = {}
        if not hasattr(self, "array_paint_controller"):
            self.array_paint_controller = BinaryArrayPaintController(self)
        if self.input_array is not None:
            columns = int(self.input_array.get("columns", 0))
            mappings_by_column = {
                mapping["column_index"]: mapping
                for mapping in self.input_columns
            }
            widgets_by_column = {
                data["mapping"]["column_index"]: data
                for data in self.input_widgets
            }
            for position, column_index in enumerate(
                self.input_array.get("column_indices", [])
            ):
                mapping = mappings_by_column.get(column_index)
                widget_data = widgets_by_column.get(column_index)
                if mapping is None or widget_data is None:
                    continue
                button = QPushButton()
                button.setCheckable(True)
                button.setFixedSize(58, 58)
                button.setToolTip(mapping["neuron"].name)
                button.toggled.connect(
                    lambda checked, data=widget_data:
                    self.array_cell_toggled(data, checked)
                )
                self.array_layout.addWidget(
                    button, position // max(1, columns), position % max(1, columns)
                )
                self.array_buttons[column_index] = button
        self.array_paint_controller.set_buttons(self.array_buttons.values())
        self.array_view_button.setVisible(bool(self.array_buttons))
        if not self.array_buttons:
            self.array_view_active = False
            self.array_group.setVisible(False)
            self.input_group.setVisible(True)
        self.update_array_buttons()

    def style_array_button(self, button, checked):
        button.setText("")
        button.setStyleSheet(
            "QPushButton { border: 1px solid #8c969f; border-radius: 5px; "
            f"background: {self.color_settings.get('binary_array_on', '#242424') if checked else self.color_settings.get('binary_array_off', '#ffffff')}; "
            f"color: {self.color_settings.get('binary_array_off', '#ffffff') if checked else self.color_settings.get('binary_array_on', '#242424')}; "
            "font-size: 18px; } QPushButton:hover { border: 2px solid #4f788f; }"
        )

    def array_cell_toggled(self, widget_data, checked):
        """Überträgt einen Rasterklick auf den vorhandenen Binärschalter."""

        widget = widget_data["input_widget"]
        checked = bool(checked)

        if self.experimental_binary_mode:
            # Das Raster bleibt auch in der Zwischenwertansicht eine binäre
            # Eingabe. Deshalb müssen dort sowohl der unsichtbare
            # Ein/Aus-Schalter als auch das aktive Zwischenwertfeld folgen.
            widget.blockSignals(True)
            widget.setChecked(checked)
            widget.blockSignals(False)
            widget_data["experimental_widget"].setValue(
                1.0 if checked else 0.0
            )
        elif widget.isChecked() != checked:
            widget.setChecked(checked)

        button = self.array_buttons.get(widget_data["mapping"]["column_index"])
        if button is not None:
            self.style_array_button(button, checked)

    def update_array_buttons(self):
        for widget_data in self.input_widgets:
            column_index = widget_data["mapping"]["column_index"]
            button = self.array_buttons.get(column_index)
            if button is None:
                continue
            checked = widget_data["input_widget"].isChecked()
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
            self.style_array_button(button, checked)

    def toggle_array_view(self):
        """Wechselt zwischen tabellarischer Eingabe und 2D-Raster."""

        self.array_view_active = not self.array_view_active
        self.input_group.setVisible(not self.array_view_active)
        self.array_group.setVisible(self.array_view_active)
        self.array_view_button.setText(
            self.language.text(
                "forward.button.show_list"
                if self.array_view_active
                else "forward.button.show_array"
            )
        )
        self.update_array_buttons()
        self.input_layout.invalidate()
        self.input_group.adjustSize()
        self.main_layout.activate()
        self.schedule_fit_window()

    def schedule_fit_window(self):
        """Passt die normale Fensterhöhe nach einem Ansichtswechsel an."""

        QTimer.singleShot(0, self.fit_window_to_content)

    def fit_window_to_content(self):
        if self.isMaximized() or self.isFullScreen():
            return
        self.update_compact_text_heights()
        self.main_layout.activate()
        for _pass in range(4):
            self.compact_visible_grid_groups()
            self.main_layout.activate()
        requested_height = self.sizeHint().height()
        screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            requested_height = min(
                requested_height,
                max(420, screen.availableGeometry().height() - 60),
            )
        self.resize(self.width(), requested_height)

    def compact_visible_grid_groups(self):
        """Beendet Tabellen-Gruppen direkt nach ihrer letzten sichtbaren Zeile."""

        for group, layout in (
            (self.input_group, self.input_layout),
            (self.output_group, self.output_layout),
        ):
            if not group.isVisible():
                continue
            layout.activate()
            visible_rows = []
            for row in range(layout.rowCount()):
                widgets = [
                    item.widget()
                    for column in range(layout.columnCount())
                    for item in (layout.itemAtPosition(row, column),)
                    if (
                        item is not None
                        and item.widget() is not None
                        and item.widget().isVisible()
                    )
                ]
                if widgets:
                    visible_rows.append((row, widgets))

            if not visible_rows:
                continue

            first_widgets = visible_rows[0][1]
            content_top = min(
                widget.geometry().top()
                for widget in first_widgets
            )
            row_heights = []
            for row, widgets in visible_rows:
                row_heights.append(
                    max(
                        layout.rowMinimumHeight(row),
                        *(
                            max(
                                widget.minimumHeight(),
                                widget.sizeHint().height()
                            )
                            for widget in widgets
                        )
                    )
                )

            desired_height = (
                content_top
                + sum(row_heights)
                + layout.verticalSpacing() * (len(row_heights) - 1)
                + layout.contentsMargins().bottom()
                + 1
            )
            group.setFixedHeight(
                desired_height
            )
            layout.invalidate()
            layout.setGeometry(group.contentsRect())
            final_widgets = [
                widget
                for _row, widgets in visible_rows
                for widget in widgets
            ]
            bottom_clearance = 4 if group is self.output_group else 1
            group.setFixedHeight(
                max(widget.geometry().bottom() for widget in final_widgets)
                + layout.contentsMargins().bottom()
                + bottom_clearance
            )

    def apply_shared_column_layout(self, layout):
        """Verwendet in Ein- und Ausgabe dasselbe horizontale Spaltenraster."""

        for column, width in enumerate(self.SHARED_COLUMN_WIDTHS):
            layout.setColumnMinimumWidth(column, width)
            layout.setColumnStretch(column, 0)
            for row in range(layout.rowCount()):
                item = layout.itemAtPosition(row, column)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.setFixedWidth(width)

        layout.setColumnMinimumWidth(5, self.VALUE_COLUMN_MINIMUM)
        layout.setColumnStretch(5, 1)
        for row in range(layout.rowCount()):
            item = layout.itemAtPosition(row, 5)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setMinimumWidth(self.VALUE_COLUMN_MINIMUM)
                widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed
                )

    def training_step(self, column_index):
        """Leitet eine sinnvolle Pfeilschrittweite aus den Trainingswerten ab."""

        values = sorted({
            float(record[column_index])
            for record in self.records
            if (
                isinstance(record, (list, tuple))
                and column_index < len(record)
                and isinstance(record[column_index], (int, float))
                and not isinstance(record[column_index], bool)
                and math.isfinite(float(record[column_index]))
            )
        })
        if values and min(values) >= 0.0 and all(value.is_integer() for value in values):
            return 1.0
        differences = [
            second - first
            for first, second in zip(values, values[1:])
            if second > first
        ]
        if differences:
            return min(differences)
        if values:
            magnitude = abs(values[0])
            return magnitude / 10.0 if magnitude > 0.0 else 0.1
        return 0.1

    def sync_slider_from_value(self, widget_data, value):
        """Hält den analogen Schieberegler mit dem Zahlenfeld synchron."""

        slider = widget_data.get("slider")
        minimum = widget_data["minimum"]
        maximum = widget_data["maximum"]
        if slider is None or maximum <= minimum:
            return
        position = round(
            (float(value) - minimum) / (maximum - minimum) * slider.maximum()
        )
        slider.blockSignals(True)
        slider.setValue(max(slider.minimum(), min(slider.maximum(), position)))
        slider.blockSignals(False)

    def slider_value_changed(self, widget_data, position):
        """Übernimmt eine Reglerbewegung sofort in die Vorwärtsrechnung."""

        slider = widget_data["slider"]
        minimum = widget_data["minimum"]
        maximum = widget_data["maximum"]
        if slider.maximum() <= 0:
            return
        value = minimum + (
            position / slider.maximum()
        ) * (maximum - minimum)
        target_widget = (
            widget_data["experimental_widget"]
            if widget_data["is_binary"]
            else widget_data["input_widget"]
        )
        target_widget.setValue(value)

    def show_description(self):
        """Zeigt die Beschreibung des aktuellen Projekts."""

        parent = self.parent()
        if parent is not None and hasattr(parent, "open_project_description_dialog"):
            parent.open_project_description_dialog()

    def open_graphical_experiment(self):
        """Öffnet das getrennte, frei gestaltbare Experimentierfenster."""

        initial_values = {
            widget_data["mapping"]["neuron"].id: self.input_value(widget_data)
            for widget_data in self.input_widgets
        }
        dialog = GraphicalExperimentDialog(
            self.network,
            self.input_columns,
            self.output_columns,
            records=self.records,
            file_path=self.file_path,
            input_array=self.input_array,
            color_settings=self.color_settings,
            initial_input_values=initial_values,
            language_manager=self.language,
            parent=self,
        )
        dialog.exec()
        self.apply_input_values(dialog.current_input_values())

    def show_test_results(self):
        """Öffnet die Auswertung mit den aktuellen Trainingsdaten."""

        parent = self.parent()
        if parent is not None and hasattr(parent, "test_network_with_training_data"):
            parent.test_network_with_training_data()
            self.calculate()

    def update_binary_view_button(self):
        """Beschriftet die Umschaltung passend zur nächsten Ansicht."""

        self.binary_view_button.setText(
            self.language.text(
                "forward.button.show_binary"
                if self.experimental_binary_mode
                else "forward.button.show_intermediate"
            )
        )

    def toggle_binary_view(self):
        """Wechselt nur die Anzeige binärer Ausgänge."""

        self.experimental_binary_mode = not self.experimental_binary_mode
        page = 1 if self.experimental_binary_mode else 0
        for widget_data in self.output_widgets:
            if widget_data["is_binary"]:
                widget_data["display_stack"].setCurrentIndex(page)
                widget_data["quality_led"].setVisible(
                    self.experimental_binary_mode
                )
        self.binary_led_info_button.setVisible(self.experimental_binary_mode)
        self.experimental_info.setVisible(False)
        self.update_binary_view_button()

    def training_range(self, column_index):
        """Liefert die geschlossenen Rohwertgrenzen einer Trainingsspalte."""

        values = [
            float(record[column_index])
            for record in self.records
            if (
                isinstance(record, (list, tuple))
                and column_index < len(record)
                and isinstance(record[column_index], (int, float))
                and not isinstance(record[column_index], bool)
                and math.isfinite(float(record[column_index]))
            )
        ]
        if values:
            return min(values), max(values)
        return -1.0e12, 1.0e12

    def format_calibration(self, calibration):
        calibration = TrainingDataIO.normalize_calibration(calibration)
        mode = calibration["mode"]

        if mode == "minmax_0_1":
            return "0 … 1"
        if mode == "minmax_minus1_1":
            return "−1 … +1"
        if mode == "standard":
            return self.language.text("forward.scaling.standardized")
        return self.language.text("forward.scaling.none")

    def update_input_previews(self):
        for widget_data in self.input_widgets:
            mapping = widget_data["mapping"]

            try:
                internal_value = TrainingDataIO.scale_value(
                    self.input_value(widget_data),
                    mapping["calibration"],
                    self.language.text
                )
                text = format_number(internal_value, 7)
            except (TypeError, ValueError):
                text = self.language.text("forward.value.invalid")

            widget_data["internal_label"].setText(text)
        self.update_array_buttons()

    def input_value(self, widget_data):
        widget = widget_data["input_widget"]
        return (
            widget.numeric_value()
            if widget_data["is_binary"]
            else widget.value()
        )

    def current_input_values(self):
        """Liefert die aktuellen Experimentwerte in ihren Rohwerteinheiten."""

        return {
            data["mapping"]["neuron"].id: float(self.input_value(data))
            for data in self.input_widgets
        }

    def apply_input_values(self, values):
        """Übernimmt Eingaben aus dem grafischen Experiment in dieses Fenster."""

        values = dict(values or {})
        for data in self.input_widgets:
            neuron_id = data["mapping"]["neuron"].id
            if neuron_id not in values:
                continue
            value = float(values[neuron_id])
            if data["is_binary"]:
                checked = value > 0.5
                data["input_widget"].blockSignals(True)
                data["input_widget"].setChecked(checked)
                data["input_widget"].blockSignals(False)
                data["experimental_widget"].blockSignals(True)
                data["experimental_widget"].setValue(1.0 if checked else 0.0)
                data["experimental_widget"].blockSignals(False)
                value = 1.0 if checked else 0.0
            else:
                value = max(data["minimum"], min(data["maximum"], value))
                data["input_widget"].blockSignals(True)
                data["input_widget"].setValue(value)
                data["input_widget"].blockSignals(False)
            self.sync_slider_from_value(data, value)
        self.update_input_previews()
        self.calculate()

    def inputs_changed(self, *_):
        self.update_input_previews()
        self.calculate()

    def calculate(self, *_):
        try:
            self.network.reset_runtime_values()

            for widget_data in self.input_widgets:
                mapping = widget_data["mapping"]
                neuron = mapping["neuron"]
                neuron.input_value = TrainingDataIO.scale_value(
                    self.input_value(widget_data),
                    mapping["calibration"],
                    self.language.text
                )
                neuron.set_external_input_value(
                    self.input_value(widget_data),
                    mapping["calibration"]["mode"] != "none",
                    unit=mapping.get("unit", ""),
                    is_binary=mapping.get("data_type") == "binary"
                )
                neuron.update()

            self.network.forward_pass()

            for widget_data in self.output_widgets:
                mapping = widget_data["mapping"]
                internal_value = mapping["neuron"].output_value
                raw_value = TrainingDataIO.unscale_value(
                    internal_value,
                    mapping["calibration"],
                    self.language.text
                )
                widget_data["internal_label"].setText(
                    format_number(internal_value, 4)
                )
                widget_data["raw_label"].setText(
                    (
                        f"{format_number(raw_value, 4)} {mapping['unit']}"
                        if mapping.get("unit")
                        else format_number(raw_value, 4)
                    )
                )
                if widget_data["is_binary"]:
                    widget_data["state_label"].set_state(
                        internal_value > 0.5
                    )
                    active = internal_value >= 0.5
                    widget_data["quality_led"].setStyleSheet(
                        "QLabel { background:%s; border:1px solid %s; "
                        "border-radius:7px; }" % (
                            "#00c853" if active else "#d91e18",
                            "#008c3a" if active else "#9f1612",
                        )
                    )
                widget_data["output_bar"].set_result(raw_value)
                mapping["neuron"].set_external_output_values(
                    actual_value=raw_value,
                    is_raw=mapping["calibration"]["mode"] != "none",
                    unit=mapping.get("unit", ""),
                    is_binary=mapping.get("data_type") == "binary"
                )

        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("forward.message.title"),
                str(error)
            )
            return

        self.calculation_performed = True
        self.status_label.setText(
            self.language.text("forward.status.completed_unchanged")
        )
        self.calculation_updated.emit()
