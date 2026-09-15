"""Regression for pauses while entering decimals and non-destructive live preview."""
from _test_plc_pruning import app
from PySide6.QtCore import QLocale, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from plcexportsettings import PruningThresholdSpinBox

dialog = QDialog()
layout = QVBoxLayout(dialog)
field = PruningThresholdSpinBox(dialog)
field.setDecimals(9)
field.setRange(0, 1000000)
field.setKeyboardTracking(False)
layout.addWidget(field)
button = QPushButton("Default action", dialog)
button.setDefault(True)
layout.addWidget(button)
clicks = QSignalSpy(button.clicked)
dialog.show()
for locale in ("de_DE", "en_US"):
    field.setLocale(QLocale(locale))
    for separator in (",", "."):
        field.setValue(0.123)
        field.setFocus()
        editor = field.lineEdit()
        editor.selectAll()
        QTest.keyClicks(editor, "0" + separator)
        QTest.qWait(400)
        assert editor.text() == "0" + separator
        assert field.value() == 0.123
        for digit in "001":
            QTest.keyClicks(editor, digit)
            text, cursor = editor.text(), editor.cursorPosition()
            QTest.qWait(400)
            assert editor.text() == text and editor.cursorPosition() == cursor
        assert field.value() == 0.001
        QTest.keyClicks(editor, "00")
        QTest.qWait(400)
        assert editor.text() == "0" + separator + "00100"
        QTest.keyClick(editor, Qt.Key.Key_Return)
        assert editor.text() == field.textFromValue(0.001)
        assert clicks.count() == 0
        editor.selectAll()
        QTest.keyClicks(editor, "0" + separator + "00200")
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        assert field.value() == 0.002
        assert editor.text() == field.textFromValue(0.002)
    field.setValue(1000000)
    assert field.hasAcceptableInput()
dialog.close()
print("Pruning decimal input: slow typing, comma/dot, Enter and focus loss passed")
