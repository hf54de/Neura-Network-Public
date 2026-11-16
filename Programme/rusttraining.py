"""Optional native training engine for the isolated Windows test build."""

import ctypes as c
from functools import lru_cache
import os
from pathlib import Path
import random

from neurontype import NeuronType
from trainingdataio import TrainingDataIO


class Node(c.Structure):
    _fields_ = [(name, c.c_size_t) for name in ("begin_in", "end_in", "begin_out", "end_out")] + [
        ("activation", c.c_uint32), ("kind", c.c_uint32)
    ]


class Edge(c.Structure):
    _fields_ = [("source", c.c_size_t), ("target", c.c_size_t)]


class Parameter(c.Structure):
    _fields_ = [(name, c.c_double) for name in ("value", "m", "v")]


class Problem(c.Structure):
    _fields_ = [
        ("nodes", c.POINTER(Node)), ("node_count", c.c_size_t),
        ("edges", c.POINTER(Edge)), ("edge_count", c.c_size_t),
        ("incoming", c.POINTER(c.c_size_t)), ("outgoing", c.POINTER(c.c_size_t)),
        ("input_ids", c.POINTER(c.c_size_t)), ("input_count", c.c_size_t),
        ("output_ids", c.POINTER(c.c_size_t)), ("output_count", c.c_size_t),
        ("records", c.POINTER(c.c_double)), ("record_count", c.c_size_t),
        ("rate", c.c_double), ("momentum", c.c_double), ("solver", c.c_uint32),
        ("tanh", c.c_void_p), ("exp", c.c_void_p), ("pow", c.c_void_p), ("sqrt", c.c_void_p),
    ]


class Metrics(c.Structure):
    _fields_ = [
        ("mean_squared_error", c.c_double), ("maximum_absolute_error", c.c_double),
        ("record", c.c_size_t), ("output", c.c_size_t), ("actual", c.c_double),
    ]


def native_array(element_type, values):
    values = list(values)
    return (element_type * len(values))(*values)


@lru_cache(maxsize=1)
def load_library():
    dll_path = Path(__file__).resolve().parent / "rust" / "training.dll"
    try:
        library = c.CDLL(str(dll_path))
        runtime = c.CDLL("ucrtbase.dll")
        math_functions = tuple(c.cast(getattr(runtime, name), c.c_void_p)
                               for name in ("tanh", "exp", "pow", "sqrt"))
        train_epoch = library.train_epoch
    except (OSError, AttributeError):
        return None

    train_epoch.argtypes = [
        c.POINTER(Problem), c.POINTER(c.c_size_t), c.POINTER(Parameter),
        c.POINTER(c.c_size_t), c.POINTER(Metrics),
    ]
    train_epoch.restype = c.c_uint32
    return train_epoch, math_functions


def selected_backend():
    return None if os.environ.get("NEURONNET_TRAINING_BACKEND") == "python" else load_library()


class RustTrainingSession:
    def __init__(self, backend, network, records, inputs, outputs, text):
        self.network = network
        self.records = records
        self.outputs = outputs
        self.text = text
        self.train_epoch, math_functions = backend
        self.edges = network.get_connections()
        self.nodes = network.prepared_training_order()
        self.solver = network.get_solver()
        edge_index = {edge.id: index for index, edge in enumerate(self.edges)}
        node_index = {node.id: index for index, node in enumerate(self.nodes)}
        kind = {NeuronType.INPUT: 0, NeuronType.HIDDEN: 1, NeuronType.OUTPUT: 2}
        activation = {"Linear": 1, "ReLU": 2, "Sigmoid": 3, "Tanh": 4}
        incoming, outgoing, nodes = [], [], []
        for node in self.nodes:
            start_in, start_out = len(incoming), len(outgoing)
            incoming.extend(edge_index[edge.id] for edge in node.incoming_connections)
            outgoing.extend(edge_index[edge.id] for edge in node.outgoing_connections)
            nodes.append(Node(start_in, len(incoming), start_out, len(outgoing),
                              activation[node.activation_function], kind[node.neuron_type]))

        columns = [*inputs, *outputs]
        values = (
            TrainingDataIO.scale_value(record[column["column_index"]], column["calibration"], text)
            for record in records for column in columns
        )
        self.problem = Problem(
            native_array(Node, nodes), len(nodes),
            native_array(Edge, (Edge(node_index[edge.source_neuron.id], node_index[edge.target_neuron.id])
                                for edge in self.edges)), len(self.edges),
            native_array(c.c_size_t, incoming), native_array(c.c_size_t, outgoing),
            native_array(c.c_size_t, (node_index[mapping["neuron"].id] for mapping in inputs)), len(inputs),
            native_array(c.c_size_t, (node_index[mapping["neuron"].id] for mapping in outputs)), len(outputs),
            native_array(c.c_double, values), len(records), network.get_learning_rate(),
            network.get_momentum(), int(self.solver == "adam"), *math_functions,
        )

        state = network.get_optimizer_state() if self.solver == "adam" else network.get_momentum_state()
        bias_states = state["biases"]
        edge_states = state["connections"]
        self.step = c.c_size_t(state.get("step", 0))
        parameters = [self.make_parameter(edge.weight, edge_states.get(str(edge.id))) for edge in self.edges]
        parameters.extend(self.make_parameter(node.bias, bias_states.get(str(node.id))) for node in self.nodes)
        self.parameters = native_array(Parameter, parameters)
        self.metrics = Metrics()
        self.order_buffer = (c.c_size_t * len(records))()

    def make_parameter(self, value, state):
        if state is None:
            return Parameter(value, 0.0, 0.0)
        if self.solver == "adam":
            return Parameter(value, state["m"], state["v"])
        return Parameter(value, state, 0.0)

    def run_epoch(self, epoch, seed):
        self.advance_epoch(epoch, seed)
        self.synchronize_parameters()

        metrics = self.metrics
        record = self.records[metrics.record]
        mapping = self.outputs[metrics.output]
        raw_target = record[mapping["column_index"]]
        raw_actual = TrainingDataIO.unscale_value(metrics.actual, mapping["calibration"], self.text)
        return {
            "mean_squared_error": metrics.mean_squared_error,
            "maximum_absolute_error": metrics.maximum_absolute_error,
            "maximum_error_details": {
                "record": metrics.record + 1,
                "output": mapping["column_name"],
                "unit": mapping.get("unit", ""),
                "data_type": mapping.get("data_type", "analog"),
                "raw_target": raw_target,
                "raw_actual": raw_actual,
                "raw_error": abs(raw_target - raw_actual),
                "internal_error": metrics.maximum_absolute_error,
            },
        }

    def advance_epoch(self, epoch, seed):
        order = list(range(len(self.records)))
        epoch_seed = (int(seed or 0) + epoch * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        random.Random(epoch_seed).shuffle(order)
        self.order_buffer[:] = order
        status = self.train_epoch(c.byref(self.problem), self.order_buffer, self.parameters,
                                  c.byref(self.step), c.byref(self.metrics))
        if status:
            raise ValueError(f"Rust training / Rust-Training: Ep. {epoch}, error code {status}.")

    def synchronize_parameters(self):
        split = len(self.edges)
        for edge, parameter in zip(self.edges, self.parameters[:split]):
            edge.set_weight(parameter.value, update_display=False)
        for node, parameter in zip(self.nodes, self.parameters[split:]):
            node.bias = parameter.value

    def store_optimizer_state(self):
        split = len(self.edges)
        edges = [(str(edge.id), parameter) for edge, parameter in zip(self.edges, self.parameters[:split])]
        biases = [(str(node.id), parameter) for node, parameter in zip(self.nodes, self.parameters[split:])
                  if node.neuron_type != NeuronType.INPUT]
        if self.solver == "adam":
            self.network.restore_optimizer_state({
                "solver": "adam", "step": self.step.value,
                "connections": {key: {"m": value.m, "v": value.v} for key, value in edges},
                "biases": {key: {"m": value.m, "v": value.v} for key, value in biases},
            })
        else:
            self.network.restore_momentum_state({
                "connections": {key: value.m for key, value in edges},
                "biases": {key: value.m for key, value in biases},
            })
