"""Fixed-input analysis slices, target matching and UI regressions."""
import unittest
from unittest.mock import patch
from pathlib import Path
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from _test_applicationcurve import APP, build, lang, runtime
from resultanalysisdialog import ResultAnalysisDialog

ROOT = Path(__file__).resolve().parent
OUT = ROOT / ".change_baseline_interpolation_20261019"

class InteractiveCharacteristicTests(unittest.TestCase):
    def make_dialog(self, code="de", binary=False, keep_start=False):
        self.net, self.m = build()
        if binary:
            self.m[1]["data_type"] = "binary"
        self.source = dict(label="Training", kind="training", inputs=self.m[:2],
            outputs=self.m[2:], records=[[-2., 0., -3.], [0., 0., 1.], [2., 1., 8.]])
        self.before = runtime(self.net)
        self.d = ResultAnalysisDialog(self.net, [self.source], language_manager=lang(code))
        self.d.tabs.setCurrentWidget(self.d.characteristic_tab)
        self.d.show()
        APP.processEvents()
        if not keep_start:
            self.d.characteristic_value.setValue(0.)
            QTest.qWait(60)
        return self.d

    def tearDown(self):
        if hasattr(self, "d"):
            self.d.characteristic_marker_timer.stop()
            self.d.close()
            self.d.deleteLater()
            APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            APP.processEvents()

    def test_first_record_initializes_all_inputs_and_preserves_edits(self):
        d=self.make_dialog(keep_start=True)
        self.assertEqual(d.characteristic_values, {1:-2.,2:0.})
        self.assertEqual(d.characteristic_plot.reference_record,1)
        self.assertTrue(d.characteristic_plot.comparison_active)
        other=dict(self.source, label="Different", records=[[.3456789123,.73123456789,9.],[1.,.73123456789,7.],[2.,0.,0.]])
        d.sources.append(other)
        d.source_combo.addItem("Different",other)
        d.source_combo.setCurrentIndex(1)
        APP.processEvents()
        self.assertEqual(d.characteristic_values, {1:.3456789123,2:.73123456789})
        self.assertEqual(d.characteristic_plot.reference_point,(.3456789123,9.))
        self.assertIn("Abweichung",d.characteristic_context.text())
        curve=d.characteristic_plot.curve_points
        d.select_characteristic_record("training",2)
        QTest.qWait(60)
        self.assertEqual(d.characteristic_values,{1:1.,2:.73123456789})
        self.assertEqual(d.characteristic_plot.reference_point,(1.,7.))
        self.assertIs(d.characteristic_plot.curve_points,curve)
        d.characteristic_input_combo.setCurrentIndex(1)
        self.assertEqual(d.characteristic_values,{1:1.,2:.73123456789})
        d.refresh_characteristic()
        self.assertEqual(d.characteristic_values,{1:1.,2:.73123456789})
        self.assertEqual(runtime(self.net),self.before)

    def test_interpolation_matches_current_x_and_only_fixed_inputs(self):
        d=self.make_dialog()
        self.source["records"]=[[-2.,0.,0.],[2.,0.,8.],[0.,1.,100.]]
        d.characteristic_curve_key=d.characteristic_plot_key=None
        d.refresh_characteristic()
        curve=d.characteristic_plot.curve_points
        scale=d.characteristic_plot.base_view_range()
        for position in (0,2500,5000,7500,10000):
            d.characteristic_slider.setValue(position)
            QTest.qWait(60)
            x=-2+position/2500
            self.assertEqual(d.characteristic_values[2],0.)
            self.assertEqual(d.characteristic_plot.reference_point,(x,2*x+4))
            self.assertEqual(d.characteristic_plot.comparison_prediction,(x,2*x+1))
            self.assertEqual(d.characteristic_plot.operating_point,(x,2*x+1))
            self.assertEqual(d.characteristic_plot.base_view_range(),scale)
            self.assertIs(d.characteristic_plot.curve_points,curve)
            if position not in (0,10000):
                self.assertIn("geschätzt",d.characteristic_context.text())
                self.assertIn("3,00",d.characteristic_context.text())
            else:
                self.assertNotIn("geschätzt",d.characteristic_context.text())
        d.characteristic_slider.setValue(7500)
        QTest.qWait(60)
        d.resize(930,740)
        APP.processEvents()
        d.grab().save(str(OUT/"interpolation.png"))
        # Conflicting target values must not silently be averaged.
        self.source["records"].append([2.,0.,9.])
        d.characteristic_curve_key=d.characteristic_plot_key=None
        d.refresh_characteristic()
        self.assertIsNone(d.characteristic_plot.reference_point)
        # Binary class labels do not define fractional target classes.
        self.source["records"].pop()
        self.m[2]["data_type"]="binary"
        d.characteristic_curve_key=d.characteristic_plot_key=None
        d.refresh_characteristic()
        self.assertIsNone(d.characteristic_plot.reference_point)
        self.assertEqual(runtime(self.net),self.before)

    def test_slider_keeps_other_inputs_curve_scale_zoom_and_runtime(self):
        d=self.make_dialog()
        self.assertFalse(hasattr(d, "characteristic_compare"))
        self.assertTrue(d.characteristic_show_points.isChecked())
        self.assertEqual(d.characteristic_plot.operating_point, (0., 1.))
        self.source["records"] = [[i/13, 0., i/13+7] for i in range(-20,21)]
        self.source["records"].append([2.,1.,8.])
        d.characteristic_curve_key = d.characteristic_plot_key = None
        d.refresh_characteristic()
        points=d.characteristic_plot.curve_points
        scale=d.characteristic_plot.base_view_range()
        d.characteristic_plot.view_range=(-1., 1., -1., 3.)
        updates=[]
        with patch.object(d, "evaluate_characteristic", wraps=d.evaluate_characteristic) as evaluate:
            for i in range(40):
                d.characteristic_slider.setValue(i*250)
                QTest.qWait(60)
                updates.append(d.characteristic_plot.operating_point)
                self.assertEqual(d.characteristic_values[2], 0.)
                low,high=d.characteristic_input_range(self.source,self.m[0])
                self.assertAlmostEqual(d.characteristic_values[1],low+(high-low)*i/40,places=7)
                if d.characteristic_values[1] <= 20/13:
                    self.assertTrue(d.characteristic_plot.comparison_active)
                    self.assertEqual(d.characteristic_plot.reference_point[0],
                                     d.characteristic_plot.operating_point[0])
                    self.assertIn("Abweichung", d.characteristic_context.text())
                else:
                    self.assertIsNone(d.characteristic_plot.reference_point)
                self.assertEqual(d.characteristic_plot.base_view_range(), scale)
            self.assertLessEqual(evaluate.call_count, 80)
        self.assertGreater(len(set(updates)), 15)
        self.assertIs(d.characteristic_plot.curve_points, points)
        self.assertEqual(d.characteristic_plot.view_range, (-1.,1.,-1.,3.))
        self.assertEqual(runtime(self.net), self.before)

    def test_duplicate_targets_and_single_match(self):
        d=self.make_dialog()
        self.source["records"] = [[.123456789123,0.,4.], [.123456789123,0.,9.], [2.,1.,8.]]
        d.characteristic_curve_key = d.characteristic_plot_key = None
        d.refresh_characteristic()
        for pos in (1,0,1):
            d.select_characteristic_record("training",pos+1)
            QTest.qWait(60)
            self.assertEqual(d.characteristic_values[1], .123456789123)
            self.assertEqual(d.characteristic_values[2], 0.)
            self.assertEqual(d.characteristic_plot.reference_record, pos+1)
            self.assertEqual(d.characteristic_plot.reference_point[1], [4.,9.][pos])
        d.characteristic_editors[2].setValue(1.)
        self.assertEqual(d.characteristic_slider.maximum(),10000)
        curve=d.characteristic_plot.curve_points
        scale=d.characteristic_plot.base_view_range()
        for position in (0,2500,5000,7500,10000):
            d.characteristic_slider.setValue(position)
            QTest.qWait(60)
            if position == 10000:
                self.assertEqual(d.characteristic_plot.reference_point,(2.,8.))
            else:
                self.assertIsNone(d.characteristic_plot.reference_point)
            self.assertEqual(d.characteristic_values[2],1.)
            self.assertEqual(d.characteristic_plot.base_view_range(),scale)
            self.assertIs(d.characteristic_plot.curve_points,curve)
        self.assertEqual(d.characteristic_plot.reference_record,3)
        self.assertEqual(d.characteristic_values[2],1.)
        d.characteristic_editors[2].setValue(.5)
        self.assertEqual(d.characteristic_slider.maximum(),10000)
        d.characteristic_slider.setValue(5000)
        QTest.qWait(60)
        self.assertIsNone(d.characteristic_plot.reference_point)
        self.assertEqual(d.characteristic_values[2],.5)

    def test_matching_targets_gray_points_and_click_do_not_replace_inputs(self):
        d=self.make_dialog()
        self.assertEqual(d.characteristic_plot.data_point_records, [1,2])
        self.assertEqual(d.characteristic_plot.background_point_records, [3])
        self.assertEqual(d.characteristic_plot.reference_point, (0.,1.))
        self.assertIn("Abweichende",d.characteristic_plot.record_details[3])
        d.characteristic_plot.recordActivated.emit("training",3)
        self.assertEqual(d.characteristic_values, {1:0.,2:0.})
        self.assertIn("festen Werte bleiben",d.characteristic_context.text())
        d.characteristic_plot.recordActivated.emit("training",1)
        self.assertEqual(d.characteristic_values, {1:-2.,2:0.})
        self.assertEqual(d.characteristic_plot.reference_point, (-2.,-3.))
        d.characteristic_value.setValue(1.)
        QTest.qWait(30)
        self.assertEqual(d.characteristic_plot.operating_point, (1.,3.))
        self.assertIsNone(d.characteristic_plot.reference_point)
        self.assertIn("Kein Sollwert",d.characteristic_context.text())
        self.assertEqual(runtime(self.net), self.before)

    def test_error_two_decimals_zero_target_and_same_x_different_inputs(self):
        d=self.make_dialog()
        self.source["records"] = [[0.,0.,0.], [0.,1.,10.], [2.,0.,4.]]
        d.characteristic_curve_key = d.characteristic_plot_key = None
        d.refresh_characteristic()
        self.assertEqual(d.characteristic_plot.reference_point,(0.,0.))
        self.assertIn("— %",d.characteristic_context.text())
        d.characteristic_value.setValue(2.)
        QTest.qWait(30)
        self.assertIn("Soll 4,00 | Ist 5,00 | Abweichung 1,00 (25,00 %",d.characteristic_context.text())
        d.characteristic_value.setValue(0.)
        QTest.qWait(30)
        d.characteristic_other_button.click()
        d.characteristic_editors[2].setValue(1.)
        self.assertEqual(d.characteristic_plot.reference_point,(0.,10.))
        self.assertEqual(d.characteristic_plot.operating_point,(0.,4.))
        self.assertIn("60,00 %",d.characteristic_context.text())
        d.characteristic_value.setValue(.12345678)
        QTest.qWait(30)
        self.assertIn("0,12",d.characteristic_context.text())
        self.assertEqual(d.characteristic_values[1],.12345678)
        self.assertIsNone(d.characteristic_plot.reference_point)
        self.assertIn("Kein Sollwert",d.characteristic_context.text())
        d.resize(930,740)
        APP.processEvents()
        d.grab().save(str(OUT/"independent_error.png"))
        self.assertEqual(runtime(self.net),self.before)

    def test_scale_stable_even_with_targets_hidden_and_new_fixed_input(self):
        d=self.make_dialog()
        self.source["records"][0][2] = 50.
        d.characteristic_curve_key = d.characteristic_plot_key = None
        d.characteristic_show_points.setChecked(False)
        initial=d.characteristic_plot.base_view_range()
        self.assertGreater(initial[3],50.)
        for value in (-2.,-.5,0.,1.,2.):
            d.characteristic_value.setValue(value)
            QTest.qWait(60)
            self.assertEqual(d.characteristic_plot.base_view_range(),initial)
        d.characteristic_other_button.click()
        d.characteristic_editors[2].setValue(.5)
        self.assertEqual(d.characteristic_plot.operating_point,(2.,6.5))
        self.assertNotEqual(d.characteristic_plot.base_view_range(),initial)
        self.assertIsNone(d.characteristic_plot.reference_point)
        self.assertEqual(runtime(self.net),self.before)

    def test_calibration_and_binary_inputs_outputs(self):
        d=self.make_dialog("en",binary=True)
        self.assertEqual(d.output_combo.currentData(),3)
        self.assertTrue(d.output_combo.view().isRowHidden(0))
        self.assertEqual(d.characteristic_input_combo.count(),2)
        self.m[0]["calibration"]=dict(mode="minmax_0_1",source_min=100.,source_max=1100.)
        d.refresh_characteristic()
        d.characteristic_value.setValue(600.)
        QTest.qWait(30)
        self.assertEqual(d.characteristic_slider.value(),5000)
        self.assertEqual(d.characteristic_plot.operating_point,(600.,2.))
        d.characteristic_input_combo.setCurrentIndex(1)
        self.assertEqual(len(d.characteristic_plot.curve_points),2)
        d.characteristic_slider.setValue(1)
        QTest.qWait(30)
        self.assertEqual(d.characteristic_values[1],600.)
        self.assertEqual(d.characteristic_plot.operating_point,(1.,5.))
        self.assertEqual(runtime(self.net),self.before)

    def test_single_input_source_switch_and_rendering_both_languages(self):
        d=self.make_dialog()
        self.net.remove_neuron(self.m[1]["neuron"])
        other=dict(self.source,label="Test",kind="test",inputs=self.m[:1],
                   records=[[x/10,0.,(x/10)**3] for x in range(-20,21)])
        d.sources.append(other)
        d.source_combo.addItem("Test",other)
        d.source_combo.setCurrentIndex(1)
        APP.processEvents()
        self.assertFalse(d.characteristic_other_button.isVisible())
        self.assertEqual(len(d.characteristic_plot.data_points),41)
        self.assertEqual(d.characteristic_plot.background_points,[])
        d.characteristic_value.setValue(2.)
        QTest.qWait(30)
        self.assertEqual(d.characteristic_plot.reference_point,(2.,8.))
        for width in (760,930):
            d.resize(width,740)
            APP.processEvents()
            self.assertEqual(d.width(),width)
            d.grab().save(str(OUT/("fixed_de_"+str(width)+".png")))
        empty=dict(other,label="Empty",records=[])
        d.sources.append(empty)
        d.source_combo.blockSignals(True)
        d.source_combo.addItem("Empty",empty)
        d.source_combo.setCurrentIndex(2)
        d.source_combo.blockSignals(False)
        d.populate_characteristic_inputs()
        d.refresh_characteristic()
        self.assertFalse(d.characteristic_slider.isEnabled())
        self.assertIsNone(d.characteristic_plot.reference_point)
        self.tearDown()
        del self.d
        d=self.make_dialog("en")
        d.characteristic_other_button.click()
        d.resize(760,740)
        APP.processEvents()
        metrics=d.characteristic_plot.fontMetrics()
        items=d.characteristic_plot.legend_items()
        width=sum(32+metrics.horizontalAdvance(label) for kind,label in items)+18*(len(items)-1)
        self.assertLess(d.characteristic_plot.plot_rect().center().x()+width/2,d.characteristic_plot.width())
        d.grab().save(str(OUT/"fixed_en_multi.png"))
        self.assertEqual(d.characteristic_show_points.text(),"Show training points")

if __name__ == "__main__":
    result=unittest.main(verbosity=2,exit=False).result
    APP.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    APP.processEvents()
    APP.clipboard().clear()
    raise SystemExit(0 if result.wasSuccessful() else 1)
