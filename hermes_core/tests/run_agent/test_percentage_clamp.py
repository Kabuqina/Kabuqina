"""Tests for percentage clamping at 100% across display paths.

PR #3480 capped context pressure percentage at 100% in agent/display.py.
When token counts overshoot the context length (possible during streaming or
before compression fires), users should not see >100% in gateway status or
memory tool output.
"""

class TestMemoryToolPercentClamp:
    """tools/memory_tool.py — _success_response and _render_block pct"""

    def test_over_limit_clamped_at_100(self):
        """Percentage should be capped at 100 even if current > limit."""
        # Simulate the calculation directly
        current = 5500
        limit = 5000
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0
        assert pct == 100

    def test_normal_percentage(self):
        current = 2500
        limit = 5000
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0
        assert pct == 50

    def test_zero_limit_returns_zero(self):
        current = 100
        limit = 0
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0
        assert pct == 0


class TestGatewayStatsPercentClamp:
    """gateway/run.py — _format_usage_stats percentage"""

    def test_over_context_clamped_at_100(self):
        last_prompt_tokens = 210_000
        context_length = 200_000
        pct = min(100, last_prompt_tokens / context_length * 100) if context_length else 0
        assert pct == 100

    def test_normal_context(self):
        last_prompt_tokens = 150_000
        context_length = 200_000
        pct = min(100, last_prompt_tokens / context_length * 100) if context_length else 0
        assert pct == 75.0


class TestSourceLinesAreClamped:
    """Verify the actual source files have min(100, ...) applied."""

    @staticmethod
    def _read_file(rel_path: str) -> str:
        import os
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        with open(os.path.join(base, rel_path), encoding="utf-8") as f:
            return f.read()

    def test_gateway_run_clamped(self):
        src = self._read_file("gateway/run.py")
        # Check that the stats handler has min(100, ...)
        assert "min(100, ctx.last_prompt_tokens" in src, (
            "gateway/run.py stats pct is not clamped with min(100, ...)"
        )

    def test_memory_tool_clamped(self):
        src = self._read_file("tools/memory_tool.py")
        # Both _success_response and _render_block should have min(100, ...)
        count = src.count("min(100, int((current / limit)")
        assert count >= 2, (
            f"memory_tool.py has only {count} clamped pct lines, expected >= 2"
        )
