# -------------------------------------------------------------------------------------------------
# Datei: _test_training_comparison.py
# Zweck: Prüft Vergleichskurven und deren Bedienung während des laufenden Trainings.
# Letzte Änderung: 05.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math
import unittest
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

from connection import Connection
from language import LanguageManager
from network import NeuralNetwork
from neuron import Neuron
from neurontype import NeuronType
from trainingcomparison import clipped_curve, normalized_curve
from trainingdataio import TrainingDataIO
from trainingdialog import TrainingDialog


class HistoryParent(QWidget):
    def __init__(self):
        super().__init__()
        self.training_history = [
            dict(run_id=i, timestamp="2026-08-19T10:28:58", completed_epochs=5000,
                 maximum_absolute_error=0.2814, training_data="Test",
                 curve_points=[[1, 0.2 + i / 100], [50, 0.08], [100, 0.03], [5000, 0.001]])
            for i in range(1, 13)
        ]

    def training_run_matches_active_data(self, entry):
        return entry.get("training_data") == "Test"


def make_dialog(language="de"):
    net = NeuralNetwork()
    first = Neuron(1, 0, 0, "Input")
    first.neuron_type = NeuronType.INPUT
    last = Neuron(2, 300, 0, "Output")
    last.neuron_type = NeuronType.OUTPUT
    net.add_neuron(first)
    net.add_neuron(last)
    net.add_connection(Connection(1, first, last, weight=0.1))
    document = TrainingDataIO.create_empty_document(1, 1, "Test")
    for column, neuron in zip(document["columns"], (first, last)):
        column["mapped_neuron_id"] = neuron.id
        column["mapped_neuron_name"] = neuron.name
    document["records"] = [[0., 0.], [1., 1.]] * 50
    parent = HistoryParent()
    dialog = TrainingDialog(net, document, parent=parent, language_manager=LanguageManager(language))
    dialog.set_next_training_run_id(20)
    return parent, dialog


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
            cls.app.setFont(QFont("Segoe UI", 9))

    def test_curve_validation_and_clipping(self):
        self.assertEqual(normalized_curve([[2, .2], [1, .1], [2, .3], [0, 0], [3, math.inf], None]), [(1, .1), (2, .3)])
        points = [(1, 1.), (101, .01), (10000, .001)]
        self.assertEqual(clipped_curve(points, 51), [(1, 1.), (51, .505)])
        self.assertAlmostEqual(clipped_curve(points, 51, True)[-1][1], .1)
        self.assertEqual(clipped_curve(points, 0), [])
        self.assertEqual(clipped_curve(points, 101)[-1], (101, .01))

    def test_localized_compact_selection_and_chart(self):
        for language in ("de", "en"):
            parent, dialog = make_dialog(language)
            before = deepcopy(parent.training_history)
            weights = [c.weight for c in dialog.network.get_connections()]
            dialog.current_run_id = 12
            dialog.resize(1180, 780)
            dialog.show()
            dialog.show_comparison_runs()
            self.app.processEvents()
            popup = dialog.comparison_popup
            self.assertEqual(popup.table.rowCount(), 11)
            self.assertLess(popup.width(), 430)
            self.assertFalse(dialog.comparison_button.font().bold())
            self.assertEqual(dialog.comparison_button.font().pointSize(), dialog.close_button.font().pointSize())
            self.assertFalse(popup.table.horizontalScrollBar().isVisible())
            self.assertTrue(popup.table.verticalScrollBar().isVisible())
            self.assertEqual(popup.table.item(0, 2).text(), "19.08.26")
            self.assertEqual(popup.table.item(0, 3).text(), "5.000" if language == "de" else "5,000")
            self.assertNotIn("training.comparison", dialog.comparison_button.text())
            self.assertNotIn("training.comparison", popup.table.horizontalHeaderItem(4).text())
            chart_height = dialog.error_chart.height()
            for row in (0, 1):
                popup.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(len(dialog.error_chart.comparison_runs), 2)
            popup.table.item(2, 0).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(len(dialog.error_chart.comparison_runs), 3)
            self.assertFalse(popup.table.item(3, 0).flags() & Qt.ItemFlag.ItemIsEnabled)
            popup.table.item(3, 0).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(popup.table.item(3, 0).checkState(), Qt.CheckState.Unchecked)
            self.assertEqual(len(dialog.error_chart.comparison_runs), 3)
            self.app.processEvents()
            self.assertEqual(dialog.error_chart.height(), chart_height)
            self.assertEqual(dialog.error_chart_controls_layout.indexOf(dialog.comparison_legend), 1)
            self.assertGreaterEqual(dialog.comparison_legend.width(), dialog.comparison_legend.sizeHint().width())
            self.assertFalse(dialog.comparison_legend.wordWrap())
            popup.table.item(2, 0).setCheckState(Qt.CheckState.Unchecked)
            self.assertTrue(popup.table.item(3, 0).flags() & Qt.ItemFlag.ItemIsEnabled)
            for epoch in range(1, 101):
                dialog.error_chart.add_point(epoch, .25 / (1 + epoch / 10))
            for mode in ("linear", "logarithmic"):
                dialog.error_chart.set_scale_mode(mode)
                self.assertFalse(dialog.error_chart.grab().isNull())
            self.assertEqual(before, parent.training_history)
            self.assertEqual(weights, [c.weight for c in dialog.network.get_connections()])
            selected = next(iter(dialog.comparison_run_ids))
            dialog.hide_comparison_run(str(selected))
            self.assertNotIn(selected, dialog.comparison_run_ids)
            self.assertEqual(len(dialog.error_chart.comparison_runs), 1)
            dialog.error_chart.clear()
            self.assertEqual(len(dialog.error_chart.comparison_runs), 1)
            popup.hide()
            dialog.hide()
            parent.hide()

    def test_selection_does_not_stop_training(self):
        parent, dialog = make_dialog()
        events = []
        timer = QTimer(dialog)

        def compare_during_training():
            if not dialog.is_training or dialog.processed_training_records < 1:
                return
            if not events:
                dialog.show_comparison_runs()
                dialog.comparison_popup.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
                events.append(dialog.processed_training_records)
            elif dialog.processed_training_records > events[0]:
                events.append(dialog.processed_training_records)
                dialog.comparison_popup.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
                dialog.comparison_popup.hide()
                timer.stop()

        timer.timeout.connect(compare_during_training)
        timer.start(1)
        dialog.initialize_network.setChecked(False)
        dialog.monitor_training_data.setChecked(False)
        dialog.execute_training(1000, False)
        timer.stop()
        self.assertGreaterEqual(len(events), 2)
        self.assertGreater(events[1], events[0])
        self.assertEqual(dialog.current_run_completed_epochs, 1000)
        self.assertFalse(dialog.stop_requested)
        dialog.hide()
        parent.hide()


if __name__ == "__main__":
    unittest.main()
