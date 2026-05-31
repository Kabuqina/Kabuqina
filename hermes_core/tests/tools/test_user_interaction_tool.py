from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_review_outline_passes_artifact_to_callback():
    from tools.user_interaction_tool import review_outline_tool

    captured = {}

    def callback(question, choices, kind=None, artifact=None):
        captured["question"] = question
        captured["choices"] = choices
        captured["kind"] = kind
        captured["artifact"] = artifact
        return {"action": "edit", "text": "# Edited outline"}

    result = json.loads(
        review_outline_tool(
            question="请确认 PPT 大纲",
            outline="# 原始大纲",
            choices=["通过", "补充要求", "自行编辑"],
            callback=callback,
        )
    )

    assert result["ok"] is True
    assert result["user_response"]["action"] == "edit"
    assert captured["kind"] == "outline_review"
    assert captured["artifact"] == {"type": "ppt_outline", "content": "# 原始大纲"}
