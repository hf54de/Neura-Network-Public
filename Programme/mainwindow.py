# -------------------------------------------------------------------------------------------------
# Datei: mainwindow.py
# Zweck: Verbindet Hauptfenster, Menüs, Werkzeugleisten und zentrale Programmabläufe.
# Letzte Änderung: 20.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import json
import math
import os
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QPoint,
    QLocale,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QDoubleValidator,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QToolBox,
    QToolBar,
    QVBoxLayout,
    QWidget
)

from aboutdialog import AboutDialog
from commentitem import CommentItem
from connection import Connection
from editorscene import EditorScene
from forwardcalibrationdialog import ForwardCalibrationDialog
from graphicalexperimentdialog import GraphicalExperimentDialog
from graphicsview import GraphicsView
from helpdialog import HelpDialog
from language import LanguageManager
from mathematicsdialog import MathematicsDialog
from neuron import Neuron
from neurontype import NeuronType
from networkcreatedialog import NetworkCreateDialog
from networkfromtrainingdialog import NetworkFromTrainingDataDialog
from networklayoutdialog import NetworkLayoutDialog
from networkstructuredialog import NetworkStructureDialog
from networktestdialog import NetworkTestDialog
from newprojectdialog import NewProjectDialog
from numberformat import format_number
from projectassistantdialog import ProjectAssistantDialog
from projectio import ProjectIO
from projectdescriptiondialog import ProjectDescriptionDialog
from projectimagedialog import ProjectImageDialog
from projectoverviewdialog import ProjectOverviewDialog
from resultanalysisdialog import ResultAnalysisDialog
from projectsavedialog import ProjectSaveDialog
from settings import Settings
from settingsdialog import SettingsDialog
from trainingdialog import TrainingDialog
from traininghistorydialog import TrainingHistoryDialog
from trainingdatadialog import TrainingDataDialog
from trainingdataio import TrainingDataIO
from trainingdatamanager import TrainingDataManager
from toolbaricons import ToolbarIcons


class MainWindow(QMainWindow):
    """
    Hauptfenster des NeuronNetz-Editors.

    Aufgabe:
        Enthält die komplette Benutzeroberfläche.

    Zuständig für:
        - Menüleiste
        - Zeichenfläche
        - Eigenschaftenfenster
        - Statusleiste

    Nicht zuständig:
        - Berechnung des Netzwerkes
        - Verhalten eines Neurons
    """

    PROJECT_SUBDIRECTORIES = (
        "trainingsdaten",
        "testdaten",
        "exporte"
    )

    def __init__(self, defer_initial_show=False):

        super().__init__()

        self._defer_initial_show = bool(defer_initial_show)
        self._restore_maximized_on_show = False
        self._pending_loaded_project_fit = None

        self.resize(
            1280,
            820
        )

        self.current_object = None
        self.current_project_path = None
        self.project_modified = False
        self.project_description = ""
        self.is_example_project = False
        self.example_difficulty = None

        # Zum Projekt gehörende Einstellungen des Trainingsdialogs.
        self.training_settings = (
            ProjectIO.default_training_settings()
        )

        # Projektbezogene Kennzahlen und kompakte Fehlerkurven
        # bereits ausgeführter Trainingsläufe.
        self.training_history = []
        self.active_training_run_id = None
        self.analysis_tolerances = {}

        # Zum Projekt gehörende Einstellungen der Darstellung.
        self.display_settings = (
            ProjectIO.default_display_settings()
        )

        # Persönliche, projektunabhängige Einstellungen.
        self.ui_settings = Settings.get_ui_settings()
        self.language = LanguageManager(
            self.ui_settings["language"]
        )
        self.ui_settings["language"] = (
            self.language.current_language
        )
        self.normalize_language_project_directory()
        self._applying_ui_settings = False
        self._is_closing = False
        self.training_dialog = None
        self.training_observation_mode = False
        self._training_locked_action_states = {}

        # Interne Zwischenablage für Neuronen, Kommentare
        # und die Verbindungen zwischen kopierten Neuronen.
        self.object_clipboard = None

        # Zentrale Verwaltung der vom Projekt unabhängigen
        # Trainingsdatendatei.
        self.training_data_manager = TrainingDataManager(
            self,
            language_manager=self.language
        )

        self.training_data_manager.state_changed.connect(
            self.training_data_state_changed
        )

        # Eine zweite, unabhängige Datendatei kann dem
        # Projekt ausschließlich für Tests zugeordnet werden.
        self.test_data_manager = TrainingDataManager(
            self,
            language_manager=self.language
        )

        self.test_data_manager.state_changed.connect(
            self.test_data_state_changed
        )

        self.scene = EditorScene(language_manager=self.language)

        # Rückgängig-/Wiederholen-Verlauf.
        #
        # Es werden vollständige Momentaufnahmen des bearbeitbaren
        # Netzwerkes gespeichert. Bewegungen und fortlaufende
        # Texteingaben werden durch den verzögerten Abschluss
        # jeweils zu einem einzigen Arbeitsschritt zusammengefasst.
        self.undo_history = []
        self.redo_history = []
        self.undo_history_limit = 100

        self._history_baseline = None
        self._saved_history_snapshot = None
        self._history_restoring = False

        self._history_timer = QTimer(
            self
        )
        self._history_timer.setSingleShot(
            True
        )
        self._history_timer.setInterval(
            300
        )
        self._history_timer.timeout.connect(
            self.commit_history_snapshot
        )

        self.scene.setSceneRect(
            0,
            0,
            800,
            600
        )

        self.view = GraphicsView(
            self.scene
        )
        self.view.scene_margin = self.ui_settings[
            "editor_scene_margin"
        ]
        self.view.zoom_factor = (
            1.0
            + self.ui_settings["editor_zoom_step_percent"] / 100.0
        )
        self.view.update_scene_rect()

        self.setCentralWidget(
            self.view
        )

        # Menüleiste
        menubar = self.menuBar()
        text = self.language.text

        # Menü Datei
        datei_menu = menubar.addMenu(
            text("menu.file")
        )

        self.action_new = datei_menu.addAction(
            text("action.new")
        )

        self.action_new.triggered.connect(
            self.open_new_project_dialog
        )
        self.action_new.setShortcut(
            QKeySequence.StandardKey.New
        )

        self.action_open = datei_menu.addAction(
            text("action.open")
        )

        self.action_open.triggered.connect(
            self.open_project
        )
        self.action_open.setShortcut(
            QKeySequence.StandardKey.Open
        )

        self.recent_projects_menu = datei_menu.addMenu(
            text("action.recent_projects")
        )
        self.recent_projects_menu.aboutToShow.connect(
            self.update_recent_projects_menu
        )
        self.recent_projects_menu.hovered.connect(
            lambda action: self.schedule_project_menu_preview(
                self.recent_projects_menu, action
            )
        )
        self.recent_projects_menu.aboutToHide.connect(
            self.hide_project_menu_preview
        )
        self.update_recent_projects_menu()

        self.example_projects_menu = datei_menu.addMenu(
            text("action.example_projects")
        )
        self.example_projects_menu.aboutToShow.connect(
            self.update_example_projects_menu
        )
        self.example_projects_menu.hovered.connect(
            lambda action: self.schedule_project_menu_preview(
                self.example_projects_menu, action
            )
        )
        self.example_projects_menu.aboutToHide.connect(
            self.hide_project_menu_preview
        )
        self.update_example_projects_menu()

        self.project_preview_timer = QTimer(self)
        self.project_preview_timer.setSingleShot(True)
        self.project_preview_timer.setInterval(500)
        self.project_preview_timer.timeout.connect(
            self.show_scheduled_project_preview
        )
        self.project_preview_menu = None
        self.project_preview_action = None
        self.project_preview_popup = QFrame(
            None,
            Qt.WindowType.ToolTip
        )
        self.project_preview_popup.setObjectName("projectPreviewPopup")
        self.project_preview_popup.setFixedSize(420, 300)
        self.project_preview_popup.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True
        )
        preview_layout = QVBoxLayout(self.project_preview_popup)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        self.project_preview_label = QLabel(self.project_preview_popup)
        self.project_preview_label.setTextFormat(Qt.TextFormat.RichText)
        self.project_preview_label.setWordWrap(True)
        self.project_preview_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.project_preview_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        preview_layout.addWidget(self.project_preview_label)
        self.project_preview_popup.setStyleSheet(
            "QFrame#projectPreviewPopup {"
            "background: #ffffdc; border: 1px solid #767676;"
            "border-radius: 3px; }"
            "QLabel { background: transparent; color: #202020; }"
        )

        datei_menu.addSeparator()

        self.action_save = datei_menu.addAction(
            text("action.save")
        )

        self.action_save.triggered.connect(
            self.save_project
        )
        self.action_save.setShortcut(
            QKeySequence.StandardKey.Save
        )
        self.action_save.setEnabled(False)

        self.action_save_as = datei_menu.addAction(
            text("action.save_as")
        )

        self.action_save_as.triggered.connect(
            self.save_project_as
        )
        self.action_save_as.setShortcut(
            QKeySequence.StandardKey.SaveAs
        )

        self.action_rename_project = datei_menu.addAction(
            text("action.rename_project")
        )
        self.action_rename_project.triggered.connect(
            self.rename_current_project
        )

        datei_menu.addSeparator()

        self.action_project_description = datei_menu.addAction(
            text("action.project_description")
        )
        self.action_project_description.triggered.connect(
            self.open_project_description_dialog
        )

        self.action_project_overview = datei_menu.addAction(
            text("action.project_overview")
        )
        self.action_project_overview.setIcon(
            ToolbarIcons.icon("project_overview")
        )
        self.action_project_overview.triggered.connect(
            self.open_project_overview_dialog
        )

        self.action_export_word_report = datei_menu.addAction(
            text("analysis.report.word_export")
        )
        self.action_export_word_report.setIcon(
            ToolbarIcons.icon("word_report", accent="#2468a2")
        )
        self.action_export_word_report.triggered.connect(
            self.export_word_training_report
        )

        self.action_project_image = datei_menu.addAction(
            text("action.project_image")
        )
        self.action_project_image.triggered.connect(
            self.open_project_image
        )
        self.action_project_image.setVisible(False)

        datei_menu.addSeparator()

        self.action_exit = datei_menu.addAction(
            text("action.exit")
        )

        self.action_exit.triggered.connect(
            self.close
        )
        self.action_exit.setShortcut(
            QKeySequence("Alt+F4")
        )

        # Menü Bearbeiten
        bearbeiten_menu = menubar.addMenu(
            text("menu.edit")
        )

        self.action_undo = bearbeiten_menu.addAction(
            text("action.undo")
        )

        self.action_undo.setShortcut(
            "Ctrl+Z"
        )

        self.action_undo.triggered.connect(
            self.undo_last_action
        )

        self.action_undo.setEnabled(
            False
        )

        self.action_redo = bearbeiten_menu.addAction(
            text("action.redo")
        )

        self.action_redo.setShortcut(
            "Ctrl+Y"
        )

        self.action_redo.triggered.connect(
            self.redo_last_action
        )

        self.action_redo.setEnabled(
            False
        )

        bearbeiten_menu.addSeparator()

        self.action_cut = bearbeiten_menu.addAction(
            text("action.cut")
        )

        self.action_cut.setShortcut(
            "Ctrl+X"
        )

        self.action_cut.triggered.connect(
            self.cut_selected_objects
        )

        self.action_copy = bearbeiten_menu.addAction(
            text("action.copy")
        )

        self.action_copy.setShortcut(
            "Ctrl+C"
        )

        self.action_copy.triggered.connect(
            self.copy_selected_objects
        )

        self.action_paste = bearbeiten_menu.addAction(
            text("action.paste")
        )

        self.action_paste.setShortcut(
            "Ctrl+V"
        )

        self.action_paste.triggered.connect(
            self.paste_objects
        )

        bearbeiten_menu.addSeparator()

        self.action_select_all = bearbeiten_menu.addAction(
            text("action.select_all")
        )

        self.action_select_all.setShortcut(
            "Ctrl+A"
        )

        self.action_select_all.triggered.connect(
            self.select_all_objects
        )

        bearbeiten_menu.addSeparator()

        self.action_delete = bearbeiten_menu.addAction(
            text("action.delete")
        )

        self.action_delete.setShortcut(
            Qt.Key.Key_Delete
        )

        self.action_delete.triggered.connect(
            self.delete_selected_object
        )

        # Menü Ansicht
        ansicht_menu = menubar.addMenu(
            text("menu.view")
        )

        self.action_zoom_in = ansicht_menu.addAction(
            text("action.zoom_in")
        )

        self.action_zoom_in.setShortcut(
            "Ctrl++"
        )

        self.action_zoom_in.triggered.connect(
            self.view.zoom_in
        )

        self.action_zoom_out = ansicht_menu.addAction(
            text("action.zoom_out")
        )

        self.action_zoom_out.setShortcut(
            "Ctrl+-"
        )

        self.action_zoom_out.triggered.connect(
            self.view.zoom_out
        )

        self.action_zoom_reset = ansicht_menu.addAction(
            text("action.zoom_reset")
        )

        self.action_zoom_reset.setShortcut(
            "Ctrl+0"
        )

        self.action_zoom_reset.triggered.connect(
            self.view.reset_zoom
        )

        self.action_zoom_fit = ansicht_menu.addAction(
            text("action.zoom_fit")
        )

        self.action_zoom_fit.setShortcut(
            "Ctrl+F"
        )

        self.action_zoom_fit.triggered.connect(
            self.show_all_project_objects
        )

        # Menü Netzwerk
        netzwerk_menu = menubar.addMenu(
            text("menu.network")
        )

        self.action_layout_network = netzwerk_menu.addAction(
            text("action.layout_network")
        )

        self.action_layout_network.triggered.connect(
            self.open_network_layout_dialog
        )

        self.action_change_structure = netzwerk_menu.addAction(
            text("action.change_structure")
        )

        self.action_change_structure.triggered.connect(
            self.open_network_structure_dialog
        )

        netzwerk_menu.addSeparator()

        self.action_validate_network = netzwerk_menu.addAction(
            text("action.validate_network")
        )

        self.action_validate_network.triggered.connect(
            self.validate_network
        )

        netzwerk_menu.addSeparator()

        self.action_forward_pass = netzwerk_menu.addAction(
            text("action.forward")
        )

        self.action_forward_pass.triggered.connect(
            self.forward_pass
        )

        self.action_graphical_experiment = netzwerk_menu.addAction(
            text("forward.button.graphical_experiment")
        )
        self.action_graphical_experiment.triggered.connect(
            self.open_graphical_experiment
        )

        netzwerk_menu.addSeparator()

        self.action_training_step = netzwerk_menu.addAction(
            text("action.train")
        )

        self.action_training_step.triggered.connect(
            self.open_training_dialog
        )

        self.action_test_network = netzwerk_menu.addAction(
            text("action.test_network")
        )

        self.action_test_network.triggered.connect(
            self.test_network_with_training_data
        )

        self.action_result_analysis = netzwerk_menu.addAction(
            text("action.result_analysis")
        )
        self.action_result_analysis.setIcon(
            ToolbarIcons.icon("history", accent="#2b8a3e")
        )
        self.action_result_analysis.triggered.connect(
            self.open_result_analysis
        )
        self.action_result_analysis.setEnabled(False)
        netzwerk_menu.removeAction(self.action_test_network)

        self.action_mathematics_mode = netzwerk_menu.addAction(
            text("action.mathematics")
        )
        self.action_mathematics_mode.setEnabled(False)
        self.action_mathematics_mode.triggered.connect(
            self.open_mathematics_mode
        )
        self.scene.network.neuron_removed.connect(
            lambda _neuron: self.update_network_data_action_states()
        )
        self.scene.network.neuron_added.connect(
            lambda _neuron: self.update_network_data_action_states()
        )
        self.scene.network.connection_added.connect(
            lambda _connection: self.update_network_data_action_states()
        )
        self.scene.network.connection_removed.connect(
            lambda _connection: self.update_network_data_action_states()
        )
        self.scene.network.network_cleared.connect(
            self.update_network_data_action_states
        )

        self.action_training_history = netzwerk_menu.addAction(
            text("action.history")
        )

        self.action_training_history.triggered.connect(
            self.open_training_history
        )

        # Menü Trainingsdaten
        training_menu = menubar.addMenu(
            text("menu.training_data")
        )

        self.action_training_data = training_menu.addAction(
            text("action.edit_training_data")
        )

        self.action_training_data.triggered.connect(
            self.open_training_data_dialog
        )

        training_menu.addSeparator()

        self.action_edit_test_data = training_menu.addAction(
            text("action.edit_test_data")
        )
        self.action_edit_test_data.triggered.connect(
            self.open_test_data_dialog
        )

        self.action_remove_test_data = training_menu.addAction(
            text("action.remove_test_data")
        )
        self.action_remove_test_data.triggered.connect(
            self.remove_test_data_association
        )

        training_menu.addSeparator()

        self.action_test_with_test_data = training_menu.addAction(
            text("action.test_with_test_data")
        )
        self.action_test_with_test_data.triggered.connect(
            self.test_network_with_test_data
        )

        self.update_test_data_actions()

        # Menü Einstellungen
        settings_menu = menubar.addMenu(
            text("menu.settings")
        )

        self.action_display_settings = settings_menu.addAction(
            text("action.program_settings")
        )
        self.action_display_settings.triggered.connect(
            self.open_settings_dialog
        )

        # Menü Hilfe
        hilfe_menu = menubar.addMenu(
            text("menu.help")
        )

        self.action_documentation = hilfe_menu.addAction(
            text("action.documentation")
        )

        self.action_documentation.triggered.connect(
            self.open_help_dialog
        )

        hilfe_menu.addSeparator()

        self.action_tutorials = hilfe_menu.addAction(
            text("action.tutorials")
        )
        self.action_tutorials.setIcon(
            ToolbarIcons.icon(
                "open",
                accent="#2878b8"
            )
        )
        self.action_tutorials.triggered.connect(
            self.open_tutorial
        )

        hilfe_menu.addSeparator()

        self.action_about = hilfe_menu.addAction(
            text("action.about")
        )

        self.action_about.triggered.connect(
            self.open_about_dialog
        )

        self.create_main_toolbar(
            ansicht_menu
        )
        self.update_mathematics_action_state()
        self.update_network_data_action_states()
        self.update_undo_redo_actions()

        # Auf Änderungen der Zeichenfläche reagieren
        self.scene.object_selected.connect(
            self.object_selected
        )

        self.scene.object_position_changed.connect(
            self.object_position_changed
        )

        self.scene.scene_content_changed.connect(
            self.scene_content_changed
        )

        self.scene.delete_requested.connect(
            self.delete_graphics_items
        )

        self.scene.edit_neuron_requested.connect(
            self.open_neuron_edit_dialog
        )

        self.scene.edit_comment_requested.connect(
            self.open_comment_edit_dialog
        )

        # Eigenschaftenfenster
        self.property_dock = QDockWidget(
            text("properties.title"),
            self
        )
        self.property_dock.setObjectName(
            "property_dock"
        )
        self.property_dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.property_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # Der Benutzer kann die Breite am linken Rand verändern. Die
        # Mindestbreite hält Beschriftungen und Eingabefelder lesbar.
        self.property_dock.setMinimumWidth(
            190
        )

        self.property_stack = QStackedWidget()
        self.property_stack.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding
        )

        # Leere Eigenschaftsseite
        self.empty_property_widget = QWidget()

        self.empty_property_layout = QVBoxLayout(
            self.empty_property_widget
        )

        self.empty_property_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        self.empty_property_label = QLabel(
            text("properties.none_selected")
        )

        self.empty_property_label.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )

        self.empty_property_layout.addWidget(
            self.empty_property_label
        )

        self.empty_property_layout.addStretch()

        self.neuron_details_widget = QWidget()

        self.neuron_property_main_layout = QVBoxLayout(
            self.neuron_details_widget
        )

        self.neuron_property_main_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )

        self.neuron_property_main_layout.setSpacing(
            14
        )

        self.neuron_math_widget = QWidget()
        self.neuron_math_layout = QVBoxLayout(
            self.neuron_math_widget
        )
        self.neuron_math_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )
        self.neuron_math_layout.setSpacing(8)

        # Gruppe: Allgemeine Neuronendaten
        self.neuron_general_group = QGroupBox(
            text("properties.neuron.group")
        )

        neuron_general_font = self.neuron_general_group.font()
        neuron_general_font.setBold(
            True
        )
        self.neuron_general_group.setFont(
            neuron_general_font
        )

        self.neuron_general_layout = QFormLayout(
            self.neuron_general_group
        )

        self.neuron_general_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.neuron_general_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.neuron_general_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.neuron_general_layout.setHorizontalSpacing(
            12
        )

        self.property_id = QLineEdit()
        self.property_id.setReadOnly(
            True
        )

        self.property_name = QLineEdit()

        self.property_type = QComboBox()

        for neuron_type in NeuronType:
            self.property_type.addItem(
                text(
                    f"properties.type.{neuron_type.value.lower()}"
                ),
                neuron_type
            )

        # Gruppe: Parameter
        self.neuron_parameter_group = QGroupBox(
            text("properties.parameter.group")
        )

        neuron_parameter_font = self.neuron_parameter_group.font()
        neuron_parameter_font.setBold(
            True
        )
        self.neuron_parameter_group.setFont(
            neuron_parameter_font
        )

        self.neuron_parameter_layout = QFormLayout(
            self.neuron_parameter_group
        )

        self.neuron_parameter_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.neuron_parameter_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.neuron_parameter_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.neuron_parameter_layout.setHorizontalSpacing(
            12
        )

        self.property_activation = QComboBox()

        self.property_activation.addItems(
            [
                "Linear",
                "ReLU",
                "Sigmoid",
                "Tanh"
            ]
        )

        self.property_bias = QLineEdit()

        self.bias_validator = QDoubleValidator()
        self.bias_validator.setLocale(
            QLocale.c()
        )

        self.property_bias.setValidator(
            self.bias_validator
        )

        self.property_input_value = QLineEdit()

        self.input_value_validator = QDoubleValidator()
        self.input_value_validator.setLocale(
            QLocale.c()
        )

        self.property_input_value.setValidator(
            self.input_value_validator
        )

        # Gruppe: Position
        self.neuron_position_group = QGroupBox(
            text("properties.position.group")
        )

        neuron_position_font = self.neuron_position_group.font()
        neuron_position_font.setBold(
            True
        )
        self.neuron_position_group.setFont(
            neuron_position_font
        )

        self.neuron_position_layout = QFormLayout(
            self.neuron_position_group
        )

        self.neuron_position_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.neuron_position_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.neuron_position_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.neuron_position_layout.setHorizontalSpacing(
            12
        )

        self.property_x = QLineEdit()
        self.property_x.setReadOnly(
            True
        )

        self.property_y = QLineEdit()
        self.property_y.setReadOnly(
            True
        )

        # Gruppe: Laufzeitwerte
        self.neuron_runtime_group = QGroupBox(
            text("properties.runtime.group")
        )

        neuron_runtime_font = self.neuron_runtime_group.font()
        neuron_runtime_font.setBold(
            True
        )
        self.neuron_runtime_group.setFont(
            neuron_runtime_font
        )

        self.neuron_runtime_layout = QFormLayout(
            self.neuron_runtime_group
        )

        self.neuron_runtime_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.neuron_runtime_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.neuron_runtime_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.neuron_runtime_layout.setHorizontalSpacing(
            12
        )

        self.property_runtime_x = QLineEdit()
        self.property_runtime_x.setReadOnly(
            True
        )

        self.property_runtime_sum = QLineEdit()
        self.property_runtime_sum.setReadOnly(
            True
        )

        self.property_runtime_y = QLineEdit()
        self.property_runtime_y.setReadOnly(
            True
        )

        self.property_target_value = QLineEdit()

        self.target_value_validator = QDoubleValidator()
        self.target_value_validator.setLocale(
            QLocale.c()
        )

        self.property_target_value.setValidator(
            self.target_value_validator
        )

        self.property_error_value = QLineEdit()
        self.property_error_value.setReadOnly(
            True
        )

        self.property_delta_value = QLineEdit()
        self.property_delta_value.setReadOnly(
            True
        )

        # Gruppe: Rechenweg
        self.neuron_calculation_group = QGroupBox(
            text("properties.calculation.group")
        )

        neuron_calculation_font = self.neuron_calculation_group.font()
        neuron_calculation_font.setBold(
            True
        )
        self.neuron_calculation_group.setFont(
            neuron_calculation_font
        )

        self.property_calculation = QPlainTextEdit()
        self.property_calculation.setReadOnly(
            True
        )
        self.property_calculation.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.property_calculation.setMinimumHeight(
            135
        )
        self.property_calculation.setMaximumHeight(
            16777215
        )

        self.property_calculation.setFont(
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        )

        neuron_calculation_layout = QVBoxLayout(
            self.neuron_calculation_group
        )
        neuron_calculation_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )
        neuron_calculation_layout.addWidget(
            self.property_calculation
        )

        # Einheitliche Monospace-Schrift für alle Feldinhalte
        # des Eigenschaftenfensters.
        self.property_field_font = (
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        )

        self.label_id = QLabel(
            text("properties.id")
        )

        self.label_name = QLabel(
            text("properties.name")
        )

        self.label_type = QLabel(
            text("properties.type")
        )

        self.label_activation = QLabel(
            text("properties.activation")
        )

        self.label_bias = QLabel(
            text("properties.bias")
        )

        self.label_input_value = QLabel(
            text("properties.input_value")
        )

        self.label_x = QLabel(
            text("properties.position_x")
        )

        self.label_y = QLabel(
            text("properties.position_y")
        )

        self.label_runtime_x = QLabel(
            "X:"
        )

        self.label_runtime_sum = QLabel(
            "Σ:"
        )

        self.label_runtime_y = QLabel(
            "Y:"
        )

        self.label_target_value = QLabel(
            text("properties.target")
        )

        self.label_error_value = QLabel(
            text("properties.error")
        )

        self.label_delta_value = QLabel(
            text("properties.delta")
        )

        neuron_labels = [
            self.label_id,
            self.label_name,
            self.label_type,
            self.label_activation,
            self.label_bias,
            self.label_input_value,
            self.label_x,
            self.label_y,
            self.label_runtime_x,
            self.label_runtime_sum,
            self.label_runtime_y,
            self.label_target_value,
            self.label_error_value,
            self.label_delta_value
        ]

        for label in neuron_labels:
            label.setMinimumWidth(
                95
            )

        neuron_fields = [
            self.property_id,
            self.property_name,
            self.property_type,
            self.property_activation,
            self.property_bias,
            self.property_input_value,
            self.property_x,
            self.property_y,
            self.property_runtime_x,
            self.property_runtime_sum,
            self.property_runtime_y,
            self.property_target_value,
            self.property_error_value,
            self.property_delta_value
        ]

        for field in neuron_fields:
            field.setFont(
                self.property_field_font
            )

            field.setMinimumWidth(
                145
            )

            field.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed
            )

        self.neuron_general_layout.addRow(
            self.label_id,
            self.property_id
        )

        self.neuron_general_layout.addRow(
            self.label_name,
            self.property_name
        )

        self.neuron_general_layout.addRow(
            self.label_type,
            self.property_type
        )

        self.neuron_parameter_layout.addRow(
            self.label_activation,
            self.property_activation
        )

        self.neuron_parameter_layout.addRow(
            self.label_bias,
            self.property_bias
        )

        self.neuron_parameter_layout.addRow(
            self.label_input_value,
            self.property_input_value
        )

        self.neuron_position_layout.addRow(
            self.label_x,
            self.property_x
        )

        self.neuron_position_layout.addRow(
            self.label_y,
            self.property_y
        )

        self.neuron_runtime_layout.addRow(
            self.label_runtime_x,
            self.property_runtime_x
        )

        self.neuron_runtime_layout.addRow(
            self.label_runtime_sum,
            self.property_runtime_sum
        )

        self.neuron_runtime_layout.addRow(
            self.label_runtime_y,
            self.property_runtime_y
        )

        self.neuron_runtime_layout.addRow(
            self.label_target_value,
            self.property_target_value
        )

        self.neuron_runtime_layout.addRow(
            self.label_error_value,
            self.property_error_value
        )

        self.neuron_runtime_layout.addRow(
            self.label_delta_value,
            self.property_delta_value
        )

        self.neuron_property_main_layout.addWidget(
            self.neuron_general_group
        )

        self.neuron_property_main_layout.addWidget(
            self.neuron_parameter_group
        )

        self.neuron_property_main_layout.addWidget(
            self.neuron_position_group
        )

        self.neuron_property_main_layout.addWidget(
            self.neuron_runtime_group
        )

        self.neuron_math_intro = QLabel(
            text("properties.neuron.calculation_intro")
        )
        self.neuron_math_intro.setWordWrap(True)

        self.neuron_math_layout.addWidget(
            self.neuron_math_intro
        )
        self.neuron_math_layout.addWidget(
            self.neuron_calculation_group,
            1
        )

        self.neuron_property_main_layout.addStretch()

        self.connection_details_widget = QWidget()

        self.connection_property_main_layout = QVBoxLayout(
            self.connection_details_widget
        )

        self.connection_property_main_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )

        self.connection_math_widget = QWidget()
        self.connection_math_layout = QVBoxLayout(
            self.connection_math_widget
        )
        self.connection_math_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )
        self.connection_math_layout.setSpacing(8)

        self.connection_property_group = QGroupBox(
            text("properties.connection.group")
        )

        connection_group_font = self.connection_property_group.font()
        connection_group_font.setBold(
            True
        )
        self.connection_property_group.setFont(
            connection_group_font
        )

        self.connection_property_layout = QFormLayout(
            self.connection_property_group
        )

        self.connection_property_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.connection_property_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.connection_property_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.connection_property_layout.setHorizontalSpacing(
            12
        )

        self.property_connection_id = QLineEdit()
        self.property_connection_id.setReadOnly(
            True
        )

        self.property_connection_source = QLineEdit()
        self.property_connection_source.setReadOnly(
            True
        )

        self.property_connection_target = QLineEdit()
        self.property_connection_target.setReadOnly(
            True
        )

        self.property_connection_weight = QLineEdit()

        self.connection_weight_validator = QDoubleValidator()
        self.connection_weight_validator.setLocale(
            QLocale.c()
        )

        self.property_connection_weight.setValidator(
            self.connection_weight_validator
        )

        self.label_connection_id = QLabel(
            "ID:"
        )

        self.label_connection_source = QLabel(
            text("properties.connection.source")
        )

        self.label_connection_target = QLabel(
            text("properties.connection.target")
        )

        self.label_connection_weight = QLabel(
            text("properties.connection.weight")
        )

        connection_labels = [
            self.label_connection_id,
            self.label_connection_source,
            self.label_connection_target,
            self.label_connection_weight
        ]

        for label in connection_labels:
            label.setMinimumWidth(
                95
            )

        connection_fields = [
            self.property_connection_id,
            self.property_connection_source,
            self.property_connection_target,
            self.property_connection_weight
        ]

        for field in connection_fields:
            field.setFont(
                self.property_field_font
            )

            field.setMinimumWidth(
                145
            )

            field.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed
            )

        self.connection_property_layout.addRow(
            self.label_connection_id,
            self.property_connection_id
        )

        self.connection_property_layout.addRow(
            self.label_connection_source,
            self.property_connection_source
        )

        self.connection_property_layout.addRow(
            self.label_connection_target,
            self.property_connection_target
        )

        self.connection_property_layout.addRow(
            self.label_connection_weight,
            self.property_connection_weight
        )

        self.connection_property_main_layout.addWidget(
            self.connection_property_group
        )

        self.connection_property_main_layout.addStretch()

        self.connection_math_intro = QLabel(
            text("properties.connection.calculation_intro")
        )
        self.connection_math_intro.setWordWrap(True)

        self.property_connection_calculation = QPlainTextEdit()
        self.property_connection_calculation.setReadOnly(True)
        self.property_connection_calculation.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.property_connection_calculation.setFont(
            self.property_field_font
        )

        self.connection_math_layout.addWidget(
            self.connection_math_intro
        )
        self.connection_math_layout.addWidget(
            self.property_connection_calculation,
            1
        )

        # Eigenschaften eines Kommentars
        self.comment_property_widget = QWidget()

        self.comment_property_main_layout = QVBoxLayout(
            self.comment_property_widget
        )

        self.comment_property_main_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )

        self.comment_property_main_layout.setSpacing(
            14
        )

        self.comment_general_group = QGroupBox(
            text("properties.comment.group")
        )

        comment_general_font = self.comment_general_group.font()
        comment_general_font.setBold(
            True
        )
        self.comment_general_group.setFont(
            comment_general_font
        )

        self.comment_general_layout = QFormLayout(
            self.comment_general_group
        )

        self.comment_general_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.comment_general_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.comment_general_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.comment_general_layout.setHorizontalSpacing(
            12
        )

        self.property_comment_id = QLineEdit()
        self.property_comment_id.setReadOnly(
            True
        )

        self.property_comment_x = QLineEdit()
        self.property_comment_x.setReadOnly(
            True
        )

        self.property_comment_y = QLineEdit()
        self.property_comment_y.setReadOnly(
            True
        )

        self.property_comment_width = QLineEdit()
        self.property_comment_height = QLineEdit()

        self.property_comment_font_size = QSpinBox()
        self.property_comment_font_size.setRange(
            8,
            48
        )
        self.property_comment_font_size.setSuffix(
            " pt"
        )

        self.comment_size_validator = QDoubleValidator()
        self.comment_size_validator.setLocale(
            QLocale.c()
        )
        self.comment_size_validator.setBottom(
            1.0
        )

        self.property_comment_width.setValidator(
            self.comment_size_validator
        )

        self.property_comment_height.setValidator(
            self.comment_size_validator
        )

        self.label_comment_id = QLabel(
            "ID:"
        )

        self.label_comment_x = QLabel(
            text("properties.position_x")
        )

        self.label_comment_y = QLabel(
            text("properties.position_y")
        )

        self.label_comment_width = QLabel(
            text("properties.comment.width")
        )

        self.label_comment_height = QLabel(
            text("properties.comment.height")
        )

        self.label_comment_font_size = QLabel(
            text("properties.comment.font_size")
        )

        comment_labels = [
            self.label_comment_id,
            self.label_comment_x,
            self.label_comment_y,
            self.label_comment_width,
            self.label_comment_height,
            self.label_comment_font_size
        ]

        for label in comment_labels:
            label.setMinimumWidth(
                95
            )

        comment_fields = [
            self.property_comment_id,
            self.property_comment_x,
            self.property_comment_y,
            self.property_comment_width,
            self.property_comment_height,
            self.property_comment_font_size
        ]

        for field in comment_fields:
            field.setFont(
                self.property_field_font
            )

            field.setMinimumWidth(
                145
            )

            field.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed
            )

        self.comment_general_layout.addRow(
            self.label_comment_id,
            self.property_comment_id
        )

        self.comment_general_layout.addRow(
            self.label_comment_x,
            self.property_comment_x
        )

        self.comment_general_layout.addRow(
            self.label_comment_y,
            self.property_comment_y
        )

        self.comment_general_layout.addRow(
            self.label_comment_width,
            self.property_comment_width
        )

        self.comment_general_layout.addRow(
            self.label_comment_height,
            self.property_comment_height
        )

        self.comment_general_layout.addRow(
            self.label_comment_font_size,
            self.property_comment_font_size
        )

        self.comment_text_group = QGroupBox(
            text("properties.comment.text_group")
        )

        comment_text_font = self.comment_text_group.font()
        comment_text_font.setBold(
            True
        )
        self.comment_text_group.setFont(
            comment_text_font
        )

        self.property_comment_text = QPlainTextEdit()
        self.property_comment_text.setFont(
            self.property_field_font
        )
        self.property_comment_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.property_comment_text.setMinimumHeight(
            180
        )

        self.comment_text_layout = QVBoxLayout(
            self.comment_text_group
        )

        self.comment_text_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )

        self.comment_text_layout.addWidget(
            self.property_comment_text
        )

        self.comment_property_main_layout.addWidget(
            self.comment_general_group
        )

        self.comment_property_main_layout.addWidget(
            self.comment_text_group
        )

        self.comment_property_main_layout.addStretch()

        # Seiten zum Eigenschaftenfenster hinzufügen
        self.property_stack.addWidget(
            self.empty_property_widget
        )

        self.property_stack.addWidget(
            self.neuron_details_widget
        )

        self.property_stack.addWidget(
            self.connection_details_widget
        )

        self.property_stack.addWidget(
            self.comment_property_widget
        )

        # Vertikale Bereichsauswahl statt einer breiten Reiterzeile. Dadurch
        # bleibt das Eigenschaftenfenster auch auf kleinen Bildschirmen schmal.
        self.property_dock_tabs = QToolBox()
        self.property_dock_tabs.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding
        )
        self.property_dock_tabs.addItem(
            self.property_stack,
            text("properties.tab.details")
        )

        self.property_math_stack = QStackedWidget()
        self.empty_math_widget = QWidget()
        empty_math_layout = QVBoxLayout(self.empty_math_widget)
        empty_math_layout.setContentsMargins(12, 12, 12, 12)
        empty_math_label = QLabel(text("properties.none_selected"))
        empty_math_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        empty_math_layout.addWidget(empty_math_label)
        empty_math_layout.addStretch(1)
        self.comment_math_widget = QWidget()
        comment_math_layout = QVBoxLayout(self.comment_math_widget)
        comment_math_layout.setContentsMargins(12, 12, 12, 12)
        comment_math_label = QLabel(text("properties.none_selected"))
        comment_math_label.setWordWrap(True)
        comment_math_layout.addWidget(comment_math_label)
        comment_math_layout.addStretch(1)
        self.property_math_stack.addWidget(self.empty_math_widget)
        self.property_math_stack.addWidget(self.neuron_math_widget)
        self.property_math_stack.addWidget(self.connection_math_widget)
        self.property_math_stack.addWidget(self.comment_math_widget)
        self.property_dock_tabs.addItem(
            self.property_math_stack,
            text("properties.tab.mathematics")
        )
        self.property_dock_tabs.currentChanged.connect(
            self.refresh_current_math_display
        )
        self.property_dock_tabs.currentChanged.connect(
            self.update_property_section_arrows
        )

        self.project_workflow_widget = QWidget()
        workflow_layout = QVBoxLayout(self.project_workflow_widget)
        workflow_layout.setContentsMargins(10, 10, 10, 10)
        workflow_layout.setSpacing(8)
        workflow_intro = QLabel(text("project_workflow.introduction"))
        workflow_intro.setWordWrap(True)
        workflow_layout.addWidget(workflow_intro)
        self.project_workflow_buttons = []
        workflow_steps = (
            ("network", "project_workflow.network", self.open_workflow_network),
            ("training_data", "project_workflow.training_data", self.open_training_data_dialog),
            ("calibration", "project_workflow.calibration", self.open_training_data_dialog),
            ("training", "project_workflow.training", self.open_training_dialog),
            ("analysis", "project_workflow.analysis", self.open_result_analysis),
        )
        for step, label_key, callback in workflow_steps:
            button = QPushButton()
            button.setProperty("workflow_step", step)
            button.setProperty("workflow_label_key", label_key)
            button.setMinimumHeight(32)
            button.clicked.connect(callback)
            workflow_layout.addWidget(button)
            self.project_workflow_buttons.append(button)
        workflow_layout.addStretch(1)
        self.property_dock_tabs.addItem(
            self.project_workflow_widget,
            text("properties.tab.project_workflow")
        )
        self.update_property_section_arrows()

        self.property_dock.setWidget(self.property_dock_tabs)

        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.property_dock
        )
        self.property_dock.visibilityChanged.connect(
            self.property_dock_visibility_changed
        )

        # Änderungen der Eigenschaften übernehmen
        self.property_name.editingFinished.connect(
            self.update_name
        )

        self.property_type.currentIndexChanged.connect(
            self.update_neuron_type
        )

        self.property_activation.currentTextChanged.connect(
            self.update_activation
        )

        self.property_bias.editingFinished.connect(
            self.update_bias
        )

        self.property_input_value.editingFinished.connect(
            self.update_input_value
        )

        self.property_target_value.editingFinished.connect(
            self.update_target_value
        )

        self.property_connection_weight.editingFinished.connect(
            self.update_connection_weight
        )

        self.property_comment_width.editingFinished.connect(
            self.update_comment_size
        )

        self.property_comment_height.editingFinished.connect(
            self.update_comment_size
        )

        self.property_comment_font_size.valueChanged.connect(
            self.update_comment_font_size
        )

        self.property_comment_text.textChanged.connect(
            self.update_comment_text
        )

        self.property_stack.setCurrentWidget(
            self.empty_property_widget
        )
        self.property_math_stack.setCurrentWidget(self.empty_math_widget)

        # Dauerhafte Projektübersicht. Zeitlich begrenzte Meldungen der
        # Statusleiste blenden normale Widgets automatisch vorübergehend aus.
        self.status_summary_label = QLabel()
        self.status_summary_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        self.statusBar().addWidget(
            self.status_summary_label,
            1
        )
        self.statusBar().messageChanged.connect(
            self.update_status_summary_visibility
        )

        # Zoomanzeige in der Statusleiste
        self.zoom_label = QLabel(
            text("status.zoom", percent=100)
        )

        self.statusBar().addPermanentWidget(
            self.zoom_label
        )

        self.view.zoom_changed.connect(
            self.update_zoom_label
        )

        self.update_status_summary()
        self.update_result_analysis_action_state()
        self.update_project_workflow()

        self.update_window_title()

        self.apply_display_settings(
            self.display_settings,
            mark_as_modified=False
        )

        desired_property_dock_visibility = self.ui_settings[
            "property_dock_visible"
        ]
        self._applying_ui_settings = True

        try:
            restore_maximized = Settings.restore_window(
                self
            )
            self.set_property_dock_visible(
                desired_property_dock_visibility
            )
            QTimer.singleShot(
                0,
                self.restore_property_dock_width
            )
        finally:
            self._applying_ui_settings = False

        self.update_toolbar_visibility_action()

        self._restore_maximized_on_show = bool(restore_maximized)
        if restore_maximized and not self._defer_initial_show:
            QTimer.singleShot(
                0,
                self.showMaximized
            )

        self.reset_undo_history(
            mark_as_saved=True
        )

    def show_after_startup(self):
        """Zeigt das vorbereitete Hauptfenster im gespeicherten Zustand."""

        if self._restore_maximized_on_show:
            self.showMaximized()
        else:
            self.show()

        self.schedule_loaded_project_fit()

    def schedule_loaded_project_fit(self):
        """Passt ein vollständig geladenes Projekt genau einmal sichtbar ein."""

        project_path = self._pending_loaded_project_fit
        if not project_path or not self.isVisible():
            return

        QTimer.singleShot(
            0,
            lambda expected_path=project_path: (
                self.fit_loaded_project(expected_path)
            )
        )

    def fit_loaded_project(self, expected_path):
        """Führt denselben Befehl wie die Schaltfläche „Alles zeigen“ aus."""

        if (
            self._pending_loaded_project_fit != expected_path
            or self.current_project_path != expected_path
            or not self.isVisible()
        ):
            return

        self._pending_loaded_project_fit = None
        self.view.fit_all()

    def show_all_project_objects(self):
        """Hebt Darstellungsfilter auf und passt das gesamte Projekt ein."""

        self.scene.clear_connection_focus()
        self.view.fit_all()

    def create_main_toolbar(self, ansicht_menu):
        """Erzeugt den gruppierten Werkzeugleistenbereich."""

        text = self.language.text
        file_entries = (
            (
                self.action_new,
                "new",
                text("toolbar.new"),
                text("tooltip.new")
            ),
            (
                self.action_open,
                "open",
                text("toolbar.open"),
                text("tooltip.open")
            ),
            (
                self.action_save,
                "save",
                text("toolbar.save"),
                text("tooltip.save")
            ),
            (
                self.action_save_as,
                "save_as",
                text("toolbar.save_as"),
                text("tooltip.save_as")
            ),
            (
                self.action_project_description,
                "project_description",
                text("toolbar.project_description"),
                text("tooltip.project_description")
            ),
            (
                self.action_project_overview,
                "project_overview",
                text("toolbar.project_overview"),
                text("tooltip.project_overview")
            ),
            (
                self.action_export_word_report,
                "word_report",
                text("toolbar.word_report"),
                text("tooltip.word_report")
            ),
        )
        edit_entries = (
            (self.action_undo, "undo", text("toolbar.back"), text("tooltip.undo")),
            (self.action_redo, "redo", text("toolbar.redo"), text("tooltip.redo")),
            (self.action_cut, "cut", text("toolbar.cut"), text("tooltip.cut")),
            (self.action_copy, "copy", text("toolbar.copy"), text("tooltip.copy")),
            (self.action_paste, "paste", text("toolbar.paste"), text("tooltip.paste")),
            (self.action_select_all, "select", text("toolbar.all"), text("tooltip.select_all")),
            (self.action_delete, "delete", text("toolbar.delete"), text("tooltip.delete"))
        )
        view_entries = (
            (
                self.action_display_settings,
                "display",
                text("toolbar.settings"),
                text("tooltip.settings")
            ),
            (self.action_zoom_in, "zoom_in", text("toolbar.zoom_in"), text("tooltip.zoom_in")),
            (self.action_zoom_out, "zoom_out", text("toolbar.zoom_out"), text("tooltip.zoom_out")),
            (self.action_zoom_reset, "zoom_reset", text("toolbar.zoom_reset"), text("tooltip.zoom_reset")),
            (self.action_zoom_fit, "fit", text("toolbar.fit"), text("tooltip.zoom_fit"))
        )
        network_entries = (
            (
                self.action_layout_network,
                "network_layout",
                text("toolbar.arrange"),
                text("tooltip.layout_network")
            ),
            (
                self.action_change_structure,
                "network_structure",
                text("toolbar.change_structure"),
                text("tooltip.change_structure")
            ),
            (
                self.action_validate_network,
                "validate",
                text("toolbar.validate"),
                text("tooltip.validate_network")
            ),
            (
                self.action_forward_pass,
                "forward",
                text("toolbar.forward"),
                text("tooltip.forward")
            ),
            (
                self.action_graphical_experiment,
                "graphical_experiment",
                (
                    "Anwendungs-\nansicht"
                    if self.language.current_language == "de"
                    else "Application\nView"
                ),
                text("forward.button.graphical_experiment")
            ),
            (
                self.action_training_step,
                "train",
                text("toolbar.train"),
                text("tooltip.train")
            ),
            (
                self.action_result_analysis,
                "history",
                text("toolbar.analysis"),
                text("tooltip.result_analysis")
            ),
            (
                self.action_mathematics_mode,
                "math",
                text("toolbar.mathematics"),
                text("tooltip.mathematics")
            ),
            (
                self.action_training_history,
                "history",
                text("toolbar.history"),
                text("tooltip.history")
            )
        )
        data_entries = (
            (
                self.action_training_data,
                "training_data",
                text("toolbar.training_data"),
                text("tooltip.training_data")
            ),
            (
                self.action_edit_test_data,
                "test_data",
                text("toolbar.test_data"),
                text("tooltip.test_data")
            ),
            (
                self.action_test_with_test_data,
                "test",
                text("toolbar.test"),
                text("tooltip.test")
            )
        )
        help_entries = (
            (
                self.action_documentation,
                "help",
                text("toolbar.help"),
                text("tooltip.help")
            ),
            (
                self.action_tutorials,
                "tutorial",
                text("toolbar.tutorials"),
                text("tooltip.tutorials")
            ),
        )

        toolbar_definitions = (
            (text("toolbar.group.file"), "toolbar_file", file_entries, "#2878b8"),
            (text("toolbar.group.edit"), "toolbar_edit", edit_entries, "#5c6f82"),
            (text("toolbar.group.view"), "toolbar_view", view_entries, "#7657a8"),
            (text("toolbar.group.network"), "toolbar_network", network_entries, "#168a83"),
            (text("toolbar.group.data"), "toolbar_data", data_entries, "#d27624"),
            (text("toolbar.group.help"), "toolbar_help", help_entries, "#2878b8")
        )

        self.main_toolbars = []

        for index, definition in enumerate(toolbar_definitions):
            title, object_name, entries, accent = definition
            toolbar = self.create_toolbar_group(
                title,
                object_name,
                entries,
                accent
            )

            if index == 3:
                self.addToolBarBreak(
                    Qt.ToolBarArea.TopToolBarArea
                )

            self.addToolBar(
                Qt.ToolBarArea.TopToolBarArea,
                toolbar
            )
            self.main_toolbars.append(
                toolbar
            )

        self.action_toolbar_visible = QAction(
            text("settings.toolbar.visible"),
            self
        )
        self.action_toolbar_visible.setCheckable(
            True
        )
        self.action_toolbar_visible.setChecked(
            True
        )
        self.action_toolbar_visible.toggled.connect(
            self.set_toolbars_visible
        )
        ansicht_menu.addSeparator()
        ansicht_menu.addAction(
            self.action_toolbar_visible
        )

        self.set_toolbars_visible(
            self.ui_settings["toolbars_visible"]
        )

    def create_toolbar_group(
        self,
        title,
        object_name,
        entries,
        accent
    ):
        toolbar = QToolBar(
            title,
            self
        )
        toolbar.setObjectName(
            object_name
        )
        toolbar.setMovable(
            True
        )
        toolbar.setFloatable(
            True
        )
        toolbar.setIconSize(
            QSize(
                self.ui_settings["toolbar_icon_size"],
                self.ui_settings["toolbar_icon_size"]
            )
        )
        toolbar.setToolButtonStyle(
            (
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon
                if self.ui_settings["toolbar_show_text"]
                else Qt.ToolButtonStyle.ToolButtonIconOnly
            )
        )
        toolbar.setStyleSheet(
            "QToolBar { spacing: 1px; padding: 1px; }"
            "QToolButton { min-width: 49px; padding: 2px 1px; "
            "border-radius: 5px; }"
            "QToolButton:hover { background: #e7f0f7; }"
            "QToolButton:pressed { background: #d4e5f1; }"
        )

        group_label = QLabel(
            title.upper()
        )
        group_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        group_label.setStyleSheet(
            f"color: {accent}; font-weight: bold; "
            "padding: 4px 6px;"
        )
        toolbar.addWidget(
            group_label
        )

        for action, symbol_name, short_text, tooltip in entries:
            action.setIcon(
                ToolbarIcons.icon(
                    symbol_name,
                    accent=accent
                )
            )
            # Qt übernimmt beim Aktivieren oder Deaktivieren einer Aktion
            # deren iconText erneut in die Werkzeugschaltfläche. Der kurze
            # Text muss deshalb an der Aktion selbst gespeichert sein und
            # nicht nur einmalig am erzeugten QToolButton gesetzt werden.
            action.setIconText(
                short_text
            )
            action.setToolTip(
                tooltip
            )
            toolbar.addAction(
                action
            )
            button = toolbar.widgetForAction(
                action
            )

            if button is not None:
                button.setText(
                    short_text
                )

        toolbar.visibilityChanged.connect(
            lambda _visible: self.update_toolbar_visibility_action()
        )
        toolbar.orientationChanged.connect(
            lambda _orientation, bar=toolbar:
            self.update_toolbar_dimensions(bar)
        )
        self.update_toolbar_dimensions(toolbar)

        return toolbar

    def toolbar_dimensions(self):
        """Liefert automatische oder manuell gewählte Werkzeugleistenmaße."""

        if not self.ui_settings.get("toolbar_auto_size", True):
            return (
                self.ui_settings["toolbar_vertical_width"],
                self.ui_settings["toolbar_horizontal_height"]
            )

        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen is not None else None
        if geometry is None:
            return 82, 62
        if geometry.width() <= 1366 or geometry.height() <= 768:
            return 72, 54
        if geometry.width() <= 1920 or geometry.height() <= 1080:
            return 82, 62
        return 90, 68

    def update_toolbar_dimensions(self, toolbar):
        """Passt Breite oder Höhe an die aktuelle Andockrichtung an."""

        vertical_width, horizontal_height = self.toolbar_dimensions()
        toolbar.setMinimumWidth(0)
        toolbar.setMaximumWidth(16777215)
        toolbar.setMinimumHeight(0)
        toolbar.setMaximumHeight(16777215)
        if toolbar.orientation() == Qt.Orientation.Vertical:
            toolbar.setFixedWidth(vertical_width)
        else:
            toolbar.setFixedHeight(horizontal_height)

    def set_toolbars_visible(self, visible):
        for toolbar in self.main_toolbars:
            toolbar.setVisible(
                bool(visible)
            )

    def set_property_dock_visible(self, visible):
        """Blendet das Eigenschaftenfenster rechts angedockt ein."""

        visible = bool(visible)

        if visible:
            self.removeDockWidget(
                self.property_dock
            )
            self.property_dock.setFloating(
                False
            )
            self.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea,
                self.property_dock
            )

        self.property_dock.setVisible(
            visible
        )

    def restore_property_dock_width(self):
        """Stellt die persönlich gespeicherte Dock-Breite wieder her."""

        if not self.property_dock.isVisible():
            return

        self.resizeDocks(
            [self.property_dock],
            [self.ui_settings["property_dock_width"]],
            Qt.Orientation.Horizontal
        )

    def property_dock_visibility_changed(self, visible):
        """Speichert eine direkte Änderung am Eigenschaftenfenster."""

        if self._applying_ui_settings or self._is_closing:
            return

        self.ui_settings["property_dock_visible"] = bool(
            visible
        )

        try:
            Settings.save_ui_settings(
                self.ui_settings
            )
        except OSError:
            self.statusBar().showMessage(
                self.language.text(
                    "status.properties_visibility_save_error"
                ),
                5000
            )

    def update_toolbar_visibility_action(self):
        if not hasattr(self, "action_toolbar_visible"):
            return

        any_visible = any(
            toolbar.isVisible()
            for toolbar in self.main_toolbars
        )
        self.action_toolbar_visible.blockSignals(
            True
        )
        self.action_toolbar_visible.setChecked(
            any_visible
        )
        self.action_toolbar_visible.blockSignals(
            False
        )

    def set_weight_labels_visible(
        self,
        visible,
        mark_as_modified=True
    ):
        """
        Blendet die Gewichtsanzeigen aller Verbindungen
        ein oder aus und übernimmt die Auswahl als
        Projekteinstellung.
        """

        visible = bool(
            visible
        )

        previous_value = self.display_settings[
            "show_weights"
        ]

        self.display_settings[
            "show_weights"
        ] = visible

        self.scene.set_weight_labels_visible(
            visible
        )

        if (
            mark_as_modified
            and visible != previous_value
        ):
            self.set_project_modified(
                True
            )

    def apply_display_settings(
        self,
        display_settings,
        mark_as_modified=False
    ):
        """
        Übernimmt gespeicherte Darstellungseinstellungen
        in Menü und Zeichenfläche.
        """

        normalized_settings = (
            ProjectIO.normalize_display_settings(
                display_settings
            )
        )

        previous_settings = dict(
            self.display_settings
        )
        self.display_settings = dict(
            normalized_settings
        )

        self.scene.set_weight_labels_visible(
            self.display_settings["show_weights"]
        )
        self.scene.set_weight_visualization_enabled(
            self.display_settings["visualize_weights"]
        )
        self.scene.set_neuron_values_visible(
            self.display_settings["show_neuron_values"]
        )
        self.scene.set_activation_charts_visible(
            self.display_settings["show_activation_charts"]
        )
        self.scene.set_neuron_io_fields_visible(
            self.display_settings["show_io_value_fields"]
        )
        self.scene.set_neuron_ports_visible(
            self.display_settings["show_ports"]
        )
        self.scene.set_neuron_names_visible(
            self.display_settings["show_neuron_names"]
        )
        self.scene.set_comments_visible(
            self.display_settings["show_comments"]
        )
        self.scene.set_color_settings(
            self.display_settings["colors"]
        )

        if (
            mark_as_modified
            and self.display_settings != previous_settings
        ):
            self.set_project_modified(
                True
            )

    def apply_ui_settings(self, ui_settings):
        """Wendet persönliche Programm- und Editoroptionen an."""

        self.ui_settings = Settings.normalize_ui_settings(
            ui_settings
        )
        icon_size = self.ui_settings["toolbar_icon_size"]
        button_style = (
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            if self.ui_settings["toolbar_show_text"]
            else Qt.ToolButtonStyle.ToolButtonIconOnly
        )

        for toolbar in self.main_toolbars:
            toolbar.setIconSize(
                QSize(icon_size, icon_size)
            )
            toolbar.setToolButtonStyle(
                button_style
            )
            self.update_toolbar_dimensions(toolbar)

        self.set_toolbars_visible(
            self.ui_settings["toolbars_visible"]
        )

        if hasattr(self, "property_dock"):
            self._applying_ui_settings = True

            try:
                self.set_property_dock_visible(
                    self.ui_settings["property_dock_visible"]
                )
            finally:
                self._applying_ui_settings = False

        self.view.scene_margin = self.ui_settings[
            "editor_scene_margin"
        ]
        self.view.zoom_factor = (
            1.0
            + self.ui_settings["editor_zoom_step_percent"] / 100.0
        )
        self.scene.simplify_large_moves = self.ui_settings[
            "simplify_large_moves"
        ]
        self.view.update_scene_rect()

    def preview_settings(self, project_settings, ui_settings):
        self.apply_display_settings(
            project_settings,
            mark_as_modified=False
        )
        self.apply_ui_settings(
            ui_settings
        )

    def open_settings_dialog(self, initial_page="display"):
        """Zeigt die zentralen Projekt- und Programmeinstellungen."""

        if not isinstance(initial_page, str):
            initial_page = "display"

        previous_project_settings = deepcopy(
            self.display_settings
        )
        previous_ui_settings = deepcopy(
            self.ui_settings
        )
        previous_ui_settings["toolbars_visible"] = any(
            toolbar.isVisible()
            for toolbar in self.main_toolbars
        )
        previous_ui_settings["property_dock_visible"] = (
            self.property_dock.isVisible()
        )

        dialog = SettingsDialog(
            previous_project_settings,
            ProjectIO.default_display_settings(),
            previous_ui_settings,
            Settings.default_ui_settings(),
            self.language,
            initial_page=initial_page,
            parent=self
        )
        dialog.preview_changed.connect(
            self.preview_settings
        )

        result = dialog.exec()

        if result != dialog.DialogCode.Accepted:
            self.preview_settings(
                previous_project_settings,
                previous_ui_settings
            )
            return

        final_project_settings = dialog.project_settings()
        final_ui_settings = dialog.ui_settings()
        language_changed = (
            final_ui_settings["language"]
            != previous_ui_settings["language"]
        )
        self.preview_settings(
            final_project_settings,
            final_ui_settings
        )

        if final_project_settings != previous_project_settings:
            self.set_project_modified(
                True
            )

        try:
            Settings.save_ui_settings(final_ui_settings)
        except OSError as error:
            QMessageBox.warning(
                self,
                self.language.text("dialog.settings_save_error.title"),
                self.language.text(
                    "dialog.settings_save_error.message",
                    error=error
                )
            )
            return

        if (
            final_ui_settings.get("project_directory", "")
            != previous_ui_settings.get("project_directory", "")
        ):
            self.update_example_projects_menu()
            self.update_recent_projects_menu()

        if language_changed:
            self.update_example_projects_menu()
            self.update_recent_projects_menu()
            QMessageBox.information(
                self,
                self.language.text("settings.language.restart_title"),
                self.language.text("settings.language.restart_message")
            )

    def set_weight_visualization_enabled(
        self,
        enabled,
        mark_as_modified=True
    ):
        """
        Schaltet Farbe und Linienstärke nach Gewicht um und
        übernimmt die Auswahl als Projekteinstellung.
        """

        enabled = bool(
            enabled
        )

        previous_value = self.display_settings[
            "visualize_weights"
        ]

        self.display_settings[
            "visualize_weights"
        ] = enabled

        self.scene.set_weight_visualization_enabled(
            enabled
        )

        if (
            mark_as_modified
            and enabled != previous_value
        ):
            self.set_project_modified(
                True
            )

    def open_about_dialog(
        self
    ):
        """
        Öffnet das Informationsfenster zum Programm.
        """

        dialog = AboutDialog(
            language_manager=self.language,
            parent=self
        )

        dialog.exec()

    def open_project_description_dialog(self):
        """Öffnet den freien Rich-Text-Editor der Projektbeschreibung."""

        dialog = ProjectDescriptionDialog(
            self.project_description,
            example_project=self.is_example_project,
            example_difficulty=self.example_difficulty,
            language_manager=self.language,
            parent=self
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_description = dialog.description_html()
        new_example_project = dialog.is_example_project()
        new_example_difficulty = dialog.example_difficulty()
        example_settings_changed = (
            new_example_project != self.is_example_project
            or new_example_difficulty != self.example_difficulty
        )

        if (
            new_description == self.project_description
            and new_example_project == self.is_example_project
            and new_example_difficulty == self.example_difficulty
        ):
            return

        self.project_description = new_description
        self.is_example_project = new_example_project
        self.example_difficulty = new_example_difficulty
        self.set_project_modified(True)

        self.statusBar().showMessage(
            self.language.text(
                "status.project_description.example_updated"
                if example_settings_changed
                else "status.project_description.updated"
            ),
            3000
        )

    def network_structure_text(self):
        """Liefert die aktuelle Schichtstruktur in kompakter Schreibweise."""
        try:
            layers = self.scene.network.get_topological_layers()
            sizes = [len(layer) for layer in layers if layer]
        except ValueError:
            sizes = []
        if not sizes:
            sizes = [len(self.scene.network.get_input_neurons())]
            hidden_count = len(self.scene.network.get_hidden_neurons())
            if hidden_count:
                sizes.append(hidden_count)
            sizes.append(len(self.scene.network.get_output_neurons()))
        return " → ".join(str(size) for size in sizes)

    def project_overview_values(self):
        """Ermittelt die Angaben der kompakten Projektübersicht."""
        neurons = self.scene.network.get_neurons()
        connections = self.scene.network.get_connections()
        last_run_entry = self.training_history[-1] if self.training_history else None
        if last_run_entry is None:
            last_run = self.language.text("common.none")
            mean_error = self.language.text("common.none")
        else:
            timestamp = str(last_run_entry.get("timestamp", "")).replace("T", " ")
            last_run = self.language.text(
                "project_overview.run_value",
                date=timestamp or self.language.text("common.unknown"),
                epochs=int(last_run_entry.get("completed_epochs", 0)),
            )
            mean_error = format_number(float(last_run_entry.get("end_error", 0.0)))
        return {
            "structure": self.network_structure_text(),
            "neurons": len(neurons),
            "connections": len(connections),
            "training_records": self.training_data_manager.record_count,
            "test_records": self.test_data_manager.record_count,
            "last_run": last_run,
            "mean_error": mean_error,
            "no_training": last_run_entry is None,
        }

    def open_project_overview_dialog(self):
        """Öffnet die kompakte Übersicht des aktuellen Projekts."""
        ProjectOverviewDialog(
            self.project_overview_values(),
            parent=self,
            language_manager=self.language,
        ).exec()

    def set_project_workflow_visible(self, visible):
        """Blendet den optionalen Bereich Projektablauf ein oder aus."""
        if not hasattr(self, "property_dock_tabs"):
            return

        workflow_index = self.property_dock_tabs.indexOf(
            self.project_workflow_widget
        )
        if visible and workflow_index < 0:
            self.property_dock_tabs.addItem(
                self.project_workflow_widget,
                self.language.text("properties.tab.project_workflow")
            )
        elif not visible and workflow_index >= 0:
            if self.property_dock_tabs.currentIndex() == workflow_index:
                self.property_dock_tabs.setCurrentIndex(0)
            self.property_dock_tabs.removeItem(workflow_index)

        self.update_property_section_arrows()

        self.ui_settings["project_workflow_visible"] = bool(visible)
        if not self._applying_ui_settings and not self._is_closing:
            Settings.save_ui_settings(self.ui_settings)

    def update_property_section_arrows(self, *_args):
        """Kennzeichnet offene und geschlossene Eigenschaftsbereiche."""

        if not hasattr(self, "property_dock_tabs"):
            return

        sections = (
            (self.property_stack, "properties.tab.details"),
            (self.property_math_stack, "properties.tab.mathematics"),
            (self.project_workflow_widget, "properties.tab.project_workflow"),
        )
        current_index = self.property_dock_tabs.currentIndex()
        for widget, text_key in sections:
            index = self.property_dock_tabs.indexOf(widget)
            if index < 0:
                continue
            arrow_icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_ArrowDown
                if index == current_index
                else QStyle.StandardPixmap.SP_ArrowRight
            )
            self.property_dock_tabs.setItemIcon(index, arrow_icon)
            self.property_dock_tabs.setItemText(
                index,
                self.language.text(text_key)
            )

    def open_workflow_network(self):
        """Öffnet für den ersten Ablaufschritt Erzeugung oder Prüfung."""
        if self.scene.network.get_neurons():
            self.validate_network()
        else:
            self.open_network_create_dialog()

    def training_data_are_calibrated(self):
        """Prüft, ob alle analogen Trainingsspalten skaliert sind."""
        document = self.training_data_manager.document
        if not isinstance(document, dict):
            return False
        columns = document.get("columns", [])
        if not columns:
            return False
        for column in columns:
            if not isinstance(column, dict):
                return False
            if column.get("data_type", "analog") == "binary":
                continue
            calibration = column.get("calibration")
            if not isinstance(calibration, dict) or calibration.get("mode", "none") == "none":
                return False
        return True

    def update_project_workflow(self):
        """Aktualisiert die automatisch ermittelten Haken des Projektablaufs."""
        if not hasattr(self, "project_workflow_buttons"):
            return
        try:
            network_done = bool(self.scene.network.get_neurons()) and bool(
                self.scene.network.validate_network(translator=self.language.text)["valid"]
            )
        except (TypeError, ValueError, KeyError):
            network_done = False
        states = {
            "network": network_done,
            "training_data": self.training_data_manager.has_document,
            "calibration": self.training_data_are_calibrated(),
            "training": self.active_training_history_entry() is not None,
            "analysis": bool(
                hasattr(self, "action_result_analysis")
                and self.action_result_analysis.isEnabled()
            ),
        }
        for button in self.project_workflow_buttons:
            step = button.property("workflow_step")
            label = self.language.text(button.property("workflow_label_key"))
            button.setText(f"{'✓' if states.get(step) else '○'}  {label}")

    def project_image_path(self):
        """Liefert das vorhandene Projektbild des aktuellen Projekts."""

        if not self.current_project_path:
            return None

        image_path = (
            Path(self.current_project_path).resolve().parent
            / "Projektbild.png"
        )
        return image_path if image_path.is_file() else None

    def update_project_image_action(self):
        """Hält den veralteten Projektbild-Befehl aus Kompatibilitätsgründen verborgen."""

        if hasattr(self, "action_project_image"):
            self.action_project_image.setVisible(False)

    def open_project_image(self):
        """Öffnet das Projektbild in einem skalierbaren Dialog."""

        image_path = self.project_image_path()
        if image_path is None:
            self.update_project_image_action()
            return

        dialog = ProjectImageDialog(
            image_path,
            self.language,
            self
        )
        if not dialog.image_is_valid:
            QMessageBox.warning(
                self,
                self.language.text("project_image.error_title"),
                self.language.text("project_image.error_text")
            )
            return

        dialog.exec()

    def open_help_dialog(
        self
    ):
        """
        Öffnet die Markdown-Dokumentation
        in einem eigenen Hilfefenster.
        """

        dialog = HelpDialog(
            self,
            help_file_path=self.language.find_help_file(),
            language_manager=self.language
        )

        dialog.exec()

    @staticmethod
    def application_content_root():
        """
        Liefert den sichtbaren Stammordner für portable Inhalte.

        In der Einzeldatei-EXE ist dies der Ordner der EXE. Im Quellbetrieb
        liegt der Inhalt eine Ebene oberhalb des Python-Programmordners.
        Der temporäre PyInstaller-Entpackordner wird bewusst nicht verwendet.
        """

        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent

        return Path(__file__).resolve().parent.parent

    @staticmethod
    def documents_content_directory(directory_name):
        """Liefert den benutzerbezogenen Ausweichordner unter Dokumente."""

        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )

        if documents:
            base_directory = Path(documents)
        else:
            base_directory = Path.home() / "Documents"

        return base_directory / "NeuronNetz" / str(directory_name)

    @classmethod
    def portable_content_directory(cls, directory_name):
        """
        Verwendet bevorzugt einen sichtbaren Ordner neben der Anwendung.

        Kann dieser nicht angelegt werden, wird auf Dokumente\\NeuronNetz
        ausgewichen. Dadurch funktioniert sowohl ein entpacktes ZIP-Paket
        als auch eine Installation in einem schreibgeschützten Verzeichnis.
        """

        portable_directory = (
            cls.application_content_root() / str(directory_name)
        )

        try:
            portable_directory.mkdir(parents=True, exist_ok=True)
            return portable_directory
        except OSError:
            fallback_directory = cls.documents_content_directory(
                directory_name
            )
            fallback_directory.mkdir(parents=True, exist_ok=True)
            return fallback_directory

    def normalize_language_project_directory(self):
        """Passt einen sprachgebundenen Projektordner an die UI-Sprache an."""

        selected_directory = str(
            self.ui_settings.get("project_directory") or ""
        ).strip()
        if not selected_directory:
            return

        selected_path = Path(selected_directory).expanduser()
        if selected_path.name.casefold() not in {
            "projects_de",
            "projects_en"
        }:
            return

        directory_name = (
            "Projects_de"
            if self.language.current_language == "de"
            else "Projects_en"
        )
        language_path = selected_path.parent / directory_name
        if not language_path.is_dir():
            return

        normalized_path = str(language_path.resolve())
        if normalized_path == selected_directory:
            return

        self.ui_settings["project_directory"] = normalized_path
        try:
            Settings.save_ui_settings(self.ui_settings)
        except OSError:
            pass

    def project_content_directory(self, language_code=None):
        """Liefert den gewählten oder den vorgegebenen Projektordner."""

        selected_language = str(
            language_code or self.language.current_language
        ).strip().lower()
        directory_name = (
            "Projects_de"
            if selected_language == "de"
            else "Projects_en"
        )

        selected_directory = str(
            self.ui_settings.get("project_directory") or ""
        ).strip()
        if selected_directory:
            selected_path = Path(selected_directory).expanduser()
            if selected_path.name.casefold() in {
                "projects_de",
                "projects_en"
            }:
                selected_path = selected_path.parent / directory_name
            if selected_path.is_dir():
                return selected_path.resolve()

        if getattr(sys, "frozen", False):
            portable_directory = (
                Path(sys.executable).resolve().parent / directory_name
            )
        else:
            portable_directory = (
                Path(__file__).resolve().parent
                / "dist"
                / directory_name
            )

        try:
            portable_directory.mkdir(parents=True, exist_ok=True)
            return portable_directory
        except OSError:
            fallback_directory = self.documents_content_directory(
                directory_name
            )
            fallback_directory.mkdir(parents=True, exist_ok=True)
            return fallback_directory

    @classmethod
    def tutorials_destination_directory(cls):
        """
        Liefert den benutzerbezogenen, auch außerhalb der EXE sichtbaren
        Zielordner für Tutorials.
        """

        saved_directory = Settings.get_tutorials_directory()

        if saved_directory:
            saved_path = Path(saved_directory).expanduser()

            if saved_path.is_dir():
                return saved_path

        return cls.portable_content_directory("Tutorials")

    @staticmethod
    def bundled_tutorials_directory():
        """
        Sucht die mitgelieferten Tutorials sowohl im Quellprojekt als auch
        im temporär entpackten Datenbereich einer PyInstaller-EXE.
        """

        candidates = []
        pyinstaller_directory = getattr(
            sys,
            "_MEIPASS",
            None
        )

        if pyinstaller_directory:
            candidates.append(
                Path(pyinstaller_directory) / "tutorials"
            )

        candidates.append(
            Path(__file__).resolve().parent / "tutorials"
        )

        for candidate in candidates:
            if candidate.is_dir():
                return candidate

        return None

    @staticmethod
    def copy_bundled_tutorials(source_directory, target_directory):
        """
        Kopiert noch nicht vorhandene mitgelieferte Tutorials in den
        Benutzerordner. Eigene oder bereits bearbeitete Dateien werden
        dabei nicht überschrieben.
        """

        target_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        if source_directory is None:
            return

        for source_path in source_directory.rglob("*"):
            if not source_path.is_file():
                continue

            relative_path = source_path.relative_to(
                source_directory
            )
            target_path = target_directory / relative_path
            target_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            if not target_path.exists():
                shutil.copy2(
                    source_path,
                    target_path
                )

    def open_tutorial(
        self
    ):
        """
        Öffnet den normalen Windows-Dateidialog für Tutorials, merkt sich
        dessen Ordner und startet die ausgewählte Datei mit dem zugehörigen
        Windows-Programm.
        """

        target_directory = self.tutorials_destination_directory()

        try:
            self.copy_bundled_tutorials(
                self.bundled_tutorials_directory(),
                target_directory
            )
        except OSError as error:
            QMessageBox.warning(
                self,
                self.language.text("dialog.tutorial.error_title"),
                self.language.text(
                    "dialog.tutorial.prepare_error",
                    error=error
                )
            )
            return

        selected_file, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.language.text(
                "dialog.tutorial.open"
            ),
            str(target_directory),
            self.language.text(
                "dialog.tutorial.filter"
            )
        )

        if not selected_file:
            return

        selected_path = Path(
            selected_file
        )

        try:
            Settings.save_tutorials_directory(
                selected_path.parent
            )
        except OSError as error:
            QMessageBox.warning(
                self,
                self.language.text("dialog.tutorial.error_title"),
                self.language.text(
                    "dialog.tutorial.remember_error",
                    error=error
                )
            )

        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(selected_path)
            )
        )

        if not opened:
            QMessageBox.warning(
                self,
                self.language.text("dialog.tutorial.error_title"),
                self.language.text(
                    "dialog.tutorial.open_error",
                    file_path=selected_path
                )
            )

    def update_zoom_label(
        self,
        zoom_percent
    ):
        """
        Aktualisiert die Zoomanzeige
        in der Statusleiste.
        """

        self.zoom_label.setText(
            self.language.text(
                "status.zoom",
                percent=zoom_percent
            )
        )

    def update_status_summary(self):
        """Aktualisiert die dauerhafte kompakte Projektübersicht."""

        if not hasattr(self, "status_summary_label"):
            return

        training_status = self.language.text(
            "status.summary.loaded"
            if self.training_data_manager.has_document
            else "status.summary.not_loaded"
        )
        project_status = self.language.text(
            "status.summary.modified"
            if self.project_modified
            else "status.summary.saved"
        )
        self.status_summary_label.setText(
            self.language.text(
                "status.summary",
                neurons=len(self.scene.network.get_neurons()),
                connections=len(self.scene.network.get_connections()),
                training=training_status,
                project=project_status
            )
        )

    def update_status_summary_visibility(self, message):
        """Verhindert überlagerte Texte in der Statusleiste."""

        if not hasattr(self, "status_summary_label"):
            return
        self.status_summary_label.setVisible(not bool(message))

    def localize_message_box_buttons(self, message_box):
        """Beschriftet vorhandene Standardknöpfe in der Programmsprache."""

        button_texts = {
            QMessageBox.StandardButton.Ok: "common.ok",
            QMessageBox.StandardButton.Cancel: "common.cancel",
            QMessageBox.StandardButton.Save: "common.save",
            QMessageBox.StandardButton.Discard: "common.discard",
            QMessageBox.StandardButton.Yes: "common.yes",
            QMessageBox.StandardButton.No: "common.no"
        }

        for standard_button, text_key in button_texts.items():
            button = message_box.button(
                standard_button
            )

            if button is not None:
                button.setText(
                    self.language.text(text_key)
                )

    def update_mathematics_action_state(self):
        """Aktualisiert die gemeinsame Freigabe datenabhängiger Netzfunktionen."""

        self.update_network_data_action_states()

    def network_data_functions_available(self):
        """Prüft Netz, Trainingsdaten und die vollständige Spaltenzuordnung."""

        if (
            self.training_observation_mode
            or not self.scene.network.get_neurons()
            or not self.training_data_manager.has_document
        ):
            return False
        try:
            validation = self.scene.network.validate_network(
                translator=self.language.text
            )
            if not validation["valid"]:
                return False
            NetworkTestDialog.prepare_document(
                self.scene.network,
                self.training_data_manager.document,
                data_label=self.language.text("test.data.training"),
                translator=self.language.text,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def update_network_data_action_states(self):
        """Verwendet für alle datenabhängigen Netzfunktionen dieselbe Freigabe."""

        required_names = (
            "action_forward_pass",
            "action_graphical_experiment",
            "action_training_step",
            "action_result_analysis",
            "action_mathematics_mode",
            "action_training_history",
        )
        actions = [
            getattr(self, name) for name in required_names if hasattr(self, name)
        ]
        if not actions:
            return False
        enabled = self.network_data_functions_available()
        disabled_tooltip = self.language.text(
            "tooltip.disabled.analysis_required"
        )
        for action in actions:
            action.setEnabled(enabled)
            action.setToolTip(action.text() if enabled else disabled_tooltip)
        return enabled

    def object_selected(
        self,
        obj
    ):
        """
        Wird aufgerufen, wenn in der EditorScene
        ein Objekt ausgewählt oder erzeugt wurde.
        """

        self.current_object = obj

        self.update_mathematics_action_state()

        if obj is None:
            self.clear_property_fields()

            self.property_stack.setCurrentWidget(
                self.empty_property_widget
            )
            self.property_math_stack.setCurrentWidget(self.empty_math_widget)

            return

        if isinstance(
            obj,
            Neuron
        ):
            self.show_neuron_properties(
                obj
            )
            return

        if isinstance(
            obj,
            Connection
        ):
            self.show_connection_properties(
                obj
            )
            return

        if isinstance(
            obj,
            CommentItem
        ):
            self.show_comment_properties(
                obj
            )
            return

        self.clear_property_fields()

        self.property_stack.setCurrentWidget(
            self.empty_property_widget
        )
        self.property_math_stack.setCurrentWidget(self.empty_math_widget)

    def show_neuron_properties(
        self,
        neuron
    ):
        """
        Zeigt die Eigenschaften eines Neurons an.
        """

        self.property_type.blockSignals(
            True
        )

        self.property_activation.blockSignals(
            True
        )

        self.property_id.setText(
            str(
                neuron.id
            )
        )

        self.property_name.setText(
            neuron.name
        )

        type_index = self.property_type.findData(
            neuron.neuron_type
        )

        if type_index >= 0:
            self.property_type.setCurrentIndex(
                type_index
            )

        self.property_activation.setCurrentText(
            neuron.activation_function
        )

        self.property_bias.setText(
            format_number(
                neuron.bias
            )
        )
        self.property_bias.setModified(False)

        self.property_input_value.setText(
            format_number(
                neuron.input_value
            )
        )
        self.property_input_value.setModified(False)

        self.property_x.setText(
            f"{neuron.x():.1f}"
        )

        self.property_y.setText(
            f"{neuron.y():.1f}"
        )

        if neuron.neuron_type == NeuronType.INPUT:
            runtime_x_text = format_number(neuron.input_value)
        else:
            runtime_x_text = "-"

        self.property_runtime_x.setText(
            runtime_x_text
        )

        self.property_runtime_sum.setText(
            format_number(neuron.sum_value)
        )

        self.property_runtime_y.setText(
            format_number(neuron.output_value)
        )

        self.property_target_value.setText(
            format_number(neuron.target_value)
        )
        self.property_target_value.setModified(False)

        self.property_error_value.setText(
            format_number(neuron.error_value)
        )

        self.property_delta_value.setText(
            format_number(neuron.delta_value)
        )

        self.property_calculation.setPlainText(
            self.scene.network.get_calculation_details(
                neuron,
                self.language.text
            )
        )

        self.property_type.blockSignals(
            False
        )

        self.property_activation.blockSignals(
            False
        )

        self.update_neuron_property_visibility(
            neuron.neuron_type
        )

        self.property_stack.setCurrentWidget(
            self.neuron_details_widget
        )
        self.property_math_stack.setCurrentWidget(self.neuron_math_widget)

    def refresh_current_math_display(self, *args):
        """Aktualisiert die Mathematikseite des ausgewählten Objekts."""

        if isinstance(self.current_object, Neuron):
            self.property_calculation.setPlainText(
                self.scene.network.get_calculation_details(
                    self.current_object,
                    self.language.text
                )
            )

        elif isinstance(self.current_object, Connection):
            self.property_connection_calculation.setPlainText(
                self.scene.network.get_connection_calculation_details(
                    self.current_object,
                    self.language.text
                )
            )

    def show_connection_properties(
        self,
        connection
    ):
        """
        Zeigt die Eigenschaften einer Verbindung an.
        """

        self.property_connection_id.setText(
            str(
                connection.id
            )
        )

        self.property_connection_source.setText(
            connection.source_neuron.name
        )

        self.property_connection_target.setText(
            connection.target_neuron.name
        )

        self.property_connection_weight.setText(
            format_number(
                connection.weight
            )
        )
        self.property_connection_weight.setModified(False)

        self.property_connection_calculation.setPlainText(
            self.scene.network.get_connection_calculation_details(
                connection,
                self.language.text
            )
        )

        self.property_stack.setCurrentWidget(
            self.connection_details_widget
        )
        self.property_math_stack.setCurrentWidget(self.connection_math_widget)

    def show_comment_properties(
        self,
        comment
    ):
        """
        Zeigt die Eigenschaften eines Kommentars an.
        """

        self.property_comment_text.blockSignals(
            True
        )

        self.property_comment_id.setText(
            str(
                comment.id
            )
        )

        self.property_comment_x.setText(
            f"{comment.x():.1f}"
        )

        self.property_comment_y.setText(
            f"{comment.y():.1f}"
        )

        self.property_comment_width.setText(
            f"{comment.width:.1f}"
        )

        self.property_comment_height.setText(
            f"{comment.height:.1f}"
        )

        self.property_comment_font_size.blockSignals(
            True
        )

        self.property_comment_font_size.setValue(
            comment.font_size
        )

        self.property_comment_font_size.blockSignals(
            False
        )

        self.property_comment_text.setPlainText(
            comment.text
        )

        self.property_comment_text.blockSignals(
            False
        )

        self.property_stack.setCurrentWidget(
            self.comment_property_widget
        )
        self.property_math_stack.setCurrentWidget(self.comment_math_widget)

    def update_neuron_property_visibility(
        self,
        neuron_type
    ):
        """
        Blendet die Eigenschaften abhängig
        vom Neuronentyp ein oder aus.
        """

        is_input_neuron = (
            neuron_type
            == NeuronType.INPUT
        )

        self.label_input_value.setVisible(
            is_input_neuron
        )

        self.property_input_value.setVisible(
            is_input_neuron
        )

        self.label_activation.setVisible(
            not is_input_neuron
        )

        self.property_activation.setVisible(
            not is_input_neuron
        )

        self.label_bias.setVisible(
            not is_input_neuron
        )

        self.property_bias.setVisible(
            not is_input_neuron
        )

        self.label_runtime_x.setVisible(
            True
        )

        self.property_runtime_x.setVisible(
            True
        )

        self.label_runtime_sum.setVisible(
            not is_input_neuron
        )

        self.property_runtime_sum.setVisible(
            not is_input_neuron
        )

        is_output_neuron = (
            neuron_type
            == NeuronType.OUTPUT
        )

        self.label_target_value.setVisible(
            is_output_neuron
        )

        self.property_target_value.setVisible(
            is_output_neuron
        )

        self.label_error_value.setVisible(
            not is_input_neuron
        )

        self.property_error_value.setVisible(
            not is_input_neuron
        )

        self.label_delta_value.setVisible(
            not is_input_neuron
        )

        self.property_delta_value.setVisible(
            not is_input_neuron
        )

        self.neuron_calculation_group.setVisible(
            not is_input_neuron
        )

    def clear_property_fields(self):
        """
        Leert alle Felder des Eigenschaftenfensters.
        """

        self.property_type.blockSignals(
            True
        )

        self.property_activation.blockSignals(
            True
        )

        self.property_id.clear()
        self.property_name.clear()

        self.property_type.setCurrentIndex(
            -1
        )

        self.property_activation.setCurrentIndex(
            -1
        )

        self.property_bias.clear()
        self.property_input_value.clear()
        self.property_x.clear()
        self.property_y.clear()
        self.property_runtime_x.clear()
        self.property_runtime_sum.clear()
        self.property_runtime_y.clear()
        self.property_target_value.clear()
        self.property_error_value.clear()
        self.property_delta_value.clear()
        self.property_calculation.clear()

        self.property_type.blockSignals(
            False
        )

        self.property_activation.blockSignals(
            False
        )

        self.property_connection_id.clear()
        self.property_connection_source.clear()
        self.property_connection_target.clear()
        self.property_connection_weight.clear()
        self.property_connection_calculation.clear()

        self.property_comment_text.blockSignals(
            True
        )

        self.property_comment_id.clear()
        self.property_comment_x.clear()
        self.property_comment_y.clear()
        self.property_comment_width.clear()
        self.property_comment_height.clear()

        self.property_comment_font_size.blockSignals(
            True
        )

        self.property_comment_font_size.setValue(
            12
        )

        self.property_comment_font_size.blockSignals(
            False
        )

        self.property_comment_text.clear()

        self.property_comment_text.blockSignals(
            False
        )

    def object_position_changed(
        self,
        obj
    ):
        """
        Aktualisiert die angezeigte Position,
        wenn das ausgewählte Neuron verschoben wurde.
        """

        if obj is self.current_object:
            if isinstance(
                obj,
                Neuron
            ):
                self.property_x.setText(
                    f"{obj.x():.1f}"
                )

                self.property_y.setText(
                    f"{obj.y():.1f}"
                )

            elif isinstance(
                obj,
                CommentItem
            ):
                self.property_comment_x.setText(
                    f"{obj.x():.1f}"
                )

                self.property_comment_y.setText(
                    f"{obj.y():.1f}"
                )

                self.property_comment_width.setText(
                    f"{obj.width:.1f}"
                )

                self.property_comment_height.setText(
                    f"{obj.height:.1f}"
                )

        self.set_project_modified(
            True
        )

    def scene_content_changed(self):
        """
        Wird aufgerufen, wenn ein Objekt
        erzeugt oder gelöscht wurde.
        """

        self.set_project_modified(
            True
        )
        self.refresh_current_math_display()
        self.update_status_summary()
        self.update_result_analysis_action_state()
        self.update_project_workflow()

    def update_name(self):
        """
        Übernimmt den geänderten Namen
        in das aktuell ausgewählte Neuron.
        """

        if not isinstance(
            self.current_object,
            Neuron
        ):
            return

        new_name = self.property_name.text().strip()

        duplicate = next(
            (
                neuron
                for neuron in self.scene.network.get_neurons()
                if neuron.id != self.current_object.id
                and str(neuron.name).strip().casefold() == new_name.casefold()
            ),
            None,
        )
        if not new_name or duplicate is not None:
            self.property_name.setText(self.current_object.name)
            QMessageBox.warning(
                self,
                self.language.text("data.name.duplicate.title"),
                self.language.text(
                    "data.name.empty.message"
                    if not new_name
                    else "data.name.duplicate.message",
                    name=new_name,
                ),
            )
            return

        if (
            new_name
            == self.current_object.name
        ):
            return

        self.current_object.name = new_name
        self.current_object.update()
        self.synchronize_neuron_name_in_data(
            self.current_object,
            new_name,
        )

        self.set_project_modified(
            True
        )
        self.refresh_current_math_display()

    def synchronize_neuron_name_in_data(self, neuron, new_name):
        """Hält zugeordnete Trainings- und Testspalten beim Neuronnamen."""

        for manager in (
            self.training_data_manager,
            self.test_data_manager,
        ):
            if manager is None or not manager.has_document:
                continue
            changed = False
            document = manager.document
            for column in document.get("columns", []):
                if column.get("mapped_neuron_id") != neuron.id:
                    continue
                if (
                    column.get("name") != new_name
                    or column.get("mapped_neuron_name") != new_name
                ):
                    column["name"] = new_name
                    column["mapped_neuron_name"] = new_name
                    changed = True
            if changed:
                manager.set_document(
                    document,
                    file_path=manager.file_path,
                    modified=True,
                )

        self.set_project_modified(True)

    def update_neuron_type(self):
        """
        Übernimmt den gewählten Typ
        in das aktuell ausgewählte Neuron.
        """

        if not isinstance(
            self.current_object,
            Neuron
        ):
            return

        new_type = self.property_type.currentData()

        if not isinstance(
            new_type,
            NeuronType
        ):
            return

        if (
            new_type
            == self.current_object.neuron_type
        ):
            self.update_neuron_property_visibility(
                new_type
            )
            return

        old_type = self.current_object.neuron_type
        data_types = {NeuronType.INPUT, NeuronType.OUTPUT}

        if old_type in data_types or new_type in data_types:
            answer = QMessageBox.warning(
                self,
                self.language.text("network.data_mapping_warning.title"),
                self.language.text("network.data_mapping_warning.message"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                self.property_type.blockSignals(True)
                try:
                    old_index = self.property_type.findData(old_type)
                    if old_index >= 0:
                        self.property_type.setCurrentIndex(old_index)
                finally:
                    self.property_type.blockSignals(False)
                self.update_neuron_property_visibility(old_type)
                return

        self.current_object.prepareGeometryChange()
        self.current_object.neuron_type = new_type

        self.update_neuron_property_visibility(
            new_type
        )

        self.current_object.update()

        self.set_project_modified(
            True
        )
        self.refresh_current_math_display()

    def update_activation(
        self,
        activation
    ):
        """
        Übernimmt die gewählte Aktivierungsfunktion
        in das aktuell ausgewählte Neuron.
        """

        if not isinstance(
            self.current_object,
            Neuron
        ):
            return

        if (
            self.current_object.neuron_type
            == NeuronType.INPUT
        ):
            return

        if (
            activation
            == self.current_object.activation_function
        ):
            return

        self.current_object.activation_function = activation
        self.current_object.update()

        self.set_project_modified(
            True
        )
        self.refresh_current_math_display()

    def update_bias(self):
        """
        Übernimmt den geänderten Bias
        in das aktuell ausgewählte Neuron.
        """

        if not isinstance(
            self.current_object,
            Neuron
        ):
            return

        if (
            self.current_object.neuron_type
            == NeuronType.INPUT
        ):
            return

        # Die kompakte Anzeige darf die intern gespeicherte Genauigkeit
        # nicht allein durch das Betreten und Verlassen des Feldes
        # reduzieren. Nur eine tatsächliche Eingabe wird übernommen.
        if not self.property_bias.isModified():
            self.property_bias.setText(
                format_number(
                    self.current_object.bias
                )
            )
            return

        text = self.property_bias.text()

        try:
            new_bias = float(
                text
            )

            if (
                new_bias
                != self.current_object.bias
            ):
                self.current_object.bias = new_bias
                self.current_object.update()

                self.set_project_modified(
                    True
                )

            self.property_bias.setText(
                format_number(
                    self.current_object.bias
                )
            )

        except ValueError:
            self.property_bias.setText(
                format_number(
                    self.current_object.bias
                )
            )

        self.property_bias.setModified(False)

        self.refresh_current_math_display()

    def update_input_value(self):
        """
        Übernimmt den aktuellen Eingabewert
        in das ausgewählte Input-Neuron.

        Der Ausgangswert Y wird erst bei einer
        Vorwärtsberechnung aktualisiert.
        """

        if not isinstance(
            self.current_object,
            Neuron
        ):
            return

        if (
            self.current_object.neuron_type
            != NeuronType.INPUT
        ):
            return

        if not self.property_input_value.isModified():
            self.property_input_value.setText(
                format_number(
                    self.current_object.input_value
                )
            )
            return

        text = self.property_input_value.text()

        try:
            new_input_value = float(
                text
            )

            if (
                new_input_value
                != self.current_object.input_value
            ):
                self.current_object.input_value = new_input_value
                self.current_object.set_external_input_value(
                    new_input_value,
                    False
                )
                self.current_object.update()

                self.property_runtime_x.setText(
                    format_number(self.current_object.input_value)
                )

                self.set_project_modified(
                    True
                )

            self.property_input_value.setText(
                format_number(
                    self.current_object.input_value
                )
            )

        except ValueError:
            self.property_input_value.setText(
                format_number(
                    self.current_object.input_value
                )
            )

        self.property_input_value.setModified(False)

        self.refresh_current_math_display()

    def update_target_value(self):
        """
        Übernimmt den Sollwert in das aktuell
        ausgewählte Output-Neuron.
        """

        if not isinstance(
            self.current_object,
            Neuron
        ):
            return

        if (
            self.current_object.neuron_type
            != NeuronType.OUTPUT
        ):
            return

        if not self.property_target_value.isModified():
            self.property_target_value.setText(
                format_number(
                    self.current_object.target_value
                )
            )
            return

        text = self.property_target_value.text()

        try:
            new_target_value = float(
                text
            )

            if (
                new_target_value
                != self.current_object.target_value
            ):
                self.current_object.target_value = (
                    new_target_value
                )
                self.current_object.set_external_output_values(
                    actual_value=(
                        self.current_object.external_output_value
                    ),
                    target_value=new_target_value,
                    is_raw=False
                )

                self.current_object.update()

                self.set_project_modified(
                    True
                )

            self.property_target_value.setText(
                format_number(
                    self.current_object.target_value
                )
            )

        except ValueError:
            self.property_target_value.setText(
                format_number(
                    self.current_object.target_value
                )
            )

        self.property_target_value.setModified(False)

        self.refresh_current_math_display()

    def update_comment_text(self):
        """
        Übernimmt den Text direkt in den
        ausgewählten Kommentar.
        """

        if not isinstance(
            self.current_object,
            CommentItem
        ):
            return

        new_text = self.property_comment_text.toPlainText()

        if new_text == self.current_object.text:
            return

        self.current_object.set_text(
            new_text
        )

    def update_comment_size(self):
        """
        Übernimmt Breite und Höhe in den
        ausgewählten Kommentar.

        Die Größe bleibt zusätzlich weiterhin
        direkt mit der Maus veränderbar.
        """

        if not isinstance(
            self.current_object,
            CommentItem
        ):
            return

        try:
            new_width = float(
                self.property_comment_width.text()
            )

            new_height = float(
                self.property_comment_height.text()
            )

            self.current_object.set_size(
                new_width,
                new_height
            )

        except ValueError:
            pass

        self.property_comment_width.setText(
            f"{self.current_object.width:.1f}"
        )

        self.property_comment_height.setText(
            f"{self.current_object.height:.1f}"
        )

    def update_comment_font_size(
        self,
        font_size
    ):
        """
        Übernimmt die Schriftgröße direkt in den
        ausgewählten Kommentar.
        """

        if not isinstance(
            self.current_object,
            CommentItem
        ):
            return

        self.current_object.set_font_size(
            font_size
        )

    def update_connection_weight(self):
        """
        Übernimmt das geänderte Gewicht
        in die aktuell ausgewählte Verbindung.
        """

        if not isinstance(
            self.current_object,
            Connection
        ):
            return

        if not self.property_connection_weight.isModified():
            self.property_connection_weight.setText(
                format_number(
                    self.current_object.weight
                )
            )
            return

        text = self.property_connection_weight.text()

        try:
            new_weight = float(
                text
            )

            if (
                new_weight
                != self.current_object.weight
            ):
                self.current_object.weight = new_weight

                self.set_project_modified(
                    True
                )

            self.property_connection_weight.setText(
                format_number(
                    self.current_object.weight
                )
            )

        except ValueError:
            self.property_connection_weight.setText(
                format_number(
                    self.current_object.weight
                )
            )

        self.property_connection_weight.setModified(False)

        self.refresh_current_math_display()

    def get_focused_text_widget(self):
        """
        Liefert das aktuell fokussierte Texteingabefeld.

        Dadurch funktionieren Strg+C, Strg+X und Strg+V
        in Eingabefeldern weiterhin wie gewohnt.
        """

        focused_widget = QApplication.focusWidget()

        if isinstance(
            focused_widget,
            (QLineEdit, QPlainTextEdit)
        ):
            return focused_widget

        return None

    def create_unique_pasted_neuron_name(
        self,
        original_name,
        original_id,
        new_id
    ):
        """
        Erzeugt für ein eingefügtes Neuron einen eindeutigen Namen.

        Standardnamen wie N1 werden passend zur neuen ID angepasst.
        Benutzerdefinierte Namen erhalten den Zusatz 'Kopie'.
        """

        original_name = str(
            original_name
        )

        if original_name == f"N{original_id}":
            return f"N{new_id}"

        existing_names = {
            neuron.name
            for neuron in self.scene.network.get_neurons()
        }

        base_name = f"{original_name} Kopie"
        candidate_name = base_name
        copy_number = 2

        while candidate_name in existing_names:
            candidate_name = (
                f"{base_name} {copy_number}"
            )
            copy_number += 1

        return candidate_name

    def build_object_clipboard_data(
        self,
        is_cut=False
    ):
        """
        Erstellt aus der aktuellen Auswahl eine unabhängige
        interne Zwischenablage.

        Verbindungen werden automatisch mitkopiert, wenn sowohl
        Start- als auch Zielneuron zur Auswahl gehören.
        """

        selected_items = list(
            self.scene.selectedItems()
        )

        selected_neurons = sorted(
            [
                item
                for item in selected_items
                if isinstance(
                    item,
                    Neuron
                )
            ],
            key=lambda neuron: neuron.id
        )

        selected_comments = sorted(
            [
                item
                for item in selected_items
                if isinstance(
                    item,
                    CommentItem
                )
            ],
            key=lambda comment: comment.id
        )

        selected_neuron_ids = {
            neuron.id
            for neuron in selected_neurons
        }

        copied_connections = sorted(
            [
                connection
                for connection in self.scene.network.get_connections()
                if (
                    connection.source_neuron.id
                    in selected_neuron_ids
                    and connection.target_neuron.id
                    in selected_neuron_ids
                )
            ],
            key=lambda connection: connection.id
        )

        if (
            not selected_neurons
            and not selected_comments
        ):
            return None

        return {
            "is_cut": bool(
                is_cut
            ),
            "paste_count": 0,
            "neurons": [
                {
                    "id": neuron.id,
                    "name": neuron.name,
                    "type": neuron.neuron_type.value,
                    "bias": float(
                        neuron.bias
                    ),
                    "activation": neuron.activation_function,
                    "input_value": float(
                        neuron.input_value
                    ),
                    "target_value": float(
                        neuron.target_value
                    ),
                    "x": float(
                        neuron.x()
                    ),
                    "y": float(
                        neuron.y()
                    )
                }
                for neuron in selected_neurons
            ],
            "comments": [
                {
                    "id": comment.id,
                    "text": comment.text,
                    "x": float(
                        comment.x()
                    ),
                    "y": float(
                        comment.y()
                    ),
                    "width": float(
                        comment.width
                    ),
                    "height": float(
                        comment.height
                    ),
                    "font_size": int(
                        comment.font_size
                    )
                }
                for comment in selected_comments
            ],
            "connections": [
                {
                    "source": connection.source_neuron.id,
                    "target": connection.target_neuron.id,
                    "weight": float(
                        connection.weight
                    )
                }
                for connection in copied_connections
            ]
        }

    def copy_selected_objects(self):
        """
        Kopiert ausgewählte Neuronen und Kommentare.

        Verbindungen zwischen gemeinsam ausgewählten Neuronen
        werden automatisch übernommen.
        """

        text_widget = self.get_focused_text_widget()

        if text_widget is not None:
            text_widget.copy()
            return

        clipboard_data = self.build_object_clipboard_data(
            is_cut=False
        )

        if clipboard_data is None:
            self.statusBar().showMessage(
                self.language.text("status.clipboard.nothing_to_copy"),
                3000
            )
            return

        self.object_clipboard = clipboard_data

        neuron_count = len(
            clipboard_data["neurons"]
        )

        comment_count = len(
            clipboard_data["comments"]
        )

        connection_count = len(
            clipboard_data["connections"]
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.clipboard.copied",
                neurons=neuron_count,
                connections=connection_count,
                comments=comment_count
            ),
            4000
        )

    def cut_selected_objects(self):
        """
        Schneidet ausgewählte Neuronen und Kommentare aus.

        Die Objekte werden zunächst vollständig kopiert und
        anschließend sicher aus der Szene entfernt.
        """

        text_widget = self.get_focused_text_widget()

        if text_widget is not None:
            text_widget.cut()
            return

        clipboard_data = self.build_object_clipboard_data(
            is_cut=True
        )

        if clipboard_data is None:
            self.statusBar().showMessage(
                self.language.text("status.clipboard.nothing_to_cut"),
                3000
            )
            return

        self.object_clipboard = clipboard_data

        self.delete_selected_object()

        self.statusBar().showMessage(
            self.language.text("status.clipboard.cut"),
            3000
        )

    def paste_objects(self):
        """
        Fügt die Objekte aus der internen Zwischenablage ein.

        Beim Kopieren wird jede Einfügung leicht versetzt.
        Nach Ausschneiden bleibt die erste Einfügung an der
        ursprünglichen Position.
        """

        text_widget = self.get_focused_text_widget()

        if text_widget is not None:
            text_widget.paste()
            return

        if not isinstance(
            self.object_clipboard,
            dict
        ):
            self.statusBar().showMessage(
                self.language.text("status.clipboard.empty"),
                3000
            )
            return

        clipboard_data = self.object_clipboard

        paste_count = int(
            clipboard_data.get(
                "paste_count",
                0
            )
        )

        is_cut = bool(
            clipboard_data.get(
                "is_cut",
                False
            )
        )

        if is_cut and paste_count == 0:
            paste_offset = 0.0
        else:
            offset_number = (
                paste_count
                if is_cut
                else paste_count + 1
            )

            paste_offset = (
                30.0
                * max(
                    1,
                    offset_number
                )
            )

        self.scene.clearSelection()

        neuron_id_map = {}
        created_items = []

        for neuron_data in clipboard_data["neurons"]:
            new_neuron_id = self.scene.next_id
            self.scene.next_id += 1

            new_name = self.create_unique_pasted_neuron_name(
                neuron_data["name"],
                neuron_data["id"],
                new_neuron_id
            )

            neuron = self.scene.add_neuron(
                new_neuron_id,
                neuron_data["x"] + paste_offset,
                neuron_data["y"] + paste_offset,
                new_name,
                mark_as_modified=False
            )

            neuron.neuron_type = NeuronType(
                neuron_data["type"]
            )

            neuron.bias = float(
                neuron_data["bias"]
            )

            neuron.activation_function = (
                neuron_data["activation"]
            )

            neuron.input_value = float(
                neuron_data["input_value"]
            )

            neuron.target_value = float(
                neuron_data["target_value"]
            )

            neuron.update()

            neuron_id_map[
                neuron_data["id"]
            ] = neuron

            created_items.append(
                neuron
            )

        for comment_data in clipboard_data["comments"]:
            new_comment_id = self.scene.next_comment_id
            self.scene.next_comment_id += 1

            comment = self.scene.add_comment(
                new_comment_id,
                comment_data["x"] + paste_offset,
                comment_data["y"] + paste_offset,
                comment_data["text"],
                comment_data["width"],
                comment_data["height"],
                comment_data["font_size"],
                mark_as_modified=False
            )

            created_items.append(
                comment
            )

        for connection_data in clipboard_data["connections"]:
            source_neuron = neuron_id_map.get(
                connection_data["source"]
            )

            target_neuron = neuron_id_map.get(
                connection_data["target"]
            )

            if (
                source_neuron is None
                or target_neuron is None
            ):
                continue

            connection = self.scene.add_connection(
                self.scene.next_connection_id,
                source_neuron,
                target_neuron,
                connection_data["weight"],
                mark_as_modified=False
            )

            self.scene.next_connection_id += 1

            created_items.append(
                connection
            )

        for item in created_items:
            item.setSelected(
                True
            )

        clipboard_data["paste_count"] = (
            paste_count + 1
        )

        # Nach der ersten Einfügung verhält sich eine zuvor
        # ausgeschnittene Auswahl wie eine normale Kopie.
        clipboard_data["is_cut"] = False

        if created_items:
            self.object_selected(
                None
            )

            self.set_project_modified(
                True
            )

            self.scene.scene_geometry_changed.emit()

            self.statusBar().showMessage(
                self.language.text("status.clipboard.pasted"),
                3000
            )

    def select_all_objects(self):
        """
        Markiert alle Neuronen und Verbindungen
        in der Zeichenfläche.
        """

        self.scene.clearSelection()

        for item in self.scene.items():
            if isinstance(
                item,
                (Neuron, Connection, CommentItem)
            ):
                item.setSelected(
                    True
                )

    def delete_selected_object(self):
        """
        Löscht alle aktuell ausgewählten Objekte
        aus der Zeichenfläche.

        Verbindungen werden zuerst entfernt, damit eine
        Mehrfachauswahl mit Neuronen und Verbindungslinien
        nicht zu einer doppelten Entfernung führt.
        """

        selected_items = list(
            self.scene.selectedItems()
        )

        self.delete_graphics_items(selected_items)

    def delete_graphics_items(self, selected_items):
        """Löscht Grafikobjekte nach einer möglichen Datenwarnung."""

        selected_items = list(selected_items or [])

        if not selected_items:
            return

        answer = QMessageBox.question(
            self,
            self.language.text("dialog.delete_objects.title"),
            self.language.text(
                "dialog.delete_objects.question",
                count=len(selected_items)
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        selected_connections = [
            item
            for item in selected_items
            if isinstance(
                item,
                Connection
            )
        ]

        selected_comments = [
            item
            for item in selected_items
            if isinstance(
                item,
                CommentItem
            )
        ]

        selected_neurons = [
            item
            for item in selected_items
            if isinstance(
                item,
                Neuron
            )
        ]

        if any(
            neuron.neuron_type in (NeuronType.INPUT, NeuronType.OUTPUT)
            for neuron in selected_neurons
        ):
            answer = QMessageBox.warning(
                self,
                self.language.text("network.data_mapping_warning.title"),
                self.language.text("network.data_mapping_warning.message"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        for item in (
            selected_connections
            + selected_comments
            + selected_neurons
        ):
            if item.scene() is self.scene:
                self.scene.remove_graphics_item(
                    item
                )

        if selected_items:
            self.object_selected(
                None
            )

            self.set_project_modified(
                True
            )

    def open_neuron_edit_dialog(self, neuron):
        """Bearbeitet Name, Typ und Aktivierung eines Neurons."""

        if not isinstance(neuron, Neuron):
            return

        selected_neurons = [
            item for item in self.scene.selectedItems()
            if isinstance(item, Neuron)
        ]
        if neuron not in selected_neurons:
            selected_neurons = [neuron]
        multiple = len(selected_neurons) > 1

        dialog = QDialog(self)
        dialog.setWindowTitle(
            self.language.text("dialog.neuron_edit.title")
        )
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit(neuron.name)
        type_combo = QComboBox()
        activation_combo = QComboBox()
        activation_combo.addItems(
            [
                "Linear",
                "ReLU",
                "Sigmoid",
                "Tanh",
            ]
        )
        activation_combo.setCurrentText(
            neuron.activation_function
        )

        for neuron_type in NeuronType:
            type_combo.addItem(
                self.language.text(
                    f"properties.type.{neuron_type.value.lower()}"
                ),
                neuron_type
            )

        type_combo.setCurrentIndex(
            type_combo.findData(neuron.neuron_type)
        )
        if not multiple:
            form.addRow(
                self.language.text("properties.name"),
                name_edit
            )
            form.addRow(
                self.language.text("properties.type"),
                type_combo
            )
        form.addRow(
            self.language.text("properties.activation"),
            activation_combo
        )

        def update_activation_availability():
            activation_combo.setEnabled(
                any(
                    selected.neuron_type != NeuronType.INPUT
                    for selected in selected_neurons
                )
                if multiple
                else type_combo.currentData() != NeuronType.INPUT
            )

        type_combo.currentIndexChanged.connect(
            update_activation_availability
        )
        update_activation_availability()
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Apply
        ).setText(self.language.text("common.apply"))
        buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(self.language.text("common.cancel"))
        buttons.button(
            QDialogButtonBox.StandardButton.Apply
        ).setAutoDefault(True)
        buttons.button(
            QDialogButtonBox.StandardButton.Apply
        ).setDefault(True)
        buttons.button(
            QDialogButtonBox.StandardButton.Apply
        ).clicked.connect(dialog.accept)
        if not multiple:
            name_edit.returnPressed.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        while dialog.exec() == QDialog.DialogCode.Accepted:
            if multiple:
                new_activation = activation_combo.currentText()
                changed = False
                for selected in selected_neurons:
                    if (
                        selected.neuron_type != NeuronType.INPUT
                        and selected.activation_function != new_activation
                    ):
                        selected.activation_function = new_activation
                        selected.update()
                        changed = True
                if changed:
                    self.set_project_modified(True)
                    self.refresh_current_math_display()
                self.object_selected(neuron)
                break

            new_name = name_edit.text().strip()
            duplicate = next(
                (
                    other
                    for other in self.scene.network.get_neurons()
                    if other.id != neuron.id
                    and str(other.name).strip().casefold()
                    == new_name.casefold()
                ),
                None,
            )

            if not new_name or duplicate is not None:
                QMessageBox.warning(
                    dialog,
                    self.language.text("data.name.duplicate.title"),
                    self.language.text(
                        "data.name.empty.message"
                        if not new_name
                        else "data.name.duplicate.message",
                        name=new_name,
                    ),
                )
                continue

            new_type = type_combo.currentData()
            new_activation = activation_combo.currentText()
            old_type = neuron.neuron_type
            data_types = {NeuronType.INPUT, NeuronType.OUTPUT}

            if (
                new_type != old_type
                and (old_type in data_types or new_type in data_types)
            ):
                answer = QMessageBox.warning(
                    dialog,
                    self.language.text("network.data_mapping_warning.title"),
                    self.language.text("network.data_mapping_warning.message"),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    continue

            changed = False
            if new_name != neuron.name:
                neuron.name = new_name
                self.synchronize_neuron_name_in_data(neuron, new_name)
                changed = True

            if isinstance(new_type, NeuronType) and new_type != old_type:
                neuron.prepareGeometryChange()
                neuron.neuron_type = new_type
                neuron.update_connections()
                changed = True

            if (
                new_type != NeuronType.INPUT
                and new_activation != neuron.activation_function
            ):
                neuron.activation_function = new_activation
                changed = True

            if changed:
                neuron.update()
                self.set_project_modified(True)
                self.refresh_current_math_display()

            self.object_selected(neuron)
            break

    def open_comment_edit_dialog(self, comment):
        """Bearbeitet Kommentartext und Schriftgröße gemeinsam."""

        if not isinstance(comment, CommentItem):
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(
            self.language.text("comment.edit.title")
        )
        dialog.setModal(True)
        dialog.resize(440, 300)

        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(self.language.text("comment.edit.text"))
        )

        text_edit = QPlainTextEdit(comment.text)
        text_edit.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        layout.addWidget(text_edit, 1)

        form = QFormLayout()
        font_size = QSpinBox()
        font_size.setRange(8, 48)
        font_size.setValue(comment.font_size)
        font_size.setSuffix(" pt")
        form.addRow(
            self.language.text("properties.comment.font_size"),
            font_size
        )
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = buttons.button(
            QDialogButtonBox.StandardButton.Apply
        )
        apply_button.setText(self.language.text("common.apply"))
        apply_button.setAutoDefault(False)
        apply_button.setDefault(False)
        buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(self.language.text("common.cancel"))
        apply_button.clicked.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        for sequence in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(sequence), dialog)
            shortcut.activated.connect(dialog.accept)

        text_edit.setFocus()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_text = text_edit.toPlainText()
        new_font_size = font_size.value()
        changed = (
            new_text != comment.text
            or new_font_size != comment.font_size
        )
        if not changed:
            return

        comment.set_text(new_text, mark_as_modified=False)
        comment.set_font_size(new_font_size, mark_as_modified=False)
        comment.content_changed.emit()
        self.object_selected(comment)

    def confirm_training_data_replacement(self):
        """
        Sichert auf Wunsch geänderte Trainingsdaten, bevor
        sie durch eine neue leere Struktur ersetzt werden.
        """

        if not self.training_data_manager.has_document:
            return True

        if self.training_data_manager.modified:
            result = QMessageBox.warning(
                self,
                self.language.text("data.replace.title"),
                self.language.text("data.replace.modified_question"),
                (
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel
                ),
                QMessageBox.StandardButton.Save
            )

            if (
                result
                == QMessageBox.StandardButton.Cancel
            ):
                return False

            if (
                result
                == QMessageBox.StandardButton.Discard
            ):
                return True

            try:
                if self.training_data_manager.file_path:
                    self.training_data_manager.save()
                    return True

                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    self.language.text("data.save.title", data_label=self.language.text("test.data.training")),
                    self.get_project_data_directory(
                        "trainingsdaten"
                    ),
                    self.language.text("data.file_filter.training")
                )

                if not file_path:
                    return False

                self.training_data_manager.save_as(
                    file_path
                )

                return True

            except (
                OSError,
                TypeError,
                ValueError
            ) as error:
                QMessageBox.critical(
                    self,
                    self.language.text("data.save.error_title", data_label=self.language.text("test.data.training")),
                    str(
                        error
                    )
                )

                return False

        result = QMessageBox.question(
            self,
            self.language.text("data.replace.title"),
            self.language.text("data.replace.question"),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No
        )

        return (
            result
            == QMessageBox.StandardButton.Yes
        )

    def clear_network_objects(self):
        """
        Entfernt ausschließlich Neuronen und Verbindungen.

        Kommentare bleiben erhalten.
        """

        self.scene.cancel_connection()
        self.scene.clearSelection()

        for connection in list(
            self.scene.network.get_connections()
        ):
            if connection.scene() is self.scene:
                self.scene.remove_graphics_item(
                    connection
                )

        for neuron in list(
            self.scene.network.get_neurons()
        ):
            if neuron.scene() is self.scene:
                self.scene.remove_graphics_item(
                    neuron
                )

        self.scene.next_id = 1
        self.scene.next_connection_id = 1

        self.current_object = None

        self.object_selected(
            None
        )

    def open_network_create_dialog(self, start_new_project=False):
        """
        Öffnet den Dialog zur automatischen Erzeugung
        eines vollständig angeordneten Netzwerkes.
        """

        dialog = NetworkCreateDialog(
            language_manager=self.language,
            parent=self
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        settings = dialog.get_settings()

        if start_new_project:
            if not self.confirm_unsaved_changes():
                return
            self.initialize_new_project()

        if settings["create_training_data"]:
            if not self.confirm_training_data_replacement():
                return

        previous_snapshot = (
            self.capture_editor_snapshot(
                include_training_data=(
                    settings[
                        "create_training_data"
                    ]
                )
            )
        )

        self._history_timer.stop()

        created_layers = []
        created_connection_count = 0
        generation_error = None

        previous_signal_state = self.scene.blockSignals(
            True
        )

        try:
            existing_after_clear = list(
                self.scene.network.get_neurons()
            )

            if existing_after_clear:
                start_x = (
                    max(
                        neuron.sceneBoundingRect().right()
                        for neuron in existing_after_clear
                    )
                    + 180.0
                )
            else:
                start_x = 80.0

            layer_counts = [
                settings["input_count"]
            ]

            layer_counts.extend(
                settings["hidden_layer_sizes"]
            )

            layer_counts.append(
                settings["output_count"]
            )

            maximum_layer_count = max(
                layer_counts
            )

            # Großzügigere automatische Anordnung.
            #
            # Horizontal bleibt mehr Platz für Verbindungslinien
            # und Gewichtsanzeigen. Vertikal überlappen sich auch
            # größere Neuronendarstellungen nicht mehr.
            layer_spacing = 400.0 + min(
                320.0,
                max(0, maximum_layer_count - 4) * 18.0
            )
            neuron_spacing = 225.0
            top_margin = 100.0

            for layer_index, layer_count in enumerate(
                layer_counts
            ):
                layer_neurons = []

                layer_height = (
                    (layer_count - 1)
                    * neuron_spacing
                )

                maximum_height = (
                    (maximum_layer_count - 1)
                    * neuron_spacing
                )

                start_y = (
                    top_margin
                    + (
                        maximum_height
                        - layer_height
                    )
                    / 2.0
                )

                for neuron_index in range(
                    layer_count
                ):
                    neuron_id = self.scene.next_id
                    self.scene.next_id += 1

                    neuron = self.scene.add_neuron(
                        neuron_id,
                        (
                            start_x
                            + layer_index
                            * layer_spacing
                        ),
                        (
                            start_y
                            + neuron_index
                            * neuron_spacing
                        ),
                        f"N{neuron_id}",
                        mark_as_modified=False
                    )

                    if layer_index == 0:
                        neuron.neuron_type = (
                            NeuronType.INPUT
                        )

                        neuron.activation_function = (
                            "Linear"
                        )

                    elif (
                        layer_index
                        == len(layer_counts) - 1
                    ):
                        neuron.neuron_type = (
                            NeuronType.OUTPUT
                        )

                        neuron.activation_function = (
                            settings[
                                "output_activation"
                            ]
                        )

                    else:
                        neuron.neuron_type = (
                            NeuronType.HIDDEN
                        )

                        neuron.activation_function = (
                            settings[
                                "hidden_activation"
                            ]
                        )

                    neuron.bias = 0.0
                    neuron.input_value = 0.0
                    neuron.target_value = 0.0

                    neuron.update()

                    layer_neurons.append(
                        neuron
                    )

                created_layers.append(
                    layer_neurons
                )

            if settings["fully_connected"]:
                for layer_index in range(
                    len(created_layers) - 1
                ):
                    source_layer = (
                        created_layers[
                            layer_index
                        ]
                    )

                    target_layer = (
                        created_layers[
                            layer_index + 1
                        ]
                    )

                    for source_neuron in source_layer:
                        for target_neuron in target_layer:
                            self.scene.add_connection(
                                self.scene.next_connection_id,
                                source_neuron,
                                target_neuron,
                                1.0,
                                mark_as_modified=False
                            )

                            self.scene.next_connection_id += 1
                            created_connection_count += 1

            if settings["create_training_data"]:
                training_document = (
                    TrainingDataIO.create_document_for_network(
                        self.scene.network.get_input_neurons(),
                        self.scene.network.get_output_neurons()
                    )
                )

                self.training_data_manager.set_document(
                    training_document,
                    file_path=None,
                    modified=True
                )

        except Exception as error:
            generation_error = error

        finally:
            self.scene.blockSignals(
                previous_signal_state
            )

        if generation_error is not None:
            self.restore_editor_snapshot(
                previous_snapshot
            )

            QMessageBox.critical(
                self,
                self.language.text("network.create.error_title"),
                str(
                    generation_error
                )
            )

            return

        self.scene.scene_geometry_changed.emit()
        self.scene.update()
        self.view.viewport().update()

        self.commit_explicit_history_step(
            previous_snapshot
        )

        created_neuron_count = sum(
            len(
                layer
            )
            for layer in created_layers
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.network.created",
                neurons=created_neuron_count,
                connections=created_connection_count
            ),
            7000
        )

        QTimer.singleShot(
            0,
            self.view.fit_all
        )

        if settings["create_training_data"]:
            QTimer.singleShot(
                0,
                self.open_training_data_dialog
            )

    def open_network_from_training_data_dialog(self, start_new_project=False):
        """Erzeugt Tabelle, Skalierung und Netzwerk in einem getrennten Ablauf."""

        existing_neurons = (
            []
            if start_new_project
            else list(self.scene.network.get_neurons())
        )
        dialog = NetworkFromTrainingDataDialog(
            existing_network=bool(existing_neurons),
            default_directory=self.get_project_data_directory("trainingsdaten"),
            language_manager=self.language,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        result = dialog.get_result()

        if start_new_project:
            if not self.confirm_unsaved_changes():
                return
            self.initialize_new_project()
            existing_neurons = []

        if existing_neurons:
            answer = QMessageBox.warning(
                self,
                self.language.text("network.create.replace_title"),
                self.language.text("network.create.replace_question"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if not self.confirm_training_data_replacement():
            return

        previous_snapshot = self.capture_editor_snapshot(
            include_training_data=True
        )
        self._history_timer.stop()
        created_layers = []
        created_connection_count = 0
        generation_error = None
        previous_signal_state = self.scene.blockSignals(True)

        try:
            self.clear_network_objects()

            document = deepcopy(result["training_document"])
            input_columns = [
                column
                for column in document.get("columns", [])
                if column.get("role") == "input"
            ]
            output_columns = [
                column
                for column in document.get("columns", [])
                if column.get("role") == "output"
            ]

            layer_counts = [result["input_count"]]
            layer_counts.extend(result["hidden_layer_sizes"])
            layer_counts.append(result["output_count"])
            maximum_layer_count = max(layer_counts)
            layer_spacing = 400.0 + min(
                320.0,
                max(0, maximum_layer_count - 4) * 18.0
            )
            neuron_spacing = 225.0
            top_margin = 100.0

            for layer_index, layer_count in enumerate(layer_counts):
                layer_neurons = []
                layer_height = (layer_count - 1) * neuron_spacing
                maximum_height = (maximum_layer_count - 1) * neuron_spacing
                start_y = top_margin + (maximum_height - layer_height) / 2.0

                for neuron_index in range(layer_count):
                    neuron_id = self.scene.next_id
                    self.scene.next_id += 1
                    if layer_index == 0:
                        name = str(
                            input_columns[neuron_index].get("name")
                            or f"N{neuron_id}"
                        )
                    elif layer_index == len(layer_counts) - 1:
                        name = str(
                            output_columns[neuron_index].get("name")
                            or f"N{neuron_id}"
                        )
                    else:
                        name = f"N{neuron_id}"

                    neuron = self.scene.add_neuron(
                        neuron_id,
                        80.0 + layer_index * layer_spacing,
                        start_y + neuron_index * neuron_spacing,
                        name,
                        mark_as_modified=False,
                    )

                    if layer_index == 0:
                        neuron.neuron_type = NeuronType.INPUT
                        neuron.activation_function = "Linear"
                    elif layer_index == len(layer_counts) - 1:
                        neuron.neuron_type = NeuronType.OUTPUT
                        neuron.activation_function = result[
                            "output_activations"
                        ][neuron_index]
                    else:
                        neuron.neuron_type = NeuronType.HIDDEN
                        neuron.activation_function = result[
                            "hidden_activation"
                        ]

                    neuron.bias = 0.0
                    neuron.input_value = 0.0
                    neuron.target_value = 0.0
                    neuron.update()
                    layer_neurons.append(neuron)

                created_layers.append(layer_neurons)

            if result["fully_connected"]:
                for layer_index in range(len(created_layers) - 1):
                    for source_neuron in created_layers[layer_index]:
                        for target_neuron in created_layers[layer_index + 1]:
                            self.scene.add_connection(
                                self.scene.next_connection_id,
                                source_neuron,
                                target_neuron,
                                1.0,
                                mark_as_modified=False,
                            )
                            self.scene.next_connection_id += 1
                            created_connection_count += 1

            created_inputs = created_layers[0]
            created_outputs = created_layers[-1]
            for column, neuron in zip(input_columns, created_inputs):
                column["mapped_neuron_id"] = neuron.id
                column["mapped_neuron_name"] = neuron.name
            for column, neuron in zip(output_columns, created_outputs):
                column["mapped_neuron_id"] = neuron.id
                column["mapped_neuron_name"] = neuron.name

            self.training_data_manager.set_document(
                document,
                file_path=result["training_file_path"],
                modified=True,
            )

        except Exception as error:
            generation_error = error
        finally:
            self.scene.blockSignals(previous_signal_state)

        if generation_error is not None:
            self.restore_editor_snapshot(previous_snapshot)
            QMessageBox.critical(
                self,
                self.language.text("network.create.error_title"),
                str(generation_error),
            )
            return

        self.scene.scene_geometry_changed.emit()
        self.scene.update()
        self.view.viewport().update()
        self.commit_explicit_history_step(previous_snapshot)

        created_neuron_count = sum(len(layer) for layer in created_layers)
        self.statusBar().showMessage(
            self.language.text(
                "status.network.created_from_data",
                neurons=created_neuron_count,
                connections=created_connection_count,
                records=len(result["training_document"].get("records", [])),
            ),
            8000,
        )
        QTimer.singleShot(0, self.view.fit_all)

    def apply_network_layout_positions(self, positions):
        """Wendet eine Layoutvorschau ohne einzelne Verlaufsschritte an."""

        previous_signal_state = self.scene.blockSignals(
            True
        )

        try:
            for neuron, position in positions.items():
                neuron.setPos(
                    position
                )
        finally:
            self.scene.blockSignals(
                previous_signal_state
            )

        self.scene.scene_geometry_changed.emit()
        self.scene.update()
        self.view.viewport().update()

        if isinstance(self.current_object, Neuron):
            self.object_position_changed(
                self.current_object
            )

    def reconcile_data_mappings(self, manager):
        """Repariert nur eindeutige Input-/Output-Zuordnungen eines Datensatzes."""

        if manager is None or not manager.has_document:
            return False

        document = manager.document
        columns = document.get("columns", [])
        changed = False

        for role, neuron_type, neurons in (
            ("input", NeuronType.INPUT, self.scene.network.get_input_neurons()),
            ("output", NeuronType.OUTPUT, self.scene.network.get_output_neurons()),
        ):
            role_columns = [
                column
                for column in columns
                if isinstance(column, dict) and column.get("role") == role
            ]
            neurons = list(neurons)

            # Eine Zuordnung nach Reihenfolge ist nur eindeutig, wenn beide
            # Seiten gleich viele Elemente besitzen.
            if len(role_columns) != len(neurons):
                continue

            neurons_by_id = {neuron.id: neuron for neuron in neurons}
            neurons_by_name = {
                str(neuron.name).strip().casefold(): neuron
                for neuron in neurons
            }
            used_ids = set()

            for column_index, column in enumerate(role_columns):
                neuron = neurons_by_id.get(column.get("mapped_neuron_id"))
                if neuron is not None and neuron.id in used_ids:
                    neuron = None

                if neuron is None:
                    for candidate_name in (
                        column.get("mapped_neuron_name"),
                        column.get("name"),
                    ):
                        normalized_name = str(candidate_name or "").strip().casefold()
                        candidate = neurons_by_name.get(normalized_name)
                        if candidate is not None and candidate.id not in used_ids:
                            neuron = candidate
                            break

                if neuron is None:
                    candidate = neurons[column_index]
                    if candidate.id not in used_ids:
                        neuron = candidate

                if neuron is None or neuron.neuron_type != neuron_type:
                    continue

                used_ids.add(neuron.id)
                if (
                    column.get("mapped_neuron_id") != neuron.id
                    or column.get("mapped_neuron_name") != neuron.name
                ):
                    column["mapped_neuron_id"] = neuron.id
                    column["mapped_neuron_name"] = neuron.name
                    changed = True

        if changed:
            manager.set_document(
                document,
                file_path=manager.file_path,
                modified=True,
            )

        return changed

    def reconcile_active_data_mappings(self):
        """Repariert Zuordnungen aller aktuell geladenen Datensätze."""

        training_changed = self.reconcile_data_mappings(
            self.training_data_manager
        )
        test_changed = self.reconcile_data_mappings(
            self.test_data_manager
        )
        return training_changed or test_changed

    def open_network_structure_dialog(self):
        """Baut nur die Hidden-Schichten eines vorhandenen Netzwerkes neu auf."""

        network = self.scene.network
        input_neurons = list(network.get_input_neurons())
        output_neurons = list(network.get_output_neurons())

        if not input_neurons or not output_neurons:
            QMessageBox.information(
                self,
                self.language.text("network.structure.title"),
                self.language.text("network.structure.missing_io"),
            )
            return

        try:
            topological_layers = network.get_topological_layers()
        except ValueError as error:
            QMessageBox.warning(
                self,
                self.language.text("network.structure.error_title"),
                str(error),
            )
            return

        hidden_layers = [
            [
                neuron
                for neuron in layer
                if neuron.neuron_type == NeuronType.HIDDEN
            ]
            for layer in topological_layers
        ]
        hidden_layers = [layer for layer in hidden_layers if layer]
        old_sizes = [len(layer) for layer in hidden_layers]

        # Den vorhandenen horizontalen Schichtabstand vor dem Umbau
        # ermitteln. Der Median bleibt auch bei einer einzeln manuell
        # verschobenen Schicht stabil.
        existing_layout_layers = [
            input_neurons,
            *hidden_layers,
            output_neurons,
        ]
        layer_centers_x = [
            sum(neuron.x() for neuron in layer) / len(layer)
            for layer in existing_layout_layers
            if layer
        ]
        horizontal_gaps = sorted(
            abs(layer_centers_x[index + 1] - layer_centers_x[index])
            for index in range(len(layer_centers_x) - 1)
            if abs(layer_centers_x[index + 1] - layer_centers_x[index]) > 1.0
        )
        if horizontal_gaps:
            middle = len(horizontal_gaps) // 2
            horizontal_spacing = (
                horizontal_gaps[middle]
                if len(horizontal_gaps) % 2
                else (horizontal_gaps[middle - 1] + horizontal_gaps[middle]) / 2.0
            )
        else:
            horizontal_spacing = 400.0

        dialog = NetworkStructureDialog(
            old_sizes,
            language_manager=self.language,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_sizes = dialog.hidden_sizes()
        if new_sizes == old_sizes:
            return

        layer_counts = [len(input_neurons), *new_sizes, len(output_neurons)]
        horizontal_spacing = max(
            horizontal_spacing,
            400.0 + min(
                320.0,
                max(0, max(layer_counts) - 4) * 18.0
            )
        )
        connection_count = sum(
            layer_counts[index] * layer_counts[index + 1]
            for index in range(len(layer_counts) - 1)
        )

        if sum(layer_counts) > 500:
            QMessageBox.warning(
                self,
                self.language.text("network.create.too_large.title"),
                self.language.text("network.create.too_many_neurons"),
            )
            return

        if connection_count > 50000:
            QMessageBox.warning(
                self,
                self.language.text("network.create.too_large.title"),
                self.language.text("network.create.too_many_connections"),
            )
            return

        confirmation = QMessageBox.question(
            self,
            self.language.text("network.structure.confirm_title"),
            self.language.text("network.structure.confirm_text"),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        previous_snapshot = self.capture_editor_snapshot(
            include_training_data=True,
            include_test_data=True,
        )
        self._history_timer.stop()
        previous_signal_state = self.scene.blockSignals(True)
        rebuild_error = None

        old_hidden = list(network.get_hidden_neurons())
        hidden_activation = (
            old_hidden[0].activation_function
            if old_hidden
            else "Sigmoid"
        )
        all_existing = input_neurons + old_hidden + output_neurons
        center_x = sum(neuron.x() for neuron in all_existing) / len(all_existing)
        center_y = sum(neuron.y() for neuron in all_existing) / len(all_existing)

        try:
            for connection in list(network.get_connections()):
                self.scene.remove_graphics_item(connection)

            for neuron in old_hidden:
                self.scene.remove_graphics_item(neuron)

            layers = [input_neurons]

            for layer_size in new_sizes:
                layer = []
                for _ in range(layer_size):
                    neuron_id = self.scene.next_id
                    self.scene.next_id += 1
                    neuron = self.scene.add_neuron(
                        neuron_id,
                        0.0,
                        0.0,
                        f"N{neuron_id}",
                        mark_as_modified=False,
                    )
                    neuron.neuron_type = NeuronType.HIDDEN
                    neuron.activation_function = hidden_activation
                    neuron.bias = 0.0
                    neuron.input_value = 0.0
                    neuron.target_value = 0.0
                    neuron.update()
                    layer.append(neuron)
                layers.append(layer)

            layers.append(output_neurons)

            vertical_spacing = 225.0
            total_width = (len(layers) - 1) * horizontal_spacing
            start_x = center_x - total_width / 2.0

            for layer_index, layer in enumerate(layers):
                layer_height = (len(layer) - 1) * vertical_spacing
                start_y = center_y - layer_height / 2.0
                for neuron_index, neuron in enumerate(layer):
                    neuron.setPos(
                        start_x + layer_index * horizontal_spacing,
                        start_y + neuron_index * vertical_spacing,
                    )

            for layer_index in range(len(layers) - 1):
                for source_neuron in layers[layer_index]:
                    for target_neuron in layers[layer_index + 1]:
                        self.scene.add_connection(
                            self.scene.next_connection_id,
                            source_neuron,
                            target_neuron,
                            1.0,
                            mark_as_modified=False,
                        )
                        self.scene.next_connection_id += 1

            # Frühere Trainingszustände gehören zur alten Topologie.
            self.training_history = []
            self.active_training_run_id = None
            self.analysis_tolerances = {}
            self.reconcile_active_data_mappings()

        except Exception as error:
            rebuild_error = error
        finally:
            self.scene.blockSignals(previous_signal_state)

        if rebuild_error is not None:
            self.restore_editor_snapshot(previous_snapshot)
            QMessageBox.critical(
                self,
                self.language.text("network.structure.error_title"),
                str(rebuild_error),
            )
            return

        self.current_object = None
        self.object_selected(None)
        self.scene.scene_geometry_changed.emit()
        self.scene.update()
        self.view.viewport().update()
        self.commit_explicit_history_step(previous_snapshot)
        self.statusBar().showMessage(
            self.language.text(
                "status.network.structure_changed",
                structure=" → ".join(str(count) for count in layer_counts),
            ),
            7000,
        )
        QTimer.singleShot(0, self.view.fit_all)

    def open_network_layout_dialog(self):
        """Ordnet das vorhandene Netzwerk automatisch in Schichten an."""

        neurons = list(
            self.scene.network.get_neurons()
        )

        if not neurons:
            QMessageBox.information(
                self,
                self.language.text("network.layout.title"),
                self.language.text("network.layout.no_neurons")
            )
            return

        original_positions = {
            neuron: neuron.pos()
            for neuron in neurons
        }
        previous_snapshot = self.capture_editor_snapshot()
        self._history_timer.stop()

        try:
            dialog = NetworkLayoutDialog(
                self.scene.network,
                self,
                language_manager=self.language
            )
        except ValueError as error:
            QMessageBox.warning(
                self,
                self.language.text("network.layout.error_title"),
                str(error)
            )
            return

        dialog.preview_changed.connect(
            self.apply_network_layout_positions
        )

        result = dialog.exec()

        if result != dialog.DialogCode.Accepted:
            self.apply_network_layout_positions(
                original_positions
            )
            self.statusBar().showMessage(
                self.language.text("status.network.layout_discarded"),
                3000
            )
            return

        # Auch ohne eine Änderung der Abstandsfelder muss OK die vom Dialog
        # berechnete Anordnung anwenden. Die Live-Vorschau wird sonst nicht
        # ausgelöst und das Netzwerk bliebe unverändert.
        self.apply_network_layout_positions(
            dialog.positions()
        )

        changed = any(
            neuron.pos() != original_positions[neuron]
            for neuron in neurons
        )

        if not changed:
            return

        self.commit_explicit_history_step(
            previous_snapshot
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.network.arranged",
                neurons=len(neurons),
                layers=dialog.structure["output_layer"] + 1
            ),
            6000
        )

        QTimer.singleShot(
            0,
            self.view.fit_all
        )

    def validate_network(self):
        """
        Prüft die Struktur des aktuellen Netzwerkes
        und zeigt das Ergebnis an.
        """

        result = (
            self.scene.network.validate_network(
                translator=self.language.text
            )
        )

        summary = self.language.text(
            "network.validation.summary",
            inputs=result["input_count"],
            hidden=result["hidden_count"],
            outputs=result["output_count"],
            connections=result["connection_count"]
        )

        if result["valid"]:
            QMessageBox.information(
                self,
                self.language.text("network.validation.title"),
                self.language.text(
                    "network.validation.success",
                    summary=summary
                )
            )

            return

        error_text = "\n".join(
            f"• {error}"
            for error in result["errors"]
        )

        QMessageBox.warning(
            self,
            self.language.text("network.validation.title"),
            self.language.text(
                "network.validation.failed",
                summary=summary,
                errors=error_text
            )
        )

    def forward_pass(self):
        """
        Führt eine vollständige Vorwärtsberechnung
        des aktuellen Netzwerkes durch.
        """

        if self.training_data_manager.has_document:
            try:
                records, input_columns, output_columns = (
                    NetworkTestDialog.prepare_document(
                        self.scene.network,
                        self.training_data_manager.document,
                        data_label=self.language.text("test.data.training"),
                        translator=self.language.text
                    )
                )

                input_state_before = {
                    mapping["neuron"].id: float(mapping["neuron"].input_value)
                    for mapping in input_columns
                }

                dialog = ForwardCalibrationDialog(
                    self.scene.network,
                    input_columns,
                    output_columns,
                    records=records,
                    file_path=self.training_data_manager.file_path,
                    input_array=self.training_data_manager.document.get(
                        "input_array"
                    ),
                    training_document=self.training_data_manager.document,
                    parent=self,
                    language_manager=self.language,
                    color_settings=self.display_settings.get("colors", {}),
                )
                dialog.calculation_updated.connect(
                    lambda: self.show_neuron_properties(
                        self.current_object
                    )
                    if isinstance(self.current_object, Neuron)
                    else None
                )
                dialog.exec()

                if any(
                    not math.isclose(
                        input_state_before.get(mapping["neuron"].id, 0.0),
                        float(mapping["neuron"].input_value),
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    )
                    for mapping in input_columns
                ):
                    self.set_project_modified(True)

                if dialog.training_document_modified:
                    self.training_data_manager.set_document(
                        dialog.training_document,
                        file_path=self.training_data_manager.file_path,
                        modified=True
                    )

                if isinstance(self.current_object, Neuron):
                    self.show_neuron_properties(
                        self.current_object
                    )

                if dialog.calculation_performed:
                    self.statusBar().showMessage(
                        self.language.text("status.forward.completed"),
                        5000
                    )

                return

            except (TypeError, ValueError):
                # Sind die Trainingsdaten nicht vollständig zugeordnet,
                # bleibt die bisherige direkte Berechnung verfügbar.
                pass

        try:
            output_neurons = (
                self.scene.network.forward_pass()
            )

        except ValueError as error:
            QMessageBox.warning(
                self,
                self.language.text("forward.message.title"),
                str(
                    error
                )
            )

            return

        output_lines = []

        for neuron in output_neurons:
            output_lines.append(
                f"{neuron.name}: {format_number(neuron.output_value)}"
            )

        if output_lines:
            output_text = "\n".join(
                output_lines
            )

        else:
            output_text = self.language.text("forward.no_outputs")

        QMessageBox.information(
            self,
            self.language.text("forward.message.title"),
            self.language.text(
                "forward.direct.completed",
                outputs=output_text
            )
        )

        if isinstance(
            self.current_object,
            Neuron
        ):
            self.show_neuron_properties(
                self.current_object
            )

        self.statusBar().showMessage(
            self.language.text("status.forward.completed"),
            5000
        )

    def open_graphical_experiment(self):
        """Öffnet das projektbezogene grafische Experiment direkt."""

        if not self.network_data_functions_available():
            return
        try:
            records, input_columns, output_columns = (
                NetworkTestDialog.prepare_document(
                    self.scene.network,
                    self.training_data_manager.document,
                    data_label=self.language.text("test.data.training"),
                    translator=self.language.text,
                )
            )
            initial_values = {
                mapping["neuron"].id: TrainingDataIO.unscale_value(
                    mapping["neuron"].input_value,
                    mapping["calibration"],
                    self.language.text,
                )
                for mapping in input_columns
            }
            dialog = GraphicalExperimentDialog(
                self.scene.network,
                input_columns,
                output_columns,
                records=records,
                file_path=(
                    self.current_project_path
                    or self.training_data_manager.file_path
                ),
                input_array=self.training_data_manager.document.get("input_array"),
                color_settings=self.display_settings.get("colors", {}),
                initial_input_values=initial_values,
                language_manager=self.language,
                parent=self,
            )
            viewport = self.view.viewport()
            viewport.setUpdatesEnabled(False)
            try:
                dialog.exec()
            finally:
                viewport.setUpdatesEnabled(True)
                self.scene.update()
                viewport.update()
            if isinstance(self.current_object, Neuron):
                self.show_neuron_properties(self.current_object)
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("forward.message.title"),
                str(error),
            )


    def training_data_state_changed(self):
        """
        Aktualisiert den sichtbaren Status der zentral
        verwalteten Trainingsdatendatei.
        """

        self.update_status_summary()
        self.update_result_analysis_action_state()
        self.update_project_workflow()

        if not self.training_data_manager.has_document:
            self.statusBar().showMessage(
                self.language.text("status.data.no_training_loaded"),
                3000
            )
            return

        modified_marker = (
            " *"
            if self.training_data_manager.modified
            else ""
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.data.training",
                name=self.training_data_manager.display_name,
                marker=modified_marker,
                count=self.training_data_manager.record_count
            ),
            5000
        )

    def update_test_data_actions(self):
        """Aktiviert die Befehle, die geladene Testdaten benötigen."""

        has_test_data = self.test_data_manager.has_document

        if self.training_observation_mode:
            self.action_edit_test_data.setEnabled(False)
            self.action_remove_test_data.setEnabled(False)
            self.action_test_with_test_data.setEnabled(False)
            return

        # Der Editor bleibt auch ohne Zuordnung erreichbar und
        # kann dann eine neue Testdatendatei anlegen.
        self.action_edit_test_data.setEnabled(
            True
        )
        self.action_remove_test_data.setEnabled(
            has_test_data
        )
        self.action_test_with_test_data.setEnabled(
            has_test_data
        )
        disabled_tooltip = self.language.text(
            "tooltip.disabled.test_data_required"
        )
        self.action_remove_test_data.setToolTip(
            self.language.text("action.remove_test_data")
            if has_test_data else disabled_tooltip
        )
        self.action_test_with_test_data.setToolTip(
            self.language.text("tooltip.test")
            if has_test_data else disabled_tooltip
        )

    def open_project_assistant(self):
        """Öffnet den projektunabhängigen Assistenten für eigene Projekte."""

        dialog = ProjectAssistantDialog(
            saved_selections=Settings.get_project_assistant_selections(),
            language_manager=self.language,
            parent=self
        )
        dialog.exec()

        try:
            Settings.save_project_assistant_selections(
                dialog.selection_values()
            )
        except OSError as error:
            QMessageBox.warning(
                self,
                self.language.text("dialog.settings_save_error.title"),
                self.language.text(
                    "dialog.settings_save_error.message",
                    error=error
                )
            )

    def test_data_state_changed(self):
        """Aktualisiert Menü und Status nach einer Testdatenänderung."""

        if hasattr(self, "action_edit_test_data"):
            self.update_test_data_actions()

        self.update_status_summary()
        self.update_project_workflow()

        if not self.test_data_manager.has_document:
            return

        modified_marker = (
            " *"
            if self.test_data_manager.modified
            else ""
        )
        self.statusBar().showMessage(
            self.language.text(
                "status.data.test",
                name=self.test_data_manager.display_name,
                marker=modified_marker,
                count=self.test_data_manager.record_count
            ),
            5000
        )

    def open_test_data_dialog(self):
        """Bearbeitet die dem Projekt zugeordneten Testdaten."""

        self.reconcile_active_data_mappings()

        previous_file_path = self.test_data_manager.file_path
        test_document = self.test_data_manager.document

        if test_document is None:
            accepted, test_document = (
                TrainingDataDialog.create_test_document_from_training(
                    self.training_data_manager.document,
                    self,
                    self.language
                )
            )

            if not accepted:
                return

        dialog = TrainingDataDialog(
            self.scene.network,
            test_document,
            self.test_data_manager.file_path,
            parent=self,
            document_modified=self.test_data_manager.modified,
            data_label=self.language.text("test.data.test"),
            data_extension=".nntest",
            default_directory=self.get_project_data_directory(
                "testdaten"
            ),
            training_document=self.training_data_manager.document,
            training_file_path=self.training_data_manager.file_path,
            language_manager=self.language,
            color_settings=self.display_settings.get("colors", {}),
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self.test_data_manager.set_document(
            dialog.document,
            file_path=dialog.current_file_path,
            modified=dialog.modified
        )

        if (
            previous_file_path != self.test_data_manager.file_path
            or previous_file_path is None
            or dialog.modified
        ):
            self.set_project_modified(
                True
            )

    def remove_test_data_association(self):
        """Entfernt nur die Projektzuordnung, nicht die Testdatendatei."""

        if not self.test_data_manager.has_document:
            return

        question = self.language.text("test.association.remove_question")

        if self.test_data_manager.modified:
            question += "\n\n" + self.language.text("test.association.unsaved_warning")

        answer = QMessageBox.question(
            self,
            self.language.text("test.association.remove_title"),
            question,
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.test_data_manager.clear()
        self.set_project_modified(
            True
        )
        self.statusBar().showMessage(
            self.language.text("status.test.association_removed"),
            4000
        )

    def test_network_with_test_data(self):
        """Berechnet alle Testdaten, ohne das Netzwerk zu trainieren."""

        validation_result = self.scene.network.validate_network(
            translator=self.language.text
        )

        if not validation_result["valid"]:
            QMessageBox.warning(
                self,
                self.language.text("test.test_data.title"),
                self.language.text("test.network_invalid", errors="\n".join(validation_result["errors"]))
            )
            return

        if not self.test_data_manager.has_document:
            QMessageBox.information(
                self,
                self.language.text("test.test_data.title"),
                self.language.text("test.test_data.select_first")
            )
            return

        calibration_differences = (
            self.get_test_calibration_differences()
        )

        if calibration_differences:
            message_box = QMessageBox(self)
            message_box.setWindowTitle(
                self.language.text("test.scaling_difference.title")
            )
            message_box.setIcon(
                QMessageBox.Icon.Warning
            )
            message_box.setText(
                self.language.text("test.scaling_difference.text")
            )
            message_box.setInformativeText(
                "\n".join(calibration_differences)
                + "\n\n" + self.language.text("test.scaling_difference.consequence")
            )
            test_button = message_box.addButton(
                self.language.text("test.scaling_difference.continue"),
                QMessageBox.ButtonRole.AcceptRole
            )
            cancel_button = message_box.addButton(
                self.language.text("common.cancel"),
                QMessageBox.ButtonRole.RejectRole
            )
            message_box.setDefaultButton(cancel_button)
            message_box.exec()

            if message_box.clickedButton() is not test_button:
                return

        try:
            records, input_columns, output_columns = (
                NetworkTestDialog.prepare_document(
                    self.scene.network,
                    self.test_data_manager.document,
                    data_label=self.language.text("test.data.test"),
                    translator=self.language.text
                )
            )
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("test.test_data.invalid_title"),
                str(error)
            )
            return

        self.open_test_analysis_window(
            initial_tab=0,
            initial_source_kind="test"
        )

    def test_network_with_training_data(self):
        """Berechnet alle Trainingsdaten, ohne das Netzwerk zu trainieren."""

        self.reconcile_active_data_mappings()

        validation_result = self.scene.network.validate_network(
            translator=self.language.text
        )

        if not validation_result["valid"]:
            QMessageBox.warning(
                self,
                self.language.text("test.training_data.title"),
                self.language.text("test.network_invalid", errors="\n".join(validation_result["errors"]))
            )
            return

        if not self.training_data_manager.has_document:
            QMessageBox.information(
                self,
                self.language.text("test.training_data.title"),
                self.language.text("test.training_data.open_first")
            )
            return

        try:
            records, input_columns, output_columns = (
                NetworkTestDialog.prepare_document(
                    self.scene.network,
                    self.training_data_manager.document,
                    data_label=self.language.text("test.data.training"),
                    translator=self.language.text
                )
            )
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("test.training_data.invalid_title"),
                str(error)
            )
            return

        self.open_test_analysis_window(
            initial_tab=0,
            initial_source_kind="training"
        )

    def update_result_analysis_action_state(self):
        """Aktualisiert die gemeinsame Freigabe und den Berichtsexport."""

        if not hasattr(self, "action_result_analysis"):
            return

        enabled = self.update_network_data_action_states()
        if enabled:
            self.action_result_analysis.setToolTip(
                self.language.text("tooltip.result_analysis")
            )
        if hasattr(self, "action_export_word_report"):
            report_enabled = (
                enabled and self.active_training_history_entry() is not None
            )
            self.action_export_word_report.setEnabled(report_enabled)
            self.action_export_word_report.setToolTip(
                self.language.text(
                    "tooltip.word_report"
                    if report_enabled
                    else "tooltip.disabled.training_run_required"
                )
            )
        self.update_project_workflow()

    def open_result_analysis(self):
        """Öffnet das gemeinsame Fenster beim Datensatzvergleich."""

        self.open_test_analysis_window(initial_tab=0)

    def export_training_report(self, word_format=None):
        """Exportiert den aktiven Trainingslauf direkt aus dem Dateimenü."""

        training_run = self.active_training_history_entry()
        if training_run is None or not self.training_data_manager.has_document:
            QMessageBox.information(
                self,
                self.language.text("analysis.report.title"),
                self.language.text("analysis.report.no_active_run"),
            )
            return

        try:
            records, inputs, outputs = NetworkTestDialog.prepare_document(
                self.scene.network,
                self.training_data_manager.document,
                data_label=self.language.text("test.data.training"),
                translator=self.language.text,
            )
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("analysis.report.error_title"),
                str(error),
            )
            return

        overview = self.project_overview_values()
        dialog = ResultAnalysisDialog(
            self.scene.network,
            [{
                "kind": "training",
                "label": self.language.text("test.data.training"),
                "records": records,
                "inputs": inputs,
                "outputs": outputs,
                "file_path": self.training_data_manager.file_path,
            }],
            parent=self,
            language_manager=self.language,
            initial_source_kind="training",
            tolerances=self.analysis_tolerances,
            report_context={
                "project_name": (
                    Path(self.current_project_path).stem
                    if self.current_project_path
                    else self.language.text("common.unknown")
                ),
                "project_description": self.project_description,
                "structure": overview["structure"],
                "neurons": overview["neurons"],
                "connections": overview["connections"],
                "training_run": training_run,
                "training_history": deepcopy(self.training_history),
                "active_training_run_id": self.active_training_run_id,
                "scene": self.scene,
                "export_dir": (
                    str(
                        Path(self.current_project_path).resolve().parent
                        / (
                            "exporte"
                            if self.language.current_language == "de"
                            else "exports"
                        )
                    )
                    if self.current_project_path else ""
                ),
            },
        )
        if word_format is True:
            dialog.export_word_report()
        elif word_format is False:
            dialog.export_pdf_report()
        else:
            dialog.export_report()
        dialog.deleteLater()

    def export_word_training_report(self, checked=False):
        """Öffnet die gemeinsame Auswahl für PDF- oder DOCX-Berichte."""
        self.export_training_report()

    def open_test_analysis_window(self, initial_tab=1, initial_source_kind=None):
        """Öffnet die gemeinsame, rein lesende Ergebnisanalyse."""

        self.reconcile_active_data_mappings()
        validation = self.scene.network.validate_network(
            translator=self.language.text
        )
        if not validation["valid"]:
            QMessageBox.warning(
                self,
                self.language.text("analysis.title"),
                self.language.text(
                    "test.network_invalid",
                    errors="\n".join(validation["errors"])
                )
            )
            return

        sources = []
        specifications = [
            (
                "training",
                self.training_data_manager,
                self.language.text("test.data.training")
            )
        ]
        if self.test_data_manager.has_document:
            specifications.append(
                (
                    "test",
                    self.test_data_manager,
                    self.language.text("test.data.test")
                )
            )
        try:
            for kind, manager, label in specifications:
                records, inputs, outputs = NetworkTestDialog.prepare_document(
                    self.scene.network,
                    manager.document,
                    data_label=label,
                    translator=self.language.text
                )
                sources.append({
                    "kind": kind,
                    "label": label,
                    "records": records,
                    "inputs": inputs,
                    "outputs": outputs,
                    "file_path": manager.file_path,
                })
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("analysis.title"),
                str(error)
            )
            return

        previous_tolerances = deepcopy(self.analysis_tolerances)
        overview = self.project_overview_values()
        ResultAnalysisDialog(
            self.scene.network,
            sources,
            parent=self,
            language_manager=self.language,
            initial_tab=initial_tab,
            initial_source_kind=initial_source_kind,
            tolerances=self.analysis_tolerances,
            report_context={
                "project_name": (
                    Path(self.current_project_path).stem
                    if self.current_project_path
                    else self.language.text("common.unknown")
                ),
                "project_description": self.project_description,
                "structure": overview["structure"],
                "neurons": overview["neurons"],
                "connections": overview["connections"],
                "training_run": self.active_training_history_entry(),
                "training_history": deepcopy(self.training_history),
                "active_training_run_id": self.active_training_run_id,
                "scene": self.scene,
                "export_dir": (
                    str(Path(self.current_project_path).resolve().parent / "exporte")
                    if self.current_project_path else ""
                ),
            },
        ).exec()
        if self.analysis_tolerances != previous_tolerances:
            self.set_project_modified(True)

    def get_test_calibration_differences(self):
        """Vergleicht Test- und Trainingsskalierung je Neuronenzuordnung."""

        training_document = self.training_data_manager.document
        test_document = self.test_data_manager.document

        if not isinstance(training_document, dict) or not isinstance(
            test_document,
            dict
        ):
            return []

        training_columns = {
            (
                column.get("role"),
                column.get("mapped_neuron_id")
            ): column
            for column in training_document.get("columns", [])
            if column.get("mapped_neuron_id") is not None
        }
        differences = []

        for test_column in test_document.get("columns", []):
            key = (
                test_column.get("role"),
                test_column.get("mapped_neuron_id")
            )
            training_column = training_columns.get(key)

            if training_column is None:
                continue

            if TrainingDataIO.calibrations_equal(
                training_column.get("calibration"),
                test_column.get("calibration")
            ):
                continue

            neuron_name = (
                test_column.get("mapped_neuron_name")
                or training_column.get("mapped_neuron_name")
                or self.language.text("test.neuron_fallback", neuron_id=key[1])
            )
            differences.append(
                self.language.text(
                    "test.scaling_difference.item",
                    column=test_column.get("name", self.language.text("test.column.generic")),
                    neuron=neuron_name
                )
            )

        return differences

    def open_training_data_dialog(self):
        """
        Öffnet den unabhängigen Editor für
        Trainingsdatendateien.

        Die Trainingsdaten bleiben eine eigenständige Datei.
        Der Dateipfad wird jedoch mit dem Projekt verknüpft.
        """

        self.reconcile_active_data_mappings()

        dialog = TrainingDataDialog(
            self.scene.network,
            self.training_data_manager.document,
            self.training_data_manager.file_path,
            parent=self,
            data_label=self.language.text("test.data.training"),
            document_modified=(
                self.training_data_manager.modified
            ),
            default_directory=self.get_project_data_directory(
                "trainingsdaten"
            ),
            language_manager=self.language,
            color_settings=self.display_settings.get("colors", {}),
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        previous_training_file_path = (
            self.training_data_manager.file_path
        )

        self.training_data_manager.set_document(
            dialog.document,
            file_path=dialog.current_file_path,
            modified=dialog.modified
        )

        if (
            previous_training_file_path
            != self.training_data_manager.file_path
            or dialog.modified
        ):
            self.set_project_modified(
                True
            )

        record_count = (
            self.training_data_manager.record_count
        )

        file_name = (
            self.training_data_manager.display_name
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.data.training_ready",
                name=file_name,
                count=record_count
            ),
            5000
        )

    def open_mathematics_mode(self):
        """Öffnet den datensatzweisen Lernmodus mit freier Neuronwahl."""

        self.reconcile_active_data_mappings()

        selected_neuron = (
            self.current_object
            if isinstance(self.current_object, Neuron)
            else None
        )

        if not self.scene.network.get_neurons():
            return

        validation_result = self.scene.network.validate_network(
            check_parameters=False
        )
        if not validation_result["valid"]:
            error_text = "\n".join(validation_result["errors"])
            QMessageBox.warning(
                self,
                self.language.text("math.message.title"),
                self.language.text(
                    "math.open.invalid_network",
                    errors=error_text
                )
            )
            return

        if not self.training_data_manager.has_document:
            QMessageBox.information(
                self,
                self.language.text("math.message.title"),
                self.language.text("math.open.no_data")
            )
            return

        try:
            dialog = MathematicsDialog(
                self.scene.network,
                selected_neuron,
                self.training_data_manager.document,
                file_path=self.training_data_manager.file_path,
                learning_rate=self.training_settings.get(
                    "learning_rate",
                    0.01
                ),
                parent=self,
                language_manager=self.language
            )
        except (TypeError, ValueError) as error:
            QMessageBox.warning(
                self,
                self.language.text("math.message.title"),
                str(error)
            )
            return

        dialog.exec()

        self.scene.update()
        self.view.viewport().update()

        if dialog.applied:
            self.training_settings["learning_rate"] = (
                dialog.learning_rate_value
            )
            self.set_project_modified(True)

        if isinstance(self.current_object, Neuron):
            self.show_neuron_properties(self.current_object)

    def open_training_dialog(self):
        """
        Öffnet den Trainingsdialog und trainiert das
        Netzwerk mit der aktuell geladenen Trainingsdatei.
        """

        self.reconcile_active_data_mappings()

        if (
            self.training_dialog is not None
            and self.training_dialog.isVisible()
        ):
            self.training_dialog.showNormal()
            self.training_dialog.raise_()
            self.training_dialog.activateWindow()
            return

        validation_result = (
            self.scene.network.validate_network(
                check_parameters=False
            )
        )

        if not validation_result["valid"]:
            error_text = "\n".join(
                validation_result["errors"]
            )

            QMessageBox.warning(
                self,
                self.language.text("training.message.title"),
                self.language.text(
                    "training.open.invalid_network",
                    errors=error_text
                )
            )

            return

        if not self.training_data_manager.has_document:
            QMessageBox.information(
                self,
                self.language.text("training.message.title"),
                self.language.text("training.open.no_data")
            )
            return

        try:
            dialog = TrainingDialog(
                self.scene.network,
                self.training_data_manager.document,
                self.training_data_manager.file_path,
                project_path=self.current_project_path,
                parent=self,
                training_settings=self.training_settings,
                language_manager=self.language
            )

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

        existing_run_ids = [
            int(entry.get("run_id", 0))
            for entry in self.training_history
            if isinstance(entry, dict)
            and isinstance(entry.get("run_id"), int)
        ]
        dialog.set_next_training_run_id(
            max(existing_run_ids, default=0) + 1
        )

        active_entry = self.active_training_history_entry()
        if active_entry is not None:
            self.active_training_run_id = active_entry.get("run_id")
            dialog.show_restored_training_run(active_entry)

        dialog.training_progress.connect(
            self.training_progress_updated
        )

        dialog.training_monitoring_changed.connect(
            self.set_training_monitoring_enabled
        )

        dialog.training_completed.connect(
            self.training_step_completed
        )

        previous_training_settings = dict(
            self.training_settings
        )
        dialog.previous_training_settings = previous_training_settings
        dialog.finished.connect(
            lambda result, current_dialog=dialog:
            self.training_dialog_finished(current_dialog)
        )

        self.training_dialog = dialog
        self.enter_training_observation_mode()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def enter_training_observation_mode(self):
        """Erlaubt während des Trainings nur gefahrlose Editoraktionen."""

        if self.training_observation_mode:
            return

        self.training_observation_mode = True
        self.scene.set_observation_mode(True)

        locked_actions = (
            self.action_new,
            self.action_open,
            self.action_save,
            self.action_save_as,
            self.action_rename_project,
            self.action_project_description,
            self.action_exit,
            self.action_undo,
            self.action_redo,
            self.action_cut,
            self.action_paste,
            self.action_delete,
            self.action_layout_network,
            self.action_change_structure,
            self.action_validate_network,
            self.action_forward_pass,
            self.action_graphical_experiment,
            self.action_training_step,
            self.action_test_network,
            self.action_result_analysis,
            self.action_export_word_report,
            self.action_mathematics_mode,
            self.action_training_history,
            self.action_training_data,
            self.action_edit_test_data,
            self.action_remove_test_data,
            self.action_test_with_test_data,
            self.action_display_settings,
        )

        self._training_locked_action_states = {
            action: (action.isEnabled(), action.toolTip(), action.statusTip())
            for action in locked_actions
        }

        for action in locked_actions:
            action.setEnabled(False)
            action.setToolTip(
                self.language.text("tooltip.disabled.training_active")
            )

        self.recent_projects_menu.menuAction().setEnabled(False)
        self.example_projects_menu.menuAction().setEnabled(False)
        self.property_stack.setEnabled(False)
        self.property_math_stack.setEnabled(False)
        self.project_workflow_widget.setEnabled(False)
        self.statusBar().showMessage(
            self.language.text("status.training_observation")
        )

    def leave_training_observation_mode(self):
        """Stellt nach dem Schließen des Trainingsfensters die Bedienung wieder her."""

        if not self.training_observation_mode:
            return

        self.training_observation_mode = False
        self.scene.set_observation_mode(False)

        for action, state in self._training_locked_action_states.items():
            was_enabled, tooltip, status_tip = state
            action.setEnabled(was_enabled)
            action.setToolTip(tooltip)
            action.setStatusTip(status_tip)

        self._training_locked_action_states = {}
        self.recent_projects_menu.menuAction().setEnabled(True)
        self.example_projects_menu.menuAction().setEnabled(True)
        self.property_stack.setEnabled(True)
        self.property_math_stack.setEnabled(True)
        self.project_workflow_widget.setEnabled(True)
        self.update_undo_redo_actions()
        self.update_test_data_actions()
        self.update_result_analysis_action_state()
        self.object_selected(self.current_object)
        self.update_window_title()
        self.statusBar().clearMessage()

    def training_dialog_finished(self, dialog):
        """Übernimmt Einstellungen und beendet den Beobachtungsmodus."""

        if dialog is not self.training_dialog:
            return

        self.set_training_monitoring_enabled(True)
        self.training_settings = dialog.get_training_settings()

        if (
            self.training_settings
            != dialog.previous_training_settings
        ):
            self.set_project_modified(True)

        self.leave_training_observation_mode()
        self.training_dialog = None
        dialog.deleteLater()

    def set_training_monitoring_enabled(
        self,
        enabled
    ):
        """
        Schaltet die sichtbare Aktualisierung der
        Netzwerkdarstellung während des Trainings ein oder aus.

        Die Bedienung des Trainingsdialogs und insbesondere
        die Stop-Schaltfläche bleiben davon unberührt.
        """

        enabled = bool(
            enabled
        )

        self.view.setUpdatesEnabled(
            enabled
        )

        if enabled:
            self.scene.update()
            self.view.viewport().update()

            if isinstance(
                self.current_object,
                Neuron
            ):
                self.show_neuron_properties(
                    self.current_object
                )

            elif isinstance(
                self.current_object,
                Connection
            ):
                self.show_connection_properties(
                    self.current_object
                )

    def open_training_history(self):
        """Öffnet die projektbezogene Übersicht früherer Trainingsläufe."""

        previous_snapshot = self.capture_editor_snapshot()
        active_entry_before = next(
            (
                entry
                for entry in self.training_history
                if entry.get("run_id") == self.active_training_run_id
            ),
            None,
        )
        restorable_run_ids = {
            entry.get("run_id")
            for entry in self.training_history
            if isinstance(entry, dict)
            and self.training_network_state_is_compatible(
                entry.get("network_state")
            )
        }
        dialog = TrainingHistoryDialog(
            self.training_history,
            parent=self,
            language_manager=self.language,
            restorable_run_ids=restorable_run_ids,
            active_run_id=self.active_training_run_id,
        )
        dialog.exec()

        updated_history = dialog.get_training_history()
        restore_run_id = dialog.get_restore_run_id()

        if restore_run_id is not None:
            selected_entry = next(
                (
                    entry
                    for entry in updated_history
                    if entry.get("run_id") == restore_run_id
                ),
                None
            )

            if (
                selected_entry is None
                or not self.restore_training_network_state(
                    selected_entry.get("network_state")
                )
            ):
                QMessageBox.warning(
                    self,
                    self.language.text("history.restore_error_title"),
                    self.language.text("history.restore_incompatible")
                )
                return

            self.training_history = updated_history
            self.active_training_run_id = restore_run_id
            self.restore_training_settings_from_history(
                selected_entry
            )
            self.commit_explicit_history_step(
                previous_snapshot
            )
            self.statusBar().showMessage(
                self.language.text(
                    "history.restore_success",
                    run=restore_run_id
                ),
                7000
            )
            self.update_project_workflow()
            return deepcopy(selected_entry)

        if updated_history != self.training_history:
            self.training_history = updated_history
            retained_active = None
            if active_entry_before is not None:
                retained_active = next(
                    (
                        entry
                        for entry in self.training_history
                        if entry.get("timestamp") == active_entry_before.get("timestamp")
                        and entry.get("training_data_path")
                        == active_entry_before.get("training_data_path")
                    ),
                    None,
                )
            if retained_active is not None:
                self.active_training_run_id = retained_active.get("run_id")
            else:
                self.active_training_run_id = None
                fallback = self.active_training_history_entry()
                self.active_training_run_id = (
                    fallback.get("run_id") if fallback is not None else None
                )
            self.set_project_modified(
                True
            )
            self.update_project_workflow()

            if (
                not self.training_history
                and self.training_dialog is not None
            ):
                self.training_dialog.clear_training_run_display()

        return None

    def training_run_matches_active_data(self, entry):
        """Prüft, ob ein Historienlauf zur aktuell geladenen Trainingsdatei gehört."""
        if not isinstance(entry, dict) or not self.training_data_manager.has_document:
            return False
        current_path = str(self.training_data_manager.file_path or "").strip()
        stored_path = str(entry.get("training_data_path", "") or "").strip()
        if current_path and stored_path:
            if os.path.normcase(os.path.abspath(current_path)) == os.path.normcase(
                os.path.abspath(stored_path)
            ):
                return True
            # Nach dem Verschieben eines vollständigen Projektordners ist der
            # frühere absolute Pfad nicht mehr gültig. Der im Lauf gespeicherte
            # Anzeigename ordnet ihn weiterhin eindeutig dem Projekt zu.
            return str(entry.get("training_data", "")) == str(
                self.training_data_manager.display_name
            )
        return str(entry.get("training_data", "")) == str(
            self.training_data_manager.display_name
        )

    def active_training_history_entry(self):
        """Liefert den aktiven oder neuesten passenden Trainingslauf."""
        matching = [
            entry for entry in self.training_history
            if self.training_run_matches_active_data(entry)
            and self.training_network_state_is_compatible(entry.get("network_state"))
        ]
        active = next(
            (
                entry for entry in matching
                if entry.get("run_id") == self.active_training_run_id
            ),
            None,
        )
        return active if active is not None else (matching[-1] if matching else None)

    def capture_training_network_state(self):
        """Erfasst Gewichte und Bias-Werte am Ende eines Trainingslaufes."""

        neurons = sorted(
            self.scene.network.get_neurons(),
            key=lambda neuron: neuron.id
        )
        connections = sorted(
            self.scene.network.get_connections(),
            key=lambda connection: connection.id
        )

        values = [
            float(neuron.bias)
            for neuron in neurons
        ] + [
            float(connection.weight)
            for connection in connections
        ]

        if not all(math.isfinite(value) for value in values):
            return None

        return {
            "neurons": [
                {
                    "id": int(neuron.id),
                    "bias": float(neuron.bias)
                }
                for neuron in neurons
            ],
            "connections": [
                {
                    "id": int(connection.id),
                    "source": int(connection.source_neuron.id),
                    "target": int(connection.target_neuron.id),
                    "weight": float(connection.weight)
                }
                for connection in connections
            ],
            "momentum_state": self.scene.network.get_momentum_state(),
        }

    def training_network_state_is_compatible(self, network_state):
        """Prüft, ob ein Historienzustand zum aktuellen Netz passt."""

        if not isinstance(network_state, dict):
            return False

        neuron_states = network_state.get("neurons")
        connection_states = network_state.get("connections")

        if not isinstance(neuron_states, list) or not isinstance(
            connection_states,
            list
        ):
            return False

        current_neurons = {
            neuron.id: neuron
            for neuron in self.scene.network.get_neurons()
        }
        current_connections = {
            connection.id: connection
            for connection in self.scene.network.get_connections()
        }

        if set(current_neurons) != {
            state.get("id")
            for state in neuron_states
            if isinstance(state, dict)
        }:
            return False

        if set(current_connections) != {
            state.get("id")
            for state in connection_states
            if isinstance(state, dict)
        }:
            return False

        for state in neuron_states:
            try:
                bias = float(state["bias"])
            except (KeyError, TypeError, ValueError):
                return False

            if not math.isfinite(bias):
                return False

        for state in connection_states:
            if not isinstance(state, dict):
                return False

            connection = current_connections.get(state.get("id"))

            try:
                weight = float(state["weight"])
                source_id = int(state["source"])
                target_id = int(state["target"])
            except (KeyError, TypeError, ValueError):
                return False

            if (
                connection is None
                or not math.isfinite(weight)
                or connection.source_neuron.id != source_id
                or connection.target_neuron.id != target_id
            ):
                return False

        return True

    def restore_training_network_state(self, network_state):
        """Stellt einen kompatiblen Endzustand aus der Historie wieder her."""

        if not self.training_network_state_is_compatible(network_state):
            return False

        for neuron_state in network_state["neurons"]:
            neuron = self.scene.network.get_neuron(
                neuron_state["id"]
            )
            neuron.bias = float(neuron_state["bias"])

        for connection_state in network_state["connections"]:
            connection = self.scene.network.get_connection(
                connection_state["id"]
            )
            connection.weight = float(connection_state["weight"])

        self.scene.network.restore_momentum_state(
            network_state.get("momentum_state")
        )

        self.scene.network.reset_runtime_values()

        for neuron in self.scene.network.get_neurons():
            neuron.update()

        self.scene.update()
        self.view.viewport().update()
        self.object_selected(self.current_object)
        return True

    def restore_training_settings_from_history(self, history_entry):
        """Übernimmt die für eine Fortsetzung geeigneten Laufparameter."""

        if not isinstance(history_entry, dict):
            return

        restored_settings = deepcopy(
            self.training_settings
        )
        restored_settings["initialize_network"] = False
        restored_settings["learning_rate"] = float(
            history_entry["learning_rate"]
        )
        restored_settings["momentum"] = float(
            history_entry.get("momentum", 0.0)
        )
        restored_settings["error_limit"] = float(
            history_entry["error_limit"]
        )
        restored_settings["maximum_epochs"] = int(
            history_entry["requested_epochs"]
        )
        restored_settings["fast_mode"] = bool(
            history_entry.get("fast_mode", False)
        )
        restored_settings["weight_initialization"] = str(
            history_entry.get("weight_initialization", "auto")
        )
        restored_settings["bias_initialization"] = str(
            history_entry.get("bias_initialization", "zero")
        )
        restored_settings["error_chart_scale"] = str(
            history_entry.get("error_chart_scale", "linear")
        )
        self.training_settings = ProjectIO.normalize_training_settings(
            restored_settings
        )

    def training_progress_updated(
        self,
        result
    ):
        """
        Aktualisiert die sichtbare Netzwerkdarstellung
        während eines längeren Trainingslaufes.
        """

        self.scene.update()
        self.view.viewport().update()

        if isinstance(
            self.current_object,
            Neuron
        ):
            self.show_neuron_properties(
                self.current_object
            )

        elif isinstance(
            self.current_object,
            Connection
        ):
            self.show_connection_properties(
                self.current_object
            )

    def training_step_completed(
        self,
        result
    ):
        """
        Aktualisiert die Oberfläche nach einem
        erfolgreich ausgeführten Trainingsschritt.
        """

        self.set_project_modified(
            True
        )

        existing_run_ids = [
            entry.get("run_id", 0)
            for entry in self.training_history
            if isinstance(entry, dict)
            and isinstance(entry.get("run_id"), int)
        ]
        try:
            requested_run_id = int(result.get("run_id"))
        except (TypeError, ValueError):
            requested_run_id = 0
        continuation = bool(result.get("continue_existing", False))
        existing_entry = next(
            (
                entry for entry in self.training_history
                if isinstance(entry, dict)
                and entry.get("run_id") == requested_run_id
            ),
            None,
        )
        if continuation and existing_entry is not None:
            run_id = requested_run_id
        else:
            run_id = (
                requested_run_id
                if requested_run_id > 0
                and requested_run_id not in existing_run_ids
                else max(existing_run_ids, default=0) + 1
            )
            continuation = False

        end_error = float(
            result["mean_squared_error"]
        )
        start_error = result.get(
            "start_error"
        )

        if start_error is None:
            start_error = end_error

        maximum_absolute_error = result.get(
            "maximum_absolute_error"
        )

        if maximum_absolute_error is None:
            maximum_absolute_error = 0.0

        updated_values = {
                "run_id": run_id,
                "timestamp": str(
                    result.get("timestamp")
                    or (
                        existing_entry.get("timestamp", "")
                        if existing_entry is not None else ""
                    )
                    or datetime.now().isoformat(timespec="seconds")
                ),
                "training_data": (
                    self.training_data_manager.display_name
                ),
                "training_data_path": (
                    self.training_data_manager.file_path or ""
                ),
                "initialized": bool(
                    result.get("initialized", False)
                ),
                "fast_mode": bool(
                    result.get("fast_mode", False)
                ),
                "weight_initialization": str(
                    result.get("weight_initialization", "auto")
                ),
                "bias_initialization": str(
                    result.get("bias_initialization", "zero")
                ),
                "learning_rate": float(
                    result.get("learning_rate", 0.01)
                ),
                "momentum": float(result.get("momentum", 0.0)),
                "shuffle_seed": result.get("shuffle_seed"),
                "error_limit": float(
                    result.get("error_limit", 0.01)
                ),
                "requested_epochs": int(
                    result.get("requested_epochs", 1)
                ),
                "completed_epochs": int(
                    result.get("completed_epochs", 1)
                ),
                "start_error": float(start_error),
                "end_error": end_error,
                "maximum_absolute_error": float(
                    maximum_absolute_error
                ),
                "elapsed_seconds": float(
                    result.get("elapsed_seconds", 0.0)
                ),
                "status_text": str(
                    result.get(
                        "status_text",
                        self.language.text("training.status.completed")
                    )
                ),
                "stop_at_error_limit": bool(
                    result.get("stop_at_error_limit", False)
                ),
                "training_stopped": bool(
                    result.get("training_stopped", False)
                ),
                "continuable": bool(result.get("continuable", True)),
                "curve_points": deepcopy(
                    result.get("curve_points", [])
                ),
                "error_chart_scale": str(
                    result.get("error_chart_scale", "linear")
                ),
                "initial_network_state": deepcopy(
                    result.get("initial_network_state")
                ),
                "network_state": self.capture_training_network_state()
            }
        if continuation:
            # Nummer, ursprünglicher Startzeitpunkt und Startfehler gehören
            # weiterhin zum selben Lauf; alle fortgeschriebenen Werte werden
            # durch den neuen Abschnitt aktualisiert.
            updated_values["timestamp"] = existing_entry.get(
                "timestamp", updated_values["timestamp"]
            )
            updated_values["start_error"] = float(
                existing_entry.get("start_error", start_error)
            )
            updated_values["initialized"] = bool(
                existing_entry.get("initialized", False)
            )
            updated_values["weight_initialization"] = str(
                existing_entry.get("weight_initialization", "auto")
            )
            updated_values["bias_initialization"] = str(
                existing_entry.get("bias_initialization", "zero")
            )
            updated_values["initial_network_state"] = deepcopy(
                existing_entry.get("initial_network_state")
            )
            updated_values["shuffle_seed"] = existing_entry.get(
                "shuffle_seed", updated_values.get("shuffle_seed")
            )
            existing_entry.update(updated_values)
        else:
            self.training_history.append(updated_values)
        self.active_training_run_id = run_id
        self.update_project_workflow()

        if isinstance(
            self.current_object,
            Neuron
        ):
            self.show_neuron_properties(
                self.current_object
            )

        elif isinstance(
            self.current_object,
            Connection
        ):
            self.show_connection_properties(
                self.current_object
            )

        mean_squared_error = result[
            "mean_squared_error"
        ]

        completed_epochs = result.get(
            "completed_epochs",
            1
        )

        status_text = result.get(
            "status_text",
            self.language.text("training.status.completed")
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.training.completed",
                status=status_text,
                epochs=completed_epochs,
                error=format_number(mean_squared_error)
            ),
            7000
        )

    def capture_editor_snapshot(
        self,
        include_training_data=False,
        include_test_data=False,
    ):
        """
        Erstellt eine vollständige Momentaufnahme des
        bearbeitbaren Netzwerkzustandes.

        Trainingsdaten werden nur bei ausdrücklich dafür
        vorgesehenen Arbeitsschritten mitgesichert. Dadurch
        bleiben normale Rückgängig-Schritte auch bei großen
        Datensätzen speicherschonend.
        """

        neurons = sorted(
            self.scene.network.get_neurons(),
            key=lambda neuron: neuron.id
        )

        connections = sorted(
            self.scene.network.get_connections(),
            key=lambda connection: connection.id
        )

        comments = sorted(
            [
                item
                for item in self.scene.items()
                if isinstance(
                    item,
                    CommentItem
                )
            ],
            key=lambda comment: comment.id
        )

        snapshot = {
            "neurons": [
                {
                    "id": int(
                        neuron.id
                    ),
                    "name": str(
                        neuron.name
                    ),
                    "type": neuron.neuron_type.value,
                    "bias": float(
                        neuron.bias
                    ),
                    "activation": str(
                        neuron.activation_function
                    ),
                    "input_value": float(
                        neuron.input_value
                    ),
                    "target_value": float(
                        neuron.target_value
                    ),
                    "x": float(
                        neuron.x()
                    ),
                    "y": float(
                        neuron.y()
                    )
                }
                for neuron in neurons
            ],
            "comments": [
                {
                    "id": int(
                        comment.id
                    ),
                    "text": str(
                        comment.text
                    ),
                    "x": float(
                        comment.x()
                    ),
                    "y": float(
                        comment.y()
                    ),
                    "width": float(
                        comment.width
                    ),
                    "height": float(
                        comment.height
                    ),
                    "font_size": int(
                        comment.font_size
                    )
                }
                for comment in comments
            ],
            "connections": [
                {
                    "id": int(
                        connection.id
                    ),
                    "source": int(
                        connection.source_neuron.id
                    ),
                    "target": int(
                        connection.target_neuron.id
                    ),
                    "weight": float(
                        connection.weight
                    )
                }
                for connection in connections
            ],
            "next_id": int(
                self.scene.next_id
            ),
            "next_connection_id": int(
                self.scene.next_connection_id
            ),
            "next_comment_id": int(
                self.scene.next_comment_id
            ),
            "training_settings": deepcopy(
                self.training_settings
            ),
            "training_history": deepcopy(
                self.training_history
            ),
            "active_training_run_id": self.active_training_run_id,
            "analysis_tolerances": deepcopy(self.analysis_tolerances),
            "display_settings": deepcopy(
                self.display_settings
            ),
            "momentum_state": self.scene.network.get_momentum_state(),
        }

        if include_training_data:
            snapshot["training_data_state"] = {
                "document": (
                    self.training_data_manager.document
                ),
                "file_path": (
                    self.training_data_manager.file_path
                ),
                "modified": (
                    self.training_data_manager.modified
                )
            }

        if include_test_data:
            snapshot["test_data_state"] = {
                "document": self.test_data_manager.document,
                "file_path": self.test_data_manager.file_path,
                "modified": self.test_data_manager.modified,
            }

        return snapshot

    def restore_editor_snapshot(
        self,
        snapshot
    ):
        """
        Stellt eine zuvor gespeicherte Momentaufnahme wieder her.
        """

        if not isinstance(
            snapshot,
            dict
        ):
            return

        self._history_timer.stop()
        self._history_restoring = True

        try:
            self.scene.clearSelection()
            self.scene.clear_project()

            self.apply_display_settings(
                snapshot.get(
                    "display_settings",
                    ProjectIO.default_display_settings()
                ),
                mark_as_modified=False
            )

            neurons_by_id = {}

            for neuron_data in snapshot[
                "neurons"
            ]:
                neuron = self.scene.add_neuron(
                    neuron_data["id"],
                    neuron_data["x"],
                    neuron_data["y"],
                    neuron_data["name"],
                    mark_as_modified=False
                )

                neuron.neuron_type = NeuronType(
                    neuron_data["type"]
                )

                neuron.bias = float(
                    neuron_data["bias"]
                )

                neuron.activation_function = (
                    neuron_data["activation"]
                )

                neuron.input_value = float(
                    neuron_data["input_value"]
                )

                neuron.target_value = float(
                    neuron_data["target_value"]
                )

                neuron.update()

                neurons_by_id[
                    neuron.id
                ] = neuron

            for comment_data in snapshot[
                "comments"
            ]:
                self.scene.add_comment(
                    comment_data["id"],
                    comment_data["x"],
                    comment_data["y"],
                    comment_data["text"],
                    comment_data["width"],
                    comment_data["height"],
                    comment_data["font_size"],
                    mark_as_modified=False
                )

            for connection_data in snapshot[
                "connections"
            ]:
                source_neuron = neurons_by_id[
                    connection_data["source"]
                ]

                target_neuron = neurons_by_id[
                    connection_data["target"]
                ]

                self.scene.add_connection(
                    connection_data["id"],
                    source_neuron,
                    target_neuron,
                    connection_data["weight"],
                    mark_as_modified=False
                )

            self.scene.next_id = int(
                snapshot["next_id"]
            )

            self.scene.next_connection_id = int(
                snapshot["next_connection_id"]
            )

            self.scene.next_comment_id = int(
                snapshot["next_comment_id"]
            )

            self.training_settings = deepcopy(
                snapshot[
                    "training_settings"
                ]
            )

            self.training_history = deepcopy(
                snapshot.get(
                    "training_history",
                    []
                )
            )
            self.active_training_run_id = snapshot.get("active_training_run_id")
            self.analysis_tolerances = deepcopy(
                snapshot.get("analysis_tolerances", {})
            )

            self.scene.network.set_learning_rate(
                self.training_settings[
                    "learning_rate"
                ]
            )
            self.scene.network.set_momentum(
                self.training_settings.get("momentum", 0.0)
            )
            self.scene.network.restore_momentum_state(
                snapshot.get("momentum_state")
            )

            training_data_state = snapshot.get(
                "training_data_state"
            )

            if isinstance(
                training_data_state,
                dict
            ):
                training_document = training_data_state.get(
                    "document"
                )

                if training_document is None:
                    self.training_data_manager.clear()

                else:
                    self.training_data_manager.set_document(
                        training_document,
                        file_path=training_data_state.get(
                            "file_path"
                        ),
                        modified=training_data_state.get(
                            "modified",
                            False
                        )
                    )

            test_data_state = snapshot.get("test_data_state")

            if isinstance(test_data_state, dict):
                test_document = test_data_state.get("document")

                if test_document is None:
                    self.test_data_manager.clear()
                else:
                    self.test_data_manager.set_document(
                        test_document,
                        file_path=test_data_state.get("file_path"),
                        modified=test_data_state.get("modified", False),
                    )

            self.current_object = None

            self.object_selected(
                None
            )

            self.scene.update()
            self.view.viewport().update()

            self.scene.scene_geometry_changed.emit()

        finally:
            self._history_restoring = False

    def commit_explicit_history_step(
        self,
        previous_snapshot
    ):
        """
        Schließt einen bewusst gebündelten Arbeitsschritt ab.

        Dies wird für größere Aktionen verwendet, die als genau
        ein Rückgängig-Schritt erscheinen sollen.
        """

        if not isinstance(
            previous_snapshot,
            dict
        ):
            return

        self._history_timer.stop()

        self.undo_history.append(
            deepcopy(
                previous_snapshot
            )
        )

        if (
            len(
                self.undo_history
            )
            > self.undo_history_limit
        ):
            del self.undo_history[
                0
            ]

        self._history_baseline = deepcopy(
            self.capture_editor_snapshot()
        )

        self.redo_history.clear()

        self.project_modified = True

        self.update_window_title()
        self.update_status_summary()
        self.update_undo_redo_actions()

    def schedule_history_snapshot(self):
        """
        Plant den Abschluss des aktuellen Arbeitsschrittes.

        Durch den kurzen Aufschub werden beispielsweise alle
        Positionsänderungen eines Ziehvorganges oder mehrere
        unmittelbar aufeinanderfolgende Zeichen eines Kommentars
        zu genau einem Rückgängig-Schritt zusammengefasst.
        """

        if self._history_restoring:
            return

        if self._history_baseline is None:
            self._history_baseline = deepcopy(
                self.capture_editor_snapshot()
            )

        self._history_timer.start()

    def commit_history_snapshot(self):
        """
        Schließt den aktuellen Arbeitsschritt ab und legt
        den vorherigen Zustand im Rückgängig-Verlauf ab.
        """

        if self._history_restoring:
            return

        current_snapshot = (
            self.capture_editor_snapshot()
        )

        if self._history_baseline is None:
            self._history_baseline = deepcopy(
                current_snapshot
            )
            self.update_undo_redo_actions()
            return

        if (
            current_snapshot
            == self._history_baseline
        ):
            self.update_undo_redo_actions()
            return

        self.undo_history.append(
            deepcopy(
                self._history_baseline
            )
        )

        if (
            len(
                self.undo_history
            )
            > self.undo_history_limit
        ):
            del self.undo_history[
                0
            ]

        self._history_baseline = deepcopy(
            current_snapshot
        )

        self.redo_history.clear()

        self.update_undo_redo_actions()

    def reset_undo_history(
        self,
        mark_as_saved=False
    ):
        """
        Löscht den bisherigen Verlauf und verwendet den
        aktuellen Netzwerkzustand als neuen Ausgangspunkt.
        """

        self._history_timer.stop()

        self.undo_history.clear()
        self.redo_history.clear()

        current_snapshot = (
            self.capture_editor_snapshot()
        )

        self._history_baseline = deepcopy(
            current_snapshot
        )

        if mark_as_saved:
            self._saved_history_snapshot = deepcopy(
                current_snapshot
            )

        self.update_undo_redo_actions()

    def update_undo_redo_actions(self):
        """
        Aktiviert oder deaktiviert die beiden Menüeinträge
        entsprechend dem vorhandenen Verlauf.
        """

        if self.training_observation_mode:
            if hasattr(self, "action_undo"):
                self.action_undo.setEnabled(False)
                self.action_undo.setToolTip(
                    self.language.text("tooltip.disabled.training_active")
                )
            if hasattr(self, "action_redo"):
                self.action_redo.setEnabled(False)
                self.action_redo.setToolTip(
                    self.language.text("tooltip.disabled.training_active")
                )
            return

        if hasattr(
            self,
            "action_undo"
        ):
            undo_enabled = bool(self.undo_history)
            self.action_undo.setEnabled(undo_enabled)
            self.action_undo.setToolTip(
                self.language.text(
                    "tooltip.undo"
                    if undo_enabled else "tooltip.disabled.nothing_to_undo"
                )
            )

        if hasattr(
            self,
            "action_redo"
        ):
            redo_enabled = bool(self.redo_history)
            self.action_redo.setEnabled(redo_enabled)
            self.action_redo.setToolTip(
                self.language.text(
                    "tooltip.redo"
                    if redo_enabled else "tooltip.disabled.nothing_to_redo"
                )
            )

    def update_modified_state_from_snapshot(self):
        """
        Vergleicht den aktuellen Zustand mit dem zuletzt
        gespeicherten Projektzustand.
        """

        if self._saved_history_snapshot is None:
            self.project_modified = True

        else:
            self.project_modified = (
                self.capture_editor_snapshot()
                != self._saved_history_snapshot
            )

        self.update_window_title()

    def undo_last_action(self):
        """
        Macht den zuletzt abgeschlossenen Arbeitsschritt rückgängig.
        """

        text_widget = self.get_focused_text_widget()

        if text_widget is not None:
            text_widget.undo()
            return

        self._history_timer.stop()
        self.commit_history_snapshot()

        if not self.undo_history:
            return

        target_snapshot = self.undo_history.pop()

        include_training_data = (
            "training_data_state"
            in target_snapshot
        )
        include_test_data = "test_data_state" in target_snapshot

        current_snapshot = (
            self.capture_editor_snapshot(
                include_training_data=include_training_data,
                include_test_data=include_test_data,
            )
        )

        self.redo_history.append(
            deepcopy(
                current_snapshot
            )
        )

        if (
            len(
                self.redo_history
            )
            > self.undo_history_limit
        ):
            del self.redo_history[
                0
            ]

        self.restore_editor_snapshot(
            target_snapshot
        )

        self._history_baseline = deepcopy(
            self.capture_editor_snapshot()
        )

        self.update_modified_state_from_snapshot()
        self.update_undo_redo_actions()

        self.statusBar().showMessage(
            self.language.text("status.undo"),
            3000
        )

    def redo_last_action(self):
        """
        Stellt den zuletzt rückgängig gemachten
        Arbeitsschritt wieder her.
        """

        text_widget = self.get_focused_text_widget()

        if text_widget is not None:
            text_widget.redo()
            return

        self._history_timer.stop()

        if not self.redo_history:
            return

        target_snapshot = self.redo_history.pop()

        include_training_data = (
            "training_data_state"
            in target_snapshot
        )
        include_test_data = "test_data_state" in target_snapshot

        current_snapshot = (
            self.capture_editor_snapshot(
                include_training_data=include_training_data,
                include_test_data=include_test_data,
            )
        )

        self.undo_history.append(
            deepcopy(
                current_snapshot
            )
        )

        if (
            len(
                self.undo_history
            )
            > self.undo_history_limit
        ):
            del self.undo_history[
                0
            ]

        self.restore_editor_snapshot(
            target_snapshot
        )

        self._history_baseline = deepcopy(
            self.capture_editor_snapshot()
        )

        self.update_modified_state_from_snapshot()
        self.update_undo_redo_actions()

        self.statusBar().showMessage(
            self.language.text("status.redo"),
            3000
        )

    def set_project_modified(
        self,
        modified
    ):
        """
        Setzt den Änderungsstatus des Projektes,
        aktualisiert den Fenstertitel und verwaltet
        den Rückgängig-Verlauf.
        """

        if modified:
            if not self._history_restoring:
                self.schedule_history_snapshot()

            self.project_modified = True

        else:
            self._history_timer.stop()
            self.commit_history_snapshot()

            current_snapshot = (
                self.capture_editor_snapshot()
            )

            self._history_baseline = deepcopy(
                current_snapshot
            )

            self._saved_history_snapshot = deepcopy(
                current_snapshot
            )

            self.project_modified = False

        self.update_window_title()

        self.update_status_summary()

    def update_window_title(self):
        """
        Aktualisiert den Fenstertitel.
        """

        if hasattr(self, "action_save"):
            self.action_save.setEnabled(
                bool(self.project_modified)
                and not self.training_observation_mode
            )

        if self.current_project_path:
            project_name = os.path.basename(
                self.current_project_path
            )

        else:
            project_name = self.language.text(
                "window.new_project"
            )

        title = (
            self.language.text(
                "window.title",
                project_name=project_name
            )
        )

        if self.project_modified:
            title += " *"

        self.setWindowTitle(
            title
        )

    def confirm_unsaved_changes(self):
        """
        Fragt bei ungespeicherten Änderungen nach,
        ob gespeichert, verworfen oder abgebrochen werden soll.
        """

        if not self.project_modified:
            return True

        message_box = QMessageBox(
            self
        )
        message_box.setIcon(
            QMessageBox.Icon.Warning
        )
        message_box.setWindowTitle(
            self.language.text("dialog.unsaved.title")
        )
        message_box.setText(
            self.language.text("dialog.unsaved.message")
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(
            QMessageBox.StandardButton.Save
        )
        self.localize_message_box_buttons(
            message_box
        )
        message_box.exec()
        clicked_button = message_box.clickedButton()

        if clicked_button == message_box.button(
            QMessageBox.StandardButton.Save
        ):
            return self.save_project()

        if clicked_button == message_box.button(
            QMessageBox.StandardButton.Discard
        ):
            return True

        return False

    def reset_project(self):
        """
        Setzt den Editor auf ein neues,
        vollständig leeres Projekt zurück.
        """

        self.scene.clear_project()
        self.training_data_manager.clear()
        self.test_data_manager.clear()

        self.training_settings = (
            ProjectIO.default_training_settings()
        )
        self.training_history = []
        self.active_training_run_id = None
        self.analysis_tolerances = {}
        self.project_description = ""
        self.is_example_project = False
        self.example_difficulty = None

        self.apply_display_settings(
            ProjectIO.default_display_settings(),
            mark_as_modified=False
        )

        self.scene.network.set_learning_rate(
            self.training_settings[
                "learning_rate"
            ]
        )
        self.scene.network.set_momentum(
            self.training_settings.get("momentum", 0.0)
        )
        self.scene.network.reset_momentum_state()

        self.current_object = None
        self.current_project_path = None
        self._pending_loaded_project_fit = None
        self.update_project_image_action()

        self.object_selected(
            None
        )

        self.view.reset_zoom()

        self.reset_undo_history(
            mark_as_saved=True
        )

        self.set_project_modified(
            False
        )

    def new_project(self):
        """
        Erstellt nach einer möglichen Sicherheitsabfrage
        ein neues leeres Projekt.
        """

        if not self.confirm_unsaved_changes():
            return

        self.initialize_new_project()

    def initialize_new_project(self):
        """Setzt ohne weitere Rückfrage auf ein leeres Projekt zurück."""

        self.reset_project()

        self.statusBar().showMessage(
            self.language.text("status.new_project"),
            3000
        )

    def open_new_project_dialog(self):
        """Wählt einen verständlichen Einstieg in ein neues Projekt."""

        dialog = NewProjectDialog(
            language_manager=self.language,
            parent=self,
            show_assistant=self.ui_settings["show_project_assistant"],
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        choice = dialog.selected_choice
        if choice not in {"empty", "automatic", "from_data", "assistant"}:
            return

        if choice == "assistant":
            QTimer.singleShot(0, self.open_project_assistant)
            return

        if choice == "empty":
            if self.confirm_unsaved_changes():
                self.initialize_new_project()
            return

        next_action = {
            "automatic": lambda: self.open_network_create_dialog(
                start_new_project=True
            ),
            "from_data": lambda: self.open_network_from_training_data_dialog(
                start_new_project=True
            ),
        }.get(choice)

        if next_action is not None:
            QTimer.singleShot(0, next_action)

    def ask_for_training_data_file(
        self,
        project_file_path,
        missing_file_path=None
    ):
        """
        Fragt nach einer Trainingsdatendatei, wenn dem
        Projekt keine Trainingsdaten zugeordnet sind oder
        die gespeicherte Datei nicht gefunden wurde.
        """

        message_box = QMessageBox(
            self
        )

        message_box.setWindowTitle(
            self.language.text("test.data.training")
        )

        message_box.setIcon(
            QMessageBox.Icon.Question
        )

        if missing_file_path:
            message_box.setText(
                self.language.text("project_data.training.missing")
            )

            message_box.setInformativeText(
                self.language.text("project_data.training.missing_info", path=missing_file_path)
            )

        else:
            message_box.setText(
                self.language.text("project_data.training.unassigned")
            )

            message_box.setInformativeText(
                self.language.text("project_data.training.unassigned_info")
            )

        select_button = message_box.addButton(
            self.language.text("project_data.training.select"),
            QMessageBox.ButtonRole.ActionRole
        )

        without_button = message_box.addButton(
            self.language.text("project_data.training.open_without"),
            QMessageBox.ButtonRole.AcceptRole
        )

        cancel_button = message_box.addButton(
            self.language.text("common.cancel"),
            QMessageBox.ButtonRole.RejectRole
        )

        message_box.setDefaultButton(
            select_button
        )

        message_box.exec()

        clicked_button = message_box.clickedButton()

        if clicked_button is cancel_button:
            return (
                "cancel",
                None
            )

        if clicked_button is without_button:
            return (
                "without",
                None
            )

        initial_directory = os.path.dirname(
            os.path.abspath(
                project_file_path
            )
        )

        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            self.language.text("project_data.training.select_title"),
            initial_directory,
            self.language.text("data.file_filter.training")
        )

        if not selected_path:
            return (
                "cancel",
                None
            )

        return (
            "load",
            selected_path
        )

    def prepare_project_training_data(
        self,
        project_file_path,
        project_data
    ):
        """
        Ermittelt und prüft die zum Projekt gehörenden
        Trainingsdaten, bevor das aktuelle Projekt ersetzt wird.
        """

        training_data_info = project_data.get(
            "training_data"
        )

        stored_reference = None

        if isinstance(
            training_data_info,
            dict
        ):
            stored_reference = training_data_info.get(
                "file"
            )

        resolved_path = ProjectIO.resolve_training_data_path(
            project_file_path,
            stored_reference
        )

        if resolved_path and os.path.isfile(
            resolved_path
        ):
            try:
                document = TrainingDataIO.load(
                    resolved_path
                )
            except (
                OSError,
                TypeError,
                ValueError
            ) as error:
                QMessageBox.warning(
                    self,
                    self.language.text("project_data.training.load_warning_title"),
                    self.language.text("project_data.training.load_warning", error=error)
                )
            else:
                return {
                    "cancelled": False,
                    "document": document,
                    "file_path": resolved_path,
                    "association_changed": False
                }

        action, selected_path = self.ask_for_training_data_file(
            project_file_path,
            missing_file_path=(
                resolved_path
                if stored_reference
                else None
            )
        )

        if action == "cancel":
            return {
                "cancelled": True,
                "document": None,
                "file_path": None,
                "association_changed": False
            }

        if action == "without":
            return {
                "cancelled": False,
                "document": None,
                "file_path": None,
                "association_changed": bool(
                    stored_reference
                )
            }

        try:
            document = TrainingDataIO.load(
                selected_path
            )
        except (
            OSError,
            TypeError,
            ValueError
        ) as error:
            QMessageBox.critical(
                self,
                self.language.text("project_data.training.load_error_title"),
                str(
                    error
                )
            )

            return {
                "cancelled": True,
                "document": None,
                "file_path": None,
                "association_changed": False
            }

        return {
            "cancelled": False,
            "document": document,
            "file_path": selected_path,
            "association_changed": True
        }

    def ask_for_missing_test_data_file(
        self,
        project_file_path,
        missing_file_path
    ):
        """Fragt nach Ersatz, wenn zugeordnete Testdaten fehlen."""

        message_box = QMessageBox(
            self
        )
        message_box.setWindowTitle(
            self.language.text("test.data.test")
        )
        message_box.setIcon(
            QMessageBox.Icon.Question
        )
        message_box.setText(
            self.language.text("project_data.test.missing")
        )
        message_box.setInformativeText(
            self.language.text("project_data.test.missing_info", path=missing_file_path)
        )
        select_button = message_box.addButton(
            self.language.text("project_data.test.select"),
            QMessageBox.ButtonRole.ActionRole
        )
        without_button = message_box.addButton(
            self.language.text("project_data.test.open_without"),
            QMessageBox.ButtonRole.AcceptRole
        )
        cancel_button = message_box.addButton(
            self.language.text("common.cancel"),
            QMessageBox.ButtonRole.RejectRole
        )
        message_box.setDefaultButton(
            select_button
        )
        message_box.exec()

        if message_box.clickedButton() is cancel_button:
            return "cancel", None

        if message_box.clickedButton() is without_button:
            return "without", None

        initial_directory = os.path.dirname(
            os.path.abspath(project_file_path)
        )
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            self.language.text("project_data.test.select_title"),
            initial_directory,
            self.language.text("data.file_filter.test_open")
        )

        if not selected_path:
            return "cancel", None

        return "load", selected_path

    def prepare_project_test_data(
        self,
        project_file_path,
        project_data
    ):
        """Lädt eine vorhandene Testdatenzuordnung des Projekts vorab."""

        test_data_info = project_data.get(
            "test_data"
        )
        stored_reference = (
            test_data_info.get("file")
            if isinstance(test_data_info, dict)
            else None
        )

        # Alte Projekte und Projekte ohne Testdaten werden ohne
        # zusätzliche Nachfrage geöffnet.
        if not stored_reference:
            return {
                "cancelled": False,
                "document": None,
                "file_path": None,
                "association_changed": False
            }

        resolved_path = ProjectIO.resolve_training_data_path(
            project_file_path,
            stored_reference
        )

        if resolved_path and os.path.isfile(resolved_path):
            try:
                document = TrainingDataIO.load(
                    resolved_path
                )
            except (OSError, TypeError, ValueError) as error:
                QMessageBox.warning(
                    self,
                    self.language.text("project_data.test.load_warning_title"),
                    self.language.text("project_data.test.load_warning", error=error)
                )
            else:
                return {
                    "cancelled": False,
                    "document": document,
                    "file_path": resolved_path,
                    "association_changed": False
                }

        action, selected_path = self.ask_for_missing_test_data_file(
            project_file_path,
            resolved_path or stored_reference
        )

        if action == "cancel":
            return {
                "cancelled": True,
                "document": None,
                "file_path": None,
                "association_changed": False
            }

        if action == "without":
            return {
                "cancelled": False,
                "document": None,
                "file_path": None,
                "association_changed": True
            }

        try:
            document = TrainingDataIO.load(
                selected_path
            )
        except (OSError, TypeError, ValueError) as error:
            QMessageBox.critical(
                self,
                self.language.text("project_data.test.load_error_title"),
                str(error)
            )
            return {
                "cancelled": True,
                "document": None,
                "file_path": None,
                "association_changed": False
            }

        return {
            "cancelled": False,
            "document": document,
            "file_path": selected_path,
            "association_changed": True
        }

    def get_initial_project_directory(self):
        """
        Liefert den bevorzugten Projektordner
        als Startposition für einen Dateidialog.
        """

        try:
            return str(self.project_content_directory())
        except OSError:
            return str(Path.home())

    def get_project_open_directory(self):
        """Startet im bevorzugten Projektordner."""

        return self.get_initial_project_directory()

    def get_project_data_directory(self, directory_name):
        """Liefert den passenden Datenordner des aktuellen Projekts."""

        if not self.current_project_path:
            return ""

        project_directory = Path(
            self.current_project_path
        ).resolve().parent
        data_directory = project_directory / str(directory_name)

        if data_directory.is_dir():
            return str(data_directory)

        return str(project_directory)

    def project_save_dialog_defaults(self):
        """Bestimmt Name und Basisordner für Speichern unter."""

        if self.current_project_path:
            current_path = Path(
                self.current_project_path
            ).resolve()
            project_name = current_path.stem
            return project_name, str(self.project_content_directory())

        try:
            base_directory = str(
                self.project_content_directory()
            )
        except OSError:
            base_directory = self.get_initial_project_directory()

            if not base_directory:
                base_directory = str(Path.home())

        return self.language.text("window.new_project"), base_directory

    def create_project_directory_structure(self, project_file_path):
        """Legt den Projektordner und alle vorgesehenen Unterordner an."""

        project_directory = Path(project_file_path).resolve().parent
        project_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        for directory_name in self.PROJECT_SUBDIRECTORIES:
            (project_directory / directory_name).mkdir(
                exist_ok=True
            )

    @staticmethod
    def unique_data_destination(
        directory_path,
        source_path,
        default_stem,
        extension
    ):
        """Erzeugt einen freien Dateinamen ohne vorhandene Daten zu ersetzen."""

        directory = Path(directory_path)
        source = Path(source_path).resolve() if source_path else None
        stem = source.stem if source else default_stem
        candidate = directory / f"{stem}{extension}"

        if source is not None and candidate.resolve() == source:
            return candidate

        counter = 2

        while candidate.exists():
            candidate = directory / f"{stem}-{counter}{extension}"
            counter += 1

        return candidate

    def prepare_related_data_copies(self, project_file_path):
        """Schreibt zugeordnete Daten in die neue Projektstruktur."""

        project_directory = Path(project_file_path).resolve().parent
        copied_paths = {
            "training": None,
            "test": None,
        }
        specifications = (
            (
                "training",
                self.training_data_manager,
                "trainingsdaten",
                "trainingsdaten",
                ".nndata"
            ),
            (
                "test",
                self.test_data_manager,
                "testdaten",
                "testdaten",
                ".nntest"
            )
        )

        for key, manager, folder, default_stem, extension in specifications:
            if not manager.has_document:
                continue

            destination = self.unique_data_destination(
                project_directory / folder,
                manager.file_path,
                default_stem,
                extension
            )
            TrainingDataIO.save(
                destination,
                manager.document
            )
            copied_paths[key] = str(destination)

        return copied_paths

    def copy_graphical_experiment_to_project(self, project_file_path):
        """Übernimmt die gespeicherte Anwendungsansicht beim Speichern unter."""

        if not self.current_project_path:
            return

        source_directory = Path(self.current_project_path).resolve().parent
        target_directory = Path(project_file_path).resolve().parent

        if source_directory == target_directory:
            return

        source_layout_directory = source_directory / "grafisches_experiment"
        target_layout_directory = target_directory / "grafisches_experiment"

        if source_layout_directory.is_dir():
            shutil.copytree(
                source_layout_directory,
                target_layout_directory,
                dirs_exist_ok=True,
            )

        source_image = source_directory / "Experimentbild.png"
        if source_image.is_file():
            target_directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                source_image,
                target_directory / source_image.name,
            )

    def save_modified_related_data(self, project_file_path):
        """Speichert geänderte Trainings- und Testdaten mit dem Projekt."""

        project_directory = Path(project_file_path).resolve().parent
        saved_paths = {}
        specifications = (
            (
                "training",
                self.training_data_manager,
                "trainingsdaten",
                "trainingsdaten",
                ".nndata"
            ),
            (
                "test",
                self.test_data_manager,
                "testdaten",
                "testdaten",
                ".nntest"
            )
        )

        for key, manager, folder, default_stem, extension in specifications:
            if not manager.has_document or not manager.modified:
                continue

            file_path = manager.file_path

            if not file_path:
                directory = project_directory / folder
                directory.mkdir(
                    parents=True,
                    exist_ok=True
                )
                file_path = str(
                    self.unique_data_destination(
                        directory,
                        None,
                        default_stem,
                        extension
                    )
                )

            TrainingDataIO.save(
                file_path,
                manager.document
            )
            manager.set_document(
                manager.document,
                file_path=file_path,
                modified=False
            )
            saved_paths[key] = file_path

        return saved_paths

    def apply_copied_data_paths(self, copied_paths):
        """Übernimmt die neuen Datenpfade nach erfolgreichem Projektspeichern."""

        specifications = (
            (
                self.training_data_manager,
                copied_paths.get("training")
            ),
            (
                self.test_data_manager,
                copied_paths.get("test")
            )
        )

        for manager, file_path in specifications:
            if file_path and manager.has_document:
                manager.set_document(
                    manager.document,
                    file_path=file_path,
                    modified=False
                )

    def remember_project_directory(
        self,
        file_path
    ):
        """
        Merkt sich den Ordner einer erfolgreich geöffneten
        oder gespeicherten Projektdatei.
        """

        if not file_path:
            return

        directory_path = os.path.dirname(
            os.path.abspath(
                file_path
            )
        )

        try:
            Settings.save_last_project_directory(
                directory_path
            )
            for language_code in self.project_history_languages(file_path):
                Settings.add_recent_project_file(
                    file_path,
                    language_code
                )
                Settings.save_last_project_file(
                    file_path,
                    language_code
                )

            if hasattr(self, "recent_projects_menu"):
                self.update_recent_projects_menu()
            if hasattr(self, "example_projects_menu"):
                self.update_example_projects_menu()

        except OSError:
            # Ein nicht beschreibbarer Einstellungsordner darf
            # das Öffnen oder Speichern eines Projekts nicht
            # verhindern.
            pass

    def current_project_language(self):
        """Liefert den Sprachschlüssel für sprachabhängige Projektpfade."""

        language_code = str(
            self.language.current_language
        ).strip().lower()
        return language_code if language_code in {"de", "en"} else "en"

    @staticmethod
    def project_history_languages(file_path):
        """Ordnet Standardprojekte einer Sprache, eigene Projekte beiden zu."""

        path_parts = {
            part.casefold()
            for part in Path(file_path).expanduser().parts
        }
        if "projects_de" in path_parts:
            return ("de",)
        if "projects_en" in path_parts:
            return ("en",)
        return ("de", "en")

    def remove_project_from_history(self, file_path):
        """Entfernt einen Pfad aus allen Listen, in denen er erscheinen kann."""

        for language_code in self.project_history_languages(file_path):
            Settings.remove_recent_project_file(file_path, language_code)

    def update_recent_projects_menu(self):
        """Baut das Untermenü der zuletzt verwendeten Projekte neu auf."""

        self.recent_projects_menu.clear()

        try:
            recent_files = Settings.get_recent_project_files(
                self.current_project_language()
            )
        except OSError:
            recent_files = []

        if not recent_files:
            empty_action = self.recent_projects_menu.addAction(
                self.language.text(
                    "action.no_recent_projects"
                )
            )
            empty_action.setEnabled(False)
            return

        for index, file_path in enumerate(recent_files, start=1):
            project_name = Path(file_path).stem
            action = self.recent_projects_menu.addAction(
                f"&{index}  {project_name}"
            )
            action.setToolTip(file_path)
            action.setStatusTip(file_path)
            action.setProperty(
                "project_preview_html",
                self.project_description_preview(file_path)
            )
            action.triggered.connect(
                lambda checked=False, path=file_path: (
                    self.open_recent_project(path)
                )
            )

    def find_example_projects(self):
        """Findet gültig gekennzeichnete Beispiele im gesamten Projektordner."""

        project_root = Path(self.project_content_directory())
        if not project_root.is_dir():
            return []

        examples = []
        try:
            project_files = project_root.rglob("*.nnproj")
            for file_path in project_files:
                try:
                    with file_path.open("r", encoding="utf-8") as project_file:
                        project_data = json.load(project_file)
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue

                if not isinstance(project_data, dict):
                    continue
                difficulty = project_data.get("example_difficulty")
                if (
                    project_data.get("is_example_project") is not True
                    or isinstance(difficulty, bool)
                    or not isinstance(difficulty, int)
                    or not 1 <= difficulty <= 4
                ):
                    continue
                examples.append((
                    difficulty,
                    file_path.stem,
                    str(file_path),
                    self.format_project_description_preview(
                        project_data.get("project_description", "")
                    ),
                ))
        except OSError:
            return []

        return sorted(
            examples,
            key=lambda entry: (entry[0], entry[1].casefold(), entry[2].casefold())
        )

    def update_example_projects_menu(self):
        """Baut das Untermenü aus den gekennzeichneten Projektdateien auf."""

        self.example_projects_menu.clear()
        examples = self.find_example_projects()
        if not examples:
            empty_action = self.example_projects_menu.addAction(
                self.language.text("action.no_example_projects")
            )
            empty_action.setEnabled(False)
            empty_action.setToolTip(
                self.language.text("tooltip.no_example_projects")
            )
            return

        for difficulty, project_name, file_path, preview_html in examples:
            stars = "★" * difficulty
            star_padding = "\u2003" * (4 - difficulty)
            action = self.example_projects_menu.addAction(
                f"{stars}{star_padding}  {project_name}"
            )
            action.setToolTip(file_path)
            action.setStatusTip(file_path)
            action.setProperty("project_preview_html", preview_html)
            action.triggered.connect(
                lambda checked=False, path=file_path: (
                    self.open_example_project(path)
                )
            )

    def format_project_description_preview(self, description_html):
        """Erzeugt eine gekürzte, schreibgeschützte Rich-Text-Vorschau."""

        if not isinstance(description_html, str) or not description_html.strip():
            return ""
        document = QTextDocument()
        document.setHtml(description_html)
        plain_text = document.toPlainText().strip()
        if not plain_text:
            return ""
        maximum_characters = 900
        cursor = QTextCursor(document)
        cursor.setPosition(0)
        cursor.setPosition(
            min(maximum_characters, max(0, document.characterCount() - 1)),
            QTextCursor.MoveMode.KeepAnchor,
        )
        fragment_html = QTextDocumentFragment(cursor).toHtml()
        suffix = "…" if len(plain_text) > maximum_characters else ""
        return (
            "<div style='font-size:10pt; color:#202020;'>"
            + fragment_html + suffix + "</div>"
        )

    def project_description_preview(self, file_path):
        """Liest ausschließlich die Beschreibung einer erreichbaren Projektdatei."""

        try:
            with Path(file_path).open("r", encoding="utf-8") as project_file:
                project_data = json.load(project_file)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return ""
        if not isinstance(project_data, dict):
            return ""
        return self.format_project_description_preview(
            project_data.get("project_description", "")
        )

    def schedule_project_menu_preview(self, menu, action):
        """Zeigt die Projektbeschreibung erst nach ruhigem Verweilen an."""

        self.project_preview_popup.hide()
        self.project_preview_timer.stop()
        self.project_preview_menu = None
        self.project_preview_action = None
        if not self.ui_settings.get("show_project_menu_previews", True):
            return
        preview_html = action.property("project_preview_html")
        if not isinstance(preview_html, str) or not preview_html:
            return
        self.project_preview_menu = menu
        self.project_preview_action = action
        self.project_preview_timer.start()

    def show_scheduled_project_preview(self):
        menu = self.project_preview_menu
        action = self.project_preview_action
        if menu is None or action is None or not menu.isVisible():
            return
        preview_html = action.property("project_preview_html")
        if not preview_html:
            return
        action_rect = menu.actionGeometry(action)
        position = menu.mapToGlobal(
            QPoint(menu.width() + 8, action_rect.top())
        )
        self.project_preview_label.setText(preview_html)
        self.project_preview_popup.move(position)
        self.project_preview_popup.show()
        self.project_preview_popup.raise_()

    def hide_project_menu_preview(self):
        if hasattr(self, "project_preview_timer"):
            self.project_preview_timer.stop()
        self.project_preview_menu = None
        self.project_preview_action = None
        if hasattr(self, "project_preview_popup"):
            self.project_preview_popup.hide()

    def open_example_project(self, file_path):
        """Öffnet ein Beispielprojekt wie jedes andere Projekt."""

        if self.open_project(file_path):
            self.statusBar().showMessage(
                self.language.text(
                    "status.example_project.opened",
                    name=Path(file_path).stem
                ),
                5000
            )

    def open_recent_project(self, file_path):
        """Öffnet einen Verlaufseintrag oder entfernt einen ungültigen Pfad."""

        if not Path(file_path).is_file():
            QMessageBox.warning(
                self,
                self.language.text("dialog.recent_project_missing.title"),
                self.language.text(
                    "dialog.recent_project_missing.message",
                    file_path=file_path
                )
            )

            try:
                self.remove_project_from_history(file_path)
            except OSError:
                pass

            self.update_recent_projects_menu()
            return

        self.open_project(file_path)

    def open_startup_project(self, explicit_file_path=None):
        """Lädt beim Programmstart ein ausdrückliches oder gemerktes Projekt."""

        if explicit_file_path:
            return self.open_project(explicit_file_path)

        if not self.ui_settings.get("reopen_last_project", True):
            return False

        try:
            file_path = Settings.get_last_project_file(
                self.current_project_language()
            )
        except OSError:
            return False

        if not file_path:
            return False

        if not Path(file_path).is_file():
            try:
                Settings.clear_last_project_file(
                    self.current_project_language()
                )
                self.remove_project_from_history(file_path)
            except OSError:
                pass

            self.update_recent_projects_menu()
            self.statusBar().showMessage(
                self.language.text(
                    "status.project.startup_missing",
                    file_path=file_path
                ),
                10000
            )
            return False

        return self.open_project(file_path, automatic_start=True)

    def open_project(self, file_path=None, automatic_start=False):
        """
        Öffnet eine bestehende Projektdatei und lädt
        deren Neuronen, Verbindungen und Ansichtsdaten.
        """

        if not self.confirm_unsaved_changes():
            return False

        if not isinstance(file_path, (str, os.PathLike)):
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                self.language.text("dialog.project_open.title"),
                self.get_project_open_directory(),
                self.language.text("dialog.project_open.filter")
            )

        if not file_path:
            return False

        file_path = str(file_path)

        try:
            project_data = ProjectIO.load_project(
                file_path
            )

        except (
            OSError,
            ValueError,
            TypeError
        ) as error:
            QMessageBox.critical(
                self,
                self.language.text("dialog.project_open.error_title"),
                str(
                    error
                )
            )

            if automatic_start:
                try:
                    Settings.clear_last_project_file(
                        self.current_project_language()
                    )
                except OSError:
                    pass

            return False

        parameter_repairs = project_data.pop(
            "_parameter_repairs",
            []
        )

        training_data_result = (
            self.prepare_project_training_data(
                file_path,
                project_data
            )
        )

        if training_data_result[
            "cancelled"
        ]:
            return False

        test_data_result = self.prepare_project_test_data(
            file_path,
            project_data
        )

        if test_data_result["cancelled"]:
            return False

        self.reset_project()

        self.apply_display_settings(
            project_data[
                "display_settings"
            ],
            mark_as_modified=False
        )

        neurons_by_id = {}
        highest_neuron_id = 0

        # Zuerst alle Neuronen erzeugen
        for neuron_data in project_data["neurons"]:
            neuron = self.scene.add_neuron(
                neuron_data["id"],
                neuron_data["x"],
                neuron_data["y"],
                neuron_data["name"],
                mark_as_modified=False
            )

            neuron.neuron_type = NeuronType(
                neuron_data["type"]
            )

            neuron.bias = float(
                neuron_data["bias"]
            )

            neuron.activation_function = (
                neuron_data["activation"]
            )

            neuron.input_value = float(
                neuron_data["input_value"]
            )

            neuron.target_value = float(
                neuron_data["target_value"]
            )

            neurons_by_id[
                neuron.id
            ] = neuron

            highest_neuron_id = max(
                highest_neuron_id,
                neuron.id
            )

        # Danach alle Kommentare erzeugen
        highest_comment_id = 0

        for comment_data in project_data["comments"]:
            comment = self.scene.add_comment(
                comment_data["id"],
                comment_data["x"],
                comment_data["y"],
                comment_data["text"],
                comment_data["width"],
                comment_data["height"],
                comment_data["font_size"],
                mark_as_modified=False
            )

            highest_comment_id = max(
                highest_comment_id,
                comment.id
            )

        # Danach alle Verbindungen erzeugen
        highest_connection_id = 0

        for connection_data in project_data["connections"]:
            source_neuron = neurons_by_id[
                connection_data["source"]
            ]

            target_neuron = neurons_by_id[
                connection_data["target"]
            ]

            connection = self.scene.add_connection(
                connection_data["id"],
                source_neuron,
                target_neuron,
                connection_data["weight"],
                mark_as_modified=False
            )

            highest_connection_id = max(
                highest_connection_id,
                connection.id
            )

        self.scene.next_id = (
            highest_neuron_id + 1
        )

        self.scene.next_connection_id = (
            highest_connection_id + 1
        )

        self.scene.next_comment_id = (
            highest_comment_id + 1
        )

        saved_zoom = float(
            project_data["view"]["zoom"]
        )

        saved_center_x = float(
            project_data["view"]["center_x"]
        )

        saved_center_y = float(
            project_data["view"]["center_y"]
        )

        self.view.set_zoom(
            saved_zoom
        )

        QTimer.singleShot(
            0,
            lambda: self.view.centerOn(
                saved_center_x,
                saved_center_y
            )
        )

        self.training_settings = dict(
            project_data[
                "training_settings"
            ]
        )

        self.training_history = deepcopy(
            project_data.get(
                "training_history",
                []
            )
        )
        self.active_training_run_id = project_data.get("active_training_run_id")

        self.analysis_tolerances = {}
        for entry in project_data.get("analysis_tolerances", []):
            if not isinstance(entry, dict) or entry.get("neuron_id") is None:
                continue
            try:
                key = (
                    str(entry.get("source", "training")),
                    int(entry["neuron_id"]),
                )
                value = float(entry.get("value", 0.0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value >= 0.0:
                self.analysis_tolerances[key] = value

        self.project_description = str(
            project_data.get(
                "project_description",
                ""
            )
        )
        self.is_example_project = bool(
            project_data.get("is_example_project", False)
        )
        self.example_difficulty = project_data.get("example_difficulty")

        self.scene.network.set_learning_rate(
            self.training_settings[
                "learning_rate"
            ]
        )
        self.scene.network.set_momentum(
            self.training_settings.get("momentum", 0.0)
        )
        active_history_entry = next(
            (
                entry for entry in self.training_history
                if isinstance(entry, dict)
                and entry.get("run_id") == self.active_training_run_id
            ),
            None,
        )
        active_network_state = (
            active_history_entry.get("network_state")
            if isinstance(active_history_entry, dict) else None
        )
        saved_momentum_state = project_data.get("momentum_state")
        self.scene.network.restore_momentum_state(
            saved_momentum_state
            if isinstance(saved_momentum_state, dict)
            else (
                active_network_state.get("momentum_state")
                if isinstance(active_network_state, dict) else None
            )
        )

        self.current_project_path = file_path
        self.update_project_image_action()
        self.remember_project_directory(
            file_path
        )

        if training_data_result[
            "document"
        ] is not None:
            self.training_data_manager.set_document(
                training_data_result[
                    "document"
                ],
                file_path=training_data_result[
                    "file_path"
                ],
                modified=False
            )

            training_status = (
                self.language.text(
                    "status.project.training_data_loaded",
                    name=self.training_data_manager.display_name
                )
            )

        else:
            self.training_data_manager.clear()

            training_status = (
                self.language.text(
                    "status.project.no_training_data"
                )
            )

        if test_data_result["document"] is not None:
            self.test_data_manager.set_document(
                test_data_result["document"],
                file_path=test_data_result["file_path"],
                modified=False
            )
            test_status = (
                self.language.text(
                    "status.project.test_data_loaded",
                    name=self.test_data_manager.display_name
                )
            )
        else:
            self.test_data_manager.clear()
            test_status = self.language.text(
                "status.project.no_test_data"
            )

        mapping_repairs = self.reconcile_active_data_mappings()

        self.reset_undo_history(
            mark_as_saved=True
        )

        self.set_project_modified(
            (
                training_data_result["association_changed"]
                or test_data_result["association_changed"]
                or bool(parameter_repairs)
                or mapping_repairs
            )
        )

        if parameter_repairs:
            QMessageBox.warning(
                self,
                self.language.text("dialog.parameter_repair.title"),
                self.language.text(
                    "dialog.parameter_repair.message",
                    repairs="\n".join(parameter_repairs)
                )
            )

        self.statusBar().showMessage(
            self.language.text(
                "status.project.opened",
                file_path=file_path,
                training_status=training_status,
                test_status=test_status
            ),
            7000
        )

        self._pending_loaded_project_fit = self.current_project_path
        self.schedule_loaded_project_fit()
        return True

    def save_project(self):
        """
        Speichert das aktuelle Projekt.
        """

        if self.current_project_path is None:
            return self.save_project_as()

        saved = self.write_project_file(
            self.current_project_path
        )
        if saved:
            self.update_project_image_action()
            self.update_example_projects_menu()
        return saved

    def rename_current_project(self):
        """Benennt Projektordner und Projektdatei gemeinsam und sicher um."""

        if not self.current_project_path:
            QMessageBox.information(
                self,
                self.language.text("dialog.rename_project.title"),
                self.language.text("dialog.rename_project.no_project")
            )
            return False
        if self.project_modified and not self.save_project():
            return False

        old_file = Path(self.current_project_path).resolve()
        old_directory = old_file.parent
        old_name = old_file.stem
        if old_directory.name.casefold() != old_name.casefold():
            QMessageBox.warning(
                self,
                self.language.text("dialog.rename_project.title"),
                self.language.text("dialog.rename_project.folder_mismatch")
            )
            return False
        new_name, accepted = QInputDialog.getText(
            self,
            self.language.text("dialog.rename_project.title"),
            self.language.text("dialog.rename_project.prompt"),
            QLineEdit.EchoMode.Normal,
            old_name
        )
        if not accepted:
            return False
        new_name = new_name.strip()
        invalid_characters = '<>:"/\\|?*'
        reserved_names = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{number}" for number in range(1, 10)),
            *(f"LPT{number}" for number in range(1, 10)),
        }
        if (
            not new_name
            or new_name.endswith((".", " "))
            or any(character in new_name for character in invalid_characters)
            or new_name.upper() in reserved_names
        ):
            QMessageBox.warning(
                self,
                self.language.text("dialog.rename_project.title"),
                self.language.text("dialog.rename_project.invalid")
            )
            return False
        if new_name.casefold() == old_name.casefold():
            return True

        new_directory = old_directory.with_name(new_name)
        new_file = new_directory / f"{new_name}.nnproj"
        if new_directory.exists() or new_file.exists():
            QMessageBox.warning(
                self,
                self.language.text("dialog.rename_project.title"),
                self.language.text(
                    "dialog.rename_project.exists",
                    name=new_name
                )
            )
            return False

        directory_moved = False
        try:
            old_directory.rename(new_directory)
            directory_moved = True
            moved_old_file = new_directory / old_file.name
            moved_old_file.rename(new_file)
        except OSError as error:
            if directory_moved and new_directory.exists():
                try:
                    moved_old_file = new_directory / old_file.name
                    if new_file.exists() and not moved_old_file.exists():
                        new_file.rename(moved_old_file)
                    new_directory.rename(old_directory)
                except OSError:
                    pass
            QMessageBox.critical(
                self,
                self.language.text("dialog.rename_project.title"),
                self.language.text(
                    "dialog.rename_project.failed",
                    error=str(error)
                )
            )
            return False

        for manager in (self.training_data_manager, self.test_data_manager):
            manager_path = manager.file_path
            if not manager_path:
                continue
            try:
                relative_path = Path(manager_path).resolve().relative_to(
                    old_directory
                )
            except (OSError, ValueError):
                continue
            manager.set_document(
                manager.document,
                file_path=str(new_directory / relative_path),
                modified=manager.modified
            )

        for history_entry in self.training_history:
            if not isinstance(history_entry, dict):
                continue
            history_path = history_entry.get("training_data_path")
            if not history_path:
                continue
            try:
                relative_path = Path(history_path).resolve().relative_to(
                    old_directory
                )
            except (OSError, ValueError):
                continue
            history_entry["training_data_path"] = str(
                new_directory / relative_path
            )

        try:
            self.remove_project_from_history(str(old_file))
        except OSError:
            pass
        self.current_project_path = str(new_file)
        if not self.write_project_file(self.current_project_path):
            return False
        self.remember_project_directory(self.current_project_path)
        self.update_window_title()
        self.update_project_image_action()
        self.update_recent_projects_menu()
        self.update_example_projects_menu()
        self.statusBar().showMessage(
            self.language.text(
                "status.project.renamed",
                old_name=old_name,
                new_name=new_name
            ),
            5000
        )
        return True

    def save_project_as(self):
        """
        Fragt einen Dateinamen ab und speichert
        das aktuelle Projekt unter diesem Namen.
        """

        project_name, base_directory = (
            self.project_save_dialog_defaults()
        )
        has_related_data = (
            self.training_data_manager.has_document
            or self.test_data_manager.has_document
        )
        dialog = ProjectSaveDialog(
            project_name,
            base_directory,
            has_related_data=has_related_data,
            language_manager=self.language,
            parent=self
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return False

        file_path = str(
            dialog.project_file_path()
        )

        if Path(file_path).exists():
            message_box = QMessageBox(
                self
            )
            message_box.setIcon(
                QMessageBox.Icon.Question
            )
            message_box.setWindowTitle(
                self.language.text("dialog.project_overwrite.title")
            )
            message_box.setText(
                self.language.text(
                    "dialog.project_overwrite.message",
                    file_path=file_path
                )
            )
            message_box.setStandardButtons(
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )
            message_box.setDefaultButton(
                QMessageBox.StandardButton.No
            )
            self.localize_message_box_buttons(
                message_box
            )
            overwrite = message_box.exec()

            if overwrite != QMessageBox.StandardButton.Yes:
                return False

        copied_paths = None

        try:
            if dialog.create_project_folder:
                self.create_project_directory_structure(
                    file_path
                )

            if dialog.copy_related_data:
                copied_paths = self.prepare_related_data_copies(
                    file_path
                )

            self.copy_graphical_experiment_to_project(
                file_path
            )

        except (OSError, TypeError, ValueError) as error:
            QMessageBox.critical(
                self,
                self.language.text("dialog.project_folder_error.title"),
                str(error)
            )
            return False

        if not self.write_project_file(
            file_path,
            data_file_paths=copied_paths
        ):
            return False

        if copied_paths is not None:
            self.apply_copied_data_paths(
                copied_paths
            )

        self.current_project_path = file_path
        self.update_project_image_action()
        self.remember_project_directory(
            file_path
        )

        self.set_project_modified(
            False
        )

        return True

    def write_project_file(
        self,
        file_path,
        data_file_paths=None,
        save_as_normal_copy=False
    ):
        """
        Schreibt das aktuelle Projekt einschließlich
        des aktuellen Zoomfaktors in eine Datei.
        """

        try:
            if data_file_paths is None:
                saved_data_paths = self.save_modified_related_data(
                    file_path
                )

                if saved_data_paths:
                    data_file_paths = saved_data_paths

            viewport_center = self.view.mapToScene(
                self.view.viewport().rect().center()
            )

            training_data_file_path = (
                data_file_paths.get(
                    "training",
                    self.training_data_manager.file_path
                )
                if data_file_paths is not None
                else self.training_data_manager.file_path
            )
            test_data_file_path = (
                data_file_paths.get(
                    "test",
                    self.test_data_manager.file_path
                )
                if data_file_paths is not None
                else self.test_data_manager.file_path
            )
            ProjectIO.save_project(
                file_path,
                self.scene,
                self.view.get_zoom(),
                viewport_center.x(),
                viewport_center.y(),
                training_data_file_path=(
                    training_data_file_path
                ),
                test_data_file_path=(
                    test_data_file_path
                ),
                training_settings=self.training_settings,
                display_settings=self.display_settings,
                training_history=self.training_history,
                active_training_run_id=self.active_training_run_id,
                momentum_state=self.scene.network.get_momentum_state(),
                project_description=self.project_description,
                is_example_project=(
                    False if save_as_normal_copy else self.is_example_project
                ),
                example_difficulty=(
                    None if save_as_normal_copy else self.example_difficulty
                ),
                analysis_tolerances=[
                    {
                        "source": key[0],
                        "neuron_id": key[1],
                        "value": value,
                    }
                    for key, value in self.analysis_tolerances.items()
                ],
            )

        except (
            OSError,
            TypeError,
            ValueError
        ) as error:
            QMessageBox.critical(
                self,
                self.language.text("dialog.project_save_error.title"),
                str(
                    error
                )
            )

            return False

        self.set_project_modified(
            False
        )

        self.statusBar().showMessage(
            self.language.text(
                "status.project.saved",
                file_path=file_path
            ),
            5000
        )

        return True

    def closeEvent(
        self,
        event
    ):
        """
        Prüft beim Beenden, ob noch
        ungespeicherte Änderungen vorhanden sind.

        Bei bestätigtem Beenden werden außerdem
        Fensterposition, Fenstergröße und der
        maximierte Zustand sowie die Anordnung der
        Werkzeugleisten gespeichert.
        """

        if self.training_observation_mode:
            if self.training_dialog is not None:
                self.training_dialog.showNormal()
                self.training_dialog.raise_()
                self.training_dialog.activateWindow()

            self.statusBar().showMessage(
                self.language.text("status.close_training_first"),
                5000
            )
            event.ignore()
            return

        if not self.confirm_unsaved_changes():
            event.ignore()
            return

        self._is_closing = True

        try:
            self.ui_settings["property_dock_visible"] = (
                self.property_dock.isVisible()
            )
            self.ui_settings["property_dock_width"] = (
                self.property_dock.width()
            )
            Settings.save_ui_settings(
                self.ui_settings
            )

            settings_path = Settings.save_window(
                self
            )

            print(
                "Programmeinstellungen gespeichert:",
                settings_path
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                self.language.text("dialog.window_settings_error.title"),
                self.language.text("dialog.window_settings_error.message", error=error)
            )

            self._is_closing = False
            event.ignore()
            return

        event.accept()
