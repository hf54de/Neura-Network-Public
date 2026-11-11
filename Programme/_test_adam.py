"""Adam reference tests plus exact regression against the preserved SGD baseline."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import ast
import json
import math
import random
import unittest
from pathlib import Path
from copy import deepcopy
from PySide6.QtWidgets import QApplication
from network import NeuralNetwork
from neuron import Neuron
from neurontype import NeuronType
from connection import Connection
from adamoptimizer import validate_optimizer_state

ROOT = Path(__file__).resolve().parent
APP = QApplication.instance() or QApplication([])
BASELINE = Path((ROOT / "diagnostics/adam_baseline_current.txt").read_text(encoding="utf-8"))


def build(hidden="Tanh", output="Linear", momentum=0.):
    net = NeuralNetwork()
    rng = random.Random(517)
    kinds = (NeuronType.INPUT, NeuronType.INPUT, NeuronType.HIDDEN, NeuronType.HIDDEN, NeuronType.OUTPUT, NeuronType.OUTPUT)
    for i, kind in enumerate(kinds, 1):
        n = Neuron(i, 0, 0, "N" + str(i)); n.neuron_type = kind
        n.activation_function = "Linear" if kind == NeuronType.INPUT else hidden if kind == NeuronType.HIDDEN else output
        n.bias = 0 if kind == NeuronType.INPUT else rng.uniform(-.1, .1)
        net.add_neuron(n)
    for cid, (a, b) in enumerate([(a,b) for a in (1,2) for b in (3,4)] + [(a,b) for a in (3,4) for b in (5,6)], 1):
        net.add_connection(Connection(cid, net.get_neuron(a), net.get_neuron(b), rng.uniform(-.5, .5)))
    net.set_learning_rate(.007); net.set_momentum(momentum)
    net.trainer.visual_updates_enabled = False; net.prepare_training_calculation()
    return net, rng


def step(net, a, b):
    net.get_neuron(1).input_value = a; net.get_neuron(2).input_value = b
    return net.train_step({5: .3 + .2*a - .1*b, 6: .6 - .15*a + .05*b})


class CoreTests(unittest.TestCase):
    def test_sgd_matches_all_preserved_values_exactly(self):
        expected = json.loads((BASELINE / "sgd_baseline.json").read_text(encoding="utf-8"))
        for hidden, output in (("Sigmoid", "Sigmoid"), ("Tanh", "Linear"), ("ReLU", "Linear")):
            for momentum in (0., .5, .9):
                net, rng = build(hidden, output, momentum)
                errors = []
                for i in range(30):
                    result = step(net, rng.uniform(-.8,.8), rng.uniform(-.8,.8))
                    errors.append(result["mean_squared_error"])
                actual = {"weights": [c.weight for c in net.get_connections()],
                          "biases": [n.bias for n in net.get_neurons()],
                          "momentum": net.get_momentum_state(), "errors": errors,
                          "details": net.trainer.last_step_details}
                actual = json.loads(json.dumps(actual, default=str))
                self.assertEqual(actual, expected[hidden+"/"+output+"/"+str(momentum)])

    def test_existing_forward_and_backpropagation_methods_unchanged(self):
        for filename, names in (("network.py", {"forward_pass"}), ("trainer.py", {"calculate_deltas", "train_step"})):
            def selected(path):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                return {n.name: ast.dump(n, include_attributes=False) for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name in names}
            self.assertEqual(selected(ROOT/filename), selected(BASELINE/filename))

    def test_adam_matches_independent_scalar_reference(self):
        net, rng = build()
        net.set_solver("adam")
        weights = {c.id: c.weight for c in net.get_connections()}
        biases = {n.id: n.bias for n in net.get_neurons() if n.neuron_type != NeuronType.INPUT}
        moments = {}
        for t in range(1, 31):
            x = {1:rng.uniform(-.8,.8), 2:rng.uniform(-.8,.8)}
            values = dict(x)
            for n in (3,4,5,6):
                z = biases[n] + sum(values[c.source_neuron.id]*weights[c.id] for c in net.get_neuron(n).incoming_connections)
                values[n] = math.tanh(z) if n < 5 else z
            target = {5:.3+.2*x[1]-.1*x[2], 6:.6-.15*x[1]+.05*x[2]}
            gradients = {n:values[n]-target[n] for n in (5,6)}
            for n in (3,4):
                gradients[n] = sum(weights[c.id]*gradients[c.target_neuron.id] for c in net.get_neuron(n).outgoing_connections)*(1-values[n]**2)
            for key, val, grad in [(('w',c.id),weights[c.id],gradients[c.target_neuron.id]*values[c.source_neuron.id]) for c in net.get_connections()] + [(('b',n),biases[n],gradients[n]) for n in biases]:
                old_m, old_v = moments.get(key,(0.,0.))
                m = .9*old_m + (1-.9)*grad; v = .999*old_v + (1-.999)*grad**2
                new = val - .007 * (m/(1-.9**t))/(math.sqrt(v/(1-.999**t))+1e-8)
                moments[key] = m,v
                (weights if key[0]=='w' else biases)[key[1]] = new
            step(net,x[1],x[2])
            for c in net.get_connections(): self.assertAlmostEqual(c.weight,weights[c.id],places=14)
            for n in biases: self.assertAlmostEqual(net.get_neuron(n).bias,biases[n],places=14)
            self.assertEqual(net.get_optimizer_state()["step"],t)

    def test_adam_state_roundtrip_and_continuation_are_exact(self):
        full,_ = build(); full.set_solver("adam")
        split,_ = build(); split.set_solver("adam")
        rows=[(.1,.2),(-.4,.7),(.8,-.3)]*5
        for row in rows: step(full,*row)
        for row in rows[:7]: step(split,*row)
        restored,_=build()
        for c in split.get_connections(): restored.connections[c.id].weight=c.weight
        for n in split.get_neurons(): restored.get_neuron(n.id).bias=n.bias
        restored.restore_optimizer_state(json.loads(json.dumps(split.get_optimizer_state())))
        for row in rows[7:]:step(restored,*row)
        self.assertEqual(restored.get_optimizer_state(),full.get_optimizer_state())
        self.assertEqual([c.weight for c in restored.get_connections()],[c.weight for c in full.get_connections()])
        self.assertEqual([n.bias for n in restored.get_neurons()],[n.bias for n in full.get_neurons()])

    def test_invalid_state_is_rejected_without_partial_restore(self):
        net,_=build();net.set_solver("adam");step(net,.1,.2)
        saved=net.get_optimizer_state()
        for mutate in (lambda s:s.update(step=-1),lambda s:s.update(step=True),
                       lambda s:s['connections']['1'].update(v=-1),
                       lambda s:s['connections']['1'].update(m=float('nan')),
                       lambda s:s['connections'].pop('1')):
            invalid=deepcopy(saved);mutate(invalid)
            with self.assertRaises(ValueError):net.restore_optimizer_state(invalid)
            self.assertEqual(net.get_optimizer_state(),saved)

    def test_adam_overflow_preserves_parameters_and_state(self):
        net,_=build();net.set_solver("adam");step(net,.1,.2)
        before=([c.weight for c in net.get_connections()],[n.bias for n in net.get_neurons()],net.get_optimizer_state())
        net.trainer.delta_values={n.id:1e308 for n in net.get_neurons() if n.neuron_type!=NeuronType.INPUT}
        with self.assertRaises(ValueError):net.apply_training_gradients()
        self.assertEqual(before,([c.weight for c in net.get_connections()],[n.bias for n in net.get_neurons()],net.get_optimizer_state()))


class IntegrationTests(unittest.TestCase):
    # Reuse the existing isolated temporary-project fixture, never user projects.
    from _test_trainingprotocol import ProtocolIntegrationTests as _Fixture
    setUp = _Fixture.setUp
    tearDown = _Fixture.tearDown

    def make_dialog(self, solver="adam", code="de"):
        from _test_review_fixes import document, language
        from trainingdialog import TrainingDialog
        self.w.language = language(code)
        self.w.training_settings.update(solver=solver, learning_rate=.001 if solver=="adam" else .01)
        self.dialog = TrainingDialog(self.w.scene.network, document(), parent=self.w,
            training_settings=self.w.training_settings, language_manager=self.w.language)
        self.w.training_dialog = self.dialog
        self.dialog.previous_training_settings = self.dialog.get_training_settings()
        self.dialog.training_completed.connect(self.w.training_step_completed)
        return self.dialog

    def test_solver_controls_and_rate_memory(self):
        dialog = self.make_dialog("sgd")
        self.assertEqual(dialog.solver_combo.currentData(), "sgd")
        dialog.learning_rate.setValue(.023)
        dialog.solver_combo.setCurrentIndex(1)
        self.assertEqual(dialog.learning_rate.value(), .001)
        self.assertTrue(dialog.momentum.isHidden())
        self.assertTrue(dialog.training_values_layout.labelForField(dialog.momentum).isHidden())
        dialog.learning_rate.setValue(.002)
        dialog.solver_combo.setCurrentIndex(0)
        self.assertEqual(dialog.learning_rate.value(), .023)
        dialog.solver_combo.setCurrentIndex(1)
        self.assertEqual(dialog.learning_rate.value(), .002)
        dialog.set_training_controls_enabled(False)
        self.assertFalse(dialog.solver_combo.isEnabled())

    def test_adam_real_training_and_project_roundtrip_continuation(self):
        from PySide6.QtWidgets import QMessageBox
        from unittest.mock import patch
        dialog = self.make_dialog()
        with patch.object(QMessageBox, "warning") as warning:
            dialog.execute_training(2, False, shuffle_seed=42)
            warning.assert_not_called()
        self.assertEqual(self.w.training_history[0]["solver"], "adam")
        self.assertEqual(self.w.scene.network.get_optimizer_state()["step"], 4)
        saved_state = deepcopy(self.w.scene.network.get_optimizer_state())
        saved_weights = [c.weight for c in self.w.scene.network.get_connections()]
        self.w.training_dialog = None
        self.assertTrue(self.w.write_project_file(str(self.file)))
        stored = json.loads(self.file.read_text(encoding="utf-8"))
        self.assertEqual(stored["version"], __import__("projectio").ProjectIO.PROJECT_VERSION)
        self.assertEqual(stored["optimizer_state"], saved_state)
        self.w.project_modified = False
        self.w.open_project(str(self.file))
        self.assertEqual(self.w.scene.network.get_optimizer_state(), saved_state)
        self.assertEqual([c.weight for c in self.w.scene.network.get_connections()], saved_weights)
        self.dialog.deleteLater(); APP.processEvents(); self.dialog=None
        self.w.open_training_dialog(); self.dialog = self.w.training_dialog
        self.assertEqual(self.dialog.solver_combo.currentData(), "adam")
        self.assertEqual(self.dialog.current_run_solver, "adam")
        with patch.object(QMessageBox, "warning") as warning:
            self.dialog.execute_training(3, False, continue_existing=True)
            warning.assert_not_called()
        self.assertEqual(len(self.w.training_history), 1)
        self.assertEqual(self.w.scene.network.get_optimizer_state()["step"], 10)
        self.assertEqual(self.dialog.current_run_completed_epochs, 5)
        self.assertTrue(any((b.get("parameters") or {}).get("solver") == "adam"
                            for b in self.w.training_protocol.blocks))

    def test_solver_change_starts_linked_run_without_reinitializing_weights(self):
        from unittest.mock import patch
        dialog = self.make_dialog("sgd")
        dialog.execute_training(2, False, shuffle_seed=42)
        previous_id = dialog.current_run_id
        previous_weights = [c.weight for c in dialog.network.get_connections()]
        dialog.initialize_network.setChecked(True)
        dialog.solver_combo.setCurrentIndex(1)
        self.assertFalse(dialog.initialize_network.isChecked())
        with patch.object(dialog, "initialize_network_parameters") as initialize:
            dialog.execute_training(1, False, continue_existing=True)
            initialize.assert_not_called()
        self.assertNotEqual(dialog.current_run_id, previous_id)
        self.assertEqual(dialog.current_run_parent_id, previous_id)
        self.assertEqual(dialog.current_run_solver, "adam")
        self.assertEqual(dialog.network.get_optimizer_state()["step"], 2)
        self.assertEqual([c["weight"] for c in dialog.current_run_initial_state["connections"]], previous_weights)
        self.assertEqual([r["solver"] for r in self.w.training_history], ["sgd", "adam"])
        for entry in self.w.training_history:
            self.assertTrue(self.w.restore_training_network_state(entry["network_state"]))
            self.w.restore_training_settings_from_history(entry)
            dialog.show_restored_training_run(entry)
            self.assertEqual(dialog.current_run_solver, entry["solver"])
            self.assertEqual(dialog.solver_combo.currentData(), entry["solver"])
            self.assertEqual(dialog.network.get_optimizer_state(), entry["network_state"]["optimizer_state"])


    def check_repeat_after_solver_change(self, source_solver, target_solver):
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        from traininghistorydialog import TrainingHistoryDialog
        dialog = self.make_dialog(source_solver)
        dialog.execute_training(2, False, shuffle_seed=42)
        source_run = dialog.current_run_id
        initial = deepcopy(dialog.current_run_initial_state)
        self.assertNotEqual(dialog.capture_training_state(), initial)
        dialog.solver_combo.setCurrentIndex(dialog.solver_combo.findData(target_solver))
        dialog.select_training_target("one")
        starts = []
        train_epoch = dialog.train_epoch
        def record_start(*args, **kwargs):
            starts.append((dialog.capture_training_state(), dialog.network.get_optimizer_state(),
                           dialog.network.get_momentum_state()))
            return train_epoch(*args, **kwargs)
        with patch.object(dialog, "train_epoch", side_effect=record_start), patch.object(QMessageBox, "warning") as warning:
            dialog.repeat_with_same_initialization()
            warning.assert_not_called()
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0][0], initial)
        self.assertEqual(starts[0][1]["solver"], target_solver)
        if target_solver == "adam":self.assertEqual(starts[0][1]["step"], 0)
        self.assertTrue(all(not values for values in starts[0][2].values()))
        self.assertNotEqual(dialog.current_run_id, source_run)
        self.assertIsNone(dialog.current_run_parent_id)
        self.assertEqual(dialog.current_run_initial_state, initial)
        self.assertEqual(dialog.current_run_shuffle_seed, 42)
        self.assertEqual(dialog.current_run_completed_epochs, 1)
        saved = self.w.training_history[-1]
        self.assertEqual(saved["initial_network_state"], initial)
        self.assertEqual(saved["solver"], target_solver)
        history = TrainingHistoryDialog(self.w.training_history, language_manager=self.w.language)
        try:
            self.assertEqual(history.table.item(0, 2).text(),
                self.w.language.text("history.initialization.repeated", run=source_run))
        finally:history.deleteLater()

    def test_repeat_initialization_adam_to_sgd(self):
        self.check_repeat_after_solver_change("adam", "sgd")

    def test_repeat_initialization_sgd_to_adam(self):
        self.check_repeat_after_solver_change("sgd", "adam")

    def test_failed_adam_training_restores_complete_state(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        dialog=self.make_dialog()
        dialog.execute_training(2,False,shuffle_seed=42)
        before=(self.w.capture_training_network_state(),dialog.current_run_id,dialog.current_run_completed_epochs)
        def fail(*args):
            dialog.network.get_neuron(2).bias=123
            dialog.network.trainer.adam.step+=20
            raise ValueError("Injected failure")
        with patch.object(dialog,"train_epoch",side_effect=fail),patch.object(QMessageBox,"warning"):
            dialog.execute_training(2,False,continue_existing=True)
        self.assertEqual(before,(self.w.capture_training_network_state(),dialog.current_run_id,dialog.current_run_completed_epochs))

    def test_mathematics_debugger_and_reset_use_adam_formulas(self):
        from trainingdebugdialog import TrainingDebugDialog
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        for code in ("de", "en"):
            dialog=self.make_dialog(code=code)
            dialog.execute_training(1,False,shuffle_seed=42)
            net=dialog.network
            connection=net.get_connections()[0]
            for text in (net.get_calculation_details(net.get_neuron(2),self.w.language.text),
                         net.get_connection_calculation_details(connection,self.w.language.text)):
                self.assertIn("ADAM",text)
                self.assertIn("m_hat",text)
                self.assertIn("v_hat",text)
                self.assertNotIn("ΔW = Lernrate",text)
                self.assertNotIn("ΔB = Lernrate",text)
            debug=TrainingDebugDialog(net,dialog.records,dialog.input_columns,dialog.output_columns,language_manager=self.w.language)
            try:
                initial=net.get_optimizer_state()
                first="\n".join(debug.execute_single_step(1))
                second="\n".join(debug.execute_single_step(2))
                self.assertEqual(net.get_optimizer_state()["step"],initial["step"]+2)
                self.assertIn("m_hat",first)
                self.assertIn("v_hat",second)
                self.assertNotIn("Momentumanteil",first)
                with patch.object(QMessageBox,"information"):
                    debug.restore_initial_parameters()
                self.assertEqual(net.get_optimizer_state(),initial)
            finally: debug.deleteLater()
            self.w.training_dialog=None
            self.dialog.deleteLater();APP.processEvents();self.dialog=None

    def test_mathematics_clone_adam_phases_and_undo_are_isolated(self):
        from mathematicsdialog import MathematicsDialog
        from _test_review_fixes import document
        dialog=self.make_dialog();dialog.execute_training(1,False,shuffle_seed=42)
        net=dialog.network
        before=self.w.capture_training_network_state()
        math_dialog=MathematicsDialog(net,net.get_neuron(2),document(),learning_rate=.001,language_manager=self.w.language)
        try:
            self.assertEqual(math_dialog.network.get_optimizer_state(),net.get_optimizer_state())
            self.assertEqual(math_dialog.solver_combo.currentData(),"adam")
            self.assertTrue(math_dialog.momentum.isHidden())
            math_dialog.continue_radio.setChecked(True)
            math_dialog.start_experiment()
            state=math_dialog.capture_network_state()
            self.assertTrue(math_dialog.execute_next_record())
            after=math_dialog.capture_network_state()
            self.assertEqual(after["optimizer_state"]["step"],before["optimizer_state"]["step"]+1)
            detail=math_dialog.epoch_details[0]
            for phase in ("start","inputs","sum","activation","error","updates","complete"):
                text=math_dialog.create_guided_html(phase,detail)
                if phase in ("start","updates","complete"):
                    self.assertIn("Adam",text)
                    self.assertNotIn("Momentum",text)
                if phase=="updates":
                    self.assertIn("m_hat",text);self.assertIn("v_hat",text)
            report=math_dialog.create_report(1,0,math_dialog.records[0],detail["result"],step=detail["step"])
            self.assertIn("ADAM",report)
            self.assertNotIn("Momentumanteil",report)
            math_dialog.step_back()
            self.assertEqual(math_dialog.capture_network_state(),state)
            self.assertTrue(math_dialog.execute_next_record())
            self.assertEqual(math_dialog.capture_network_state(),after)
            math_dialog.request_close()
            self.assertEqual(self.w.capture_training_network_state(),before)
        finally: math_dialog.deleteLater()

    def test_mathematics_sgd_reports_match_preserved_version(self):
        import importlib.util
        from mathematicsdialog import MathematicsDialog
        from _test_review_fixes import document
        spec=importlib.util.spec_from_file_location("adam_baseline_mathematics",BASELINE/"mathematicsdialog.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        net=self.w.scene.network
        old=module.MathematicsDialog(net,net.get_neuron(2),document(),language_manager=self.w.language)
        new=MathematicsDialog(net,net.get_neuron(2),document(),language_manager=self.w.language)
        try:
            for dialog in (old,new):
                dialog.continue_radio.setChecked(True);dialog.start_experiment()
                self.assertTrue(dialog.execute_next_record())
            for phase in ("start","inputs","sum","activation","error","updates","complete"):
                self.assertEqual(old.create_guided_html(phase,old.epoch_details[0]),new.create_guided_html(phase,new.epoch_details[0]))
            self.assertEqual(old.epoch_reports[0],new.epoch_reports[0])
        finally:old.deleteLater();new.deleteLater()

    def test_legacy_project_defaults_to_sgd(self):
        from projectio import ProjectIO
        self.assertTrue(self.w.write_project_file(str(self.file)))
        stored=json.loads(self.file.read_text(encoding="utf-8"))
        stored["version"]=15
        stored.pop("optimizer_state",None)
        stored["training_settings"].pop("solver",None)
        self.file.write_text(json.dumps(stored),encoding="utf-8")
        loaded=ProjectIO.load_project(str(self.file))
        self.assertEqual(loaded["training_settings"]["solver"],"sgd")
        self.assertIsNone(loaded["optimizer_state"])
        self.assertEqual(loaded["version"],__import__("projectio").ProjectIO.PROJECT_VERSION)

    def test_corrupt_adam_project_is_rejected_before_replacing_editor(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        dialog=self.make_dialog();dialog.execute_training(1,False,shuffle_seed=42)
        self.assertTrue(self.w.write_project_file(str(self.file)))
        stored=json.loads(self.file.read_text(encoding="utf-8"))
        before=self.w.capture_training_network_state()
        self.w.training_dialog=None
        for corruption in ("counter","missing_connection","missing_bias","historical_bias"):
            broken=deepcopy(stored)
            if corruption=="counter":broken["optimizer_state"]["step"]=-3
            elif corruption=="missing_connection":broken["optimizer_state"]["connections"].pop(next(iter(broken["optimizer_state"]["connections"])))
            elif corruption=="missing_bias":broken["optimizer_state"]["biases"].pop(next(iter(broken["optimizer_state"]["biases"])))
            else:
                broken["optimizer_state"]=None
                values=broken["training_history"][0]["network_state"]["optimizer_state"]["biases"]
                values.pop(next(iter(values)))
            self.file.write_text(json.dumps(broken),encoding="utf-8")
            self.w.project_modified=False
            with patch.object(QMessageBox,"critical") as error:
                self.w.open_project(str(self.file));error.assert_called_once()
            self.assertEqual(before,self.w.capture_training_network_state())


class WorkflowAuditTests(unittest.TestCase):
    setUp = IntegrationTests.setUp
    tearDown = IntegrationTests.tearDown
    make_dialog = IntegrationTests.make_dialog

    def test_explicit_new_initialization_survives_solver_change(self):
        from unittest.mock import patch
        dialog = self.make_dialog()
        dialog.execute_training(2, False, shuffle_seed=42)
        dialog.solver_combo.setCurrentIndex(dialog.solver_combo.findData("sgd"))
        dialog.initialize_network.setChecked(True)
        dialog.select_training_target("one")
        def initialize():
            for c in dialog.network.get_connections():c.weight=.321
            for n in dialog.network.get_neurons():n.bias=.123
        with patch.object(dialog, "initialize_network_parameters", side_effect=initialize) as initialized:
            dialog.start_selected_training()
            initialized.assert_called_once()
        self.assertIsNone(dialog.current_run_parent_id)
        self.assertTrue(all(c["weight"]==.321 for c in dialog.current_run_initial_state["connections"]))
        self.assertTrue(all(n["bias"]==.123 for n in dialog.current_run_initial_state["neurons"]))

    def check_debugger_state(self, restore):
        from unittest.mock import patch
        from trainingdebugdialog import TrainingDebugDialog
        from PySide6.QtWidgets import QMessageBox
        dialog = self.make_dialog()
        dialog.execute_training(2, False, shuffle_seed=42)
        before = deepcopy(self.w.capture_training_network_state())
        before_rate = dialog.network.get_learning_rate()
        before_momentum = dialog.network.get_momentum()
        dialog.solver_combo.setCurrentIndex(dialog.solver_combo.findData("sgd"))
        def inspect(debug):
            if restore:
                debug.execute_steps(1)
                self.assertEqual(debug.network.get_solver(), "sgd")
                with patch.object(QMessageBox,"information"):debug.restore_initial_parameters()
            return 0
        with patch.object(TrainingDebugDialog, "exec", inspect):dialog.debug_training()
        self.assertEqual(self.w.capture_training_network_state(), before)
        self.assertEqual(dialog.network.get_learning_rate(), before_rate)
        self.assertEqual(dialog.network.get_momentum(), before_momentum)

    def test_debugger_open_close_keeps_original_optimizer(self):
        self.check_debugger_state(False)

    def test_debugger_reset_restores_original_optimizer_after_switch(self):
        self.check_debugger_state(True)

    def check_stop_save_reopen_resume(self, solver):
        from unittest.mock import patch
        from trainingdialog import TrainingDialog
        from _test_review_fixes import network, document
        from PySide6.QtCore import QEvent
        dialog=self.make_dialog(solver)
        dialog.momentum.setValue(.8)
        initial=dialog.capture_training_state()
        reference=TrainingDialog(network(),document(),training_settings=dialog.get_training_settings(),language_manager=self.w.language)
        try:
            reference.execute_training(3,False,initial_state=initial,shuffle_seed=42)
            expected=(reference.capture_training_state(), reference.network.get_optimizer_state(), reference.network.get_momentum_state())
            real_step=dialog.network.train_step
            count=0
            def stop_at_epoch_end(*args,**kwargs):
                nonlocal count
                result=real_step(*args,**kwargs);count+=1
                if count==len(dialog.records):dialog.request_stop()
                return result
            with patch.object(dialog.network,"train_step",side_effect=stop_at_epoch_end):
                dialog.execute_training(5,False,initial_state=initial,shuffle_seed=42)
            self.assertTrue(dialog.current_run_stopped)
            self.assertEqual(dialog.current_run_completed_epochs,1)
            run_id=dialog.current_run_id
            optimizer=dialog.network.get_optimizer_state()
            momentum=dialog.network.get_momentum_state()
            self.w.training_dialog_finished(dialog);self.dialog=None
            APP.processEvents();APP.sendPostedEvents(None,QEvent.Type.DeferredDelete);APP.processEvents()
            self.assertTrue(self.w.write_project_file(str(self.file)))
            self.w.project_modified=False;self.w.open_project(str(self.file))
            self.assertEqual(self.w.scene.network.get_optimizer_state(),optimizer)
            self.assertEqual(self.w.scene.network.get_momentum_state(),momentum)
            self.w.open_training_dialog();self.dialog=self.w.training_dialog
            self.dialog.select_training_target("epochs");self.dialog.epoch_count.setValue(2)
            self.dialog.continue_selected_training()
            self.assertEqual(self.dialog.current_run_id,run_id)
            self.assertEqual(len(self.w.training_history),1)
            self.assertEqual(self.dialog.current_run_completed_epochs,3)
            self.assertEqual((self.dialog.capture_training_state(),self.dialog.network.get_optimizer_state(),self.dialog.network.get_momentum_state()),expected)
            self.assertEqual(self.dialog.history_curve_points,reference.history_curve_points)
        finally:reference.deleteLater()

    def test_adam_stop_save_reopen_matches_uninterrupted_training(self):
        self.check_stop_save_reopen_resume("adam")

    def test_sgd_stop_save_reopen_matches_uninterrupted_training(self):
        self.check_stop_save_reopen_resume("sgd")

    def check_delete_mixed_history(self, source, target):
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        dialog=self.make_dialog(source);dialog.momentum.setValue(.8)
        dialog.execute_training(2,False,shuffle_seed=42)
        original=deepcopy(self.w.capture_training_network_state())
        previous_id=dialog.current_run_id
        dialog.solver_combo.setCurrentIndex(dialog.solver_combo.findData(target))
        dialog.select_training_target("one");dialog.continue_selected_training()
        self.assertEqual(dialog.current_run_parent_id,previous_id)
        with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.Yes):
            dialog.load_previous_training_run(delete_run_id=dialog.current_run_id)
        self.assertEqual(dialog.current_run_id,previous_id)
        self.assertEqual(dialog.solver_combo.currentData(),source)
        self.assertEqual(self.w.capture_training_network_state(),original)
        self.assertEqual(self.w.training_settings["solver"],source)
        self.assertEqual(len(self.w.training_history),1)
        dialog.maximum_epochs.setValue(10)
        dialog.select_training_target("one");dialog.continue_selected_training()
        self.assertEqual(dialog.current_run_id,previous_id)
        self.assertEqual(dialog.current_run_completed_epochs,3)
        with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.Yes):
            dialog.load_previous_training_run(delete_run_id=previous_id)
        self.assertIsNone(dialog.current_run_id)
        self.assertEqual(self.w.training_history,[])
        self.assertTrue(all(not v for v in dialog.network.get_momentum_state().values()))
        if source=="adam":self.assertEqual(dialog.network.get_optimizer_state()["step"],0)

    def test_delete_sgd_restores_adam_and_delete_last_clears_state(self):
        self.check_delete_mixed_history("adam","sgd")

    def test_delete_adam_restores_sgd_and_delete_last_clears_state(self):
        self.check_delete_mixed_history("sgd","adam")

    def test_mathematics_adam_all_neuron_types_and_languages_are_isolated(self):
        from mathematicsdialog import MathematicsDialog
        from _test_review_fixes import document,language
        dialog=self.make_dialog();dialog.execute_training(2,False,shuffle_seed=42)
        original=self.w.capture_training_network_state()
        for code in ("de","en"):
            for neuron in dialog.network.get_neurons():
                math_dialog=MathematicsDialog(dialog.network,neuron,document(),learning_rate=.001,language_manager=language(code))
                try:
                    math_dialog.continue_radio.setChecked(True);math_dialog.start_experiment()
                    self.assertTrue(math_dialog.execute_next_record())
                    detail=math_dialog.epoch_details[0]
                    for phase in ("start","inputs","sum","activation","error","updates","complete"):
                        self.assertTrue(math_dialog.create_guided_html(phase,detail))
                    self.assertIn("m_hat",math_dialog.create_guided_html("updates",detail))
                    math_dialog.request_close()
                    self.assertEqual(self.w.capture_training_network_state(),original)
                finally:math_dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
