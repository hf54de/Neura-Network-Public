"""Portable appearance and UI profiles, independent of project data."""
import json
import sys
from pathlib import Path

from atomicjson import write_json_atomic
from projectio import ProjectIO
from settings import Settings


class SettingsProfile:
    LOCAL_KEYS = {"project_directory", "property_dock_width", "forward_dialog_width"}

    @staticmethod
    def directory():
        root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        return root / "Profile"

    @classmethod
    def build(cls, display, ui):
        return {"format": "NeuronNetz-settings-profile", "version": 1,
                "display": ProjectIO.normalize_display_settings(display),
                "ui": {k: v for k, v in Settings.normalize_ui_settings(ui).items() if k not in cls.LOCAL_KEYS}}

    @classmethod
    def validate(cls, data):
        if not isinstance(data, dict) or data.get("format") != "NeuronNetz-settings-profile" or data.get("version") != 1:
            raise ValueError("Unsupported profile format / Nicht unterstütztes Profilformat")
        display, ui = data.get("display", {}), data.get("ui", {})
        if not isinstance(display, dict) or not isinstance(ui, dict):
            raise ValueError("Invalid settings / Ungültige Einstellungen")
        normalized = ProjectIO.normalize_display_settings(display)
        ProjectIO._validate_display_settings_data(normalized)
        defaults = Settings.default_ui_settings()
        for key, value in ui.items():
            if key in defaults and type(value) is not type(defaults[key]):
                raise ValueError(f"Invalid setting / Ungültige Einstellung: {key}")
        if ui.get("language", "en") not in ("de", "en"):
            raise ValueError("Invalid language / Ungültige Sprache")
        return cls.build(normalized, ui)

    @classmethod
    def read(cls, path):
        return cls.validate(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    @classmethod
    def write(cls, path, data):
        write_json_atomic(path, cls.validate(data))
