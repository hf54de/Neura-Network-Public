# -------------------------------------------------------------------------------------------------
# Datei: neurontype.py
# Zweck: Definiert die unterstützten Typen von Neuronen.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from enum import Enum


class NeuronType(Enum):
    """
    Definiert die möglichen Typen eines Neurons.
    """

    INPUT = "Input"
    HIDDEN = "Hidden"
    OUTPUT = "Output"