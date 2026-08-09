#!/usr/bin/env python3
"""Convert docs/07 LaTeX math to Word UnicodeMath linear format."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'docs/07_极热无风源荷失衡与热故障耦合风险评估论文初稿.md'
LATEX_SRC = ROOT / 'docs/07_极热无风源荷失衡与热故障耦合风险评估论文初稿.latex.md'


def strip_tag(body: str) -> tuple[str, str | None]:
    m = re.search(r'\\tag\{(\d+)\}\s*$', body.strip(), flags=re.MULTILINE)
    if not m:
        return body.strip(), None
    body = body[: m.start()].strip()
    return body, m.group(1)


def convert_latex_to_unicodemath(expr: str) -> str:
    s = expr.strip()
    s = re.sub(r'\\tag\{\d+\}', '', s)
    s = s.replace('\n', ' ')

    replacements = [
        (r'\\mathrm\{([^}]+)\}', r'\1'),
        (r'\\mathbf\{([^}]+)\}', r'\\bold(\1)'),
        (r'\\boldsymbol\{([^}]+)\}', r'\\bold(\1)'),
        (r'\\mathcal\{([^}]+)\}', r'\1'),
        (r'\\mathsf\{([^}]+)\}', r'\1'),
        (r'\\text\{([^}]+)\}', r'\1'),
        (r'\\dfrac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)'),
        (r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)'),
        (r'\\left\[', '['),
        (r'\\right\]', ']'),
        (r'\\left\(', '('),
        (r'\\right\)', ')'),
        (r'\\left\\\{', '{'),
        (r'\\right\\\}', '}'),
        (r'\\overline\{([^}]+)\}', r'\\overbar(\1)'),
        (r'\\underline\{([^}]+)\}', r'\\underbar(\1)'),
        (r'\\exp\\left', r'\\exp('),
        (r'\\min\\left', r'\\min('),
        (r'\\max\\left', r'\\max('),
        (r'\\sum_', r'\\sum_'),
        (r'\\prod_', r'\\prod_'),
        (r'\\quad', '  '),
        (r'\\cdot', '·'),
        (r'\\downarrow', '↓'),
        (r'\\uparrow', '↑'),
        (r'\\star', '★'),
        (r'\\alpha', 'α'),
        (r'\\beta', 'β'),
        (r'\\gamma', 'γ'),
        (r'\\rho', 'ρ'),
        (r'\\theta', 'θ'),
        (r'\\lambda', 'λ'),
        (r'\\Delta', 'Δ'),
        (r'\\bigl', ''),
        (r'\\bigr', ''),
        (r'\\ell', 'ℓ'),
        (r'\\tau', 'τ'),
        (r'\\in', '∈'),
        (r'\\forall', '∀'),
        (r'\\le', '≤'),
        (r'\\ge', '≥'),
        (r'\\sim', '~'),
        (r'\\exp', 'exp'),
        (r'\\min', 'min'),
        (r'\\max', 'max'),
    ]
    for old, new in replacements:
        s = re.sub(old, new, s)

    # cases environment
    cases = re.search(
        r'\\begin\{cases\}(.*?)\\end\{cases\}', s, flags=re.DOTALL
    )
    if cases:
        rows = [r.strip() for r in cases.group(1).split('\\\\') if r.strip()]
        parts = []
        for row in rows:
            left, right = [x.strip() for x in row.split('&', 1)]
            parts.append(f'{left},&{right}')
        case_body = '@'.join(parts)
        s = s.replace(cases.group(0), f'\\cases({case_body})')

    # subscripts / superscripts with braces
    for _ in range(6):
        s = re.sub(r'_\{([^}]+)\}', r'_(\1)', s)
        s = re.sub(r'\^\{([^}]+)\}', r'^(\1)', s)

    s = re.sub(r'\s+', ' ', s).strip()
    return s


def convert_inline(expr: str) -> str:
    return convert_latex_to_unicodemath(expr)


def convert_display(expr: str) -> str:
    body, tag = strip_tag(expr)
    um = convert_latex_to_unicodemath(body)
    if tag:
        return f'({tag})  {um}'
    return um


def transform_markdown(text: str) -> str:
    if not text.startswith('> 公式格式说明'):
        text = (
            '> 公式格式说明：本文公式采用 Microsoft Word 公式编辑器的 **UnicodeMath 线性格式**。\n'
            '> 在 Word 中按 `Alt+=` 打开公式框，粘贴 `word` 代码块中的内容后按空格即可生成专业格式公式。\n\n'
            + text
        )

    def repl_display(m: re.Match[str]) -> str:
        content = convert_display(m.group(1))
        return f'```word\n{content}\n```'

    text = re.sub(r'\$\$\s*\n(.*?)\n\$\$', repl_display, text, flags=re.DOTALL)

    def repl_inline(m: re.Match[str]) -> str:
        return f'【{convert_inline(m.group(1))}】'

    text = re.sub(r'\$([^$\n]+?)\$', repl_inline, text)
    return text


def main() -> None:
    text = SRC.read_text(encoding='utf-8')
    if '```word' not in text:
        LATEX_SRC.write_text(text, encoding='utf-8')
    else:
        text = LATEX_SRC.read_text(encoding='utf-8') if LATEX_SRC.exists() else text

    if '```word' in SRC.read_text(encoding='utf-8') and LATEX_SRC.exists():
        text = LATEX_SRC.read_text(encoding='utf-8')

    if not LATEX_SRC.exists():
        LATEX_SRC.write_text(text, encoding='utf-8')

    converted = transform_markdown(LATEX_SRC.read_text(encoding='utf-8'))
    SRC.write_text(converted, encoding='utf-8')
    print(f'written {SRC}')


if __name__ == '__main__':
    main()
