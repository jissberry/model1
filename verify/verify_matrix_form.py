"""
校验 matlab/build_and_solve_dcopf.m 的"矩阵形式"装配是否正确。

本脚本严格按照 build_and_solve_dcopf.m 中的变量排列、约束行、目标 Q/obj、
上下界，原样在 Python 中复现 Gurobi 标准型:

    min  x' Q x + obj' x
    s.t. A x  (sense)  rhs
         lb <= x <= ub

再用同一 QP 求解器求解，并与 verify_dcopf.py 的参考实现对比目标值与机组出力，
从而在无 MATLAB/Gurobi 的环境下验证 MATLAB 矩阵装配的正确性
(变量排序 / 符号 / 索引 / 约束行 是否有误)。
"""

import numpy as np
import cvxpy as cp

import case_data as cd
import models as md
import verify_dcopf as ref


def solve_matrix_form():
    sc = cd.SCENARIO
    base = cd.BASE_MVA
    nb = cd.N_BUS
    gens = cd.GENS
    ng = len(gens)

    load_buses = sorted(cd.PD0.keys())
    nL = len(load_buses)
    nLev = len(sc['level_frac'])

    # ---- 源/荷模型 ----
    Pmax = np.array([md.source_pmax(g, sc) for g in gens])
    Pmin = np.array([md.source_pmin(g, Pmax[i]) for i, g in enumerate(gens)])
    lbPg = np.zeros(ng)
    ubPg = np.zeros(ng)
    for i, g in enumerate(gens):
        lbPg[i], ubPg[i] = md.source_dispatch_bounds(
            g, cd.GEN_OPS[i], sc, Pmax[i], Pmin[i])

    Dtotal = np.array([md.bus_demand(cd.PD0[b], sc) for b in load_buses])
    Dlevel = np.outer(Dtotal, np.array(sc['level_frac']))  # (nL, nLev)

    # ---- 变量索引 (1-based 思路转 0-based) ----
    # x = [Pg(ng); theta(nb); shed( (k)*nL + l )]
    def iPg(g):  # g: 0..ng-1
        return g

    def iTh(n):  # n: 1..nb (bus number)
        return ng + (n - 1)

    def iSh(l, k):  # l:0..nL-1, k:0..nLev-1
        return ng + nb + k * nL + l

    nvar = ng + nb + nL * nLev

    busToLoadPos = {b: l for l, b in enumerate(load_buses)}
    gen_at_bus = {b: [] for b in range(1, nb + 1)}
    for g, gen in enumerate(gens):
        gen_at_bus[gen[0]].append(g)

    # ---- Bbus / bser ----
    Bbus = np.zeros((nb, nb))
    bser = []
    fb = []
    tb = []
    rateA = []
    for (f, t, x, ra, ratio) in cd.BRANCHES:
        tap = ratio if ratio != 0 else 1.0
        b = 1.0 / (x * tap)
        bser.append(b)
        fb.append(f)
        tb.append(t)
        rateA.append(ra)
        Bbus[f - 1, f - 1] += b
        Bbus[t - 1, t - 1] += b
        Bbus[f - 1, t - 1] -= b
        Bbus[t - 1, f - 1] -= b
    nbr = len(bser)

    # ---- 约束三元组 ----
    rows = []
    rhs = []
    sense = []
    r = 0
    A_entries = []  # (row, col, val)

    # (1) 功率平衡 nb 行
    for n in range(1, nb + 1):
        for m in range(1, nb + 1):
            if Bbus[n - 1, m - 1] != 0:
                A_entries.append((r, iTh(m), base * Bbus[n - 1, m - 1]))
        for g in gen_at_bus[n]:
            A_entries.append((r, iPg(g), -1.0))
        Dn = 0.0
        if n in busToLoadPos:
            l = busToLoadPos[n]
            Dn = Dtotal[l]
            for k in range(nLev):
                A_entries.append((r, iSh(l, k), -1.0))
        rhs.append(-Dn)
        sense.append('=')
        r += 1

    # (4) 线路潮流 2*nbr 行
    for l in range(nbr):
        i, j = fb[l], tb[l]
        coef = base * bser[l]
        # f <= rateA
        A_entries.append((r, iTh(i), coef))
        A_entries.append((r, iTh(j), -coef))
        rhs.append(rateA[l]); sense.append('<'); r += 1
        # f >= -rateA
        A_entries.append((r, iTh(i), coef))
        A_entries.append((r, iTh(j), -coef))
        rhs.append(-rateA[l]); sense.append('>'); r += 1

    nrow = r
    A = np.zeros((nrow, nvar))
    for (rr, cc, vv) in A_entries:
        A[rr, cc] += vv
    rhs = np.array(rhs)

    # ---- 上下界 ----
    lb = -np.inf * np.ones(nvar)
    ub = np.inf * np.ones(nvar)
    lb[:ng] = lbPg
    ub[:ng] = ubPg
    lb[iTh(cd.SLACK_BUS)] = 0.0
    ub[iTh(cd.SLACK_BUS)] = 0.0
    for l in range(nL):
        for k in range(nLev):
            lb[iSh(l, k)] = 0.0
            ub[iSh(l, k)] = Dlevel[l, k]

    # ---- 目标 ----
    obj = np.zeros(nvar)
    c2 = np.array([g[5] for g in gens])
    c1 = np.array([g[6] for g in gens])
    obj[:ng] = c1
    for l in range(nL):
        for k in range(nLev):
            obj[iSh(l, k)] = sc['voll'][k]
    Qdiag = np.zeros(nvar)
    Qdiag[:ng] = c2

    # ---- 解 QP: min x'Qx + obj'x ----
    x = cp.Variable(nvar)
    eq = np.array([s == '=' for s in sense])
    le = np.array([s == '<' for s in sense])
    ge = np.array([s == '>' for s in sense])
    cons = [
        A[eq] @ x == rhs[eq],
        A[le] @ x <= rhs[le],
        A[ge] @ x >= rhs[ge],
    ]
    # 有限上下界
    finite_lb = np.isfinite(lb)
    finite_ub = np.isfinite(ub)
    cons += [x[finite_lb] >= lb[finite_lb], x[finite_ub] <= ub[finite_ub]]

    objective = cp.Minimize(cp.quad_form(x, np.diag(Qdiag)) + obj @ x)
    prob = cp.Problem(objective, cons)
    prob.solve(solver=cp.CLARABEL)

    return {
        'status': prob.status,
        'obj': prob.value,
        'Pg': x.value[:ng],
        'shed_total': sum(x.value[ng + nb:]),
    }


if __name__ == '__main__':
    print('>> 求解 MATLAB 矩阵形式复现 ...')
    m = solve_matrix_form()
    print('>> 求解参考实现 (verify_dcopf) ...')
    refr = ref.build_and_solve(verbose=False)

    print('\n', '=' * 70)
    print('矩阵形式 vs 参考实现 对比')
    print('=' * 70)
    print(f"目标值   矩阵形式={m['obj']:.4f}   参考={refr['obj']:.4f}   "
          f"差={abs(m['obj']-refr['obj']):.4e}")
    dPg = np.max(np.abs(m['Pg'] - refr['Pg']))
    print(f"机组出力 最大偏差 = {dPg:.4e} MW")
    print(f"总切负荷 矩阵形式={m['shed_total']:.3f}  参考={refr['shed'].sum():.3f}")
    ok = abs(m['obj'] - refr['obj']) < 1e-2 and dPg < 1e-2
    print('\n结论:', '[OK] 矩阵装配正确 (两实现一致)' if ok else '[FAIL] 不一致，需检查 MATLAB 装配')
    print('=' * 70)
