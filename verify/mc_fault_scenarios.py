"""基于元件故障概率生成蒙特卡洛0/1故障场景。

场景向量顺序固定为：
    [G1..G10, L1..L46, T1..T29]

其中 0 表示故障，1 表示良好。对每个元件 e，若 U(0,1) < p_e，则该次
抽样中元件 e 故障(0)，否则良好(1)。
"""

import csv
import json
from pathlib import Path

import numpy as np

import fault_probability as fp


DEFAULT_N_SCENARIOS = 2000
DEFAULT_SEED = 20260627
OUT_CSV = Path('/workspace/verify/fault_scenarios_2000.csv')
OUT_JSON = Path('/workspace/verify/fault_scenarios_2000_meta.json')


def build_probability_vector(prob_res):
    """返回 labels 与按 [G, L, T] 排列的故障概率向量。"""
    generators = prob_res['generators']
    lines = prob_res['lines']
    transformers = prob_res['transformers']

    n_gen = len(generators)
    n_line = len(lines)
    n_xf = len(transformers)
    if (n_gen, n_line, n_xf) != (10, 46, 29):
        raise ValueError(
            f'期望 10台发电机 + 46条线路 + 29台变压器 = 85维；'
            f'当前为 {n_gen} + {n_line} + {n_xf}'
        )

    labels = []
    probabilities = []

    for g in generators:
        labels.append(f"G{g['G']}")
        probabilities.append(float(g['Pf']))
    for line in lines:
        labels.append(f"L{line['L']}")
        probabilities.append(float(line['Pf']))
    for xf in transformers:
        labels.append(f"T{xf['Tx']}")
        probabilities.append(float(xf['Pf']))

    return labels, np.array(probabilities, dtype=float)


def sample_scenarios(prob_failure, n_scenarios=DEFAULT_N_SCENARIOS, seed=DEFAULT_SEED):
    """生成 n_scenarios x 85 的0/1矩阵：0=故障，1=良好。"""
    rng = np.random.default_rng(seed)
    draws = rng.random((n_scenarios, prob_failure.size))
    return (draws >= prob_failure).astype(np.uint8)


def write_csv(path, labels, states):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['scenario', *labels])
        for i, row in enumerate(states, start=1):
            writer.writerow([i, *row.tolist()])


def write_meta(path, labels, probabilities, states, seed):
    meta = {
        'n_scenarios': int(states.shape[0]),
        'n_components': int(states.shape[1]),
        'seed': int(seed),
        'state_encoding': {'0': 'fault', '1': 'healthy'},
        'vector_order': '[G1..G10, L1..L46, T1..T29]',
        'blocks': {
            'generators': {'start_col_1based': 1, 'end_col_1based': 10},
            'lines': {'start_col_1based': 11, 'end_col_1based': 56},
            'transformers': {'start_col_1based': 57, 'end_col_1based': 85},
        },
        'labels': labels,
        'prob_failure': [float(x) for x in probabilities],
        'sample_first_5_scenarios': states[:5, :].astype(int).tolist(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def generate(n_scenarios=DEFAULT_N_SCENARIOS, seed=DEFAULT_SEED, verbose=True):
    prob_res = fp.compute(verbose=False)
    labels, probabilities = build_probability_vector(prob_res)
    states = sample_scenarios(probabilities, n_scenarios=n_scenarios, seed=seed)

    write_csv(OUT_CSV, labels, states)
    write_meta(OUT_JSON, labels, probabilities, states, seed)

    if verbose:
        print(f'generated {states.shape[0]} scenarios x {states.shape[1]} components')
        print(f'vector order: [G1..G10, L1..L46, T1..T29]')
        print(f'encoding: 0=fault, 1=healthy')
        print(f'csv: {OUT_CSV}')
        print(f'metadata: {OUT_JSON}')
        print(f'first scenario: {states[0, :].astype(int).tolist()}')
    return states


if __name__ == '__main__':
    generate()
