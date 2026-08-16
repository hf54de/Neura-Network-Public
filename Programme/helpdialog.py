# -------------------------------------------------------------------------------------------------
# Datei: helpdialog.py
# Zweck: Zeigt die sprachabhängige Markdown-Hilfe innerhalb des Programms an.
# Letzte Änderung: 09.08.2026
# Copyright © 2026 Helwig Fülling
# -------------------------------------------------------------------------------------------------
import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget
)

from language import LanguageManager


class HelpDialog(QDialog):
    """
    Zeigt die bearbeitbare Markdown-Hilfedatei
    hilfe.md in einem eigenen Fenster an.

    Die Datei wird beim Öffnen des Dialogs neu eingelesen.
    Änderungen an hilfe.md sind deshalb ohne Änderung
    des Python-Codes sichtbar.
    """

    def __init__(
        self,
        parent=None,
        help_file_path=None,
        language_manager=None
    ):
        super().__init__(
            parent
        )

        self.language = language_manager or LanguageManager()
        self.t = self.language.text

        self.help_file_path = (
            Path(
                help_file_path
            )
            if help_file_path
            else self.find_help_file()
        )

        self.search_matches = []
        self.current_search_index = -1
        self.search_term = ""

        self.setWindowTitle(
            self.t("help.title")
        )

        self.resize(
            1050,
            780
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.search_layout = QHBoxLayout()

        self.search_label = QLabel(
            self.t("help.search.label")
        )

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            self.t("help.search.placeholder")
        )

        self.search_button = QPushButton(
            self.t("help.search.button")
        )

        self.search_next_button = QPushButton(
            self.t("help.search.next")
        )

        self.search_layout.addWidget(
            self.search_label
        )

        self.search_layout.addWidget(
            self.search_edit,
            1
        )

        self.search_layout.addWidget(
            self.search_button
        )

        self.search_layout.addWidget(
            self.search_next_button
        )

        self.main_layout.addLayout(
            self.search_layout
        )

        self.help_browser = QTextBrowser()
        self.apply_document_style()

        self.help_browser.setOpenExternalLinks(
            True
        )

        self.help_browser.setOpenLinks(
            True
        )

        self.navigation_widget = QWidget()
        self.navigation_widget.setMinimumWidth(
            230
        )
        self.navigation_widget.setMaximumWidth(
            340
        )

        self.navigation_layout = QVBoxLayout(
            self.navigation_widget
        )
        self.navigation_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )
        self.navigation_layout.setSpacing(
            8
        )

        self.navigation_title = QLabel(
            self.t("help.chapters")
        )
        self.navigation_title.setStyleSheet(
            "font-size: 13pt; font-weight: 600; color: #174f78;"
        )

        self.navigation_tree = QTreeWidget()
        self.navigation_tree.setHeaderHidden(
            True
        )
        self.navigation_tree.setIndentation(
            14
        )
        self.navigation_tree.setStyleSheet(
            """
            QTreeWidget {
                background-color: #f3f7fa;
                border: 1px solid #c9d2dc;
                border-radius: 4px;
                color: #263442;
                font-family: "Segoe UI";
                font-size: 10pt;
                outline: 0;
            }

            QTreeWidget::item {
                min-height: 27px;
                padding-left: 4px;
                padding-right: 4px;
            }

            QTreeWidget::item:hover {
                background-color: #e3eef6;
            }

            QTreeWidget::item:selected {
                background-color: #3479a6;
                color: #ffffff;
            }
            """
        )

        self.navigation_layout.addWidget(
            self.navigation_title
        )
        self.navigation_layout.addWidget(
            self.navigation_tree,
            1
        )

        self.content_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )
        self.content_splitter.setChildrenCollapsible(
            False
        )
        self.content_splitter.addWidget(
            self.navigation_widget
        )
        self.content_splitter.addWidget(
            self.help_browser
        )
        self.content_splitter.setStretchFactor(
            0,
            0
        )
        self.content_splitter.setStretchFactor(
            1,
            1
        )
        self.content_splitter.setSizes(
            [270, 780]
        )

        self.main_layout.addWidget(
            self.content_splitter,
            1
        )

        self.status_label = QLabel()
        self.status_label.setWordWrap(
            True
        )

        self.main_layout.addWidget(
            self.status_label
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.button_box.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(self.t("common.close"))

        self.button_box.rejected.connect(
            self.reject
        )

        self.main_layout.addWidget(
            self.button_box
        )

        self.search_button.clicked.connect(
            self.start_search
        )

        self.search_next_button.clicked.connect(
            self.find_next
        )

        self.search_edit.returnPressed.connect(
            self.find_next
        )

        self.search_edit.textChanged.connect(
            self.clear_search_highlights
        )

        self.navigation_tree.itemClicked.connect(
            self.navigate_to_chapter
        )

        self.load_help_file()

    @staticmethod
    def get_application_directory():
        """
        Liefert den Programmordner sowohl beim normalen
        Python-Start als auch bei einer später gepackten EXE.
        """

        if getattr(
            sys,
            "frozen",
            False
        ):
            return Path(
                sys.executable
            ).resolve().parent

        return Path(
            __file__
        ).resolve().parent

    @classmethod
    def find_help_file(
        cls
    ):
        """
        Sucht hilfe.md an den üblichen Stellen.
        """

        application_directory = (
            cls.get_application_directory()
        )

        candidates = [
            # Normalfall: hilfe.md liegt direkt
            # neben den Python-Dateien beziehungsweise
            # neben der später erzeugten EXE.
            application_directory
            / "hilfe.md",

            Path.cwd()
            / "hilfe.md",

            # Abwärtskompatibilität mit einer früheren
            # Ordnerstruktur.
            application_directory
            / "docs"
            / "hilfe.md",

            Path.cwd()
            / "docs"
            / "hilfe.md"
        ]

        temporary_directory = getattr(
            sys,
            "_MEIPASS",
            None
        )

        if temporary_directory:
            candidates.insert(
                0,
                Path(
                    temporary_directory
                )
                / "hilfe.md"
            )

            candidates.insert(
                1,
                Path(
                    temporary_directory
                )
                / "docs"
                / "hilfe.md"
            )

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return candidates[0]

    @staticmethod
    def create_anchor_name(
        heading_text
    ):
        """
        Erzeugt aus einer Überschrift den Namen der
        zugehörigen internen Sprungmarke.
        """

        anchor_name = re.sub(
            r"[^\w\s-]",
            "",
            heading_text.strip().lower()
        )

        return re.sub(
            r"[\s-]+",
            "-",
            anchor_name
        ).strip("-")

    def populate_navigation(
        self,
        help_text
    ):
        """
        Erstellt die dauerhaft sichtbare Kapitelnavigation
        aus den nummerierten Hauptüberschriften der Hilfe.
        """

        self.navigation_tree.clear()

        navigation_groups = [
            (1, 6, self.t("help.group.basics")),
            (7, 15, self.t("help.group.editing")),
            (16, 24, self.t("help.group.training")),
            (25, 28, self.t("help.group.files")),
            (29, 33, self.t("help.group.reference"))
        ]

        group_items = []

        for first_number, last_number, title in navigation_groups:
            group_item = QTreeWidgetItem(
                [title]
            )
            group_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                None
            )

            group_font = group_item.font(
                0
            )
            group_font.setBold(
                True
            )
            group_item.setFont(
                0,
                group_font
            )

            self.navigation_tree.addTopLevelItem(
                group_item
            )
            group_items.append(
                (
                    first_number,
                    last_number,
                    group_item
                )
            )

        first_chapter_item = None

        chapter_pattern = re.compile(
            r"^#\s+(\d+)\.\s+(.+?)\s*$",
            re.MULTILINE
        )

        for match in chapter_pattern.finditer(
            help_text
        ):
            chapter_number = int(
                match.group(1)
            )
            chapter_title = match.group(2).strip()
            full_title = (
                f"{chapter_number}. {chapter_title}"
            )

            parent_item = None

            for first_number, last_number, group_item in group_items:
                if first_number <= chapter_number <= last_number:
                    parent_item = group_item
                    break

            if parent_item is None:
                continue

            chapter_item = QTreeWidgetItem(
                [full_title]
            )
            chapter_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                self.create_anchor_name(
                    full_title
                )
            )
            chapter_item.setToolTip(
                0,
                full_title
            )

            parent_item.addChild(
                chapter_item
            )

            if first_chapter_item is None:
                first_chapter_item = chapter_item

        self.navigation_tree.expandAll()

        if first_chapter_item is not None:
            self.navigation_tree.setCurrentItem(
                first_chapter_item
            )

    def navigate_to_chapter(
        self,
        item,
        column
    ):
        """
        Springt beim Anklicken eines Kapitels zur
        entsprechenden Überschrift im Hilfetext.
        """

        anchor_name = item.data(
            column,
            Qt.ItemDataRole.UserRole
        )

        if not anchor_name:
            item.setExpanded(
                not item.isExpanded()
            )
            return

        self.help_browser.scrollToAnchor(
            anchor_name
        )
        self.status_label.setText(
            self.t("help.status.chapter", chapter=item.text(column))
        )

    def apply_document_style(
        self
    ):
        """
        Legt eine ruhige und gut lesbare Darstellung
        für die Markdown-Dokumentation fest.
        """

        self.help_browser.setStyleSheet(
            """
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #c9d2dc;
                border-radius: 4px;
                padding: 14px;
                selection-background-color: #b9d7f2;
                selection-color: #17212b;
            }
            """
        )

        self.help_browser.document().setDefaultStyleSheet(
            """
            body {
                color: #263442;
                font-family: "Segoe UI";
                font-size: 11pt;
                line-height: 145%;
            }

            h1 {
                color: #174f78;
                font-size: 22pt;
                font-weight: 600;
                margin-top: 34px;
                margin-bottom: 20px;
            }

            h2 {
                color: #27668f;
                font-size: 16pt;
                font-weight: 600;
                margin-top: 28px;
                margin-bottom: 16px;
            }

            h3 {
                color: #3a718f;
                font-size: 13pt;
                font-weight: 600;
                margin-top: 22px;
                margin-bottom: 12px;
            }

            p {
                margin-top: 7px;
                margin-bottom: 13px;
            }

            a {
                color: #1769a0;
                text-decoration: none;
            }

            ul, ol {
                margin-top: 9px;
                margin-bottom: 15px;
                margin-left: 22px;
            }

            li {
                margin-bottom: 6px;
            }

            blockquote {
                color: #40566a;
                background-color: #eef5fa;
                border-left: 4px solid #5e96bb;
                margin: 12px 8px;
                padding: 8px 12px;
            }

            code {
                color: #7b2f3a;
                background-color: #f2f4f6;
                font-family: "Consolas";
            }

            pre {
                color: #263442;
                background-color: #f2f4f6;
                border: 1px solid #d8dee4;
                margin: 14px 4px;
                padding: 10px;
                font-family: "Consolas";
            }

            table {
                border-collapse: collapse;
                margin-top: 14px;
                margin-bottom: 18px;
            }

            th {
                color: #ffffff;
                background-color: #376f94;
                border: 1px solid #9aabb8;
                padding: 6px 9px;
                font-weight: 600;
            }

            td {
                border: 1px solid #bdc8d1;
                padding: 6px 9px;
            }

            hr {
                color: #c7d2dc;
                margin-top: 24px;
                margin-bottom: 24px;
            }
            """
        )

    def load_help_file(
        self
    ):
        """
        Liest die Markdown-Datei ein und zeigt sie an.
        """

        try:
            help_text = self.help_file_path.read_text(
                encoding="utf-8"
            )

        except OSError as error:
            self.help_browser.setHtml(
                (
                    self.t("help.file_missing.html")
                    +
                    f"<p>{error}</p>"
                )
            )

            self.status_label.setText(
                self.t("help.status.searched_path", path=self.help_file_path)
            )

            QMessageBox.warning(
                self,
                self.t("help.message.title"),
                self.t("help.file_missing.message", path=self.help_file_path, error=error)
            )

            return

        self.help_browser.setMarkdown(
            help_text
        )

        self.apply_block_spacing()
        self.create_heading_anchors()
        self.populate_navigation(
            help_text
        )

        self.help_browser.moveCursor(
            QTextCursor.MoveOperation.Start
        )

        self.status_label.setText(
            self.t("help.status.file", path=self.help_file_path)
        )

    def apply_block_spacing(
        self
    ):
        """
        Setzt gut sichtbare Abstände direkt an den
        Textblöcken des eingelesenen Markdown-Dokuments.

        QTextBrowser berücksichtigt CSS-Ränder bei
        Markdown-Überschriften nicht auf allen Systemen
        zuverlässig. Die Blockformatierung stellt deshalb
        unabhängig vom verwendeten Qt-Stil eine luftige
        Gliederung sicher.
        """

        document = self.help_browser.document()
        block = document.begin()

        heading_spacing = {
            1: (34.0, 20.0),
            2: (28.0, 16.0),
            3: (22.0, 12.0)
        }

        while block.isValid():
            cursor = QTextCursor(
                block
            )
            block_format = block.blockFormat()
            heading_level = block_format.headingLevel()

            if heading_level > 0:
                top_margin, bottom_margin = (
                    heading_spacing.get(
                        heading_level,
                        (18.0, 10.0)
                    )
                )

                block_format.setTopMargin(
                    top_margin
                )
                block_format.setBottomMargin(
                    bottom_margin
                )

            elif (
                block.text().strip()
                and cursor.currentTable() is None
                and not block.charFormat().fontFixedPitch()
            ):
                if block.textList() is not None:
                    block_format.setBottomMargin(
                        6.0
                    )

                else:
                    block_format.setBottomMargin(
                        12.0
                    )

            cursor.setBlockFormat(
                block_format
            )

            block = block.next()

    def create_heading_anchors(
        self
    ):
        """
        Ergänzt die internen Sprungmarken für
        Markdown-Überschriften.

        QTextBrowser übernimmt beim Einlesen von Markdown
        zwar die Verweise aus dem Inhaltsverzeichnis, erzeugt
        für die Überschriften jedoch keine passenden Anker.
        """

        document = self.help_browser.document()
        block = document.begin()

        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                anchor_name = self.create_anchor_name(
                    block.text()
                )

                if anchor_name and block.length() > 1:
                    cursor = QTextCursor(
                        block
                    )

                    cursor.movePosition(
                        QTextCursor.MoveOperation.Right,
                        QTextCursor.MoveMode.KeepAnchor,
                        1
                    )

                    anchor_format = cursor.charFormat()
                    anchor_format.setAnchor(
                        True
                    )
                    anchor_format.setAnchorNames(
                        [anchor_name]
                    )
                    cursor.mergeCharFormat(
                        anchor_format
                    )

            block = block.next()

    def start_search(
        self
    ):
        """
        Markiert alle Treffer und zeigt den ersten an.
        """

        search_text = self.search_edit.text().strip()
        self.clear_search_highlights()

        if not search_text:
            self.search_edit.setFocus()
            return

        document = self.help_browser.document()
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        while True:
            match = document.find(search_text, cursor)
            if match.isNull():
                break

            self.search_matches.append(QTextCursor(match))
            cursor = match

        self.search_term = search_text

        if self.search_matches:
            self.current_search_index = 0
            self.show_current_search_match()
        else:
            self.status_label.setText(
                self.t("help.status.not_found", text=search_text)
            )

    def clear_search_highlights(
        self
    ):
        """Entfernt alle vorübergehenden Suchmarkierungen."""

        self.search_matches = []
        self.current_search_index = -1
        self.search_term = ""
        self.help_browser.setExtraSelections([])

    def show_current_search_match(
        self
    ):
        """Hebt alle Treffer und den aktuellen Treffer verschieden hervor."""

        selections = []

        for index, match in enumerate(self.search_matches):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(match)

            text_format = QTextCharFormat()
            text_format.setForeground(QColor("#000000"))
            text_format.setBackground(
                QColor("#ffb74d")
                if index == self.current_search_index
                else QColor("#fff59d")
            )
            selection.format = text_format
            selections.append(selection)

        self.help_browser.setExtraSelections(selections)

        current_match = self.search_matches[self.current_search_index]
        navigation_cursor = QTextCursor(current_match)
        navigation_cursor.clearSelection()
        self.help_browser.setTextCursor(navigation_cursor)
        self.help_browser.ensureCursorVisible()

        self.status_label.setText(
            self.t(
                "help.status.found_position",
                text=self.search_term,
                current=self.current_search_index + 1,
                total=len(self.search_matches)
            )
        )

    def find_next(
        self
    ):
        """
        Sucht ab der aktuellen Position nach dem
        nächsten Vorkommen des Suchbegriffs.
        """

        search_text = self.search_edit.text().strip()

        if not search_text:
            self.search_edit.setFocus()
            return

        if search_text != self.search_term or not self.search_matches:
            self.start_search()
            return

        self.current_search_index = (
            self.current_search_index + 1
        ) % len(self.search_matches)
        self.show_current_search_match()
