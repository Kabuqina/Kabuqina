# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the idempotent built-in course seeder."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for p in (SRC_DIR, CORE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from learning.builtin_course_seed import (  # noqa: E402
    BUILTIN_COURSE_MIGRATION_KEY,
    load_course,
    seed_builtin_course,
)
from learning.builtin_courses import python_advanced  # noqa: E402
from learning.flashcards import FLASHCARD_ITEM_TYPE, FlashcardService  # noqa: E402
from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_contract import validate_envelope  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402
from learning.quizzes import QUIZ_QUESTION_ITEM_TYPE, QuizService  # noqa: E402

OWNER = "desktop:seed-owner"


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        yield LearningExecutionContext(store, owner_id=OWNER)
    finally:
        store.close()


def test_course_artifacts_pass_contract():
    """Every seed artifact payload must satisfy the frozen contract."""
    course = load_course()
    assert course["artifacts"], "course must define artifacts"
    for spec in course["artifacts"]:
        envelope = {
            "version": 1,
            "kind": spec["kind"],
            "space_id": course["space"]["space_id"],
            "title": spec["title"],
            "payload": spec["payload"],
        }
        # Raises ContractError on any violation.
        validate_envelope(envelope)


def test_seed_creates_space_artifacts_and_materials(ctx, tmp_path):
    workspace = tmp_path / "workspace"
    result = seed_builtin_course(ctx, workspace_root=workspace)

    assert result["seeded"] is True
    space_id = python_advanced.SPACE_ID
    assert result["space_id"] == space_id

    # Space exists and — on a fresh owner — is current (visible immediately).
    assert any(s["space_id"] == space_id for s in ctx.list_spaces())
    assert ctx.current_space() == space_id

    # Flashcards and quiz questions materialized into items.
    cards = FlashcardService(ctx).list_cards()
    assert len(cards) == len(python_advanced._flashcard_deck()["payload"]["cards"])
    questions = QuizService(ctx).list_questions()
    assert len(questions) == len(python_advanced._quiz()["payload"]["questions"])

    # Plan / knowledge_base / resource_pack persisted as reviewable drafts.
    for kind in ("learning_plan", "knowledge_base", "resource_pack"):
        drafts = ctx.list_artifacts(kind=kind, status="draft")
        assert len(drafts) == 1, f"expected one {kind} draft"

    # Materials written under the workspace.
    base = workspace / python_advanced.MATERIALS_SUBDIR
    assert (base / "README.md").is_file()
    assert (base / "code" / "iterators_generators.py").is_file()
    assert result["materials"]["written"] == len(python_advanced._MATERIALS)


def test_course_links_code_repo(ctx, tmp_path):
    """The structured layer must reference the external code+dataset repo."""
    repo = python_advanced.CODE_REPO_URL
    assert repo.startswith("https://github.com/")

    result = seed_builtin_course(ctx, workspace_root=tmp_path / "workspace")
    assert result["code_repo"] == repo

    # resource_pack draft carries the repo url; source_refs record it too.
    ctx.select_space(python_advanced.SPACE_ID)
    pack = ctx.list_artifacts(kind="resource_pack")[0]
    resources = pack["envelope"]["payload"]["resources"]
    assert any(r.get("url") == repo for r in resources)
    assert any(
        isinstance(ref, dict) and ref.get("code_repo") == repo
        for ref in pack["envelope"]["source_refs"]
    )


def test_seed_is_idempotent(ctx, tmp_path):
    workspace = tmp_path / "workspace"
    first = seed_builtin_course(ctx, workspace_root=workspace)
    assert first["seeded"] is True

    second = seed_builtin_course(ctx, workspace_root=workspace)
    assert second["seeded"] is False
    assert second["reason"] == "already_seeded"

    # No duplicate artifacts from the second run.
    space_id = python_advanced.SPACE_ID
    ctx.select_space(space_id)
    assert len(ctx.list_artifacts(kind="quiz")) == 1
    assert len(ctx.list_items(item_type=FLASHCARD_ITEM_TYPE)) == len(
        python_advanced._flashcard_deck()["payload"]["cards"]
    )
    assert len(ctx.list_items(item_type=QUIZ_QUESTION_ITEM_TYPE)) == len(
        python_advanced._quiz()["payload"]["questions"]
    )
    assert ctx.is_migrated(BUILTIN_COURSE_MIGRATION_KEY)


def test_seed_preserves_prior_space_focus(ctx, tmp_path):
    # Owner already working in another space.
    ctx.create_space(title="My space", space_id="my-space", make_current=True)
    assert ctx.current_space() == "my-space"

    seed_builtin_course(ctx, workspace_root=tmp_path / "workspace")

    # Built-in course seeded but focus restored to the owner's space.
    assert ctx.current_space() == "my-space"
    assert any(s["space_id"] == python_advanced.SPACE_ID for s in ctx.list_spaces())


def test_seed_without_workspace_skips_materials(ctx):
    result = seed_builtin_course(ctx, workspace_root=None)
    assert result["seeded"] is True
    assert result["materials"]["skipped"] == "no_workspace"


def test_materials_are_not_overwritten(ctx, tmp_path):
    workspace = tmp_path / "workspace"
    base = workspace / python_advanced.MATERIALS_SUBDIR
    base.mkdir(parents=True)
    (base / "README.md").write_text("USER EDIT", encoding="utf-8")

    seed_builtin_course(ctx, workspace_root=workspace)

    # Pre-existing file preserved; others still written.
    assert (base / "README.md").read_text(encoding="utf-8") == "USER EDIT"
    assert (base / "01-iterators-generators.md").is_file()


def test_route_seeds_once(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    secret = "seed-route-secret"
    db_path = tmp_path / "learning.db"
    workspace = tmp_path / "workspace"
    env = {
        "HERMESDESK_BRIDGE_SECRET": secret,
        "HERMESDESK_WORKSPACE": str(workspace),
    }
    with patch.dict(os.environ, env, clear=False):
        with patch(
            "learning.learning_store.default_learning_db_path", return_value=db_path
        ):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                client = TestClient(create_app())
                headers = {"X-HermesDesk-Auth": secret}

                first = client.post(
                    "/api/desk/study/migrations/builtin-course", headers=headers
                )
                assert first.status_code == 200
                assert first.json()["seeded"] is True

                second = client.post(
                    "/api/desk/study/migrations/builtin-course", headers=headers
                )
                assert second.status_code == 200
                assert second.json()["seeded"] is False

    assert (workspace / python_advanced.MATERIALS_SUBDIR / "README.md").is_file()
