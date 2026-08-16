# -------------------------------------------------------------------------------------------------
# Datei: projectassistantdialog.py
# Zweck: Erstellt aus Benutzervorgaben einen bearbeitbaren Prompt für Projektideen.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout
)

from language import LanguageManager


class ProjectAssistantDialog(QDialog):
    """Erzeugt einen bearbeitbaren Prompt für eine externe KI."""

    FIELD_OPTIONS = {
        "starting_point": (
            "project_assistant.option.idea_existing",
            "project_assistant.option.idea_topic",
            "project_assistant.option.idea_new"
        ),
        "interest": (
            "project_assistant.option.interest_technology",
            "project_assistant.option.interest_nature",
            "project_assistant.option.interest_science",
            "project_assistant.option.interest_photography",
            "project_assistant.option.interest_vehicles",
            "project_assistant.option.interest_household",
            "project_assistant.option.interest_energy",
            "project_assistant.option.interest_mathematics",
            "project_assistant.option.interest_sport",
            "project_assistant.option.interest_own"
        ),
        "project_type": (
            "project_assistant.option.type_value",
            "project_assistant.option.type_states",
            "project_assistant.option.type_decision",
            "project_assistant.option.type_relationship",
            "project_assistant.option.type_control"
        ),
        "relationship": (
            "project_assistant.option.relationship_physical",
            "project_assistant.option.relationship_mathematical",
            "project_assistant.option.relationship_logical",
            "project_assistant.option.relationship_observed",
            "project_assistant.option.relationship_combined"
        ),
        "training_data": (
            "project_assistant.option.data_formula",
            "project_assistant.option.data_simulated",
            "project_assistant.option.data_experiments",
            "project_assistant.option.data_public"
        ),
        "difficulty": (
            "project_assistant.option.difficulty_easy",
            "project_assistant.option.difficulty_medium",
            "project_assistant.option.difficulty_complex"
        ),
        "exclusions": (
            "project_assistant.option.exclusions_none",
            "project_assistant.option.exclusions_examples",
            "project_assistant.option.exclusions_standard",
            "project_assistant.option.exclusions_both",
            "project_assistant.option.exclusions_own"
        )
    }

    FIELD_LABELS = {
        "starting_point": "project_assistant.field.starting_point",
        "interest": "project_assistant.field.interest",
        "project_type": "project_assistant.field.project_type",
        "relationship": "project_assistant.field.relationship",
        "training_data": "project_assistant.field.training_data",
        "difficulty": "project_assistant.field.difficulty",
        "exclusions": "project_assistant.field.exclusions"
    }

    def __init__(
        self,
        saved_selections=None,
        language_manager=None,
        parent=None
    ):
        super().__init__(parent)

        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.combos = {}
        self.setWindowTitle(self.t("project_assistant.title"))
        self.resize(900, 720)
        self.setMinimumSize(720, 600)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        introduction = QLabel(
            self.t("project_assistant.introduction")
        )
        introduction.setWordWrap(True)
        introduction.setStyleSheet(
            "color: #34495e; background: #eef5f8; "
            "border: 1px solid #cbdde6; border-radius: 5px; padding: 8px;"
        )
        main_layout.addWidget(introduction)

        selection_group = QGroupBox(
            self.t("project_assistant.selection_group")
        )
        selection_form = QFormLayout(selection_group)
        selection_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        saved_selections = (
            saved_selections
            if isinstance(saved_selections, dict)
            else {}
        )

        for field_name, option_keys in self.FIELD_OPTIONS.items():
            combo = QComboBox()
            combo.addItem(
                self.t("project_assistant.option.unselected"),
                ""
            )

            for option_key in option_keys:
                combo.addItem(
                    self.t(option_key),
                    option_key
                )

            stored_value = saved_selections.get(field_name, "")
            stored_index = combo.findData(stored_value)
            combo.setCurrentIndex(max(0, stored_index))
            self.combos[field_name] = combo
            selection_form.addRow(
                self.t(self.FIELD_LABELS[field_name]),
                combo
            )

        self.idea_label = QLabel(
            self.t("project_assistant.field.idea_text")
        )
        self.idea_text = QLineEdit()
        self.idea_text.setPlaceholderText(
            self.t("project_assistant.placeholder.idea")
        )
        selection_form.addRow(
            self.idea_label,
            self.idea_text
        )

        self.own_interest_label = QLabel(
            self.t("project_assistant.field.own_interest")
        )
        self.own_interest_text = QLineEdit()
        self.own_interest_text.setPlaceholderText(
            self.t("project_assistant.placeholder.own_interest")
        )
        selection_form.addRow(
            self.own_interest_label,
            self.own_interest_text
        )

        self.own_exclusions_label = QLabel(
            self.t("project_assistant.field.own_exclusions")
        )
        self.own_exclusions_text = QLineEdit()
        self.own_exclusions_text.setPlaceholderText(
            self.t("project_assistant.placeholder.own_exclusions")
        )
        selection_form.addRow(
            self.own_exclusions_label,
            self.own_exclusions_text
        )

        main_layout.addWidget(selection_group)

        selection_buttons = QHBoxLayout()
        self.generate_button = QPushButton(
            self.t("project_assistant.generate")
        )
        self.reset_button = QPushButton(
            self.t("project_assistant.reset")
        )
        selection_buttons.addWidget(self.generate_button)
        selection_buttons.addWidget(self.reset_button)
        selection_buttons.addStretch()
        main_layout.addLayout(selection_buttons)

        prompt_label = QLabel(
            self.t("project_assistant.prompt_label")
        )
        main_layout.addWidget(prompt_label)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            self.t("project_assistant.prompt_placeholder")
        )
        self.prompt_edit.setMinimumHeight(240)
        main_layout.addWidget(self.prompt_edit, 1)

        bottom_layout = QHBoxLayout()
        self.copy_button = QPushButton(
            self.t("project_assistant.copy")
        )
        self.copy_button.setEnabled(False)
        self.copy_status = QLabel()
        self.copy_status.setStyleSheet("color: #2b7a3d;")
        bottom_layout.addWidget(self.copy_button)
        bottom_layout.addWidget(self.copy_status)
        bottom_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.t("common.close"))
        bottom_layout.addWidget(self.button_box)
        main_layout.addLayout(bottom_layout)

        self.combos["starting_point"].currentIndexChanged.connect(
            self.update_optional_fields
        )
        self.combos["interest"].currentIndexChanged.connect(
            self.update_optional_fields
        )
        self.combos["exclusions"].currentIndexChanged.connect(
            self.update_optional_fields
        )
        self.generate_button.clicked.connect(self.generate_prompt)
        self.reset_button.clicked.connect(self.reset_selections)
        self.copy_button.clicked.connect(self.copy_prompt)
        self.prompt_edit.textChanged.connect(
            self.update_copy_button
        )
        self.button_box.rejected.connect(self.reject)
        self.update_optional_fields()

    def selection_values(self):
        """Liefert nur die projektunabhängig zu speichernden Auswahlen."""

        return {
            field_name: str(combo.currentData() or "")
            for field_name, combo in self.combos.items()
        }

    def selected_text(self, field_name):
        combo = self.combos[field_name]

        if not combo.currentData():
            return self.t("project_assistant.prompt.no_selection")

        return combo.currentText()

    def update_optional_fields(self, _index=None):
        starting_point = self.combos["starting_point"].currentData()
        idea_visible = starting_point in {
            "project_assistant.option.idea_existing",
            "project_assistant.option.idea_topic"
        }
        self.idea_label.setVisible(idea_visible)
        self.idea_text.setVisible(idea_visible)

        own_interest_visible = (
            self.combos["interest"].currentData()
            == "project_assistant.option.interest_own"
        )
        self.own_interest_label.setVisible(own_interest_visible)
        self.own_interest_text.setVisible(own_interest_visible)

        own_exclusions_visible = (
            self.combos["exclusions"].currentData()
            == "project_assistant.option.exclusions_own"
        )
        self.own_exclusions_label.setVisible(own_exclusions_visible)
        self.own_exclusions_text.setVisible(own_exclusions_visible)

    def requirement_text(self):
        """Erstellt die sieben klar gekennzeichneten Benutzervorgaben."""

        lines = []

        for number, field_name in enumerate(
            self.FIELD_OPTIONS,
            start=1
        ):
            value = self.selected_text(field_name)

            if field_name == "starting_point":
                detail = self.idea_text.text().strip()

                if (
                    detail
                    and self.combos["starting_point"].currentData()
                    in {
                        "project_assistant.option.idea_existing",
                        "project_assistant.option.idea_topic"
                    }
                ):
                    value += self.t(
                        "project_assistant.prompt.detail",
                        detail=detail
                    )

            elif field_name == "interest":
                detail = self.own_interest_text.text().strip()

                if (
                    detail
                    and self.combos["interest"].currentData()
                    == "project_assistant.option.interest_own"
                ):
                    value += self.t(
                        "project_assistant.prompt.detail",
                        detail=detail
                    )

            elif field_name == "exclusions":
                detail = self.own_exclusions_text.text().strip()

                if (
                    detail
                    and self.combos["exclusions"].currentData()
                    == "project_assistant.option.exclusions_own"
                ):
                    value += self.t(
                        "project_assistant.prompt.detail",
                        detail=detail
                    )

            lines.append(
                self.t(
                    "project_assistant.prompt.requirement",
                    number=number,
                    label=self.t(self.FIELD_LABELS[field_name]),
                    value=value
                )
            )

        return "\n".join(lines)

    def generate_prompt(self):
        prompt = self.t(
            "project_assistant.prompt.template",
            requirements=self.requirement_text()
        )
        prompt += (
            "\n\n"
            + self.t("project_assistant.prompt.unscaled")
        )
        self.prompt_edit.setPlainText(prompt)
        self.copy_status.clear()

    def reset_selections(self):
        for combo in self.combos.values():
            combo.setCurrentIndex(0)

        self.idea_text.clear()
        self.own_interest_text.clear()
        self.own_exclusions_text.clear()
        self.prompt_edit.clear()
        self.copy_status.clear()
        self.update_optional_fields()

    def update_copy_button(self):
        self.copy_button.setEnabled(
            bool(self.prompt_edit.toPlainText().strip())
        )

    def copy_prompt(self):
        prompt = self.prompt_edit.toPlainText()

        if not prompt.strip():
            return

        QApplication.clipboard().setText(prompt)
        self.copy_status.setText(
            self.t("project_assistant.copied")
        )
