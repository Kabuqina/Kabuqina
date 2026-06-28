from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from cron.goal_state import GoalReport
from cron.goal_verifiers import VerificationContext, verify


def _report(*artifacts: str) -> GoalReport:
    return GoalReport(
        status="candidate_done",
        summary="ready",
        artifacts=tuple(artifacts),
        evidence={},
        next_step=None,
        external_side_effects=(),
    )


def _context(workdir: Path, *, config, artifacts=(), previous=None):
    return VerificationContext(
        workdir=workdir,
        report=_report(*artifacts),
        config=config,
        previous_evidence_hash=previous,
    )


@pytest.mark.parametrize("path", ["../outside.txt", "nested/../../outside.txt"])
def test_artifact_exists_rejects_parent_traversal(tmp_path, path):
    result = verify(
        "artifact_exists",
        _context(tmp_path, config={"paths": [path]}),
    )

    assert result.outcome == "error"
    assert "confined" in result.summary


def test_artifact_exists_rejects_absolute_paths(tmp_path):
    outside = (tmp_path.parent / "outside.txt").resolve()
    outside.write_text("secret", encoding="utf-8")

    result = verify(
        "artifact_exists",
        _context(tmp_path, config={"paths": [str(outside)]}),
    )

    assert result.outcome == "error"
    assert "relative" in result.summary


def test_artifact_exists_rejects_missing_workdir(tmp_path):
    result = verify(
        "artifact_exists",
        _context(tmp_path / "missing", config={"paths": ["a.txt"]}),
    )

    assert result.outcome == "error"
    assert "workdir" in result.summary


def test_artifact_exists_rejects_symlink_escape(tmp_path):
    workdir = tmp_path / "work"
    outside = tmp_path / "outside"
    workdir.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = workdir / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    result = verify(
        "artifact_exists",
        _context(workdir, config={"paths": ["link/secret.txt"]}),
    )

    assert result.outcome == "error"
    assert "confined" in result.summary


def test_artifact_exists_passes_only_for_regular_files(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "one.txt").write_text("one", encoding="utf-8")

    passed = verify(
        "artifact_exists",
        _context(tmp_path, config={"paths": ["nested/one.txt"]}),
    )
    failed = verify(
        "artifact_exists",
        _context(tmp_path, config={"paths": ["nested", "missing.txt"]}),
    )

    assert passed.outcome == "pass"
    assert passed.evidence["paths"] == ["nested/one.txt"]
    assert failed.outcome == "fail"
    assert failed.evidence["missing_or_not_file"] == ["missing.txt", "nested"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_record(workdir: Path, relative: str, **changes):
    path = workdir / relative
    record = {
        "path": relative.replace("\\", "/"),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }
    record.update(changes)
    return record


def _write_manifest(workdir: Path, records):
    (workdir / "learning-materials.json").write_text(
        json.dumps({"files": records}), encoding="utf-8"
    )


def _manifest_context(workdir: Path):
    return _context(
        workdir,
        artifacts=("learning-materials.json",),
        config={
            "manifest": "learning-materials.json",
            "roots": ["materials"],
            "extensions": [".pdf", ".docx", ".pptx"],
        },
    )


def test_manifest_complete_passes_with_sorted_normalized_records(tmp_path):
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "z.pdf").write_bytes(b"z")
    (materials / "a.docx").write_bytes(b"aa")
    (materials / "ignored.txt").write_text("ignored", encoding="utf-8")
    records = [
        _manifest_record(tmp_path, "materials/z.pdf"),
        _manifest_record(tmp_path, "materials/a.docx"),
    ]
    _write_manifest(tmp_path, records)

    result = verify("manifest_complete", _manifest_context(tmp_path))

    assert result.outcome == "pass"
    assert result.evidence["manifest_complete"] is True
    assert result.evidence["paths"] == ["materials/a.docx", "materials/z.pdf"]
    expected_hash = result.evidence["content_hash"]

    _write_manifest(tmp_path, list(reversed(records)))
    reordered = verify("manifest_complete", _manifest_context(tmp_path))
    assert reordered.evidence["content_hash"] == expected_hash


@pytest.mark.parametrize(
    ("mutate", "diagnostic"),
    [
        (lambda records: records[:-1], "missing_records"),
        (lambda records: records + [dict(records[0])], "duplicate_records"),
        (
            lambda records: records + [
                {"path": "outside.pdf", "sha256": "0" * 64, "size_bytes": 1}
            ],
            "out_of_root_records",
        ),
        (
            lambda records: [dict(records[0], sha256="bad"), records[1]],
            "invalid_records",
        ),
        (
            lambda records: [dict(records[0], size_bytes="1"), records[1]],
            "invalid_records",
        ),
    ],
)
def test_manifest_complete_rejects_incomplete_or_invalid_records(
    tmp_path, mutate, diagnostic
):
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "one.pdf").write_bytes(b"one")
    (materials / "two.docx").write_bytes(b"two")
    records = [
        _manifest_record(tmp_path, "materials/one.pdf"),
        _manifest_record(tmp_path, "materials/two.docx"),
    ]
    _write_manifest(tmp_path, mutate(records))

    result = verify("manifest_complete", _manifest_context(tmp_path))

    assert result.outcome == "fail"
    assert result.evidence["manifest_complete"] is False
    assert result.evidence[diagnostic]


def test_manifest_complete_rejects_non_normalized_record_path(tmp_path):
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "one.pdf").write_bytes(b"one")
    record = _manifest_record(tmp_path, "materials/one.pdf")
    record["path"] = "materials/../materials/one.pdf"
    _write_manifest(tmp_path, [record])

    result = verify("manifest_complete", _manifest_context(tmp_path))

    assert result.outcome == "fail"
    assert result.evidence["invalid_records"]


def test_content_hash_changed_uses_sorted_artifact_hashes(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    context = _context(
        tmp_path,
        artifacts=("b.txt", "a.txt"),
        config={},
    )

    first = verify("content_hash_changed", context)
    same = verify(
        "content_hash_changed",
        replace(context, previous_evidence_hash=first.evidence["content_hash"]),
    )
    (tmp_path / "a.txt").write_text("changed", encoding="utf-8")
    changed = verify(
        "content_hash_changed",
        replace(context, previous_evidence_hash=first.evidence["content_hash"]),
    )

    assert first.outcome == "pass"
    assert [item["path"] for item in first.evidence["artifacts"]] == ["a.txt", "b.txt"]
    assert same.outcome == "fail"
    assert changed.outcome == "pass"
    assert changed.evidence["content_hash"] != first.evidence["content_hash"]


def test_unknown_verifier_returns_error_without_fallback(tmp_path):
    result = verify("llm_rubric", _context(tmp_path, config={}))

    assert result.outcome == "error"
    assert "unknown verifier" in result.summary

