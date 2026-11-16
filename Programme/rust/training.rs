// Copyright © 2026 Helwig Fülling
// SPDX-License-Identifier: GPL-3.0-only

use std::slice;

#[repr(C)]
struct Node {
    begin_in: usize,
    end_in: usize,
    begin_out: usize,
    end_out: usize,
    activation: u32,
    kind: u32, // input=0, hidden=1, output=2
}

#[repr(C)]
struct Edge {
    source: usize,
    target: usize,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct Parameter {
    value: f64,
    m: f64,
    v: f64,
}

impl Parameter {
    fn update_sgd(&mut self, base: f64, momentum: f64) -> bool {
        let velocity = if momentum == 0.0 { base } else { base + momentum * self.m };
        let value = self.value + velocity;
        if !velocity.is_finite() || !value.is_finite() { return false; }
        let m = if momentum == 0.0 { 0.0 } else { velocity };
        *self = Self { value, m, v: 0.0 };
        true
    }

    fn update_adam(&mut self, gradient: f64, rate: f64, correction1: f64, correction2: f64, sqrt: extern "C" fn(f64) -> f64) -> bool {
        const BETA1: f64 = 0.9;
        const BETA2: f64 = 0.999;
        let m = BETA1 * self.m + (1.0 - BETA1) * gradient;
        let v = BETA2 * self.v + (1.0 - BETA2) * gradient * gradient;
        let m_hat = m / correction1;
        let v_hat = v / correction2;
        let value = self.value + (-rate * m_hat / (sqrt(v_hat) + 1e-8));
        if ![gradient, m, v, m_hat, v_hat, value].into_iter().all(f64::is_finite) {
            return false;
        }
        *self = Self { value, m, v };
        true
    }
}

#[repr(C)]
struct Problem {
    nodes: *const Node,
    node_count: usize,
    edges: *const Edge,
    edge_count: usize,
    incoming: *const usize,
    outgoing: *const usize,
    input_ids: *const usize,
    input_count: usize,
    output_ids: *const usize,
    output_count: usize,
    records: *const f64,
    record_count: usize,
    rate: f64,
    momentum: f64,
    solver: u32,
    tanh: extern "C" fn(f64) -> f64,
    exp: extern "C" fn(f64) -> f64,
    pow: extern "C" fn(f64, f64) -> f64,
    sqrt: extern "C" fn(f64) -> f64,
}

fn sigmoid(p: &Problem, z: f64) -> f64 {
    if z >= 0.0 {
        1.0 / (1.0 + (p.exp)(-z))
    } else {
        let exp = (p.exp)(z);
        exp / (1.0 + exp)
    }
}

fn derivative(p: &Problem, activation: u32, z: f64) -> f64 {
    match activation {
        1 => 1.0,
        2 => if z > 0.0 { 1.0 } else { 0.0 },
        3 => { let value = sigmoid(p, z); value * (1.0 - value) },
        4 => { let value = (p.tanh)(z); 1.0 - value * value },
        _ => f64::NAN,
    }
}

#[repr(C)]
struct Metrics {
    mean_squared_error: f64,
    maximum_absolute_error: f64,
    record: usize,
    output: usize,
    actual: f64,
}

#[unsafe(no_mangle)]
unsafe extern "C" fn train_epoch(
    problem: *const Problem, order: *const usize, params: *mut Parameter,
    step: *mut usize, metrics: *mut Metrics,
) -> u32 {
    // The test caller owns valid arrays with the declared dimensions.
    let p = unsafe { &*problem };
    let nodes = unsafe { slice::from_raw_parts(p.nodes, p.node_count) };
    let edges = unsafe { slice::from_raw_parts(p.edges, p.edge_count) };
    let incoming = unsafe { slice::from_raw_parts(p.incoming, p.edge_count) };
    let outgoing = unsafe { slice::from_raw_parts(p.outgoing, p.edge_count) };
    let input_ids = unsafe { slice::from_raw_parts(p.input_ids, p.input_count) };
    let output_ids = unsafe { slice::from_raw_parts(p.output_ids, p.output_count) };
    let stride = p.input_count + p.output_count;
    let records = unsafe { slice::from_raw_parts(p.records, p.record_count * stride) };
    let order = unsafe { slice::from_raw_parts(order, p.record_count) };
    let parameters = unsafe { slice::from_raw_parts_mut(params, p.edge_count + p.node_count) };
    let step = unsafe { &mut *step };
    let metrics = unsafe { &mut *metrics };
    let mut values = vec![0.0; p.node_count];
    let mut sums = vec![0.0; p.node_count];
    let mut deltas = vec![0.0; p.node_count];

    let forward = |input: &[f64], values: &mut [f64], sums: &mut [f64], parameters: &[Parameter]| {
        for (&id, &value) in input_ids.iter().zip(input) {
            if !value.is_finite() { return false; }
            values[id] = value;
        }
        for (id, node) in nodes.iter().enumerate() {
            if node.kind == 0 { continue; }
            let mut weighted_sum = 0.0;
            for &edge in &incoming[node.begin_in..node.end_in] {
                weighted_sum += values[edges[edge].source] * parameters[edge].value;
            }
            let z = weighted_sum + parameters[p.edge_count + id].value;
            let value = match node.activation {
                1 => z,
                2 => z.max(0.0),
                3 => sigmoid(p, z),
                4 => (p.tanh)(z),
                _ => f64::NAN,
            };
            if !z.is_finite() || !value.is_finite() { return false; }
            sums[id] = z;
            values[id] = value;
        }
        true
    };

    for &row in order {
        let data = &records[row * stride..(row + 1) * stride];
        if !forward(&data[..p.input_count], &mut values, &mut sums, parameters) { return 1; }
        for (&id, &target) in output_ids.iter().zip(&data[p.input_count..]) {
            deltas[id] = (target - values[id]) * derivative(p, nodes[id].activation, sums[id]);
            if !deltas[id].is_finite() { return 2; }
        }
        for (id, node) in nodes.iter().enumerate().rev() {
            if node.kind != 1 { continue; }
            let mut weighted_delta = 0.0;
            for &edge in &outgoing[node.begin_out..node.end_out] {
                weighted_delta += parameters[edge].value * deltas[edges[edge].target];
            }
            deltas[id] = weighted_delta * derivative(p, node.activation, sums[id]);
            if !deltas[id].is_finite() { return 3; }
        }

        if p.solver == 1 && *step >= (1usize << 53) { return 8; }
        *step += 1;
        if p.solver == 1 {
            let correction1 = 1.0 - (p.pow)(0.9, *step as f64);
            let correction2 = 1.0 - (p.pow)(0.999, *step as f64);
            for (id, edge) in edges.iter().enumerate() {
                let gradient = -deltas[edge.target] * values[edge.source];
                if !parameters[id].update_adam(gradient, p.rate, correction1, correction2, p.sqrt) { return 4; }
            }
            for (id, node) in nodes.iter().enumerate() {
                if node.kind == 0 { continue; }
                if !parameters[p.edge_count + id].update_adam(-deltas[id], p.rate, correction1, correction2, p.sqrt) {
                    return 5;
                }
            }
        } else {
            for (id, edge) in edges.iter().enumerate() {
                let base = p.rate * deltas[edge.target] * values[edge.source];
                if !parameters[id].update_sgd(base, p.momentum) { return 4; }
            }
            for (id, node) in nodes.iter().enumerate() {
                if node.kind == 0 { continue; }
                if !parameters[p.edge_count + id].update_sgd(p.rate * deltas[id], p.momentum) {
                    return 5;
                }
            }
        }
    }

    let mut sum = 0.0;
    let mut maximum = 0.0_f64;
    for (record, data) in records.chunks_exact(stride).enumerate() {
        if !forward(&data[..p.input_count], &mut values, &mut sums, parameters) { return 6; }
        for (output, (&id, &target)) in output_ids.iter().zip(&data[p.input_count..]).enumerate() {
            let actual = values[id];
            let error = target - actual;
            sum += error * error;
            if (record == 0 && output == 0) || error.abs() > maximum {
                maximum = error.abs();
                metrics.record = record;
                metrics.output = output;
                metrics.actual = actual;
            }
        }
    }
    if !sum.is_finite() { return 7; }
    metrics.mean_squared_error = sum / (p.record_count * p.output_count) as f64;
    metrics.maximum_absolute_error = maximum;
    0
}
