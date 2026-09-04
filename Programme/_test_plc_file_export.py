from pathlib import Path
from xml.etree import ElementTree as ET

from PySide6.QtWidgets import QApplication

from gxworks2export import GxWorks2ExportGenerator
from gxworks3export import GxWorks3ExportGenerator, GxWorks3XmlExportGenerator
from iec61131export import Iec61131ExportGenerator
from mainwindow import MainWindow
from networktestdialog import NetworkTestDialog
from plcfileexport import GxWorks2AscExporter, GxWorks3XmlExporter, Iec61131XmlExporter
from spsexportdialog import SpsExportDialog
from xmlexportdialog import XmlExportDialog


app = QApplication([])
window = MainWindow()
project = Path(__file__).parent / "dist" / "Projects_en" / "AND 01" / "AND 01.nnproj"
assert window.open_project(str(project)), "Example project could not be loaded"

_records, input_mappings, output_mappings = NetworkTestDialog.prepare_document(
    window.scene.network,
    window.training_data_manager.document,
    data_label=window.language.text("test.data.training"),
    translator=window.language.text,
)
gx2 = GxWorks2ExportGenerator(
    window.scene.network,
    input_mappings,
    output_mappings,
    project_name=project.stem,
    language_code="en",
).generate()
gx3 = GxWorks3ExportGenerator(
    window.scene.network,
    input_mappings,
    output_mappings,
    project_name=project.stem,
    language_code="en",
).generate()

output_dir = Path(__file__).parent / "export_test"
output_dir.mkdir(exist_ok=True)
asc = GxWorks2AscExporter.build(
    gx2["fb_name"], gx2["headers"], gx2["declarations"], gx2["code"]
)
xml = Iec61131XmlExporter.build(
    gx3["fb_name"], gx3["headers"], gx3["declarations"], gx3["code"]
)
(output_dir / "AND_01_GXWorks2.asc").write_text(asc, encoding="utf-8", newline="")
(output_dir / "AND_01_IEC61131_10.xml").write_text(xml, encoding="utf-8", newline="")

assert "FUNCTION_BLOCK FB_AND_01" in asc
assert "EXP(TRUE" in asc
assert "Not a safety or emergency-stop function" in asc
assert "IF Enable AND NOT Input_Range_Error THEN" in asc
assert "Fallback_Output_1" in asc
assert "Model_Version" in asc
assert 'FunctionBlock name="FB_AND_01"' in xml
assert "EXP(" in xml
assert "Not a safety or emergency-stop function" in xml
assert "Enable_Range_Check" in xml and "Invalid_Input_Number" in xml
assert "Range_Tolerance_Percent" in xml and "10.0" in xml
root = ET.fromstring(xml)
xml_namespace = {"iec": Iec61131XmlExporter.NAMESPACE}
xml_variables = root.findall(".//iec:Variable", xml_namespace)
name_column = gx3["headers"].index("Label Name")
comment_column = gx3["headers"].index("Comment")
expected_comments = {
    row[name_column]: row[comment_column]
    for row in gx3["declarations"]
    if row[comment_column].strip()
}
for variable_name, expected_comment in expected_comments.items():
    matching_variable = next(
        variable
        for variable in xml_variables
        if variable.get("name") == variable_name
    )
    assert matching_variable.findtext(
        "iec:Documentation", namespaces=xml_namespace
    ) == expected_comment.strip()
    assert [child.tag.rsplit("}", 1)[-1] for child in matching_variable][:2] == [
        "Documentation", "Type"
    ]
assert (
    root.find(
        ".//iec:Variable[@name='Enable']/iec:Documentation",
        xml_namespace,
    ).get(f"{{{Iec61131XmlExporter.XSI}}}type")
    == "SimpleText"
)
assert GxWorks3XmlExporter.VARIABLE_COMMENTS_NAME not in xml
assert gx2["operation_summary"]["multiplications"] == len(window.scene.network.get_connections())

def generated_with(options):
    return GxWorks2ExportGenerator(
        window.scene.network,
        input_mappings,
        output_mappings,
        project_name=project.stem,
        language_code="en",
        export_options=options,
    ).generate()

minimal = generated_with({
    "enable": False, "network_active": False, "range_check": False,
    "range_tolerance_input": False, "range_error": False,
    "invalid_input_number": False, "fallback": False,
    "hold_last_output": False,
})
minimal_names = {row[1] for row in minimal["declarations"]}
assert not {"Enable", "Network_Active", "Enable_Range_Check", "Fallback_Output_1"} & minimal_names
assert "IF Enable" not in minimal["code"]

enable_only = generated_with({
    "enable": True, "network_active": True, "range_check": False,
    "fallback": False, "hold_last_output": False,
})
enable_names = {row[1] for row in enable_only["declarations"]}
assert {"Enable", "Network_Active"} <= enable_names
assert "Fallback_Output_1" not in enable_names and "IF Enable THEN" in enable_only["code"]

range_internal = generated_with({
    "enable": False, "network_active": False, "range_check": True,
    "range_tolerance_input": False, "range_error": False,
    "invalid_input_number": False, "fallback": False,
})
range_names = {row[1] for row in range_internal["declarations"]}
assert "Input_Range_Error_Internal" in range_names and "Input_Range_Error" not in range_names
assert "VAR_CONSTANT" in {row[0] for row in range_internal["declarations"] if row[1] == "Range_Tolerance_Percent"}

fallback_direct = generated_with({
    "enable": True, "network_active": False, "range_check": False,
    "fallback": True, "hold_last_output": False,
})
assert "Hold_Last_Output" not in {row[1] for row in fallback_direct["declarations"]}
assert "Fallback_Output_1" in fallback_direct["code"]

def regenerate(options, model_version):
    data = GxWorks3ExportGenerator(
        window.scene.network,
        input_mappings,
        output_mappings,
        project_name=project.stem,
        language_code="en",
        model_version=model_version,
        export_options=options,
    ).generate()
    data["regenerate_export"] = regenerate
    data["export_options"] = dict(options)
    return data

gx3["regenerate_export"] = regenerate
gx3["export_options"] = {}
dialog = XmlExportDialog(gx3, language_code="en")
assert dialog.xml_editor.isReadOnly()
assert dialog.width() == 820 and dialog.minimumWidth() == 680
assert hasattr(dialog.settings_panel, "connections_info_button")
assert not hasattr(dialog.fb_preview_panel, "info_button")
assert dialog.settings_panel.options_toggle.isChecked()
assert not dialog.settings_panel.options_widget.isHidden()
assert dialog.fb_preview_panel.toggle.isChecked()
assert not dialog.fb_preview_panel.scroll.isHidden()
assert "Variables:" in dialog.technical_info_label.text()
assert "Effort:" in dialog.technical_info_label.text()
assert "Scaling:" in dialog.technical_info_label.text()
assert "<Project" in dialog.xml_editor.toPlainText()
assert 'FunctionBlock name="FB_AND_01"' in dialog.xml_editor.toPlainText()
dialog.fb_name_edit.setText("FB_XML_Renamed")
assert 'FunctionBlock name="FB_XML_Renamed"' in dialog.xml_editor.toPlainText()
assert not hasattr(dialog, "declaration_table")
dialog.settings_panel.range_check.click()
assert "Enable_Range_Check" not in dialog.xml_editor.toPlainText()
dialog.close()

gx2["regenerate_export"] = regenerate
gx2["export_options"] = {}
sps_dialog = SpsExportDialog(gx2, language_code="en")
assert sps_dialog.width() == 820 and sps_dialog.minimumWidth() == 680
assert sps_dialog.code_editor.isReadOnly()
assert sps_dialog.declaration_table.editTriggers() == sps_dialog.declaration_table.EditTrigger.NoEditTriggers
sps_dialog.settings_panel.enable.click()
assert "Enable" not in {row[1] for row in sps_dialog.declaration_rows()}
assert "IF Enable AND" not in sps_dialog.code_editor.toPlainText()
assert sps_dialog.fb_preview_panel.toggle.isChecked()
assert not sps_dialog.fb_preview_panel.scroll.isHidden()
sps_dialog.close()

neutral = Iec61131ExportGenerator(
    window.scene.network, input_mappings, output_mappings,
    project_name=project.stem, language_code="en",
).generate()
neutral_xml = Iec61131XmlExporter.build(
    neutral["fb_name"], neutral["headers"], neutral["declarations"], neutral["code"]
)
assert "Export format: IEC 61131-10 XML" in neutral_xml
assert "Mitsubishi" not in neutral_xml and "GX Works" not in neutral_xml
assert "EXP(" in neutral_xml and "EXP(TRUE" not in neutral_xml

gx3_xml_data = GxWorks3XmlExportGenerator(
    window.scene.network, input_mappings, output_mappings,
    project_name=project.stem, language_code="en",
).generate()
gx3_xml = GxWorks3XmlExporter.build(
    gx3_xml_data["fb_name"], gx3_xml_data["headers"],
    gx3_xml_data["declarations"], gx3_xml_data["code"],
)
gx3_xml_root = ET.fromstring(gx3_xml)
gx3_variables = gx3_xml_root.findall(".//iec:Variable", xml_namespace)
for variable_name, expected_comment in expected_comments.items():
    matching_variable = next(
        variable for variable in gx3_variables
        if variable.get("name") == variable_name
    )
    assert matching_variable.find("iec:Documentation", xml_namespace) is None
    assert matching_variable.findtext(
        "iec:AddData/iec:Data/iec:VariableComments/iec:Comment/iec:CommentText",
        namespaces=xml_namespace,
    ) == expected_comment.strip()
    assert matching_variable.find(
        "iec:AddData/iec:Data", xml_namespace
    ).get("name") == GxWorks3XmlExporter.VARIABLE_COMMENTS_NAME
    assert matching_variable.find(
        "iec:AddData/iec:Data/iec:VariableComments/iec:Comment", xml_namespace
    ).get("number") == "1"
assert gx3_xml_data["xml_profile"] == "gxworks3"
gx3_xml_data["regenerate_export"] = regenerate
gx3_xml_data["export_options"] = {}
gx3_xml_dialog = XmlExportDialog(gx3_xml_data, language_code="en")
assert "Mitsubishi GX Works3 XML" in gx3_xml_dialog.windowTitle()
assert GxWorks3XmlExporter.VARIABLE_COMMENTS_NAME in gx3_xml_dialog.xml_editor.toPlainText()
assert "<Documentation" not in gx3_xml_dialog.xml_editor.toPlainText()
gx3_xml_dialog.close()
print("TRAINED_EXPORT_OK", len(gx2["declarations"]), len(asc), len(xml))
window.close()
