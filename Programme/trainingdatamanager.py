# -------------------------------------------------------------------------------------------------
# Datei: trainingdatamanager.py
# Zweck: Verwaltet zugeordnete Trainings- und Testdaten eines Projekts.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import copy
import os

from PySide6.QtCore import QObject, Signal

from trainingdataio import TrainingDataIO
from language import LanguageManager


class TrainingDataManager(QObject):
    """
    Verwaltet die aktuell verwendete Trainingsdatendatei.

    Zuständig für:
        - aktuelles Trainingsdatendokument
        - Dateipfad
        - Änderungsstatus
        - Erzeugen, Laden und Speichern
        - zentrale Bereitstellung für Editor und Trainer

    Nicht zuständig:
        - grafische Bearbeitung der Datensätze
        - Training des Netzwerkes
        - Zuordnungsprüfung gegen ein konkretes Netzwerk
    """

    document_changed = Signal(object)
    file_path_changed = Signal(object)
    modified_changed = Signal(bool)
    state_changed = Signal()

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        self._document = None
        self._file_path = None
        self._modified = False

    @property
    def document(self):
        """
        Liefert eine Kopie des aktuellen Dokumentes.
        """

        if self._document is None:
            return None

        return copy.deepcopy(self._document)

    @property
    def file_path(self):
        return self._file_path

    @property
    def modified(self):
        return self._modified

    @property
    def has_document(self):
        return self._document is not None

    @property
    def record_count(self):
        if self._document is None:
            return 0

        return len(
            self._document.get(
                "records",
                []
            )
        )

    @property
    def display_name(self):
        if self._file_path:
            return os.path.basename(
                self._file_path
            )

        if self._document is not None:
            return self._document.get(
                "name",
                self.t("data.new_training.name")
            )

        return self.t("data.no_training")

    def create_new(
        self,
        input_count,
        output_count,
        name=None
    ):
        if name is None:
            name = self.t("data.new_training.name")
        document = TrainingDataIO.create_empty_document(
            input_count,
            output_count,
            name
        )

        self.set_document(
            document,
            file_path=None,
            modified=True
        )

        return self.document

    def clear(self):
        self._document = None
        self._file_path = None
        self._modified = False

        self.document_changed.emit(
            None
        )
        self.file_path_changed.emit(
            None
        )
        self.modified_changed.emit(
            False
        )
        self.state_changed.emit()

    def set_document(
        self,
        document,
        file_path=None,
        modified=False
    ):
        prepared_document = TrainingDataIO.prepare_document(
            copy.deepcopy(document)
        )

        TrainingDataIO.validate(prepared_document, translator=self.t)

        self._document = prepared_document
        self._file_path = (
            str(file_path)
            if file_path
            else None
        )
        self._modified = bool(
            modified
        )

        self.document_changed.emit(
            self.document
        )
        self.file_path_changed.emit(
            self._file_path
        )
        self.modified_changed.emit(
            self._modified
        )
        self.state_changed.emit()

    def load(self, file_path):
        document = TrainingDataIO.load(
            file_path
        )

        self.set_document(
            document,
            file_path=file_path,
            modified=False
        )

        return self.document

    def save(self):
        if self._document is None:
            raise ValueError(
                self.t("data.manager.none_loaded")
            )

        if self._file_path is None:
            raise ValueError(
                self.t("data.manager.no_path")
            )

        TrainingDataIO.save(
            self._file_path,
            self._document
        )

        self.set_modified(
            False
        )

        return self._file_path

    def save_as(self, file_path):
        if self._document is None:
            raise ValueError(
                self.t("data.manager.none_loaded")
            )

        file_path = str(
            file_path
        )

        if not file_path.lower().endswith(
            ".nndata"
        ):
            file_path += ".nndata"

        TrainingDataIO.save(
            file_path,
            self._document
        )

        self._file_path = file_path
        self._modified = False

        self.file_path_changed.emit(
            self._file_path
        )
        self.modified_changed.emit(
            False
        )
        self.state_changed.emit()

        return self._file_path

    def set_modified(self, modified=True):
        modified = bool(
            modified
        )

        if modified == self._modified:
            return

        self._modified = modified

        self.modified_changed.emit(
            self._modified
        )
        self.state_changed.emit()
