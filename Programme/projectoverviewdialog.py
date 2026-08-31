# -------------------------------------------------------------------------------------------------
# Datei: projectoverviewdialog.py
# Zweck: Zeigt Projektübersicht und ausführliche Projektprüfung.
# Letzte Änderung: 24.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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


class ProjectCheckDialog(QDialog):
    """Zeigt eine rein lesende Prüfung des aktuellen Projektzustands."""

    STATUS_STYLE = {
        "ok": ("✓", "#1b5e20", "#e8f5e9", "#81c784"),
        "warning": ("!", "#7a4700", "#fff8d8", "#d6c36a"),
        "error": ("✕", "#8b1a1a", "#fdecec", "#df8b8b"),
    }

    def __init__(self, result_provider, parent=None, language_manager=None):
        super().__init__(parent)
        self.language = language_manager or LanguageManager()
        self.t = self.language.text
        self.result_provider = result_provider
        self.setWindowTitle(self.t("project_check.title"))
        self.setMinimumWidth(640)
        self.resize(720, 1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        main_layout.addWidget(self.summary_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 6, 0)
        self.content_layout.setSpacing(9)
        self.scroll_area.setWidget(self.content)
        main_layout.addWidget(self.scroll_area, 1)

        button_layout = QHBoxLayout()
        self.recheck_button = QPushButton(self.t("project_check.recheck"))
        self.recheck_button.clicked.connect(self.refresh)
        button_layout.addWidget(self.recheck_button)
        button_layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.t("common.close")
        )
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        main_layout.addLayout(button_layout)
        self.refresh()

    def clear_sections(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self):
        """Ermittelt den aktuellen Zustand erneut und baut die Anzeige neu auf."""

        result = self.result_provider()
        overall = result.get("overall", "warning")
        _symbol, color, background, border = self.STATUS_STYLE[overall]
        self.summary_label.setText(result.get("summary", ""))
        self.summary_label.setStyleSheet(
            "QLabel { font-weight: bold; padding: 10px; border-radius: 5px; "
            f"color: {color}; background: {background}; border: 1px solid {border}; }}"
        )

        self.clear_sections()
        for section in result.get("sections", []):
            status = section.get("status", "warning")
            symbol, color, background, border = self.STATUS_STYLE[status]
            group = QGroupBox(f"{symbol}  {section.get('title', '')}")
            group.setStyleSheet(
                "QGroupBox { font-weight: bold; margin-top: 8px; "
                f"border: 1px solid {border}; border-radius: 5px; }}"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; "
                f"padding: 0 4px; color: {color}; }}"
            )
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(12, 14, 12, 10)
            group_layout.setSpacing(5)
            for line in section.get("lines", []):
                label = QLabel(str(line))
                label.setWordWrap(True)
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                group_layout.addWidget(label)
            self.content_layout.addWidget(group)

        # Der Scrollbereich folgt der tatsächlichen Inhaltshöhe. Erst bei
        # umfangreicheren Prüfergebnissen wird seine Höhe begrenzt und der
        # vorhandene vertikale Scrollbalken verwendet.
        self.content_layout.activate()
        content_height = self.content_layout.sizeHint().height()
        self.scroll_area.setFixedHeight(
            min(560, max(100, content_height + 2))
        )
        self.adjustSize()
