# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Owned-core semantics for the course-less Study scratch notebook."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from learning.learning_context import LearningExecutionContext

SCRATCH_SPACE_TITLE = "杂记本"
logger = logging.getLogger(__name__)


def scratch_space_id(owner_id: str) -> str:
    """Return a stable owner-scoped id without exposing the owner on the wire."""
    return uuid.uuid5(
        uuid.NAMESPACE_URL, f"https://kabuqina.local/study/scratch/{owner_id}"
    ).hex


def ensure_scratch_notebook(ctx: LearningExecutionContext) -> Dict[str, Any]:
    """Idempotently ensure exactly one discoverable scratch space for this owner.

    Existing scratch spaces win so restored bundles keep their original ids. A
    newly seeded notebook never becomes current and therefore never steals the
    learner's active course.
    """
    for space in ctx.list_spaces():
        if space.get("kind", "course") == "scratch":
            return space
    sid = ctx.create_space(
        title=SCRATCH_SPACE_TITLE,
        space_id=scratch_space_id(ctx.owner_id),
        make_current=False,
        kind="scratch",
    )
    logger.info("seeded scratch notebook space=%s without changing current course", sid)
    return next(space for space in ctx.list_spaces() if space["space_id"] == sid)
