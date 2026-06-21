# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""LaTeX -> HTML formula rendering for the document writers (split from document_tools.py)."""

import html

from tools.document.common import _text


_LATEX_SYMBOLS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ϵ",
    "varepsilon": "ε",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "omega": "ω",
    "times": "×",
    "cdot": "·",
    "cap": "∩",
    "cup": "∪",
    "in": "∈",
    "notin": "∉",
    "leq": "≤",
    "geq": "≥",
    "neq": "≠",
    "approx": "≈",
    "emptyset": "∅",
    "angle": "∠",
    "ldots": "…",
    "cdots": "…",
    "langle": "⟨",
    "rangle": "⟩",
    "to": "→",
    "leftarrow": "←",
    "rightarrow": "→",
    "infty": "∞",
    "arg": "arg",
    "min": "min",
    "max": "max",
}


def _latex_group(text: str, start: int) -> Tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        return "", start
    depth = 1
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return text[start + 1:], len(text)


def _latex_atom(text: str, start: int) -> Tuple[str, int]:
    if start >= len(text):
        return "", start
    if text[start] == "{":
        group, end = _latex_group(text, start)
        return _render_latex_html(group), end
    if text[start] == "\\":
        raw, end = _latex_command_html(text, start)
        return raw, end
    return html.escape(text[start]), start + 1


def _latex_command_html(text: str, start: int) -> Tuple[str, int]:
    i = start + 1
    if i < len(text) and text[i].isalpha():
        while i < len(text) and text[i].isalpha():
            i += 1
        command = text[start + 1:i]
    elif i < len(text):
        command = text[i]
        i += 1
    else:
        return "", i

    if command in {"left", "right"}:
        return "", i
    if command in {",", ";", ":", "quad", "qquad"}:
        return " ", i
    if command == "|":
        return "‖", i
    if command == "frac":
        numerator, i = _latex_group(text, i)
        denominator, i = _latex_group(text, i)
        return (
            '<span class="frac"><span class="num">'
            f"{_render_latex_html(numerator)}</span><span class=\"den\">"
            f"{_render_latex_html(denominator)}</span></span>"
        ), i
    if command == "sqrt":
        radicand, i = _latex_group(text, i)
        return (
            '<span class="sqrt"><span class="radicand">'
            f"{_render_latex_html(radicand)}</span></span>"
        ), i
    if command == "overline":
        group, i = _latex_group(text, i)
        return f'<span class="overline">{_render_latex_html(group)}</span>', i
    if command == "vec":
        atom, i = _latex_atom(text, i)
        return f'{atom}<span class="vec-mark">⃗</span>', i
    symbol = _LATEX_SYMBOLS.get(command)
    if symbol is not None:
        return html.escape(symbol), i
    return html.escape(command), i


def _render_latex_html(text: str) -> str:
    source = _text(text)
    out: List[str] = []
    i = 0
    while i < len(source):
        c = source[i]
        if c == "\\":
            rendered, i = _latex_command_html(source, i)
            out.append(rendered)
            continue
        if c in {"_", "^"}:
            atom, i = _latex_atom(source, i + 1)
            tag = "sub" if c == "_" else "sup"
            out.append(f"<{tag}>{atom}</{tag}>")
            continue
        if c in "{}":
            i += 1
            continue
        out.append(html.escape(c))
        i += 1
    return "".join(out)


def _formula_to_html(text: str) -> str:
    return f'<span class="formula-math">{_render_latex_html(text)}</span>'
