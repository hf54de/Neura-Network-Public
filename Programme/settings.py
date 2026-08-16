# -------------------------------------------------------------------------------------------------
# Datei: settings.py
# Zweck: Speichert und lädt projektunabhängige Programmeinstellungen.
# Letzte Änderung: 11.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import base64
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray


class Settings:
    """
    Verwaltet programmeigene Einstellungen.

    Zuständig für:
        - Fensterposition
        - Fenstergröße
        - maximierten Fensterzustand
        - Position und Sichtbarkeit von Werkzeugleisten
        - persönliche Bedienoberfläche und Editorwerte
        - zuletzt verwendeten Projektordner
        - zuletzt bearbeitete Projektdatei und automatischen Projektstart
    """

    SETTINGS_FILE_NAME = "settings.json"
    SETTINGS_DIRECTORY_NAME = "NeuronNetz"
    MAX_RECENT_PROJECTS = 5
    PROJECT_ASSISTANT_FIELDS = (
        "starting_point",
        "interest",
        "project_type",
        "relationship",
        "training_data",
        "difficulty",
        "exclusions"
    )

    @staticmethod
    def language_path_key(base_key, language_code=None):
        """Erzeugt für Deutsch und Englisch getrennte Pfadschlüssel."""

        normalized = str(language_code or "").strip().lower()
        if normalized in {"de", "en"}:
            return f"{base_key}_{normalized}"
        return base_key

    @classmethod
    def get_settings_path(cls):
        app_data_directory = os.environ.get("APPDATA")

        if app_data_directory:
            settings_directory = (
                Path(app_data_directory)
                / cls.SETTINGS_DIRECTORY_NAME
            )
        else:
            settings_directory = (
                Path.home()
                / ".config"
                / cls.SETTINGS_DIRECTORY_NAME
            )

        return settings_directory / cls.SETTINGS_FILE_NAME

    @classmethod
    def get_legacy_settings_path(cls):
        """Früher lag settings.json direkt neben der Programmdatei."""

        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().with_name(
                cls.SETTINGS_FILE_NAME
            )

        return Path(__file__).resolve().with_name(cls.SETTINGS_FILE_NAME)

    @staticmethod
    def load_file(settings_path):
        try:
            with settings_path.open(
                mode="r",
                encoding="utf-8"
            ) as settings_file:
                settings_data = json.load(settings_file)

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError
        ):
            return None

        return settings_data if isinstance(settings_data, dict) else None

    @classmethod
    def load(cls):
        settings_path = cls.get_settings_path()

        if settings_path.exists():
            return cls.load_file(settings_path) or {}

        legacy_path = cls.get_legacy_settings_path()

        if legacy_path != settings_path and legacy_path.exists():
            legacy_data = cls.load_file(legacy_path)

            if legacy_data is not None:
                try:
                    cls.save(legacy_data)
                except OSError:
                    pass

                return legacy_data

        return {}

    @classmethod
    def save(cls, settings_data):
        """
        Speichert die Programmeinstellungen und
        liefert den verwendeten Dateipfad zurück.
        """

        settings_path = cls.get_settings_path()

        settings_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with settings_path.open(
            mode="w",
            encoding="utf-8"
        ) as settings_file:
            json.dump(
                settings_data,
                settings_file,
                ensure_ascii=False,
                indent=4
            )

        return settings_path

    @classmethod
    def save_window(cls, window):
        geometry_data = bytes(
            window.saveGeometry().toBase64()
        ).decode(
            "ascii"
        )
        state_data = bytes(
            window.saveState().toBase64()
        ).decode(
            "ascii"
        )

        settings_data = cls.load()

        settings_data["window"] = {
            "geometry": geometry_data,
            "state": state_data,
            "maximized": bool(
                window.isMaximized()
            )
        }

        return cls.save(
            settings_data
        )

    @classmethod
    def get_last_project_directory(cls):
        """
        Liefert den zuletzt verwendeten Projektordner.

        Nicht mehr vorhandene oder ungültige Verzeichnisse
        werden ignoriert.
        """

        settings_data = cls.load()
        paths_data = settings_data.get(
            "paths"
        )

        if not isinstance(
            paths_data,
            dict
        ):
            return ""

        directory_text = paths_data.get(
            "last_project_directory"
        )

        if not isinstance(
            directory_text,
            str
        ):
            return ""

        directory_text = directory_text.strip()

        if not directory_text:
            return ""

        directory_path = Path(
            directory_text
        )

        if not directory_path.is_dir():
            return ""

        return str(
            directory_path
        )

    @classmethod
    def save_last_project_directory(
        cls,
        directory_path
    ):
        """
        Speichert den zuletzt verwendeten Projektordner.
        Andere Programmeinstellungen bleiben erhalten.
        """

        directory_path = Path(
            directory_path
        )

        if not directory_path.is_dir():
            return False

        settings_data = cls.load()
        paths_data = settings_data.get(
            "paths"
        )

        if not isinstance(
            paths_data,
            dict
        ):
            paths_data = {}

        paths_data["last_project_directory"] = str(
            directory_path
        )
        settings_data["paths"] = paths_data

        cls.save(
            settings_data
        )

        return True

    @classmethod
    def get_last_project_file(cls, language_code=None):
        """Liefert den zuletzt erfolgreich verwendeten Projektpfad."""

        settings_data = cls.load()
        paths_data = settings_data.get("paths")

        if not isinstance(paths_data, dict):
            return ""

        key = cls.language_path_key("last_project_file", language_code)
        file_path = paths_data.get(key)
        if file_path is None and language_code:
            file_path = paths_data.get("last_project_file")

        if not isinstance(file_path, str):
            return ""

        return file_path.strip()

    @classmethod
    def save_last_project_file(cls, file_path, language_code=None):
        """Speichert die zuletzt erfolgreich verwendete Projektdatei."""

        if not file_path:
            return False

        normalized_path = str(
            Path(file_path).expanduser().resolve()
        )
        settings_data = cls.load()
        paths_data = settings_data.get("paths")

        if not isinstance(paths_data, dict):
            paths_data = {}

        key = cls.language_path_key("last_project_file", language_code)
        paths_data[key] = normalized_path
        settings_data["paths"] = paths_data
        cls.save(settings_data)
        return True

    @classmethod
    def clear_last_project_file(cls, language_code=None):
        """Entfernt einen ungültigen automatischen Startpfad."""

        settings_data = cls.load()
        paths_data = settings_data.get("paths")

        if not isinstance(paths_data, dict):
            return False

        key = cls.language_path_key("last_project_file", language_code)
        paths_data.pop(key, None)
        settings_data["paths"] = paths_data
        cls.save(settings_data)
        return True

    @classmethod
    def get_tutorials_directory(cls):
        """Liefert den persönlich ausgewählten Tutorial-Ordner."""

        settings_data = cls.load()
        paths_data = settings_data.get(
            "paths"
        )

        if not isinstance(paths_data, dict):
            return ""

        directory_text = paths_data.get(
            "tutorials_directory"
        )

        if not isinstance(directory_text, str):
            return ""

        return directory_text.strip()

    @classmethod
    def save_tutorials_directory(
        cls,
        directory_path
    ):
        """
        Speichert den persönlichen Tutorial-Ordner, ohne andere
        Programmeinstellungen zu verändern.
        """

        directory_path = Path(
            directory_path
        ).expanduser().resolve()

        if not directory_path.is_dir():
            return False

        settings_data = cls.load()
        paths_data = settings_data.get(
            "paths"
        )

        if not isinstance(paths_data, dict):
            paths_data = {}

        paths_data["tutorials_directory"] = str(
            directory_path
        )
        settings_data["paths"] = paths_data
        cls.save(
            settings_data
        )

        return True

    @classmethod
    def get_recent_project_files(cls, language_code=None):
        """Liefert höchstens fünf zuletzt verwendete Projektdateien."""

        settings_data = cls.load()
        paths_data = settings_data.get("paths")

        if not isinstance(paths_data, dict):
            return []

        key = cls.language_path_key("recent_project_files", language_code)
        stored_files = paths_data.get(key)
        if stored_files is None and language_code:
            stored_files = paths_data.get("recent_project_files")

        if not isinstance(stored_files, list):
            return []

        recent_files = []
        known_paths = set()
        normalized_language = str(language_code or "").strip().lower()

        for file_path in stored_files:
            if not isinstance(file_path, str) or not file_path.strip():
                continue

            normalized_path = str(
                Path(file_path).expanduser().resolve()
            )
            path_parts = {
                part.casefold()
                for part in Path(normalized_path).parts
            }
            if (
                normalized_language == "de"
                and "projects_en" in path_parts
            ):
                continue
            if (
                normalized_language == "en"
                and "projects_de" in path_parts
            ):
                continue
            comparison_path = normalized_path.casefold()

            if comparison_path in known_paths:
                continue

            known_paths.add(comparison_path)
            recent_files.append(normalized_path)

            if len(recent_files) >= cls.MAX_RECENT_PROJECTS:
                break

        return recent_files

    @classmethod
    def add_recent_project_file(cls, file_path, language_code=None):
        """Setzt eine Projektdatei an den Anfang der Verlaufsliste."""

        if not file_path:
            return False

        normalized_path = str(
            Path(file_path).expanduser().resolve()
        )
        comparison_path = normalized_path.casefold()
        recent_files = [
            stored_path
            for stored_path in cls.get_recent_project_files(language_code)
            if stored_path.casefold() != comparison_path
        ]
        recent_files.insert(0, normalized_path)
        recent_files = recent_files[:cls.MAX_RECENT_PROJECTS]

        settings_data = cls.load()
        paths_data = settings_data.get("paths")

        if not isinstance(paths_data, dict):
            paths_data = {}

        key = cls.language_path_key("recent_project_files", language_code)
        paths_data[key] = recent_files
        settings_data["paths"] = paths_data
        cls.save(settings_data)
        return True

    @classmethod
    def remove_recent_project_file(cls, file_path, language_code=None):
        """Entfernt eine Projektdatei aus der Verlaufsliste."""

        if not file_path:
            return False

        comparison_path = str(
            Path(file_path).expanduser().resolve()
        ).casefold()
        recent_files = [
            stored_path
            for stored_path in cls.get_recent_project_files(language_code)
            if stored_path.casefold() != comparison_path
        ]

        settings_data = cls.load()
        paths_data = settings_data.get("paths")

        if not isinstance(paths_data, dict):
            paths_data = {}

        key = cls.language_path_key("recent_project_files", language_code)
        paths_data[key] = recent_files
        settings_data["paths"] = paths_data
        cls.save(settings_data)
        return True

    @staticmethod
    def default_ui_settings():
        return {
            "language": "en",
            "toolbar_icon_size": 18,
            "toolbar_show_text": True,
            "toolbars_visible": True,
            "toolbar_auto_size": True,
            "toolbar_vertical_width": 86,
            "toolbar_horizontal_height": 68,
            "property_dock_visible": True,
            "property_dock_width": 305,
            "project_workflow_visible": True,
            "simplify_large_moves": True,
            "forward_dialog_width": 760,
            "reopen_last_project": True,
            "show_startup_splash": True,
            "show_project_menu_previews": True,
            "show_project_assistant": True,
            "project_directory": "",
            "editor_scene_margin": 100,
            "editor_zoom_step_percent": 15
        }

    @classmethod
    def normalize_ui_settings(cls, ui_settings):
        normalized = cls.default_ui_settings()

        if not isinstance(ui_settings, dict):
            return normalized

        language = ui_settings.get("language")

        if isinstance(language, str) and language.strip():
            normalized["language"] = language.strip().lower()

        icon_size = ui_settings.get("toolbar_icon_size")

        if isinstance(icon_size, int) and not isinstance(icon_size, bool):
            normalized["toolbar_icon_size"] = max(12, min(icon_size, 36))

        show_text = ui_settings.get("toolbar_show_text")

        if isinstance(show_text, bool):
            normalized["toolbar_show_text"] = show_text

        visible = ui_settings.get("toolbars_visible")

        if isinstance(visible, bool):
            normalized["toolbars_visible"] = visible

        toolbar_auto_size = ui_settings.get("toolbar_auto_size")
        if isinstance(toolbar_auto_size, bool):
            normalized["toolbar_auto_size"] = toolbar_auto_size

        vertical_width = ui_settings.get("toolbar_vertical_width")
        if isinstance(vertical_width, int) and not isinstance(vertical_width, bool):
            normalized["toolbar_vertical_width"] = max(70, min(vertical_width, 160))

        horizontal_height = ui_settings.get("toolbar_horizontal_height")
        if isinstance(horizontal_height, int) and not isinstance(horizontal_height, bool):
            normalized["toolbar_horizontal_height"] = max(50, min(horizontal_height, 100))

        simplify_large_moves = ui_settings.get("simplify_large_moves")
        if isinstance(simplify_large_moves, bool):
            normalized["simplify_large_moves"] = simplify_large_moves

        property_dock_visible = ui_settings.get(
            "property_dock_visible"
        )

        if isinstance(property_dock_visible, bool):
            normalized["property_dock_visible"] = property_dock_visible

        project_workflow_visible = ui_settings.get("project_workflow_visible")
        if isinstance(project_workflow_visible, bool):
            normalized["project_workflow_visible"] = project_workflow_visible

        property_dock_width = ui_settings.get(
            "property_dock_width"
        )

        if isinstance(property_dock_width, int) and not isinstance(
            property_dock_width,
            bool
        ):
            normalized["property_dock_width"] = max(
                190,
                min(property_dock_width, 800)
            )

        forward_dialog_width = ui_settings.get("forward_dialog_width")
        if isinstance(forward_dialog_width, int) and not isinstance(
            forward_dialog_width,
            bool
        ):
            normalized["forward_dialog_width"] = max(
                700,
                min(forward_dialog_width, 2400)
            )

        reopen_last_project = ui_settings.get(
            "reopen_last_project"
        )

        if isinstance(reopen_last_project, bool):
            normalized["reopen_last_project"] = reopen_last_project

        show_startup_splash = ui_settings.get(
            "show_startup_splash"
        )
        if isinstance(show_startup_splash, bool):
            normalized["show_startup_splash"] = show_startup_splash

        show_previews = ui_settings.get("show_project_menu_previews")
        if isinstance(show_previews, bool):
            normalized["show_project_menu_previews"] = show_previews

        show_project_assistant = ui_settings.get(
            "show_project_assistant"
        )
        if isinstance(show_project_assistant, bool):
            normalized["show_project_assistant"] = show_project_assistant

        project_directory = ui_settings.get("project_directory")
        if isinstance(project_directory, str):
            normalized["project_directory"] = project_directory.strip()

        scene_margin = ui_settings.get("editor_scene_margin")

        if isinstance(scene_margin, int) and not isinstance(scene_margin, bool):
            normalized["editor_scene_margin"] = max(
                20,
                min(scene_margin, 500)
            )

        zoom_step = ui_settings.get("editor_zoom_step_percent")

        if isinstance(zoom_step, int) and not isinstance(zoom_step, bool):
            normalized["editor_zoom_step_percent"] = max(
                5,
                min(zoom_step, 50)
            )

        return normalized

    @classmethod
    def get_ui_settings(cls):
        settings_data = cls.load()
        return cls.normalize_ui_settings(
            settings_data.get("ui")
        )

    @classmethod
    def save_ui_settings(cls, ui_settings):
        settings_data = cls.load()
        settings_data["ui"] = cls.normalize_ui_settings(
            ui_settings
        )
        return cls.save(settings_data)

    @classmethod
    def get_project_assistant_selections(cls):
        """Liefert die zuletzt verwendeten projektunabhängigen Auswahlen."""

        settings_data = cls.load()
        stored = settings_data.get("project_assistant")

        if not isinstance(stored, dict):
            return {
                field_name: ""
                for field_name in cls.PROJECT_ASSISTANT_FIELDS
            }

        return {
            field_name: (
                stored.get(field_name, "")
                if isinstance(stored.get(field_name, ""), str)
                else ""
            )
            for field_name in cls.PROJECT_ASSISTANT_FIELDS
        }

    @classmethod
    def save_project_assistant_selections(cls, selections):
        """Speichert ausschließlich die sieben Dropdown-Auswahlen."""

        selections = selections if isinstance(selections, dict) else {}
        settings_data = cls.load()
        settings_data["project_assistant"] = {
            field_name: (
                selections.get(field_name, "")
                if isinstance(selections.get(field_name, ""), str)
                else ""
            )
            for field_name in cls.PROJECT_ASSISTANT_FIELDS
        }
        return cls.save(settings_data)

    @classmethod
    def restore_window(cls, window):
        settings_data = cls.load()

        window_data = settings_data.get(
            "window"
        )

        if not isinstance(
            window_data,
            dict
        ):
            return False

        geometry_data = window_data.get(
            "geometry"
        )

        if isinstance(
            geometry_data,
            str
        ):
            try:
                geometry_bytes = base64.b64decode(
                    geometry_data.encode(
                        "ascii"
                    ),
                    validate=True
                )

                window.restoreGeometry(
                    QByteArray(
                        geometry_bytes
                    )
                )

            except (
                ValueError,
                TypeError
            ):
                pass

        state_data = window_data.get(
            "state"
        )

        if isinstance(state_data, str):
            try:
                state_bytes = base64.b64decode(
                    state_data.encode("ascii"),
                    validate=True
                )
                window.restoreState(
                    QByteArray(state_bytes)
                )
            except (ValueError, TypeError):
                pass

        return bool(
            window_data.get(
                "maximized",
                False
            )
        )
