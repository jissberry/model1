#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate focused figures for fault-scenario evaluation results.

The script intentionally avoids plotting dependencies. It reads the existing
CSV/JSON outputs under ``verify/`` and writes two UTF-8 SVG files:

* docs/figures/load_shed_distribution.svg
* docs/figures/fault_distribution.svg

Chinese labels are stored as unicode escapes so the source file remains ASCII
and is robust in the cloud editing environment.
"""
from __future__ import annotations

import csv
import html
import json
import math
import os
from collections import Counter, defaultdict
from typing import Iterable


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERIFY = os.path.join(ROOT, "verify")
FIG_DIR = os.path.join(ROOT, "docs", "figures")
FONT = (
    "'WenQuanYi Micro Hei','Noto Sans CJK SC','PingFang SC',"
    "'Microsoft YaHei',sans-serif"
)

T = {
    "load_title": "\u5207\u8d1f\u8377\u5206\u5e03\uff082000 \u4e2a\u6545\u969c\u573a\u666f\uff09",
    "load_sub": "\u5927\u591a\u6570\u573a\u666f\u505c\u7559\u5728\u57fa\u51c6\u5207\u8d1f\u8377\u9644\u8fd1\uff0c\u53f3\u5c3e\u7531\u9ad8\u5f71\u54cd\u6545\u969c\u62ac\u5347",
    "shed_x": "\u603b\u5207\u8d1f\u8377 / MW",
    "scene_log_y": "\u573a\u666f\u6570\uff08log10\uff09",
    "baseline": "\u57fa\u51c6",
    "near_base": "\u57fa\u51c6\u9644\u8fd1",
    "tail": "\u53f3\u5c3e\u98ce\u9669",
    "scenes": "\u573a\u666f",
    "mean": "\u5747\u503c",
    "median": "\u4e2d\u4f4d\u6570",
    "max": "\u6700\u5927",
    "fault_title": "\u6545\u969c\u5206\u5e03\uff082000 \u4e2a\u8499\u7279\u5361\u6d1b\u573a\u666f\uff09",
    "fault_sub": "\u65e0\u6545\u969c\u573a\u666f\u5360\u591a\u6570\uff1b\u7535\u6e90\u6545\u969c\u662f\u4e3b\u8981\u6545\u969c\u7c7b\u578b\uff0c\u53d8\u538b\u5668\u6545\u969c\u6781\u5c11",
    "combo": "\u6545\u969c\u7ec4\u5408\u573a\u666f\u6570",
    "top_components": "\u9ad8\u9891\u6545\u969c\u5143\u4ef6\uff08\u62bd\u6837\u51fa\u73b0\u6b21\u6570\uff09",
    "no_fault": "\u65e0\u6545\u969c",
    "source_only": "\u4ec5\u7535\u6e90",
    "network_only": "\u4ec5\u7f51\u7edc",
    "mixed": "\u6df7\u5408\u6545\u969c",
    "source": "\u7535\u6e90",
    "line": "\u7ebf\u8def",
    "transformer": "\u53d8\u538b\u5668",
    "any_fault": "\u542b\u8be5\u7c7b\u6545\u969c\u573a\u666f",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def quantile(values: Iterable[float], q: float) -> float:
    xs = sorted(values)
    if not xs:
        raise ValueError("empty data")
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def read_summary() -> list[dict[str, str]]:
    path = os.path.join(VERIFY, "fault_scenario_opf_summary.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_fault_vectors() -> list[dict[str, str]]:
    path = os.path.join(VERIFY, "fault_scenarios_2000.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def svg_header(width: int, height: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="5" flood-color="#1e293b" flood-opacity="0.12"/>
    </filter>
    <linearGradient id="blueTitle" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#1e3a8a"/>
      <stop offset="1" stop-color="#2563eb"/>
    </linearGradient>
  </defs>
"""


def title_block(title: str, subtitle: str) -> str:
    return f"""
  <rect x="28" y="24" width="1044" height="72" rx="18" fill="url(#blueTitle)" filter="url(#shadow)"/>
  <text x="54" y="61" font-size="27" font-weight="800" fill="#ffffff">{esc(title)}</text>
  <text x="54" y="84" font-size="14" fill="#dbeafe">{esc(subtitle)}</text>
"""


def write_svg(filename: str, content: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote", path, len(content.encode("utf-8")), "bytes")


def generate_load_shed_distribution(rows: list[dict[str, str]]) -> None:
    values = [float(r["total_shed_MW"]) for r in rows]
    stats = json.load(open(os.path.join(VERIFY, "fault_scenario_opf_stats.json"), encoding="utf-8"))
    baseline = float(stats["baseline_total_shed_MW"])
    n = len(values)
    mean = sum(values) / n
    med = quantile(values, 0.50)
    p90 = quantile(values, 0.90)
    p95 = quantile(values, 0.95)
    p99 = quantile(values, 0.99)
    vmax = max(values)
    near_baseline = sum(v <= baseline + 1.0 for v in values)

    bins = [700, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 2800, 3000, 3400]
    counts = [sum(a <= v < b for v in values) for a, b in zip(bins, bins[1:])]

    width, height = 1100, 620
    x0, y0, chart_w, chart_h = 70, 130, 710, 365
    xmin, xmax = 700, 3400
    ymax = max(counts)
    logmax = math.log10(ymax + 1)
    bottom = y0 + chart_h

    def sx(v: float) -> float:
        return x0 + (v - xmin) / (xmax - xmin) * chart_w

    def sy_count(c: float) -> float:
        return bottom - math.log10(c + 1) / logmax * chart_h

    parts = [svg_header(width, height), title_block(T["load_title"], T["load_sub"])]
    parts.append(f"""
  <rect x="28" y="112" width="1044" height="470" rx="18" fill="#ffffff" filter="url(#shadow)"/>
  <line x1="{x0}" y1="{bottom}" x2="{x0 + chart_w}" y2="{bottom}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{x0}" y1="{y0}" x2="{x0}" y2="{bottom}" stroke="#334155" stroke-width="1.5"/>
""")

    for tick in [1, 10, 100, 1000]:
        y = sy_count(tick)
        parts.append(f'  <line x1="{x0}" y1="{y:.1f}" x2="{x0 + chart_w}" y2="{y:.1f}" stroke="#e2e8f0"/>\n')
        parts.append(f'  <text x="{x0 - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#64748b">{tick}</text>\n')

    for tick in [800, 1200, 1600, 2000, 2400, 2800, 3200]:
        x = sx(tick)
        parts.append(f'  <line x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom + 6}" stroke="#334155"/>\n')
        parts.append(f'  <text x="{x:.1f}" y="{bottom + 24}" text-anchor="middle" font-size="12" fill="#475569">{tick}</text>\n')

    bar_color = "#60a5fa"
    for (a, b), c in zip(zip(bins, bins[1:]), counts):
        x = sx(a) + 2
        w = max(sx(b) - sx(a) - 4, 1)
        y = sy_count(c)
        h = bottom - y
        parts.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="3" fill="{bar_color}" opacity="0.86"/>\n')
        if c >= 100:
            parts.append(f'  <text x="{x + w / 2:.1f}" y="{y - 7:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#1d4ed8">{c}</text>\n')

    markers = [
        (baseline, T["baseline"], "#64748b", "4 4", y0 + 10),
        (p90, "P90", "#f59e0b", "5 4", y0 + 52),
        (p95, "P95", "#f97316", "5 4", y0 + 94),
        (p99, "P99", "#dc2626", "5 4", y0 + 136),
    ]
    for value, label, color, dash, label_y in markers:
        x = sx(value)
        parts.append(f'  <line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{bottom}" stroke="{color}" stroke-width="2.2" stroke-dasharray="{dash}"/>\n')
        parts.append(f'  <text x="{x + 6:.1f}" y="{label_y:.1f}" font-size="13" font-weight="800" fill="{color}">{esc(label)} {fmt(value, 0)}</text>\n')

    parts.append(f"""
  <text x="{x0 + chart_w / 2}" y="{height - 82}" text-anchor="middle" font-size="15" font-weight="700" fill="#334155">{esc(T['shed_x'])}</text>
  <text x="24" y="{y0 + chart_h / 2}" transform="rotate(-90 24 {y0 + chart_h / 2})" text-anchor="middle" font-size="15" font-weight="700" fill="#334155">{esc(T['scene_log_y'])}</text>
""")

    card_x = 825
    cards = [
        (T["near_base"], f"{near_baseline}/{n}", f"{near_baseline / n * 100:.1f}% {T['scenes']}", "#eff6ff", "#2563eb"),
        ("P90 / P95 / P99", f"{fmt(p90,0)} / {fmt(p95,0)} / {fmt(p99,0)}", "MW", "#fff7ed", "#f97316"),
        (T["mean"], fmt(mean, 1), "MW", "#f8fafc", "#334155"),
        (T["max"], fmt(vmax, 1), "MW", "#fef2f2", "#dc2626"),
    ]
    for i, (label, value, unit, bg, fg) in enumerate(cards):
        y = 138 + i * 92
        value_size = 20 if label == "P90 / P95 / P99" else 25
        unit_x = card_x + 18 if label == "P90 / P95 / P99" else card_x + 152
        unit_y = y + 68 if label == "P90 / P95 / P99" else y + 55
        parts.append(f"""
  <rect x="{card_x}" y="{y}" width="210" height="74" rx="14" fill="{bg}" stroke="#e2e8f0"/>
  <text x="{card_x + 18}" y="{y + 25}" font-size="13" font-weight="700" fill="#64748b">{esc(label)}</text>
  <text x="{card_x + 18}" y="{y + 55}" font-size="{value_size}" font-weight="850" fill="{fg}">{esc(value)}</text>
  <text x="{unit_x}" y="{unit_y}" font-size="12" font-weight="700" fill="#64748b">{esc(unit)}</text>
""")

    parts.append(f"""
  <text x="{card_x}" y="535" font-size="13" fill="#475569">{esc(T['tail'])}: >=2000 MW {sum(v >= 2000 for v in values)} {esc(T['scenes'])}</text>
</svg>
""")
    write_svg("load_shed_distribution.svg", "".join(parts))


def generate_fault_distribution(rows: list[dict[str, str]], vectors: list[dict[str, str]]) -> None:
    n = len(rows)
    category_order = [T["no_fault"], T["source_only"], T["network_only"], T["mixed"]]
    colors = {
        T["no_fault"]: "#94a3b8",
        T["source_only"]: "#dc2626",
        T["network_only"]: "#f97316",
        T["mixed"]: "#7c3aed",
    }
    cat_counts = Counter()
    type_scene_counts = Counter()
    for r in rows:
        ng = int(r["n_gen_fault"])
        nl = int(r["n_line_fault_direct"])
        nt = int(r["n_transformer_fault"])
        network = (nl + nt) > 0
        if ng:
            type_scene_counts[T["source"]] += 1
        if nl:
            type_scene_counts[T["line"]] += 1
        if nt:
            type_scene_counts[T["transformer"]] += 1
        if ng == 0 and not network:
            cat_counts[T["no_fault"]] += 1
        elif ng > 0 and not network:
            cat_counts[T["source_only"]] += 1
        elif ng == 0 and network:
            cat_counts[T["network_only"]] += 1
        else:
            cat_counts[T["mixed"]] += 1

    comp_counts = Counter()
    for row in vectors:
        for key, val in row.items():
            if key != "scenario" and val == "0":
                comp_counts[key] += 1
    top_components = comp_counts.most_common(12)

    width, height = 1100, 620
    parts = [svg_header(width, height), title_block(T["fault_title"], T["fault_sub"])]
    parts.append("""
  <rect x="28" y="112" width="1044" height="470" rx="18" fill="#ffffff" filter="url(#shadow)"/>
""")

    # Left panel: scenario-combination distribution.
    x0, y0, chart_w, chart_h = 70, 154, 460, 315
    bottom = y0 + chart_h
    ymax = 1500

    def sy(v: float) -> float:
        return bottom - v / ymax * chart_h

    parts.append(f'  <text x="{x0}" y="135" font-size="17" font-weight="800" fill="#1e293b">{esc(T["combo"])}</text>\n')
    parts.append(f'  <line x1="{x0}" y1="{bottom}" x2="{x0 + chart_w}" y2="{bottom}" stroke="#334155" stroke-width="1.5"/>\n')
    parts.append(f'  <line x1="{x0}" y1="{y0}" x2="{x0}" y2="{bottom}" stroke="#334155" stroke-width="1.5"/>\n')
    for tick in [0, 500, 1000, 1500]:
        y = sy(tick)
        parts.append(f'  <line x1="{x0}" y1="{y:.1f}" x2="{x0 + chart_w}" y2="{y:.1f}" stroke="#e2e8f0"/>\n')
        parts.append(f'  <text x="{x0 - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#64748b">{tick}</text>\n')

    gap = 28
    bw = (chart_w - gap * 5) / 4
    for i, cat in enumerate(category_order):
        c = cat_counts[cat]
        x = x0 + gap + i * (bw + gap)
        y = sy(c)
        h = bottom - y
        parts.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="6" fill="{colors[cat]}"/>\n')
        parts.append(f'  <text x="{x + bw / 2:.1f}" y="{y - 22:.1f}" text-anchor="middle" font-size="16" font-weight="850" fill="{colors[cat]}">{c}</text>\n')
        parts.append(f'  <text x="{x + bw / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#64748b">{c / n * 100:.1f}%</text>\n')
        parts.append(f'  <text x="{x + bw / 2:.1f}" y="{bottom + 25:.1f}" text-anchor="middle" font-size="13" font-weight="700" fill="#334155">{esc(cat)}</text>\n')

    # Right panel: top component realized failures.
    rx, ry, rw = 610, 154, 405
    parts.append(f'  <text x="{rx}" y="135" font-size="17" font-weight="800" fill="#1e293b">{esc(T["top_components"])}</text>\n')
    max_top = max(c for _, c in top_components)
    for i, (comp, c) in enumerate(top_components):
        y = ry + i * 24
        if comp.startswith("G"):
            color = "#dc2626"
        elif comp.startswith("L"):
            color = "#f97316"
        else:
            color = "#7c3aed"
        w = c / max_top * (rw - 86)
        parts.append(f'  <text x="{rx}" y="{y + 14}" font-size="13" font-weight="800" fill="#334155">{esc(comp)}</text>\n')
        parts.append(f'  <rect x="{rx + 45}" y="{y + 2}" width="{w:.1f}" height="16" rx="4" fill="{color}" opacity="0.82"/>\n')
        parts.append(f'  <text x="{rx + 54 + w:.1f}" y="{y + 15}" font-size="12" font-weight="800" fill="{color}">{c}</text>\n')

    # Bottom cards: scenario-level type coverage and component failure totals.
    total_component_by_type = {
        T["source"]: sum(c for k, c in comp_counts.items() if k.startswith("G")),
        T["line"]: sum(c for k, c in comp_counts.items() if k.startswith("L")),
        T["transformer"]: sum(c for k, c in comp_counts.items() if k.startswith("T")),
    }
    card_data = [
        (T["source"], type_scene_counts[T["source"]], total_component_by_type[T["source"]], "#fee2e2", "#dc2626"),
        (T["line"], type_scene_counts[T["line"]], total_component_by_type[T["line"]], "#ffedd5", "#f97316"),
        (T["transformer"], type_scene_counts[T["transformer"]], total_component_by_type[T["transformer"]], "#f3e8ff", "#7c3aed"),
    ]
    for i, (label, scene_count, comp_total, bg, fg) in enumerate(card_data):
        x = 610 + i * 142
        y = 470
        parts.append(f"""
  <rect x="{x}" y="{y}" width="126" height="78" rx="14" fill="{bg}" stroke="#e2e8f0"/>
  <text x="{x + 14}" y="{y + 24}" font-size="14" font-weight="800" fill="{fg}">{esc(label)}</text>
  <text x="{x + 14}" y="{y + 49}" font-size="22" font-weight="850" fill="#1e293b">{scene_count}</text>
  <text x="{x + 67}" y="{y + 48}" font-size="12" fill="#64748b">{scene_count / n * 100:.1f}%</text>
  <text x="{x + 14}" y="{y + 67}" font-size="11" fill="#64748b">{esc(T['any_fault'])} / {comp_total}</text>
""")

    parts.append("</svg>\n")
    write_svg("fault_distribution.svg", "".join(parts))


def main() -> None:
    rows = read_summary()
    vectors = read_fault_vectors()
    generate_load_shed_distribution(rows)
    generate_fault_distribution(rows, vectors)


if __name__ == "__main__":
    main()
