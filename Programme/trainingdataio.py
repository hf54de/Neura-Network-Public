# -------------------------------------------------------------------------------------------------
# Datei: trainingdataio.py
# Zweck: Liest, schreibt und validiert Trainings- und Testdatendateien.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import json
import math
from pathlib import Path


class TrainingDataIO:
    """
    Speichert und lädt unabhängige Trainingsdatendateien.

    Jede Datenspalte besitzt eigene Eigenschaften:
        - Name
        - optionale Einheit
        - Rolle (Input oder Output)
        - optionale Zuordnung zu einem Netzwerkneuron

    Die Zuordnung ist optional. Dadurch bleibt eine Trainingsdatei
    auch ohne geöffnetes oder passendes Netzwerk bearbeitbar.
    """

    FILE_VERSION = 5

    DATA_TYPES = (
        "analog",
        "binary"
    )

    CALIBRATION_MODES = (
        "none",
        "minmax_0_1",
        "minmax_minus1_1",
        "standard"
    )

    @staticmethod
    def translated(translator, key, default, **values):
        """Liefert optional einen Oberflächentext, sonst den Bestandstext."""

        if callable(translator):
            return translator(key, **values)

        try:
            return default.format(**values)
        except (KeyError, ValueError, IndexError):
            return default

    @staticmethod
    def default_calibration():
        return {
            "mode": "none",
            "source_min": 0.0,
            "source_max": 1.0,
            "mean": 0.0,
            "stddev": 1.0
        }

    @classmethod
    def normalize_calibration(cls, calibration):
        normalized = cls.default_calibration()

        if not isinstance(calibration, dict):
            return normalized

        mode = calibration.get("mode")

        if mode in cls.CALIBRATION_MODES:
            normalized["mode"] = mode

        for key in (
            "source_min",
            "source_max",
            "mean",
            "stddev"
        ):
            value = calibration.get(key)

            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            ):
                normalized[key] = float(value)

        return normalized

    @classmethod
    def calibrations_equal(cls, first, second):
        """Vergleicht zwei Kalibrierungen tolerant auf Zahlenwerte."""

        first = cls.normalize_calibration(first)
        second = cls.normalize_calibration(second)

        if first["mode"] != second["mode"]:
            return False

        return all(
            math.isclose(
                first[key],
                second[key],
                rel_tol=1e-12,
                abs_tol=1e-12
            )
            for key in (
                "source_min",
                "source_max",
                "mean",
                "stddev"
            )
        )

    @classmethod
    def scale_value(cls, value, calibration, translator=None):
        """Rechnet einen Rohwert in den internen Netzwert um."""

        value = float(value)

        if not math.isfinite(value):
            raise ValueError(
                cls.translated(
                    translator,
                    "training.scaling.invalid_raw_value",
                    "Der zu skalierende Rohwert ist keine endliche Zahl."
                )
            )

        calibration = cls.normalize_calibration(calibration)
        mode = calibration["mode"]

        if mode == "none":
            result = value
        elif mode in ("minmax_0_1", "minmax_minus1_1"):
            source_min = calibration["source_min"]
            source_max = calibration["source_max"]
            difference = source_max - source_min

            if difference <= 0.0:
                raise ValueError(
                    cls.translated(
                        translator,
                        "training.scaling.invalid_range",
                        "Der Rohwertbereich der Kalibrierung ist ungültig."
                    )
                )

            result = (value - source_min) / difference

            if mode == "minmax_minus1_1":
                result = result * 2.0 - 1.0
        else:
            stddev = calibration["stddev"]

            if stddev <= 0.0:
                raise ValueError(
                    cls.translated(
                        translator,
                        "training.scaling.invalid_stddev",
                        "Die Standardabweichung der Kalibrierung ist ungültig."
                    )
                )

            result = (value - calibration["mean"]) / stddev

        if not math.isfinite(result):
            raise ValueError(
                cls.translated(
                    translator,
                    "training.scaling.invalid_network_result",
                    "Die Skalierung hat keinen endlichen Netzwert ergeben."
                )
            )

        return result

    @classmethod
    def unscale_value(cls, value, calibration, translator=None):
        """Rechnet einen internen Netzwert zurück in den Rohwert."""

        value = float(value)

        if not math.isfinite(value):
            raise ValueError(
                cls.translated(
                    translator,
                    "training.scaling.invalid_network_value",
                    "Der zurückzurechnende Netzwert ist keine endliche Zahl."
                )
            )

        calibration = cls.normalize_calibration(calibration)
        mode = calibration["mode"]

        if mode == "none":
            result = value
        elif mode in ("minmax_0_1", "minmax_minus1_1"):
            normalized_value = value

            if mode == "minmax_minus1_1":
                normalized_value = (value + 1.0) / 2.0

            result = (
                calibration["source_min"]
                + normalized_value
                * (
                    calibration["source_max"]
                    - calibration["source_min"]
                )
            )
        else:
            result = (
                value * calibration["stddev"]
                + calibration["mean"]
            )

        if not math.isfinite(result):
            raise ValueError(
                cls.translated(
                    translator,
                    "training.scaling.invalid_raw_result",
                    "Die Rückskalierung hat keinen endlichen Rohwert ergeben."
                )
            )

        return result

    @classmethod
    def create_empty_document(
        cls,
        input_count,
        output_count,
        name="Neue Trainingsdaten"
    ):
        input_count = int(input_count)
        output_count = int(output_count)

        if input_count < 1:
            raise ValueError(
                "Die Anzahl der Eingänge muss mindestens 1 betragen."
            )

        if output_count < 1:
            raise ValueError(
                "Die Anzahl der Ausgänge muss mindestens 1 betragen."
            )

        columns = []

        for index in range(input_count):
            columns.append(
                {
                    "name": f"Input {index + 1}",
                    "unit": "",
                    "role": "input",
                    "data_type": "analog",
                    "mapped_neuron_id": None,
                    "mapped_neuron_name": None,
                    "calibration": cls.default_calibration()
                }
            )

        for index in range(output_count):
            columns.append(
                {
                    "name": f"Output {index + 1}",
                    "unit": "",
                    "role": "output",
                    "data_type": "analog",
                    "mapped_neuron_id": None,
                    "mapped_neuron_name": None,
                    "calibration": cls.default_calibration()
                }
            )

        return {
            "version": cls.FILE_VERSION,
            "name": str(name),
            "columns": columns,
            "records": []
        }

    @classmethod
    def create_document_for_network(
        cls,
        input_neurons,
        output_neurons,
        name="Trainingsdaten zum Netzwerk"
    ):
        """
        Erzeugt eine leere Trainingsdatenstruktur und
        ordnet jede Spalte sofort einem Neuron zu.
        """

        input_neurons = sorted(
            list(
                input_neurons
            ),
            key=lambda neuron: neuron.id
        )

        output_neurons = sorted(
            list(
                output_neurons
            ),
            key=lambda neuron: neuron.id
        )

        document = cls.create_empty_document(
            len(
                input_neurons
            ),
            len(
                output_neurons
            ),
            name
        )

        for column, neuron in zip(
            document["columns"][
                :len(input_neurons)
            ],
            input_neurons
        ):
            column["name"] = str(
                neuron.name
            )
            column["mapped_neuron_id"] = int(
                neuron.id
            )

            column["mapped_neuron_name"] = str(
                neuron.name
            )

        output_start_index = len(
            input_neurons
        )

        for column, neuron in zip(
            document["columns"][
                output_start_index:
            ],
            output_neurons
        ):
            column["name"] = str(
                neuron.name
            )
            column["mapped_neuron_id"] = int(
                neuron.id
            )

            column["mapped_neuron_name"] = str(
                neuron.name
            )

        cls.validate(
            document
        )

        return document

    @classmethod
    def save(cls, file_path, document, translator=None):
        cls.validate(document, translator)

        path = Path(file_path)

        with path.open(
            mode="w",
            encoding="utf-8"
        ) as data_file:
            json.dump(
                document,
                data_file,
                ensure_ascii=False,
                indent=4
            )

    @classmethod
    def load(cls, file_path, translator=None):
        path = Path(file_path)

        with path.open(
            mode="r",
            encoding="utf-8"
        ) as data_file:
            document = json.load(
                data_file
            )

        document = cls.prepare_document(
            document
        )

        cls.validate(document, translator)

        return document

    @classmethod
    def prepare_document(cls, document):
        """
        Übernimmt ältere Trainingsdatendateien der Version 1
        in das aktuelle spaltenorientierte Format.
        """

        if not isinstance(document, dict):
            return document

        version = document.get(
            "version"
        )

        if version == cls.FILE_VERSION:
            return document

        if version in (2, 3, 4):
            converted = copy.deepcopy(document)
            converted["version"] = cls.FILE_VERSION

            columns = converted.get("columns")

            if isinstance(columns, list):
                for column in columns:
                    if isinstance(column, dict):
                        column["unit"] = str(
                            column.get("unit", "")
                        ).strip()
                        column["data_type"] = (
                            column.get("data_type")
                            if column.get("data_type") in cls.DATA_TYPES
                            else "analog"
                        )
                        column["calibration"] = (
                            cls.normalize_calibration(
                                column.get("calibration")
                            )
                        )

            return converted

        if version != 1:
            return document

        input_count = document.get(
            "input_count"
        )
        output_count = document.get(
            "output_count"
        )
        input_names = document.get(
            "input_names"
        )
        output_names = document.get(
            "output_names"
        )
        old_records = document.get(
            "records"
        )

        if not isinstance(input_names, list):
            input_names = [
                f"Input {index + 1}"
                for index in range(int(input_count or 0))
            ]

        if not isinstance(output_names, list):
            output_names = [
                f"Output {index + 1}"
                for index in range(int(output_count or 0))
            ]

        columns = []

        for name in input_names:
            columns.append(
                {
                    "name": str(name),
                    "unit": "",
                    "role": "input",
                    "data_type": "analog",
                    "mapped_neuron_id": None,
                    "mapped_neuron_name": None,
                    "calibration": cls.default_calibration()
                }
            )

        for name in output_names:
            columns.append(
                {
                    "name": str(name),
                    "unit": "",
                    "role": "output",
                    "data_type": "analog",
                    "mapped_neuron_id": None,
                    "mapped_neuron_name": None,
                    "calibration": cls.default_calibration()
                }
            )

        records = []

        if isinstance(old_records, list):
            for record in old_records:
                if not isinstance(record, dict):
                    continue

                inputs = record.get(
                    "inputs",
                    []
                )
                targets = record.get(
                    "targets",
                    []
                )

                records.append(
                    list(inputs) + list(targets)
                )

        return {
            "version": cls.FILE_VERSION,
            "name": str(
                document.get(
                    "name",
                    "Trainingsdaten"
                )
            ),
            "columns": columns,
            "records": records
        }

    @classmethod
    def validate(cls, document, translator=None):
        if not isinstance(document, dict):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.invalid_document",
                    "Die Datei enthält keine gültigen Trainingsdaten."
                )
            )

        if document.get("version") != cls.FILE_VERSION:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.unsupported_version",
                    "Die Version der Trainingsdatendatei wird nicht unterstützt."
                )
            )

        name = document.get(
            "name"
        )

        if not isinstance(name, str):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.invalid_name",
                    "Die Trainingsdaten enthalten keinen gültigen Namen."
                )
            )

        columns = document.get(
            "columns"
        )

        if not isinstance(columns, list) or not columns:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.invalid_columns",
                    "Die Trainingsdaten enthalten keine gültigen Spalten."
                )
            )

        input_count = 0
        output_count = 0

        for column_index, column in enumerate(
            columns,
            start=1
        ):
            cls._validate_column(
                column,
                column_index,
                translator
            )

            if column["role"] == "input":
                input_count += 1
            else:
                output_count += 1

        if input_count < 1:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.missing_input",
                    "Die Trainingsdaten müssen mindestens eine Input-Spalte enthalten."
                )
            )

        if output_count < 1:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.missing_output",
                    "Die Trainingsdaten müssen mindestens eine Output-Spalte enthalten."
                )
            )

        records = document.get(
            "records"
        )

        if not isinstance(records, list):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.invalid_records",
                    "Die Trainingsdaten enthalten keine gültige Datensatzliste."
                )
            )

        for record_index, record in enumerate(
            records,
            start=1
        ):
            cls._validate_record(
                record,
                record_index,
                columns,
                translator
            )

        cls._validate_input_array(document, columns, translator)

    @classmethod
    def _validate_input_array(cls, document, columns, translator=None):
        """Prüft die optionale 2D-Anordnung vollständig binärer Eingänge."""

        definition = document.get("input_array")
        if definition is None:
            return
        if not isinstance(definition, dict):
            raise ValueError(cls.translated(
                translator, "data.validation.array_invalid",
                "Die Definition des Eingabe-Arrays ist ungültig."
            ))
        rows = definition.get("rows")
        array_columns = definition.get("columns")
        order = definition.get("column_indices")
        if (
            not isinstance(rows, int) or isinstance(rows, bool) or rows < 1
            or not isinstance(array_columns, int)
            or isinstance(array_columns, bool) or array_columns < 1
            or not isinstance(order, list)
        ):
            raise ValueError(cls.translated(
                translator, "data.validation.array_invalid",
                "Die Definition des Eingabe-Arrays ist ungültig."
            ))
        input_indices = [
            index
            for index, column in enumerate(columns)
            if column.get("role") == "input"
        ]
        binary_input_indices = [
            index
            for index in input_indices
            if columns[index].get("data_type", "analog") == "binary"
        ]
        if (
            len(binary_input_indices) != len(input_indices)
            or rows * array_columns != len(input_indices)
            or len(order) != len(input_indices)
            or any(not isinstance(index, int) or isinstance(index, bool) for index in order)
            or set(order) != set(input_indices)
        ):
            raise ValueError(cls.translated(
                translator, "data.validation.array_mismatch",
                "Das Eingabe-Array muss jeden binären Eingang genau einmal enthalten."
            ))

    @classmethod
    def _validate_column(cls, column, column_index, translator=None):
        if not isinstance(column, dict):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_invalid",
                    "Spalte {column} ist ungültig.",
                    column=column_index
                )
            )

        name = column.get(
            "name"
        )

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_name",
                    "Spalte {column} besitzt keinen gültigen Namen.",
                    column=column_index
                )
            )

        unit = column.get(
            "unit",
            ""
        )

        if not isinstance(unit, str):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_unit",
                    "Spalte {column} enthält keine gültige Einheit.",
                    column=column_index
                )
            )

        role = column.get(
            "role"
        )

        if role not in (
            "input",
            "output"
        ):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_role",
                    "Spalte {column} besitzt keinen gültigen Typ.",
                    column=column_index
                )
            )

        data_type = column.get("data_type", "analog")
        if data_type not in cls.DATA_TYPES:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_data_type",
                    "Spalte {column} besitzt keine gültige Datenart.",
                    column=column_index
                )
            )

        if (
            data_type == "binary"
            and TrainingDataIO.normalize_calibration(
                column.get("calibration")
            )["mode"] != "none"
        ):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.binary_scaling",
                    "Binärspalte {column} darf nicht skaliert werden.",
                    column=name
                )
            )

        neuron_id = column.get(
            "mapped_neuron_id"
        )

        if (
            neuron_id is not None
            and (
                not isinstance(neuron_id, int)
                or isinstance(neuron_id, bool)
                or neuron_id < 1
            )
        ):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_neuron_id",
                    "Spalte {column} enthält eine ungültige Neuronen-ID.",
                    column=column_index
                )
            )

        neuron_name = column.get(
            "mapped_neuron_name"
        )

        if (
            neuron_name is not None
            and not isinstance(neuron_name, str)
        ):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_neuron_name",
                    "Spalte {column} enthält einen ungültigen Neuronennamen.",
                    column=column_index
                )
            )

        calibration = column.get(
            "calibration"
        )

        if not isinstance(calibration, dict):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_calibration",
                    "Spalte {column} enthält keine gültige Kalibrierung.",
                    column=column_index
                )
            )

        mode = calibration.get(
            "mode"
        )

        if mode not in TrainingDataIO.CALIBRATION_MODES:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_calibration_mode",
                    "Spalte {column} enthält ein ungültiges Skalierungsverfahren.",
                    column=column_index
                )
            )

        for key in (
            "source_min",
            "source_max",
            "mean",
            "stddev"
        ):
            value = calibration.get(key)

            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
            ):
                raise ValueError(
                    cls.translated(
                        translator,
                        "data.validation.column_calibration_values",
                        "Spalte {column} enthält ungültige Kalibrierungswerte.",
                        column=column_index
                    )
                )

        if (
            mode in ("minmax_0_1", "minmax_minus1_1")
            and calibration["source_min"] >= calibration["source_max"]
        ):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_raw_range",
                    "Spalte {column}: Das Rohwert-Maximum muss größer als das Minimum sein.",
                    column=column_index
                )
            )

        if mode == "standard" and calibration["stddev"] <= 0:
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.column_stddev",
                    "Spalte {column}: Die Standardabweichung muss größer als null sein.",
                    column=column_index
                )
            )

    @classmethod
    def _validate_record(
        cls,
        record,
        record_index,
        columns,
        translator=None
    ):
        if (
            not isinstance(record, list)
            or len(record) != len(columns)
        ):
            raise ValueError(
                cls.translated(
                    translator,
                    "data.validation.record_length",
                    "Datensatz {record} enthält nicht die erwartete Anzahl an Werten.",
                    record=record_index
                )
            )

        for column_index, (value, column) in enumerate(
            zip(record, columns), start=1
        ):
            cls._validate_number(
                value,
                cls.translated(
                    translator,
                    "data.validation.record_number",
                    "Datensatz {record} enthält einen ungültigen Zahlenwert.",
                    record=record_index
                )
            )
            if (
                column.get("data_type", "analog") == "binary"
                and float(value) not in (0.0, 1.0)
            ):
                raise ValueError(
                    cls.translated(
                        translator,
                        "data.validation.binary_value",
                        "Datensatz {record}, Spalte {column}: Binärwerte müssen 0 oder 1 sein.",
                        record=record_index,
                        column=column_index
                    )
                )

    @staticmethod
    def _validate_number(value, error_message):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(
                error_message
            )
