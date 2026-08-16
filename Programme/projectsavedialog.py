# -------------------------------------------------------------------------------------------------
# Datei: projectsavedialog.py
# Zweck: Steuert Projektname, Speicherort und Datenübernahme beim Speichern unter.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout
)

from language import LanguageManager


class ProjectSaveDialog(QDialog):
    """Erfasst Name, Speicherort und Ordnerstruktur eines Projekts."""

    INVALID_NAME_CHARACTERS = '<>:"/\\|?*'

    def __init__(
        self,
        project_name,
        base_directory,
        has_related_data=False,
        language_manager=None,
        parent=None
    ):
        super().__init__(parent)

        self.language_manager = language_manager or LanguageManager()
        text = self.language_manager.text
        self.setWindowTitle(
            text("project_save.title")
        )
        self.setModal(True)
        self.resize(620, 270)
        self.has_related_data = bool(has_related_data)

        layout = QVBoxLayout(self)
        explanation = QLabel(
            text("project_save.explanation")
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        self.name_edit = QLineEdit(str(project_name))
        self.name_edit.textChanged.connect(self.update_preview)
        form.addRow(
            text("project_save.project_name"),
            self.name_edit
        )

        directory_row = QHBoxLayout()
        self.directory_edit = QLineEdit(str(base_directory))
        self.directory_edit.textChanged.connect(self.update_preview)
        directory_row.addWidget(self.directory_edit, 1)
        browse_button = QPushButton(
            text("project_save.browse")
        )
        browse_button.clicked.connect(self.select_directory)
        directory_row.addWidget(browse_button)
        form.addRow(
            text("project_save.location"),
            directory_row
        )
        layout.addLayout(form)

        self.create_folder_check = QCheckBox(
            text("project_save.create_folder")
        )
        self.create_folder_check.setChecked(True)
        self.create_folder_check.toggled.connect(
            self.project_folder_changed
        )
        layout.addWidget(self.create_folder_check)

        self.copy_data_check = QCheckBox(
            text("project_save.copy_data")
        )
        self.copy_data_check.setChecked(bool(has_related_data))
        self.copy_data_check.setEnabled(bool(has_related_data))
        layout.addWidget(self.copy_data_check)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(
            "color: #445; background: #eef4f8; "
            "border: 1px solid #ccdce7; border-radius: 4px; padding: 7px;"
        )
        layout.addWidget(self.preview_label)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Save
        ).setText(
            text("common.save")
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText(
            text("common.cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.update_preview()

    def normalized_project_name(self):
        name = self.name_edit.text().strip()

        if name.lower().endswith(".nnproj"):
            name = name[:-7].rstrip()

        return name

    def project_folder_changed(self, enabled):
        if not enabled:
            self.copy_data_check.setChecked(False)

        self.copy_data_check.setEnabled(
            bool(enabled)
            and self.has_related_data
        )
        self.update_preview()

    def select_directory(self):
        selected = QFileDialog.getExistingDirectory(
            self,
            self.language_manager.text(
                "project_save.select_location"
            ),
            self.directory_edit.text().strip()
        )

        if selected:
            self.directory_edit.setText(selected)

    def project_file_path(self):
        base_directory = Path(
            self.directory_edit.text().strip()
        )
        project_name = self.normalized_project_name()

        if self.create_folder_check.isChecked():
            base_directory = base_directory / project_name

        return base_directory / f"{project_name}.nnproj"

    def update_preview(self, _value=None):
        project_name = (
            self.normalized_project_name()
            or self.language_manager.text(
                "project_save.placeholder_name"
            )
        )
        directory_text = self.directory_edit.text().strip()

        if directory_text:
            base_directory = Path(directory_text)
            if self.create_folder_check.isChecked():
                base_directory = base_directory / project_name
            preview = base_directory / f"{project_name}.nnproj"
            text = self.language_manager.text(
                "project_save.preview",
                path=preview
            )
        else:
            text = self.language_manager.text(
                "project_save.preview_no_location"
            )

        if self.create_folder_check.isChecked():
            text += (
                "\n"
                + self.language_manager.text(
                    "project_save.subdirectories"
                )
            )

        self.preview_label.setText(text)

    def accept(self):
        project_name = self.normalized_project_name()

        if not project_name:
            QMessageBox.warning(
                self,
                self.language_manager.text("project_save.missing_name.title"),
                self.language_manager.text("project_save.missing_name.message")
            )
            return

        if (
            project_name in {".", ".."}
            or project_name.endswith((" ", "."))
            or any(
                character in project_name
                for character in self.INVALID_NAME_CHARACTERS
            )
        ):
            QMessageBox.warning(
                self,
                self.language_manager.text("project_save.invalid_name.title"),
                self.language_manager.text("project_save.invalid_name.message")
            )
            return

        directory_text = self.directory_edit.text().strip()

        if not directory_text:
            QMessageBox.warning(
                self,
                self.language_manager.text("project_save.missing_location.title"),
                self.language_manager.text("project_save.missing_location.message")
            )
            return

        base_directory = Path(directory_text)

        if not base_directory.is_dir():
            QMessageBox.warning(
                self,
                self.language_manager.text("project_save.location_missing.title"),
                self.language_manager.text("project_save.location_missing.message")
            )
            return

        super().accept()

    @property
    def create_project_folder(self):
        return self.create_folder_check.isChecked()

    @property
    def copy_related_data(self):
        return self.copy_data_check.isChecked()
