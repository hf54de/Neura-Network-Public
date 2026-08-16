# -------------------------------------------------------------------------------------------------
# Datei: projectoverviewdialog.py
# Zweck: Zeigt eine kompakte Übersicht der Projekt- und Netzwerkdaten.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from language import LanguageManager


class ProjectOverviewDialog(QDialog):
    """Kompakte, ausschließlich automatisch ermittelte Projektübersicht."""

    def __init__(self, values, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.setWindowTitle(self.t("project_overview.title"))
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        rows = (
            ("project_overview.structure", values["structure"]),
            ("project_overview.neurons", values["neurons"]),
            ("project_overview.connections", values["connections"]),
            ("project_overview.training_records", values["training_records"]),
            ("project_overview.test_records", values["test_records"]),
            ("project_overview.last_run", values["last_run"]),
            ("project_overview.mean_error", values["mean_error"]),
        )
        for label_key, value in rows:
            value_label = QLabel(str(value))
            value_label.setTextInteractionFlags(value_label.textInteractionFlags())
            form.addRow(self.t(label_key), value_label)
        layout.addLayout(form)

        if values.get("no_training"):
            note = QLabel(self.t("project_overview.no_training"))
            note.setWordWrap(True)
            note.setStyleSheet(
                "QLabel { background: #eef4f8; border: 1px solid #b9cbd8; "
                "border-radius: 4px; padding: 7px; }"
            )
            layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.t("common.close")
        )
        layout.addWidget(buttons)
