# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Idempotent seeder for built-in learning courses.

A built-in course cannot ship as a pre-populated ``learning.db`` — that database
is created at runtime and scoped to a per-install ``owner_id``
(``desktop:<uuid>``). Instead the course content is a version-controlled Python
data module (see :mod:`learning.builtin_courses.python_advanced`) and this
seeder writes it into the current owner's ``learning.db`` **once**, guarded by a
migration key. This mirrors the localStorage→db migration flow in
``desk_server.routes.study_routes`` (``is_migrated`` + trusted write + activate).

The seeder is a *trusted* caller: it may write artifacts and drive the
draft→active lifecycle directly (unlike a model tool). Flashcard decks and
quizzes are activated so their items materialize immediately; plan / knowledge
base / resource pack stay as ``draft`` so they surface in the review flow.

Embedded source materials are written into ``<workspace>/<materials_subdir>``
so the Read layer / material index (confined by ``PathPolicy`` to the workspace)
can read them.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from learning.builtin_courses import python_advanced
from learning.flashcards import FlashcardService
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter
from learning.quizzes import QuizService

logger = logging.getLogger(__name__)

# Bump the version suffix to re-seed after a content change (a new key re-runs).
BUILTIN_COURSE_MIGRATION_KEY = "builtin:course:python-advanced:v1"

DEFAULT_COURSE: Dict[str, Any] = python_advanced.COURSE


def load_course() -> Dict[str, Any]:
    """Return the default built-in course definition."""
    return DEFAULT_COURSE


def _write_materials(
    course: Dict[str, Any], workspace_root: Optional[Path]
) -> Dict[str, Any]:
    """Write embedded materials into ``<workspace>/<materials_subdir>``.

    Idempotent: existing files are left untouched (preserves user edits / re-run
    safety). Paths are constrained to stay under the materials base directory.
    """
    if not workspace_root:
        return {"written": 0, "skipped": "no_workspace"}

    base = (Path(workspace_root) / course.get("materials_subdir", "courses")).resolve()
    written = 0
    skipped = 0
    for material in course.get("materials", []):
        rel = str(material.get("path") or "").strip()
        content = material.get("content")
        if not rel or not isinstance(content, str):
            continue
        dest = (base / rel).resolve()
        try:
            dest.relative_to(base)
        except ValueError:
            logger.warning("skipping material escaping base: %r", rel)
            continue
        if dest.exists():
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written += 1
    return {"written": written, "skipped": skipped, "path": str(base)}


def seed_builtin_course(
    ctx: LearningExecutionContext,
    *,
    workspace_root: Optional[Path] = None,
    course: Optional[Dict[str, Any]] = None,
    migration_key: str = BUILTIN_COURSE_MIGRATION_KEY,
) -> Dict[str, Any]:
    """Seed the built-in course into the current owner's ``learning.db`` once.

    Idempotent via ``migration_key``: a no-op after the first successful run for
    this owner. Writes into the course's dedicated space (created if absent) and
    restores the previously-current space afterwards — so seeding never steals
    focus from a space the owner was already using. On a fresh install (no prior
    current space) the built-in course becomes current, so it is visible at once.

    Returns a summary dict; ``{"seeded": False}`` when already seeded.
    """
    course = course or DEFAULT_COURSE

    if ctx.is_migrated(migration_key):
        return {"seeded": False, "reason": "already_seeded"}

    space = course["space"]
    space_id = space["space_id"]
    source_refs = course.get("source_refs")

    previous_space = ctx.current_space()
    # make_current so put_artifact writes land in the course space.
    ctx.create_space(title=space["title"], space_id=space_id, make_current=True)

    writer = OutputWriter(ctx)
    artifacts = []
    for spec in course.get("artifacts", []):
        kind = spec["kind"]
        res = writer.write_artifact(
            kind=kind,
            title=spec["title"],
            payload=spec["payload"],
            source_refs=source_refs,
        )
        artifact_id = res["artifact_id"]
        materialized = 0
        if kind == "flashcard_deck":
            materialized = FlashcardService(ctx).activate_deck(artifact_id)["materialized"]
        elif kind == "quiz":
            materialized = QuizService(ctx).activate_quiz(artifact_id)["materialized"]
        artifacts.append(
            {"artifact_id": artifact_id, "kind": kind, "materialized": materialized}
        )

    materials = _write_materials(course, workspace_root)

    # Restore prior focus if the owner was already working in another space.
    if previous_space and previous_space != space_id:
        ctx.select_space(previous_space)

    ctx.mark_migration(
        migration_key,
        detail={
            "space_id": space_id,
            "artifacts": len(artifacts),
            "materials_written": materials.get("written", 0),
        },
    )
    return {
        "seeded": True,
        "space_id": space_id,
        "title": space["title"],
        "code_repo": course.get("code_repo"),
        "artifacts": artifacts,
        "materials": materials,
    }
