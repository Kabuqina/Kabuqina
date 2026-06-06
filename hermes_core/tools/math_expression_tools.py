"""V1 deterministic math expression engineering tools."""

from __future__ import annotations

import ast
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tools.registry import registry, tool_error


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strip_math_wrappers(expression: str) -> str:
    text = _text(expression)
    text = text.replace("\r\n", "\n")
    text = re.sub(r"^\s*\$\$|\$\$\s*$", "", text)
    text = re.sub(r"^\s*\$|\$\s*$", "", text)
    text = text.strip("` \t\n")
    replacements = {
        "×": "*",
        "·": " ",
        "\\cdot": " ",
        "\\times": " ",
        "\\left": "",
        "\\right": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def _split_assignment(expression: str) -> Tuple[str, str]:
    text = _strip_math_wrappers(expression)
    if "=" not in text:
        return "result", text
    lhs, rhs = text.split("=", 1)
    return lhs.strip() or "result", rhs.strip()


def _compact_implicit_products(text: str) -> str:
    value = re.sub(r"\s+", "", text)
    value = re.sub(r"([A-Za-z])([A-Za-z])", r"\1 \2", value)
    value = re.sub(r"([A-Za-z0-9)])\*([A-Za-z0-9(])", r"\1 \2", value)
    return value


def _cleanup_rhs_to_latex(rhs: str) -> str:
    value = _strip_math_wrappers(rhs)
    value = value.replace("**", "^")
    value = _compact_implicit_products(value)
    value = re.sub(r"\^(-?\d+)", r"^{\1}", value)
    value = re.sub(r"\^\{([^{}]+)\}", r"^{\1}", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _cleanup_to_latex(expression: str) -> str:
    lhs, rhs = _split_assignment(expression)
    lhs = _strip_math_wrappers(lhs)
    return f"{lhs} = {_cleanup_rhs_to_latex(rhs)}"


def _variables_from_latex(latex: str) -> List[Dict[str, str]]:
    names: List[str] = []
    for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9_]*\b", latex):
        name = match.group(0)
        if name in {"sin", "cos", "tan", "log", "ln", "exp", "sqrt"}:
            continue
        if name not in names:
            names.append(name)
    return [
        {
            "name": name,
            "role": "output" if idx == 0 and "=" in latex else "input",
            "description": "",
        }
        for idx, name in enumerate(names)
    ]


def _latex_rhs_to_python_expr(rhs_latex: str) -> str:
    expr = rhs_latex
    expr = re.sub(r"\^\{(-?\d+)\}", r" ** \1", expr)
    expr = re.sub(r"\^(-?\d+)", r" ** \1", expr)
    expr = re.sub(r"\s+", " ", expr).strip()
    tokens = expr.split(" ")
    if len(tokens) > 1:
        out: List[str] = []
        previous_was_value = False
        for token in tokens:
            is_value = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?", token))
            is_operator = token in {"+", "-", "*", "/", "**"}
            if previous_was_value and is_value:
                out.append("*")
            out.append(token)
            previous_was_value = is_value and not is_operator
        expr = " ".join(out)
    expr = re.sub(r"\s+", " ", expr).strip()
    return expr


def _cpp_expr_from_python(python_expr: str) -> str:
    def repl(match: re.Match[str]) -> str:
        base = match.group(1).strip()
        power = match.group(2).strip()
        return f"std::pow({base}, {power})"

    return re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\*\*\s*(-?\d+)\b", repl, python_expr)


def _function_name_for(lhs: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_]+", "", lhs).lower()
    if key == "e":
        return "compute_energy"
    return f"compute_{key or 'result'}"


def _input_variables(variable_table: List[Dict[str, str]]) -> List[str]:
    return [row["name"] for row in variable_table if row.get("role") != "output"]


def math_expression_cleanup(expression: str, source_kind: str = "auto") -> str:
    if not _text(expression):
        return tool_error("expression is required")
    clean_latex = _cleanup_to_latex(expression)
    warnings: List[str] = []
    if clean_latex.count("=") > 1:
        warnings.append("Multiple equality signs detected; V1 cleanup preserves only a simple expression shape.")
    return _json({
        "ok": True,
        "source_kind": source_kind or "auto",
        "clean_latex": clean_latex,
        "markdown": f"$$\n{clean_latex}\n$$",
        "variable_table": _variables_from_latex(clean_latex),
        "warnings": warnings,
    })


def math_formula_to_code(formula: str, language: str = "python") -> str:
    if not _text(formula):
        return tool_error("formula is required")
    target = _text(language).lower() or "python"
    if target == "cpp":
        target = "cpp17"
    if target not in {"python", "numpy", "cpp17"}:
        return tool_error(f"unsupported target language: {language}", supported=["python", "numpy", "cpp17"])

    clean_latex = _cleanup_to_latex(formula)
    lhs, rhs_latex = _split_assignment(clean_latex)
    variable_table = _variables_from_latex(clean_latex)
    inputs = _input_variables(variable_table)
    python_expr = _latex_rhs_to_python_expr(rhs_latex)
    fn = _function_name_for(lhs)

    if target == "python":
        args = ", ".join(inputs)
        code = f"def {fn}({args}):\n    return {python_expr}\n"
    elif target == "numpy":
        args = ", ".join(inputs)
        setup = "\n".join(f"    {name}_arr = np.asarray({name})" for name in inputs)
        expr = python_expr
        for name in inputs:
            expr = re.sub(rf"\b{re.escape(name)}\b", f"{name}_arr", expr)
        code = f"import numpy as np\n\n\ndef {fn}({args}):\n{setup}\n    return {expr}\n"
    else:
        args = ", ".join(f"double {name}" for name in inputs)
        code = (
            "#include <cmath>\n\n"
            f"double {fn}({args}) {{\n"
            f"    return {_cpp_expr_from_python(python_expr)};\n"
            "}\n"
        )

    return _json({
        "ok": True,
        "code": code,
        "language": target,
        "variable_table": variable_table,
        "assumptions": [
            "V1 performs deterministic expression conversion and does not prove algebraic equivalence.",
            "Variables are treated as numeric scalars unless the NumPy target is selected.",
        ],
        "example_inputs": [{name: 1 for name in inputs}],
        "latex": clean_latex,
    })


def _python_expr_to_latex(node: ast.AST) -> str:
    if isinstance(node, ast.BinOp):
        left = _python_expr_to_latex(node.left)
        right = _python_expr_to_latex(node.right)
        if isinstance(node.op, ast.Pow):
            return f"{left}^{{{right}}}"
        if isinstance(node.op, ast.Mult):
            return f"{left} {right}"
        if isinstance(node.op, ast.Add):
            return f"{left} + {right}"
        if isinstance(node.op, ast.Sub):
            return f"{left} - {right}"
        if isinstance(node.op, ast.Div):
            return f"\\frac{{{left}}}{{{right}}}"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Call):
        func = _python_expr_to_latex(node.func)
        args = ", ".join(_python_expr_to_latex(arg) for arg in node.args)
        if func.endswith(".sqrt") or func == "sqrt":
            return f"\\sqrt{{{_python_expr_to_latex(node.args[0])}}}" if node.args else "\\sqrt{}"
        return f"{func}({args})"
    if isinstance(node, ast.Attribute):
        return f"{_python_expr_to_latex(node.value)}.{node.attr}"
    return ast.unparse(node)


def _extract_python_formula(code: str) -> Tuple[str, str]:
    tree = ast.parse(code)
    lhs = "result"
    expr_node: ast.AST | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in {"energy", "compute_energy"}:
                lhs = "E"
            else:
                lhs = "result"
            for stmt in node.body:
                if isinstance(stmt, ast.Return):
                    expr_node = stmt.value
                    break
        if expr_node is None and isinstance(node, ast.Assign) and node.targets:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                lhs = target.id
                expr_node = node.value
                break
    if expr_node is None:
        raise ValueError("V1 could not find a simple return or assignment expression")
    return lhs, _python_expr_to_latex(expr_node)


def _extract_cpp_formula(code: str) -> Tuple[str, str]:
    match = re.search(r"return\s+(.+?);", code, re.DOTALL)
    if not match:
        raise ValueError("V1 could not find a simple C++ return expression")
    expr = match.group(1)
    expr = re.sub(r"std::pow\(([^,]+),\s*([^)]+)\)", r"\1^{\2}", expr)
    expr = expr.replace("*", " ")
    return "result", re.sub(r"\s+", " ", expr).strip()


def _write_html_report(latex: str, markdown: str, variable_table: List[Dict[str, str]], output_dir: str) -> str:
    root = Path(output_dir).expanduser() if _text(output_dir) else Path(tempfile.gettempdir()) / "kabuqina-math-reports"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "math-expression-report.html"
    rows = "\n".join(
        f"<tr><td>{html.escape(row['name'])}</td><td>{html.escape(row['role'])}</td><td>{html.escape(row.get('description', ''))}</td></tr>"
        for row in variable_table
    )
    path.write_text(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Math Expression Report</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;line-height:1.55}"
        "code,pre{background:#f5f5f5;padding:2px 4px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px 10px}</style>"
        "</head><body>"
        "<h1>Math Expression Report</h1>"
        f"<h2>Formula</h2><pre>{html.escape(latex)}</pre>"
        f"<h2>Markdown</h2><pre>{html.escape(markdown)}</pre>"
        "<h2>Variables</h2><table><thead><tr><th>Name</th><th>Role</th><th>Description</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "</body></html>",
        encoding="utf-8",
    )
    return str(path)


def code_to_math_formula(code: str, language: str = "auto", output_dir: str = "") -> str:
    if not _text(code):
        return tool_error("code is required")
    lang = _text(language).lower() or "auto"
    try:
        if lang in {"auto", "python", "numpy"}:
            lhs, rhs = _extract_python_formula(code)
        elif lang in {"cpp", "cpp17", "c++"}:
            lhs, rhs = _extract_cpp_formula(code)
        else:
            return tool_error(f"unsupported source language: {language}", supported=["python", "numpy", "cpp17"])
    except Exception as exc:
        return tool_error(str(exc))

    latex = f"{lhs} = {_cleanup_rhs_to_latex(rhs)}"
    variable_table = _variables_from_latex(latex)
    markdown = f"### Formula\n\n$$\n{latex}\n$$\n\nV1 report generated from a simple code expression."
    html_path = _write_html_report(latex, markdown, variable_table, output_dir)
    warnings = [
        "PDF export is not available in V1 without an HTML-to-PDF backend; pdf_path is empty and html_path is the canonical report."
    ]
    return _json({
        "ok": True,
        "formulas": [{"latex": latex, "source": "code"}],
        "latex": latex,
        "markdown": markdown,
        "html_path": html_path,
        "pdf_path": "",
        "variable_table": variable_table,
        "warnings": warnings,
    })


MATH_EXPRESSION_CLEANUP_SCHEMA = {
    "name": "math_expression_cleanup",
    "description": "Normalize messy OCR, LaTeX, document math, or code-like math expressions into clean LaTeX and Markdown.",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string"},
            "source_kind": {"type": "string", "description": "auto, ocr, latex, document_math, or code_expression"},
        },
        "required": ["expression"],
    },
}

MATH_FORMULA_TO_CODE_SCHEMA = {
    "name": "math_formula_to_code",
    "description": "Convert a simple formula or LaTeX expression into Python, NumPy, or C++17 code.",
    "parameters": {
        "type": "object",
        "properties": {
            "formula": {"type": "string"},
            "language": {"type": "string", "description": "python, numpy, or cpp17"},
        },
        "required": ["formula"],
    },
}

CODE_TO_MATH_FORMULA_SCHEMA = {
    "name": "code_to_math_formula",
    "description": "Convert a simple Python, NumPy, or C++17 code expression into LaTeX, Markdown, and an HTML report.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "language": {"type": "string", "description": "auto, python, numpy, or cpp17"},
            "output_dir": {"type": "string", "description": "Directory for the generated HTML report."},
        },
        "required": ["code"],
    },
}


registry.register(
    name="math_expression_cleanup",
    toolset="math",
    schema=MATH_EXPRESSION_CLEANUP_SCHEMA,
    handler=lambda args, **kw: math_expression_cleanup(
        expression=args.get("expression", ""),
        source_kind=args.get("source_kind", "auto"),
    ),
    check_fn=lambda: True,
    emoji="M",
)

registry.register(
    name="math_formula_to_code",
    toolset="math",
    schema=MATH_FORMULA_TO_CODE_SCHEMA,
    handler=lambda args, **kw: math_formula_to_code(
        formula=args.get("formula", ""),
        language=args.get("language", "python"),
    ),
    check_fn=lambda: True,
    emoji="C",
)

registry.register(
    name="code_to_math_formula",
    toolset="math",
    schema=CODE_TO_MATH_FORMULA_SCHEMA,
    handler=lambda args, **kw: code_to_math_formula(
        code=args.get("code", ""),
        language=args.get("language", "auto"),
        output_dir=args.get("output_dir", ""),
    ),
    check_fn=lambda: True,
    emoji="R",
)
