# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""L-4 bounded knowledge-point post-node contracts."""

from __future__ import annotations

import hashlib

import pytest

from agent.knowledge_post_node import (
    KNOWLEDGE_POST_POLICY_VERSION,
    MAX_KNOWLEDGE_CANDIDATES,
    MAX_POST_INPUT_CODEPOINTS,
    KnowledgePointCandidateV2,
    KnowledgePostContractError,
    KnowledgePostResultV2,
    run_knowledge_post_node,
    strip_legacy_kq_kp_blocks,
)


def test_extracts_only_explicit_visible_definitions_and_headings():
    result = run_knowledge_post_node(
        "**动量守恒**：封闭系统的总动量在相互作用前后保持不变。\n\n"
        "## 单位分析\n检查量纲是否一致可以快速发现公式错配。"
    )

    assert result.visible_text.startswith("**动量守恒**")
    assert [item.to_dict() for item in result.candidates] == [
        {
            "schema_version": 2,
            "name": "动量守恒",
            "gist": "封闭系统的总动量在相互作用前后保持不变。",
            "source": "model",
            "confidence": "inferred",
        },
        {
            "schema_version": 2,
            "name": "单位分析",
            "gist": "检查量纲是否一致可以快速发现公式错配。",
            "source": "model",
            "confidence": "inferred",
        },
    ]
    assert result.policy_version == KNOWLEDGE_POST_POLICY_VERSION
    assert result.legacy_block_removed is False
    assert result.analysis_truncated is False


def test_plain_prose_silently_produces_no_candidates():
    result = run_knowledge_post_node("先把等式两边同时除以质量，再检查单位是否一致。")

    assert result.candidates == ()
    assert result.visible_text == "先把等式两边同时除以质量，再检查单位是否一致。"


def test_legacy_payload_is_removed_but_never_used_as_candidate_truth():
    result = run_knowledge_post_node(
        "正文保持可见。\n\n"
        "```kq-kp\n"
        '[{"name":"伪造事实","gist":"这一项只能来自旧协议负载。"}]\n'
        "```"
    )

    assert result.visible_text == "正文保持可见。"
    assert result.candidates == ()
    assert result.legacy_block_removed is True


def test_final_unterminated_legacy_block_is_removed_after_completion():
    visible, removed = strip_legacy_kq_kp_blocks(
        "干净正文。\n```kq-kp\n[{\"name\":\"partial\"}"
    )

    assert visible == "干净正文。"
    assert removed is True


def test_definitions_inside_complete_or_unterminated_code_fences_are_ignored():
    result = run_knowledge_post_node(
        "```python\n**danger**: this is source code, not teaching metadata\n```\n"
        "```text\n## still code\nthis must also stay out of candidates"
    )

    assert result.candidates == ()


def test_candidate_cleanup_deduplicates_and_caps_at_five():
    definitions = [
        f"**知识点 {index}**：这是足够长的知识点解释文本 {index}。"
        for index in range(MAX_KNOWLEDGE_CANDIDATES + 3)
    ]
    definitions.insert(1, "**知识点 0**：重复项不得覆盖最初提取结果。")
    definitions.append("**控\x00制符**：内容\x08仍然会在候选字段中安全清理。")

    result = run_knowledge_post_node("\n".join(definitions))

    assert len(result.candidates) == MAX_KNOWLEDGE_CANDIDATES
    assert [item.name for item in result.candidates] == [
        f"知识点 {index}" for index in range(MAX_KNOWLEDGE_CANDIDATES)
    ]


def test_analysis_is_bounded_without_truncating_or_rehashing_visible_message():
    prefix = "普通正文。" * (MAX_POST_INPUT_CODEPOINTS // 5 + 1)
    text = prefix + "\n**边界外知识点**：这个定义位于分析窗口之外，不应被提取。"

    result = run_knowledge_post_node(text)

    assert result.visible_text == text
    assert result.visible_sha256 == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert result.analysis_truncated is True
    assert result.candidates == ()


def test_exact_candidate_schema_rejects_unknown_or_branch_fields():
    base = {
        "schema_version": 2,
        "name": "单位分析",
        "gist": "检查量纲是否一致可以发现公式错配。",
        "source": "model",
        "confidence": "inferred",
    }

    for forbidden in ("passed", "mastery", "auto_capture", "branch"):
        with pytest.raises(KnowledgePostContractError):
            KnowledgePointCandidateV2.from_mapping({**base, forbidden: True})


def test_result_contract_rejects_hash_or_candidate_shape_drift():
    candidate = KnowledgePointCandidateV2(
        name="单位分析",
        gist="检查量纲是否一致可以发现公式错配。",
    )

    with pytest.raises(KnowledgePostContractError):
        KnowledgePostResultV2(
            visible_text="正文",
            candidates=(candidate,),
            legacy_block_removed=False,
            analysis_truncated=False,
            visible_sha256="0" * 64,
        )
    with pytest.raises(KnowledgePostContractError):
        KnowledgePostResultV2(
            visible_text="正文",
            candidates=[candidate],  # type: ignore[arg-type]
            legacy_block_removed=False,
            analysis_truncated=False,
            visible_sha256=hashlib.sha256("正文".encode()).hexdigest(),
        )
