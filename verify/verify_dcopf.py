"""
第二步：极热无风场景源-荷失衡最优调度（直流最优潮流）—— Python 验证实现。

目标函数:  min  发电成本 + 切负荷惩罚成本
           min  sum_g (c2_g*Pg^2 + c1_g*Pg) + sum_{j,k} VOLL_k * shed_{j,k}

约束:
  (1) 直流潮流节点功率平衡:  B_bus * theta = Pinj_pu
  (2) 机组出力区间(含高温降容):  Pmin_g <= Pg <= Pmax_g(T)
  (3) 切负荷区间:  0 <= shed_{j,k} <= D_{j,k}(T)
  (4) 线路潮流约束:  -rateA_l <= f_l <= rateA_l
  (5) 平衡节点相角:  theta_slack = 0

本脚本用 cvxpy(开源 QP 求解器) 复现 MATLAB+Gurobi 模型，用于在无 MATLAB/
Gurobi 环境下校验模型可行性与结果合理性。两套实现使用同一套数据
(case_data.py)，最优目标值/出力应当一致。
"""

import numpy as np
import cvxpy as cp

import case_data as cd
import models as md


def build_and_solve(verbose=True):
    sc = cd.SCENARIO
    base = cd.BASE_MVA

    # ---- 节点 / 机组 / 负荷索引 ----
    buses = list(range(1, cd.N_BUS + 1))
    bidx = {b: i for i, b in enumerate(buses)}
    nb = len(buses)

    gens = cd.GENS
    ng = len(gens)

    # 负荷节点（Pd0>0）
    load_buses = sorted(cd.PD0.keys())
    nlevel = len(sc['level_frac'])

    # ---- 源侧：各机组极热降容后的出力区间 ----
    pmax = np.zeros(ng)
    pmin = np.zeros(ng)
    for g, gen in enumerate(gens):
        pmax_rated = gen[3]
        pmin_frac = gen[4]
        pmax[g] = md.source_pmax(gen, sc)
        # 火电/水电最小技术出力按额定容量的比例；风光最小为 0（可弃风弃光）
        # 注意：当高温降容后 Pmax < 名义 Pmin 时，取 Pmin = min(Pmin, Pmax)
        pmin[g] = min(pmin_frac * pmax_rated, pmax[g])

    # ---- 荷侧：温度修正需求 + 等级拆分 ----
    # D_level[bus][k]
    D_level = {}
    D_total = {}
    for b in load_buses:
        d = md.bus_demand(cd.PD0[b], sc)
        D_total[b] = d
        D_level[b] = md.split_by_level(d, sc)

    # ---- 直流潮流 B_bus 矩阵 与 支路灵敏度 ----
    Bbus = np.zeros((nb, nb))
    branch_rows = []  # (i, j, b_series, rateA) 用于线路潮流约束
    for (f, t, x, rateA, ratio) in cd.BRANCHES:
        tap = ratio if ratio != 0.0 else 1.0
        b_series = 1.0 / (x * tap)
        i, j = bidx[f], bidx[t]
        Bbus[i, i] += b_series
        Bbus[j, j] += b_series
        Bbus[i, j] -= b_series
        Bbus[j, i] -= b_series
        branch_rows.append((i, j, b_series, rateA))

    # ---- 决策变量 ----
    Pg = cp.Variable(ng, name='Pg')
    theta = cp.Variable(nb, name='theta')
    # 切负荷: 字典 (bus,k) -> 变量；用矩阵更紧凑
    shed = cp.Variable((len(load_buses), nlevel), name='shed')

    constraints = []

    # (2) 机组出力区间
    constraints += [Pg >= pmin, Pg <= pmax]

    # (3) 切负荷区间
    Dmat = np.array([D_level[b] for b in load_buses])  # (nL, nlevel)
    constraints += [shed >= 0, shed <= Dmat]

    # (5) 平衡节点相角 = 0
    constraints += [theta[bidx[cd.SLACK_BUS]] == 0]

    # (1) 节点功率平衡:  Bbus*theta(p.u.) = (P_gen - P_netload)/base
    #     P_netload_n = D_n - sum_k shed_{n,k}
    gen_at_bus = {b: [] for b in buses}
    for g, gen in enumerate(gens):
        gen_at_bus[gen[0]].append(g)

    lb_pos = {b: i for i, b in enumerate(load_buses)}

    inj = []  # 每个节点注入(MW)表达式
    for b in buses:
        expr = 0
        for g in gen_at_bus[b]:
            expr = expr + Pg[g]
        if b in D_total:
            shed_sum = cp.sum(shed[lb_pos[b], :])
            expr = expr - (D_total[b] - shed_sum)
        inj.append(expr)
    inj = cp.hstack(inj)

    constraints += [Bbus @ theta == inj / base]

    # (4) 线路潮流约束:  f_l = base * b_series * (theta_i - theta_j)
    for (i, j, b_series, rateA) in branch_rows:
        flow = base * b_series * (theta[i] - theta[j])
        constraints += [flow <= rateA, flow >= -rateA]

    # ---- 目标函数 ----
    c2 = np.array([g[5] for g in gens])
    c1 = np.array([g[6] for g in gens])
    voll = np.array(sc['voll'])

    gen_cost = cp.sum(cp.multiply(c2, cp.square(Pg)) + cp.multiply(c1, Pg))
    shed_cost = cp.sum(shed @ voll)
    objective = cp.Minimize(gen_cost + shed_cost)

    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.CLARABEL, verbose=False)

    result = {
        'status': prob.status,
        'obj': prob.value,
        'Pg': Pg.value,
        'theta': theta.value,
        'shed': shed.value,
        'pmax': pmax, 'pmin': pmin,
        'gens': gens, 'load_buses': load_buses,
        'D_total': D_total, 'D_level': D_level,
        'gen_cost': gen_cost.value, 'shed_cost': shed_cost.value,
        'branch_rows': branch_rows, 'bidx': bidx,
    }
    if verbose:
        report(result, sc)
    return result


def report(r, sc):
    gens = r['gens']
    Pg = r['Pg']
    pmax = r['pmax']
    sep = '=' * 74
    print(sep)
    print('极热无风场景 直流最优潮流（DC-OPF）求解结果  [Python/cvxpy 验证]')
    print(sep)
    print(f"求解状态        : {r['status']}")
    print(f"目标函数最优值  : {r['obj']:.2f}  ($/h)")
    print(f"  发电成本      : {r['gen_cost']:.2f}  ($/h)")
    print(f"  切负荷惩罚成本: {r['shed_cost']:.2f}  ($/h)")
    print('-' * 74)

    # 源侧
    print('源侧机组出力 (MW):')
    print(f"{'机组':<6}{'母线':<5}{'类型':<9}{'额定':>8}{'高温Pmax':>10}{'出力Pg':>10}{'利用率':>8}")
    tot_pg = 0.0
    type_cn = {'thermal': '火电', 'hydro': '水电', 'wind': '风电', 'solar': '光伏'}
    for g, gen in enumerate(gens):
        bus, gtype, fuel, prated = gen[0], gen[1], gen[2], gen[3]
        name = type_cn[gtype] + (f"-{fuel}" if fuel else '')
        util = Pg[g] / prated * 100 if prated > 0 else 0
        print(f"G{g+1:<5}{bus:<5}{name:<9}{prated:>8.0f}{pmax[g]:>10.1f}{Pg[g]:>10.1f}{util:>7.1f}%")
        tot_pg += Pg[g]
    print(f"{'合计总发电':<29}{pmax.sum():>10.1f}{tot_pg:>10.1f}")
    print('-' * 74)

    # 荷侧
    tot_demand = sum(r['D_total'].values())
    shed = r['shed']
    tot_shed = shed.sum()
    print('荷侧切负荷 (MW):')
    print(f"  极热修正后总需求 : {tot_demand:.1f}")
    print(f"  总切负荷         : {tot_shed:.1f}  ({tot_shed/tot_demand*100:.2f}%)")
    for k, nm in enumerate(cd.LEVEL_NAMES):
        print(f"    {nm:<12} VOLL={sc['voll'][k]:>7.0f}  切除={shed[:,k].sum():>8.1f} MW")
    print('-' * 74)

    # 功率平衡校验
    print('系统功率平衡校验 (MW):')
    print(f"  总发电  {tot_pg:.1f}  =?=  净需求 {tot_demand - tot_shed:.1f}  "
          f"(残差 {tot_pg-(tot_demand-tot_shed):+.3f})")

    # 线路潮流越限检查
    base = cd.BASE_MVA
    theta = r['theta']
    n_overload = 0
    max_load_pct = 0.0
    for (i, j, b_series, rateA) in r['branch_rows']:
        flow = base * b_series * (theta[i] - theta[j])
        pct = abs(flow) / rateA * 100
        max_load_pct = max(max_load_pct, pct)
        if pct > 100.0 + 1e-6:
            n_overload += 1
    print(f"  线路最大负载率 {max_load_pct:.1f}%，越限线路数 {n_overload}")
    print(sep)


if __name__ == '__main__':
    import case_data as cd  # noqa
    build_and_solve(verbose=True)
