# -------------------------------------------------------------------------------------------------
# Datei: _test_error_metrics.py
# Zweck: Prüft Fehlerumschaltung, Altbestände und unveränderte Trainingsergebnisse.
# Letzte Änderung: 05.09.2026
# -------------------------------------------------------------------------------------------------
import ast
import importlib.util
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import _test_training_comparison as comparisons
from _test_training_comparison import make_dialog
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGraphicsScene
from projectio import ProjectIO
from traininghistorydialog import TrainingHistoryDialog

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "build" / "metric_baseline"


class MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        comparisons.ComparisonTests.setUpClass()
        cls.app = comparisons.ComparisonTests.app

    def test_comparison_selection_survives_metric_switch(self):
        parent, dialog = make_dialog()
        dialog.show()
        self.app.processEvents()
        parent.training_history[0]["maximum_error_curve_points"] = [[1, .9], [50, .3]]
        dialog.refresh_comparison_runs()
        dialog.apply_comparison_selection({1, 2})
        original = deepcopy(dialog.error_chart.comparison_runs)
        dialog.error_metric_combo.setCurrentIndex(1)
        self.assertEqual(dialog.comparison_run_ids, {1, 2})
        self.assertEqual(dict(dialog.error_chart.comparison_runs)[1], [(1, .9), (50, .3)])
        self.assertEqual(dict(dialog.error_chart.comparison_runs)[2], [])
        self.assertIn(dialog.language.text("training.metric.unavailable"), dialog.comparison_legend.toolTip())
        dialog.error_metric_combo.setCurrentIndex(0)
        self.assertEqual(dialog.error_chart.comparison_runs, original)
        self.app.processEvents()
        dialog.close()
        parent.close()

    def test_training_and_legacy_continuation(self):
        parent, dialog = make_dialog()
        results = []
        dialog.training_completed.connect(results.append)
        dialog.initialize_network.setChecked(False)
        dialog.execute_training(25, False, shuffle_seed=42)
        self.assertEqual(len(results[-1]["maximum_error_curve_points"]), 25)
        self.assertEqual(results[-1]["maximum_error_curve_points"][-1][1], results[-1]["maximum_absolute_error"])
        old = deepcopy(results[-1])
        del old["maximum_error_curve_points"]
        dialog.show_restored_training_run(old)
        self.assertEqual(dialog.maximum_error_curve_points, [])
        dialog.error_metric_combo.setCurrentIndex(1)
        dialog.error_chart.grab()
        self.assertEqual(dialog.maximum_error_curve_points, [])
        dialog.execute_training(3, False, continue_existing=True)
        self.assertEqual([p[0] for p in results[-1]["maximum_error_curve_points"]], [26, 27, 28])
        self.assertEqual(results[-1]["curve_points"][:25], old["curve_points"])
        dialog.execute_training(2, False, shuffle_seed=42)
        self.assertEqual([p[0] for p in results[-1]["maximum_error_curve_points"]], [1, 2])
        dialog.close()
        parent.close()

    def test_old_projects_and_roundtrip(self):
        projects = list((ROOT / "dist").rglob("*.nnproj"))
        self.assertTrue(projects)
        history = None
        for path in projects:
            data = ProjectIO.load_project(str(path))
            if data.get("training_history"):
                history = deepcopy(data["training_history"])
        self.assertIsNotNone(history)
        history[0]["maximum_error_curve_points"] = [[1, .8], [2, .5]]
        with tempfile.TemporaryDirectory(prefix="nn_metrics_") as folder:
            path = str(Path(folder) / "roundtrip.nnproj")
            scene = QGraphicsScene()
            ProjectIO.save_project(path, scene, training_history=history)
            loaded = ProjectIO.load_project(path)
            self.assertEqual(loaded["training_history"], history)
        broken = deepcopy(history)
        broken[0]["maximum_error_curve_points"] = [[2, .5], [1, .2]]
        with self.assertRaises(ValueError):
            ProjectIO._validate_training_history_data(broken)
        for language in ("de", "en"):
            parent, training = make_dialog(language)
            records = [deepcopy(history[0]), deepcopy(history[0])]
            records[1].pop("maximum_error_curve_points", None)
            records[1]["run_id"] = records[0]["run_id"] + 1
            window = TrainingHistoryDialog(records, language_manager=training.language)
            window.show()
            self.app.processEvents()
            if (BASE / "traininghistorydialog.py").exists():
                spec = importlib.util.spec_from_file_location("baseline_history", BASE / "traininghistorydialog.py")
                baseline_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(baseline_module)
                baseline_window = baseline_module.TrainingHistoryDialog(records, language_manager=training.language)
                baseline_window.show()
                self.app.processEvents()
                self.assertLessEqual(window.width(), baseline_window.width())
                self.assertEqual(window.height(), baseline_window.height())
                self.assertGreaterEqual(window.chart.height(), baseline_window.chart.height())
                baseline_window.close()
            window.table.selectAll()
            selected = [i.row() for i in window.table.selectionModel().selectedRows()]
            window.metric_combo.setCurrentIndex(1)
            self.assertEqual([i.row() for i in window.table.selectionModel().selectedRows()], selected)
            self.assertIn(training.language.text("training.metric.unavailable"), [window.table.item(r, 0).toolTip() for r in range(2)])
            self.assertEqual(len(window.chart.runs), 2)
            window.grab().save(str(ROOT / "build" / f"history_maximum_{language}.png"))
            window.scale_combo.setCurrentIndex(1)
            window.chart.grab()
            window.close()
            training.close()
            parent.close()
        print(f"Loaded {len(projects)} existing projects; optional curve roundtrip passed.")

    @unittest.skipUnless((BASE / "trainingdialog.py").exists(), "Local pre-change snapshot unavailable")
    def test_exact_baseline_results_and_geometry(self):
        spec = importlib.util.spec_from_file_location("metric_baseline_dialog", BASE / "trainingdialog.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for filename in ("trainer.py", "network.py"):
            self.assertEqual((ROOT / filename).read_bytes(), (BASE / filename).read_bytes())
        def methods(path):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            return {n.name: ast.dump(n) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        before = methods(BASE / "trainingdialog.py")
        after = methods(ROOT / "trainingdialog.py")
        for name in ("train_epoch", "calculate_dataset_metrics", "initialize_network_parameters"):
            if name in before:
                self.assertEqual(before[name], after[name], name)
        p1, new = make_dialog()
        p2, fixture = make_dialog()
        old = module.TrainingDialog(fixture.network, fixture.training_document, parent=p2, language_manager=fixture.language)
        runs = []
        dimensions = []
        switches = []
        timer = QTimer(new)
        def switch():
            if new.is_training:
                new.error_metric_combo.setCurrentIndex(1 - new.error_metric_combo.currentIndex())
                switches.append(new.processed_training_records)
        timer.timeout.connect(switch)
        for dialog in (old, new):
            result = []
            dialog.training_completed.connect(result.append)
            dialog.initialize_network.setChecked(False)
            dialog.momentum.setValue(.3)
            dialog.resize(1180, 780)
            dialog.show()
            self.app.processEvents()
            dimensions.append((dialog.width(), dialog.height(), dialog.error_chart.height()))
            if dialog is new:
                timer.start(1)
            dialog.execute_training(1000, False, shuffle_seed=42)
            timer.stop()
            runs.append((dialog.capture_training_state(), result[-1]))
            dialog.hide()
        self.assertTrue(switches)
        self.assertEqual(runs[0][0], runs[1][0])
        for key in ("mean_squared_error", "maximum_absolute_error", "completed_epochs", "curve_points", "error_limit_reached"):
            self.assertEqual(runs[0][1][key], runs[1][1][key], key)
        self.assertEqual(dimensions[0][:2], dimensions[1][:2])
        self.assertGreaterEqual(dimensions[1][2], dimensions[0][2])
        new.error_metric_combo.setCurrentIndex(1)
        new.show()
        self.app.processEvents()
        new.grab().save(str(ROOT / "build" / "training_maximum_de.png"))
        print("Baseline/current geometry:", dimensions)
        print("Baseline/current training seconds:", [r[1]["elapsed_seconds"] for r in runs])
        for widget in (new, old, fixture, p1, p2):
            widget.close()


if __name__ == "__main__":
    unittest.main()

