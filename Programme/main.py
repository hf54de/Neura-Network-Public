# -------------------------------------------------------------------------------------------------
# Datei: main.py
# Purpose: Launches NeuronNetz and controls the flow of the intro and main window.
# Last modified: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import sys
from PySide6.QtCore import (
    QLibraryInfo,
    QLocale,
    QTimer,
    QTranslator,
)
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow
from aboutdialog import program_version
from language import LanguageManager
from settings import Settings
from startsplash import StartSplash


class GermanStandardTranslator(QTranslator):
    """Fallback für Qt-Standardschaltflächen ohne verfügbare QM-Datei."""

    TRANSLATIONS = {
        "Yes": "Ja",
        "&Yes": "&Ja",
        "Yes to All": "Ja, alle",
        "&Yes to All": "&Ja, alle",
        "No": "Nein",
        "&No": "&Nein",
        "No to All": "Nein, alle",
        "&No to All": "&Nein, alle",
        "OK": "OK",
        "Cancel": "Abbrechen",
        "&Cancel": "&Abbrechen",
        "Close": "Schließen",
        "&Close": "&Schließen",
        "Open": "Öffnen",
        "&Open": "&Öffnen",
        "Save": "Speichern",
        "&Save": "&Speichern",
        "Save All": "Alle speichern",
        "Discard": "Verwerfen",
        "Don't Save": "Nicht speichern",
        "Apply": "Übernehmen",
        "&Apply": "&Übernehmen",
        "Reset": "Zurücksetzen",
        "Restore Defaults": "Standardwerte",
        "Abort": "Abbrechen",
        "Retry": "Wiederholen",
        "Ignore": "Ignorieren",
        "Help": "Hilfe"
    }

    def translate(
        self,
        context,
        source_text,
        disambiguation=None,
        n=-1
    ):
        return self.TRANSLATIONS.get(
            source_text,
            source_text
        )


def center_splash_on_saved_window(app, splash):
    """Zentriert das Startbild über der gespeicherten Hauptfensterlage."""

    target_center = None
    settings_data = Settings.load()
    if isinstance(settings_data.get("window"), dict):
        anchor_window = QMainWindow()
        Settings.restore_window(anchor_window)
        target_center = anchor_window.frameGeometry().center()
        anchor_window.deleteLater()

    screen = (
        app.screenAt(target_center)
        if target_center is not None
        else None
    )
    if screen is None:
        screen = app.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    if target_center is None or not available.contains(target_center):
        target_center = available.center()

    x = target_center.x() - splash.width() // 2
    y = target_center.y() - splash.height() // 2
    x = max(available.left(), min(x, available.right() - splash.width() + 1))
    y = max(available.top(), min(y, available.bottom() - splash.height() + 1))
    splash.move(x, y)


app = QApplication(sys.argv)

selected_language = Settings.get_ui_settings().get("language", "en")
german_interface = selected_language == "de"

# Qt liefert die Beschriftungen seiner Standardschaltflächen selbst.
# Die deutsche Übersetzung muss deshalb vor dem Erzeugen der Fenster
# installiert werden, damit zum Beispiel Ja/Nein, Abbrechen, Speichern
# und Schließen in allen Dialogen einheitlich deutsch erscheinen.
selected_locale = QLocale(
    QLocale.Language.German if german_interface else QLocale.Language.English,
    QLocale.Country.Germany if german_interface else QLocale.Country.UnitedStates
)
QLocale.setDefault(selected_locale)

fallback_translator = None
if german_interface:
    fallback_translator = GermanStandardTranslator(app)
    app.installTranslator(fallback_translator)

qt_translator = QTranslator(app)
translations_path = QLibraryInfo.path(
    QLibraryInfo.LibraryPath.TranslationsPath
)
qt_translation_loaded = qt_translator.load(
    selected_locale,
    "qtbase",
    "_",
    translations_path
)

if german_interface and not qt_translation_loaded:
    qt_translation_loaded = qt_translator.load(
        "qt_de",
        translations_path
    )

if qt_translation_loaded:
    app.installTranslator(qt_translator)

ui_settings = Settings.get_ui_settings()
language_manager = LanguageManager(selected_language)
splash = None

if ui_settings.get("show_startup_splash", True):
    splash = StartSplash(
        language_manager,
        program_version(language_manager),
    )
    splash.show()
    splash.show_status("startup.status.interface")
    app.processEvents()
    center_splash_on_saved_window(app, splash)
    splash.raise_()
    app.processEvents()

# Der umfangreiche Hauptfensterimport erfolgt bewusst erst nach dem Anzeigen
# des Startbildes. So begleitet es auch den tatsächlichen Modul- und
# Oberflächenaufbau, ohne den Programmstart künstlich zu verlängern.
from mainwindow import MainWindow

window = MainWindow(defer_initial_show=True)

explicit_project_path = next(
    (
        argument
        for argument in sys.argv[1:]
        if Path(argument).suffix.lower() == ".nnproj"
    ),
    None
)
def complete_startup():
    if splash is not None:
        startup_project_available = bool(
            explicit_project_path
            or (
                ui_settings.get("reopen_last_project", True)
                and Settings.get_last_project_file()
            )
        )
        splash.show_status(
            "startup.status.project"
            if startup_project_available
            else "startup.status.ready"
        )
        app.processEvents()

    window.open_startup_project(explicit_project_path)

    def reveal_main_window():
        window.show_after_startup()
        if splash is not None:
            splash.finish(window)

    if splash is None:
        reveal_main_window()
        return

    # Nach dem abgeschlossenen Laden bleibt das Intro bewusst noch kurz
    # stehen. Dadurch ist es auch auf schnellen Rechnern gut wahrnehmbar.
    QTimer.singleShot(2500, reveal_main_window)


QTimer.singleShot(0, complete_startup)

sys.exit(app.exec())
