# -------------------------------------------------------------------------------------------------
# Datei: bitmustererzeugen.py
# Zweck: Erzeugt Trainingsdaten für konfigurierbare binäre Bitmuster.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import random

def generate_excel_ready_data(num_samples=100, sequence_length=8, pattern=[1, 0, 1, 1]):
    p_len = len(pattern)
    
    # Überschriften für Excel
    print("Bit_1\tBit_2\tBit_3\tBit_4\tBit_5\tBit_6\tBit_7\tBit_8\tLabel")
    
    for _ in range(num_samples):
        if random.random() > 0.5:
            # Positives Beispiel (Muster einbetten)
            seq = [random.randint(0, 1) for _ in range(sequence_length)]
            start_idx = random.randint(0, sequence_length - p_len)
            seq[start_idx:start_idx+p_len] = pattern
            label = 1
        else:
            # Negatives Beispiel (Zufall ohne das Muster)
            while True:
                seq = [random.randint(0, 1) for _ in range(sequence_length)]
                contains = any(seq[i:i+p_len] == pattern for i in range(sequence_length - p_len + 1))
                if not contains:
                    break
            label = 0
            
        # Wandelt die Liste in Text um, getrennt durch Tabulatoren (\t)
        row_str = "\t".join(map(str, seq)) + f"\t{label}"
        print(row_str)

# Generiert 50 Zeilen zum Testen (kannst du oben bei num_samples erhöhen)
generate_excel_ready_data(num_samples=50)