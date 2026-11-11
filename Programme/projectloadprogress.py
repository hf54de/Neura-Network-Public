"""Visible project loading, with file validation outside the GUI thread."""
import time
from PySide6.QtCore import QEventLoop, QThread, Signal, Qt, QObject, Slot
from PySide6.QtWidgets import QApplication, QProgressDialog
from projectio import ProjectIO


class ProjectReader(QThread):
    phase_changed = Signal(str)

    def __init__(self, path, translator):
        super().__init__()
        self.path, self.translator = path, translator
        self.result = self.error = None

    def run(self):
        try:
            self.result = ProjectIO.load_project(self.path, translator=self.translator,
                                                progress=self.phase_changed.emit)
        except Exception as error:
            self.error = error


class LoadingDialog(QProgressDialog):
    def reject(self):
        pass

    def closeEvent(self, event):
        event.ignore()


class ProjectLoadProgress(QObject):
    def __init__(self, parent, language):
        super().__init__(parent)
        self.language = language
        self.dialog = LoadingDialog(parent)
        self.dialog.setWindowTitle(language.text("project.loading.title"))
        self.dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.dialog.setCancelButton(None)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        self.dialog.setMinimumDuration(0)
        self.dialog.setMinimumWidth(430)
        self.window = parent
        self.loaded = False
        self.scene = getattr(parent, "scene", None)
        self.saved_weight_labels = None
        self.total = self.done = 0
        self.last_update = 0

    def __enter__(self):
        if self.window is not None and hasattr(self.window, "view"):
            viewport = self.window.view.viewport()
            self.window._loading_viewport_visibility = not viewport.isHidden()
            viewport.hide()
        self.phase("project.loading.read")
        self.dialog.show()
        self.dialog.raise_()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        return self

    def __exit__(self, *args):
        self.restore_weight_labels()
        if self.window is not None and hasattr(self.window, "view"):
            if self.loaded and not args[0]:
                # Finish queued centering/layout before revealing the fitted scene.
                if self.window.isVisible():
                    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                    self.window.fit_loaded_project(self.window.current_project_path)
            else:
                self.window.restore_loading_viewport()
        self.dialog.hide()
        self.dialog.deleteLater()

    def restore_weight_labels(self):
        if self.saved_weight_labels is not None:
            visible = self.saved_weight_labels
            self.saved_weight_labels = None
            self.scene.set_weight_labels_visible(visible)

    @Slot(str)
    def phase(self, key):
        if key == "project.loading.view":
            self.restore_weight_labels()
        self.dialog.setRange(0,0)
        self.dialog.setLabelText(self.language.text(key))
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def read(self, path):
        reader = ProjectReader(path, self.language.text)
        loop = QEventLoop()
        reader.phase_changed.connect(self.phase, Qt.ConnectionType.QueuedConnection)
        reader.finished.connect(loop.quit)
        reader.start()
        loop.exec()
        reader.wait()
        if reader.error is not None:
            self.dialog.hide()
            raise reader.error
        return reader.result

    def begin(self, total):
        if self.scene is not None:
            self.saved_weight_labels = self.scene.weight_labels_visible
            self.scene.set_weight_labels_visible(False)
        self.total, self.done = total, 0
        self.dialog.setRange(0,max(1,total))
        self.dialog.setValue(0)

    def advance(self):
        self.done += 1
        now = time.monotonic()
        if now-self.last_update < .08 and self.done != self.total:
            return
        self.last_update = now
        self.dialog.setLabelText(self.language.text("project.loading.count",done=self.done,total=self.total))
        self.dialog.setValue(self.done)
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
