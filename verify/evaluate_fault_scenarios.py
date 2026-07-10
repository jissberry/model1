"""遍历 2000 个热故障场景并求解故障后 DC-OPF。

规则：
  1. 基准源-荷失衡 OPF 不施加爬坡；
  2. 故障后 OPF 施加爬坡，基准出力为步骤1得到的 Pg；
  3. 火电有启停变量，可在孤岛最小出力过剩时关停以保证可解；
  4. 水电无启停变量。
"""

import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np

import case_data as cd
import mc_fault_scenarios
import models as md
import verify_dcopf


SCENARIO_CSV = Path('/workspace/verify/fault_scenarios_2000.csv')
OUT_SUMMARY_CSV = Path('/workspace/verify/fault_scenario_opf_summary.csv')
OUT_JSON = Path('/workspace/verify/fault_scenario_opf_stats.json')
OPTIMAL_STATUSES = {'optimal', 'optimal_inaccurate'}


def transformer_buses():
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
    rows = []
    scenario_ids = []
    with path.open('r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        labels = next(reader)[1:]
        for row in reader:
            scenario_ids.append(int(row[0]))
            rows.append([int(x) for x in row[1:]])
    states = np.asarray(rows, dtype=np.uint8)
    if states.ndim != 2 or states.shape[1] != 85:
        raise ValueError(f'期望场景矩阵为 n x 85，当前为 {states.shape}')
    return labels, scenario_ids, states


def availability_from_state(state):
    state = np.asarray(state, dtype=np.uint8).reshape(-1)
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
        'direct_branch_available': direct_branch_available,
        'branch_available': branch_available,
        'xf_available': xf_available,
        'failed_xf_buses': sorted(failed_xf_buses),
        'xf_forced_outages': xf_forced_outages,
    }


def components(branch_available):
    adj = defaultdict(set)
    for bus in range(1, cd.N_BUS + 1):
        adj[bus] = set()
    for idx, (fbus, tbus, _x, _rateA, _ratio) in enumerate(cd.BRANCHES):
        if branch_available[idx]:
            adj[fbus].add(tbus)
            adj[tbus].add(fbus)

    seen = set()
    comps = []
    for bus in range(1, cd.N_BUS + 1):
        if bus in seen:
            continue
        q = deque([bus])
        seen.add(bus)
        comp = {bus}
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    comp.add(v)
                    q.append(v)
        comps.append(comp)
    return comps


def auto_unit_commitment(gen_available, branch_available, lb_pg):
    """按孤岛检测自动关停过剩火电，减少最小出力导致的不可行。

    初始假设所有可用火电开机；若某孤岛内开机最小出力超过该岛全部负荷，
    则优先关停最小出力较大的火电，直到最小出力不超过可消纳负荷。
    """
    unit_on = np.ones(len(cd.GENS))
    for g, gen in enumerate(cd.GENS):
        if gen[1] == 'thermal':
            unit_on[g] = 1 if gen_available[g] else 0
        elif not gen_available[g]:
            unit_on[g] = 0

    gen_by_bus = {gen[0]: idx for idx, gen in enumerate(cd.GENS)}
    for comp in components(branch_available):
        demand = sum(cd.PD0.get(bus, 0.0) for bus in comp)
        thermal = [
            gen_by_bus[bus]
            for bus in comp
            if bus in gen_by_bus
            and cd.GENS[gen_by_bus[bus]][1] == 'thermal'
            and gen_available[gen_by_bus[bus]]
        ]
        min_gen = sum(lb_pg[g] for g in thermal if unit_on[g] > 0.5)
        if min_gen <= demand + 1e-6:
            continue
        # 过剩孤岛：关停火电。按最小出力从大到小关停，更快消除过剩。
        for g in sorted(thermal, key=lambda x: lb_pg[x], reverse=True):
            unit_on[g] = 0
            min_gen -= lb_pg[g]
            if min_gen <= demand + 1e-6:
                break
    return unit_on


def _safe_float(value):
    if value is None:
        return ''
    value = float(value)
    if not np.isfinite(value):
        return ''
    return value


def solve_one(scenario_id, state, baseline_pg):
    masks = availability_from_state(state)
    # 获取故障后爬坡上下界，用于自动孤岛启停判断；这里不求解OPF。
    lb_pg = np.zeros(len(cd.GENS))
    for g, gen in enumerate(cd.GENS):
        pmax = md.source_pmax(gen, cd.SCENARIO)
        pmin = md.source_pmin(gen, pmax)
        lb_pg[g], _ = md.source_dispatch_bounds(
            gen,
            cd.GEN_OPS[g],
            cd.SCENARIO,
            pmax,
            pmin,
            use_ramp=True,
            pg0_override=baseline_pg[g],
        )
        if not masks['gen_available'][g]:
            lb_pg[g] = 0.0
    fixed_unit_on = auto_unit_commitment(
        masks['gen_available'], masks['branch_available'], lb_pg
    )

    result = verify_dcopf.build_and_solve(
        verbose=False,
        use_ramp=True,
        pg0_override=baseline_pg,
        gen_available=masks['gen_available'],
        branch_available=masks['branch_available'],
        fixed_unit_on=fixed_unit_on,
    )
    # 若自动启停仍不可行，回退为完整火电启停枚举。
    if result['status'] not in OPTIMAL_STATUSES:
        result = verify_dcopf.build_and_solve(
            verbose=False,
            use_ramp=True,
            pg0_override=baseline_pg,
            gen_available=masks['gen_available'],
            branch_available=masks['branch_available'],
            fixed_unit_on=None,
        )

    gen_faults = np.where(~masks['gen_available'])[0] + 1
    line_faults = np.where(~masks['direct_branch_available'])[0] + 1
    xf_faults = np.where(~masks['xf_available'])[0] + 1
    branch_outages = np.where(~masks['branch_available'])[0] + 1

    total_demand = float(sum(result['D_total'].values()))
    optimal = result['status'] in OPTIMAL_STATUSES
    if optimal:
        shed = np.asarray(result['shed'], dtype=float)
        shed_by_level = shed.sum(axis=0)
        total_shed = float(shed.sum())
        served = total_demand - total_shed
        shed_pct = total_shed / total_demand * 100.0
    else:
        shed_by_level = np.full(3, np.nan)
        total_shed = served = shed_pct = np.nan

    return {
        'scenario': scenario_id,
        'status': result['status'],
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
        'n_thermal_off': int(sum(1 for g, gen in enumerate(cd.GENS) if gen[1] == 'thermal' and result['unit_on'][g] < 0.5)),
        'failed_generators': ';'.join(f'G{i}' for i in gen_faults),
        'failed_lines_direct': ';'.join(f'L{i}' for i in line_faults),
        'failed_transformers': ';'.join(f'T{i}' for i in xf_faults),
        'failed_transformer_buses': ';'.join(str(b) for b in masks['failed_xf_buses']),
        'outaged_branches_total': ';'.join(f'L{i}' for i in branch_outages),
        'thermal_unit_on': ';'.join(
            f"G{g+1}={int(round(result['unit_on'][g]))}"
            for g, gen in enumerate(cd.GENS)
            if gen[1] == 'thermal'
        ),
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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
        'p05': float(np.percentile(values, 5)),
        'p25': float(np.percentile(values, 25)),
        'median': float(np.percentile(values, 50)),
        'p75': float(np.percentile(values, 75)),
        'p90': float(np.percentile(values, 90)),
        'p95': float(np.percentile(values, 95)),
        'p99': float(np.percentile(values, 99)),
        'max': float(np.max(values)),
    }


def evaluate(path=SCENARIO_CSV, verbose=True):
    _labels, scenario_ids, states = read_scenarios(path)
    baseline = verify_dcopf.build_and_solve(verbose=False, use_ramp=False)
    baseline_pg = baseline['Pg']
    baseline_shed = float(np.sum(baseline['shed']))

    rows = []
    for pos, (scenario_id, state) in enumerate(zip(scenario_ids, states), start=1):
        rows.append(solve_one(scenario_id, state, baseline_pg))
        if verbose and (pos == 1 or pos % 100 == 0 or pos == len(scenario_ids)):
            print(f'solved {pos}/{len(scenario_ids)} scenarios')

    write_csv(OUT_SUMMARY_CSV, rows)
    optimal_rows = [r for r in rows if r['status'] in OPTIMAL_STATUSES]
    total_shed = np.array([float(r['total_shed_MW']) for r in optimal_rows])
    incremental = total_shed - baseline_shed
    stats = {
        'n_scenarios': len(rows),
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'baseline_uses_ramp': False,
        'fault_opf_uses_ramp': True,
        'fault_ramp_reference': 'baseline OPF Pg',
        'baseline_total_shed_MW': baseline_shed,
        'total_shed_MW': distribution(total_shed),
        'incremental_shed_vs_baseline_MW': distribution(incremental),
        'summary_csv': str(OUT_SUMMARY_CSV),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open('w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f'written {OUT_SUMMARY_CSV}')
        print(f'written {OUT_JSON}')
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    return stats


if __name__ == '__main__':
    evaluate(verbose=True)
