"""Math expression engineering tools.

V2 reworks the engine around a **canonical SymPy core**: every formula is parsed
into a SymPy expression, transpiled to the user-selected target language via
SymPy's code printers, and numerically self-validated with NumPy through
``lambdify``. Code -> formula reuses the same SymPy core (``sympy.latex``).

Target languages offered to the user: python, numpy, javascript, octave
(MATLAB/Octave), cpp17 (C++17). Fortran is reachable internally but not advertised.

SymPy/NumPy are imported lazily inside handlers so tool *registration* stays
cheap and a missing dependency degrades to a clear error instead of breaking
import-time discovery.
"""

from __future__ import annotations

import ast
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import registry, tool_error


# --- Language registry -----------------------------------------------------

# Languages exposed in the UI / capability writer_targets.
OFFERED_LANGUAGES: Tuple[str, ...] = ("python", "numpy", "javascript", "octave", "cpp17")

# Languages we can emit code→formula *from* (parsing other source languages into
# SymPy is a future follow-up).
CODE_TO_FORMULA_LANGUAGES: Tuple[str, ...] = ("python", "numpy")

_LANGUAGE_ALIASES: Dict[str, str] = {
    "py": "python",
    "python": "python",
    "python3": "python",
    "np": "numpy",
    "numpy": "numpy",
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
    "ecmascript": "javascript",
    "octave": "octave",
    "matlab": "octave",
    "m": "octave",
    "fortran": "fortran",
    "f90": "fortran",
    "f95": "fortran",
    "fortran90": "fortran",
    # internal-only, not advertised
    "cpp": "cpp17",
    "c++": "cpp17",
    "cpp17": "cpp17",
}

_LANGUAGE_LABELS: Dict[str, str] = {
    "python": "Python",
    "numpy": "NumPy",
    "javascript": "JavaScript",
    "octave": "MATLAB/Octave",
    "fortran": "Fortran",
    "cpp17": "C++17",
}


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_language(language: str, *, offered_only: bool = True) -> Optional[str]:
    key = _text(language).lower().replace(" ", "")
    canonical = _LANGUAGE_ALIASES.get(key)
    if canonical is None:
        return None
    if offered_only and canonical not in OFFERED_LANGUAGES:
        return None
    return canonical


# --- Parsing: messy formula / LaTeX -> sympify-able source -----------------


def _strip_math_wrappers(expression: str) -> str:
    text = _text(expression)
    text = text.replace("\r\n", "\n")
    text = re.sub(r"^\s*\$\$|\$\$\s*$", "", text)
    text = re.sub(r"^\s*\$|\$\s*$", "", text)
    text = text.strip("` \t\n")
    return text.strip()


def _split_assignment(expression: str) -> Tuple[str, str]:
    text = _strip_math_wrappers(expression)
    if "=" in text:
        lhs, rhs = text.split("=", 1)
        return lhs.strip() or "result", rhs.strip()
    return "result", text


def _latex_commands_to_python(text: str) -> str:
    """Best-effort LaTeX -> sympify-able source (no antlr/lark dependency).

    Handles the common student-formula subset: \\frac, \\sqrt, ^{...}, \\cdot,
    \\times, common function names, and brace groups. parse_expr then resolves
    implicit multiplication and ``^`` via transformations.
    """
    s = text
    # \left( \right) decorations
    s = re.sub(r"\\left|\\right", "", s)
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = s.replace("\\,", " ").replace("\\;", " ").replace("\\!", "").replace("\\ ", " ")
    # exponent groups: ^{...} -> **(...)
    s = re.sub(r"\^\s*\{([^{}]*)\}", r"**(\1)", s)
    # \frac{A}{B} -> ((A)/(B)); loop to flatten one level of nesting
    frac = re.compile(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
    for _ in range(6):
        new = frac.sub(r"((\1)/(\2))", s)
        if new == s:
            break
        s = new
    # \sqrt{A} -> sqrt(A)
    s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", s)
    # known function commands: drop the backslash
    s = re.sub(
        r"\\(sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|arcsin|arccos|arctan|log|ln|exp|min|max|abs)\b",
        r"\1",
        s,
    )
    # natural log: ln(...) -> log(...)  (sympy log is natural log)
    s = re.sub(r"\bln\s*\(", "log(", s)
    s = s.replace("\\pi", "pi")
    # residual braces become parentheses (covers x^{2} already handled, sub_{i}, etc.)
    s = s.replace("{", "(").replace("}", ")")
    # leftover stray backslashes
    s = s.replace("\\", " ")
    return re.sub(r"\s+", " ", s).strip()


def _transformations():
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        standard_transformations,
    )

    return standard_transformations + (implicit_multiplication_application, convert_xor)


def _function_name_for(lhs: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_]+", "", lhs).lower()
    if key in {"e", "ke", "energy"}:
        return "compute_energy"
    return f"compute_{key or 'result'}"


def _parse_formula(formula: str):
    """Return (lhs_name, sympy_expr, is_assignment). Raises on parse failure."""
    from sympy.parsing.sympy_parser import parse_expr

    raw = _strip_math_wrappers(formula)
    is_assignment = "=" in raw
    lhs, rhs = _split_assignment(formula)
    rhs_src = _latex_commands_to_python(rhs)
    if not rhs_src:
        raise ValueError("expression is empty after normalization")
    expr = parse_expr(rhs_src, transformations=_transformations(), evaluate=True)
    return lhs, expr, is_assignment


def _ordered_inputs(expr) -> List[str]:
    return sorted(symbol.name for symbol in expr.free_symbols)


def _variable_table(expr, lhs: str, is_assignment: bool) -> List[Dict[str, str]]:
    table: List[Dict[str, str]] = []
    if is_assignment:
        table.append({"name": lhs, "role": "output", "description": ""})
    for name in _ordered_inputs(expr):
        table.append({"name": name, "role": "input", "description": ""})
    return table


# --- Code emission ---------------------------------------------------------


def _emit_code(expr, fn_name: str, inputs: List[str], language: str) -> str:
    import sympy

    args = ", ".join(inputs)
    if language == "python":
        body = sympy.pycode(expr)
        header = "import math\n\n\n" if "math." in body else ""
        return f"{header}def {fn_name}({args}):\n    return {body}\n"

    if language == "numpy":
        from sympy.printing.numpy import NumPyPrinter

        body = NumPyPrinter().doprint(expr).replace("numpy.", "np.")
        return f"import numpy as np\n\n\ndef {fn_name}({args}):\n    return {body}\n"

    if language == "javascript":
        body = sympy.jscode(expr)
        return f"function {fn_name}({args}) {{\n  return {body};\n}}\n"

    if language == "octave":
        body = sympy.octave_code(expr)
        return f"function y = {fn_name}({args})\n  y = {body};\nend\n"

    if language == "fortran":
        assign = sympy.fcode(expr, assign_to="y", source_format="free", standard=2003).strip()
        assign_block = "\n".join(("  " + ln if ln.strip() else ln) for ln in assign.splitlines())
        decl = f"  real(8), intent(in) :: {args}\n" if inputs else ""
        return (
            f"function {fn_name}({args}) result(y)\n"
            f"  implicit none\n"
            f"{decl}"
            f"  real(8) :: y\n"
            f"{assign_block}\n"
            f"end function {fn_name}\n"
        )

    if language == "cpp17":
        body = sympy.cxxcode(expr, standard="c++17")
        cargs = ", ".join(f"double {name}" for name in inputs)
        return f"#include <cmath>\n\ndouble {fn_name}({cargs}) {{\n    return {body};\n}}\n"

    raise ValueError(f"unsupported target language: {language}")


# --- Numeric self-validation ----------------------------------------------


def _numeric_validation(expr, inputs: List[str]) -> Dict[str, Any]:
    """Evaluate the canonical expression on a few deterministic samples via
    lambdify(numpy) and compare against SymPy's own ``evalf`` reference."""
    import sympy

    symbols = [sympy.Symbol(name) for name in inputs]
    try:
        fn = sympy.lambdify(symbols, expr, modules="numpy")
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "skipped", "reason": f"lambdify failed: {exc}", "samples": []}

    samples: List[Dict[str, float]] = [
        {name: 1.0 for name in inputs},
        {name: float(idx + 2) for idx, name in enumerate(inputs)},
    ]
    if not inputs:
        samples = [{}]

    records: List[Dict[str, Any]] = []
    max_abs_error = 0.0
    status = "checked"
    for sample in samples:
        try:
            numeric = float(fn(*[sample[name] for name in inputs]))
            reference = float(expr.evalf(subs={sympy.Symbol(k): v for k, v in sample.items()}))
        except Exception as exc:
            records.append({"inputs": sample, "error": str(exc)})
            status = "partial"
            continue
        abs_error = abs(numeric - reference)
        max_abs_error = max(max_abs_error, abs_error)
        records.append(
            {
                "inputs": sample,
                "lambdify_numpy": numeric,
                "sympy_reference": reference,
                "abs_error": abs_error,
            }
        )

    return {
        "status": status,
        "modules": "numpy",
        "samples": records,
        "max_abs_error": max_abs_error,
        "note": (
            "Numeric agreement between the NumPy lambdify of the canonical SymPy "
            "expression and SymPy's own evalf. This checks transpilation fidelity, "
            "not the semantic correctness of the formula."
        ),
    }


_SEMANTIC_VALIDATION = {
    "status": "required_by_agent",
    "contract_required": True,
    "must_check": [
        "variable meanings and units/dimensions",
        "domain and boundary or open/closed interval constraints",
        "numeric agreement within tolerance",
        "invariants or known analytic properties",
        "negative or edge cases where applicable",
    ],
    "note": (
        "The numeric validation block only proves the emitted code matches the SymPy "
        "core. The agent must still test domains, boundaries, units, and invariants "
        "before reporting formula-to-code conversion as semantically correct."
    ),
}


# --- Public tools ----------------------------------------------------------


def math_expression_cleanup(expression: str, source_kind: str = "auto") -> str:
    if not _text(expression):
        return tool_error("expression is required")

    warnings: List[str] = []
    try:
        import sympy

        lhs, expr, is_assignment = _parse_formula(expression)
        rhs_latex = sympy.latex(expr)
        clean_latex = f"{lhs} = {rhs_latex}" if is_assignment else rhs_latex
        variable_table = _variable_table(expr, lhs, is_assignment)
        engine = "sympy"
    except Exception as exc:
        # Fall back to a light regex normalization so cleanup still returns something.
        warnings.append(f"SymPy could not parse this expression ({exc}); used regex normalization.")
        text = _strip_math_wrappers(expression)
        clean_latex = re.sub(r"\*\*", "^", text)
        variable_table = []
        engine = "regex_fallback"

    return _json(
        {
            "ok": True,
            "source_kind": source_kind or "auto",
            "engine": engine,
            "clean_latex": clean_latex,
            "markdown": f"$$\n{clean_latex}\n$$",
            "variable_table": variable_table,
            "warnings": warnings,
        }
    )


def math_formula_to_code(formula: str, language: str = "python") -> str:
    if not _text(formula):
        return tool_error("formula is required")

    norm = _normalize_language(language)
    if norm is None:
        return tool_error(
            f"unsupported target language: {language}",
            supported=list(OFFERED_LANGUAGES),
        )

    try:
        import sympy  # noqa: F401

        lhs, expr, is_assignment = _parse_formula(formula)
    except Exception as exc:
        return tool_error(
            f"could not parse formula into a SymPy expression: {exc}",
            hint="V2 supports the common student-formula subset; try plain LaTeX or a Python-style expression.",
        )

    inputs = _ordered_inputs(expr)
    fn_name = _function_name_for(lhs)
    try:
        code = _emit_code(expr, fn_name, inputs, norm)
    except Exception as exc:
        return tool_error(f"code emission failed for {norm}: {exc}")

    validation = _numeric_validation(expr, inputs)
    rhs_latex = sympy.latex(expr)
    canonical_latex = f"{lhs} = {rhs_latex}" if is_assignment else rhs_latex

    return _json(
        {
            "ok": True,
            "code": code,
            "language": norm,
            "language_label": _LANGUAGE_LABELS.get(norm, norm),
            "function_name": fn_name,
            "canonical": {
                "engine": "sympy",
                "latex": canonical_latex,
                "srepr": sympy.srepr(expr),
            },
            "variable_table": _variable_table(expr, lhs, is_assignment),
            "validation": validation,
            "example_inputs": [{name: 1 for name in inputs}],
            "assumptions": [
                "Parsed through the SymPy canonical core, then transpiled with SymPy's code printer.",
                "Variables are treated as real scalars; the NumPy target vectorizes element-wise.",
            ],
            "semantic_validation": _SEMANTIC_VALIDATION,
            "latex": canonical_latex,
        }
    )


# Math functions the code→formula guard accepts as calls (bare or math./np./numpy.
# prefixed). Anything outside this set — string ops, I/O, attribute chains — marks
# the expression as "not math" so we don't emit nonsense LaTeX from business logic.
_MATH_CALL_NAMES: frozenset = frozenset(
    {
        "sin", "cos", "tan", "cot", "sec", "csc",
        "asin", "acos", "atan", "atan2", "arcsin", "arccos", "arctan",
        "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
        "exp", "expm1", "log", "log2", "log10", "log1p", "ln",
        "sqrt", "cbrt", "pow", "hypot", "copysign",
        "abs", "fabs", "floor", "ceil", "trunc", "sign",
        "factorial", "gamma", "lgamma", "erf", "erfc",
        "degrees", "radians",
    }
)

# Module prefixes whose attribute access we treat as a math-namespace lookup.
_MATH_NAMESPACES: frozenset = frozenset({"math", "np", "numpy", "cmath", "sympy"})

# Constants allowed to appear bare (e.g. ``pi``, ``math.pi``).
_MATH_CONSTANTS: frozenset = frozenset({"pi", "e", "tau", "inf"})


class _NotMathExpression(ValueError):
    """Raised when extracted code is not a closed-form mathematical expression."""


def _math_call_name(func: ast.AST) -> Optional[str]:
    """Return the math-function name for a call target, or None if not math.

    Accepts a bare ``Name`` (``sqrt``) or a ``math.``/``np.``/``numpy.`` style
    ``Attribute`` whose root is a recognized math namespace.
    """
    if isinstance(func, ast.Name):
        return func.id if func.id in _MATH_CALL_NAMES else None
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id in _MATH_NAMESPACES and func.attr in _MATH_CALL_NAMES:
            return func.attr
    return None


def _assert_math_expression(node: ast.AST) -> bool:
    """Walk an expression subtree, allowing only closed-form math constructs.

    Returns True if the subtree contains at least one "math signal" (an operator
    or a math-function call); raises ``_NotMathExpression`` on any disallowed
    construct (attribute access, subscripts, comprehensions, string literals,
    comparisons, calls to non-math functions, etc.).
    """
    has_signal = False

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
            raise _NotMathExpression("unsupported operator for a mathematical formula")
        _assert_math_expression(node.left)
        _assert_math_expression(node.right)
        return True

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise _NotMathExpression("unsupported unary operator for a mathematical formula")
        _assert_math_expression(node.operand)
        return True

    if isinstance(node, ast.Call):
        name = _math_call_name(node.func)
        if name is None:
            raise _NotMathExpression(
                "found a call to a non-mathematical function; code→formula only handles closed-form math"
            )
        if node.keywords:
            raise _NotMathExpression("mathematical function calls must use positional arguments only")
        for arg in node.args:
            _assert_math_expression(arg)
        return True

    if isinstance(node, ast.Name):
        return False

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float, complex)):
            raise _NotMathExpression("only numeric constants are allowed in a mathematical formula")
        return False

    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        # Bare math constant such as ``math.pi`` / ``np.e``.
        if node.value.id in _MATH_NAMESPACES and node.attr in _MATH_CONSTANTS:
            return False

    raise _NotMathExpression(
        f"the selected code is not a closed-form mathematical expression "
        f"(unsupported construct: {type(node).__name__})"
    )


class _FlattenMathNamespaces(ast.NodeTransformer):
    """Rewrite ``math.sqrt`` / ``np.sin`` / ``math.pi`` to bare ``sqrt`` / ``sin``
    / ``pi`` so the unparsed source is sympify-able (SymPy doesn't read the
    ``math.``/``np.`` prefixes)."""

    def visit_Attribute(self, node: ast.Attribute):  # noqa: N802
        if (
            isinstance(node.value, ast.Name)
            and node.value.id in _MATH_NAMESPACES
            and (node.attr in _MATH_CALL_NAMES or node.attr in _MATH_CONSTANTS)
        ):
            return ast.copy_location(ast.Name(id=node.attr, ctx=ast.Load()), node)
        return self.generic_visit(node)


def _extract_python_expr(code: str) -> Tuple[str, str]:
    """Return (lhs_name, expression_source) from a simple Python/NumPy snippet.

    Validates that the extracted expression is closed-form math before returning,
    so non-mathematical code (I/O, string processing, data-structure logic) is
    rejected with a clear error instead of being transpiled into nonsense LaTeX.
    """
    tree = ast.parse(code)
    lhs = "result"
    expr_node: Optional[ast.AST] = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            lhs = "E" if node.name in {"energy", "compute_energy"} else "result"
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and stmt.value is not None:
                    expr_node = stmt.value
                    break
        if expr_node is None and isinstance(node, ast.Assign) and node.targets:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                lhs = target.id
                expr_node = node.value
                break
    if expr_node is None:
        raise ValueError("could not find a simple return or assignment expression")
    has_signal = _assert_math_expression(expr_node)
    if not has_signal:
        raise _NotMathExpression(
            "the selected code has no mathematical operation (just a variable or constant); "
            "code→formula expects a closed-form formula"
        )
    flattened = _FlattenMathNamespaces().visit(expr_node)
    return lhs, ast.unparse(flattened)


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
    if lang != "auto":
        norm = _normalize_language(lang, offered_only=False)
        if norm not in CODE_TO_FORMULA_LANGUAGES:
            return tool_error(
                f"code-to-formula currently supports {', '.join(CODE_TO_FORMULA_LANGUAGES)} source code",
                supported=list(CODE_TO_FORMULA_LANGUAGES),
                hint="Other source languages are a future follow-up; paste the equivalent Python/NumPy expression.",
            )

    try:
        import sympy
        from sympy.parsing.sympy_parser import parse_expr

        lhs, expr_src = _extract_python_expr(code)
        expr = parse_expr(expr_src, transformations=_transformations(), evaluate=True)
    except _NotMathExpression as exc:
        return tool_error(
            str(exc),
            hint=(
                "code→formula only converts closed-form numeric/mathematical expressions "
                "(scientific formulas, analytic algorithm bodies). It does not handle business "
                "logic, I/O, string processing, or data-structure manipulation."
            ),
        )
    except Exception as exc:
        return tool_error(str(exc))

    rhs_latex = sympy.latex(expr)
    latex = f"{lhs} = {rhs_latex}"
    variable_table = _variable_table(expr, lhs, True)
    markdown = f"### Formula\n\n$$\n{latex}\n$$\n\nGenerated from source code via the SymPy core."
    html_path = _write_html_report(latex, markdown, variable_table, output_dir)
    warnings = [
        "PDF export is not available without an HTML-to-PDF backend; pdf_path is empty and html_path is the canonical report."
    ]
    return _json(
        {
            "ok": True,
            "formulas": [{"latex": latex, "source": "code"}],
            "latex": latex,
            "markdown": markdown,
            "html_path": html_path,
            "pdf_path": "",
            "variable_table": variable_table,
            "warnings": warnings,
        }
    )


MATH_EXPRESSION_CLEANUP_SCHEMA = {
    "name": "math_expression_cleanup",
    "description": (
        "Normalize messy OCR, LaTeX, document math, or code-like math expressions into clean LaTeX "
        "and Markdown using the SymPy canonical core (regex fallback when SymPy cannot parse)."
    ),
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
    "description": (
        "Convert a formula or LaTeX expression into code for a user-selected target language. "
        "The formula is parsed into a canonical SymPy expression, transpiled with SymPy's code "
        "printers, and numerically self-checked against SymPy's evalf via a NumPy lambdify. "
        "Output includes a semantic_validation reminder; callers must still test domains, "
        "boundaries, invariants, and numeric agreement before claiming correctness."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "formula": {"type": "string"},
            "language": {
                "type": "string",
                "description": "python, numpy, javascript, octave (MATLAB/Octave), or cpp17 (C++17)",
            },
        },
        "required": ["formula"],
    },
}

CODE_TO_MATH_FORMULA_SCHEMA = {
    "name": "code_to_math_formula",
    "description": (
        "Convert a simple Python or NumPy code expression into LaTeX, Markdown, and an HTML report "
        "using the SymPy core (sympy.latex). The selected code must be a closed-form mathematical "
        "expression (arithmetic and whitelisted math functions); non-mathematical code — I/O, string "
        "processing, attribute/data-structure access — is rejected with a clear error. Other source "
        "languages are a future follow-up."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "language": {"type": "string", "description": "auto, python, or numpy"},
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
