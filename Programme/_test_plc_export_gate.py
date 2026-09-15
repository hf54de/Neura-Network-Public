"""Export gating and metadata, including yellow confirmation and clipboard safety."""
from _test_plc_quality import app, snapshot, build, Iec61131ExportGenerator, XmlExportDialog, SpsExportDialog, GxWorks2ExportGenerator
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from unittest.mock import patch
from xml.etree import ElementTree as ET


def choose_warning(accept):
    for widget in app.topLevelWidgets():
        if isinstance(widget, QMessageBox) and widget.isVisible():
            for button in widget.buttons():
                if (widget.buttonRole(button) == QMessageBox.ButtonRole.AcceptRole) == accept:
                    button.click()
                    return


for cls, generator in ((XmlExportDialog, Iec61131ExportGenerator), (SpsExportDialog, GxWorks2ExportGenerator)):
    data = build(generator)
    data['quality_snapshot'] = snapshot
    data['regenerate_export'] = lambda options, version: build(generator, options)
    dialog = cls(data)
    panel = dialog.quality_panel
    settings = dialog.settings_panel
    assert panel.export_comment(settings) == ''
    settings.pruning.setChecked(True)
    with patch.object(QMessageBox, 'warning', return_value=QMessageBox.StandardButton.Ok):
        assert panel.export_comment(settings) is None
    QTest.qWait(50)
    panel.result = dict(original=1, pruned=1.002, percent=0.2, records=1, outputs=1)
    panel.display_result()
    preview = dialog.xml_editor.toPlainText() if cls is XmlExportDialog else dialog.code_editor.toPlainText()
    assert "Pruning: aktiviert" in preview and "GRÜN" in preview
    comment = panel.export_comment(settings)
    assert 'GRÜN' in comment and 'Pruning: aktiviert' in comment
    panel.result.update(pruned=1.021, percent=2.1)
    panel.display_result()
    preview = dialog.xml_editor.toPlainText() if cls is XmlExportDialog else dialog.code_editor.toPlainText()
    assert "Exportbestätigung erforderlich" in preview
    assert "ausdrücklich bestätigt" not in preview
    QTimer.singleShot(10, lambda: choose_warning(False))
    assert panel.export_comment(settings) is None
    QTimer.singleShot(10, lambda: choose_warning(True))
    assert 'ausdrücklich bestätigt' in panel.export_comment(settings)
    panel.result.update(pruned=1.2, percent=20)
    app.clipboard().setText('unchanged')
    with patch.object(QMessageBox, 'warning', return_value=QMessageBox.StandardButton.Ok):
        assert panel.export_comment(settings) is None
        if cls is XmlExportDialog:
            dialog.copy_xml()
            dialog.save_xml()
            editor = dialog.xml_editor
        else:
            dialog.copy_code()
            dialog.copy_declarations()
            dialog.save_complete_file()
            editor = dialog.code_editor
        QTest.keyClick(editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert app.clipboard().text() == 'unchanged'
    panel.result.update(pruned=0.9, percent=-10)
    if cls is XmlExportDialog:
        dialog.copy_xml()
        content = app.clipboard().text()
        ET.fromstring(content)
    else:
        dialog.copy_code()
        content = app.clipboard().text()
    assert 'Fehlerreduktion' in content and 'GRÜN' in content
    assert content.count("Pruning: aktiviert") == 1
    settings.pruning.setChecked(False)
    assert panel.export_comment(settings) == ''
    preview = dialog.xml_editor.toPlainText() if cls is XmlExportDialog else dialog.code_editor.toPlainText()
    assert 'Pruning: aktiviert' not in preview
    dialog.close()
print('PLC export gate: green/yellow/red, pending, keyboard copy and XML metadata passed')
