from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_cleanup_normalizes_via_sympy_core():
    from tools.math_expression_tools import math_expression_cleanup

    result = json.loads(math_expression_cleanup("E = m c ^ 2"))

    assert result["ok"] is True
    assert result["engine"] == "sympy"
    # SymPy canonicalizes (alphabetical ordering); E stays the output name.
    assert result["clean_latex"].startswith("E =")
    assert "c^{2}" in result["clean_latex"]
    assert "c^{2}" in result["markdown"]
    assert any(row["name"] == "E" and row["role"] == "output" for row in result["variable_table"])
    assert result["warnings"] == []


def test_formula_to_code_python_with_validation():
    from tools.math_expression_tools import math_formula_to_code

    py = json.loads(math_formula_to_code("E = mc^2", "python"))

    assert py["ok"] is True
    assert py["language"] == "python"
    assert "def compute_energy" in py["code"]
    assert "c**2*m" in py["code"]
    assert py["canonical"]["engine"] == "sympy"
    # Numeric self-check: NumPy lambdify must agree with SymPy evalf.
    assert py["validation"]["status"] in {"checked", "partial"}
    assert py["validation"]["max_abs_error"] == 0.0
    assert py["semantic_validation"]["contract_required"] is True
    assert any("open/closed interval" in item for item in py["semantic_validation"]["must_check"])


def test_formula_to_code_rejects_numpy_target():
    """NumPy is a Python library, not an advertised target language."""
    from tools.math_expression_tools import math_formula_to_code

    result = json.loads(math_formula_to_code("E = mc^2", "numpy"))
    assert "error" in result
    assert "numpy" not in result["supported"]


def test_formula_to_code_emits_each_offered_language():
    from tools.math_expression_tools import OFFERED_LANGUAGES, math_formula_to_code

    expected_signature = {
        "python": "def compute_energy",
        "javascript": "function compute_energy",
        "octave": "function y = compute_energy",
        "cpp17": "double compute_energy",
    }
    assert set(OFFERED_LANGUAGES) == set(expected_signature)
    for language, signature in expected_signature.items():
        result = json.loads(math_formula_to_code("E = mc^2", language))
        assert result["ok"] is True, (language, result)
        assert result["language"] == language
        assert signature in result["code"], (language, result["code"])


def test_formula_to_code_rejects_unsupported_language():
    from tools.math_expression_tools import math_formula_to_code

    result = json.loads(math_formula_to_code("a + b", "rust"))
    assert "error" in result
    assert "rust" in result["error"]
    assert "python" in result["supported"]


def test_code_to_math_formula_writes_html_via_sympy(tmp_path):
    from tools.math_expression_tools import code_to_math_formula

    result = json.loads(
        code_to_math_formula(
            "def energy(m, c):\n    return m * c ** 2",
            "python",
            str(tmp_path),
        )
    )

    assert result["ok"] is True
    assert result["latex"].startswith("E =")
    assert "c^{2}" in result["latex"]
    assert "c^{2}" in result["markdown"]
    assert Path(result["html_path"]).exists()
    assert result["pdf_path"] == ""
    assert any("PDF" in warning for warning in result["warnings"])
    assert any(row["name"] == "m" for row in result["variable_table"])


def test_code_to_math_formula_rejects_non_mathematical_code():
    from tools.math_expression_tools import code_to_math_formula

    # Attribute call (I/O-ish) -> not a closed-form formula.
    io_like = json.loads(code_to_math_formula("def f(url):\n    return requests.get(url).json()", "python"))
    assert "error" in io_like
    assert "closed-form" in io_like["error"] or "non-mathematical" in io_like["error"]

    # String processing -> rejected.
    string_like = json.loads(code_to_math_formula("def f(s):\n    return s.strip()", "python"))
    assert "error" in string_like

    # Subscript / data-structure access -> rejected.
    subscript = json.loads(code_to_math_formula("def f(data, rate):\n    return data[0] * rate", "python"))
    assert "error" in subscript

    # Bare variable with no math operation -> rejected.
    bare = json.loads(code_to_math_formula("def f(x):\n    return x", "python"))
    assert "error" in bare


def test_code_to_math_formula_allows_whitelisted_math_functions(tmp_path):
    from tools.math_expression_tools import code_to_math_formula

    result = json.loads(
        code_to_math_formula(
            "def f(t, w):\n    return math.sqrt(t) * np.sin(w)",
            "python",
            str(tmp_path),
        )
    )
    assert result["ok"] is True
    assert "sin" in result["latex"]
    assert "sqrt" in result["latex"] or "\\sqrt" in result["latex"]


def test_code_to_math_formula_rejects_unsupported_source_language():
    from tools.math_expression_tools import code_to_math_formula

    result = json.loads(code_to_math_formula("function f() { return 1; }", "javascript"))
    assert "error" in result
    assert "numpy" in result["supported"]


def test_math_expression_tools_are_in_math_toolset():
    from toolsets import TOOLSETS

    assert TOOLSETS["math"]["tools"] == [
        "math_expression_cleanup",
        "math_formula_to_code",
        "code_to_math_formula",
    ]
