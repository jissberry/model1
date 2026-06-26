#!/usr/bin/env python3
"""从 baseline_state.json 生成 docs 中“求解后基准状态”章节的 Markdown 表格。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with open(ROOT / 'verify/baseline_state.json', encoding='utf-8') as f:
    st = json.load(f)

s = st['summary']


def md_section():
    lines = []
    lines.append('## 11. 极热场景求解后系统运行基准状态（DC-OPF 最优解）')
    lines.append('')
    lines.append('以下为 $T=40℃$、$v=2\\,\\text{m/s}$、$G=900\\,\\text{W/m}^2$ 条件下 DC-OPF 最优解，'
                 '供后续极热条件下元件故障概率分析使用。潮流正方向为 $f_{bus}\\to t_{bus}$（MW）；'
                 '负值表示功率由 $t_{bus}$ 流向 $f_{bus}$。')
    lines.append('')
    lines.append('### 11.1 求解汇总')
    lines.append('')
    lines.append('| 指标 | 数值 |')
    lines.append('|---|---:|')
    lines.append(f"| 求解状态 | {s['status']} |")
    lines.append(f"| 目标函数最优值 ($/h) | {s['obj_total']:.2f} |")
    lines.append(f"| 发电成本 ($/h) | {s['gen_cost']:.2f} |")
    lines.append(f"| 切负荷惩罚成本 ($/h) | {s['shed_cost']:.2f} |")
    lines.append(f"| 总发电 $\\sum P_G$ (MW) | {s['total_Pg_MW']:.2f} |")
    lines.append(f"| 极热修正总需求 $\\sum D(T)$ (MW) | {s['total_D_MW']:.2f} |")
    lines.append(f"| 总切负荷 (MW) | {s['total_shed_MW']:.2f} ({s['total_shed_MW']/s['total_D_MW']*100:.2f}%) |")
    lines.append(f"| 实际供电负荷 (MW) | {s['total_served_MW']:.2f} |")
    lines.append(f"| 线路最大负载率 | {s['max_branch_loading_pct']:.2f}% |")
    lines.append(f"| 越限线路数 | {s['n_overloaded']} |")
    lines.append('')

    # Generators
    lines.append('### 11.2 发电机出力（10 台）')
    lines.append('')
    lines.append('| G | bus | 类型 | $P_G$ (MW) | 调度下界 | 调度上界 | 利用率 |')
    lines.append('|---|----:|------|----------:|---------:|---------:|-------:|')
    for g in st['generators']:
        lines.append(f"| G{g['G']} | {g['bus']} | {g['type']} | {g['Pg']:.2f} | "
                     f"{g['lb']:.1f} | {g['ub']:.1f} | {g['util_pct']:.1f}% |")
    lines.append(f"| **合计** | | | **{s['total_Pg_MW']:.2f}** | | | |")
    lines.append('')

    # Bus state - all 39
    lines.append('### 11.3 节点运行状态（39 节点）')
    lines.append('')
    lines.append('| bus | $\\theta$ (°) | $P_G$ (MW) | $D(T)$ (MW) | 切负荷 (MW) | 实际供电 (MW) | 净注入 (MW) |')
    lines.append('|----:|------------:|-----------:|------------:|------------:|--------------:|------------:|')
    for b in st['buses']:
        lines.append(f"| {b['bus']} | {b['theta_deg']:.3f} | {b['Pg']:.2f} | {b['D_T']:.2f} | "
                     f"{b['shed_total']:.2f} | {b['P_served']:.2f} | {b['P_inj']:.2f} |")
    lines.append('')

    # Load detail
    lines.append('### 11.4 负荷与切负荷明细（21 个负荷节点）')
    lines.append('')
    lines.append('| bus | $P_D^0$ | $D(T)$ | 一级需求 | 二级需求 | 三级需求 | 切除三级 | 切除合计 | 实际供电 |')
    lines.append('|----:|--------:|-------:|---------:|---------:|---------:|---------:|---------:|---------:|')
    for l in st['loads']:
        lines.append(f"| {l['bus']} | {l['Pd0']:.2f} | {l['D_T']:.2f} | {l['D_L1']:.2f} | "
                     f"{l['D_L2']:.2f} | {l['D_L3']:.2f} | {l['shed_L3']:.2f} | "
                     f"{l['shed_total']:.2f} | {l['P_served']:.2f} |")
    lines.append(f"| **合计** | **6254.23** | **{s['total_D_MW']:.2f}** | | | | "
                 f"**{s['total_shed_MW']:.2f}** | **{s['total_shed_MW']:.2f}** | **{s['total_served_MW']:.2f}** |")
    lines.append('')
    lines.append('> 最优解仅切除**三级（可中断）负荷**，一/二级关键负荷切除量均为 0。')
    lines.append('')

    # Branches - all 46
    lines.append('### 11.5 支路/变压器潮流（46 条完整表）')
    lines.append('')
    lines.append('列说明：`类型` 为线路或变压器；`tap` 为变比（线路取 1.0）；`潮流` 为 $f_{bus}\\to t_{bus}$ 方向有功 (MW)。')
    lines.append('')
    lines.append('| No. | fbus | tbus | 类型 | tap | 潮流 (MW) | 限额 (MW) | 负载率 (%) | 功率方向 |')
    lines.append('|----:|-----:|-----:|------|----:|----------:|----------:|-----------:|----------|')
    for b in st['branches']:
        typ = '变压器' if b['is_transformer'] else '线路'
        tap = b['tap'] if b['is_transformer'] else 1.0
        lines.append(f"| {b['L']} | {b['fbus']} | {b['tbus']} | {typ} | {tap:.3f} | "
                     f"{b['flow_MW']:.2f} | {b['rateA']:.0f} | {b['loading_pct']:.2f} | {b['direction']} |")
    lines.append('')

    # Transformer only
    lines.append('### 11.6 变压器支路潮流专表（12 台）')
    lines.append('')
    lines.append('| No. | fbus | tbus | tap | 潮流 (MW) | 限额 (MW) | 负载率 (%) | 功率方向 |')
    lines.append('|----:|-----:|-----:|----:|----------:|----------:|-----------:|----------|')
    for b in st['branches']:
        if b['is_transformer']:
            lines.append(f"| {b['L']} | {b['fbus']} | {b['tbus']} | {b['tap']:.3f} | "
                         f"{b['flow_MW']:.2f} | {b['rateA']:.0f} | {b['loading_pct']:.2f} | {b['direction']} |")
    lines.append('')
    lines.append('> 满载断面：L27（bus 16–19），负载率 100.0%。')
    lines.append('')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(md_section())
