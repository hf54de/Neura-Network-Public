# -------------------------------------------------------------------------------------------------
# Datei: topology.py
# Zweck: Analysiert Schichten, Reihenfolge und Struktur neuronaler Netzwerke.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from collections import deque

from neurontype import NeuronType


class NetworkTopology:
    """
    Analysiert die Graphstruktur eines neuronalen Netzwerkes.

    Zuständig für:
        - Ermittlung der Neuronentypen
        - Erreichbarkeitsanalyse
        - topologische Sortierung
        - Ermittlung topologischer Ebenen
        - Schleifenprüfung

    Nicht zuständig:
        - Verwaltung der Neuronen
        - Verwaltung der Verbindungen
        - Vorwärtsberechnung
        - Training
        - grafische Darstellung
    """

    def __init__(self, network):

        self.network = network

    def get_neurons(self):
        """
        Liefert alle Neuronen nach ID sortiert.
        """

        return self.network.get_neurons()

    def get_connections(self):
        """
        Liefert alle Verbindungen nach ID sortiert.
        """

        return self.network.get_connections()

    def get_input_neurons(self):
        """
        Liefert alle Input-Neuronen nach ID sortiert.
        """

        return [
            neuron
            for neuron in self.get_neurons()
            if neuron.neuron_type == NeuronType.INPUT
        ]

    def get_hidden_neurons(self):
        """
        Liefert alle Hidden-Neuronen nach ID sortiert.
        """

        return [
            neuron
            for neuron in self.get_neurons()
            if neuron.neuron_type == NeuronType.HIDDEN
        ]

    def get_output_neurons(self):
        """
        Liefert alle Output-Neuronen nach ID sortiert.
        """

        return [
            neuron
            for neuron in self.get_neurons()
            if neuron.neuron_type == NeuronType.OUTPUT
        ]

    def get_reachable_neurons(self, start_neurons=None):
        """
        Liefert alle Neuronen, die von den angegebenen
        Startneuronen aus erreichbar sind.

        Werden keine Startneuronen angegeben, beginnt
        die Suche bei allen Input-Neuronen.
        """

        if start_neurons is None:
            start_neurons = self.get_input_neurons()

        start_neurons = sorted(
            set(start_neurons),
            key=lambda neuron: neuron.id
        )

        reachable_neurons = set(
            start_neurons
        )

        pending_neurons = deque(
            start_neurons
        )

        while pending_neurons:
            neuron = pending_neurons.popleft()

            outgoing_connections = sorted(
                neuron.outgoing_connections,
                key=lambda connection: connection.id
            )

            for connection in outgoing_connections:
                target_neuron = connection.target_neuron

                if target_neuron in reachable_neurons:
                    continue

                reachable_neurons.add(
                    target_neuron
                )

                pending_neurons.append(
                    target_neuron
                )

        return reachable_neurons

    def get_topological_order(self):
        """
        Liefert die Neuronen in einer gültigen
        topologischen Berechnungsreihenfolge.

        Die Reihenfolge ist bei mehreren gleichzeitig
        berechenbaren Neuronen über deren ID eindeutig.

        Wirft ValueError, wenn das Netzwerk
        eine gerichtete Schleife enthält.
        """

        neurons = self.get_neurons()

        incoming_count = {
            neuron.id: 0
            for neuron in neurons
        }

        outgoing_targets = {
            neuron.id: []
            for neuron in neurons
        }

        for connection in self.get_connections():
            source_id = connection.source_neuron.id
            target_id = connection.target_neuron.id

            incoming_count[target_id] += 1

            outgoing_targets[source_id].append(
                connection.target_neuron
            )

        for source_id in outgoing_targets:
            outgoing_targets[source_id].sort(
                key=lambda neuron: neuron.id
            )

        ready_neurons = deque(
            sorted(
                (
                    neuron
                    for neuron in neurons
                    if incoming_count[neuron.id] == 0
                ),
                key=lambda neuron: neuron.id
            )
        )

        ordered_neurons = []

        while ready_neurons:
            neuron = ready_neurons.popleft()

            ordered_neurons.append(
                neuron
            )

            newly_ready_neurons = []

            for target_neuron in outgoing_targets[neuron.id]:
                incoming_count[target_neuron.id] -= 1

                if incoming_count[target_neuron.id] == 0:
                    newly_ready_neurons.append(
                        target_neuron
                    )

            if newly_ready_neurons:
                combined_neurons = list(
                    ready_neurons
                ) + newly_ready_neurons

                ready_neurons = deque(
                    sorted(
                        combined_neurons,
                        key=lambda item: item.id
                    )
                )

        if len(ordered_neurons) != len(neurons):
            raise ValueError(
                "Das Netzwerk enthält mindestens eine gerichtete Schleife."
            )

        return ordered_neurons

    def get_topological_layers(self):
        """
        Liefert die Neuronen gruppiert nach
        topologischen Ebenen.

        Ebene 0 enthält alle Neuronen ohne eingehende
        Verbindung. Jede weitere Ebene enthält Neuronen,
        deren Vorgänger vollständig in früheren Ebenen liegen.

        Wirft ValueError, wenn das Netzwerk
        eine gerichtete Schleife enthält.
        """

        neurons = self.get_neurons()

        incoming_count = {
            neuron.id: 0
            for neuron in neurons
        }

        outgoing_targets = {
            neuron.id: []
            for neuron in neurons
        }

        for connection in self.get_connections():
            source_id = connection.source_neuron.id
            target_id = connection.target_neuron.id

            incoming_count[target_id] += 1

            outgoing_targets[source_id].append(
                connection.target_neuron
            )

        for source_id in outgoing_targets:
            outgoing_targets[source_id].sort(
                key=lambda neuron: neuron.id
            )

        current_layer = sorted(
            (
                neuron
                for neuron in neurons
                if incoming_count[neuron.id] == 0
            ),
            key=lambda neuron: neuron.id
        )

        layers = []
        processed_count = 0

        while current_layer:
            layers.append(
                current_layer
            )

            processed_count += len(
                current_layer
            )

            next_layer_candidates = []

            for neuron in current_layer:
                for target_neuron in outgoing_targets[neuron.id]:
                    incoming_count[target_neuron.id] -= 1

                    if incoming_count[target_neuron.id] == 0:
                        next_layer_candidates.append(
                            target_neuron
                        )

            current_layer = sorted(
                next_layer_candidates,
                key=lambda neuron: neuron.id
            )

        if processed_count != len(neurons):
            raise ValueError(
                "Das Netzwerk enthält mindestens eine gerichtete Schleife."
            )

        return layers

    def has_cycles(self):
        """
        Prüft, ob das Netzwerk eine gerichtete Schleife enthält.
        """

        try:
            self.get_topological_order()
            return False

        except ValueError:
            return True

    def has_complete_input_output_path(self):
        """
        Prüft, ob mindestens ein vollständiger gerichteter
        Pfad von einem Input-Neuron zu einem Output-Neuron besteht.
        """

        reachable_neurons = self.get_reachable_neurons()

        return any(
            output_neuron in reachable_neurons
            for output_neuron in self.get_output_neurons()
        )
