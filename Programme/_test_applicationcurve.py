"""Focused application-curve and percentage regression tests (no project/settings writes)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import time
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from threading import Event
from unittest.mock import patch
from PySide6.QtCore import QMimeData, QPointF, QRectF, Qt, QEvent
from PySide6.QtWidgets import QApplication, QMenu, QDoubleSpinBox, QDialogButtonBox
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase, QFont, QColor, QHelpEvent, QImage, QPainter
from applicationcurve import sample_slice, clean_settings, CurveSettings, nice_ticks, tick_label, CurvePlot
from graphicalexperimentdialog import GraphicalExperimentDialog, calculate_forward_snapshot
from resultanalysisdialog import ResultAnalysisDialog
from trainingdataio import TrainingDataIO
from language import LanguageManager
from network import NeuralNetwork
from neuron import Neuron
from neurontype import NeuronType
from connection import Connection

ROOT = Path(__file__).resolve().parent
APP = QApplication.instance() or QApplication([])
APP.clipboard().setMimeData(QMimeData())
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
APP.setFont(QFont("Segoe UI", 9))

def lang(code):
    return LanguageManager(code, ROOT / "languages.json")

def build():
    net = NeuralNetwork(translator=lang("en").text)
    for i in (1, 2, 3):
        n = Neuron(i, i * 150, 0, f"N{i}")
        n.neuron_type = NeuronType.INPUT if i < 3 else NeuronType.OUTPUT
        n.activation_function = "Linear"
        n.bias = 1 if i == 3 else 0
        net.add_neuron(n)
    net.add_connection(Connection(1, net.get_neuron(1), net.get_neuron(3), 2))
    net.add_connection(Connection(2, net.get_neuron(2), net.get_neuron(3), 3))
    mappings = [dict(neuron=net.get_neuron(i), column_name=f"Channel {i}", column_index=i-1,
                     calibration=TrainingDataIO.default_calibration(), data_type="analog", unit="V")
                for i in (1, 2, 3)]
    return net, mappings

def drain(condition, seconds=5):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        APP.processEvents()
        QTest.qWait(5)
    assert condition(), "Background calculation did not finish"

def runtime(net):
    return [(n.input_value, n.output_value, n.sum_value, n.bias) for n in net.get_neurons()]

class CurveTests(unittest.TestCase):
    def test_nice_axis_ticks(self):
        import math
        low, high, ticks = nice_ticks(-28.9, 39.9, 7, expand=True)
        self.assertEqual((low, high), (-30, 40))
        self.assertEqual(ticks, [-30, -20, -10, 0, 10, 20, 30, 40])
        self.assertEqual(nice_ticks(-1.5, 3.6, 10)[2],
                         [-1.5, -1, -.5, 0, .5, 1, 1.5, 2, 2.5, 3, 3.5])
        for low, high in ((-1e-8, 3e-8), (-9000, -2000), (1e6, 9e6), (-1e-9, 1e-9)):
            for count in (2, 5, 10):
                a, b, ticks = nice_ticks(low, high, count, expand=True)
                self.assertLessEqual(a, low)
                self.assertGreaterEqual(b, high)
                self.assertGreater(len(ticks), 1)
                self.assertEqual(len(set(map(tick_label, ticks))), len(ticks))
                self.assertTrue(all(math.isclose(ticks[i+1]-ticks[i], ticks[1]-ticks[0], rel_tol=1e-8)
                                    for i in range(len(ticks)-1)))
        plot = CurvePlot(lambda de, en: de, {})
        plot.resize(730, 420)
        plot.points = [(x/10, (x/10)**5-4*(x/10)**4+2*(x/10)**3+2*(x/10)**2-5*x/10+3)
                       for x in range(-15, 37)]
        plot.x_label, plot.y_label = "Eingang N1", "Ausgang N10"
        plot.ensure_background()
        self.assertEqual(plot._range[:2], (-1.5, 3.6))
        self.assertTrue(all(plot._range[2] <= y <= plot._range[3] for x, y in plot.points))
        plot.grab().save(str(ROOT / ".change_baseline_curve_ticks_20261019" / "rounded_axes.png"))
        plot.deleteLater()

    def setUp(self):
        self.net, self.m = build()
        with patch.object(GraphicalExperimentDialog, "restore_window_geometry"):
            self.d = GraphicalExperimentDialog(self.net, self.m[:2], self.m[2:],
                [[-2, -2, -9], [2, 2, 11]], None, language_manager=lang("de"))
        drain(lambda: not self.d.forward_calculation_running and not self.d.calculation_timer.isActive())
        self.d.mode_combo.setCurrentIndex(self.d.mode_combo.findData("edit"))

    def tearDown(self):
        self.d.stop_forward_executor()
        drain(lambda: not self.d.curves.busy)
        self.d.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()

    def ready(self):
        drain(lambda: not self.d.curves.busy and not self.d.curves.pending and not self.d.curves.timer.isActive())

    def deliver_outputs(self):
        raw = self.d.current_input_values()
        internal = {m["neuron"].id: TrainingDataIO.scale_value(raw[m["neuron"].id], m["calibration"])
                    for m in self.m[:2]}
        _, values = calculate_forward_snapshot(self.d.forward_specification, internal)
        self.d.curves.update_outputs(values)
        return values

    def test_slice_is_correct_and_does_not_touch_network(self):
        before = runtime(self.net)
        p = self.d.curves.create()
        self.ready()
        self.assertEqual(runtime(self.net), before)
        self.assertEqual(len(p.widget().plot.points), 161)
        b = self.d.current_input_values()[2]
        for x, y in p.widget().plot.points:
            self.assertAlmostEqual(y, 2*x + 3*b + 1)
        x, y = p.widget().plot.point
        self.assertAlmostEqual(y, 2*x + 3*b + 1)
        original = p.widget().plot.points
        self.d.apply_saved_input_values({"1": 1., "2": b})
        self.deliver_outputs()
        self.ready()
        self.assertIs(p.widget().plot.points, original)
        self.assertEqual(p.widget().plot.point[0], 1.)
        self.d.apply_saved_input_values({"1": 1., "2": 1.})
        self.deliver_outputs()
        self.ready()
        self.assertIsNot(p.widget().plot.points, original)
        self.assertAlmostEqual(p.widget().plot.point[1], 6.)

    def test_continuous_marker_updates_reuse_curve_and_background(self):
        p = self.d.curves.create()
        self.ready()
        plot = p.widget().plot
        plot.grab()
        background = plot._background.cacheKey()
        curve = plot.points
        serial = self.d.curves.serial
        with patch("applicationcurve.sample_slice", wraps=sample_slice) as samples:
            for step in range(101):
                x = -1.5 + step*.03
                self.d.apply_saved_input_values({"1": x})
                self.deliver_outputs()
                self.assertAlmostEqual(plot.point[0], x)
                self.assertIs(plot.points, curve)
                self.assertIsNotNone(plot.point)
                plot.grab()
            self.ready()
            self.assertEqual(samples.call_count, 0)
        self.assertEqual(self.d.curves.serial, serial)
        self.assertEqual(plot._background.cacheKey(), background)

    def test_live_forward_updates_while_dragging(self):
        p = self.d.curves.create(); self.ready()
        self.d.mode_combo.setCurrentIndex(self.d.mode_combo.findData("experiment"))
        self.d.input_slider_pressed()
        seen = set()
        with patch("applicationcurve.sample_slice", wraps=sample_slice) as samples:
            for step in range(40):
                self.d.apply_saved_input_values({"1": -1.5+step*.075})
                self.d.input_state_changed()
                QTest.qWait(20)
                APP.processEvents()
                if p.widget().plot.point:
                    seen.add(round(p.widget().plot.point[0], 5))
            self.d.input_slider_released()
            drain(lambda: not self.d.forward_calculation_running and not self.d.calculation_timer.isActive())
            self.assertEqual(samples.call_count, 0)
        self.assertGreater(len(seen), 15)
        self.assertAlmostEqual(p.widget().plot.point[0], 1.425)
        print("LIVE_MARKER_UPDATES", len(seen), "during 40 input changes", flush=True)

    def test_pending_forward_request_does_not_starve_point(self):
        p = self.d.curves.create(); self.ready()
        self.d.forward_request_number = 20
        self.d.pending_forward_request = (20, {1: 1., 2: 0.})
        result = calculate_forward_snapshot(self.d.forward_specification, {1: .5, 2: 0.})
        with patch.object(self.d, "start_forward_calculation") as start:
            self.d.forward_calculation_finished(19, result, None)
            start.assert_called_once()
        self.assertEqual(p.widget().plot.point, (.5, 2.))

    def test_compact_plot_info_and_point_tooltip(self):
        self.m[0]["column_name"] = "N1"
        self.m[2]["column_name"] = "N3"
        p = self.d.curves.create(); self.ready()
        p.set_card_size(840, 400)
        plot = p.widget().plot
        plot.grab()
        self.assertLess(plot._box.top(), 15)
        self.assertLess(plot._box.left(), 60)
        self.assertLess(plot.width()-plot._box.right(), 25)
        self.assertNotIn("N1 – N1", plot.x_label)
        self.assertIn("Eingang N1", plot.x_label)
        position = plot.map_point(plot.point).toPoint()
        event = QHelpEvent(QEvent.Type.ToolTip, position, plot.mapToGlobal(position))
        with patch("applicationcurve.QToolTip.showText") as tip:
            APP.sendEvent(plot, event)
            self.assertTrue(tip.called)
            self.assertIn("Eingang N1", tip.call_args.args[1])
            self.assertIn("Ausgang N3", tip.call_args.args[1])
        self.assertIn("Ohne Sollwerte", plot.explanation())
        with patch("applicationcurve.QMessageBox.information") as info:
            plot.info_button.click()
            self.assertTrue(info.called)
        p.widget().grab().save(str(ROOT / ".change_baseline_curve_refinement_20261019" / "compact_plot.png"))

    def test_colors_and_removed_manual_ranges(self):
        settings = dict(input_id=1, output_id=3, x_auto=False, x_min=100, x_max=200,
                        y_auto=False, y_min=100, y_max=200)
        p = self.d.curves.create(dict(settings=settings)); self.ready()
        self.assertEqual(p.widget().plot.points[0][0], -2)
        for code in ("de", "en"):
            self.d.language = lang(code)
            dialog = CurveSettings(self.d, settings)
            self.assertEqual(dialog.findChildren(QDoubleSpinBox), [])
            buttons = dialog.findChild(QDialogButtonBox)
            self.assertEqual(buttons.button(QDialogButtonBox.StandardButton.Cancel).text(),
                             "Abbrechen" if code == "de" else "Cancel")
            for key, button in dialog.color_buttons.items():
                self.assertIn(dialog.values[key], button.styleSheet())
            button = dialog.color_buttons["curve"]
            with patch("applicationcurve.choose_color", return_value=QColor("#ffffff")):
                dialog.choose_color("curve", button)
            self.assertIn("color: #000000", button.styleSheet())
            with patch("applicationcurve.choose_color", return_value=QColor("#000000")):
                dialog.choose_color("curve", button)
            self.assertIn("color: #ffffff", button.styleSheet())
            dialog.accept()
            self.assertNotIn("x_min", dialog.values)
            dialog.grab().save(str(ROOT / ".change_baseline_curve_refinement_20261019" / ("settings_"+code+".png")))
            dialog.deleteLater()

    def test_zoom_buffer_resolution_and_marker_cache(self):
        proxy = self.d.curves.create(); self.ready()
        plot = proxy.widget().plot
        source = proxy.sceneBoundingRect()
        out = ROOT / ".change_baseline_curve_sharpness_20261019"
        out.mkdir(exist_ok=True)
        for zoom, dpr in ((.75, 1.), (1., 1.), (1.5, 1.), (2., 1.), (1.25, 2.)):
            image = QImage(round(source.width()*zoom*dpr), round(source.height()*zoom*dpr),
                           QImage.Format.Format_ARGB32_Premultiplied)
            image.setDevicePixelRatio(dpr)
            image.fill(QColor("white"))
            def render():
                painter = QPainter(image)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                self.d.scene.render(painter, QRectF(0, 0, source.width()*zoom, source.height()*zoom),
                                    source, Qt.AspectRatioMode.IgnoreAspectRatio)
                painter.end()
            render()
            self.assertAlmostEqual(plot._background.devicePixelRatio(), zoom*dpr, places=5)
            self.assertGreaterEqual(plot._background.width(), plot.width()*zoom*dpr)
            cached = plot._background.cacheKey()
            plot.set_point((.25, 1.5))
            render()
            self.assertEqual(plot._background.cacheKey(), cached)
            # Cosmetic vertical border remains a single solid pixel column.
            pixels = plot._background.toImage()
            y = round((plot._box.top()+plot._box.height()*.3)*zoom*dpr)
            x = round(plot._box.left()*zoom*dpr)
            dark = [pixels.pixelColor(i, y) for i in range(max(0,x-2), min(pixels.width(),x+3))]
            self.assertTrue(any(c.alpha() == 255 and c.red() < 100 for c in dark))
            image.save(str(out / f"zoom_{zoom}_dpr_{dpr}.png"))

    def test_binary_inputs_have_only_two_points(self):
        inputs = [dict(id=m["neuron"].id, calibration=m["calibration"]) for m in self.m[:2]]
        value = sample_slice(calculate_forward_snapshot, self.d.forward_specification, inputs,
            dict(id=3, calibration=self.m[2]["calibration"]), {1: 0., 2: 0.}, 1,
            (-2., 2.), True, Event())
        self.assertEqual([x for x, y in value[0]], [0., 1.])

    def test_raw_calibration_and_cancellation(self):
        inputs = [dict(id=1, calibration=dict(mode="minmax_minus1_1", source_min=-10, source_max=10)),
                  dict(id=2, calibration=TrainingDataIO.default_calibration())]
        output = dict(id=3, calibration=dict(mode="minmax_0_1", source_min=100, source_max=200))
        value = sample_slice(calculate_forward_snapshot, self.d.forward_specification, inputs, output,
                             {1: 5., 2: 0.}, 1, (-10., 10.), False, Event())
        self.assertAlmostEqual(value[1][1], 300.)
        cancel = Event(); cancel.set()
        self.assertIsNone(sample_slice(calculate_forward_snapshot, self.d.forward_specification,
            inputs, output, {1: 0., 2: 0.}, 1, (-10., 10.), False, cancel))

    def test_placement_copy_undo_redo_and_save_roundtrip(self):
        self.d.characteristic_action.trigger()
        self.assertEqual(len(self.d.placement_items), 1)
        self.d.finish_element_placement(QPointF(300, 200), Qt.KeyboardModifier.NoModifier)
        p = self.d.curves.proxies[0]
        self.d.begin_history_action()
        p.set_card_size(510, 350)
        p.widget().set_card_color("#eeeeff")
        p.widget().plot.settings.update(point="#aa00cc")
        self.d.finish_history_action()
        original = self.d.layout_state()["characteristics"]
        self.d.copy_selected_shapes()
        self.d.paste_clipboard_content(QPointF(700, 200))
        self.d.finish_element_placement(QPointF(700, 200), Qt.KeyboardModifier.NoModifier)
        self.assertEqual(len(self.d.curves.proxies), 2)
        self.d.undo_design_change()
        self.assertEqual(self.d.layout_state()["characteristics"], original)
        self.d.redo_design_change()
        self.assertEqual(len(self.d.curves.proxies), 2)
        state = self.d.capture_history_state()
        state["layout"] = json.loads(json.dumps(state["layout"]))
        self.d.apply_history_state(state)
        self.assertEqual(self.d.layout_state(), state["layout"])
        p = self.d.curves.proxies[0]
        self.d.remove_elements_from_design([p], confirm=False)
        self.assertEqual(len(self.d.layout_state()["characteristics"]), 1)
        self.d.undo_design_change()
        self.assertEqual(len(self.d.curves.proxies), 2)
        self.d.curves.add()
        self.d.cancel_element_placement()
        self.assertEqual(len(self.d.curves.proxies), 2)
        self.ready()

    def test_layout_file_and_invalid_saved_range(self):
        p = self.d.curves.create()
        p.setPos(120, 80)
        p.widget().plot.settings.update(input_id=2)
        expected = self.d.layout_state()["characteristics"]
        with tempfile.TemporaryDirectory(dir=ROOT / ".change_baseline_curve_refinement_20261019") as directory:
            self.d.layout_file = Path(directory) / "layout.json"
            self.assertTrue(self.d.save_layout())
            self.d.curves.restore([])
            self.d.load_layout()
            self.assertEqual(self.d.layout_state()["characteristics"], expected)
            self.d.layout_file = None
        self.d.curves.restore([dict(x="bad", y=float("nan"), settings=dict(input_id=1, output_id=3))])
        p = self.d.curves.proxies[0]
        self.assertEqual(p.x(), 0)
        self.assertEqual(p.y(), 0)
        self.m[0]["calibration"] = dict(mode="minmax_0_1", source_min=1, source_max=1)
        self.d.curves.refresh(); self.ready()
        self.assertIn("Eingabebereich", p.widget().plot.note)
        self.assertEqual(p.widget().plot.points, [])

    def test_lock_layers_context_and_old_layout(self):
        p, q = self.d.curves.create(), self.d.curves.create()
        p.setSelected(True)
        self.d.update_selection_actions()
        self.assertTrue(self.d.copy_shapes_action.isEnabled())
        p.set_locked(True)
        self.d.remove_elements_from_design([p], confirm=False)
        self.assertTrue(p.isVisible())
        p.set_locked(False)
        self.d.bring_elements_to_front([p])
        self.assertGreater(p.zValue(), q.zValue())
        self.d.send_elements_to_back([p])
        self.assertLess(p.zValue(), q.zValue())
        captured = []
        class TestMenu(QMenu):
            def exec(self, *args):
                captured.extend(a.text() for a in self.actions())
                return None
        with patch("graphicalexperimentdialog.QMenu", TestMenu):
            self.d.show_card_context_menu(p, self.d.pos())
        self.assertIn("Kennlinie einstellen…", captured)
        self.assertEqual(captured.count("Aus Gestaltung entfernen"), 1)
        state = self.d.capture_history_state()
        state["layout"].pop("characteristics")
        self.d.apply_history_state(state)
        self.assertEqual(self.d.curves.proxies, [])
        self.ready()

    def test_stale_requests_missing_mapping_and_close(self):
        p = self.d.curves.create()
        for value in (.1, .3, .8):
            self.d.apply_saved_input_values({"1": value, "2": .5})
            self.deliver_outputs()
        self.ready()
        self.assertAlmostEqual(p.widget().plot.point[0], .8)
        p.widget().plot.settings["input_id"] = 999
        self.d.curves.refresh(); self.ready()
        self.assertEqual(p.widget().plot.points, [])
        self.assertIn("fehlt", p.widget().plot.note)
        p.widget().plot.settings["input_id"] = 1
        self.d.curves.refresh(); self.d.curves.start()
        self.d.curves.close()
        drain(lambda: not self.d.curves.busy)

    def test_settings_and_render_in_both_languages(self):
        p = self.d.curves.create()
        self.ready()
        out = ROOT / ".change_baseline_curve_refinement_20261019"
        for code in ("de", "en"):
            self.d.language = lang(code)
            dialog = CurveSettings(self.d, p.widget().plot.settings)
            self.assertEqual(dialog.inputs.count(), 2)
            dialog.accept()
            self.assertEqual(dialog.values["input_id"], 1)
            p.widget().grab().save(str(out / ("characteristic_" + code + ".png")))
            dialog.deleteLater()
        self.assertNotIn("x_auto", clean_settings({"x_auto": False, "x_min": 5, "x_max": 2}))

class PercentageTests(unittest.TestCase):
    def test_percentages_and_translations(self):
        net, mappings = build()
        for code in ("de", "en"):
            d = ResultAnalysisDialog(net, [], language_manager=lang(code))
            self.assertEqual(d.percentage_texts(dict(target=-10., raw_absolute=2., display_range_percentage=5.)), ("20 %", "5 %"))
            self.assertEqual(d.percentage_texts(dict(target=0., raw_absolute=2., display_range_percentage=None)), ("—", "—"))
            self.assertEqual(d.percentage_texts(dict(is_binary=True)), ("—", "—"))
            self.assertEqual(d.percentage_texts(dict(target=1e-320, raw_absolute=1., display_range_percentage=None)), ("—", "—"))
            self.assertEqual(d.raw_range_percentage(2, dict(calibration=dict(mode="minmax_0_1", source_min=-10, source_max=30))), 5.)
            self.assertIsNone(d.raw_range_percentage(2, dict(calibration=dict(mode="none"))))
            self.assertIsNone(d.raw_range_percentage(2, dict(calibration=dict(mode="minmax_0_1", source_min=1, source_max=1))))
            self.assertNotIn("analysis.", d.output_table.horizontalHeaderItem(7).text())
            d.deleteLater()
        APP.processEvents()

    def test_table_values_width_and_binary_result(self):
        net, mappings = build()
        mappings[2]["calibration"] = dict(mode="minmax_0_1", source_min=-10, source_max=30)
        source = dict(label="Test", kind="test", inputs=mappings[:2], outputs=mappings[2:],
                      records=[[0., 0., 0.], [.1, .2, -10.]])
        for code in ("de", "en"):
            d = ResultAnalysisDialog(net, [source], language_manager=lang(code))
            d.resize(930, 720); d.show(); APP.processEvents()
            self.assertEqual(d.output_table.columnCount(), 9)
            self.assertEqual(d.deviations_table.columnCount(), 7)
            row = d.current_result["rows"][0]
            self.assertEqual(d.deviations_table.item(0, 5).text(), d.percentage_texts(row)[0])
            self.assertIn("%", d.deviations_table.item(0, 6).text())
            self.assertTrue(d.output_table.isColumnHidden(6))
            for width in (930, 1180, 900):
                d.resize(width, 720)
                APP.processEvents(); APP.processEvents()
                for table in (d.output_table, d.deviations_table):
                    self.assertEqual(table.horizontalHeader().length(), table.viewport().width())
                    for column in range(table.columnCount()):
                        if table.isColumnHidden(column):
                            continue
                        text = table.horizontalHeaderItem(column).text()
                        needed = max(table.horizontalHeader().fontMetrics().horizontalAdvance(line)
                                     for line in text.splitlines())
                        self.assertGreaterEqual(table.columnWidth(column), needed+8)
            d.resize(930, 720); APP.processEvents()
            d.grab().save(str(ROOT / ".change_baseline_curve_refinement_20261019" / ("percentages_" + code + ".png")))
            d.deleteLater(); APP.processEvents()
        mappings[2]["data_type"] = "binary"
        mappings[2]["calibration"] = TrainingDataIO.default_calibration()
        source["records"] = [[0., 0., 1.]]
        d = ResultAnalysisDialog(net, [source], language_manager=lang("en"))
        APP.processEvents()
        self.assertFalse(d.output_table.isColumnHidden(6))
        self.assertEqual(d.output_table.item(0, 7).text(), "—")
        d.deleteLater(); APP.processEvents()

if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    APP.processEvents()
    APP.clipboard().clear()
    raise SystemExit(0 if result.wasSuccessful() else 1)
