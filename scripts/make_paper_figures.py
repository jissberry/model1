#!/usr/bin/env python3
"""生成论文插图（docs/figures/）。

图 1  研究框架流程图
图 2  极热无风源侧降容与荷侧需求增长
图 3  基准 OPF 机组出力与调度区间
图 4  分级负荷需求与切负荷分布
图 5  三类元件极热故障概率
图 6  蒙特卡洛故障场景统计
图 7  故障后 OPF 切负荷分布与经验累积分布
图 8  切负荷与故障元件数量的关系
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / 'verify'
OUTDIR = ROOT / 'docs/figures'

sys.path.insert(0, str(VERIFY))

import case_data as cd  # noqa: E402
import models as md  # noqa: E402

plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Droid Sans Fallback']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

C_THERMAL = '#c0392b'
C_HYDRO = '#2980b9'
C_WIND = '#16a085'
C_SOLAR = '#e67e22'
C_LOAD = '#8e44ad'
C_GRAY = '#7f8c8d'

TYPE_COLOR = {
    'thermal': C_THERMAL,
    'hydro': C_HYDRO,
    'wind': C_WIND,
    'solar': C_SOLAR,
}
TYPE_CN = {'thermal': '火电', 'hydro': '水电', 'wind': '风电', 'solar': '光伏'}


def load_json(name):
    with (VERIFY / name).open(encoding='utf-8') as f:
        return json.load(f)


def load_summary_rows():
    rows = []
    with (VERIFY / 'fault_scenario_opf_summary.csv').open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def fig1_framework():
    fig, ax = plt.subplots(figsize=(7.2, 8.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, 15.6)
    ax.axis('off')
    ax.grid(False)

    steps = [
        ('第一步  极热无风气象场景',
         '环境温度 T=40 °C，风速 v=2 m/s，辐照 G=900 W/m²', '#34495e'),
        ('第二步  源-荷失衡建模',
         '源侧：火电降容 / 水电枯水 / 风电停发 / 光伏降效\n'
         '荷侧：温敏负荷增长 + 一/二/三级负荷拆分', '#2980b9'),
        ('第三步  基准 DC-OPF / MIQP',
         '目标：发电成本 + 切负荷惩罚最小\n'
         '火电启停变量 u∈{0,1}；不施加爬坡约束', '#16a085'),
        ('第四步  元件热故障概率模型',
         '变压器：热点温度 + Arrhenius 老化\n'
         '发电机：温度与出力率比例风险\n'
         '线路：IEEE 738 导线温度 + 过载应力', '#e67e22'),
        ('第五步  蒙特卡洛故障场景抽样',
         '2000 个 85 维 0/1 场景\n'
         '[G1–G10, L1–L46, T1–T29]', '#8e44ad'),
        ('第六步  故障后 OPF 遍历',
         '故障映射 + 以基准出力为爬坡中心\n'
         '孤岛内火电可停机保可解', '#c0392b'),
        ('第七步  切负荷风险统计',
         '均值 / 分位数 / 极值，识别尾部风险', '#2c3e50'),
    ]

    gap = 0.46
    line_h = 0.42
    pad_top = 0.62
    pad_bot = 0.30
    y = 15.4 - 1.0
    for idx, (title, body, color) in enumerate(steps):
        nlines = body.count('\n') + 1
        height = pad_top + nlines * line_h + pad_bot
        box = FancyBboxPatch(
            (0.7, y - height), 8.6, height,
            boxstyle='round,pad=0.12,rounding_size=0.18',
            linewidth=1.6, edgecolor=color, facecolor=color + '18',
        )
        ax.add_patch(box)
        ax.text(5.0, y - pad_top / 2 - 0.10, title, ha='center', va='center',
                fontsize=11.5, fontweight='bold', color=color)
        body_center = y - pad_top - nlines * line_h / 2
        ax.text(5.0, body_center, body, ha='center', va='center',
                fontsize=9, color='#2c3e50', linespacing=1.55)

        if idx < len(steps) - 1:
            ax.add_patch(FancyArrowPatch(
                (5.0, y - height - 0.04), (5.0, y - height - gap + 0.06),
                arrowstyle='-|>', mutation_scale=15,
                linewidth=1.5, color=C_GRAY,
            ))
        y -= height + gap

    ax.text(5.0, 15.28, '图 1  极热无风源荷失衡与热故障耦合风险评估框架',
            ha='center', va='center', fontsize=12, fontweight='bold')
    fig.savefig(OUTDIR / 'fig1_framework.png')
    plt.close(fig)


def fig2_derating_and_load():
    sc = dict(cd.SCENARIO)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2))

    # (a) 四类机组降容率随温度变化
    ax = axes[0]
    temps = np.linspace(25, 45, 120)
    coal, gas, hydro, solar = [], [], [], []
    for T in temps:
        s = dict(sc)
        s['T_amb'] = T
        coal.append(md.pmax_thermal(1.0, 'coal', s) * 100)
        gas.append(md.pmax_thermal(1.0, 'gas', s) * 100)
        hydro.append(md.pmax_hydro(1.0, s) * 100)
        solar.append(md.pmax_solar(1.0, s) * 100)
    ax.plot(temps, coal, color=C_THERMAL, lw=2, label='火电-燃煤')
    ax.plot(temps, gas, color=C_THERMAL, lw=2, ls='--', label='火电-燃气')
    ax.plot(temps, hydro, color=C_HYDRO, lw=2, label='水电（枯水）')
    ax.plot(temps, solar, color=C_SOLAR, lw=2, label='光伏')
    ax.axhline(0, color=C_WIND, lw=2, ls=':', label='风电（无风）')
    ax.axvline(40, color=C_GRAY, lw=1.2, ls='-.')
    ax.text(40.25, 30, 'T = 40 °C', fontsize=8.5, color=C_GRAY, rotation=90)
    ax.set_xlabel('环境温度 T / °C')
    ax.set_ylabel('可用出力占额定容量 / %')
    ax.set_title('(a) 四类机组降容特性')
    ax.set_ylim(-4, 105)
    ax.legend(fontsize=8, loc='center left')

    # (b) 风速-功率曲线
    ax = axes[1]
    winds = np.linspace(0, 27, 300)
    frac = []
    for v in winds:
        s = dict(sc)
        s['wind_speed'] = v
        frac.append(md.pmax_wind(1.0, s) * 100)
    ax.plot(winds, frac, color=C_WIND, lw=2.2)
    ax.axvline(sc['v_cut_in'], color=C_GRAY, ls='--', lw=1)
    ax.axvline(sc['v_rated'], color=C_GRAY, ls='--', lw=1)
    ax.axvline(sc['v_cut_out'], color=C_GRAY, ls='--', lw=1)
    ax.scatter([sc['wind_speed']], [0], color=C_THERMAL, zorder=5, s=45)
    ax.annotate('极热无风工况\nv = 2 m/s < v_ci',
                xy=(sc['wind_speed'], 0), xytext=(5.4, 30),
                fontsize=8.5, color=C_THERMAL,
                arrowprops=dict(arrowstyle='->', color=C_THERMAL, lw=1.2))
    ax.text(sc['v_cut_in'], 103, 'v_ci', ha='center', fontsize=8, color=C_GRAY)
    ax.text(sc['v_rated'], 103, 'v_r', ha='center', fontsize=8, color=C_GRAY)
    ax.text(sc['v_cut_out'], 103, 'v_co', ha='center', fontsize=8, color=C_GRAY)
    ax.set_xlabel('风速 v / (m/s)')
    ax.set_ylabel('风电可用出力 / %')
    ax.set_title('(b) 风速-功率曲线')
    ax.set_ylim(-4, 112)

    # (c) 荷侧温敏增长
    ax = axes[2]
    total0 = sum(cd.PD0.values())
    demands = []
    for T in temps:
        s = dict(sc)
        s['T_amb'] = T
        demands.append(sum(md.bus_demand(p, s) for p in cd.PD0.values()))
    demands = np.array(demands)
    ax.plot(temps, demands, color=C_LOAD, lw=2.2, label='极热修正总需求 D(T)')
    ax.axhline(total0, color=C_GRAY, lw=1.4, ls='--', label='常温基准负荷')

    s40 = dict(sc)
    s40['T_amb'] = 40.0
    d40 = sum(md.bus_demand(p, s40) for p in cd.PD0.values())
    avail40 = sum(md.source_pmax(g, s40) for g in cd.GENS)
    ax.axhline(avail40, color=C_THERMAL, lw=1.6, ls='-.',
               label=f'极热可用出力 {avail40:.0f} MW')
    ax.scatter([40], [d40], color=C_LOAD, zorder=5, s=45)
    ax.annotate(f'源荷缺口\n{d40 - avail40:.0f} MW',
                xy=(40, (d40 + avail40) / 2), xytext=(32.6, 6480),
                fontsize=9, color=C_THERMAL, fontweight='bold',
                ha='center',
                arrowprops=dict(arrowstyle='->', color=C_THERMAL, lw=1.2))
    ax.fill_between([39.4, 40.6], avail40, d40, color=C_THERMAL, alpha=0.25)
    ax.set_xlabel('环境温度 T / °C')
    ax.set_ylabel('功率 / MW')
    ax.set_title('(c) 荷侧温敏增长与源荷缺口')
    ax.set_ylim(5850, 7250)
    ax.legend(fontsize=8, loc='upper left')

    fig.suptitle('图 2  极热无风条件下的源侧降容与荷侧需求增长', fontsize=12,
                 fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig2_source_load_imbalance.png')
    plt.close(fig)


def fig3_baseline_dispatch(state):
    gens = state['generators']
    names = [f"G{g['G']}" for g in gens]
    x = np.arange(len(gens))
    prated = np.array([g['Prated'] for g in gens])
    ub = np.array([g['ub'] for g in gens])
    lb = np.array([g['lb'] for g in gens])
    pg = np.array([max(g['Pg'], 0.0) for g in gens])
    colors = [TYPE_COLOR[
        'thermal' if '火电' in g['type'] else
        'hydro' if '水电' in g['type'] else
        'wind' if '风电' in g['type'] else 'solar'] for g in gens]

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.4),
                             gridspec_kw={'width_ratios': [1.65, 1]})

    ax = axes[0]
    ax.bar(x, prated, color='#dfe6e9', edgecolor='#b2bec3', zorder=1)
    ax.bar(x, ub, color=colors, alpha=0.45, edgecolor='none', zorder=2)
    ax.bar(x, pg, color=colors, edgecolor='black', linewidth=0.6, width=0.55,
           zorder=3)
    ax.plot(x, lb, 'k_', markersize=18, markeredgewidth=1.8, zorder=4)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor='#dfe6e9', edgecolor='#b2bec3',
              label='铭牌容量 $P^{rated}$'),
        Patch(facecolor='#95a5a6', alpha=0.45,
              label='极热调度上界 $\\overline{P}^{disp}$'),
        Patch(facecolor='#636e72', edgecolor='black',
              label='最优出力 $P_G^\\star$'),
        Line2D([0], [0], color='black', marker='_', linestyle='None',
               markersize=12, markeredgewidth=1.8,
               label='调度下界 $\\underline{P}^{disp}$'),
    ]
    for i, g in enumerate(gens):
        if g['Prated'] > 0:
            util = max(g['util_pct'], 0.0)
            ax.text(i, prated[i] + 18, f'{util:.0f}%',
                    ha='center', fontsize=7.6, color='#2d3436')
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel('有功功率 / MW')
    ax.set_title('(a) 基准 OPF 机组出力与调度区间')
    ax.legend(handles=handles, fontsize=8, ncol=2, loc='upper center')
    ax.set_ylim(0, prated.max() * 1.32)

    ax = axes[1]
    by_type = {}
    for g in gens:
        key = ('火电' if '火电' in g['type'] else
               '水电' if '水电' in g['type'] else
               '风电' if '风电' in g['type'] else '光伏')
        item = by_type.setdefault(key, {'rated': 0.0, 'avail': 0.0, 'pg': 0.0})
        item['rated'] += g['Prated']
        item['avail'] += g['ub']
        item['pg'] += max(g['Pg'], 0.0)

    order = ['火电', '水电', '风电', '光伏']
    cmap = {'火电': C_THERMAL, '水电': C_HYDRO, '风电': C_WIND, '光伏': C_SOLAR}
    xt = np.arange(len(order))
    w = 0.27
    rated = [by_type[k]['rated'] for k in order]
    avail = [by_type[k]['avail'] for k in order]
    out = [by_type[k]['pg'] for k in order]
    ax.bar(xt - w, rated, w, label='铭牌容量', color='#b2bec3')
    ax.bar(xt, avail, w, label='极热可用出力',
           color=[cmap[k] for k in order], alpha=0.55)
    ax.bar(xt + w, out, w, label='最优出力',
           color=[cmap[k] for k in order])
    for i, k in enumerate(order):
        if rated[i] > 0:
            ax.text(i, max(avail[i], out[i]) + 60,
                    f'{avail[i] / rated[i] * 100:.0f}%',
                    ha='center', fontsize=8.5, fontweight='bold',
                    color=cmap[k])
    ax.set_xticks(xt)
    ax.set_xticklabels(order)
    ax.set_ylabel('有功功率 / MW')
    ax.set_title('(b) 分类型容量-出力对比')
    ax.legend(fontsize=8)

    fig.suptitle('图 3  极热无风基准 OPF 调度结果', fontsize=12,
                 fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig3_baseline_dispatch.png')
    plt.close(fig)


def fig4_load_shedding(state):
    loads = sorted(state['loads'], key=lambda d: d['bus'])
    buses = [str(d['bus']) for d in loads]
    x = np.arange(len(loads))
    served = np.array([d['P_served'] for d in loads])
    shed3 = np.array([d['shed_L3'] for d in loads])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.3),
                             gridspec_kw={'width_ratios': [1.9, 1]})

    ax = axes[0]
    ax.bar(x, served, color='#74b9ff', edgecolor='#0984e3', linewidth=0.5,
           label='实际供电')
    ax.bar(x, shed3, bottom=served, color=C_THERMAL, edgecolor='#8b0000',
           linewidth=0.5, label='切除的三级负荷')
    ax.set_xticks(x)
    ax.set_xticklabels(buses, fontsize=8)
    ax.set_xlabel('负荷节点编号')
    ax.set_ylabel('有功功率 / MW')
    ax.set_title('(a) 各负荷节点极热需求与切负荷构成')
    ax.legend(fontsize=8.5)

    ax = axes[1]
    summary = state['summary']
    d_total = summary['total_D_MW']
    lvl1 = sum(d['D_L1'] for d in loads)
    lvl2 = sum(d['D_L2'] for d in loads)
    lvl3 = sum(d['D_L3'] for d in loads)
    shed1 = sum(d['shed_L1'] for d in loads)
    shed2 = sum(d['shed_L2'] for d in loads)
    shed3_t = sum(d['shed_L3'] for d in loads)

    labels = ['一级\n(VOLL 10000)', '二级\n(VOLL 5000)', '三级\n(VOLL 1000)']
    demand = [lvl1, lvl2, lvl3]
    shed = [shed1, shed2, shed3_t]
    xt = np.arange(3)
    ax.bar(xt, demand, 0.55, color='#dfe6e9', edgecolor='#b2bec3',
           label='极热修正需求')
    ax.bar(xt, shed, 0.55, color=C_THERMAL, edgecolor='#8b0000',
           label='切除量')
    for i in range(3):
        pct = shed[i] / demand[i] * 100 if demand[i] > 0 else 0
        ax.text(i, demand[i] + 60, f'{shed[i]:.1f} MW\n({pct:.1f}%)',
                ha='center', fontsize=8.5, fontweight='bold',
                color=C_THERMAL if shed[i] > 0 else '#2d3436')
    ax.set_xticks(xt)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel('有功功率 / MW')
    ax.set_title(f"(b) 分级需求与切负荷（总切 {summary['total_shed_MW']:.1f} MW）")
    ax.legend(fontsize=8.5)
    ax.set_ylim(0, max(demand) * 1.28)

    fig.suptitle('图 4  基准 OPF 的分级切负荷结果', fontsize=12,
                 fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig4_load_shedding.png')
    plt.close(fig)


def fig5_fault_probability(fp):
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.1))

    # (a) 发电机故障概率
    ax = axes[0]
    gens = fp['generators']
    names = [f"G{g['G']}" for g in gens]
    pf = np.array([g['Pf'] for g in gens]) * 100
    ell = np.array([g['ell'] for g in gens])
    colors = []
    for g in gens:
        t = g['type']
        colors.append(C_THERMAL if '火电' in t else
                      C_HYDRO if '水电' in t else
                      C_WIND if '风电' in t else C_SOLAR)
    bars = ax.bar(names, pf, color=colors, edgecolor='black', linewidth=0.5)
    for b, e in zip(bars, ell):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.05,
                f'ℓ={e:.2f}', ha='center', fontsize=7, color='#2d3436')
    ax.set_ylabel('故障概率 $P_f$ / %')
    ax.set_title('(a) 发电机故障概率（24 h 窗口）')
    ax.set_ylim(0, pf.max() * 1.3)
    ax.tick_params(axis='x', labelsize=8)

    # (b) 线路导线温度 vs 故障概率
    ax = axes[1]
    lines = fp['lines']
    beta = np.array([d['beta'] for d in lines])
    tc = np.array([d['Tc'] for d in lines])
    lpf = np.array([d['Pf'] for d in lines]) * 100
    sc_plot = ax.scatter(beta * 100, tc, c=lpf, cmap='YlOrRd',
                         s=48, edgecolor='black', linewidth=0.5,
                         vmin=lpf.min(), vmax=lpf.max())
    ax.axhline(75, color=C_GRAY, ls='--', lw=1.2)
    ax.text(2, 77, '连续运行温度 75 °C', fontsize=8, color=C_GRAY)
    imax = int(np.argmax(lpf))
    ax.annotate(f"L{lines[imax]['L']}（满载断面）",
                xy=(beta[imax] * 100, tc[imax]),
                xytext=(beta[imax] * 100 - 52, tc[imax] - 4),
                fontsize=8.5, color=C_THERMAL,
                arrowprops=dict(arrowstyle='->', color=C_THERMAL, lw=1.2))
    ax.set_ylim(min(tc) - 4, max(tc) + 8)
    cb = fig.colorbar(sc_plot, ax=ax)
    cb.set_label('$P_f$ / %', fontsize=8.5)
    ax.set_xlabel('线路负载率 β / %')
    ax.set_ylabel('导线温度 $T_c$ / °C')
    ax.set_title('(b) 线路负载率-导线温度-故障概率')

    # (c) 三类元件故障概率对比
    ax = axes[2]
    xf_pf = fp['transformers'][0]['Pf'] * 100
    groups = ['节点变压器\n(29 台)', '发电机\n(10 台)', '线路\n(46 条)']
    values = [xf_pf, float(np.mean(pf)), float(np.mean(lpf))]
    errs = [
        [0, float(np.mean(pf) - pf.min()), float(np.mean(lpf) - lpf.min())],
        [0, float(pf.max() - np.mean(pf)), float(lpf.max() - np.mean(lpf))],
    ]
    bars = ax.bar(groups, values, color=['#9b59b6', C_THERMAL, '#e67e22'],
                  edgecolor='black', linewidth=0.6, width=0.55)
    ax.errorbar(groups, values, yerr=errs, fmt='none',
                ecolor='#2d3436', elinewidth=1.2, capsize=5)
    for b, v, e_hi in zip(bars, values, errs[1]):
        ax.text(b.get_x() + b.get_width() / 2, v + e_hi + 0.14,
                f'{v:.3f}%', ha='center', fontsize=8.5, fontweight='bold')
    ax.set_ylabel('故障概率 $P_f$ / %')
    ax.set_title('(c) 三类元件故障概率（均值与范围）')
    ax.set_ylim(0, (max(values) + max(errs[1])) * 1.22)

    fig.suptitle('图 5  极热条件下三类元件的热故障概率', fontsize=12,
                 fontweight='bold', y=1.03)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig5_fault_probability.png')
    plt.close(fig)


def fig6_monte_carlo(meta):
    states = np.array(
        list(csv.reader((VERIFY / 'fault_scenarios_2000.csv').open(encoding='utf-8')))[1:],
        dtype=object)
    mat = states[:, 1:].astype(int)
    n_fault_per_scen = (mat == 0).sum(axis=1)

    gen_block = mat[:, 0:10]
    line_block = mat[:, 10:56]
    xf_block = mat[:, 56:85]

    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.1))

    ax = axes[0]
    vals, counts = np.unique(n_fault_per_scen, return_counts=True)
    bars = ax.bar(vals, counts, color='#8e44ad', edgecolor='black',
                  linewidth=0.6, width=0.6)
    for b, c in zip(bars, counts):
        ax.text(b.get_x() + b.get_width() / 2, c + 18,
                f'{c}\n({c / len(mat) * 100:.1f}%)',
                ha='center', fontsize=8)
    ax.set_xlabel('单场景故障元件数')
    ax.set_ylabel('场景数')
    ax.set_title('(a) 故障元件数分布（2000 场景）')
    ax.set_xticks(vals)
    ax.set_ylim(0, counts.max() * 1.22)

    ax = axes[1]
    cats = ['发电机\n(10)', '线路\n(46)', '节点变压器\n(29)']
    n_fault = [int((gen_block == 0).sum()),
               int((line_block == 0).sum()),
               int((xf_block == 0).sum())]
    bars = ax.bar(cats, n_fault, color=[C_THERMAL, '#e67e22', '#9b59b6'],
                  edgecolor='black', linewidth=0.6, width=0.55)
    total = sum(n_fault)
    for b, v in zip(bars, n_fault):
        ax.text(b.get_x() + b.get_width() / 2, v + 8,
                f'{v}\n({v / total * 100:.1f}%)', ha='center', fontsize=8.5)
    ax.set_ylabel('故障事件数')
    ax.set_title(f'(b) 各类元件故障事件数（共 {total} 次）')
    ax.set_ylim(0, max(n_fault) * 1.25)

    ax = axes[2]
    labels = meta['labels']
    probs = np.array(meta['prob_failure']) * 100
    emp = (mat == 0).mean(axis=0) * 100
    idx_g = np.arange(0, 10)
    idx_l = np.arange(10, 56)
    idx_t = np.arange(56, 85)
    ax.scatter(probs[idx_g], emp[idx_g], color=C_THERMAL, s=42,
               edgecolor='black', linewidth=0.5, label='发电机', zorder=3)
    ax.scatter(probs[idx_l], emp[idx_l], color='#e67e22', s=28,
               edgecolor='black', linewidth=0.4, label='线路', alpha=0.8, zorder=2)
    ax.scatter(probs[idx_t], emp[idx_t], color='#9b59b6', s=28,
               edgecolor='black', linewidth=0.4, label='节点变压器', alpha=0.8,
               zorder=2)
    lim = max(probs.max(), emp.max()) * 1.1
    ax.plot([0, lim], [0, lim], ls='--', color=C_GRAY, lw=1.2,
            label='理论=经验')
    ax.set_xlabel('理论故障概率 / %')
    ax.set_ylabel('抽样经验频率 / %')
    ax.set_title('(c) 抽样一致性校验')
    ax.legend(fontsize=8)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)

    fig.suptitle('图 6  蒙特卡洛故障场景抽样结果（2000 × 85）', fontsize=12,
                 fontweight='bold', y=1.03)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig6_monte_carlo.png')
    plt.close(fig)


def fig7_shedding_distribution(stats, rows):
    shed = np.array([float(r['total_shed_MW']) for r in rows
                     if r['total_shed_MW'] != ''])
    base = stats['baseline_total_shed_MW']
    dist = stats['total_shed_MW']

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.2))

    ax = axes[0]
    ax.hist(shed, bins=45, color='#5dade2', edgecolor='#21618c', linewidth=0.5)
    ax.axvline(base, color=C_GRAY, lw=1.8, ls='--',
               label=f'基准 {base:.1f} MW')
    ax.axvline(dist['mean'], color=C_THERMAL, lw=1.8,
               label=f"均值 {dist['mean']:.1f} MW")
    ax.axvline(dist['p95'], color='#e67e22', lw=1.8, ls='-.',
               label=f"95% 分位 {dist['p95']:.1f} MW")
    ax.set_yscale('log')
    ax.set_xlabel('总切负荷 / MW')
    ax.set_ylabel('场景数（对数刻度）')
    ax.set_title('(a) 总切负荷频数分布')
    ax.legend(fontsize=8)

    ax = axes[1]
    s = np.sort(shed)
    cdf = np.arange(1, s.size + 1) / s.size * 100
    ax.plot(s, cdf, color='#2980b9', lw=2)
    for q, c, ls in [('p90', '#f39c12', ':'), ('p95', '#e67e22', '-.'),
                     ('p99', '#c0392b', '--')]:
        ax.axvline(dist[q], color=c, lw=1.4, ls=ls,
                   label=f"{q.upper()} = {dist[q]:.0f} MW")
    ax.axvline(base, color=C_GRAY, lw=1.6, ls='--', label='基准切负荷')
    ax.set_xlabel('总切负荷 / MW')
    ax.set_ylabel('经验累积概率 / %')
    ax.set_title('(b) 经验累积分布（尾部风险）')
    ax.legend(fontsize=8, loc='lower right')
    ax.set_ylim(0, 101)

    ax = axes[2]
    keys = ['min', 'p05', 'p25', 'median', 'p75', 'p90', 'p95', 'p99', 'max']
    names = ['最小', '5%', '25%', '中位', '75%', '90%', '95%', '99%', '最大']
    vals = [dist[k] for k in keys]
    inc = [stats['incremental_shed_vs_baseline_MW'][k] for k in keys]
    y = np.arange(len(keys))
    ax.barh(y, base * np.ones(len(keys)), color='#bdc3c7',
            edgecolor='#7f8c8d', linewidth=0.5, label='基准切负荷')
    ax.barh(y, inc, left=base * np.ones(len(keys)), color=C_THERMAL,
            edgecolor='#8b0000', linewidth=0.5, label='故障新增切负荷')
    for i, v in enumerate(vals):
        ax.text(v + 40, i, f'{v:.0f}', va='center', fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8.5)
    ax.set_xlabel('总切负荷 / MW')
    ax.set_title('(c) 分位数切负荷构成')
    ax.legend(fontsize=8, loc='lower right')
    ax.set_xlim(0, max(vals) * 1.18)
    ax.invert_yaxis()

    fig.suptitle('图 7  2000 个热故障场景的切负荷分布', fontsize=12,
                 fontweight='bold', y=1.03)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig7_shedding_distribution.png')
    plt.close(fig)


def fig8_driver_analysis(stats, rows):
    base = stats['baseline_total_shed_MW']
    shed = np.array([float(r['total_shed_MW']) for r in rows])
    n_gen = np.array([int(r['n_gen_fault']) for r in rows])
    n_line = np.array([int(r['n_line_fault_direct']) for r in rows])
    n_xf = np.array([int(r['n_transformer_fault']) for r in rows])
    n_off = np.array([int(r['n_thermal_off']) for r in rows])
    n_out = np.array([int(r['n_branch_outage_total']) for r in rows])

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.2))

    ax = axes[0]
    groups, labels = [], []
    for k in sorted(np.unique(n_gen)):
        sel = shed[n_gen == k]
        if sel.size >= 3:
            groups.append(sel)
            labels.append(f'{k}\n(n={sel.size})')
    bp = ax.boxplot(groups, tick_labels=labels, patch_artist=True, widths=0.55,
                    medianprops=dict(color='black', lw=1.4),
                    flierprops=dict(marker='o', markersize=3, alpha=0.5))
    for patch, color in zip(bp['boxes'],
                            plt.cm.Reds(np.linspace(0.3, 0.85, len(groups)))):
        patch.set_facecolor(color)
    ax.axhline(base, color=C_GRAY, ls='--', lw=1.5, label='基准切负荷')
    ax.set_xlabel('场景中故障发电机台数')
    ax.set_ylabel('总切负荷 / MW')
    ax.set_title('(a) 发电机故障数对切负荷的影响')
    ax.legend(fontsize=8)

    ax = axes[1]
    sizes = 26 + 16 * n_out
    scat = ax.scatter(n_line + n_xf, shed, c=n_off, cmap='viridis',
                      s=sizes, alpha=0.72, edgecolor='black', linewidth=0.35)
    ax.axhline(base, color=C_GRAY, ls='--', lw=1.5)
    cb = fig.colorbar(scat, ax=ax)
    cb.set_label('停机火电台数', fontsize=8.5)
    ax.set_xlabel('线路与节点变压器故障总数')
    ax.set_ylabel('总切负荷 / MW')
    ax.set_title('(b) 网络类故障与火电停机的耦合')

    ax = axes[2]
    healthy = shed[(n_gen == 0) & (n_line == 0) & (n_xf == 0)]
    only_gen = shed[(n_gen > 0) & (n_line == 0) & (n_xf == 0)]
    only_net = shed[(n_gen == 0) & ((n_line > 0) | (n_xf > 0))]
    mixed = shed[(n_gen > 0) & ((n_line > 0) | (n_xf > 0))]
    cats = [('无故障', healthy, '#95a5a6'),
            ('仅电源故障', only_gen, C_THERMAL),
            ('仅网络故障', only_net, '#e67e22'),
            ('电源+网络', mixed, '#8e44ad')]
    names = [c[0] + f'\n(n={len(c[1])})' for c in cats]
    means = [float(np.mean(c[1])) if len(c[1]) else 0 for c in cats]
    p95s = [float(np.percentile(c[1], 95)) if len(c[1]) else 0 for c in cats]
    xt = np.arange(len(cats))
    w = 0.36
    ax.bar(xt - w / 2, means, w, label='均值',
           color=[c[2] for c in cats], edgecolor='black', linewidth=0.5)
    ax.bar(xt + w / 2, p95s, w, label='95% 分位',
           color=[c[2] for c in cats], alpha=0.5,
           edgecolor='black', linewidth=0.5)
    ax.axhline(base, color=C_GRAY, ls='--', lw=1.5, label='基准切负荷')
    for i in range(len(cats)):
        ax.text(i - w / 2, means[i] + 30, f'{means[i]:.0f}',
                ha='center', fontsize=7.6)
        ax.text(i + w / 2, p95s[i] + 30, f'{p95s[i]:.0f}',
                ha='center', fontsize=7.6)
    ax.set_xticks(xt)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel('总切负荷 / MW')
    ax.set_title('(c) 不同故障组合的切负荷水平')
    ax.legend(fontsize=8)
    ax.set_ylim(0, max(p95s) * 1.25)

    fig.suptitle('图 8  切负荷风险的主导因素分析', fontsize=12,
                 fontweight='bold', y=1.03)
    fig.tight_layout()
    fig.savefig(OUTDIR / 'fig8_risk_drivers.png')
    plt.close(fig)


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    state = load_json('baseline_state.json')
    fp = load_json('fault_probability.json')
    stats = load_json('fault_scenario_opf_stats.json')
    meta = load_json('fault_scenarios_2000_meta.json')
    rows = load_summary_rows()

    fig1_framework()
    fig2_derating_and_load()
    fig3_baseline_dispatch(state)
    fig4_load_shedding(state)
    fig5_fault_probability(fp)
    fig6_monte_carlo(meta)
    fig7_shedding_distribution(stats, rows)
    fig8_driver_analysis(stats, rows)

    for p in sorted(OUTDIR.glob('*.png')):
        print(f'{p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB')


if __name__ == '__main__':
    main()
