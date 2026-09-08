# Diagnose-Einstieg, zuletzt geändert: 05.09.2026
"""Separate Diagnoseausgabe; verändert weder Training noch Projektformat."""
import functools
import logging
import os
from pathlib import Path
import sys
import threading
from datetime import datetime

ROOT = (Path(sys.executable).parent if getattr(sys, "frozen", False)
        else Path(__file__).parent / "Diagnose")
ROOT.mkdir(parents=True, exist_ok=True)
LOG_DIR = ROOT / "Protokolle"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / f"diagnose_{datetime.now():%Y%m%d_%H%M%S}_{os.getpid()}.log"
logging.basicConfig(filename=LOG_PATH, encoding="utf-8", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("NeuronNetz.Diagnose")


def unhandled(exc_type, value, tb):
    LOG.error("Unbehandelte Ausnahme", exc_info=(exc_type, value, tb))


sys.excepthook = unhandled
threading.excepthook = lambda args: unhandled(
    args.exc_type, args.exc_value, args.exc_traceback)

import PySide6
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox
from settings import Settings

LOG.info("Start EXE=%s Python=%s PySide6=%s", sys.executable,
         sys.version, PySide6.__version__)
CONFIG = ROOT / "Einstellungen"
CONFIG.mkdir(exist_ok=True)
Settings.get_settings_path = classmethod(lambda cls: CONFIG / "settings.json")
Settings.get_legacy_settings_path = staticmethod(lambda: CONFIG / "legacy.json")
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
    QSettings.setPath(QSettings.Format.IniFormat, scope, str(CONFIG))
if not (CONFIG / "settings.json").exists():
    (CONFIG / "settings.json").write_text('{"ui":{"language":"de"}}', encoding="utf-8")


def diagnostic_message(original):
    @functools.wraps(original)
    def show(parent, title, text, *args, **kwargs):
        exception_info = sys.exc_info()
        LOG.error("Dialog %s: %s", title, text,
                  exc_info=exception_info if exception_info[0] else None)
        if exception_info[0]:
            label = ("Diagnoseprotokoll" if Settings.get_ui_settings().get("language") == "de"
                     else "Diagnostic log")
            text = f"{text}\n\n{label}:\n{LOG_PATH}"
        return original(parent, title, text, *args, **kwargs)
    return show


QMessageBox.critical = diagnostic_message(QMessageBox.critical)
QMessageBox.warning = diagnostic_message(QMessageBox.warning)

from mainwindow import MainWindow


def traced_action(original):
    @functools.wraps(original)
    def call(self, *args, **kwargs):
        LOG.info("Beginn %s Projekt=%s", original.__name__,
                 getattr(self, "current_project_path", None))
        try:
            result = original(self, *args, **kwargs)
        except Exception:
            LOG.exception("Ausnahme in %s", original.__name__)
            raise
        LOG.info("Ende %s", original.__name__)
        return result
    return call


for name in ("write_project_file", "save_modified_related_data",
             "open_graphical_experiment", "rename_current_project",
             "delete_graphics_items", "open_network_structure_dialog"):
    setattr(MainWindow, name, traced_action(getattr(MainWindow, name)))

if "--self-test" in sys.argv:
    # Prüft auch das Erfassen bereits abgefangener Fehler ohne Dialoganzeige.
    messages = []
    test_message = diagnostic_message(lambda *args, **kwargs: messages.append(args[2]))
    try:
        raise TypeError("DIAGNOSE_SELF_TEST")
    except TypeError as error:
        test_message(None, "Selbsttest", str(error))
    logging.shutdown()
    contents = LOG_PATH.read_text(encoding="utf-8")
    assert "Traceback (most recent call last)" in contents
    assert "DIAGNOSE_SELF_TEST" in contents
    assert str(LOG_PATH) in messages[0]
    (ROOT / "self-test-ok.txt").write_text(str(LOG_PATH), encoding="utf-8")
    sys.exit(0)

if not any(str(arg).lower().endswith(".nnproj") for arg in sys.argv[1:]):
    copies = sorted((ROOT / "Projektkopie").glob("*/*.nnproj"))
    if copies:
        sys.argv.append(str(copies[0]))
import main
