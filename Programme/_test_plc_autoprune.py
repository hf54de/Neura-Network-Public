"""Search boundary, non-monotonic error, zero MSE and cancellation checks."""
from _test_plc_quality import app, snap, finish
from plcautoprune import search_threshold, AutoPruneDialog
from PySide6.QtTest import QTest
from PySide6.QtTest import QSignalSpy
from PySide6.QtCore import QTimer
from plcexportsettings import PlcExportSettingsPanel
from plcquality import PruningQualityPanel
from plcautoprune import run_auto_prune

result = finish(search_threshold(snap, 1))
assert result is None
assert finish(search_threshold(snap, 1000))["threshold"] == 0.1


class FakeSnapshot:
    nodes = [(1, 0, "Linear", [(0, 0.012), (0, 0.014), (0, 0.019)])]

    def compare(self, threshold):
        yield None
        # Unsafe, then safe, then unsafe within a coarse interval.
        percent = 10 if 0.012 <= threshold < 0.014 or threshold >= 0.019 else 0
        return dict(original=1, pruned=1 + percent / 100, percent=percent)


assert finish(search_threshold(FakeSnapshot(), 1)) is None


class ZeroSnapshot(FakeSnapshot):
    def compare(self, threshold):
        yield None
        return dict(original=0, pruned=0 if threshold < 0.012 else 0.01, percent=None)


assert finish(search_threshold(ZeroSnapshot(), 100)) is None
dialog = AutoPruneDialog(snap)
dialog.begin()
QTest.qWait(60)
assert dialog.result is None
assert "Kein sinnvolles Pruning möglich" in dialog.status.text()
assert dialog.start.isEnabled()
dialog.reject()
assert not dialog.timer.isActive()
dialog = AutoPruneDialog(snap)
dialog.begin()
dialog.reject()
QTest.qWait(30)
assert dialog.result is None and dialog.job is None and not dialog.timer.isActive()
settings = PlcExportSettingsPanel("FB_Test", "1")
quality = PruningQualityPanel(snap)
events = QSignalSpy(settings.optionsChanged)
original = settings.export_options()

def control_search(cancel=False):
    for widget in app.topLevelWidgets():
        if isinstance(widget, AutoPruneDialog) and widget.isVisible():
            if cancel:
                widget.reject()
            else:
                widget.limit.setValue(1000)
                widget.begin()
            return
    raise AssertionError("Auto-Prune dialog missing")

QTimer.singleShot(10, lambda: control_search(True))
run_auto_prune(settings, quality)
assert settings.export_options() == original and events.count() == 0
QTimer.singleShot(10, control_search)
run_auto_prune(settings, quality)
assert settings.pruning.isChecked()
assert settings.pruning_threshold.value() == 0.1
assert events.count() == 1
print("Auto-Prune: boundary refinement, non-monotonic error, zero MSE and cancellation passed")

# A safe removal before the cliff must still be accepted.
class UsefulSnapshot(FakeSnapshot):
    nodes = [(1, 0, "Linear", [(0, 0.005), (0, 0.012)])]

useful = finish(search_threshold(UsefulSnapshot(), 1))
assert useful["threshold"] == 0.011999999
assert useful["quality"]["percent"] == 0

# Verify the actual modal entry point keeps even previously active pruning unchanged.
settings.pruning_threshold.setValue(0.02)
original = settings.export_options()
previous_events = events.count()
def reject_no_savings():
    for widget in app.topLevelWidgets():
        if isinstance(widget, AutoPruneDialog) and widget.isVisible():
            widget.limit.setValue(1)
            widget.begin()
            def check_and_close():
                assert widget.result is None
                assert "Kein sinnvolles Pruning möglich" in widget.status.text()
                widget.reject()
            QTimer.singleShot(100, check_and_close)
            return
QTimer.singleShot(10, reject_no_savings)
run_auto_prune(settings, quality)
assert settings.export_options() == original
assert events.count() == previous_events
print("Auto-Prune: no-saving message and unchanged settings passed")

# Wrapped instructions and result messages must fit above the controls.
from PySide6.QtGui import QFont
for german in (True, False):
    for font_size in (9, 12):
        layout_dialog = AutoPruneDialog(snap, german)
        layout_dialog.setFont(QFont(app.font().family(), font_size))
        layout_dialog.resize(450, 180)
        layout_dialog.show()
        QTest.qWait(30)
        layout_dialog.begin()
        QTest.qWait(100)
        for width in (450, 620):
            layout_dialog.resize(width, 180)
            QTest.qWait(30)
            for label in (layout_dialog.hint, layout_dialog.status):
                assert label.height() >= label.heightForWidth(label.width())
            assert layout_dialog.hint.geometry().bottom() < layout_dialog.limit.geometry().top()
            assert layout_dialog.status.geometry().bottom() < layout_dialog.start.geometry().top()
        if german and font_size == 9:
            layout_dialog.grab().save("Programme/export_test/autoprune_layout.png")
        layout_dialog.reject()
print("Auto-Prune layout: both text areas fit at different widths and font sizes")
