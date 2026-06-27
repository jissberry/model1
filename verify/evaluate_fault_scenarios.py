"""遍历蒙特卡洛故障场景并求解故障后 DC-OPF。

输入场景向量顺序为 [G1..G10, L1..L46, T1..T29]，0=故障，1=良好。
故障映射规则：
  * 发电机故障：该机组 Pg 上下界均置为 0；
  * 线路故障：该支路退出 DC 网络，结果潮流记为 0；
  * 节点变压器故障：该非电源节点相连支路全部退出。若该节点有负荷，
    节点功率平衡会使其负荷在 OPF 中被切除。
"""

import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

import case_data as cd
import mc_fault_scenarios
import verify_dcopf


SCENARIO_CSV = Path('/workspace/verify/fault_scenarios_2000.csv')
OUT_SUMMARY_CSV = Path('/workspace/verify/fault_scenario_opf_summary.csv')
OUT_BUS_SHED_CSV = Path('/workspace/verify/fault_scenario_bus_shed.csv')
OUT_JSON = Path('/workspace/verify/fault_scenario_opf_stats.json')

OPTIMAL_STATUSES = {'optimal', 'optimal_inaccurate'}


def transformer_buses():
    """T1..T29 对应所有非发电节点的升序列表。"""
    gen_buses = {gen[0] for gen in cd.GENS}
    buses = [bus for bus in range(1, cd.N_BUS + 1) if bus not in gen_buses]
    if len(buses) != 29:
        raise ValueError(f'期望 29 个非电源节点变压器，当前为 {len(buses)}')
    return buses


def ensure_scenarios(path=SCENARIO_CSV):
    if not path.exists():
        mc_fault_scenarios.generate(verbose=False)


def read_scenarios(path=SCENARIO_CSV):
    ensure_scenarios(path)
    with path.open('r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        labels = header[1:]
        rows = []
        scenario_ids = []
        for row in reader:
            scenario_ids.append(int(row[0]))
            rows.append([int(x) for x in row[1:]])
    states = np.asarray(rows, dtype=np.uint8)
    if states.ndim != 2 or states.shape[1] != 85:
        raise ValueError(f'期望场景矩阵为 n x 85，当前形状为 {states.shape}')
    return labels, scenario_ids, states


def availability_from_state(state):
    """把 85 维状态向量转换为发电机/支路可用性掩码。"""
    state = np.asarray(state, dtype=np.uint8)
    if state.size != 85:
        raise ValueError(f'状态向量长度应为 85，当前为 {state.size}')

    gen_available = state[:10].astype(bool)
    direct_branch_available = state[10:56].astype(bool)
    xf_available = state[56:85].astype(bool)

    xf_buses = transformer_buses()
    failed_xf_buses = {
        bus for bus, available in zip(xf_buses, xf_available) if not available
    }

    branch_available = direct_branch_available.copy()
    xf_forced_outages = []
    for idx, (fbus, tbus, _x, _rateA, _ratio) in enumerate(cd.BRANCHES):
        if fbus in failed_xf_buses or tbus in failed_xf_buses:
            if branch_available[idx]:
                xf_forced_outages.append(idx + 1)
            branch_available[idx] = False

    return {
        'gen_available': gen_available,
        'branch_available': branch_available,
        'direct_branch_available': direct_branch_available,
        'xf_available': xf_available,
        'failed_xf_buses': sorted(failed_xf_buses),
        'xf_forced_outages': xf_forced_outages,
    }


def _safe_float(value):
    if value is None:
        return ''
    value = float(value)
    if not np.isfinite(value):
        return ''
    return value


def solve_one(scenario_id, state):
    masks = availability_from_state(state)
    result = verify_dcopf.build_and_solve(
        verbose=False,
        gen_available=masks['gen_available'],
        branch_available=masks['branch_available'],
    )

    gen_faults = np.where(~masks['gen_available'])[0] + 1
    line_faults = np.where(~masks['direct_branch_available'])[0] + 1
    branch_outages = np.where(~masks['branch_available'])[0] + 1
    xf_faults = np.where(~masks['xf_available'])[0] + 1

    status = result['status']
    optimal = status in OPTIMAL_STATUSES
    total_demand = float(sum(result['D_total'].values()))
    load_buses = result['load_buses']

    if optimal:
        shed = np.asarray(result['shed'], dtype=float)
        shed_by_level = shed.sum(axis=0)
        total_shed = float(shed.sum())
        shed_pct = total_shed / total_demand * 100.0
        served = total_demand - total_shed
        bus_shed = shed.sum(axis=1)
    else:
        shed_by_level = np.full(len(cd.SCENARIO['level_frac']), np.nan)
        total_shed = np.nan
        shed_pct = np.nan
        served = np.nan
        bus_shed = np.full(len(load_buses), np.nan)

    summary = {
        'scenario': scenario_id,
        'status': status,
        'objective': _safe_float(result['obj']),
        'gen_cost': _safe_float(result['gen_cost']),
        'shed_cost': _safe_float(result['shed_cost']),
        'total_demand_MW': total_demand,
        'served_load_MW': _safe_float(served),
        'total_shed_MW': _safe_float(total_shed),
        'shed_pct': _safe_float(shed_pct),
        'shed_level1_MW': _safe_float(shed_by_level[0]),
        'shed_level2_MW': _safe_float(shed_by_level[1]),
        'shed_level3_MW': _safe_float(shed_by_level[2]),
        'n_gen_fault': int(gen_faults.size),
        'n_line_fault_direct': int(line_faults.size),
        'n_transformer_fault': int(xf_faults.size),
        'n_branch_outage_total': int(branch_outages.size),
        'n_branch_outage_by_transformer': int(len(masks['xf_forced_outages'])),
        'failed_generators': ';'.join(f'G{i}' for i in gen_faults),
        'failed_lines_direct': ';'.join(f'L{i}' for i in line_faults),
        'failed_transformers': ';'.join(f'T{i}' for i in xf_faults),
        'failed_transformer_buses': ';'.join(str(b) for b in masks['failed_xf_buses']),
        'outaged_branches_total': ';'.join(f'L{i}' for i in branch_outages),
    }

    bus_row = {'scenario': scenario_id, 'status': status}
    for bus, value in zip(load_buses, bus_shed):
        bus_row[f'bus_{bus}_shed_MW'] = _safe_float(value)

    return summary, bus_row


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def percentile(values, q):
    return float(np.percentile(values, q))


def distribution(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {}
    return {
        'count': int(values.size),
        'min': float(np.min(values)),
        'mean': float(np.mean(values)),
        'std': float(np.std(values, ddof=0)),
        'p05': percentile(values, 5),
        'p25': percentile(values, 25),
        'median': percentile(values, 50),
        'p75': percentile(values, 75),
        'p90': percentile(values, 90),
        'p95': percentile(values, 95),
        'p99': percentile(values, 99),
        'max': float(np.max(values)),
    }


def build_stats(summary_rows, baseline_shed):
    status_counts = Counter(row['status'] for row in summary_rows)
    optimal_rows = [row for row in summary_rows if row['status'] in OPTIMAL_STATUSES]

    total_shed = np.array([float(row['total_shed_MW']) for row in optimal_rows])
    level1 = np.array([float(row['shed_level1_MW']) for row in optimal_rows])
    level2 = np.array([float(row['shed_level2_MW']) for row in optimal_rows])
    level3 = np.array([float(row['shed_level3_MW']) for row in optimal_rows])
    incremental = total_shed - baseline_shed

    return {
        'n_scenarios': len(summary_rows),
        'status_counts': dict(status_counts),
        'baseline_total_shed_MW': float(baseline_shed),
        'total_shed_MW': distribution(total_shed),
        'incremental_shed_vs_baseline_MW': distribution(incremental),
        'shed_level1_MW': distribution(level1),
        'shed_level2_MW': distribution(level2),
        'shed_level3_MW': distribution(level3),
        'probability_estimates': {
            'optimal_fraction': len(optimal_rows) / len(summary_rows),
            'any_incremental_shed_fraction': float(np.mean(incremental > 1e-5)) if len(optimal_rows) else None,
            'level1_shed_fraction': float(np.mean(level1 > 1e-5)) if len(optimal_rows) else None,
            'level2_shed_fraction': float(np.mean(level2 > 1e-5)) if len(optimal_rows) else None,
            'level3_shed_fraction': float(np.mean(level3 > 1e-5)) if len(optimal_rows) else None,
        },
    }


def evaluate(path=SCENARIO_CSV, verbose=True):
    _labels, scenario_ids, states = read_scenarios(path)

    baseline = verify_dcopf.build_and_solve(verbose=False)
    baseline_shed = float(np.sum(baseline['shed']))

    summary_rows = []
    bus_rows = []
    for pos, (scenario_id, state) in enumerate(zip(scenario_ids, states), start=1):
        summary, bus_row = solve_one(scenario_id, state)
        summary_rows.append(summary)
        bus_rows.append(bus_row)
        if verbose and (pos == 1 or pos % 100 == 0 or pos == len(scenario_ids)):
            print(f'solved {pos}/{len(scenario_ids)} scenarios')

    summary_fields = list(summary_rows[0].keys())
    bus_fields = list(bus_rows[0].keys())
    write_csv(OUT_SUMMARY_CSV, summary_rows, summary_fields)
    write_csv(OUT_BUS_SHED_CSV, bus_rows, bus_fields)

    stats = build_stats(summary_rows, baseline_shed)
    stats.update({
        'input_csv': str(path),
        'summary_csv': str(OUT_SUMMARY_CSV),
        'bus_shed_csv': str(OUT_BUS_SHED_CSV),
        'state_encoding': {'0': 'fault', '1': 'healthy'},
        'fault_mapping': {
            'generator_fault': 'Pg lower/upper bounds set to 0',
            'line_fault': 'branch removed from DC network; reported flow set to 0',
            'transformer_fault': 'all branches incident to the transformer bus removed',
            'transformer_order': 'T1..T29 are non-generator buses in ascending bus order',
            'transformer_buses': transformer_buses(),
        },
    })
    with OUT_JSON.open('w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f'written {OUT_SUMMARY_CSV}')
        print(f'written {OUT_BUS_SHED_CSV}')
        print(f'written {OUT_JSON}')
        print(json.dumps(stats['total_shed_MW'], ensure_ascii=False, indent=2))
    return stats


if __name__ == '__main__':
    evaluate(verbose=True)
