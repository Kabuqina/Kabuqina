"""Tests for kabuqina_cli.model_normalize — provider-aware model name normalization."""
import pytest

from kabuqina_cli.model_normalize import (
    normalize_model_for_provider,
    _DOT_TO_HYPHEN_PROVIDERS,
    _AGGREGATOR_PROVIDERS,
    _normalize_for_deepseek,
    detect_vendor,
)


# ── Anthropic dot-to-hyphen conversion (regression) ────────────────────

class TestAnthropicDotToHyphen:
    """Anthropic API still needs dots→hyphens."""

    @pytest.mark.parametrize("model,expected", [
        ("claude-sonnet-4.6", "claude-sonnet-4-6"),
        ("claude-opus-4.5", "claude-opus-4-5"),
    ])
    def test_anthropic_converts_dots(self, model, expected):
        result = normalize_model_for_provider(model, "anthropic")
        assert result == expected

    def test_anthropic_strips_vendor_prefix(self):
        result = normalize_model_for_provider("anthropic/claude-sonnet-4.6", "anthropic")
        assert result == "claude-sonnet-4-6"


# ── Aggregator providers (regression) ──────────────────────────────────

class TestAggregatorProviders:
    """Aggregators need vendor/model slugs."""

    def test_openrouter_prepends_vendor(self):
        result = normalize_model_for_provider("claude-sonnet-4.6", "openrouter")
        assert result == "anthropic/claude-sonnet-4.6"

    def test_nous_prepends_vendor(self):
        result = normalize_model_for_provider("gpt-5.4", "nous")
        assert result == "openai/gpt-5.4"

    def test_vendor_already_present(self):
        result = normalize_model_for_provider("anthropic/claude-sonnet-4.6", "openrouter")
        assert result == "anthropic/claude-sonnet-4.6"


class TestIssue6211NativeProviderPrefixNormalization:
    @pytest.mark.parametrize("model,target_provider,expected", [
        ("zai/glm-5.1", "zai", "glm-5.1"),
        ("google/gemini-2.5-pro", "gemini", "google/gemini-2.5-pro"),
        ("moonshot/kimi-k2.5", "kimi-coding", "kimi-k2.5"),
        ("anthropic/claude-sonnet-4.6", "openrouter", "anthropic/claude-sonnet-4.6"),
        ("Qwen/Qwen3.5-397B-A17B", "huggingface", "Qwen/Qwen3.5-397B-A17B"),
        ("modal/zai-org/GLM-5-FP8", "custom", "modal/zai-org/GLM-5-FP8"),
    ])
    def test_native_provider_prefixes_are_only_stripped_on_matching_provider(
        self, model, target_provider, expected
    ):
        assert normalize_model_for_provider(model, target_provider) == expected


# ── detect_vendor ──────────────────────────────────────────────────────

class TestDetectVendor:
    @pytest.mark.parametrize("model,expected", [
        ("claude-sonnet-4.6", "anthropic"),
        ("gpt-5.4-mini", "openai"),
        ("minimax-m2.7", "minimax"),
        ("glm-4.5", "z-ai"),
        ("kimi-k2.5", "moonshotai"),
    ])
    def test_detects_known_vendors(self, model, expected):
        assert detect_vendor(model) == expected


# ── DeepSeek V-series pass-through (bug: V4 models silently folded to V3) ──

class TestDeepseekVSeriesPassThrough:
    """DeepSeek's V-series IDs (``deepseek-v4-pro``, ``deepseek-v4-flash``,
    and future ``deepseek-v<N>-*`` variants) are first-class model IDs
    accepted directly by DeepSeek's Chat Completions API. Earlier code
    folded every non-reasoner name into ``deepseek-chat``, which on
    aggregators (Nous portal, OpenRouter via DeepInfra) routes to V3 —
    silently downgrading users who picked V4.
    """

    @pytest.mark.parametrize("model", [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",          # vendor-prefixed
        "deepseek/deepseek-v4-flash",
        "DeepSeek-V4-Pro",                    # case-insensitive
        "deepseek-v4-flash-20260423",         # dated variant
        "deepseek-v5-pro",                    # future V-series
        "deepseek-v10-ultra",                 # double-digit future
    ])
    def test_v_series_passes_through(self, model):
        expected = model.split("/", 1)[-1].lower()
        assert _normalize_for_deepseek(model) == expected

    def test_deepseek_provider_preserves_v4_pro(self):
        """End-to-end via normalize_model_for_provider — user selecting
        V4 Pro must reach DeepSeek's API as V4 Pro, not V3 alias."""
        result = normalize_model_for_provider("deepseek-v4-pro", "deepseek")
        assert result == "deepseek-v4-pro"

    def test_deepseek_provider_preserves_v4_flash(self):
        result = normalize_model_for_provider("deepseek-v4-flash", "deepseek")
        assert result == "deepseek-v4-flash"


# ── DeepSeek regressions (existing behaviour still holds) ──────────────

class TestDeepseekCanonicalAndReasonerMapping:
    """Canonical pass-through and reasoner-keyword folding stay intact."""

    @pytest.mark.parametrize("model,expected", [
        ("deepseek-chat", "deepseek-chat"),
        ("deepseek-reasoner", "deepseek-reasoner"),
        ("DEEPSEEK-CHAT", "deepseek-chat"),
    ])
    def test_canonical_models_pass_through(self, model, expected):
        assert _normalize_for_deepseek(model) == expected

    @pytest.mark.parametrize("model", [
        "deepseek-r1",
        "deepseek-r1-0528",
        "deepseek-think-v3",
        "deepseek-reasoning-preview",
        "deepseek-cot-experimental",
    ])
    def test_reasoner_keywords_map_to_reasoner(self, model):
        assert _normalize_for_deepseek(model) == "deepseek-reasoner"

    @pytest.mark.parametrize("model", [
        "deepseek-chat-v3.1",    # 'chat' prefix, not V-series pattern
        "unknown-model",
        "something-random",
        "gpt-5",                 # non-DeepSeek names still fall through
    ])
    def test_unknown_names_fall_back_to_chat(self, model):
        assert _normalize_for_deepseek(model) == "deepseek-chat"
