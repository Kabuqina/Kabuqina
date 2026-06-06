from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_cleanup_normalizes_ocr_and_reports_variables():
    from tools.math_expression_tools import math_expression_cleanup

    result = json.loads(math_expression_cleanup("E = m c ^ 2"))

    assert result["ok"] is True
    assert result["clean_latex"] == "E = m c^{2}"
    assert "E = m c^{2}" in result["markdown"]
    assert any(row["name"] == "E" for row in result["variable_table"])
    assert result["warnings"] == []


def test_formula_to_code_supports_python_numpy_cpp17():
    from tools.math_expression_tools import math_formula_to_code

    py = json.loads(math_formula_to_code("E = mc^2", "python"))
    npy = json.loads(math_formula_to_code("E = mc^2", "numpy"))
    cpp = json.loads(math_formula_to_code("E = mc^2", "cpp17"))

    assert py["ok"] is True
    assert py["language"] == "python"
    assert "def compute_energy" in py["code"]
    assert "return m * c ** 2" in py["code"]

    assert npy["ok"] is True
    assert npy["language"] == "numpy"
    assert "np.asarray" in npy["code"]
    assert "return m_arr * c_arr ** 2" in npy["code"]

    assert cpp["ok"] is True
    assert cpp["language"] == "cpp17"
    assert "#include <cmath>" in cpp["code"]
    assert "std::pow(c, 2)" in cpp["code"]
    assert "Eigen" not in cpp["code"]
    assert "Boost" not in cpp["code"]


def test_code_to_math_formula_writes_html_and_pdf_warning(tmp_path):
    from tools.math_expression_tools import code_to_math_formula

    result = json.loads(
        code_to_math_formula(
            "def energy(m, c):\n    return m * c ** 2",
            "python",
            str(tmp_path),
        )
    )

    assert result["ok"] is True
    assert "E = m c^{2}" in result["latex"]
    assert "E = m c^{2}" in result["markdown"]
    assert Path(result["html_path"]).exists()
    assert result["pdf_path"] == ""
    assert any("PDF" in warning for warning in result["warnings"])
    assert any(row["name"] == "m" for row in result["variable_table"])


def test_math_expression_tools_are_in_math_toolset():
    from toolsets import TOOLSETS

    assert TOOLSETS["math"]["tools"] == [
        "math_expression_cleanup",
        "math_formula_to_code",
        "code_to_math_formula",
    ]
