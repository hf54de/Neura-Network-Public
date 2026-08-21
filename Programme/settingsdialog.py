# -------------------------------------------------------------------------------------------------
# Datei: settingsdialog.py
# Zweck: Stellt die Seiten und Bedienelemente der Programmeinstellungen bereit.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget
)
from colorpalette import choose_color


class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color_text, language_manager, parent=None):
        super().__init__(parent)
        self.language_manager = language_manager
        self.color_text = "#ffffff"
        self.setMinimumWidth(130)
        self.clicked.connect(self.choose_color)
        self.set_color(color_text, emit_signal=False)

    def set_color(self, color_text, emit_signal=True):
        color = QColor(color_text)

        if not color.isValid():
            return

        self.color_text = color.name().lower()
        text_color = (
            "#ffffff"
            if color.lightness() < 128
            else "#202020"
        )
        self.setText(self.color_text)
        self.setStyleSheet(
            f"background-color: {self.color_text}; "
            f"color: {text_color}; font-weight: bold; "
            "border: 1px solid #777; border-radius: 4px; padding: 5px;"
        )

        if emit_signal:
            self.color_changed.emit(
                self.color_text
            )

    def choose_color(self):
        color = choose_color(
            QColor(self.color_text),
            self,
            self.language_manager.text(
                "settings.color.choose"
            )
        )

        if color.isValid():
            self.set_color(
                color.name()
            )


class SettingsDialog(QDialog):
    """Zentrales Fenster für Projekt- und Programmeinstellungen."""

    preview_changed = Signal(object, object)

    DISPLAY_FIELDS = (
        ("show_weights", "settings.display.show_weights"),
        ("show_neuron_values", "settings.display.show_neuron_values"),
        (
            "show_activation_charts",
            "settings.display.show_activation_charts"
        ),
        (
            "show_io_value_fields",
            "settings.display.show_io_values"
        ),
        ("show_ports", "settings.display.show_ports"),
        ("show_neuron_names", "settings.display.show_neuron_names"),
        ("show_comments", "settings.display.show_comments"),
        (
            "visualize_weights",
            "settings.display.visualize_weights"
        )
    )

    COLOR_FIELDS = (
        ("input_header", "settings.color.input_header"),
        ("hidden_header", "settings.color.hidden_header"),
        ("output_header", "settings.color.output_header"),
        ("neuron_background", "settings.color.neuron_background"),
        ("input_port", "settings.color.input_port"),
        ("output_port", "settings.color.output_port"),
        ("positive_weight", "settings.color.positive_weight"),
        ("negative_weight", "settings.color.negative_weight"),
        ("neutral_weight", "settings.color.neutral_weight"),
        ("selection", "settings.color.selection"),
        ("comment_background", "settings.color.comment_background"),
        ("canvas_background", "settings.color.canvas_background"),
        ("binary_array_on", "settings.color.binary_array_on"),
        ("binary_array_off", "settings.color.binary_array_off")
    )

    PAGE_KEYS = (
        "display",
        "colors",
        "toolbar",
        "editor",
        "language"
    )

    def __init__(
        self,
        project_settings,
        project_defaults,
        ui_settings,
        ui_defaults,
        language_manager,
        initial_page="display",
        parent=None
    ):
        super().__init__(parent)

        self.loading = True
        self.base_project_settings = dict(project_settings)
        self.project_defaults = dict(project_defaults)
        self.base_ui_settings = dict(ui_settings)
        self.ui_defaults = dict(ui_defaults)
        self.language_manager = language_manager

        self.setWindowTitle(
            self.language_manager.text(
                "settings.window.title"
            )
        )
        self.setModal(True)
        self.resize(760, 560)

        main_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.setFixedWidth(185)
        self.category_list.addItems(
            [
                self.language_manager.text(
                    "settings.category.display"
                ),
                self.language_manager.text(
                    "settings.category.colors"
                ),
                self.language_manager.text(
                    "settings.category.toolbar"
                ),
                self.language_manager.text(
                    "settings.category.editor"
                ),
                self.language_manager.text(
                    "settings.category.language"
                )
            ]
        )
        content_layout.addWidget(self.category_list)

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)
        main_layout.addLayout(content_layout, 1)

        self.display_checks = {}
        self.color_buttons = {}
        self.create_display_page(project_settings, ui_settings)
        self.create_color_page(project_settings["colors"])
        self.create_toolbar_page(ui_settings)
        self.create_editor_page(ui_settings)
        self.create_language_page(ui_settings)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText(
            self.language_manager.text("common.ok")
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(
            self.language_manager.text("common.cancel")
        )
        self.default_button = QPushButton(
            self.language_manager.text(
                "settings.restore_page_defaults"
            )
        )
        self.button_box.addButton(
            self.default_button,
            QDialogButtonBox.ButtonRole.ResetRole
        )
        self.default_button.clicked.connect(
            self.restore_current_defaults
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.category_list.currentRowChanged.connect(
            self.pages.setCurrentIndex
        )
        initial_index = (
            self.PAGE_KEYS.index(initial_page)
            if initial_page in self.PAGE_KEYS
            else 0
        )
        self.category_list.setCurrentRow(initial_index)
        self.loading = False

    @staticmethod
    def create_page(title, scope_text):
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(title)
        heading_font = heading.font()
        heading_font.setPointSize(13)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)

        scope = QLabel(scope_text)
        scope.setWordWrap(True)
        scope.setStyleSheet(
            "color: #555; background: #eef4f8; "
            "border: 1px solid #ccdce7; border-radius: 4px; padding: 7px;"
        )
        layout.addWidget(scope)
        return page, layout

    def create_display_page(self, settings, ui_settings):
        page, layout = self.create_page(
            self.language_manager.text("settings.display.title"),
            self.language_manager.text("settings.display.scope")
        )
        group = QGroupBox(
            self.language_manager.text("settings.display.elements_group")
        )
        group_layout = QVBoxLayout(group)

        for key, text_key in self.DISPLAY_FIELDS:
            checkbox = QCheckBox(
                self.language_manager.text(text_key)
            )
            checkbox.setChecked(bool(settings[key]))
            checkbox.toggled.connect(self.emit_preview)
            self.display_checks[key] = checkbox
            group_layout.addWidget(checkbox)

        layout.addWidget(group)

        interface_group = QGroupBox(
            self.language_manager.text("settings.display.interface_group")
        )
        interface_layout = QVBoxLayout(
            interface_group
        )
        self.property_dock_visible = QCheckBox(
            self.language_manager.text(
                "settings.display.property_dock"
            )
        )
        self.property_dock_visible.setChecked(
            ui_settings["property_dock_visible"]
        )
        self.property_dock_visible.toggled.connect(
            self.emit_preview
        )
        interface_layout.addWidget(
            self.property_dock_visible
        )
        self.show_project_menu_previews = QCheckBox(
            self.language_manager.text(
                "settings.display.project_menu_previews"
            )
        )
        self.show_project_menu_previews.setChecked(
            ui_settings.get("show_project_menu_previews", True)
        )
        self.show_project_menu_previews.toggled.connect(self.emit_preview)
        interface_layout.addWidget(self.show_project_menu_previews)
        self.show_project_assistant = QCheckBox(
            self.language_manager.text(
                "settings.display.project_assistant"
            )
        )
        self.show_project_assistant.setChecked(
            ui_settings.get("show_project_assistant", True)
        )
        self.show_project_assistant.toggled.connect(self.emit_preview)
        interface_layout.addWidget(self.show_project_assistant)
        layout.addWidget(
            interface_group
        )
        layout.addStretch()
        self.pages.addWidget(page)

    def create_color_page(self, colors):
        page, layout = self.create_page(
            self.language_manager.text("settings.colors.title"),
            self.language_manager.text("settings.colors.scope")
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        form = QFormLayout(container)

        for key, text_key in self.COLOR_FIELDS:
            button = ColorButton(
                colors[key],
                self.language_manager
            )
            button.color_changed.connect(self.emit_preview)
            self.color_buttons[key] = button
            form.addRow(
                self.language_manager.text(text_key) + ":",
                button
            )

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        self.pages.addWidget(page)

    def create_toolbar_page(self, settings):
        page, layout = self.create_page(
            self.language_manager.text("settings.toolbar.title"),
            self.language_manager.text("settings.toolbar.scope")
        )
        group = QGroupBox(
            self.language_manager.text("settings.toolbar.group")
        )
        form = QFormLayout(group)

        self.toolbar_icon_size = QSpinBox()
        self.toolbar_icon_size.setRange(12, 36)
        self.toolbar_icon_size.setSuffix(" px")
        self.toolbar_icon_size.setValue(settings["toolbar_icon_size"])
        self.toolbar_icon_size.valueChanged.connect(self.emit_preview)

        self.toolbar_show_text = QCheckBox(
            self.language_manager.text("settings.toolbar.show_text")
        )
        self.toolbar_show_text.setChecked(settings["toolbar_show_text"])
        self.toolbar_show_text.toggled.connect(self.emit_preview)

        self.toolbar_auto_size = QCheckBox(
            self.language_manager.text("settings.toolbar.auto_size")
        )
        self.toolbar_auto_size.setChecked(settings["toolbar_auto_size"])
        self.toolbar_auto_size.toggled.connect(
            self.update_toolbar_dimension_controls
        )
        self.toolbar_auto_size.toggled.connect(self.emit_preview)

        self.toolbar_manual_hint = QLabel(
            self.language_manager.text("settings.toolbar.manual_hint")
        )
        self.toolbar_manual_hint.setWordWrap(True)
        self.toolbar_manual_hint.setStyleSheet("color: #666666;")

        self.toolbar_vertical_width = QSpinBox()
        self.toolbar_vertical_width.setRange(70, 160)
        self.toolbar_vertical_width.setSuffix(" px")
        self.toolbar_vertical_width.setValue(settings["toolbar_vertical_width"])
        self.toolbar_vertical_width.valueChanged.connect(self.emit_preview)

        self.toolbar_horizontal_height = QSpinBox()
        self.toolbar_horizontal_height.setRange(50, 100)
        self.toolbar_horizontal_height.setSuffix(" px")
        self.toolbar_horizontal_height.setValue(settings["toolbar_horizontal_height"])
        self.toolbar_horizontal_height.valueChanged.connect(self.emit_preview)

        self.toolbars_visible = QCheckBox(
            self.language_manager.text("settings.toolbar.visible")
        )
        self.toolbars_visible.setChecked(settings["toolbars_visible"])
        self.toolbars_visible.toggled.connect(self.emit_preview)

        form.addRow(
            self.language_manager.text("settings.toolbar.icon_size"),
            self.toolbar_icon_size
        )
        form.addRow("", self.toolbar_auto_size)
        form.addRow("", self.toolbar_manual_hint)
        form.addRow(
            self.language_manager.text("settings.toolbar.vertical_width"),
            self.toolbar_vertical_width
        )
        form.addRow(
            self.language_manager.text("settings.toolbar.horizontal_height"),
            self.toolbar_horizontal_height
        )
        form.addRow("", self.toolbar_show_text)
        form.addRow("", self.toolbars_visible)
        self.update_toolbar_dimension_controls()
        layout.addWidget(group)
        layout.addStretch()
        self.pages.addWidget(page)

    def update_toolbar_dimension_controls(self, _checked=None):
        """Sperrt manuelle Maße, solange die Bildschirmautomatik aktiv ist."""

        manual = not self.toolbar_auto_size.isChecked()
        self.toolbar_vertical_width.setEnabled(manual)
        self.toolbar_horizontal_height.setEnabled(manual)
        self.toolbar_manual_hint.setVisible(not manual)
        hint = self.language_manager.text("settings.toolbar.manual_hint")
        self.toolbar_vertical_width.setToolTip(hint if not manual else "")
        self.toolbar_horizontal_height.setToolTip(hint if not manual else "")

    def create_editor_page(self, settings):
        page, layout = self.create_page(
            self.language_manager.text("settings.editor.title"),
            self.language_manager.text("settings.editor.scope")
        )
        group = QGroupBox(
            self.language_manager.text("settings.editor.group")
        )
        form = QFormLayout(group)

        self.editor_scene_margin = QSpinBox()
        self.editor_scene_margin.setRange(20, 500)
        self.editor_scene_margin.setSuffix(" px")
        self.editor_scene_margin.setValue(settings["editor_scene_margin"])
        self.editor_scene_margin.valueChanged.connect(self.emit_preview)

        self.editor_zoom_step = QSpinBox()
        self.editor_zoom_step.setRange(5, 50)
        self.editor_zoom_step.setSuffix(" %")
        self.editor_zoom_step.setValue(
            settings["editor_zoom_step_percent"]
        )
        self.editor_zoom_step.valueChanged.connect(self.emit_preview)

        self.simplify_large_moves = QCheckBox(
            self.language_manager.text("settings.editor.simplify_large_moves")
        )
        self.simplify_large_moves.setChecked(settings["simplify_large_moves"])
        self.simplify_large_moves.toggled.connect(self.emit_preview)

        form.addRow(
            self.language_manager.text("settings.editor.scene_margin"),
            self.editor_scene_margin
        )
        form.addRow(
            self.language_manager.text("settings.editor.zoom_step"),
            self.editor_zoom_step
        )
        form.addRow("", self.simplify_large_moves)
        layout.addWidget(group)

        startup_group = QGroupBox(
            self.language_manager.text("settings.editor.startup_group")
        )
        startup_layout = QVBoxLayout(startup_group)
        self.show_startup_splash = QCheckBox(
            self.language_manager.text(
                "settings.editor.show_startup_splash"
            )
        )
        self.show_startup_splash.setChecked(
            settings["show_startup_splash"]
        )
        self.show_startup_splash.toggled.connect(self.emit_preview)
        startup_layout.addWidget(self.show_startup_splash)
        self.reopen_last_project = QCheckBox(
            self.language_manager.text(
                "settings.editor.reopen_last_project"
            )
        )
        self.reopen_last_project.setChecked(
            settings["reopen_last_project"]
        )
        self.reopen_last_project.toggled.connect(self.emit_preview)
        startup_layout.addWidget(self.reopen_last_project)
        layout.addWidget(startup_group)

        project_group = QGroupBox(
            self.language_manager.text("settings.editor.project_group")
        )
        project_layout = QHBoxLayout(project_group)
        self.project_directory = QLineEdit(
            str(settings.get("project_directory") or "")
        )
        self.project_directory.setReadOnly(True)
        self.project_directory.setPlaceholderText(
            self.language_manager.text("settings.editor.project_default")
        )
        self.project_directory.textChanged.connect(self.emit_preview)
        project_layout.addWidget(self.project_directory, 1)
        self.project_directory_button = QPushButton(
            self.language_manager.text("settings.editor.project_choose")
        )
        self.project_directory_button.clicked.connect(
            self.choose_project_directory
        )
        project_layout.addWidget(self.project_directory_button)
        layout.addWidget(project_group)
        layout.addStretch()
        self.pages.addWidget(page)

    def choose_project_directory(self):
        """Wählt den bevorzugten Projektordner im Windows-Dialog."""

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            self.language_manager.text(
                "settings.editor.project_choose_title"
            ),
            self.project_directory.text().strip(),
        )
        if selected_directory:
            self.project_directory.setText(selected_directory)

    def create_language_page(self, settings):
        page, layout = self.create_page(
            self.language_manager.text(
                "settings.language.title"
            ),
            self.language_manager.text(
                "settings.language.scope"
            )
        )
        group = QGroupBox(
            self.language_manager.text(
                "settings.language.group"
            )
        )
        form = QFormLayout(group)
        self.language_combo = QComboBox()

        for language_code, language_name in (
            self.language_manager.available_languages()
        ):
            self.language_combo.addItem(
                language_name,
                language_code
            )

        current_language = settings.get(
            "language",
            "en"
        )
        current_index = self.language_combo.findData(
            current_language
        )

        if current_index < 0:
            current_index = self.language_combo.findData(
                "en"
            )

        self.language_combo.setCurrentIndex(
            max(0, current_index)
        )
        self.language_combo.currentIndexChanged.connect(
            self.emit_preview
        )
        form.addRow(
            self.language_manager.text(
                "settings.language.label"
            ),
            self.language_combo
        )
        layout.addWidget(group)

        restart_note = QLabel(
            self.language_manager.text(
                "settings.language.restart"
            )
        )
        restart_note.setWordWrap(True)
        restart_note.setStyleSheet(
            "color: #555; padding: 6px 2px;"
        )
        layout.addWidget(restart_note)
        layout.addStretch()
        self.pages.addWidget(page)

    def project_settings(self):
        settings = dict(self.base_project_settings)

        for key, checkbox in self.display_checks.items():
            settings[key] = checkbox.isChecked()

        settings["colors"] = {
            key: button.color_text
            for key, button in self.color_buttons.items()
        }
        return settings

    def ui_settings(self):
        settings = dict(self.base_ui_settings)
        settings.update(
            {
                "toolbar_icon_size": self.toolbar_icon_size.value(),
                "toolbar_auto_size": self.toolbar_auto_size.isChecked(),
                "toolbar_vertical_width": self.toolbar_vertical_width.value(),
                "toolbar_horizontal_height": self.toolbar_horizontal_height.value(),
                "language": self.language_combo.currentData(),
                "toolbar_show_text": self.toolbar_show_text.isChecked(),
                "toolbars_visible": self.toolbars_visible.isChecked(),
                "property_dock_visible": (
                    self.property_dock_visible.isChecked()
                ),
                "project_workflow_visible": True,
                "reopen_last_project": (
                    self.reopen_last_project.isChecked()
                ),
                "show_startup_splash": (
                    self.show_startup_splash.isChecked()
                ),
                "project_directory": self.project_directory.text().strip(),
                "show_project_menu_previews": (
                    self.show_project_menu_previews.isChecked()
                ),
                "show_project_assistant": (
                    self.show_project_assistant.isChecked()
                ),
                "editor_scene_margin": self.editor_scene_margin.value(),
                "editor_zoom_step_percent": self.editor_zoom_step.value(),
                "simplify_large_moves": self.simplify_large_moves.isChecked()
            }
        )
        return settings

    def restore_current_defaults(self, _checked=False):
        page_index = self.category_list.currentRow()
        self.loading = True

        if page_index == 0:
            for key, checkbox in self.display_checks.items():
                checkbox.setChecked(bool(self.project_defaults[key]))
            self.property_dock_visible.setChecked(
                self.ui_defaults["property_dock_visible"]
            )
            self.show_project_menu_previews.setChecked(
                self.ui_defaults["show_project_menu_previews"]
            )
            self.show_project_assistant.setChecked(
                self.ui_defaults["show_project_assistant"]
            )
        elif page_index == 1:
            for key, button in self.color_buttons.items():
                button.set_color(
                    self.project_defaults["colors"][key],
                    emit_signal=False
                )
        elif page_index == 2:
            self.toolbar_icon_size.setValue(
                self.ui_defaults["toolbar_icon_size"]
            )
            self.toolbar_auto_size.setChecked(
                self.ui_defaults["toolbar_auto_size"]
            )
            self.toolbar_vertical_width.setValue(
                self.ui_defaults["toolbar_vertical_width"]
            )
            self.toolbar_horizontal_height.setValue(
                self.ui_defaults["toolbar_horizontal_height"]
            )
            self.toolbar_show_text.setChecked(
                self.ui_defaults["toolbar_show_text"]
            )
            self.toolbars_visible.setChecked(
                self.ui_defaults["toolbars_visible"]
            )
        elif page_index == 3:
            self.editor_scene_margin.setValue(
                self.ui_defaults["editor_scene_margin"]
            )
            self.editor_zoom_step.setValue(
                self.ui_defaults["editor_zoom_step_percent"]
            )
            self.simplify_large_moves.setChecked(
                self.ui_defaults["simplify_large_moves"]
            )
            self.reopen_last_project.setChecked(
                self.ui_defaults["reopen_last_project"]
            )
            self.show_startup_splash.setChecked(
                self.ui_defaults["show_startup_splash"]
            )
            self.project_directory.setText(
                self.ui_defaults["project_directory"]
            )
        elif page_index == 4:
            default_language = self.ui_defaults["language"]
            default_index = self.language_combo.findData(
                default_language
            )

            if default_index >= 0:
                self.language_combo.setCurrentIndex(
                    default_index
                )

        self.loading = False
        self.emit_preview()

    def emit_preview(self, _value=None):
        if self.loading:
            return

        self.preview_changed.emit(
            self.project_settings(),
            self.ui_settings()
        )
