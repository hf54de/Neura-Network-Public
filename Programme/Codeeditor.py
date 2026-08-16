# -------------------------------------------------------------------------------------------------
# Datei: Codeeditor.py
# Zweck: Stellt den Editor und die Verarbeitung für benutzerdefinierten Python-Code bereit.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import json
import itertools
import random
import time
import tkinter as tk
from tkinter import filedialog, ttk


class ZiffernGeneratorMitInspektorUndLiveVorschau:

    def __init__(self, root):
        self.root = root
        self.root.title("Ziffern-Generator & Datensatz-Inspektor (.nndata)")
        self.root.configure(bg="#f2f2f2")
        self.root.resizable(False, False)

        self.rows = 5
        self.cols = 3

        # Die 10 perfekten Basis-Muster für das 3x5 Raster
        self.basis_muster = {
            0: [1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1],
            1: [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
            2: [1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1],
            3: [1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1],
            4: [1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 1],
            5: [1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1],
            6: [1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1],
            7: [1, 1, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
            8: [1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1],
            9: [1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1],
        }

        self.records = []
        self.current_index = 0
        self.preview_buttons = []

        self.setup_styles()
        self.setup_ui()

    def setup_styles(self):
        """Erstellt das Theme entsprechend dem gewünschten UI-Stil."""
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Globale Hintergründe & Schriften
        self.style.configure(".", background="#f2f2f2", font=("Segoe UI", 9))
        self.style.configure("TLabel", background="#f2f2f2", foreground="#111111")

        # Gruppenboxen (TLabelframe) mit feinem grauem Rahmen
        self.style.configure(
            "TLabelframe",
            background="#f2f2f2",
            bordercolor="#cccccc",
            lightcolor="#cccccc",
            darkcolor="#cccccc",
            borderwidth=1,
            relief="solid",
        )
        self.style.configure(
            "TLabelframe.Label",
            background="#f2f2f2",
            foreground="#333333",
            font=("Segoe UI", 9),
        )

        # --- DEZENTERE PRIMÄR-BUTTONS (Rot akzentuiert) ---
        self.style.configure(
            "Primary.TButton",
            font=("Segoe UI", 9, "bold"),
            foreground="#c62828",
            background="#ffffff",
            bordercolor="#e0e0e0",     # Sanfter, dezent grauer Standard-Rahmen
            lightcolor="#e0e0e0",
            darkcolor="#e0e0e0",
            borderwidth=1,
            relief="solid",
            padding=(8, 5),
            focusthickness=0,          # Verhindert das gestrichelte Fokus-Rechteck
        )
        self.style.map(
            "Primary.TButton",
            background=[("pressed", "#fbe9e7"), ("active", "#fff5f5"), ("disabled", "#f5f5f5")],
            bordercolor=[("active", "#e57373"), ("pressed", "#c62828"), ("disabled", "#e0e0e0")],
            lightcolor=[("active", "#e57373"), ("pressed", "#c62828"), ("disabled", "#e0e0e0")],
            darkcolor=[("active", "#e57373"), ("pressed", "#c62828"), ("disabled", "#e0e0e0")],
            foreground=[("disabled", "#b0b0b0")],
        )

        # --- SEKUNDÄR-BUTTONS (Neutral) ---
        self.style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 9),
            foreground="#333333",
            background="#ffffff",
            bordercolor="#cccccc",
            lightcolor="#cccccc",
            darkcolor="#cccccc",
            borderwidth=1,
            relief="solid",
            padding=(8, 4),
            focusthickness=0,
        )
        self.style.map(
            "Secondary.TButton",
            background=[("pressed", "#e0e0e0"), ("active", "#f5f5f5"), ("disabled", "#f8f8f8")],
            foreground=[("disabled", "#aaaaaa")],
        )

        # Eingabefeld
        self.style.configure(
            "TEntry",
            fieldbackground="#ffffff",
            bordercolor="#cccccc",
            lightcolor="#cccccc",
            darkcolor="#cccccc",
            padding=3,
        )

    def setup_ui(self):
        # --- LINKE SEITE: Raster ---
        grid_frame = ttk.LabelFrame(
            self.root, text=" Muster-Visualisierung ", padding=12
        )
        grid_frame.grid(row=0, column=0, padx=15, pady=15, sticky="n")

        for i in range(self.rows * self.cols):
            row = i // self.cols
            col = i % self.cols
            btn = tk.Canvas(
                grid_frame,
                width=32,
                height=32,
                bg="#ffffff",
                highlightthickness=1,
                highlightbackground="#d0d0d0",
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            self.preview_buttons.append(btn)

        # --- RECHTE SEITE: Steuerung ---
        control_frame = ttk.Frame(self.root)
        control_frame.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="n")

        # Schritt 1 Box
        step1_box = ttk.LabelFrame(control_frame, text=" SCHRITT 1: Generieren ", padding=10)
        step1_box.pack(fill="x", pady=(0, 10))

        ttk.Label(step1_box, text="Varianten pro Ziffer (0-9):").pack(anchor="w", pady=(0, 2))
        self.count_entry = ttk.Entry(step1_box, width=12, justify="center")
        self.count_entry.insert(0, "30")
        self.count_entry.pack(anchor="w", pady=(0, 8))

        ttk.Label(step1_box, text="Vorschau-Geschwindigkeit (Sek.):").pack(anchor="w", pady=(0, 2))
        self.speed_slider = tk.Scale(
            step1_box,
            from_=0.01,
            to=0.1,
            resolution=0.01,
            orient="horizontal",
            bg="#f2f2f2",
            bd=0,
            highlightthickness=0,
            troughcolor="#e0e0e0",
            activebackground="#c62828",
            length=220,
        )
        self.speed_slider.set(0.02)
        self.speed_slider.pack(anchor="w", pady=(0, 10))

        self.gen_button = ttk.Button(
            step1_box,
            text="Datensätze erzeugen",
            style="Primary.TButton",
            command=self.generate_data,
        )
        self.gen_button.pack(fill="x", pady=(0, 5))

        self.status_label = ttk.Label(
            step1_box, text="Bereit.", foreground="#666666"
        )
        self.status_label.pack(anchor="w")

        # --- BEREICH ZUM BLÄTTERN & SPEICHERN (Anfangs versteckt) ---
        self.inspect_frame = ttk.Frame(control_frame)

        # Schritt 2 Box
        step2_box = ttk.LabelFrame(self.inspect_frame, text=" SCHRITT 2: Kontrollieren ", padding=10)
        step2_box.pack(fill="x", pady=(0, 10))

        self.info_label = ttk.Label(
            step2_box, text="", font=("Segoe UI", 9, "bold"), foreground="#c62828"
        )
        self.info_label.pack(anchor="w", pady=(0, 8))

        nav_frame = ttk.Frame(step2_box)
        nav_frame.pack(fill="x")

        self.btn_prev = ttk.Button(
            nav_frame, text="◀ Zurück", style="Secondary.TButton", command=self.show_previous
        )
        self.btn_prev.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_next = ttk.Button(
            nav_frame, text="Vorwärts ▶", style="Secondary.TButton", command=self.show_next
        )
        self.btn_next.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Schritt 3 Box
        step3_box = ttk.LabelFrame(self.inspect_frame, text=" SCHRITT 3: Speichern ", padding=10)
        step3_box.pack(fill="x")

        self.save_button = ttk.Button(
            step3_box,
            text="Als .nndata speichern...",
            style="Primary.TButton",
            command=self.save_to_file,
        )
        self.save_button.pack(fill="x")

    def update_preview(self, muster):
        for idx, pixel in enumerate(muster):
            color = "#222222" if pixel == 1.0 else "#ffffff"
            self.preview_buttons[idx].config(bg=color)
        self.root.update()

    def show_record(self, index):
        if not self.records:
            return

        record = self.records[index]
        pixel_daten = record[:15]
        target_daten = record[15:]
        soll_ziffer = target_daten.index(1.0)

        self.update_preview(pixel_daten)
        self.info_label.config(
            text=f"Zeile {index + 1} von {len(self.records)}   |   Ziffer: {soll_ziffer}"
        )

        self.btn_prev.config(state="normal" if index > 0 else "disabled")
        self.btn_next.config(
            state="normal" if index < len(self.records) - 1 else "disabled"
        )

    def show_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.show_record(self.current_index)

    def show_next(self):
        if self.current_index < len(self.records) - 1:
            self.current_index += 1
            self.show_record(self.current_index)

    def build_unambiguous_variants(self):
        """
        Erzeugt alle Muster mit null bis zwei gekippten Pixeln und entfernt
        Varianten, die mehreren Ziffern zugeordnet werden könnten.

        Die zehn perfekten Grundmuster behalten immer ihre eigene Ziffer.
        Taucht ein solches Muster als beschädigte Variante einer anderen
        Ziffer auf, wird nur diese fremde Variante verworfen.
        """

        candidates = {}
        owners = {}
        perfect_owners = {
            tuple(pattern): digit
            for digit, pattern in self.basis_muster.items()
        }

        for digit, base_pattern in self.basis_muster.items():
            digit_candidates = set()

            for mutation_count in (0, 1, 2):
                for mutation_indices in itertools.combinations(
                    range(self.rows * self.cols),
                    mutation_count
                ):
                    variant = list(base_pattern)
                    for index in mutation_indices:
                        variant[index] = 1 - variant[index]
                    pattern = tuple(variant)
                    digit_candidates.add(pattern)
                    owners.setdefault(pattern, set()).add(digit)

            candidates[digit] = digit_candidates

        unambiguous = {}

        for digit, digit_candidates in candidates.items():
            perfect_pattern = tuple(self.basis_muster[digit])
            valid_patterns = [
                pattern
                for pattern in digit_candidates
                if (
                    perfect_owners.get(pattern, digit) == digit
                    and (
                        pattern in perfect_owners
                        or owners[pattern] == {digit}
                    )
                )
            ]
            valid_patterns.remove(perfect_pattern)
            valid_patterns.sort()
            unambiguous[digit] = [perfect_pattern, *valid_patterns]

        return unambiguous

    def generate_data(self):
        try:
            variants_per_digit = int(self.count_entry.get())
            if variants_per_digit < 1:
                raise ValueError
        except ValueError:
            self.status_label.config(text="Ungültige Anzahl!", foreground="#c62828")
            return

        available_variants = self.build_unambiguous_variants()

        insufficient_digits = [
            (digit, len(patterns))
            for digit, patterns in available_variants.items()
            if variants_per_digit > len(patterns)
        ]

        if insufficient_digits:
            maximum = min(
                count
                for _digit, count in insufficient_digits
            )
            self.status_label.config(
                text=(
                    "Zu viele Varianten. Konfliktfrei sind höchstens "
                    f"{maximum} Varianten pro Ziffer möglich."
                ),
                foreground="#c62828"
            )
            return

        self.records = []
        self.gen_button.config(state="disabled")
        delay = self.speed_slider.get()

        for digit in self.basis_muster:
            target_array = [0.0] * 10
            target_array[digit] = 1.0

            perfect_pattern = available_variants[digit][0]
            selected_patterns = [
                perfect_pattern,
                *random.sample(
                    available_variants[digit][1:],
                    variants_per_digit - 1
                )
            ]

            for v, pattern in enumerate(selected_patterns):
                current_input = [float(value) for value in pattern]

                self.status_label.config(
                    text=f"Erzeuge Ziffer {digit} ({v+1}/{variants_per_digit})...",
                    foreground="#111111",
                )
                self.update_preview(current_input)
                time.sleep(delay)

                record_row = current_input + target_array
                self.records.append(record_row)

        self.status_label.config(
            text=f"Fertig! {len(self.records)} Datensätze erzeugt.", foreground="#2e7d32"
        )
        self.gen_button.config(state="normal")

        self.inspect_frame.pack(fill="x")

        self.current_index = 0
        self.show_record(self.current_index)

    def build_columns_definition(self):
        columns = []
        neuron_id = 1

        # Inputs (Pixel 1 bis 15)
        for i in range(1, 16):
            columns.append(
                {
                    "name": f"Input {i}",
                    "unit": "",
                    "role": "input",
                    "data_type": "binary",
                    "mapped_neuron_id": neuron_id,
                    "mapped_neuron_name": f"Pixel E{i}",
                    "calibration": {
                        "mode": "none",
                        "source_min": 0.0,
                        "source_max": 1.0,
                        "mean": 0.0,
                        "stddev": 1.0,
                    },
                }
            )
            neuron_id += 1

        # Outputs (Ziffern 0 bis 9)
        for i in range(10):
            columns.append(
                {
                    "name": f"Output {i}",
                    "unit": "",
                    "role": "output",
                    "data_type": "binary",
                    "mapped_neuron_id": neuron_id,
                    "mapped_neuron_name": f"Ziffer Aus {i}",
                    "calibration": {
                        "mode": "none",
                        "source_min": 0.0,
                        "source_max": 1.0,
                        "mean": 0.0,
                        "stddev": 1.0,
                    },
                }
            )
            neuron_id += 1

        return columns

    def save_to_file(self):
        if not self.records:
            return

        filename = filedialog.asksaveasfilename(
            initialfile="ziffern_trainingsdaten.nndata",
            defaultextension=".nndata",
            filetypes=[("NNDATA Dateien", "*.nndata"), ("Alle Dateien", "*.*")],
            title="Speicherort für .nndata Trainingsdaten wählen",
        )

        if not filename:
            return

        output_data = {
            "version": 4,
            "name": "Ziffern Trainingsdaten 3x5",
            "columns": self.build_columns_definition(),
            "records": self.records,
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        kurzer_name = (
            filename.split("/")[-1]
            if "/" in filename
            else filename.split("\\")[-1]
        )
        self.status_label.config(
            text=f"Gespeichert als '{kurzer_name}'!", foreground="#2e7d32"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = ZiffernGeneratorMitInspektorUndLiveVorschau(root)
    root.mainloop()
