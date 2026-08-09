#!/usr/bin/env python3
"""绘制修改版 IEEE 39 节点系统简化单线示意图。

保留 case39 的 39 个节点、46 条支路真实连接关系；图形仅用于论文/PPT
示意，不按地理位置和电气距离绘制。
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "verify"
OUT = ROOT / "docs" / "figures"
sys.path.insert(0, str(VERIFY))

import case_data as cd  # noqa: E402


# 手工布局：沿用 IEEE 39 节点常见单线图的拓扑分区，而非地理坐标。
POS = {
    1: (1.2, 2.0), 2: (2.1, 3.0), 3: (3.5, 3.0), 4: (4.8, 3.0),
    5: (6.0, 3.0), 6: (7.1, 3.0), 7: (7.1, 1.9), 8: (6.0, 1.4),
    9: (4.8, 1.4), 10: (7.8, 5.0), 11: (7.1, 4.1), 12: (7.1, 5.0),
    13: (6.3, 5.0), 14: (5.5, 3.8), 15: (5.2, 4.5), 16: (4.5, 5.25),
    17: (3.25, 4.8), 18: (3.8, 4.0), 19: (3.55, 6.25), 20: (2.4, 6.25),
    21: (4.8, 6.35), 22: (6.0, 6.35), 23: (7.1, 6.35), 24: (6.0, 5.25),
    25: (1.3, 3.0), 26: (1.4, 4.0), 27: (2.1, 4.8), 28: (0.45, 4.2),
    29: (0.65, 5.45), 30: (2.25, 1.65), 31: (8.15, 2.45), 32: (8.65, 5.75),
    33: (3.2, 7.35), 34: (1.5, 7.2), 35: (6.0, 7.45), 36: (7.55, 7.45),
    37: (0.15, 2.35), 38: (-0.35, 6.25), 39: (3.0, 1.4),
}

TYPE_COLOR = {
    "hydro": "#1674B8",
    "coal": "#8B3A2B",
    "gas": "#E36C09",
    "wind": "#2E8B57",
    "solar": "#D9A400",
}
TYPE_CN = {
    "hydro": "水电",
    "coal": "燃煤",
    "gas": "燃气",
    "wind": "风电",
    "solar": "光伏",
}


def gen_key(gen):
    _, gtype, fuel, *_ = gen
    return fuel if gtype == "thermal" else gtype


GEN_BY_BUS = {g[0]: (i + 1, g) for i, g in enumerate(cd.GENS)}


def draw_busbar(ax, bus, x, y):
    """绘制竖向母线和节点编号。"""
    ax.plot([x, x], [y - 0.16, y + 0.16], color="black", lw=4.0,
            solid_capstyle="butt", zorder=7)
    ax.text(x - 0.08, y + 0.25, str(bus), ha="right", va="bottom",
            fontsize=9.5, fontweight="bold", color="black", zorder=9)
    if bus == cd.SLACK_BUS:
        ax.text(x + 0.10, y + 0.25, "★", ha="left", va="bottom",
                fontsize=10, color="#C00000", zorder=9)


def draw_transformer(ax, p1, p2, color):
    """在线段中部绘制简化双圆变压器符号。"""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    nx, ny = -dy / length, dx / length
    mx, my = x1 + 0.58 * dx, y1 + 0.58 * dy
    for shift in (-0.055, 0.055):
        cx = mx + shift * dx / length
        cy = my + shift * dy / length
        ax.add_patch(Circle((cx, cy), 0.075, facecolor="white",
                            edgecolor=color, lw=1.15, zorder=6))


def draw_generator(ax, bus, idx, gen):
    """在发电机母线外侧绘制 G 符号和类型标签。"""
    x, y = POS[bus]
    if bus == 39:
        vx, vy = -0.35, -0.80
    else:
        # 叶节点以其唯一相邻支路反向延伸。
        neighbors = []
        for f, t, *_ in cd.BRANCHES:
            if f == bus:
                neighbors.append(t)
            elif t == bus:
                neighbors.append(f)
        n = neighbors[0]
        nx, ny = POS[n]
        vx, vy = x - nx, y - ny
        norm = max((vx * vx + vy * vy) ** 0.5, 1e-9)
        vx, vy = 0.52 * vx / norm, 0.52 * vy / norm

    key = gen_key(gen)
    color = TYPE_COLOR[key]
    gx, gy = x + vx, y + vy
    ax.plot([x, gx], [y, gy], color=color, lw=2.2, zorder=3)
    ax.add_patch(Circle((gx, gy), 0.15, facecolor="white",
                        edgecolor=color, lw=1.8, zorder=8))
    ax.text(gx, gy, "G", ha="center", va="center", fontsize=7.6,
            fontweight="bold", color=color, zorder=9)

    # 标签位置根据方向自动放在外侧。
    ha = "left" if vx >= 0 else "right"
    tx = gx + (0.18 if vx >= 0 else -0.18)
    ty = gy + (0.13 if vy >= 0 else -0.25)
    suffix = "（平衡）" if bus == cd.SLACK_BUS else ""
    ax.text(tx, ty, f"G{idx} {TYPE_CN[key]}{suffix}",
            ha=ha, va="center", fontsize=8.2, fontweight="bold",
            color=color, zorder=9)


def main():
    plt.rcParams["font.sans-serif"] = [
        "WenQuanYi Micro Hei", "Droid Sans Fallback", "DejaVu Sans"
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(13.5, 8.8))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.15, 9.55)
    ax.set_ylim(-0.65, 9.20)

    # 淡色分区背景，帮助识别网络主体与电源接入。
    ax.add_patch(FancyBboxPatch(
        (-0.75, 1.0), 9.5, 5.75,
        boxstyle="round,pad=0.02,rounding_size=0.10",
        facecolor="#FAFBFC", edgecolor="#D9E1E8", lw=1.0, zorder=0,
    ))

    # 支路：发电机升压支路按电源类型着色，其余为深灰。
    tap_edges = set()
    for f, t, _, _, tap in cd.BRANCHES:
        p1, p2 = POS[f], POS[t]
        gen_bus = t if t in GEN_BY_BUS and t != 39 else (
            f if f in GEN_BY_BUS and f != 39 else None
        )
        if gen_bus is not None:
            color = TYPE_COLOR[gen_key(GEN_BY_BUS[gen_bus][1])]
            lw = 2.1
        else:
            color = "#3D4650"
            lw = 1.35
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, lw=lw,
                solid_capstyle="round", zorder=2)
        if tap not in (0.0, 1.0):
            draw_transformer(ax, p1, p2, color)
            tap_edges.add((f, t))

    # 对发电机接入支路补画双圆（即便 tap=1.0，也作为升压变压器示意）。
    for f, t, *_ in cd.BRANCHES:
        if t in range(30, 39) or f in range(30, 39):
            if (f, t) not in tap_edges:
                draw_transformer(ax, POS[f], POS[t], "#566573")

    # 负荷：红色小三角向下，重点负荷额外标注。
    major_loads = {4, 8, 20, 39}
    for bus in cd.PD0:
        x, y = POS[bus]
        ax.scatter([x], [y - 0.30], marker="v", s=28 if bus in major_loads else 18,
                   color="#D62728", zorder=8)
        if bus in major_loads:
            ax.text(x + 0.14, y - 0.36, f"{cd.PD0[bus]:g} MW",
                    ha="left", va="center", fontsize=6.8, color="#B22222")

    # 母线与发电机。
    for bus in range(1, 40):
        draw_busbar(ax, bus, *POS[bus])
    for bus, (idx, gen) in GEN_BY_BUS.items():
        draw_generator(ax, bus, idx, gen)

    # 图题与说明。
    ax.text(4.1, 8.90, "修改版 IEEE 39 节点系统简化单线示意图",
            ha="center", va="center", fontsize=16, fontweight="bold",
            color="#1F4E79")
    ax.text(4.1, 8.54,
            "39 节点 · 46 支路 · 10 台发电机（火电 / 水电 / 风电 / 光伏）",
            ha="center", va="center", fontsize=9.5, color="#5B6573")

    # 图例。
    legend_y = -0.32
    ax.plot([-0.75, -0.25], [legend_y, legend_y], color="#3D4650", lw=1.5)
    ax.text(-0.15, legend_y, "输电支路", va="center", fontsize=8.3)
    ax.scatter([1.05], [legend_y], marker="v", s=26, color="#D62728")
    ax.text(1.22, legend_y, "负荷节点", va="center", fontsize=8.3)
    lx = 2.20
    for key in ("hydro", "coal", "gas", "wind", "solar"):
        c = TYPE_COLOR[key]
        ax.add_patch(Circle((lx, legend_y), 0.08, facecolor="white",
                            edgecolor=c, lw=1.5))
        ax.text(lx + 0.13, legend_y, TYPE_CN[key], va="center",
                fontsize=8.3, color=c)
        lx += 0.83
    ax.text(7.25, legend_y, "★ 平衡节点（31）", va="center",
            fontsize=8.3, color="#C00000")
    ax.text(9.28, -0.58, "注：位置仅为拓扑示意，不代表地理距离。",
            ha="right", va="bottom", fontsize=7.5, color="#777777")

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "fig9_modified_ieee39_schematic.png"
    svg = OUT / "fig9_modified_ieee39_schematic.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.08,
                facecolor="white")
    fig.savefig(svg, bbox_inches="tight", pad_inches=0.08,
                facecolor="white")
    plt.close(fig)
    print(png.relative_to(ROOT))
    print(svg.relative_to(ROOT))


if __name__ == "__main__":
    main()
