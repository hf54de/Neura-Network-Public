# -------------------------------------------------------------------------------------------------
# Datei: iec61131export.py
# Zweck: Erzeugt herstellerneutralen IEC Structured Text für IEC-61131-10-XML.
# Letzte Änderung: 03.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from gxworks2export import GxWorks2ExportGenerator


class Iec61131ExportGenerator(GxWorks2ExportGenerator):
    """Neutraler IEC-ST-Generator ohne zielsystemspezifische Funktionsaufrufe."""

    def activation_lines(self, activation, sum_label, output_label):
        if activation == "Sigmoid":
            return [
                f"IF {sum_label} >= 0.0 THEN",
                f"    {self.exp_result_label} := EXP(-1.0 * {sum_label});",
                f"    {output_label} := 1.0 / (1.0 + {self.exp_result_label});",
                "ELSE",
                f"    {self.exp_result_label} := EXP({sum_label});",
                f"    {output_label} := {self.exp_result_label}",
                f"        / (1.0 + {self.exp_result_label});",
                "END_IF;",
            ]
        if activation == "Tanh":
            return [
                f"IF {sum_label} >= 0.0 THEN",
                f"    {self.exp_result_label} := EXP(-2.0 * {sum_label});",
                f"    {output_label} := (1.0 - {self.exp_result_label})",
                f"        / (1.0 + {self.exp_result_label});",
                "ELSE",
                f"    {self.exp_result_label} := EXP(2.0 * {sum_label});",
                f"    {output_label} := ({self.exp_result_label} - 1.0)",
                f"        / ({self.exp_result_label} + 1.0);",
                "END_IF;",
            ]
        return super().activation_lines(activation, sum_label, output_label)

    def generate(self):
        data = super().generate()
        data["target_system"] = "IEC 61131-10 XML"
        data["code"] = data["code"].replace(
            "    Zielsystem: Mitsubishi GX Works2",
            self.text(
                "    Exportformat: IEC 61131-10 XML",
                "    Export format: IEC 61131-10 XML",
            ),
            1,
        )
        data["complete_export_format"] = "iec61131_10_xml"
        data["complete_export_label_de"] = (
            "Vollständige IEC-61131-10-XML-Datei speichern…"
        )
        data["complete_export_label_en"] = (
            "Save complete IEC 61131-10 XML file…"
        )
        return data
