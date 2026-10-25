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
from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, QEvent
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

class ApplicationComparisonTests(unittest.TestCase):
    def test_characteristic_slider_uses_input_pipeline_and_mode(self):
        for code in ("de", "en"):
            net, mappings = build()
            net.remove_neuron(mappings[1]["neuron"])
            mappings[2]["column_index"] = 1
            with patch.object(GraphicalExperimentDialog, "restore_window_geometry"):
                d = GraphicalExperimentDialog(net, mappings[:1], mappings[2:],
                    [[-2., -3.], [0., 5.], [2., 13.]], None, language_manager=lang(code))
            try:
                def ready():
                    APP.processEvents()  # Start the queued final calculation after releasing the slider.
                    drain(lambda: not d.forward_calculation_running and not d.calculation_timer.isActive()
                          and not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
                ready()
                proxy = d.curves.create()
                second = d.curves.create()
                ready()
                plot, other = proxy.widget().plot, second.widget().plot
                controls = d.input_cards[0][1]
                self.assertFalse(d.edit_mode)
                self.assertTrue(plot.input_slider.isEnabled())
                self.assertEqual(plot.input_bounds, (-2., 2.))
                original_curve = plot.points
                before = ([n.bias for n in net.get_neurons()], [c.weight for c in net.get_connections()])
                plot.input_slider.setValue(7500)
                ready()
                self.assertEqual(controls["editor"].value(), 1.)
                self.assertEqual(controls["slider"].value(), 750)
                self.assertEqual(other.input_slider.value(), 7500)
                self.assertEqual(plot.point, (1., 3.))
                self.assertEqual(plot.target, 9.)
                self.assertIn("6,00" if code == "de" else "6.00", plot.deviation_text())
                self.assertIs(plot.points, original_curve)
                self.assertTrue(d.input_state_dirty)
                controls["editor"].setValue(-1.)
                ready()
                self.assertEqual(plot.input_slider.value(), 2500)
                self.assertEqual(other.input_slider.value(), 2500)
                self.assertEqual(plot.point, (-1., -1.))
                plot.input_slider.setValue(10000)
                ready()
                self.assertEqual((controls["editor"].value(), plot.point), (2., (2., 5.)))
                plot.input_slider.setValue(0)
                ready()
                self.assertEqual((controls["editor"].value(), plot.point), (-2., (-2., -3.)))
                plot.input_slider.sliderPressed.emit()
                self.assertEqual(d.active_input_sliders, 1)
                plot.input_slider.setValue(6000)
                plot.input_slider.sliderReleased.emit()
                ready()
                self.assertEqual(d.active_input_sliders, 0)
                self.assertAlmostEqual(controls["editor"].value(), .4)
                self.assertEqual(plot.input_slider.value(), 6000)
                d.mode_combo.setCurrentIndex(d.mode_combo.findData("edit"))
                APP.processEvents()
                self.assertFalse(plot.input_slider.isEnabled())
                plot.input_slider.setValue(9000)
                self.assertAlmostEqual(controls["editor"].value(), .4)
                d.mode_combo.setCurrentIndex(d.mode_combo.findData("experiment"))
                APP.processEvents()
                self.assertFalse(d.edit_mode)
                self.assertTrue(plot.input_slider.isEnabled())
                self.assertEqual(plot.input_slider.value(), 6000)
                ready()
                self.assertAlmostEqual(plot.point[0], .4)
                self.assertAlmostEqual(plot.point[1], 1.8)
                self.assertEqual(([n.bias for n in net.get_neurons()], [c.weight for c in net.get_connections()]), before)
                out = Path(os.environ.get("NEURONNETZ_CURVE_QA", tempfile.gettempdir()))
                for width, height in ((840, 400), (440, 300), (260, 200)):
                    proxy.set_card_size(width, height)
                    APP.processEvents()
                    plot.grab().save(str(out / f"curve_slider_{code}_{width}.png"))
                    self.assertLessEqual(plot.input_slider.geometry().bottom(), plot._box.top())
            finally:
                d.stop_forward_executor()
                drain(lambda: not d.curves.busy)
                d.deleteLater()
                APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                APP.processEvents()

    def test_information_dialog_stays_outside_graphics_scene(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog, QLabel, QPushButton
        for code in ("de", "en"):
            net, mappings = build()
            net.remove_neuron(mappings[1]["neuron"])
            mappings[2]["column_index"] = 1
            with patch.object(GraphicalExperimentDialog, "restore_window_geometry"):
                d = GraphicalExperimentDialog(net, mappings[:1], mappings[2:],
                    [[-2., -3.], [0., 5.], [2., 13.]], None, language_manager=lang(code))
            try:
                drain(lambda: not d.forward_calculation_running and not d.calculation_timer.isActive())
                proxy = d.curves.create()
                plot = proxy.widget().plot
                drain(lambda: not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
                d.resize(900, 700)
                d.show()
                view = d.scene.views()[0]
                view.fitInView(proxy, Qt.AspectRatioMode.KeepAspectRatio)
                APP.processEvents()
                scene_items = set(d.scene.items())
                geometry = proxy.geometry()
                bounds = d.scene.itemsBoundingRect()
                points = list(plot.points)
                state = runtime(net)
                observations = []
                def inspect_and_close():
                    modal = APP.activeModalWidget()
                    try:
                        self.assertIsInstance(modal, QDialog)
                        self.assertIs(modal.parentWidget(), d)
                        self.assertIsNone(modal.graphicsProxyWidget())
                        labels = [label for label in modal.findChildren(QLabel) if label.text() == plot.explanation()]
                        self.assertEqual(len(labels), 1)
                        self.assertIn("#fff8d8", labels[0].styleSheet())
                        self.assertTrue(labels[0].isVisible())
                        close = next(button for button in modal.findChildren(QPushButton)
                                     if button.text() == ("Schließen" if code == "de" else "Close"))
                        self.assertEqual(set(d.scene.items()), scene_items)
                        self.assertEqual(proxy.geometry(), geometry)
                        self.assertEqual(d.scene.itemsBoundingRect(), bounds)
                        out = Path(os.environ.get("NEURONNETZ_CURVE_QA", tempfile.gettempdir()))
                        modal.grab().save(str(out / f"curve_information_{code}.png"))
                        QTest.mouseClick(close, Qt.MouseButton.LeftButton)
                    except BaseException as error:
                        observations.append(error)
                        if modal is not None:
                            modal.reject()
                QTimer.singleShot(50, inspect_and_close)
                plot.info_button.click()
                APP.processEvents()
                if observations:
                    raise observations[0]
                self.assertIsNone(APP.activeModalWidget())
                self.assertTrue(proxy.isVisible())
                self.assertEqual(set(d.scene.items()), scene_items)
                self.assertEqual(proxy.geometry(), geometry)
                self.assertEqual(d.scene.itemsBoundingRect(), bounds)
                self.assertEqual(plot.points, points)
                self.assertEqual(runtime(net), state)
                out = Path(os.environ.get("NEURONNETZ_CURVE_QA", tempfile.gettempdir()))
                d.grab().save(str(out / f"curve_information_closed_{code}.png"))
            finally:
                d.stop_forward_executor()
                drain(lambda: not d.curves.busy)
                d.deleteLater()
                APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                APP.processEvents()

    def test_curve_has_no_target_colored_fill(self):
        plot = CurvePlot(lambda de, en: de, {})
        try:
            plot.resize(730, 420)
            plot.points = [(-2., 4.), (0., -2.), (2., 4.)]
            plot.set_targets([(-1., 3., 1), (1., 4., 2)])
            plot.ensure_background()
            image = plot._background.toImage()
            position = plot.map_point((0., 2.))
            self.assertNotEqual(image.pixelColor(round(position.x()), round(position.y())).name(), "#f4c430")
            target = plot.map_point((1., 4.))
            self.assertEqual(image.pixelColor(round(target.x()), round(target.y())).name(), "#f4c430")
        finally:
            plot.deleteLater()

    def test_targets_interpolation_and_live_prediction(self):
        for code in ("de", "en"):
            net, mappings = build()
            net.remove_neuron(mappings[1]["neuron"])
            mappings[2]["column_index"] = 1
            mappings[0]["column_name"] = "Position"
            mappings[0]["unit"] = "mm"
            records = [[-2., -3.], [0., 5.], [2., 13.]]
            with patch.object(GraphicalExperimentDialog, "restore_window_geometry"):
                d = GraphicalExperimentDialog(net, mappings[:1], mappings[2:], records,
                    None, language_manager=lang(code))
            try:
                drain(lambda: not d.forward_calculation_running and not d.calculation_timer.isActive())
                proxy = d.curves.create()
                plot = proxy.widget().plot
                drain(lambda: not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
                before = runtime(net)
                self.assertEqual(plot.target_points, [(-2., -3., 1), (0., 5., 2), (2., 13., 3)])
                d.curves.update_outputs({1: 0., 3: 1.})
                self.assertEqual((plot.point, plot.target, plot.target_record), ((0., 1.), 5., 2))
                plot.resize(900, 480)
                plot.ensure_background()
                background = plot._background
                curve = plot.points
                d.curves.update_outputs({1: 1., 3: 3.})
                self.assertEqual((plot.point, plot.target, plot.target_record), ((1., 3.), 9., None))
                self.assertEqual(plot.deviation_text(), "Position = 1,00 mm | Soll ≈ 9,00 V | Ist = 3,00 V | Abweichung ≈ 6,00 V" if code == "de"
                                 else "Position = 1.00 mm | Target ≈ 9.00 V | Actual = 3.00 V | Deviation ≈ 6.00 V")
                self.assertIn("geschätzt" if code == "de" else "Estimated target", plot.context)
                plot.ensure_background()
                self.assertIs(plot._background, background)
                self.assertIs(plot.points, curve)
                mappings[2]["unit"] = ""
                d.curves.refresh()
                self.assertEqual(plot.deviation_text(), "Position = 1,00 mm | Soll ≈ 9,00 | Ist = 3,00 | Abweichung ≈ 6,00" if code == "de"
                                 else "Position = 1.00 mm | Target ≈ 9.00 | Actual = 3.00 | Deviation ≈ 6.00")
                mappings[2]["unit"] = "mV"
                d.curves.refresh()
                self.assertEqual(plot.deviation_text().count(" mV"), 3)
                mappings[2]["unit"] = "V"
                d.curves.refresh()
                plot.ensure_background()
                self.assertTrue(plot._range[2] <= -3. <= 13. <= plot._range[3])
                out = Path(os.environ.get("NEURONNETZ_CURVE_QA", tempfile.gettempdir()))
                for width, height in ((900, 480), (440, 300), (260, 200)):
                    plot.resize(width, height)
                    self.assertTrue(plot.grab().save(str(out / f"application_comparison_{code}_{width}.png")))
                plot.show_targets.setChecked(False)
                plot.ensure_background()
                self.assertEqual(plot.target, 9.)
                d.curves.update_outputs({1: 3., 3: 7.})
                self.assertIsNone(plot.target)
                self.assertIn("Kein passender" if code == "de" else "No matching", plot.context)
                plot.set_targets([(0., 1., 1), (2., 3., 2), (2., 4., 3)])
                plot.set_point((1., 3.))
                self.assertIsNone(plot.target)  # Conflicting boundary: no interpolation.
                plot.set_targets([(0., 0., 1), (2., 4., 2)])
                plot.set_point((0., 1.))
                self.assertEqual(plot.target, 0.)
                self.assertEqual(plot.deviation_text(), "Position = 0,00 mm | Soll = 0,00 V | Ist = 1,00 V | Abweichung 1,00 V" if code == "de" else "Position = 0.00 mm | Target = 0.00 V | Actual = 1.00 V | Deviation 1.00 V")
                self.assertNotIn("inf", plot.context.lower())
                self.assertEqual(plot.comparison_at(2. + 1e-11), (4., 2))
                plot.set_targets([(0., -.03, 1), (2., -.03, 2)])
                plot.set_point((1., 2.37))
                self.assertEqual(plot.deviation_text(), "Position = 1,00 mm | Soll ≈ -0,03 V | Ist = 2,37 V | Abweichung ≈ 2,40 V" if code == "de" else "Position = 1.00 mm | Target ≈ -0.03 V | Actual = 2.37 V | Deviation ≈ 2.40 V")
                self.assertNotIn("%", plot.deviation_text())
                self.assertIn("8000 %", plot.context)
                self.assertIn("% vom Sollwert" if code == "de" else "% of target", plot.toolTip())
                self.assertIn("nahe null" if code == "de" else "near zero", plot.toolTip())
                self.assertEqual(runtime(net), before)
                self.assertEqual(d.curves.data(proxy)["settings"]["input_id"], 1)
                for mapping in (d.input_columns[0], d.output_columns[0]):
                    mapping["data_type"] = "binary"
                    d.curves.refresh({1: 0.})
                    self.assertFalse(proxy.isVisible())
                    self.assertTrue(d.curves.data(proxy)["visible"])
                    mapping["data_type"] = "analog"
                    d.curves.refresh({1: 0.})
                    drain(lambda: not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
                    self.assertTrue(proxy.isVisible())
                saved = d.curves.data(proxy)
                d.curves.restore([saved])
                drain(lambda: not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
                restored = d.curves.proxies[0].widget().plot
                self.assertEqual(restored.target_points, [(-2., -3., 1), (0., 5., 2), (2., 13., 3)])
                self.assertEqual(runtime(net), before)
            finally:
                d.stop_forward_executor()
                drain(lambda: not d.curves.busy)
                d.deleteLater()
                APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                APP.processEvents()


class ForwardWindowCharacteristicTests(unittest.TestCase):
    def settle(self, dialog):
        APP.processEvents()
        dialog.fit_window_to_content()
        APP.processEvents()

    def dispose(self, dialog):
        APP.processEvents()
        dialog.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()

    def test_toggle_slider_and_compact_height_in_both_languages(self):
        from forwardcalibrationdialog import ForwardCalibrationDialog
        for code in ("de", "en"):
            net, m = build()
            net.remove_neuron(m[1]["neuron"])
            m[2]["column_index"] = 1
            m[0]["column_name"], m[0]["unit"] = "Position", "mm"
            d = ForwardCalibrationDialog(net, m[:1], m[2:], [[-2., -3.], [0., 5.], [2., 13.]], language_manager=lang(code))
            try:
                d.show(); self.settle(d)
                base = d.height()
                self.assertLess(base, 420)
                self.assertFalse(d.characteristic_button.isHidden())
                self.assertTrue(d.characteristic_group.isHidden())
                bottom = d.output_scroll.mapTo(d, QPoint(0, d.output_scroll.height())).y()
                self.assertLess(d.status_label.mapTo(d, QPoint()).y()-bottom, 35)
                before = runtime(net)
                d.characteristic_button.click(); self.settle(d)
                plot = d.characteristic_plot
                self.assertGreater(d.height(), base+150)
                self.assertEqual(len(plot.points), 161)
                self.assertEqual(runtime(net), before)
                self.assertEqual((plot.point, plot.target), ((0., 1.), 5.))
                curve = plot.points
                plot.input_slider.setValue(7500)
                self.assertEqual(d.input_widgets[0]["input_widget"].value(), 1.)
                self.assertEqual((plot.point, plot.target), ((1., 3.), 9.))
                self.assertIn("1,00 mm" if code == "de" else "1.00 mm", plot.deviation_text())
                self.assertIs(plot.points, curve)
                d.input_widgets[0]["input_widget"].setValue(-1.)
                self.assertEqual(plot.point, (-1., -1.))
                self.assertEqual(plot.input_slider.value(), 2500)
                out = Path(os.environ.get("NEURONNETZ_CURVE_QA", tempfile.gettempdir()))
                d.grab().save(str(out / f"forward_characteristic_{code}.png"))
                d.characteristic_button.click(); self.settle(d)
                self.assertTrue(d.characteristic_group.isHidden())
                self.assertLessEqual(d.height(), base+2)
                with patch("forwardcalibrationdialog.sample_slice") as sample:
                    d.input_widgets[0]["input_widget"].setValue(1.)
                    sample.assert_not_called()
                d.characteristic_button.click(); self.settle(d)
                self.assertEqual(plot.point, (1., 3.))
                d.characteristic_button.click(); self.settle(d)
                d.grab().save(str(out / f"forward_compact_{code}.png"))
            finally:
                self.dispose(d)

    def test_unsupported_network_retains_binary_and_array_buttons(self):
        from forwardcalibrationdialog import ForwardCalibrationDialog
        for code in ("de", "en"):
            net, m = build()
            for mapping in m:
                mapping["data_type"] = "binary"
            d = ForwardCalibrationDialog(net, m[:2], m[2:], [[0., 0., 0.], [1., 1., 1.]],
                input_array=dict(columns=2, column_indices=[0, 1]), language_manager=lang(code))
            try:
                d.show(); self.settle(d)
                self.assertTrue(d.characteristic_button.isHidden())
                self.assertTrue(d.characteristic_group.isHidden())
                for button in (d.description_button, d.test_data_button, d.binary_view_button,
                               d.array_view_button, d.graphical_experiment_button):
                    self.assertTrue(button.isVisible())
                d.binary_view_button.click()
                self.assertTrue(d.experimental_binary_mode)
                d.array_view_button.click(); self.settle(d)
                self.assertTrue(d.array_view_active)
                self.assertTrue(d.array_group.isVisible())
                out = Path(os.environ.get("NEURONNETZ_CURVE_QA", tempfile.gettempdir()))
                d.grab().save(str(out / f"forward_binary_array_{code}.png"))
                d.array_view_button.click(); self.settle(d)
                self.assertTrue(d.input_scroll.isVisible())
            finally:
                self.dispose(d)

    def test_analog_output_selection_excludes_binary_outputs(self):
        from forwardcalibrationdialog import ForwardCalibrationDialog
        net, m = build()
        net.remove_neuron(m[1]["neuron"])
        m[2]["column_index"] = 1
        extra = []
        for identifier, kind in ((4, "binary"), (5, "analog")):
            n = Neuron(identifier, 0, 0, f"N{identifier}")
            n.neuron_type = NeuronType.OUTPUT
            n.activation_function = "Linear"
            n.bias = 2 if kind == "analog" else 0
            net.add_neuron(n)
            net.add_connection(Connection(identifier, m[0]["neuron"], n, -1. if kind == "analog" else .1))
            extra.append(dict(m[2], neuron=n, column_index=identifier-2, data_type=kind, unit="mA"))
        outputs = [extra[0], m[2], extra[1]]
        d = ForwardCalibrationDialog(net, m[:1], outputs, [[-2., -3., 0., 8.], [2., 13., 1., 4.]], language_manager=lang("de"))
        try:
            d.show(); self.settle(d)
            self.assertTrue(d.binary_view_button.isVisible())
            self.assertEqual(d.characteristic_output.count(), 2)
            self.assertEqual(d.characteristic_output.currentData(), 1)
            d.characteristic_button.click(); self.settle(d)
            d.characteristic_output.setCurrentIndex(d.characteristic_output.findData(2))
            d.input_widgets[0]["input_widget"].setValue(1.)
            self.assertEqual((d.characteristic_plot.point, d.characteristic_plot.target), ((1., 1.), 5.))
            self.assertEqual(d.characteristic_plot.output_unit, "mA")
        finally:
            self.dispose(d)
        for kind in ("binary", "analog"):
            m[0]["data_type"] = kind
            outputs[1]["data_type"] = "binary"
            outputs[2]["data_type"] = "binary"
            d = ForwardCalibrationDialog(net, m[:1], outputs, [[-2., -3., 0., 8.], [2., 13., 1., 4.]], language_manager=lang("de"))
            try:
                self.assertTrue(d.characteristic_button.isHidden())
            finally:
                self.dispose(d)


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
