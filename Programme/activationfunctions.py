# -------------------------------------------------------------------------------------------------
# Datei: activationfunctions.py
# Zweck: Definiert Aktivierungsfunktionen und ihre mathematischen Ableitungen.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import math


class ActivationFunctions:
    """
    Stellt Aktivierungsfunktionen und deren Ableitungen bereit.

    Zuständig für:
        - Linear
        - ReLU
        - Sigmoid
        - Tanh
        - Ableitungen für die spätere Backpropagation

    Nicht zuständig:
        - Verwaltung von Neuronen
        - Vorwärtsberechnung des gesamten Netzwerkes
        - Training
        - grafische Darstellung
    """

    @staticmethod
    def linear(value):
        """
        Lineare Aktivierungsfunktion.
        """

        return value

    @staticmethod
    def linear_derivative(value):
        """
        Ableitung der linearen Aktivierungsfunktion.
        """

        return 1.0

    @staticmethod
    def relu(value):
        """
        Rectified Linear Unit.
        """

        return max(
            0.0,
            value
        )

    @staticmethod
    def relu_derivative(value):
        """
        Ableitung der ReLU-Funktion.
        """

        if value > 0.0:
            return 1.0

        return 0.0

    @staticmethod
    def sigmoid(value):
        """
        Numerisch stabile Sigmoid-Funktion.
        """

        if value >= 0.0:
            exponential = math.exp(
                -value
            )

            return 1.0 / (
                1.0 + exponential
            )

        exponential = math.exp(
            value
        )

        return exponential / (
            1.0 + exponential
        )

    @classmethod
    def sigmoid_derivative(
        cls,
        value
    ):
        """
        Ableitung der Sigmoid-Funktion.

        Der übergebene Wert ist der Summenwert Σ
        vor Anwendung der Aktivierungsfunktion.
        """

        sigmoid_value = cls.sigmoid(
            value
        )

        return (
            sigmoid_value
            * (
                1.0
                - sigmoid_value
            )
        )

    @staticmethod
    def tanh(value):
        """
        Hyperbolischer Tangens.
        """

        return math.tanh(
            value
        )

    @staticmethod
    def tanh_derivative(value):
        """
        Ableitung der Tanh-Funktion.

        Der übergebene Wert ist der Summenwert Σ
        vor Anwendung der Aktivierungsfunktion.
        """

        tanh_value = math.tanh(
            value
        )

        return (
            1.0
            - tanh_value * tanh_value
        )

    @classmethod
    def apply(
        cls,
        activation_function,
        value
    ):
        """
        Wendet die angegebene Aktivierungsfunktion
        auf einen Wert an.
        """

        if activation_function == "Linear":
            return cls.linear(
                value
            )

        if activation_function == "ReLU":
            return cls.relu(
                value
            )

        if activation_function == "Sigmoid":
            return cls.sigmoid(
                value
            )

        if activation_function == "Tanh":
            return cls.tanh(
                value
            )

        raise ValueError(
            f"Unbekannte Aktivierungsfunktion: "
            f"{activation_function}"
        )

    @classmethod
    def derivative(
        cls,
        activation_function,
        value
    ):
        """
        Liefert die Ableitung der angegebenen
        Aktivierungsfunktion.

        Der übergebene Wert ist der Summenwert Σ
        vor Anwendung der Aktivierungsfunktion.
        """

        if activation_function == "Linear":
            return cls.linear_derivative(
                value
            )

        if activation_function == "ReLU":
            return cls.relu_derivative(
                value
            )

        if activation_function == "Sigmoid":
            return cls.sigmoid_derivative(
                value
            )

        if activation_function == "Tanh":
            return cls.tanh_derivative(
                value
            )

        raise ValueError(
            f"Unbekannte Aktivierungsfunktion: "
            f"{activation_function}"
        )
