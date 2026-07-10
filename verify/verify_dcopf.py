"""
第二步：极热无风场景源-荷失衡最优调度（DC-OPF/MIQP）的 Python 验证实现。

基准源-荷失衡 OPF 不施加爬坡约束，因为此时未知上一时刻各机组出力。
故障后 OPF 可通过 ``use_ramp=True`` 与 ``pg0_override=baseline['Pg']`` 将
基准 OPF 出力作为爬坡约束的基准出力。

火电机组具有启停状态 u_i∈{0,1}：
    u_i * Pdisp_min_i <= Pg_i <= u_i * Pdisp_max_i

水电不设置启停变量，仍为连续调度区间。由于常见开源环境未必包含 MIQP
求解器，Python 验证侧枚举 6 台火电机组的启停状态(2^6=64)，每个组合下
求解连续 QP，并取目标函数最小的可行解。
"""

from itertools import product

import numpy as np
import cvxpy as cp

import case_data as cd
import models as md


OPTIMAL_STATUSES = {'optimal', 'optimal_inaccurate'}


def _as_bool_mask(mask, size, name):
    if mask is None:
        return np.ones(size, dtype=bool)
    arr = np.asarray(mask, dtype=bool).reshape(-1)
    if arr.size != size:
        raise ValueError(f'{name} 长度应为 {size}，当前为 {arr.size}')
    return arr


def _source_bounds(gens, sc, use_ramp, pg0_override, gen_available):
    ng = len(gens)
    pmax = np.zeros(ng)
    pmin = np.zeros(ng)
    lb_pg = np.zeros(ng)
    ub_pg = np.zeros(ng)
    pg0 = None if pg0_override is None else np.asarray(pg0_override, dtype=float).reshape(-1)
    if pg0 is not None and pg0.size != ng:
        raise ValueError(f'pg0_override 长度应为 {ng}，当前为 {pg0.size}')

    for g, gen in enumerate(gens):
        pmax[g] = md.source_pmax(gen, sc)
        pmin[g] = md.source_pmin(gen, pmax[g])
        lb_pg[g], ub_pg[g] = md.source_dispatch_bounds(
            gen,
            cd.GEN_OPS[g],
            sc,
            pmax[g],
            pmin[g],
            use_ramp=use_ramp,
            pg0_override=None if pg0 is None else pg0[g],
        )
        if not gen_available[g]:
            pmax[g] = 0.0
            pmin[g] = 0.0
            lb_pg[g] = 0.0
            ub_pg[g] = 0.0
    return pmax, pmin, lb_pg, ub_pg


def build_and_solve(
    verbose=True,
    use_ramp=False,
    pg0_override=None,
    gen_available=None,
    branch_available=None,
    fixed_unit_on=None,
):
    """求解基准或故障后 DC-OPF。

    Parameters
    ----------
    use_ramp:
        False 表示忽略爬坡约束（基准源-荷失衡 OPF）；True 表示施加爬坡。
    pg0_override:
        use_ramp=True 时的爬坡基准出力，故障后 OPF 应传入基准 OPF 的 Pg。
    gen_available, branch_available:
        故障场景掩码；False 表示故障/退出。
    fixed_unit_on:
        可选的 ng 维启停状态。若提供，则固定火电 u_i，不枚举；非火电忽略。
    """
    sc = cd.SCENARIO
    base = cd.BASE_MVA

    buses = list(range(1, cd.N_BUS + 1))
    bidx = {b: i for i, b in enumerate(buses)}
    nb = len(buses)

    gens = cd.GENS
    ng = len(gens)
    nbr = len(cd.BRANCHES)
    gen_available = _as_bool_mask(gen_available, ng, 'gen_available')
    branch_available = _as_bool_mask(branch_available, nbr, 'branch_available')

    load_buses = sorted(cd.PD0.keys())
    nlevel = len(sc['level_frac'])

    pmax, pmin, lb_pg, ub_pg = _source_bounds(
        gens, sc, use_ramp, pg0_override, gen_available
    )
    thermal_idx = [g for g, gen in enumerate(gens) if gen[1] == 'thermal']

    D_level = {}
    D_total = {}
    for b in load_buses:
        d = md.bus_demand(cd.PD0[b], sc)
        D_total[b] = d
        D_level[b] = md.split_by_level(d, sc)

    Bbus = np.zeros((nb, nb))
    branch_rows = []  # (i, j, b_series, rateA, active)
    for ell, (f, t, x, rateA, ratio) in enumerate(cd.BRANCHES):
        tap = ratio if ratio != 0.0 else 1.0
        b_series = 1.0 / (x * tap)
        i, j = bidx[f], bidx[t]
        active = bool(branch_available[ell])
        if active:
            Bbus[i, i] += b_series
            Bbus[j, j] += b_series
            Bbus[i, j] -= b_series
            Bbus[j, i] -= b_series
        branch_rows.append((i, j, b_series, rateA, active))

    c2 = np.array([g[5] for g in gens])
    c1 = np.array([g[6] for g in gens])
    voll = np.array(sc['voll'])

    if fixed_unit_on is not None:
        unit = np.asarray(fixed_unit_on, dtype=float).reshape(-1)
        if unit.size != ng:
            raise ValueError(f'fixed_unit_on 长度应为 {ng}，当前为 {unit.size}')
        commitments = [tuple(0 if not gen_available[g] else int(round(unit[g])) for g in thermal_idx)]
    else:
        commitments = []
        for bits in product([0, 1], repeat=len(thermal_idx)):
            ok = True
            for k, g in enumerate(thermal_idx):
                if not gen_available[g] and bits[k] != 0:
                    ok = False
                    break
            if ok:
                commitments.append(bits)

    def solve_for_commitment(commitment):
        Pg = cp.Variable(ng, name='Pg')
        theta = cp.Variable(nb, name='theta')
        shed = cp.Variable((len(load_buses), nlevel), name='shed')

        constraints = []
        commitment_map = {g: commitment[k] for k, g in enumerate(thermal_idx)}
        for g in range(ng):
            if g in commitment_map:
                if commitment_map[g] == 1:
                    constraints += [Pg[g] >= lb_pg[g], Pg[g] <= ub_pg[g]]
                else:
                    constraints += [Pg[g] == 0]
            else:
                constraints += [Pg[g] >= lb_pg[g], Pg[g] <= ub_pg[g]]

        Dmat = np.array([D_level[b] for b in load_buses])
        constraints += [shed >= 0, shed <= Dmat]
        constraints += [theta[bidx[cd.SLACK_BUS]] == 0]

        gen_at_bus = {b: [] for b in buses}
        for gg, gen in enumerate(gens):
            gen_at_bus[gen[0]].append(gg)

        lb_pos = {b: i for i, b in enumerate(load_buses)}
        inj = []
        for b in buses:
            expr = 0
            for gg in gen_at_bus[b]:
                expr = expr + Pg[gg]
            if b in D_total:
                expr = expr - (D_total[b] - cp.sum(shed[lb_pos[b], :]))
            inj.append(expr)
        constraints += [Bbus @ theta == cp.hstack(inj) / base]

        for (i, j, b_series, rateA, active) in branch_rows:
            if not active:
                continue
            flow = base * b_series * (theta[i] - theta[j])
            constraints += [flow <= rateA, flow >= -rateA]

        gen_cost_expr = cp.sum(cp.multiply(c2, cp.square(Pg)) + cp.multiply(c1, Pg))
        shed_cost_expr = cp.sum(shed @ voll)
        prob = cp.Problem(cp.Minimize(gen_cost_expr + shed_cost_expr), constraints)
        prob.solve(solver=cp.CLARABEL, verbose=False)
        return prob, Pg, theta, shed, gen_cost_expr, shed_cost_expr

    best = None
    for commitment in commitments:
        prob, Pg, theta, shed, gen_cost_expr, shed_cost_expr = solve_for_commitment(commitment)
        if prob.status not in OPTIMAL_STATUSES:
            continue
        if best is None or prob.value < best['obj']:
            unit_on = np.ones(ng)
            for k, g in enumerate(thermal_idx):
                unit_on[g] = commitment[k]
            best = {
                'status': prob.status,
                'obj': prob.value,
                'Pg': Pg.value,
                'theta': theta.value,
                'shed': shed.value,
                'gen_cost': gen_cost_expr.value,
                'shed_cost': shed_cost_expr.value,
                'unit_on': unit_on,
            }

    if best is None:
        best = {
            'status': 'infeasible',
            'obj': np.nan,
            'Pg': np.full(ng, np.nan),
            'theta': np.full(nb, np.nan),
            'shed': np.full((len(load_buses), nlevel), np.nan),
            'gen_cost': np.nan,
            'shed_cost': np.nan,
            'unit_on': np.full(ng, np.nan),
        }

    branch_flow = None
    if best['theta'] is not None and np.all(np.isfinite(best['theta'])):
        branch_flow = np.zeros(nbr)
        for ell, (i, j, b_series, _rateA, active) in enumerate(branch_rows):
            if active:
                branch_flow[ell] = base * b_series * (best['theta'][i] - best['theta'][j])

    result = {
        'status': best['status'],
        'obj': best['obj'],
        'Pg': best['Pg'],
        'theta': best['theta'],
        'shed': best['shed'],
        'pmax': pmax,
        'pmin': pmin,
        'lb_pg': lb_pg,
        'ub_pg': ub_pg,
        'gens': gens,
        'load_buses': load_buses,
        'D_total': D_total,
        'D_level': D_level,
        'gen_cost': best['gen_cost'],
        'shed_cost': best['shed_cost'],
        'branch_rows': branch_rows,
        'bidx': bidx,
        'unit_on': best['unit_on'],
        'thermal_idx': thermal_idx,
        'gen_available': gen_available,
        'branch_available': branch_available,
        'branch_flow': branch_flow,
        'use_ramp': use_ramp,
        'pg0_override': None if pg0_override is None else np.asarray(pg0_override, dtype=float),
    }
    if verbose:
        report(result, sc)
    return result


def report(r, sc):
    gens = r['gens']
    Pg = r['Pg']
    sep = '=' * 74
    print(sep)
    print('极热无风场景 直流最优潮流（DC-OPF/MIQP）求解结果  [Python/cvxpy 验证]')
    print(sep)
    print(f"求解状态        : {r['status']}")
    print(f"是否施加爬坡约束: {r['use_ramp']}")
    print(f"目标函数最优值  : {r['obj']:.2f}  ($/h)")
    print(f"  发电成本      : {r['gen_cost']:.2f}  ($/h)")
    print(f"  切负荷惩罚成本: {r['shed_cost']:.2f}  ($/h)")
    print('-' * 74)

    print('源侧机组出力 (MW):')
    print(f"{'机组':<6}{'母线':<5}{'类型':<9}{'u':>4}{'额定':>8}{'Pmin':>8}{'下界':>8}{'上界':>8}{'出力Pg':>10}{'利用率':>8}")
    tot_pg = 0.0
    type_cn = {'thermal': '火电', 'hydro': '水电', 'wind': '风电', 'solar': '光伏'}
    for g, gen in enumerate(gens):
        bus, gtype, fuel, prated = gen[0], gen[1], gen[2], gen[3]
        name = type_cn[gtype] + (f"-{fuel}" if fuel else '')
        util = Pg[g] / prated * 100 if prated > 0 and np.isfinite(Pg[g]) else 0
        u_show = f"{r['unit_on'][g]:.0f}" if gtype == 'thermal' and np.isfinite(r['unit_on'][g]) else "-"
        print(f"G{g+1:<5}{bus:<5}{name:<9}{u_show:>4}{prated:>8.0f}{r['pmin'][g]:>8.1f}"
              f"{r['lb_pg'][g]:>8.1f}{r['ub_pg'][g]:>8.1f}{Pg[g]:>10.1f}{util:>7.1f}%")
        if np.isfinite(Pg[g]):
            tot_pg += Pg[g]
    print(f"{'合计总发电':<37}{r['ub_pg'].sum():>8.1f}{tot_pg:>10.1f}")
    print('-' * 74)

    tot_demand = sum(r['D_total'].values())
    shed = r['shed']
    tot_shed = np.nansum(shed)
    print('荷侧切负荷 (MW):')
    print(f"  极热修正后总需求 : {tot_demand:.1f}")
    print(f"  总切负荷         : {tot_shed:.1f}  ({tot_shed/tot_demand*100:.2f}%)")
    for k, nm in enumerate(cd.LEVEL_NAMES):
        print(f"    {nm:<12} VOLL={sc['voll'][k]:>7.0f}  切除={np.nansum(shed[:, k]):>8.1f} MW")
    print('-' * 74)

    print('系统功率平衡校验 (MW):')
    print(f"  总发电  {tot_pg:.1f}  =?=  净需求 {tot_demand - tot_shed:.1f}  "
          f"(残差 {tot_pg-(tot_demand-tot_shed):+.3f})")

    n_overload = 0
    n_outaged = 0
    max_load_pct = 0.0
    if r['branch_flow'] is not None:
        for ell, (_i, _j, _b_series, rateA, active) in enumerate(r['branch_rows']):
            if not active:
                n_outaged += 1
                continue
            pct = abs(r['branch_flow'][ell]) / rateA * 100
            max_load_pct = max(max_load_pct, pct)
            if pct > 100.0 + 1e-6:
                n_overload += 1
    print(f"  线路最大负载率 {max_load_pct:.1f}%，越限线路数 {n_overload}，退出线路数 {n_outaged}")
    print(sep)


if __name__ == '__main__':
    build_and_solve(verbose=True, use_ramp=False)
