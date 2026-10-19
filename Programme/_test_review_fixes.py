"""Gezielte Regressionstests für die vereinbarten Reviewpunkte 1–4 und 6.

Alle temporären Dateien bleiben im Quellcodeordner. Kein Start der Anwendung,
keine persönlichen Einstellungen, kein Zugriff auf Beispielprojekte.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import math
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from atomicjson import write_json_atomic
from connection import Connection
from graphicalexperimentdialog import GraphicalExperimentDialog
from language import LanguageManager
from mainwindow import MainWindow
from network import NeuralNetwork
from neuron import Neuron
from neurontype import NeuronType
from projectio import ProjectIO
from trainingdataio import TrainingDataIO
from trainingdatamanager import TrainingDataManager
from trainingdialog import TrainingDialog
from traininghistorydialog import TrainingHistoryDialog
from trainingvalidity import data_signature, training_context, invalidate_history

ROOT = Path(__file__).resolve().parent
APP = QApplication.instance() or QApplication([])


def language(code):
    return LanguageManager(code, ROOT / "languages.json")


def network(code="de"):
    net = NeuralNetwork(translator=language(code).text)
    for identifier, kind in [(1, NeuronType.INPUT), (2, NeuronType.HIDDEN), (3, NeuronType.OUTPUT)]:
        n = Neuron(identifier, identifier * 220, 0, f"N{identifier}")
        n.neuron_type = kind
        n.activation_function = "Linear" if kind != NeuronType.HIDDEN else "Tanh"
        net.add_neuron(n)
    net.add_connection(Connection(1, net.get_neuron(1), net.get_neuron(2), 0.2))
    net.add_connection(Connection(2, net.get_neuron(2), net.get_neuron(3), 0.3))
    return net


def document():
    doc = TrainingDataIO.create_empty_document(1, 1, "Test")
    doc["columns"][0]["mapped_neuron_id"] = 1
    doc["columns"][1]["mapped_neuron_id"] = 3
    doc["records"] = [[0.0, 0.0], [1.0, 1.0]]
    return doc


def window(net=None, doc=None):
    net = net or network()
    manager = TrainingDataManager(language_manager=language("de"))
    manager.set_document(doc or document(), file_path=str(ROOT / "test.nndata"))
    w = SimpleNamespace(scene=SimpleNamespace(network=net), training_data_manager=manager,
                        training_history=[], _invalidated_training_runs={},
                        active_training_run_id=None, project_modified=False, _history_restoring=False)
    for name in ("current_training_context", "refresh_training_history_validity",
                 "training_run_matches_active_data", "active_training_history_entry",
                 "capture_training_network_state", "training_network_state_is_compatible"):
        setattr(w, name, getattr(MainWindow, name).__get__(w))
    return w


def entry(w, run_id=1):
    return dict(run_id=run_id, timestamp="2026-10-14T12:00:00", training_data="Test",
                initialized=True, weight_initialization="xavier", bias_initialization="zero",
                learning_rate=0.01, momentum=0.0, error_limit=0.01, requested_epochs=2,
                completed_epochs=2, start_error=0.2, end_error=0.1, maximum_absolute_error=0.3,
                elapsed_seconds=0.1, status_text="OK", stop_at_error_limit=False,
                training_stopped=False, curve_points=[[1, 0.2], [2, 0.1]],
                network_state=w.capture_training_network_state(), continuable=True,
                training_context=w.current_training_context())


def project(edges):
    d = dict(version=ProjectIO.PROJECT_VERSION, neurons=[
        dict(id=i, name=f"N{i}", type=kind.value, bias=0.0, activation="Linear",
             input_value=0.0, target_value=0.0, x=0.0, y=0.0)
        for i, kind in [(1, NeuronType.INPUT), (2, NeuronType.HIDDEN),
                        (3, NeuronType.HIDDEN), (4, NeuronType.OUTPUT)]
    ], connections=[dict(id=i+1, source=a, target=b, weight=0.5)
                    for i, (a,b) in enumerate(edges)])
    ProjectIO._prepare_project_data(d)
    return d


class ReviewFixTests(unittest.TestCase):
    def test_invalid_topologies_rejected_in_both_languages(self):
        for code in ("de", "en"):
            for edges in ([(2,2)], [(4,2)], [(2,1)], [(2,3),(3,2)]):
                with self.subTest(code=code, edges=edges):
                    with self.assertRaises(ValueError) as error:
                        ProjectIO._validate_project_data(project(edges), language(code).text)
                    self.assertIn("unverändert" if code == "de" else "unchanged", str(error.exception))

    def test_incomplete_and_valid_projects_remain_loadable(self):
        for edges in ([], [(1,2)], [(1,2),(2,3),(3,4)]):
            ProjectIO._validate_project_data(project(edges), language("en").text)

    def test_invalid_project_does_not_reset_current_project(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="review_test_") as directory:
            self.assertEqual(Path(directory).resolve().parent, ROOT)
            path = Path(directory) / "invalid.nnproj"
            path.write_text(json.dumps(project([(2,3),(3,2)])), encoding="utf-8")
            w = SimpleNamespace(confirm_unsaved_changes=lambda: True,
                                language=language("en"), reset_project=Mock())
            with patch("mainwindow.QMessageBox.critical") as warning:
                self.assertFalse(MainWindow.open_project(w, str(path)))
            w.reset_project.assert_not_called()
            warning.assert_called_once()

    def test_activation_change_invalidates_every_old_run(self):
        w = window()
        w.training_history = [entry(w,1), entry(w,2)]
        w.active_training_run_id = 2
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.refresh_training_history_validity()
        self.assertIsNone(w.active_training_run_id)
        self.assertIsNone(w.active_training_history_entry())
        for run in w.training_history:
            self.assertEqual(run["invalidated_reason"], "activation")
            self.assertFalse(run["continuable"])
            self.assertFalse(w.training_network_state_is_compatible(run["network_state"]))

    def test_reverting_activation_does_not_reenable_runs(self):
        w = window(); w.training_history = [entry(w)]
        before = deepcopy(w.training_history)
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.refresh_training_history_validity()
        w.scene.network.get_neuron(2).activation_function = "Tanh"
        w.training_history = before  # also covers editor undo
        self.assertIsNone(w.active_training_history_entry())
        self.assertEqual(w.training_history[0]["invalidated_reason"], "activation")

    def test_new_training_after_invalidation_is_allowed(self):
        w = window(); w.training_history = [entry(w)]
        w.scene.network.get_neuron(2).activation_function = "Sigmoid"
        w.refresh_training_history_validity()
        fresh = entry(w,2); w.training_history.append(fresh)
        self.assertIs(w.active_training_history_entry(), fresh)

    def test_data_values_scaling_and_assignment_invalidate(self):
        for kind in ("input", "target", "scaling", "mapping"):
            with self.subTest(kind=kind):
                w=window(); w.training_history=[entry(w)]; w.active_training_run_id=1
                d=w.training_data_manager.document
                if kind == "input": d["records"][1][0]=0.7
                elif kind == "target": d["records"][1][1]=0.4
                elif kind == "scaling": d["columns"][0]["calibration"]["mode"]="minmax_minus1_1"
                else: d["columns"][0]["mapped_neuron_id"]=2
                w.training_data_manager.set_document(d)
                self.assertIsNone(w.active_training_history_entry())
                self.assertEqual(w.training_history[0]["invalidated_reason"],"data")
                self.assertIsNone(w.active_training_run_id)

    def test_rename_move_and_metadata_do_not_invalidate(self):
        w=window(); run=entry(w); w.training_history=[run]
        d=w.training_data_manager.document
        d["name"]="Renamed"; d["data_origin"]="empirical"
        d["columns"][0]["name"]="Renamed input"
        w.training_data_manager.set_document(d,file_path=str(ROOT / "moved" / "renamed.nndata"))
        self.assertIs(w.active_training_history_entry(),run)

    def test_same_filename_different_data_does_not_match(self):
        w=window(); w.training_history=[entry(w)]
        d=w.training_data_manager.document;d["records"]=[[1.0,9.0]]
        w.training_data_manager.set_document(d,file_path=str(ROOT / "other" / "test.nndata"))
        self.assertIsNone(w.active_training_history_entry())

    def test_legacy_history_gets_baseline_then_invalidates(self):
        w=window(); run=entry(w); del run["training_context"]
        for n in run["network_state"]["neurons"]: n.pop("activation")
        w.training_history=[run]
        self.assertIs(w.active_training_history_entry(),run)
        w.scene.network.get_neuron(2).activation_function="ReLU"
        self.assertIsNone(w.active_training_history_entry())

    def test_invalidated_history_survives_json_and_renumbering(self):
        w=window(); w.training_history=[entry(w,7)]
        w.scene.network.get_neuron(2).activation_function="Sigmoid"
        w.refresh_training_history_validity()
        w.training_history=json.loads(json.dumps(w.training_history))
        w.training_history[0]["run_id"]=1
        w._invalidated_training_runs={}
        w.scene.network.get_neuron(2).activation_function="Tanh"
        self.assertIsNone(w.active_training_history_entry())
        ProjectIO._validate_training_history_data(w.training_history)

    def test_history_dialog_labels_and_blocks_invalid_runs(self):
        for code in ("de", "en"):
            w=window(); run=entry(w); run["invalidated_reason"]="data"; run["continuable"]=False
            dialog=TrainingHistoryDialog([run], language_manager=language(code), restorable_run_ids={1})
            try:
                dialog.table.selectRow(0); dialog.update_chart_selection()
                self.assertFalse(dialog.restore_button.isEnabled())
                self.assertIn("Ungültig" if code=="de" else "Invalid",dialog.table.item(0,0).text())
                dialog.request_restore_selected_run()
                self.assertIsNone(dialog.restore_run_id)
            finally: dialog.deleteLater()

    def test_delete_active_run_does_not_restore_invalid_fallback(self):
        w=window(); bad=entry(w,1);bad["invalidated_reason"]="data";good=entry(w,2)
        dialog=TrainingHistoryDialog([bad,good],language_manager=language("en"),restorable_run_ids={2},active_run_id=2)
        try:
            dialog.table.selectRow(0)
            # Test the deletion path with a confirmed answer, without opening a box.
            from PySide6.QtWidgets import QMessageBox
            with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.Yes):
                dialog.delete_selected_runs()
            self.assertIsNone(dialog.restore_run_id)
            self.assertIsNone(dialog.active_run_id)
            self.assertEqual(len(dialog.training_history),1)
        finally: dialog.deleteLater()

    def test_initialization_state_checks_activation(self):
        net=network(); holder=SimpleNamespace(network=net)
        state=TrainingDialog.capture_training_state(holder)
        self.assertTrue(TrainingDialog.training_state_is_compatible(holder,state))
        net.get_neuron(2).activation_function="Sigmoid"
        self.assertFalse(TrainingDialog.training_state_is_compatible(holder,state))

    def test_atomic_write_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix="review_test_") as directory:
            self.assertEqual(Path(directory).resolve().parent,ROOT)
            path=Path(directory)/"layout.json"; original=b'{"cards":{"old":true}}'
            path.write_bytes(original)
            with patch("atomicjson.os.replace",side_effect=OSError("test failure")):
                with self.assertRaises(OSError): write_json_atomic(path,{"cards":{"new":True}})
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(list(Path(directory).iterdir()),[path])

    def test_layout_and_geometry_use_atomic_writer(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix="review_test_") as directory:
            self.assertEqual(Path(directory).resolve().parent,ROOT)
            path=Path(directory)/"layout.json"
            w=SimpleNamespace(finish_nudge_history=lambda:None,layout_file=path,background_item=None,
                layout_state=lambda:{"cards":{"test":True}},width=lambda:900,height=lambda:600,
                update_save_button=lambda:None,status_label=Mock(),tr=lambda de,en:en,
                saveGeometry=lambda:b"geometry")
            self.assertTrue(GraphicalExperimentDialog.save_layout(w))
            before=path.read_bytes()
            with patch("graphicalexperimentdialog.QSettings"),patch("atomicjson.os.replace",side_effect=OSError("test failure")):
                GraphicalExperimentDialog.save_window_geometry(w)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(json.loads(before)["cards"],{"test":True})

    def test_numerical_messages_follow_language(self):
        for code in ("de","en"):
            net=network(code);net.get_neuron(1).input_value=2.0;net.get_connection(1).weight=1e308
            with self.assertRaises(ValueError) as error:net.forward_pass()
            self.assertIn("numerisch instabil" if code=="de" else "numerically unstable",str(error.exception))
            with self.assertRaises(ValueError) as error:net.set_learning_rate(0)
            self.assertIn("Lernrate" if code=="de" else "learning rate",str(error.exception))

    def test_hidden_training_error_is_translated(self):
        for code in ("de","en"):
            net=network(code);net.get_neuron(2).activation_function="Linear"
            net.get_neuron(1).input_value=0.0;net.get_connection(2).weight=1e308
            net.forward_pass()
            with self.assertRaises(ValueError) as error:net.calculate_training_deltas({3:1e308})
            self.assertIn("Hidden-Neuron" if code=="de" else "hidden neuron",str(error.exception))

    def test_saved_project_loads_history_after_data_and_restores_momentum(self):
        from editorscene import EditorScene
        for change_data in (False, True):
            with self.subTest(change_data=change_data):
                original=window(); run=entry(original)
                run["network_state"]["momentum_state"]={"connections":{"1":0.25},"biases":{}}
                saved=project([])
                saved["neurons"]=[dict(id=n.id,name=n.name,type=n.neuron_type.value,
                    bias=n.bias,activation=n.activation_function,input_value=0.0,target_value=0.0,
                    x=n.x(),y=n.y()) for n in original.scene.network.get_neurons()]
                saved["connections"]=[dict(id=c.id,source=c.source_neuron.id,target=c.target_neuron.id,
                    weight=c.weight) for c in original.scene.network.get_connections()]
                saved["training_history"]=[run];saved["active_training_run_id"]=1
                saved["momentum_state"]=None
                w=window();w.scene=EditorScene(language_manager=language("en"));w.language=language("en")
                w.test_data_manager=TrainingDataManager(language_manager=w.language)
                w.confirm_unsaved_changes=lambda:True
                def reset():
                    w.training_history=[];w._invalidated_training_runs={};w.active_training_run_id=None
                    w.scene.clear_project();w.training_data_manager.clear();w.test_data_manager.clear()
                w.reset_project=reset
                w.training_data_manager.state_changed.connect(w.refresh_training_history_validity)
                d=document()
                if change_data:d["records"][1][1]=0.7
                w.prepare_project_training_data=lambda *args:dict(cancelled=False,document=d,
                    file_path=str(ROOT/"same.nndata"),association_changed=False)
                w.prepare_project_test_data=lambda *args:dict(cancelled=False,document=None,
                    file_path=None,association_changed=False)
                w.view=SimpleNamespace(set_zoom=Mock(),centerOn=Mock())
                for name in ("apply_display_settings","update_project_image_action","remember_project_directory",
                             "reset_undo_history","set_project_modified","schedule_loaded_project_fit"):
                    setattr(w,name,Mock())
                w.reconcile_active_data_mappings=lambda:False
                status=Mock();w.statusBar=lambda:status
                with tempfile.TemporaryDirectory(dir=ROOT,prefix="review_test_") as directory:
                    self.assertEqual(Path(directory).resolve().parent,ROOT)
                    path=Path(directory)/"project.nnproj";path.write_text(json.dumps(saved),encoding="utf-8")
                    with patch("mainwindow.QTimer.singleShot"):
                        self.assertTrue(MainWindow.open_project(w,str(path)))
                self.assertEqual(w.scene.network.trainer.connection_velocities,{1:0.25})
                if change_data:
                    self.assertIsNone(w.active_training_history_entry())
                    self.assertEqual(w.training_history[0]["invalidated_reason"],"data")
                else:
                    self.assertEqual(w.active_training_history_entry()["run_id"],1)
                    self.assertNotIn("invalidated_reason",w.training_history[0])
                    w.set_project_modified.assert_called_with(False)
                w.scene.deleteLater()

    def test_malformed_history_metadata_rejected_before_loading(self):
        for code in ("de","en"):
            w=window()
            for field,value in [("validity_id",[]),("training_context",[]),("invalidated_reason","unknown")]:
                run=entry(w);run[field]=value
                with self.subTest(code=code,field=field):
                    with self.assertRaises(ValueError) as error:
                        ProjectIO._validate_training_history_data([run],translator=language(code).text)
                    self.assertIn("ungültig" if code=="de" else "invalid",str(error.exception))

    def test_language_keys_have_matching_placeholders(self):
        from string import Formatter
        data=json.loads((ROOT/"languages.json").read_text(encoding="utf-8"))["languages"]
        for key,en in data["en"]["texts"].items():
            if key.startswith(("calculation.error.","history.invalid","dialog.project_open.topology","dialog.project_open.invalid_topology")):
                de=data["de"]["texts"][key]
                fields=lambda s:{f for _,f,_,_ in Formatter().parse(s) if f is not None}
                self.assertEqual(fields(en),fields(de),key)
                self.assertEqual(language("en").BUILTIN_ENGLISH[key],en)

if __name__ == "__main__":
    unittest.main(verbosity=2)
