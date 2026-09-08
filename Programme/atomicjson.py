# -------------------------------------------------------------------------------------------------
# Datei: atomicjson.py
# Zweck: Speichert JSON-Dateien über eine temporäre Datei ohne vorzeitiges Überschreiben.
# Letzte Änderung: 05.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import json
import os
from pathlib import Path
import tempfile


def write_json_atomic(file_path, document):
    """Ersetzt die Zieldatei erst nach vollständig geschriebenem JSON-Inhalt."""

    path = Path(file_path)
    temporary_path = None
    try:
        # Derselbe Ordner ermöglicht den Austausch innerhalb eines Dateisystems.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(document, temporary_file, ensure_ascii=False, indent=4)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        # Unter Windows muss die temporäre Datei vor dem Austausch geschlossen sein.
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
