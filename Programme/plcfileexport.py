# -------------------------------------------------------------------------------------------------
# Datei: plcfileexport.py
# Zweck: Verpackt editierte SPS-Deklarationen und ST-Code als GX-Works2-ASC bzw. IEC-61131-10-XML.
# Letzte Änderung: 05.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from datetime import datetime
import re
from xml.etree import ElementTree as ET


def st_comment_text(value):
    """Entschärft Kommentargrenzen ausschließlich im ausgegebenen ST-Kommentar."""

    return str(value).replace("(*", "( *").replace("*)", "* )")


def _table_records(headers, rows):
    """Liefert Tabellenzeilen unabhängig von der sichtbaren Spaltenreihenfolge."""

    normalized = [str(header).strip().casefold() for header in headers]
    aliases = {
        "class": ("class",),
        "name": ("label name", "label-name", "name"),
        "type": ("data type", "datatype", "type"),
        "initial": ("initial value", "initialwert"),
        "constant": ("constant", "konstante"),
        "comment": ("comment", "kommentar"),
    }

    def column(field):
        for alias in aliases[field]:
            if alias in normalized:
                return normalized.index(alias)
        return None

    indices = {field: column(field) for field in aliases}
    records = []
    for row in rows:
        values = [str(value).strip() for value in row]

        def value(field):
            index = indices[field]
            return values[index] if index is not None and index < len(values) else ""

        name = value("name")
        if not name:
            continue
        records.append({
            "class": value("class").upper() or "VAR",
            "name": name,
            "type": value("type").upper() or "REAL",
            "initial": value("constant") or value("initial"),
            "comment": value("comment"),
        })
    return records


def _default_value(data_type):
    return "FALSE" if data_type.upper() in ("BOOL", "BIT") else "0.0"


def variable_summary(headers, rows):
    """Zählt die für den Export angelegten Variablengruppen."""

    records = _table_records(headers, rows)
    result = {"total": 0, "io": 0, "scaling": 0,
              "scaling_inputs": 0, "scaling_outputs": 0, "weights": 0,
              "biases": 0, "neurons": 0, "helpers": 0}
    scaled_inputs = set()
    scaled_outputs = set()
    for record in records:
        name = record["name"]
        bounds = re.search(r"ARRAY\s*\[\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\]", record["type"])
        element_count = max(0, int(bounds.group(2)) - int(bounds.group(1)) + 1) if bounds else 1
        result["total"] += element_count
        if record["class"] in ("VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT"):
            result["io"] += element_count
        if name.startswith("K_"):
            result["scaling"] += element_count
            match = re.fullmatch(r"K_(In|Out)_(.+)_(?:Min|Max|Mean|Std)", name)
            if match:
                (scaled_inputs if match.group(1) == "In" else scaled_outputs).add(
                    match.group(2)
                )
        elif name.startswith("W_"):
            result["weights"] += element_count
        elif name.startswith("B_"):
            result["biases"] += element_count
        elif name.startswith("N_"):
            result["neurons"] += element_count
        elif record["class"] == "VAR" or name == "EXP_Ergebnis":
            result["helpers"] += element_count
    result["scaling_inputs"] = len(scaled_inputs)
    result["scaling_outputs"] = len(scaled_outputs)
    return result


class GxWorks2AscExporter:
    """Erzeugt das von GX Works2 und GX Works3 lesbare GX-IEC-ASC-Format."""

    @classmethod
    def build(cls, fb_name, headers, rows, code):
        records = _table_records(headers, rows)
        sections = {
            "VAR_INPUT": [],
            "VAR_OUTPUT": [],
            "VAR_IN_OUT": [],
            "VAR": [],
        }
        for record in records:
            label_class = record["class"]
            section = label_class if label_class in sections else "VAR"
            sections[section].append(record)

        lines = [
            "(*SOFTCONTROL:        ",
            "  VERSION:7.00.03*)",
            f"FUNCTION_BLOCK {fb_name}",
            "(**)",
            "(**)",
        ]
        for section in ("VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR"):
            section_rows = sections[section]
            if not section_rows:
                continue
            lines.append(f"\t{section} ")
            for record in section_rows:
                data_type = "BOOL" if record["type"] == "BIT" else record["type"]
                initial = record["initial"] or _default_value(data_type)
                comment = (
                    f" (* {st_comment_text(record['comment'])} *)"
                    if record["comment"] else ""
                )
                lines.append(
                    f"\t\t{record['name']}: {data_type}:={initial};{comment}"
                )
            lines.append("\tEND_VAR")
        lines.extend([
            "'ST'",
            "BODY",
            str(code).rstrip(),
            "",
            "END_BODY",
            "END_FUNCTION_BLOCK",
            "",
        ])
        return "\r\n".join(lines)


class Iec61131XmlExporter:
    """Erzeugt herstellerneutrales IEC-61131-10-XML."""

    NAMESPACE = "www.iec.ch/public/TC65SC65BWG7TF10"
    XSI = "http://www.w3.org/2001/XMLSchema-instance"

    @classmethod
    def _add_variable(cls, parent, record, order=None):
        attributes = {"name": record["name"]}
        if order is not None:
            attributes["orderWithinParamSet"] = str(order)
        variable = ET.SubElement(parent, "Variable", attributes)
        comment = record["comment"].strip()
        if comment:
            documentation = ET.SubElement(
                variable,
                "Documentation",
                {f"{{{cls.XSI}}}type": "SimpleText"},
            )
            documentation.text = comment
        type_element = ET.SubElement(variable, "Type")
        type_name = "BOOL" if record["type"] == "BIT" else record["type"]
        ET.SubElement(type_element, "TypeName").text = type_name
        initial = record["initial"]
        if initial:
            initial_value = ET.SubElement(variable, "InitialValue")
            ET.SubElement(initial_value, "SimpleValue", {"value": initial})

    @classmethod
    def build(cls, fb_name, headers, rows, code):
        ET.register_namespace("", cls.NAMESPACE)
        ET.register_namespace("xsi", cls.XSI)
        root = ET.Element(
            f"{{{cls.NAMESPACE}}}Project",
            {
                f"{{{cls.XSI}}}schemaLocation": (
                    "www.iec.ch/public/TC65SC65BWG7TF10%20IEC61131_10_Ed1_0.xsd"
                ),
                "schemaVersion": "1.0",
            },
        )
        ET.SubElement(root, "FileHeader", {
            "companyName": "",
            "productName": "NeuronNetz",
            "productVersion": "",
        })
        ET.SubElement(root, "ContentHeader", {
            "name": fb_name,
            "creationDateTime": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        types = ET.SubElement(root, "Types")
        namespace = ET.SubElement(types, "GlobalNamespace")
        function_block = ET.SubElement(namespace, "FunctionBlock", {"name": fb_name})
        parameters = ET.SubElement(function_block, "Parameters")

        records = _table_records(headers, rows)
        parameter_order = 1
        local_records = []
        parameter_sections = {
            "VAR_INPUT": "InputVars",
            "VAR_OUTPUT": "OutputVars",
            "VAR_IN_OUT": "InoutVars",
        }
        for record in records:
            section_name = parameter_sections.get(record["class"])
            if section_name:
                section = ET.SubElement(parameters, section_name)
                cls._add_variable(section, record, parameter_order)
                parameter_order += 1
            else:
                local_records.append(record)

        for record in local_records:
            attributes = {"accessSpecifier": "private"}
            if "CONSTANT" in record["class"]:
                attributes["constant"] = "true"
            if "RETAIN" in record["class"]:
                attributes["retain"] = "true"
            section = ET.SubElement(function_block, "Vars", attributes)
            cls._add_variable(section, record)

        main_body = ET.SubElement(function_block, "MainBody")
        body_content = ET.SubElement(
            main_body,
            "BodyContent",
            {f"{{{cls.XSI}}}type": "ST"},
        )
        ET.SubElement(body_content, "ST").text = str(code).rstrip() + "\n"
        ET.SubElement(root, "Instances")
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


class GxWorks3XmlExporter(Iec61131XmlExporter):
    """Erzeugt IEC-61131-10-XML mit GX-Works3-kompatiblen Variablenkommentaren."""

    VARIABLE_COMMENTS_NAME = (
        "http://www.mitsubishielectric.com/xml/VariableComments"
    )

    @classmethod
    def _add_variable(cls, parent, record, order=None):
        attributes = {"name": record["name"]}
        if order is not None:
            attributes["orderWithinParamSet"] = str(order)
        variable = ET.SubElement(parent, "Variable", attributes)

        comment = record["comment"].strip()
        if comment:
            add_data = ET.SubElement(variable, "AddData")
            data = ET.SubElement(add_data, "Data", {
                "name": cls.VARIABLE_COMMENTS_NAME,
                "handleUnknown": "implementation",
            })
            variable_comments = ET.SubElement(data, "VariableComments")
            comment_element = ET.SubElement(
                variable_comments, "Comment", {"number": "1"}
            )
            ET.SubElement(comment_element, "CommentText").text = comment

        type_element = ET.SubElement(variable, "Type")
        type_name = "BOOL" if record["type"] == "BIT" else record["type"]
        ET.SubElement(type_element, "TypeName").text = type_name
        initial = record["initial"]
        if initial:
            initial_value = ET.SubElement(variable, "InitialValue")
            ET.SubElement(initial_value, "SimpleValue", {"value": initial})
