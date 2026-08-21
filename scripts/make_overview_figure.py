#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the modified IEEE 39-bus system overview figure (SVG).

All figures shown are verified against the case data in
``verify/case_data.py`` / ``matlab/case39_ehnw.m``:

    39 buses, 46 branches, 10 generators, 29 node transformers (non-source
    buses 1-29), generator mix 6 thermal / 1 hydro / 2 wind / 1 solar,
    weather T=40C, v=2 m/s, G=900 W/m^2.

Chinese labels are written as unicode escapes so the source stays pure
ASCII; the output SVG is written as UTF-8.
"""
import os

# ---- verified Chinese labels (unicode escapes -> UTF-8 on write) ----
T = {
    "title":   "\u4fee\u6539\u7248 IEEE 39 \u8282\u70b9\u7cfb\u7edf",
    "subtitle":"New England 10 \u673a 39 \u8282\u70b9 \xb7 \u6781\u70ed\u65e0\u98ce\uff08Extreme-Heat / No-Wind\uff09\u573a\u666f",
    "scale":   "\u7cfb\u7edf\u89c4\u6a21",
    "bus":     "\u8282\u70b9",
    "bus_sub": "bus\uff0821 \u4e2a\u8d1f\u8377\u8282\u70b9\uff09",
    "branch":  "\u652f\u8def",
    "branch_sub":"\u542b 12 \u6761\u5e76\u7f51\u53d8\u652f\u8def",
    "gen":     "\u53d1\u7535\u673a",
    "gen_sub": "\u989d\u5b9a\u5408\u8ba1 7150 MW",
    "xf":      "\u8282\u70b9\u53d8\u538b\u5668",
    "xf_sub1": "\u975e\u7535\u6e90\u8282\u70b9",
    "xf_sub2": "bus 1-29 \u5404\u4e00\u53f0",
    "mix":     "\u673a\u7ec4\u6784\u6210",
    "thermal": "\u706b\u7535",
    "hydro":   "\u6c34\u7535",
    "wind":    "\u98ce\u7535",
    "solar":   "\u5149\u4f0f",
    "weather": "\u6c14\u8c61\u8f93\u5165 \xb7 \u6781\u70ed\u65e0\u98ce",
    "Tlab":    "\u73af\u5883\u6e29\u5ea6 T",
    "vlab":    "\u98ce\u901f v",
    "Glab":    "\u8f90\u7167\u5ea6 G",
}

FONT = ("'WenQuanYi Micro Hei','Noto Sans CJK SC','PingFang SC',"
        "'Microsoft YaHei',sans-serif")

SVG = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="680" height="704" viewBox="0 0 680 704" font-family="{FONT}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f5f7fc"/>
      <stop offset="1" stop-color="#e9edf7"/>
    </linearGradient>
    <linearGradient id="titlebar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#1d4ed8"/>
      <stop offset="1" stop-color="#4f46e5"/>
    </linearGradient>
    <filter id="softshadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#1e293b" flood-opacity="0.12"/>
    </filter>
    <filter id="cardshadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#334155" flood-opacity="0.10"/>
    </filter>
  </defs>

  <rect x="0" y="0" width="680" height="704" fill="url(#bg)"/>
  <rect x="24" y="24" width="632" height="656" rx="24" fill="#ffffff" filter="url(#softshadow)"/>

  <rect x="48" y="48" width="584" height="76" rx="16" fill="url(#titlebar)"/>
  <text x="340" y="90" text-anchor="middle" font-size="30" font-weight="700" fill="#ffffff">{T['title']}</text>
  <text x="340" y="113" text-anchor="middle" font-size="14" fill="#dbe4ff">{T['subtitle']}</text>

  <text x="52" y="158" font-size="15" font-weight="700" fill="#334155">{T['scale']}</text>
  <rect x="118" y="149" width="514" height="2" fill="#e2e8f0"/>

  <g filter="url(#cardshadow)"><rect x="52" y="170" width="278" height="112" rx="14" fill="#ffffff" stroke="#eef2f9"/></g>
  <rect x="52" y="170" width="6" height="112" rx="3" fill="#2563eb"/>
  <text x="86" y="238" font-size="52" font-weight="800" fill="#2563eb">39</text>
  <text x="196" y="216" font-size="19" font-weight="700" fill="#1e293b">{T['bus']}</text>
  <text x="196" y="240" font-size="13" fill="#64748b">{T['bus_sub']}</text>

  <g filter="url(#cardshadow)"><rect x="350" y="170" width="278" height="112" rx="14" fill="#ffffff" stroke="#eef2f9"/></g>
  <rect x="350" y="170" width="6" height="112" rx="3" fill="#0d9488"/>
  <text x="384" y="238" font-size="52" font-weight="800" fill="#0d9488">46</text>
  <text x="494" y="216" font-size="19" font-weight="700" fill="#1e293b">{T['branch']}</text>
  <text x="494" y="240" font-size="13" fill="#64748b">{T['branch_sub']}</text>

  <g filter="url(#cardshadow)"><rect x="52" y="298" width="278" height="112" rx="14" fill="#ffffff" stroke="#eef2f9"/></g>
  <rect x="52" y="298" width="6" height="112" rx="3" fill="#ea580c"/>
  <text x="86" y="366" font-size="52" font-weight="800" fill="#ea580c">10</text>
  <text x="196" y="344" font-size="19" font-weight="700" fill="#1e293b">{T['gen']}</text>
  <text x="196" y="368" font-size="13" fill="#64748b">{T['gen_sub']}</text>

  <g filter="url(#cardshadow)"><rect x="350" y="298" width="278" height="112" rx="14" fill="#ffffff" stroke="#eef2f9"/></g>
  <rect x="350" y="298" width="6" height="112" rx="3" fill="#7c3aed"/>
  <text x="384" y="366" font-size="52" font-weight="800" fill="#7c3aed">29</text>
  <text x="494" y="338" font-size="19" font-weight="700" fill="#1e293b">{T['xf']}</text>
  <text x="494" y="360" font-size="13" fill="#64748b">{T['xf_sub1']}</text>
  <text x="494" y="378" font-size="13" fill="#64748b">{T['xf_sub2']}</text>

  <text x="52" y="452" font-size="15" font-weight="700" fill="#334155">{T['mix']}</text>
  <rect x="118" y="443" width="514" height="2" fill="#e2e8f0"/>
  <g font-size="15" font-weight="600">
    <rect x="52" y="466" width="132" height="46" rx="10" fill="#f1f5f9" stroke="#e2e8f0"/>
    <circle cx="76" cy="489" r="7" fill="#475569"/>
    <text x="92" y="494" fill="#334155">{T['thermal']} <tspan font-weight="800" fill="#1e293b">6</tspan></text>
    <rect x="196" y="466" width="132" height="46" rx="10" fill="#eff6ff" stroke="#dbeafe"/>
    <circle cx="220" cy="489" r="7" fill="#0284c7"/>
    <text x="236" y="494" fill="#334155">{T['hydro']} <tspan font-weight="800" fill="#1e293b">1</tspan></text>
    <rect x="340" y="466" width="132" height="46" rx="10" fill="#ecfdf5" stroke="#d1fae5"/>
    <circle cx="364" cy="489" r="7" fill="#14b8a6"/>
    <text x="380" y="494" fill="#334155">{T['wind']} <tspan font-weight="800" fill="#1e293b">2</tspan></text>
    <rect x="484" y="466" width="148" height="46" rx="10" fill="#fffbeb" stroke="#fef3c7"/>
    <circle cx="508" cy="489" r="7" fill="#f59e0b"/>
    <text x="524" y="494" fill="#334155">{T['solar']} <tspan font-weight="800" fill="#1e293b">1</tspan></text>
  </g>

  <text x="52" y="556" font-size="15" font-weight="700" fill="#dc2626">{T['weather']}</text>
  <rect x="200" y="547" width="432" height="2" fill="#fee2e2"/>
  <g>
    <rect x="52" y="570" width="184" height="86" rx="14" fill="#fef2f2" stroke="#fee2e2"/>
    <text x="70" y="600" font-size="14" fill="#b91c1c">{T['Tlab']}</text>
    <text x="70" y="640" font-size="34" font-weight="800" fill="#dc2626">40<tspan font-size="18" font-weight="600"> \xb0C</tspan></text>
    <rect x="248" y="570" width="184" height="86" rx="14" fill="#f0f9ff" stroke="#e0f2fe"/>
    <text x="266" y="600" font-size="14" fill="#0369a1">{T['vlab']}</text>
    <text x="266" y="640" font-size="34" font-weight="800" fill="#0284c7">2<tspan font-size="18" font-weight="600"> m/s</tspan></text>
    <rect x="444" y="570" width="188" height="86" rx="14" fill="#fffbeb" stroke="#fef3c7"/>
    <text x="462" y="600" font-size="14" fill="#b45309">{T['Glab']}</text>
    <text x="462" y="640" font-size="34" font-weight="800" fill="#d97706">900<tspan font-size="16" font-weight="600"> W/m\xb2</tspan></text>
  </g>
</svg>
"""


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "figures",
                       "ieee39_overview.svg")
    out = os.path.abspath(out)
    with open(out, "w", encoding="utf-8") as f:
        f.write(SVG)
    print("wrote", out, len(SVG.encode("utf-8")), "bytes")


if __name__ == "__main__":
    main()
