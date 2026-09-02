# -------------------------------------------------------------------------------------------------
# Datei: gxworks3export.py
# Zweck: Passt Deklarationen und Structured Text an Mitsubishi GX Works3 an.
# Letzte Änderung: 02.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from gxworks2export import GxWorks2ExportGenerator


class GxWorks3ExportGenerator(GxWorks2ExportGenerator):
    """Verwendet die Netzberechnung von GX Works2 mit GX-Works3-Spaltenfolge."""

    def activation_lines(self, activation, sum_label, output_label):
        """Verwendet für GX Works3 die einargumentige IEC-EXP-Funktion."""

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
        export_data = super().generate()
        export_data["target_system"] = "Mitsubishi GX Works3"
        export_data["headers"] = (
            "Label Name", "Data Type", "Class", "Initial Value",
            "Constant", "Comment"
        )
        export_data["declarations"] = [
            [row[1], row[2], row[0], "", row[3], row[4]]
            for row in export_data["declarations"]
        ]
        export_data["declaration_hint_de"] = (
            "Vor dem Einfügen im GX-Works3-Label-Editor „Show Details“ aktivieren."
        )
        export_data["declaration_hint_en"] = (
            "Enable 'Show Details' in the GX Works3 label editor before pasting."
        )
        export_data["declaration_clipboard_format"] = "html_table"
        export_data["code"] = export_data["code"].replace(
            "Zielsystem: Mitsubishi GX Works2",
            "Zielsystem: Mitsubishi GX Works3",
            1,
        )
        return export_data
