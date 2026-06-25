"""
第一步：极热无风气象条件下的"源-荷"失衡物理模型。

A. 源侧：火电 / 水电 / 风电 / 光伏 四类机组的最大出力(降容)公式；
B. 荷侧：温度敏感负荷模型与按可靠性等级的负荷拆分。

所有公式与 docs/01_源荷失衡模型.md 中的数学描述一一对应，并与
MATLAB 文件 matlab/derate_sources.m、matlab/load_temperature.m 数值一致。
"""

import numpy as np


# =========================================================================
# A. 源侧最大出力（极热无风降容）
# =========================================================================
def pmax_thermal(pmax_rated, fuel, sc):
    r"""火电机组最大出力（高温降容）。

    P_max(T) = P_rated * [1 - alpha * (T - T_ref)]+ ,  T > T_ref

    高温使进气密度下降、凝汽器背压升高、冷却效率下降，最大出力随温度线性下降。
    燃气机组(gas)对进气温度更敏感，alpha 取值更大。
    """
    T = sc['T_amb']
    Tref = sc['T_ref_thermal']
    alpha = sc['alpha_gas'] if fuel == 'gas' else sc['alpha_coal']
    derate = 1.0 - alpha * max(0.0, T - Tref)
    return pmax_rated * max(0.0, derate)


def pmax_hydro(pmax_rated, sc):
    r"""水电机组最大出力（极热枯水/低水头）。

    瞬时出力  P = rho * g * eta * Q * H
    极热常伴枯水与蒸发增大，可用水头 H 与流量 Q 下降，
    可用出力按系数 k_hydro 折减（并受水库可用电量约束，见多时段说明）。

    P_max = k_hydro * P_rated
    """
    return sc['k_hydro'] * pmax_rated


def pmax_wind(pmax_rated, sc):
    r"""风电机组最大出力（分段风速-功率曲线）。

              | 0                                      v < v_ci 或 v > v_co
    P_w(v) =  | P_rated * (v^3 - v_ci^3)/(v_r^3 - v_ci^3)  v_ci <= v < v_r
              | P_rated                                v_r <= v <= v_co

    "无风"工况 v < v_ci，故风电最大可用出力近乎为 0。
    """
    v = sc['wind_speed']
    vci, vr, vco = sc['v_cut_in'], sc['v_rated'], sc['v_cut_out']
    if v < vci or v > vco:
        frac = 0.0
    elif v < vr:
        frac = (v ** 3 - vci ** 3) / (vr ** 3 - vci ** 3)
    else:
        frac = 1.0
    return pmax_rated * frac


def pmax_solar(pmax_rated, sc):
    r"""光伏最大出力（辐照 + 电池温度负系数）。

    电池温度:  T_cell = T_amb + (NOCT - 20)/800 * G
    出力:      P_pv = P_stc * (G/G_stc) * [1 + gamma * (T_cell - T_stc)]

    极热使电池温度远高于环境温度，gamma<0 导致效率下降，出力被削减。
    """
    G = sc['irradiance']
    Tcell = sc['T_amb'] + (sc['NOCT'] - 20.0) / 800.0 * G
    frac = (G / sc['G_stc']) * (1.0 + sc['gamma_pv'] * (Tcell - sc['T_stc']))
    return pmax_rated * max(0.0, frac)


def source_pmax(gen, sc):
    """根据机组类型分发到对应降容公式，返回该机组极热场景下的最大出力(MW)。"""
    bus, gtype, fuel, pmax_rated = gen[0], gen[1], gen[2], gen[3]
    if gtype == 'thermal':
        return pmax_thermal(pmax_rated, fuel, sc)
    if gtype == 'hydro':
        return pmax_hydro(pmax_rated, sc)
    if gtype == 'wind':
        return pmax_wind(pmax_rated, sc)
    if gtype == 'solar':
        return pmax_solar(pmax_rated, sc)
    raise ValueError(f'未知机组类型: {gtype}')


# =========================================================================
# B. 荷侧温度响应与等级拆分
# =========================================================================
def bus_demand(pd0, sc):
    r"""节点温度修正后的总需求。

    D(T) = rho_rigid * Pd0 + rho_cool * Pd0 * [1 + beta * (T - T_L0)]+

    刚性基荷(rho_rigid)与温度无关；温敏空调负荷(rho_cool)随温度线性增长。
    """
    rho_cool = sc['rho_cool']
    rho_rigid = 1.0 - rho_cool
    T = sc['T_amb']
    cool_factor = 1.0 + sc['beta_load'] * max(0.0, T - sc['T_L0'])
    return rho_rigid * pd0 + rho_cool * pd0 * cool_factor


def split_by_level(demand, sc):
    """把节点总需求按一/二/三级可靠性比例拆分，返回各级需求(MW)列表。"""
    return [demand * f for f in sc['level_frac']]
