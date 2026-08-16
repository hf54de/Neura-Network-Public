# -------------------------------------------------------------------------------------------------
# Datei: projectio.py
# Zweck: Liest, schreibt und normalisiert NeuronNetz-Projektdateien.
# Letzte Änderung: 08.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import json
import math
import os
import re
from copy import deepcopy
from pathlib import Path

from commentitem import CommentItem
from connection import Connection
from neuron import Neuron
from neurontype import NeuronType


class ProjectIO:
    """
    Zuständig für das Speichern und Laden
    von NeuronNetz-Projektdateien.
    """

    PROJECT_VERSION = 15

    @classmethod
    def save_project(
        cls,
        file_path,
        scene,
        zoom=1.0,
        center_x=0.0,
        center_y=0.0,
        training_data_file_path=None,
        test_data_file_path=None,
        training_settings=None,
        display_settings=None,
        training_history=None,
        active_training_run_id=None,
        momentum_state=None,
        project_description="",
        analysis_tolerances=None,
        is_example_project=False,
        example_difficulty=None,
    ):
        """
        Speichert alle Neuronen, Verbindungen und
        Ansichtseinstellungen der übergebenen Szene
        in einer Projektdatei.
        """

        neurons = [
            item
            for item in scene.items()
            if isinstance(item, Neuron)
        ]

        comments = [
            item
            for item in scene.items()
            if isinstance(item, CommentItem)
        ]

        connections = [
            item
            for item in scene.items()
            if isinstance(item, Connection)
        ]

        neurons.sort(
            key=lambda neuron: neuron.id
        )

        comments.sort(
            key=lambda comment: comment.id
        )

        connections.sort(
            key=lambda connection: connection.id
        )

        training_data_reference = (
            cls.create_training_data_reference(
                file_path,
                training_data_file_path
            )
        )

        test_data_reference = (
            cls.create_training_data_reference(
                file_path,
                test_data_file_path
            )
        )

        normalized_training_settings = (
            cls.normalize_training_settings(
                training_settings
            )
        )

        cls._validate_training_settings_data(
            normalized_training_settings
        )

        normalized_display_settings = (
            cls.normalize_display_settings(
                display_settings
            )
        )

        cls._validate_display_settings_data(
            normalized_display_settings
        )

        normalized_training_history = (
            []
            if training_history is None
            else deepcopy(training_history)
        )

        cls._validate_training_history_data(
            normalized_training_history
        )

        if active_training_run_id is not None:
            if (
                isinstance(active_training_run_id, bool)
                or not isinstance(active_training_run_id, int)
                or active_training_run_id < 1
            ):
                raise TypeError(
                    "Die Kennung des aktiven Trainingslaufs ist ungültig."
                )

        if not isinstance(project_description, str):
            raise TypeError(
                "Die Projektbeschreibung muss Text enthalten."
            )

        normalized_example_project = bool(is_example_project)
        normalized_example_difficulty = (
            int(example_difficulty)
            if isinstance(example_difficulty, int)
            and not isinstance(example_difficulty, bool)
            and 1 <= example_difficulty <= 4
            else None
        )
        if normalized_example_project and normalized_example_difficulty is None:
            raise ValueError(
                "Ein Beispielprojekt benötigt einen Schwierigkeitsgrad von 1 bis 4."
            )

        normalized_analysis_tolerances = (
            [] if analysis_tolerances is None else deepcopy(analysis_tolerances)
        )
        if not isinstance(normalized_analysis_tolerances, list):
            raise TypeError("Die Analysetoleranzen müssen als Liste gespeichert werden.")

        project_data = {
            "version": cls.PROJECT_VERSION,
            "training_data": (
                {
                    "file": training_data_reference
                }
                if training_data_reference
                else None
            ),
            "test_data": (
                {
                    "file": test_data_reference
                }
                if test_data_reference
                else None
            ),
            "training_settings": normalized_training_settings,
            "training_history": normalized_training_history,
            "active_training_run_id": active_training_run_id,
            "momentum_state": deepcopy(momentum_state),
            "project_description": project_description,
            "analysis_tolerances": normalized_analysis_tolerances,
            "display_settings": normalized_display_settings,
            "view": {
                "zoom": float(zoom),
                "center_x": float(center_x),
                "center_y": float(center_y)
            },
            "neurons": [],
            "comments": [],
            "connections": []
        }

        if normalized_example_project:
            project_data["is_example_project"] = True
            project_data["example_difficulty"] = normalized_example_difficulty

        for neuron in neurons:
            project_data["neurons"].append(
                {
                    "id": neuron.id,
                    "name": neuron.name,
                    "type": neuron.neuron_type.value,
                    "bias": neuron.bias,
                    "activation": neuron.activation_function,
                    "input_value": neuron.input_value,
                    "target_value": neuron.target_value,
                    "x": neuron.x(),
                    "y": neuron.y()
                }
            )

        for comment in comments:
            project_data["comments"].append(
                {
                    "id": comment.id,
                    "text": comment.text,
                    "x": comment.x(),
                    "y": comment.y(),
                    "width": comment.width,
                    "height": comment.height,
                    "font_size": comment.font_size
                }
            )

        for connection in connections:
            project_data["connections"].append(
                {
                    "id": connection.id,
                    "source": connection.source_neuron.id,
                    "target": connection.target_neuron.id,
                    "weight": connection.weight
                }
            )

        path = Path(file_path)

        with path.open(
            mode="w",
            encoding="utf-8"
        ) as project_file:
            json.dump(
                project_data,
                project_file,
                ensure_ascii=False,
                indent=4
            )

    @staticmethod
    def default_training_settings():
        """
        Liefert die Standardwerte für den Trainingsdialog.
        """

        return {
            "initialize_network": False,
            "weight_initialization": "xavier",
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

    @staticmethod
    def default_display_settings():
        """
        Liefert die Standardwerte der Netzwerkdarstellung.
        """

        return {
            "show_weights": True,
            "visualize_weights": True,
            "show_neuron_values": True,
            "show_activation_charts": True,
            "show_io_value_fields": True,
            "show_ports": True,
            "show_neuron_names": True,
            "show_comments": True,
            "colors": ProjectIO.default_color_settings()
        }

    @staticmethod
    def default_color_settings():
        return {
            "input_header": "#a0cdf5",
            "hidden_header": "#f5d278",
            "output_header": "#9bdca5",
            "neuron_background": "#fff7cc",
            "input_port": "#3c82dc",
            "output_port": "#28aa5a",
            "positive_weight": "#2870af",
            "negative_weight": "#c34137",
            "neutral_weight": "#696969",
            "selection": "#d00000",
            "comment_background": "#fff8b4",
            "canvas_background": "#ffffff",
            "binary_array_on": "#242424",
            "binary_array_off": "#ffffff"
        }

    @classmethod
    def normalize_display_settings(
        cls,
        display_settings
    ):
        """
        Ergänzt fehlende Darstellungsoptionen mit
        Standardwerten und liefert ein unabhängiges Dictionary.
        """

        normalized = cls.default_display_settings()

        if display_settings is None:
            return normalized

        if not isinstance(
            display_settings,
            dict
        ):
            raise TypeError(
                "Die Darstellungseinstellungen müssen "
                "als Dictionary vorliegen."
            )

        for key in normalized:
            if key == "colors":
                continue

            if key in display_settings:
                normalized[key] = display_settings[key]

        color_settings = display_settings.get(
            "colors"
        )

        if color_settings is not None:
            if not isinstance(color_settings, dict):
                raise TypeError(
                    "Die Farbeinstellungen müssen als Dictionary vorliegen."
                )

            normalized["colors"].update(
                {
                    key: value
                    for key, value in color_settings.items()
                    if key in normalized["colors"]
                }
            )

            # Die frühere orange Standard-Auswahl war auf hellen
            # Neuronen kaum zu erkennen. Bereits gespeicherte Projekte,
            # die noch genau diesen alten Standard verwenden, erhalten
            # automatisch die neue kräftig rote Auswahlmarkierung.
            if (
                str(normalized["colors"]["selection"]).lower()
                == "#eba52d"
            ):
                normalized["colors"]["selection"] = "#d00000"

        return normalized

    @classmethod
    def normalize_training_settings(
        cls,
        training_settings
    ):
        """
        Ergänzt fehlende Trainingsparameter mit
        Standardwerten und liefert ein unabhängiges Dictionary.
        """

        normalized = cls.default_training_settings()

        if training_settings is None:
            return normalized

        if not isinstance(
            training_settings,
            dict
        ):
            raise TypeError(
                "Die Trainingseinstellungen müssen als Dictionary vorliegen."
            )

        for key in normalized:
            if key in training_settings:
                normalized[key] = training_settings[key]

        return normalized

    @staticmethod
    def create_training_data_reference(
        project_file_path,
        training_data_file_path
    ):
        """
        Erzeugt den in der Projektdatei gespeicherten
        Verweis auf die Trainingsdatendatei.

        Liegen beide Dateien auf demselben Laufwerk,
        wird ein relativer Pfad gespeichert. Andernfalls
        bleibt der absolute Pfad erhalten.
        """

        if not training_data_file_path:
            return None

        project_path = os.path.abspath(
            str(project_file_path)
        )

        training_path = os.path.abspath(
            str(training_data_file_path)
        )

        project_directory = os.path.dirname(
            project_path
        )

        project_drive = os.path.splitdrive(
            project_path
        )[0].lower()

        training_drive = os.path.splitdrive(
            training_path
        )[0].lower()

        if project_drive == training_drive:
            try:
                return os.path.normpath(
                    os.path.relpath(
                        training_path,
                        project_directory
                    )
                )
            except ValueError:
                pass

        return os.path.normpath(
            training_path
        )

    @staticmethod
    def resolve_training_data_path(
        project_file_path,
        training_data_reference
    ):
        """
        Wandelt einen in der Projektdatei gespeicherten
        Trainingsdatenpfad in einen absoluten Pfad um.
        """

        if not training_data_reference:
            return None

        reference = os.path.normpath(
            str(training_data_reference)
        )

        if os.path.isabs(
            reference
        ):
            return reference

        project_directory = os.path.dirname(
            os.path.abspath(
                str(project_file_path)
            )
        )

        return os.path.normpath(
            os.path.join(
                project_directory,
                reference
            )
        )

    @classmethod
    def load_project(cls, file_path):
        """
        Liest eine Projektdatei ein und gibt
        die geprüften Projektdaten zurück.
        """

        path = Path(file_path)

        with path.open(
            mode="r",
            encoding="utf-8"
        ) as project_file:
            project_data = json.load(
                project_file
            )

        cls._prepare_project_data(
            project_data
        )

        project_data["_parameter_repairs"] = (
            cls._repair_nonfinite_parameters(
                project_data
            )
        )

        cls._validate_project_data(
            project_data
        )

        return project_data

    @staticmethod
    def _repair_nonfinite_parameters(project_data):
        """
        Macht ein durch numerisch entgleistes Training beschädigtes
        Projekt wieder ladbar. Andere ungültige Projektdaten bleiben
        weiterhin ein Ladefehler.
        """

        repairs = []

        if not isinstance(project_data, dict):
            return repairs

        neurons = project_data.get("neurons")

        if isinstance(neurons, list):
            for neuron_data in neurons:
                if not isinstance(neuron_data, dict):
                    continue

                neuron_id = neuron_data.get("id", "?")

                for key, label in (
                    ("bias", "Bias"),
                    ("input_value", "Eingabewert"),
                    ("target_value", "Sollwert")
                ):
                    value = neuron_data.get(key)

                    if (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and not math.isfinite(value)
                    ):
                        neuron_data[key] = 0.0
                        repairs.append(
                            f"Neuron {neuron_id}: {label} wurde auf 0 gesetzt."
                        )

        connections = project_data.get("connections")

        if isinstance(connections, list):
            for connection_data in connections:
                if not isinstance(connection_data, dict):
                    continue

                value = connection_data.get("weight")

                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and not math.isfinite(value)
                ):
                    connection_id = connection_data.get("id", "?")
                    connection_data["weight"] = 0.0
                    repairs.append(
                        f"Verbindung {connection_id}: Gewicht wurde auf 0 gesetzt."
                    )

        return repairs

    @classmethod
    def _prepare_project_data(
        cls,
        project_data
    ):
        """
        Ergänzt fehlende Felder älterer Projektdateien,
        damit diese weiterhin geladen werden können.
        """

        if not isinstance(
            project_data,
            dict
        ):
            return

        version = project_data.get(
            "version"
        )

        project_data.setdefault(
            "training_data",
            None
        )

        project_data.setdefault(
            "test_data",
            None
        )
        project_data["training_settings"] = (
            cls.normalize_training_settings(
                project_data.get(
                    "training_settings"
                )
            )
        )

        project_data["display_settings"] = (
            cls.normalize_display_settings(
                project_data.get(
                    "display_settings"
                )
            )
        )

        project_data.setdefault(
            "training_history",
            []
        )
        project_data.setdefault("active_training_run_id", None)
        project_data.setdefault("momentum_state", None)
        active_training_run_id = project_data.get("active_training_run_id")
        if (
            isinstance(active_training_run_id, bool)
            or not isinstance(active_training_run_id, int)
            or active_training_run_id < 1
        ):
            project_data["active_training_run_id"] = None

        training_history = project_data.get(
            "training_history"
        )

        if isinstance(training_history, list):
            for history_entry in training_history:
                if isinstance(history_entry, dict):
                    history_entry.setdefault(
                        "network_state",
                        None
                    )
                    history_entry.setdefault(
                        "initial_network_state",
                        None
                    )
                    history_entry.setdefault(
                        "fast_mode",
                        None
                    )
                    history_entry.setdefault("momentum", 0.0)
                    history_entry.setdefault("shuffle_seed", None)
                    network_state = history_entry.get("network_state")
                    if isinstance(network_state, dict):
                        network_state.setdefault("momentum_state", None)

        project_data.setdefault(
            "project_description",
            ""
        )

        raw_difficulty = project_data.get("example_difficulty")
        valid_difficulty = (
            isinstance(raw_difficulty, int)
            and not isinstance(raw_difficulty, bool)
            and 1 <= raw_difficulty <= 4
        )
        project_data["is_example_project"] = bool(
            project_data.get("is_example_project") is True
            and valid_difficulty
        )
        project_data["example_difficulty"] = (
            int(raw_difficulty) if valid_difficulty else None
        )

        project_data.setdefault("analysis_tolerances", [])

        project_data.setdefault(
            "comments",
            []
        )

        project_data.setdefault(
            "connections",
            []
        )

        project_data.setdefault(
            "view",
            {
                "zoom": 1.0
            }
        )

        for data_key, data_label in (
            ("training_data", "Trainingsdaten"),
            ("test_data", "Testdaten")
        ):
            data_info = project_data.get(
                data_key
            )

            if data_info is None:
                continue

            if not isinstance(
                data_info,
                dict
            ):
                raise ValueError(
                    "Die Projektdatei enthält einen ungültigen "
                    f"Verweis auf {data_label}."
                )

            data_file = data_info.get(
                "file"
            )

            if (
                not isinstance(
                    data_file,
                    str
                )
                or not data_file.strip()
            ):
                raise ValueError(
                    "Die Projektdatei enthält keinen gültigen "
                    f"Pfad zur Datei für {data_label}."
                )

        view_data = project_data.get(
            "view"
        )

        if isinstance(
            view_data,
            dict
        ):
            view_data.setdefault(
                "zoom",
                1.0
            )

            view_data.setdefault(
                "center_x",
                0.0
            )

            view_data.setdefault(
                "center_y",
                0.0
            )

        comments = project_data.get(
            "comments"
        )

        if isinstance(
            comments,
            list
        ):
            for comment_data in comments:
                if not isinstance(
                    comment_data,
                    dict
                ):
                    continue

                comment_data.setdefault(
                    "font_size",
                    12
                )

        neurons = project_data.get(
            "neurons"
        )

        if isinstance(
            neurons,
            list
        ):
            for neuron_data in neurons:
                if not isinstance(
                    neuron_data,
                    dict
                ):
                    continue

                neuron_data.setdefault(
                    "type",
                    NeuronType.HIDDEN.value
                )

                neuron_data.setdefault(
                    "input_value",
                    0.0
                )

                neuron_data.setdefault(
                    "target_value",
                    0.0
                )

        if version in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
            project_data["version"] = (
                cls.PROJECT_VERSION
            )

    @classmethod
    def _validate_project_data(
        cls,
        project_data
    ):
        """
        Prüft die grundlegende Struktur
        einer geladenen Projektdatei.
        """

        if not isinstance(
            project_data,
            dict
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültigen Projektdaten."
            )

        version = project_data.get(
            "version"
        )

        if version != cls.PROJECT_VERSION:
            raise ValueError(
                f"Die Projektversion {version} wird nicht unterstützt."
            )

        if not isinstance(
            project_data.get("project_description"),
            str
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültige Projektbeschreibung."
            )

        if not isinstance(project_data.get("is_example_project"), bool):
            raise ValueError(
                "Die Kennzeichnung als Beispielprojekt ist ungültig."
            )
        difficulty = project_data.get("example_difficulty")
        if difficulty is not None and (
            isinstance(difficulty, bool)
            or not isinstance(difficulty, int)
            or not 1 <= difficulty <= 4
        ):
            raise ValueError(
                "Der Schwierigkeitsgrad des Beispielprojekts ist ungültig."
            )

        view_data = project_data.get(
            "view"
        )

        if not isinstance(
            view_data,
            dict
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültigen Ansichtsdaten."
            )

        required_view_fields = {
            "zoom",
            "center_x",
            "center_y"
        }

        missing_view_fields = (
            required_view_fields
            - view_data.keys()
        )

        if missing_view_fields:
            fields = ", ".join(
                sorted(
                    missing_view_fields
                )
            )

            raise ValueError(
                f"In den Ansichtsdaten fehlen folgende Felder: {fields}"
            )

        cls._validate_number(
            view_data["zoom"],
            "Die Projektdatei enthält einen ungültigen Zoomfaktor."
        )

        cls._validate_number(
            view_data["center_x"],
            "Die Projektdatei enthält einen ungültigen Mittelpunkt X."
        )

        cls._validate_number(
            view_data["center_y"],
            "Die Projektdatei enthält einen ungültigen Mittelpunkt Y."
        )

        if view_data["zoom"] <= 0.0:
            raise ValueError(
                "Der Zoomfaktor muss größer als null sein."
            )

        cls._validate_training_settings_data(
            project_data.get(
                "training_settings"
            )
        )

        cls._validate_display_settings_data(
            project_data.get(
                "display_settings"
            )
        )

        cls._validate_training_history_data(
            project_data.get(
                "training_history"
            )
        )

        neurons = project_data.get(
            "neurons"
        )

        if not isinstance(
            neurons,
            list
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültige Neuronenliste."
            )

        comments = project_data.get(
            "comments",
            []
        )

        if not isinstance(
            comments,
            list
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültige Kommentarliste."
            )

        connections = project_data.get(
            "connections",
            []
        )

        if not isinstance(
            connections,
            list
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültige Verbindungsliste."
            )

        used_neuron_ids = set()

        for neuron_data in neurons:
            cls._validate_neuron_data(
                neuron_data,
                used_neuron_ids
            )

        used_comment_ids = set()

        for comment_data in comments:
            cls._validate_comment_data(
                comment_data,
                used_comment_ids
            )

        used_connection_ids = set()

        for connection_data in connections:
            cls._validate_connection_data(
                connection_data,
                used_connection_ids,
                used_neuron_ids
            )

    @staticmethod
    def _validate_neuron_data(
        neuron_data,
        used_neuron_ids
    ):
        """
        Prüft die gespeicherten Daten eines Neurons.
        """

        if not isinstance(
            neuron_data,
            dict
        ):
            raise ValueError(
                "Die Projektdatei enthält ungültige Neuronendaten."
            )

        required_fields = {
            "id",
            "name",
            "type",
            "bias",
            "activation",
            "input_value",
            "target_value",
            "x",
            "y"
        }

        missing_fields = (
            required_fields
            - neuron_data.keys()
        )

        if missing_fields:
            fields = ", ".join(
                sorted(
                    missing_fields
                )
            )

            raise ValueError(
                f"Beim Neuron fehlen folgende Felder: {fields}"
            )

        neuron_id = neuron_data["id"]

        if (
            not isinstance(
                neuron_id,
                int
            )
            or isinstance(
                neuron_id,
                bool
            )
            or neuron_id < 1
        ):
            raise ValueError(
                "Ein Neuron enthält eine ungültige ID."
            )

        if neuron_id in used_neuron_ids:
            raise ValueError(
                f"Die Neuronen-ID {neuron_id} ist mehrfach vorhanden."
            )

        used_neuron_ids.add(
            neuron_id
        )

        if not isinstance(
            neuron_data["name"],
            str
        ):
            raise ValueError(
                f"Neuron {neuron_id} enthält einen ungültigen Namen."
            )

        valid_neuron_types = {
            neuron_type.value
            for neuron_type in NeuronType
        }

        if (
            neuron_data["type"]
            not in valid_neuron_types
        ):
            raise ValueError(
                f"Neuron {neuron_id} enthält einen "
                "unbekannten Neuronentyp."
            )

        ProjectIO._validate_number(
            neuron_data["bias"],
            f"Neuron {neuron_id} enthält einen ungültigen Bias."
        )

        valid_activations = {
            "Linear",
            "ReLU",
            "Sigmoid",
            "Tanh"
        }

        if (
            neuron_data["activation"]
            not in valid_activations
        ):
            raise ValueError(
                f"Neuron {neuron_id} enthält eine "
                "unbekannte Aktivierungsfunktion."
            )

        ProjectIO._validate_number(
            neuron_data["input_value"],
            f"Neuron {neuron_id} enthält einen "
            "ungültigen Eingabewert."
        )

        ProjectIO._validate_number(
            neuron_data["target_value"],
            f"Neuron {neuron_id} enthält einen "
            "ungültigen Sollwert."
        )

        ProjectIO._validate_number(
            neuron_data["x"],
            f"Neuron {neuron_id} enthält eine ungültige X-Position."
        )

        ProjectIO._validate_number(
            neuron_data["y"],
            f"Neuron {neuron_id} enthält eine ungültige Y-Position."
        )

    @staticmethod
    def _validate_comment_data(
        comment_data,
        used_comment_ids
    ):
        """
        Prüft die gespeicherten Daten
        eines Kommentarfeldes.
        """

        if not isinstance(comment_data, dict):
            raise ValueError(
                "Die Projektdatei enthält ungültige Kommentardaten."
            )

        required_fields = {
            "id", "text", "x", "y", "width", "height"
        }
        missing_fields = required_fields - comment_data.keys()
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise ValueError(
                f"Beim Kommentar fehlen folgende Felder: {fields}"
            )

        comment_id = comment_data["id"]
        if (
            not isinstance(comment_id, int)
            or isinstance(comment_id, bool)
            or comment_id < 1
        ):
            raise ValueError(
                "Ein Kommentar enthält eine ungültige ID."
            )

        if comment_id in used_comment_ids:
            raise ValueError(
                f"Die Kommentar-ID {comment_id} ist mehrfach vorhanden."
            )
        used_comment_ids.add(comment_id)

        if not isinstance(comment_data["text"], str):
            raise ValueError(
                f"Kommentar {comment_id} enthält einen ungültigen Text."
            )

        for field_name, description in (
            ("x", "X-Position"),
            ("y", "Y-Position"),
            ("width", "Breite"),
            ("height", "Höhe")
        ):
            ProjectIO._validate_number(
                comment_data[field_name],
                f"Kommentar {comment_id} enthält eine ungültige {description}."
            )

        if comment_data["width"] <= 0.0:
            raise ValueError(
                f"Kommentar {comment_id} enthält eine ungültige Breite."
            )
        if comment_data["height"] <= 0.0:
            raise ValueError(
                f"Kommentar {comment_id} enthält eine ungültige Höhe."
            )

        font_size = comment_data["font_size"]

        if (
            not isinstance(
                font_size,
                int
            )
            or isinstance(
                font_size,
                bool
            )
            or font_size < 8
            or font_size > 48
        ):
            raise ValueError(
                f"Kommentar {comment_id} enthält eine ungültige Schriftgröße."
            )

    @staticmethod
    def _validate_connection_data(
        connection_data,
        used_connection_ids,
        existing_neuron_ids
    ):
        """
        Prüft die gespeicherten Daten einer Verbindung.
        """

        if not isinstance(
            connection_data,
            dict
        ):
            raise ValueError(
                "Die Projektdatei enthält ungültige Verbindungsdaten."
            )

        required_fields = {
            "id",
            "source",
            "target",
            "weight"
        }

        missing_fields = (
            required_fields
            - connection_data.keys()
        )

        if missing_fields:
            fields = ", ".join(
                sorted(
                    missing_fields
                )
            )

            raise ValueError(
                f"Bei einer Verbindung fehlen folgende Felder: {fields}"
            )

        connection_id = connection_data["id"]

        if (
            not isinstance(
                connection_id,
                int
            )
            or isinstance(
                connection_id,
                bool
            )
            or connection_id < 1
        ):
            raise ValueError(
                "Eine Verbindung enthält eine ungültige ID."
            )

        if connection_id in used_connection_ids:
            raise ValueError(
                f"Die Verbindungs-ID {connection_id} "
                "ist mehrfach vorhanden."
            )

        used_connection_ids.add(
            connection_id
        )

        source_id = connection_data["source"]
        target_id = connection_data["target"]

        if (
            not isinstance(
                source_id,
                int
            )
            or isinstance(
                source_id,
                bool
            )
        ):
            raise ValueError(
                f"Verbindung {connection_id} enthält "
                "eine ungültige Start-ID."
            )

        if (
            not isinstance(
                target_id,
                int
            )
            or isinstance(
                target_id,
                bool
            )
        ):
            raise ValueError(
                f"Verbindung {connection_id} enthält "
                "eine ungültige Ziel-ID."
            )

        if source_id not in existing_neuron_ids:
            raise ValueError(
                f"Verbindung {connection_id} verweist auf "
                f"das nicht vorhandene Startneuron {source_id}."
            )

        if target_id not in existing_neuron_ids:
            raise ValueError(
                f"Verbindung {connection_id} verweist auf "
                f"das nicht vorhandene Zielneuron {target_id}."
            )

        ProjectIO._validate_number(
            connection_data["weight"],
            f"Verbindung {connection_id} enthält "
            "ein ungültiges Gewicht."
        )

    @staticmethod
    def _validate_display_settings_data(
        display_settings
    ):
        """
        Prüft die gespeicherten Darstellungsoptionen.
        """

        if not isinstance(
            display_settings,
            dict
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültigen "
                "Darstellungseinstellungen."
            )

        required_fields = {
            "show_weights",
            "visualize_weights",
            "show_neuron_values",
            "show_activation_charts",
            "show_io_value_fields",
            "show_ports",
            "show_neuron_names",
            "show_comments",
            "colors"
        }

        missing_fields = (
            required_fields
            - display_settings.keys()
        )

        if missing_fields:
            fields = ", ".join(
                sorted(
                    missing_fields
                )
            )

            raise ValueError(
                "In den Darstellungseinstellungen fehlen "
                f"folgende Felder: {fields}"
            )

        for field_name in required_fields - {"colors"}:
            if not isinstance(
                display_settings[field_name],
                bool
            ):
                raise ValueError(
                    "Eine Darstellungseinstellung ist ungültig: "
                    f"{field_name}."
                )

        color_settings = display_settings["colors"]

        if not isinstance(color_settings, dict):
            raise ValueError(
                "Die gespeicherten Farbeinstellungen sind ungültig."
            )

        required_colors = set(
            ProjectIO.default_color_settings()
        )
        missing_colors = required_colors - color_settings.keys()

        if missing_colors:
            raise ValueError(
                "In den Farbeinstellungen fehlen Werte: "
                + ", ".join(sorted(missing_colors))
            )

        for color_name in required_colors:
            color_value = color_settings[color_name]

            if (
                not isinstance(color_value, str)
                or re.fullmatch(r"#[0-9a-fA-F]{6}", color_value) is None
            ):
                raise ValueError(
                    f"Die Farbe '{color_name}' ist ungültig."
                )

    @staticmethod
    def _validate_training_settings_data(
        training_settings
    ):
        """
        Prüft die gespeicherten Trainingsparameter.
        """

        if not isinstance(
            training_settings,
            dict
        ):
            raise ValueError(
                "Die Projektdatei enthält keine gültigen "
                "Trainingseinstellungen."
            )

        required_fields = {
            "initialize_network",
            "weight_initialization",
            "bias_initialization",
            "learning_rate",
            "momentum",
            "error_limit",
            "maximum_epochs",
            "training_section_epochs",
            "monitor_training_data",
            "show_error_chart",
            "error_chart_scale"
        }

        missing_fields = (
            required_fields
            - training_settings.keys()
        )

        if missing_fields:
            fields = ", ".join(
                sorted(
                    missing_fields
                )
            )

            raise ValueError(
                "In den Trainingseinstellungen fehlen "
                f"folgende Felder: {fields}"
            )

        if not isinstance(
            training_settings["initialize_network"],
            bool
        ):
            raise ValueError(
                "Die Einstellung zur Neuinitialisierung "
                "des Netzwerkes ist ungültig."
            )

        if training_settings["weight_initialization"] not in {
            "xavier",
            "zero"
        }:
            raise ValueError(
                "Die Einstellung zur Initialisierung "
                "der Gewichte ist ungültig."
            )

        if training_settings["bias_initialization"] not in {
            "zero",
            "xavier"
        }:
            raise ValueError(
                "Die Einstellung zur Initialisierung "
                "des Bias ist ungültig."
            )

        ProjectIO._validate_number(
            training_settings["learning_rate"],
            "Die gespeicherte Lernrate ist ungültig."
        )

        if not (
            0.000001
            <= training_settings["learning_rate"]
            <= 1000.0
        ):
            raise ValueError(
                "Die gespeicherte Lernrate liegt außerhalb "
                "des zulässigen Bereiches."
            )

        ProjectIO._validate_number(
            training_settings.get("momentum", 0.0),
            "Das gespeicherte Momentum ist ungültig."
        )
        if not 0.0 <= training_settings.get("momentum", 0.0) <= 0.99:
            raise ValueError(
                "Das gespeicherte Momentum liegt außerhalb des "
                "zulässigen Bereiches."
            )

        ProjectIO._validate_number(
            training_settings["error_limit"],
            "Die gespeicherte Fehlergrenze ist ungültig."
        )

        if not (
            0.0000000001
            <= training_settings["error_limit"]
            <= 1000000.0
        ):
            raise ValueError(
                "Die gespeicherte Fehlergrenze liegt außerhalb "
                "des zulässigen Bereiches."
            )

        if not isinstance(
            training_settings.get("fast_mode", False),
            bool
        ):
            raise ValueError(
                "Die Einstellung zum Schnellmodus ist ungültig."
            )

        if not isinstance(
            training_settings[
                "monitor_training_data"
            ],
            bool
        ):
            raise ValueError(
                "Die Einstellung zum Monitoring der "
                "Trainingsdaten ist ungültig."
            )

        if not isinstance(
            training_settings[
                "show_error_chart"
            ],
            bool
        ):
            raise ValueError(
                "Die Einstellung zur Anzeige der "
                "Fehlerkurve ist ungültig."
            )

        if training_settings["error_chart_scale"] not in {
            "linear",
            "logarithmic"
        }:
            raise ValueError(
                "Die Einstellung zur Skalierung der "
                "Fehlerkurve ist ungültig."
            )

        maximum_epochs = training_settings[
            "maximum_epochs"
        ]

        if (
            not isinstance(
                maximum_epochs,
                int
            )
            or isinstance(
                maximum_epochs,
                bool
            )
            or maximum_epochs < 1
            or maximum_epochs > 1000000
        ):
            raise ValueError(
                "Die gespeicherte maximale Epochenzahl ist ungültig."
            )

        section_epochs = training_settings["training_section_epochs"]
        if (
            not isinstance(section_epochs, int)
            or isinstance(section_epochs, bool)
            or section_epochs < 1
            or section_epochs > 1000000
        ):
            raise ValueError(
                "Die gespeicherte Epochenzahl für Trainingsabschnitte ist ungültig."
            )

        if training_settings.get("training_target_mode", "epochs") not in {
            "one", "epochs", "limit"
        }:
            raise ValueError(
                "Das gespeicherte Trainingsziel ist ungültig."
            )

    @staticmethod
    def _validate_training_history_data(training_history):
        """Prüft die kompakt gespeicherte Historie der Trainingsläufe."""

        if not isinstance(training_history, list):
            raise ValueError(
                "Die Projektdatei enthält keine gültige Trainingshistorie."
            )

        used_run_ids = set()
        required_fields = {
            "run_id",
            "timestamp",
            "training_data",
            "initialized",
            "weight_initialization",
            "bias_initialization",
            "learning_rate",
            "momentum",
            "error_limit",
            "requested_epochs",
            "completed_epochs",
            "start_error",
            "end_error",
            "maximum_absolute_error",
            "elapsed_seconds",
            "status_text",
            "stop_at_error_limit",
            "training_stopped",
            "curve_points",
            "network_state"
        }

        for entry in training_history:
            if not isinstance(entry, dict):
                raise ValueError(
                    "Die Trainingshistorie enthält einen ungültigen Eintrag."
                )

            missing_fields = required_fields - entry.keys()

            if missing_fields:
                raise ValueError(
                    "In einem Eintrag der Trainingshistorie fehlen Felder: "
                    + ", ".join(sorted(missing_fields))
                )

            run_id = entry["run_id"]

            if (
                not isinstance(run_id, int)
                or isinstance(run_id, bool)
                or run_id < 1
                or run_id in used_run_ids
            ):
                raise ValueError(
                    "Die Trainingshistorie enthält eine ungültige Laufnummer."
                )

            used_run_ids.add(run_id)

            for text_key in (
                "timestamp",
                "training_data",
                "status_text"
            ):
                if not isinstance(entry[text_key], str):
                    raise ValueError(
                        "Die Trainingshistorie enthält einen ungültigen Textwert."
                    )

            for bool_key in (
                "initialized",
                "stop_at_error_limit",
                "training_stopped"
            ):
                if not isinstance(entry[bool_key], bool):
                    raise ValueError(
                        "Die Trainingshistorie enthält einen ungültigen Schalter."
                    )

            if entry.get("continuable", True) not in (True, False):
                raise ValueError(
                    "Die Trainingshistorie enthält einen ungültigen Fortsetzungsstatus."
                )

            if entry.get("fast_mode") not in (True, False, None):
                raise ValueError(
                    "Die Trainingshistorie enthält einen ungültigen "
                    "Trainingsmodus."
                )

            shuffle_seed = entry.get("shuffle_seed")
            if (
                shuffle_seed is not None
                and (
                    not isinstance(shuffle_seed, int)
                    or isinstance(shuffle_seed, bool)
                    or shuffle_seed < 0
                    or shuffle_seed >= 1 << 63
                )
            ):
                raise ValueError(
                    "Die Trainingshistorie enthält eine ungültige "
                    "Misch-Startkennung."
                )

            if entry["weight_initialization"] not in {"xavier", "zero"}:
                raise ValueError(
                    "Die Trainingshistorie enthält eine ungültige "
                    "Gewichtsinitialisierung."
                )

            if entry["bias_initialization"] not in {"xavier", "zero"}:
                raise ValueError(
                    "Die Trainingshistorie enthält eine ungültige "
                    "Bias-Initialisierung."
                )

            for number_key in (
                "learning_rate",
                "momentum",
                "error_limit",
                "start_error",
                "end_error",
                "maximum_absolute_error",
                "elapsed_seconds"
            ):
                ProjectIO._validate_number(
                    entry[number_key],
                    "Die Trainingshistorie enthält einen ungültigen Zahlenwert."
                )

            if (
                entry["learning_rate"] <= 0.0
                or not 0.0 <= entry.get("momentum", 0.0) <= 0.99
                or entry["error_limit"] <= 0.0
                or entry["start_error"] < 0.0
                or entry["end_error"] < 0.0
                or entry["maximum_absolute_error"] < 0.0
                or entry["elapsed_seconds"] < 0.0
            ):
                raise ValueError(
                    "Die Trainingshistorie enthält einen Zahlenwert "
                    "außerhalb des zulässigen Bereiches."
                )

            for integer_key in (
                "requested_epochs",
                "completed_epochs"
            ):
                value = entry[integer_key]

                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 1
                    or value > 2147483647
                ):
                    raise ValueError(
                        "Die Trainingshistorie enthält eine ungültige "
                        "Epochenzahl."
                    )

            curve_points = entry["curve_points"]

            if not isinstance(curve_points, list) or len(curve_points) > 10000:
                raise ValueError(
                    "Die Trainingshistorie enthält eine ungültige Fehlerkurve."
                )

            previous_epoch = 0

            for point in curve_points:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError(
                        "Die Trainingshistorie enthält einen ungültigen Kurvenpunkt."
                    )

                epoch, error_value = point

                if (
                    not isinstance(epoch, int)
                    or isinstance(epoch, bool)
                    or epoch <= previous_epoch
                ):
                    raise ValueError(
                        "Die Fehlerkurve der Trainingshistorie enthält eine "
                        "ungültige Epoche."
                    )

                ProjectIO._validate_number(
                    error_value,
                    "Die Fehlerkurve der Trainingshistorie enthält einen "
                    "ungültigen Fehlerwert."
                )

                if error_value < 0.0:
                    raise ValueError(
                        "Ein Fehlerwert der Trainingshistorie ist negativ."
                    )

                previous_epoch = epoch

            ProjectIO._validate_training_network_state(
                entry["network_state"]
            )
            ProjectIO._validate_training_network_state(
                entry.get("initial_network_state")
            )

    @staticmethod
    def _validate_training_network_state(network_state):
        """Prüft einen optionalen Endzustand eines Trainingslaufes."""

        if network_state is None:
            return

        if not isinstance(network_state, dict):
            raise ValueError(
                "Die Trainingshistorie enthält einen ungültigen "
                "Netzwerkzustand."
            )

        if not {"neurons", "connections"}.issubset(network_state.keys()) or (
            set(network_state.keys()) - {"neurons", "connections", "momentum_state"}
        ):
            raise ValueError(
                "Der gespeicherte Netzwerkzustand ist unvollständig."
            )

        neurons = network_state["neurons"]
        connections = network_state["connections"]
        momentum_state = network_state.get("momentum_state")
        if momentum_state is not None:
            if not isinstance(momentum_state, dict):
                raise ValueError(
                    "Der gespeicherte Momentumzustand ist ungültig."
                )
            for state_key in ("connections", "biases"):
                values = momentum_state.get(state_key, {})
                if not isinstance(values, dict):
                    raise ValueError(
                        "Der gespeicherte Momentumzustand ist ungültig."
                    )
                for identifier, value in values.items():
                    try:
                        if int(identifier) < 1:
                            raise ValueError
                    except (TypeError, ValueError):
                        raise ValueError(
                            "Der gespeicherte Momentumzustand enthält eine "
                            "ungültige ID."
                        )
                    ProjectIO._validate_number(
                        value,
                        "Der gespeicherte Momentumzustand enthält einen "
                        "ungültigen Zahlenwert."
                    )

        if not isinstance(neurons, list) or len(neurons) > 500:
            raise ValueError(
                "Der gespeicherte Netzwerkzustand enthält eine ungültige "
                "Neuronenliste."
            )

        if not isinstance(connections, list) or len(connections) > 50000:
            raise ValueError(
                "Der gespeicherte Netzwerkzustand enthält eine ungültige "
                "Verbindungsliste."
            )

        neuron_ids = set()

        for neuron_state in neurons:
            if (
                not isinstance(neuron_state, dict)
                or set(neuron_state.keys()) != {"id", "bias"}
            ):
                raise ValueError(
                    "Der gespeicherte Netzwerkzustand enthält ein "
                    "ungültiges Neuron."
                )

            neuron_id = neuron_state["id"]

            if (
                not isinstance(neuron_id, int)
                or isinstance(neuron_id, bool)
                or neuron_id < 1
                or neuron_id in neuron_ids
            ):
                raise ValueError(
                    "Der gespeicherte Netzwerkzustand enthält eine "
                    "ungültige Neuronen-ID."
                )

            ProjectIO._validate_number(
                neuron_state["bias"],
                "Der gespeicherte Netzwerkzustand enthält einen "
                "ungültigen Bias."
            )
            neuron_ids.add(neuron_id)

        connection_ids = set()

        for connection_state in connections:
            if (
                not isinstance(connection_state, dict)
                or set(connection_state.keys())
                != {"id", "source", "target", "weight"}
            ):
                raise ValueError(
                    "Der gespeicherte Netzwerkzustand enthält eine "
                    "ungültige Verbindung."
                )

            connection_id = connection_state["id"]
            source_id = connection_state["source"]
            target_id = connection_state["target"]

            if (
                not isinstance(connection_id, int)
                or isinstance(connection_id, bool)
                or connection_id < 1
                or connection_id in connection_ids
                or not isinstance(source_id, int)
                or isinstance(source_id, bool)
                or not isinstance(target_id, int)
                or isinstance(target_id, bool)
                or source_id not in neuron_ids
                or target_id not in neuron_ids
                or source_id == target_id
            ):
                raise ValueError(
                    "Der gespeicherte Netzwerkzustand enthält ungültige "
                    "Verbindungsdaten."
                )

            ProjectIO._validate_number(
                connection_state["weight"],
                "Der gespeicherte Netzwerkzustand enthält ein "
                "ungültiges Gewicht."
            )
            connection_ids.add(connection_id)

    @staticmethod
    def _validate_number(
        value,
        error_message
    ):
        """
        Prüft einen numerischen Wert.
        """

        if (
            not isinstance(
                value,
                (int, float)
            )
            or isinstance(
                value,
                bool
            )
            or not math.isfinite(
                value
            )
        ):
            raise ValueError(
                error_message
            )
