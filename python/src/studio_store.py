# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Local persistence for Studio projects and read-only source snapshots."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from kabuqina_cli.config import get_kabuqina_home


_STAGES = frozenset({"brief", "gathering", "shaping", "review"})


def default_studio_db_path() -> Path:
    return (get_kabuqina_home() / "studio" / "studio.db").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, *, name: str, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip()
    if not allow_empty and not normalized:
        raise ValueError(f"{name} is required")
    if len(normalized) > maximum:
        raise ValueError(f"{name} is too long")
    return normalized


class StudioStore:
    """Small Studio-owned SQLite store.

    Study remains the source of truth for learning objects. This database only
    owns Studio projects and immutable snapshots created by an explicit gather.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or default_studio_db_path()).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS studio_projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                brief TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL CHECK (stage IN ('brief','gathering','shaping','review')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS studio_source_snapshots (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                origin TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 1),
                return_target TEXT,
                fallback_target TEXT,
                position INTEGER NOT NULL CHECK (position >= 0),
                FOREIGN KEY (project_id) REFERENCES studio_projects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS studio_sources_project_position
                ON studio_source_snapshots(project_id, position);
            """
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "StudioStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM studio_projects ORDER BY updated_at DESC, id"
        ).fetchall()
        return [self._project_payload(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM studio_projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._project_payload(row) if row else None

    def create_project(self, title: str) -> dict[str, Any]:
        clean_title = _text(title, name="title", maximum=200)
        project_id = uuid.uuid4().hex
        timestamp = _now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO studio_projects(id,title,brief,stage,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (project_id, clean_title, "", "brief", timestamp, timestamp),
            )
        return self._require_project(project_id)

    def save_brief(self, project_id: str, brief: str) -> dict[str, Any]:
        clean_brief = _text(
            brief, name="brief", maximum=20_000, allow_empty=True
        )
        stage = "gathering" if clean_brief else "brief"
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE studio_projects SET brief = ?, "
                "stage = CASE WHEN stage IN ('shaping','review') THEN stage ELSE ? END, "
                "updated_at = ? "
                "WHERE id = ?",
                (clean_brief, stage, _now(), project_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"studio project {project_id!r} not found")
        return self._require_project(project_id)

    def delete_project(self, project_id: str) -> dict[str, Any]:
        """Delete one project and its owned snapshots, returning the deleted view.

        Chat transcripts are deliberately outside the Studio store.  The trusted
        route returns the deterministic Studio session id to the caller so the UI
        can detach its local project scope without destroying conversation history.
        """
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"studio project {project_id!r} not found")
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM studio_projects WHERE id = ?", (project_id,)
            )
            if cursor.rowcount != 1:
                raise KeyError(f"studio project {project_id!r} not found")
        return project

    def add_sources_atomic(
        self, project_id: str, snapshots: Iterable[Mapping[str, Any]]
    ) -> dict[str, Any]:
        prepared = [self._validated_snapshot(item) for item in snapshots]
        if not prepared:
            raise ValueError("at least one source is required")

        with self._conn:
            project = self._conn.execute(
                "SELECT 1 FROM studio_projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                raise KeyError(f"studio project {project_id!r} not found")
            start = self._conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM studio_source_snapshots "
                "WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            for offset, item in enumerate(prepared):
                self._conn.execute(
                    "INSERT INTO studio_source_snapshots("
                    "id,project_id,kind,title,origin,excerpt,created_at,revision,"
                    "return_target,fallback_target,position) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item["id"],
                        project_id,
                        item["kind"],
                        item["title"],
                        item["origin"],
                        item["excerpt"],
                        item["createdAt"],
                        item["revision"],
                        item["returnTarget"],
                        item["fallbackTarget"],
                        start + offset,
                    ),
                )
            self._conn.execute(
                "UPDATE studio_projects SET stage = 'shaping', updated_at = ? WHERE id = ?",
                (_now(), project_id),
            )
        return self._require_project(project_id)

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"studio project {project_id!r} not found")
        return project

    def _project_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        stage = row["stage"]
        if stage not in _STAGES:
            raise ValueError(f"invalid Studio stage {stage!r}")
        sources = self._conn.execute(
            "SELECT * FROM studio_source_snapshots WHERE project_id = ? "
            "ORDER BY position, id",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"],
            "title": row["title"],
            "brief": row["brief"],
            "stage": stage,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "sources": [
                {
                    "id": source["id"],
                    "kind": source["kind"],
                    "title": source["title"],
                    "origin": source["origin"],
                    "excerpt": source["excerpt"],
                    "createdAt": source["created_at"],
                    "revision": source["revision"],
                    "returnTarget": source["return_target"],
                    "fallbackTarget": source["fallback_target"],
                }
                for source in sources
            ],
        }

    @staticmethod
    def _validated_snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
        revision = item.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("source revision must be a positive integer")
        return {
            "id": _text(item.get("id"), name="source id", maximum=200),
            "kind": _text(item.get("kind"), name="source kind", maximum=80),
            "title": _text(item.get("title"), name="source title", maximum=500),
            "origin": _text(item.get("origin"), name="source origin", maximum=1_000),
            "excerpt": _text(
                item.get("excerpt"),
                name="source excerpt",
                maximum=20_000,
                allow_empty=True,
            ),
            "createdAt": _text(
                item.get("createdAt"), name="source createdAt", maximum=80
            ),
            "revision": revision,
            "returnTarget": StudioStore._optional_target(item.get("returnTarget")),
            "fallbackTarget": StudioStore._optional_target(item.get("fallbackTarget")),
        }

    @staticmethod
    def _optional_target(value: Any) -> str | None:
        if value is None:
            return None
        return _text(value, name="source target", maximum=2_000)


__all__ = ["StudioStore", "default_studio_db_path"]
