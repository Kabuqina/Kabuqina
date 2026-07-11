import sys
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
CORE_DIR = Path(__file__).resolve().parents[2] / "hermes_core"
for path in (SRC_DIR, CORE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from study_semantic_reviewer import review_artifact_with_model


class FakeAgent:
    max_iterations = 99
    def __init__(self, response):
        self.response = response
        self.prompt = ""
        self.closed = False
    def run_conversation(self, *, user_message, **_kwargs):
        self.prompt = user_message
        return {"final_response": self.response}
    def close(self):
        self.closed = True


def test_production_reviewer_runs_prompt_and_parses_strict_boolean():
    agent = FakeAgent('{"passed": true}')
    with patch("desk_server.chat_core._desk_chat_build_agent", return_value=agent):
        assert review_artifact_with_model({"envelope": {"kind": "knowledge_base"}}) is True
    assert "untrusted data" in agent.prompt
    assert agent.max_iterations == 1
    assert agent.closed is True


def test_production_reviewer_invalid_output_fails_closed_to_pending():
    agent = FakeAgent("passed")
    with patch("desk_server.chat_core._desk_chat_build_agent", return_value=agent):
        assert review_artifact_with_model({"envelope": {}}) is None
