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
    def test_record_progress_without_live_monitoring(self):
        from unittest.mock import patch
        from itertools import count
        parent, dialog = make_dialog()
        dialog.monitor_training_data.setChecked(False)
        dialog.fast_mode.setChecked(True)
        dialog.records = [[0., 0.]] * 20
        dialog.processed_training_records = 0
        dialog.apply_record = lambda *args, **kwargs: {}
        dialog.network.train_step = lambda targets: None
        dialog.process_training_events = lambda: None
        dialog.calculate_dataset_metrics = lambda **kwargs: {}
        dialog.update_epoch_time_display = lambda elapsed: None
        messages = []
        dialog.result_status.textChanged.connect(messages.append)
        ticks = count(0, 0.1)
        with patch('trainingdialog.time.monotonic', side_effect=lambda: next(ticks)):
            dialog.train_epoch(2, 100)
        expected = lambda record: dialog.language.text(
            'training.status.progress', epoch=2, total_epochs=100,
            record=record, total_records=20)
        self.assertEqual(messages[0], expected(1))
        self.assertEqual(messages[-1], expected(20))
        self.assertEqual(messages, [expected(record) for record in range(1, 21)])
        self.app.processEvents()
        dialog.close()
        parent.close()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_numeric_metrics_follow_each_epoch_independently_of_curve(self):
        from trainingdialog import format_number
        for monitoring in (True, False):
            parent, dialog = make_dialog()
            dialog.monitor_training_data.setChecked(monitoring)
            dialog.confirm_target_ranges = lambda: True
            seen = []

            def epoch(number, total):
                if number > 1:
                    previous = number - 1
                    self.assertEqual(dialog.result_mse.text(), format_number(0.1 / previous))
                    self.assertEqual(dialog.result_max_error.text(), format_number(0.5 / previous))
                    self.assertEqual(dialog.result_epochs.text(), str(previous))
                dialog.error_metric_combo.setCurrentIndex(number % 2)
                seen.append(number)
                if number == 5:
                    dialog.stop_requested = True
                return dict(mean_squared_error=0.1 / number,
                            maximum_absolute_error=0.5 / number,
                            maximum_error_details=None)

            dialog.train_epoch = epoch
            dialog.execute_training(1000, False)
            self.assertEqual(seen, [1, 2, 3, 4, 5])
            self.assertEqual(dialog.result_mse.text(), format_number(0.02))
            self.assertEqual(dialog.result_max_error.text(), format_number(0.1))
            dialog.close()
            parent.close()
            from shiboken6 import delete
            delete(dialog)
            delete(parent)

    def test_live_characteristic_is_lazy_static_and_keeps_error_history(self):
        parent, dialog = make_dialog()
        dialog.show()
        characteristic_index = dialog.error_metric_combo.findData(
            "characteristic"
        )
        self.assertGreaterEqual(characteristic_index, 0)
        dialog.error_metric_combo.setCurrentIndex(characteristic_index)
        self.app.processEvents()

        plot = dialog.training_characteristic_plot
        self.assertFalse(plot.isHidden())
        self.assertTrue(dialog.error_chart.isHidden())
        self.assertEqual(len(plot.curve_points), 101)
        self.assertEqual(len(plot.data_points), 100)
        self.assertTrue(
            plot.testAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
        )
        self.assertTrue(dialog.training_characteristic_reference.isHidden())

        first_curve = list(plot.curve_points)
        dialog.network.get_connections()[0].weight = 0.75
        self.assertTrue(dialog.refresh_training_characteristic())
        self.assertNotEqual(first_curve, plot.curve_points)

        mse_index = dialog.error_metric_combo.findData("mse")
        dialog.error_metric_combo.setCurrentIndex(mse_index)
        unchanged_curve = list(plot.curve_points)
        dialog.network.get_connections()[0].weight = 0.25
        self.assertFalse(dialog.refresh_training_characteristic())
        self.assertEqual(unchanged_curve, plot.curve_points)

        dialog.error_metric_combo.setCurrentIndex(characteristic_index)
        dialog.confirm_target_ranges = lambda: True
        dialog.initialize_network.setChecked(False)
        dialog.train_epoch = lambda epoch, total: {
            "mean_squared_error": 0.1 / epoch,
            "maximum_absolute_error": 0.3 / epoch,
            "maximum_error_details": None,
        }
        dialog.execute_training(3, False)
        self.assertEqual(len(dialog.history_curve_points), 3)
        self.assertEqual(len(dialog.maximum_error_curve_points), 3)
        self.assertEqual(len(plot.curve_points), 101)

        dialog.close()
        parent.close()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_initialization_toggle_reflows_every_chart_view(self):
        parent, dialog = make_dialog()
        dialog.available_window_size = lambda: (1900, 1000)
        dialog.initialize_network.setChecked(False)
        dialog.resize_full_view()
        dialog.show()
        self.app.processEvents()
        collapsed_height = dialog.left_training_container.sizeHint().height()

        resize_calls = []
        original_resize = dialog.resize_full_view

        def tracked_resize(*args, **kwargs):
            resize_calls.append(True)
            return original_resize(*args, **kwargs)

        dialog.resize_full_view = tracked_resize
        dialog.initialize_network.setChecked(True)
        self.app.processEvents()
        self.app.processEvents()

        expanded_height = dialog.left_training_container.sizeHint().height()
        self.assertGreater(expanded_height, collapsed_height)
        self.assertTrue(resize_calls)
        self.assertEqual(
            dialog.error_chart_group.height(),
            dialog.left_training_container.height(),
        )
        self.assertLess(
            dialog.error_chart_group.geometry().bottom(),
            dialog.training_control_group.geometry().top(),
        )

        for metric in ("mse", "maximum", "characteristic"):
            dialog.error_metric_combo.setCurrentIndex(
                dialog.error_metric_combo.findData(metric)
            )
            self.app.processEvents()
            chart = (
                dialog.training_characteristic_plot
                if metric == "characteristic"
                else dialog.error_chart
            )
            self.assertLessEqual(
                chart.geometry().bottom(),
                dialog.error_chart_group.contentsRect().bottom(),
            )

        dialog.available_window_size = lambda: (1900, 700)
        dialog.resize_full_view()
        self.app.processEvents()
        self.assertEqual(
            dialog.error_chart_group.height(),
            dialog.left_training_container.height(),
        )
        self.assertGreaterEqual(
            dialog.training_control_group.geometry().top()
            - dialog.error_chart_group.geometry().bottom()
            - 1,
            dialog.content_layout.verticalSpacing(),
        )

        dialog.close()
        parent.close()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_plateau_warning_keeps_chart_filling_shared_row(self):
        parent, dialog = make_dialog()
        dialog.available_window_size = lambda: (1900, 700)
        dialog.resize_full_view()
        dialog.show()
        self.app.processEvents()
        height_before = dialog.height()

        dialog.set_plateau_warning_visible(True)
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(dialog.height(), height_before)
        self.assertEqual(
            dialog.error_chart_group.height(),
            dialog.left_training_container.height(),
        )
        self.assertLessEqual(
            dialog.error_chart_group.geometry().top()
            - dialog.result_group.geometry().bottom()
            - 1,
            dialog.content_layout.verticalSpacing(),
        )
        for metric in ('mse', 'maximum', 'characteristic'):
            dialog.error_metric_combo.setCurrentIndex(
                dialog.error_metric_combo.findData(metric)
            )
            self.app.processEvents()
            chart = (
                dialog.training_characteristic_plot
                if metric == 'characteristic'
                else dialog.error_chart
            )
            self.assertLessEqual(
                chart.geometry().bottom(),
                dialog.error_chart_group.contentsRect().bottom(),
            )
        self.assertLess(
            dialog.error_chart_group.geometry().bottom(),
            dialog.training_control_group.geometry().top(),
        )

        dialog.close()
        parent.close()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_plateau_warning_fills_shared_row_on_tall_window(self):
        parent, dialog = make_dialog()
        dialog.available_window_size = lambda: (1900, 1000)
        dialog.resize_full_view()
        dialog.show()
        self.app.processEvents()

        dialog.set_plateau_warning_visible(True)
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(
            dialog.error_chart_group.height(),
            dialog.left_training_container.height(),
        )
        self.assertLessEqual(
            dialog.error_chart_group.geometry().top()
            - dialog.result_group.geometry().bottom()
            - 1,
            dialog.content_layout.verticalSpacing(),
        )
        self.assertLessEqual(
            dialog.training_control_group.geometry().top()
            - dialog.error_chart_group.geometry().bottom()
            - 1,
            dialog.content_layout.verticalSpacing(),
        )

        dialog.close()
        parent.close()
        self.app.processEvents()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_xavier_plateau_hint_requires_zero_bias_and_tanh_or_sigmoid(self):
        parent, dialog = make_dialog()
        base_text = dialog.language.text("training.plateau_warning.text")
        hint_text = dialog.language.text(
            "training.plateau_warning.xavier_hint"
        )

        dialog.current_run_started_with_zero_biases = True
        dialog.update_plateau_warning_text()
        self.assertEqual(dialog.plateau_warning_label.text(), base_text)

        hidden = Neuron(3, 150, 0, "Hidden")
        hidden.neuron_type = NeuronType.HIDDEN
        hidden.activation_function = "Tanh"
        dialog.network.add_neuron(hidden)
        state = dialog.capture_training_state()
        self.assertTrue(dialog.training_state_uses_zero_biases(state))

        dialog.current_run_started_with_zero_biases = True
        dialog.update_plateau_warning_text()
        self.assertIn(hint_text, dialog.plateau_warning_label.text())

        hidden.bias = 0.1
        self.assertFalse(
            dialog.training_state_uses_zero_biases(
                dialog.capture_training_state()
            )
        )
        dialog.current_run_started_with_zero_biases = False
        dialog.update_plateau_warning_text()
        self.assertEqual(dialog.plateau_warning_label.text(), base_text)

        hidden.bias = 0.0
        hidden.activation_function = "ReLU"
        dialog.current_run_started_with_zero_biases = True
        dialog.update_plateau_warning_text()
        self.assertEqual(dialog.plateau_warning_label.text(), base_text)

        dialog.close()
        parent.close()
        self.app.processEvents()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_plateau_warning_is_not_blocked_below_quarter_maximum_error(self):
        parent, dialog = make_dialog()
        hidden = Neuron(3, 150, 0, "Hidden")
        hidden.neuron_type = NeuronType.HIDDEN
        hidden.activation_function = "Tanh"
        dialog.network.add_neuron(hidden)
        dialog.current_run_started_with_zero_biases = True
        dialog.error_limit.setValue(0.001)

        for epoch in range(1, 251):
            dialog.update_plateau_detection(epoch, 0.0075, 0.177)

        self.assertTrue(dialog.plateau_warning_detected)
        self.assertFalse(dialog.plateau_warning_container.isHidden())
        self.assertIn(
            dialog.language.text("training.plateau_warning.xavier_hint"),
            dialog.plateau_warning_label.text(),
        )

        dialog.close()
        parent.close()
        self.app.processEvents()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

    def test_bias_zero_is_described_as_standard(self):
        for language in ("de", "en"):
            manager = LanguageManager(language)
            label = manager.text("training.initialization.bias_zero")
            help_text = manager.text("training.info.initialization.text")
            self.assertIn(
                "Standard" if language == "de" else "standard",
                label,
            )
            self.assertIn("Xavier/Glorot", help_text)
            self.assertIn(
                "Neues Training mit gleicher Initialisierung"
                if language == "de"
                else "New training with same initialization",
                help_text,
            )

    def test_new_training_disables_monitoring_but_continue_keeps_it(self):
        parent, dialog = make_dialog()
        dialog.show()
        self.app.processEvents()
        calls = []
        dialog.execute_training = lambda *args, **kwargs: calls.append(
            (args, kwargs)
        )

        dialog.monitor_training_data.setChecked(True)
        dialog.start_selected_training()
        self.assertFalse(dialog.monitor_training_data.isChecked())
        self.assertEqual(len(calls), 1)

        dialog.monitor_training_data.setChecked(True)
        dialog.current_run_initial_state = {"compatible": True}
        dialog.training_state_is_compatible = lambda _state: True
        dialog.repeat_with_same_initialization()
        self.assertFalse(dialog.monitor_training_data.isChecked())
        self.assertEqual(len(calls), 2)

        dialog.monitor_training_data.setChecked(True)
        dialog.prepare_continuation_parameters = lambda: "continue"
        dialog.current_run_completed_epochs = 0
        dialog.maximum_epochs.setValue(10)
        dialog.continue_selected_training()
        self.assertTrue(dialog.monitor_training_data.isChecked())
        self.assertEqual(len(calls), 3)

        dialog.close()
        parent.close()
        self.app.processEvents()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)

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
            dialog.available_window_size = lambda: (1900, 1000)
            dialog.resize_full_view()
            dialog.resize(1180, dialog.height())
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
            self.assertEqual(
                dialog.error_chart_controls_layout.indexOf(dialog.comparison_legend),
                dialog.error_chart_controls_layout.indexOf(
                    dialog.comparison_full_length_checkbox
                ) + 1,
            )
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

    def test_complete_comparison_runs_control_epoch_axis(self):
        parent, dialog = make_dialog()
        dialog.show()
        for epoch in range(1, 101):
            dialog.error_chart.add_point(epoch, 0.2 / epoch)

        dialog.show_comparison_runs()
        popup = dialog.comparison_popup
        self.assertTrue(dialog.comparison_full_length_checkbox.isEnabled())
        dialog.comparison_full_length_checkbox.setChecked(True)
        self.assertTrue(dialog.comparison_full_length)
        self.assertEqual(dialog.error_chart.visible_epoch_limit(), 100)

        popup.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        popup.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(dialog.error_chart.visible_epoch_limit(), 5000)
        self.assertTrue(dialog.get_training_settings()["comparison_full_length"])

        dialog.comparison_full_length_checkbox.setChecked(False)
        self.assertEqual(dialog.error_chart.visible_epoch_limit(), 100)
        dialog.comparison_full_length_checkbox.setChecked(True)
        self.assertEqual(dialog.error_chart.visible_epoch_limit(), 5000)

        popup.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
        popup.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
        self.assertTrue(dialog.comparison_full_length_checkbox.isEnabled())
        self.assertEqual(dialog.error_chart.visible_epoch_limit(), 100)
        popup.hide()
        dialog.close()
        parent.close()
        self.app.processEvents()
        from shiboken6 import delete
        delete(dialog)
        delete(parent)


if __name__ == "__main__":
    unittest.main()
