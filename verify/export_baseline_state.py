"""导出极热场景求解后的完整系统运行基准状态（供文档与 MATLAB 对照）。"""
import json
import numpy as np
import case_data as cd
import verify_dcopf as vd

TYPE_CN = {'thermal': '火电', 'hydro': '水电', 'wind': '风电', 'solar': '光伏'}


def export_baseline_state():
    r = vd.build_and_solve(verbose=False)
    sc = cd.SCENARIO
    base = cd.BASE_MVA
    theta = r['theta']
    Pg = r['Pg']
    shed = r['shed']
    load_buses = r['load_buses']
    gens = cd.GENS
    ng = len(gens)

    gen_at_bus = {b: [] for b in range(1, cd.N_BUS + 1)}
    for g, gen in enumerate(gens):
        gen_at_bus[gen[0]].append(g)
    lb_pos = {b: i for i, b in enumerate(load_buses)}

    # --- 发电机 ---
    generators = []
    for g, gen in enumerate(gens):
        bus, gtype, fuel, prated = gen[0], gen[1], gen[2], gen[3]
        name = TYPE_CN[gtype] + (f'-{fuel}' if fuel else '')
        generators.append({
            'G': g + 1, 'bus': bus, 'type': name, 'Prated': prated,
            'Pmin': float(r['pmin'][g]), 'lb': float(r['lb_pg'][g]),
            'ub': float(r['ub_pg'][g]), 'Pg': float(Pg[g]),
            'util_pct': float(Pg[g] / prated * 100) if prated > 0 else 0.0,
        })

    # --- 支路/变压器潮流 ---
    branches = []
    for idx, (f, t, x, rateA, ratio) in enumerate(cd.BRANCHES):
        tap = ratio if ratio != 0 else 1.0
        bser = 1.0 / (x * tap)
        flow = base * bser * (theta[f - 1] - theta[t - 1])
        pct = abs(flow) / rateA * 100
        branches.append({
            'L': idx + 1, 'fbus': f, 'tbus': t, 'x': x, 'tap': ratio,
            'is_transformer': ratio != 0.0,
            'flow_MW': float(flow), 'rateA': rateA,
            'loading_pct': float(pct),
            'direction': f'{f}→{t}' if flow >= 0 else f'{t}→{f}',
        })

    # --- 节点运行状态 ---
    buses = []
    for b in range(1, cd.N_BUS + 1):
        pg_sum = float(sum(Pg[g] for g in gen_at_bus[b]))
        pd0 = float(cd.PD0.get(b, 0))
        d = float(r['D_total'].get(b, 0))
        if b in lb_pos:
            s1, s2, s3 = [float(x) for x in shed[lb_pos[b], :]]
            sh = s1 + s2 + s3
            served = d - sh
        else:
            s1 = s2 = s3 = sh = served = 0.0
        buses.append({
            'bus': b, 'theta_deg': float(theta[b - 1] * 180 / np.pi),
            'Pd0': pd0, 'D_T': d, 'shed_L1': s1, 'shed_L2': s2,
            'shed_L3': s3, 'shed_total': sh, 'P_served': served,
            'Pg': pg_sum, 'P_inj': pg_sum - served,
        })

    # --- 负荷汇总 ---
    loads = []
    for i, b in enumerate(load_buses):
        d = float(r['D_total'][b])
        s = [float(x) for x in shed[i, :]]
        loads.append({
            'bus': b, 'Pd0': float(cd.PD0[b]), 'D_T': d,
            'D_L1': float(r['D_level'][b][0]),
            'D_L2': float(r['D_level'][b][1]),
            'D_L3': float(r['D_level'][b][2]),
            'shed_L1': s[0], 'shed_L2': s[1], 'shed_L3': s[2],
            'shed_total': sum(s), 'P_served': d - sum(s),
        })

    state = {
        'scenario': {
            'T_amb_C': sc['T_amb'], 'wind_mps': sc['wind_speed'],
            'irradiance_Wm2': sc['irradiance'], 'dt_h': sc['dt_h'],
        },
        'summary': {
            'status': r['status'],
            'obj_total': float(r['obj']),
            'gen_cost': float(r['gen_cost']),
            'shed_cost': float(r['shed_cost']),
            'total_Pg_MW': float(Pg.sum()),
            'total_D_MW': float(sum(r['D_total'].values())),
            'total_shed_MW': float(shed.sum()),
            'total_served_MW': float(sum(r['D_total'].values()) - shed.sum()),
            'max_branch_loading_pct': max(b['loading_pct'] for b in branches),
            'n_overloaded': sum(1 for b in branches if b['loading_pct'] > 100.0 + 1e-6),
        },
        'generators': generators,
        'branches': branches,
        'buses': buses,
        'loads': loads,
    }
    return state


if __name__ == '__main__':
    st = export_baseline_state()
    out = '/workspace/verify/baseline_state.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print(f'written {out}')
    print(json.dumps(st['summary'], indent=2, ensure_ascii=False))
