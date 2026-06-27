"""
第四步：极热条件下元件故障概率模型 —— Python 验证实现。

在第二步 DC-OPF 求解得到的"系统运行基准状态"（发电机出力 Pg、变压器/线路
潮流、节点相角）基础上，建立三类元件在极热（高温 + 无风 + 强辐照）条件下的
故障概率模型，并代入修改版 IEEE 39 节点算例计算各元件故障概率：

  A. 变压器故障概率   —— IEEE C57.91 热点温度 + Arrhenius-Weibull 老化加速
  B. 电源故障概率     —— 比例风险(Cox/Logistic)应力相关强迫停运率
  C. 线路故障概率     —— IEEE Std 738 导线温度 + 温度/过载应力指数模型

关键思想（与题目要求一致）：
  * 每个非电源节点一台同型号变压器；节点供电负荷 P_served 是变压器故障概率输入 -> 负载比 K；
  * 发电机出力 Pg 是发电机故障概率的输入参数 -> 出力率 ℓ -> 应力协变量；
  * 线路潮流是线路故障概率的输入参数 -> 电流/负载比 -> 导线温度。
并结合极热条件赋值（环境温度 40°C、风速 2 m/s、辐照 900 W/m²）。

所有公式与 docs/04_极热条件元件故障概率模型.md 一一对应，
并与 MATLAB 文件 matlab/fault_probability.m 数值一致。
"""

import json
import math

import numpy as np

import case_data as cd
import verify_dcopf as vd

TYPE_CN = {'thermal': '火电', 'hydro': '水电', 'wind': '风电', 'solar': '光伏'}

# =========================================================================
# 故障概率模型参数（在文献给出的合理范围内取值，构造极热典型场景）
# =========================================================================
FP = {
    # ---- 评估窗口：一次持续高温事件（持续高温日）----
    't_expose_h': 24.0,
    'hours_per_year': 8760.0,

    # ---- A. 变压器（IEEE C57.91-2011 + Arrhenius-Weibull）----
    'xf_lambda0_yr': 0.020,   # 正常条件基准年故障率 (/yr)
    'xf_dTO_rated': 55.0,     # 额定负载顶层油温升 ΔθTO,R (°C)
    'xf_dH_rated':  25.0,     # 额定负载热点-顶油温差 ΔθH,R (°C)
    'xf_R':         8.0,      # 负载损耗/空载损耗之比 R
    'xf_n':         0.9,      # 顶油温升指数 n
    'xf_m':         0.8,      # 绕组温升指数 m
    'xf_theta_ref': 110.0,    # 参考热点温度 (°C, 65°C-rise 绝缘正常寿命点)
    'xf_B_arr':     15000.0,  # Arrhenius 老化常数 B (IEEE C57.91-2011)
    'xf_S_rated':   500.0,    # 统一节点变压器额定容量 (MVA/MW)

    # ---- B. 电源（比例风险/Logistic 应力模型）----
    # 基准年强迫停运频次 λ0 (/yr)、温度应力系数 aT (1/°C)、出力应力系数 aL
    'gen_lambda0_yr': {'coal': 4.0, 'gas': 5.0, 'hydro': 2.0, 'wind': 6.0, 'solar': 5.0},
    'gen_aT':         {'coal': 0.020, 'gas': 0.030, 'hydro': 0.008, 'wind': 0.015, 'solar': 0.012},
    'gen_aL':         {'coal': 0.60, 'gas': 0.70, 'hydro': 0.30, 'wind': 0.40, 'solar': 0.50},
    'gen_T0': 25.0,           # 参考温度 (°C)

    # ---- C. 线路（IEEE Std 738 导线温度 + 指数应力）----
    'ln_lambda0_yr': 0.80,    # 正常条件基准年故障率 (/回·yr)
    'ln_bT': 0.030,           # 导线温度应力系数 (1/°C)
    'ln_bS': 1.50,            # 过载应力系数
    'ln_Tc_ref': 75.0,        # 导线连续运行参考温度 (°C)
    # 代表性导线（Drake 795 kcmil 26/7 ACSR）参数
    'cond_D':      0.02814,   # 外径 (m)
    'cond_R25':    7.283e-5,  # 电阻 @25°C (Ω/m)
    'cond_R75':    8.688e-5,  # 电阻 @75°C (Ω/m)
    'cond_emiss':  0.5,       # 发射率 ε
    'cond_absorp': 0.5,       # 太阳吸收率 α
    'V_base_kV':   345.0,     # 线电压 (kV)
    # 额定电流定义天气（基准天气下 β=1 时导线达连续运行温度 75°C）
    'rate_Ta': 25.0, 'rate_v': 2.0, 'rate_G': 0.0, 'rate_Tc': 75.0,
}


def pf_from_rate(lambda_yr, t_expose_h):
    """由年故障率得到评估窗口内的故障概率： Pf = 1 - exp(-λ·Δt)。"""
    lam_per_h = lambda_yr / FP['hours_per_year']
    return 1.0 - math.exp(-lam_per_h * t_expose_h)


# =========================================================================
# A. 变压器故障概率：热点温度 + Arrhenius 老化加速因子
# =========================================================================
def transformer_hotspot(K, Ta):
    r"""IEEE C57.91-2011 稳态热点温度。

    θH = θa + ΔθTO,R·[(K²R+1)/(R+1)]^n + ΔθH,R·K^(2m)

    K  : 变压器负载比 = P_served / S_T^rated（来自基准状态，非电源节点）
    Ta : 环境温度 (°C)
    """
    dTO = FP['xf_dTO_rated'] * ((K ** 2 * FP['xf_R'] + 1.0) / (FP['xf_R'] + 1.0)) ** FP['xf_n']
    dH = FP['xf_dH_rated'] * K ** (2.0 * FP['xf_m'])
    return Ta + dTO + dH


def transformer_faa(theta_H):
    r"""Arrhenius 老化加速因子（IEEE C57.91-2011）。

    FAA = exp[ B/(θ_ref+273) - B/(θH+273) ],  B = 15000
    """
    B = FP['xf_B_arr']
    ref = FP['xf_theta_ref']
    return math.exp(B / (ref + 273.0) - B / (theta_H + 273.0))


def transformer_pf(K, Ta):
    r"""变压器极热故障概率。

    热应力使绝缘老化按 Arrhenius 加速，老化加速因子 FAA 直接放大基准故障率
    （W. Li 2002 将老化失效并入可靠性评估的危险率加速思想）：

        λ_T = λ_T0 · FAA(θH(K,Ta)),   Pf = 1 - exp(-λ_T·Δt)
    """
    theta_H = transformer_hotspot(K, Ta)
    faa = transformer_faa(theta_H)
    lam_yr = FP['xf_lambda0_yr'] * faa
    pf = pf_from_rate(lam_yr, FP['t_expose_h'])
    return theta_H, faa, lam_yr, pf


# =========================================================================
# B. 电源故障概率：比例风险（应力相关强迫停运率）
# =========================================================================
def generator_pf(gtype, fuel, ell, Teff):
    r"""电源极热故障概率（Cox 比例风险 / Murphy logistic 形式）。

        λ_G = λ_G0 · exp[ aT·(Teff - T0) + aL·ℓ ]
        Pf  = 1 - exp(-λ_G·Δt)

    ℓ   : 出力率 = Pg/Prated（来自基准状态）
    Teff: 有效温度应力（火/水/风用环境温度；光伏用电池温度）
    """
    key = fuel if (gtype == 'thermal' and fuel in ('coal', 'gas')) else gtype
    lam0 = FP['gen_lambda0_yr'][key]
    aT = FP['gen_aT'][key]
    aL = FP['gen_aL'][key]
    stress = aT * (Teff - FP['gen_T0']) + aL * ell
    lam_yr = lam0 * math.exp(stress)
    pf = pf_from_rate(lam_yr, FP['t_expose_h'])
    return lam0, stress, lam_yr, pf


# =========================================================================
# C. 线路故障概率：IEEE Std 738 导线温度 + 温度/过载应力指数模型
# =========================================================================
def _air_props(Tfilm_C):
    """IEEE Std 738-2012 海平面空气物性（随膜温变化）。"""
    Tf = Tfilm_C
    kf = 2.424e-2 + 7.477e-5 * Tf - 4.407e-9 * Tf ** 2          # 导热系数 W/(m·K)
    muf = (1.458e-6 * (Tf + 273.0) ** 1.5) / (Tf + 273.0 + 383.4)  # 动力黏度 kg/(m·s)
    rhof = 1.293 / (1.0 + 0.00367 * Tf)                         # 空气密度 kg/m³ (海平面)
    return kf, muf, rhof


def _Rc(Tc):
    """导线电阻随温度线性插值/外推 (Ω/m)。"""
    R25, R75 = FP['cond_R25'], FP['cond_R75']
    return R25 + (R75 - R25) / (75.0 - 25.0) * (Tc - 25.0)


def _qc(Tc, Ta, v):
    """对流散热 (W/m)：取强迫对流(低/高风速两式)与自然对流之较大者。"""
    D = FP['cond_D']
    Tfilm = 0.5 * (Tc + Ta)
    kf, muf, rhof = _air_props(Tfilm)
    Nre = D * rhof * max(v, 0.0) / muf
    qc_f1 = (1.01 + 1.347 * Nre ** 0.52) * kf * (Tc - Ta)
    qc_f2 = 0.754 * Nre ** 0.6 * kf * (Tc - Ta)
    qc_forced = max(qc_f1, qc_f2)
    qc_nat = 3.645 * rhof ** 0.5 * D ** 0.75 * max(Tc - Ta, 0.0) ** 1.25
    return max(qc_forced, qc_nat)


def _qr(Tc, Ta):
    """辐射散热 (W/m)。"""
    D, eps = FP['cond_D'], FP['cond_emiss']
    return 17.8 * D * eps * (((Tc + 273.0) / 100.0) ** 4 - ((Ta + 273.0) / 100.0) ** 4)


def _qs():
    """太阳辐射吸热 (W/m)，取投影面积 A'=D、入射角 90°（最不利）。"""
    return FP['cond_absorp'] * FP['irradiance_for_lines'] * FP['cond_D']


def conductor_temperature(I, Ta, v, G):
    """由电流与天气，按 IEEE Std 738 稳态热平衡求解导线温度 (°C)。

    热平衡:  I²·R(Tc) + qs = qc(Tc) + qr(Tc)
    用二分法在 [Ta, 300] 内求根。
    """
    FP['irradiance_for_lines'] = G
    qs = _qs()

    def balance(Tc):
        return I ** 2 * _Rc(Tc) + qs - _qc(Tc, Ta, v) - _qr(Tc, Ta)

    lo, hi = Ta, 300.0
    flo = balance(lo)
    fhi = balance(hi)
    if flo * fhi > 0:
        # 电流过小或过大，返回边界
        return lo if abs(flo) < abs(fhi) else hi
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        fm = balance(mid)
        if abs(fm) < 1e-6:
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def rated_current():
    """求额定电流 I_R：基准天气下使导线达连续运行温度（75°C）的电流。

    I_R = sqrt[ (qc(Tc_ref) + qr(Tc_ref) - qs) / R(Tc_ref) ]
    """
    Tc = FP['rate_Tc']
    Ta, v, G = FP['rate_Ta'], FP['rate_v'], FP['rate_G']
    FP['irradiance_for_lines'] = G
    qs = _qs()
    num = _qc(Tc, Ta, v) + _qr(Tc, Ta) - qs
    return math.sqrt(max(num, 0.0) / _Rc(Tc))


def line_pf(beta, Ta, v, G, I_rated):
    r"""线路极热故障概率。

        I    = β·I_R               （β=|潮流|/rateA，来自基准状态）
        Tc   = IEEE738(I, Ta, v, G)
        λ_L  = λ_L0 · exp[ bT·(Tc - Tc_ref)+ + bS·(β - 1)+ ]
        Pf   = 1 - exp(-λ_L·Δt)
    """
    I = beta * I_rated
    Tc = conductor_temperature(I, Ta, v, G)
    over_T = max(Tc - FP['ln_Tc_ref'], 0.0)
    over_S = max(beta - 1.0, 0.0)
    stress = FP['ln_bT'] * over_T + FP['ln_bS'] * over_S
    lam_yr = FP['ln_lambda0_yr'] * math.exp(stress)
    pf = pf_from_rate(lam_yr, FP['t_expose_h'])
    return I, Tc, stress, lam_yr, pf


def node_xf_power(gens, load_buses, Dtotal_vec, shed, n_bus):
    """非电源节点变压器通过功率 = 该节点实际供电负荷（无负荷节点取 0）。"""
    gen_buses = {g[0] for g in gens}
    lb_pos = {b: i for i, b in enumerate(load_buses)}
    xf_bus, xf_p = [], []
    for b in range(1, n_bus + 1):
        if b in gen_buses:
            continue
        p = 0.0
        if b in lb_pos:
            k = lb_pos[b]
            p = float(Dtotal_vec[k] - shed[k, :].sum())
        xf_bus.append(b)
        xf_p.append(max(p, 0.0))
    return xf_bus, xf_p


# =========================================================================
# 主流程：从基准状态读取功率，计算三类元件故障概率
# =========================================================================
def compute(verbose=True):
    sc = cd.SCENARIO
    Ta, v, G = sc['T_amb'], sc['wind_speed'], sc['irradiance']
    base = cd.BASE_MVA

    r = vd.build_and_solve(verbose=False)
    theta = r['theta']
    Pg = r['Pg']
    gens = cd.GENS
    shed = r['shed']
    load_buses = r['load_buses']
    Dtotal_vec = np.array([r['D_total'][b] for b in load_buses])

    # ---------- A. 变压器（每个非电源节点一台，同型号）----------
    S_rated = FP['xf_S_rated']
    xf_bus, xf_p = node_xf_power(gens, load_buses, Dtotal_vec, shed, cd.N_BUS)
    transformers = []
    for i, (b, p) in enumerate(zip(xf_bus, xf_p), start=1):
        K = p / S_rated
        theta_H, faa, lam_yr, pf = transformer_pf(K, Ta)
        transformers.append({
            'Tx': i, 'bus': b, 'S_rated': S_rated, 'P_MW': float(p),
            'K': float(K), 'theta_H': float(theta_H), 'FAA': float(faa),
            'lambda_yr': float(lam_yr), 'Pf': float(pf),
        })

    # ---------- B. 电源 ----------
    Tcell = Ta + (sc['NOCT'] - 20.0) / 800.0 * G
    generators = []
    for gi, g in enumerate(gens):
        bus, gtype, fuel, prated = g[0], g[1], g[2], g[3]
        ell = max(Pg[gi] / prated, 0.0) if prated > 0 else 0.0
        Teff = Tcell if gtype == 'solar' else Ta
        lam0, stress, lam_yr, pf = generator_pf(gtype, fuel, ell, Teff)
        name = TYPE_CN[gtype] + (f'-{fuel}' if fuel else '')
        generators.append({
            'G': gi + 1, 'bus': bus, 'type': name, 'Prated': prated,
            'Pg': float(Pg[gi]), 'ell': float(ell), 'Teff': float(Teff),
            'lambda0_yr': lam0, 'stress': float(stress),
            'lambda_yr': float(lam_yr), 'Pf': float(pf),
        })

    # ---------- C. 线路 ----------
    I_R = rated_current()
    lines = []
    for idx, (f, t, x, rateA, ratio) in enumerate(cd.BRANCHES):
        if ratio != 0.0:
            continue
        bser = 1.0 / x
        flow = base * bser * (theta[f - 1] - theta[t - 1])
        beta = abs(flow) / rateA
        I, Tc, stress, lam_yr, pf = line_pf(beta, Ta, v, G, I_R)
        lines.append({
            'L': idx + 1, 'fbus': f, 'tbus': t, 'rateA': rateA,
            'flow_MW': float(flow), 'beta': float(beta),
            'I_A': float(I), 'Tc': float(Tc),
            'stress': float(stress), 'lambda_yr': float(lam_yr), 'Pf': float(pf),
        })

    result = {
        'scenario': {'T_amb_C': Ta, 'wind_mps': v, 'irradiance_Wm2': G,
                     't_expose_h': FP['t_expose_h'], 'I_rated_A': float(I_R),
                     'xf_S_rated': S_rated, 'n_transformers': len(transformers)},
        'transformers': transformers,
        'generators': generators,
        'lines': lines,
    }

    if verbose:
        _print_report(result)
    return result


def _print_report(res):
    sc = res['scenario']
    print('=' * 86)
    print('极热条件元件故障概率（T=%.0f°C, v=%.0f m/s, G=%.0f W/m², 评估窗口=%.0f h）'
          % (sc['T_amb_C'], sc['wind_mps'], sc['irradiance_Wm2'], sc['t_expose_h']))
    print('统一节点变压器额定容量 S_T^rated = %.0f MW（共 %d 台，非电源节点各一台）'
          % (sc['xf_S_rated'], sc['n_transformers']))
    print('代表性导线额定电流 I_R = %.1f A' % sc['I_rated_A'])

    print('\n【A】节点变压器故障概率（IEEE C57.91 热点 + Arrhenius-Weibull）')
    print('%-4s%-5s%10s%8s%10s%10s%12s%12s'
          % ('Tx', 'bus', 'P(MW)', 'K', 'thetaH', 'FAA', 'lambda/yr', 'Pf'))
    for d in res['transformers']:
        print('T%-3d%-5d%10.2f%8.3f%10.1f%10.3f%12.4f%12.3e'
              % (d['Tx'], d['bus'], d['P_MW'], d['K'],
                 d['theta_H'], d['FAA'], d['lambda_yr'], d['Pf']))

    print('\n【B】电源故障概率（比例风险应力模型）')
    print('%-4s%-5s%-12s%10s%8s%8s%12s%12s'
          % ('G', 'bus', '类型', 'Pg', 'ell', 'Teff', 'lambda/yr', 'Pf'))
    for d in res['generators']:
        print('G%-3d%-5d%-12s%10.2f%8.3f%8.1f%12.4f%12.3e'
              % (d['G'], d['bus'], d['type'], d['Pg'], d['ell'],
                 d['Teff'], d['lambda_yr'], d['Pf']))

    print('\n【C】线路故障概率（IEEE 738 导线温度 + 指数应力）')
    print('%-4s%-6s%-6s%10s%8s%10s%10s%12s%12s'
          % ('L', 'fbus', 'tbus', 'flow', 'beta', 'I(A)', 'Tc', 'lambda/yr', 'Pf'))
    for d in res['lines']:
        print('L%-3d%-6d%-6d%10.2f%8.3f%10.1f%10.1f%12.4f%12.3e'
              % (d['L'], d['fbus'], d['tbus'], d['flow_MW'], d['beta'],
                 d['I_A'], d['Tc'], d['lambda_yr'], d['Pf']))
    print('=' * 86)


if __name__ == '__main__':
    res = compute(verbose=True)
    out = '/workspace/verify/fault_probability.json'
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(res, fp, ensure_ascii=False, indent=2)
    print('\nwritten %s' % out)
