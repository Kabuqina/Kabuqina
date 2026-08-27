# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desktop-owned temporary and managed media lifecycle for Study capture."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import time
from pathlib import Path
from typing import Any

from PIL import Image

from learning.study_capture import StudyCaptureService
from learning.study_capture_contract import (
    SCHEMA_VERSION,
    StudyCaptureContractError,
    validate_capture_session,
    validate_capture_transform,
    validate_study_transcription,
)


class CaptureMediaError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(_canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _format_mime(image_format: str | None) -> str:
    return {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }.get(str(image_format or "").upper(), "")


class StudyCaptureMediaStore:
    """Own capture manifests without exposing absolute paths to the renderer."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        selected = data_dir or os.environ.get("KABUQINA_DATA_DIR") or os.environ.get(
            "HERMESDESK_DATA_DIR"
        )
        if not selected:
            raise CaptureMediaError(
                "capture_invalid_image", "desktop data directory is unavailable", status=500
            )
        self.data_dir = Path(selected).expanduser().resolve()
        self.root = self.data_dir / "study-captures"
        self.temp_root = self.root / "temp"
        self.managed_root = self.root / "managed"

    def _capture_dir(self, capture_id: str) -> Path:
        try:
            validate_capture_session(
                {
                    "schema_version": 1,
                    "capture_id": capture_id,
                    "space_id": "validation",
                    "purpose": "stuck",
                    "source_kind": "upload",
                    "status": "temporary",
                    "revision": 1,
                    "preview": {"width": 1, "height": 1},
                }
            )
        except StudyCaptureContractError as exc:
            raise CaptureMediaError(
                "capture_invalid_image", "capture_id is invalid"
            ) from exc
        return self.temp_root / capture_id

    def _manifest_path(self, capture_id: str) -> Path:
        return self._capture_dir(capture_id) / "session.json"

    def _managed_manifest_path(self, capture_id: str) -> Path:
        return self.managed_root / capture_id / "manifest.json"

    def _read_managed_manifest(self, capture_id: str) -> dict[str, Any] | None:
        try:
            value = json.loads(
                self._managed_manifest_path(capture_id).read_text(encoding="utf-8")
            )
            if set(value) != {
                "schema_version",
                "media_id",
                "sha256",
                "source_sha256",
                "capture",
                "transcription",
            }:
                raise ValueError("managed manifest fields are invalid")
            validate_capture_session(value["capture"])
            validate_study_transcription(value["transcription"])
            sha = str(value["sha256"])
            source_sha = str(value["source_sha256"])
            if (
                value["schema_version"] != SCHEMA_VERSION
                or len(sha) != 64
                or len(source_sha) != 64
                or any(character not in "0123456789abcdef" for character in sha)
                or any(character not in "0123456789abcdef" for character in source_sha)
                or value["media_id"] != f"{capture_id}/{sha}.jpg"
            ):
                raise ValueError("managed media identity is invalid")
            managed_image = self.managed_root / value["media_id"]
            if not managed_image.is_file() or _sha256(managed_image) != sha:
                raise ValueError("managed media hash does not match")
            return value
        except FileNotFoundError:
            return None
        except Exception as exc:
            raise CaptureMediaError(
                "wrongbook_idempotency_conflict",
                "managed capture manifest is invalid",
                status=409,
            ) from exc

    def managed_manifest(self, capture_id: str) -> dict[str, Any]:
        """Return the path-free managed record used by learning persistence."""
        value = self._read_managed_manifest(capture_id)
        if value is None:
            raise CaptureMediaError(
                "capture_invalid_image", "managed capture is unavailable", status=404
            )
        return {
            "media_id": str(value["media_id"]),
            "sha256": str(value["sha256"]),
            "capture": validate_capture_session(value["capture"]),
            "transcription": validate_study_transcription(value["transcription"]),
        }

    def _read_state(self, capture_id: str) -> dict[str, Any]:
        path = self._manifest_path(capture_id)
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            validate_capture_session(state["session"])
            return state
        except FileNotFoundError as exc:
            raise CaptureMediaError(
                "capture_invalid_image", "capture session is unavailable", status=404
            ) from exc
        except (KeyError, TypeError, json.JSONDecodeError, StudyCaptureContractError) as exc:
            raise CaptureMediaError(
                "capture_invalid_image", "capture session manifest is invalid", status=500
            ) from exc

    def _write_state(self, capture_id: str, state: dict[str, Any]) -> None:
        validate_capture_session(state["session"])
        _atomic_json(self._manifest_path(capture_id), state)

    @staticmethod
    def _public(state: dict[str, Any]) -> dict[str, Any]:
        return validate_capture_session(state["session"])

    def register_staged(self, body: Any) -> dict[str, Any]:
        if not isinstance(body, dict) or set(body) != {
            "schema_version",
            "capture_id",
            "space_id",
            "purpose",
            "source_kind",
            "staged_path",
            "mime_type",
            "sha256",
            "preview",
        }:
            raise CaptureMediaError("capture_invalid_image", "stage fields are invalid")
        session = validate_capture_session(
            {
                "schema_version": body.get("schema_version"),
                "capture_id": body.get("capture_id"),
                "space_id": body.get("space_id"),
                "purpose": body.get("purpose"),
                "source_kind": body.get("source_kind"),
                "status": "temporary",
                "revision": 1,
                "preview": body.get("preview"),
            }
        )
        capture_id = session["capture_id"]
        expected_dir = self._capture_dir(capture_id).resolve()
        try:
            staged = Path(body["staged_path"]).expanduser().resolve(strict=True)
        except (OSError, TypeError) as exc:
            raise CaptureMediaError(
                "capture_invalid_image", "staged image is unavailable"
            ) from exc
        if not staged.is_file() or not staged.is_relative_to(expected_dir):
            raise CaptureMediaError(
                "capture_invalid_image", "staged image escaped its capture directory"
            )
        claimed_sha = str(body.get("sha256") or "")
        if len(claimed_sha) != 64 or _sha256(staged) != claimed_sha:
            raise CaptureMediaError(
                "capture_invalid_image", "staged image hash does not match"
            )
        try:
            with Image.open(staged) as image:
                actual_mime = _format_mime(image.format)
                actual_size = image.size
                image.verify()
        except Exception as exc:
            raise CaptureMediaError(
                "capture_invalid_image", "staged image is corrupt"
            ) from exc
        if actual_mime != body.get("mime_type"):
            raise CaptureMediaError(
                "capture_invalid_image", "staged image MIME does not match"
            )
        if actual_size != (
            session["preview"]["width"],
            session["preview"]["height"],
        ):
            raise CaptureMediaError(
                "capture_invalid_image", "staged image dimensions do not match"
            )

        managed = self._read_managed_manifest(capture_id)
        if managed is not None:
            confirmed = validate_capture_session(managed["capture"])
            same_identity = all(
                confirmed[field] == session[field]
                for field in ("capture_id", "space_id", "purpose", "source_kind")
            )
            if same_identity and managed.get("source_sha256") == claimed_sha:
                shutil.rmtree(expected_dir, ignore_errors=True)
                return confirmed
            raise CaptureMediaError(
                "capture_revision_conflict",
                "capture_id already refers to confirmed media",
                status=409,
            )

        manifest = self._manifest_path(capture_id)
        if manifest.exists():
            existing = self._read_state(capture_id)
            existing_session = self._public(existing)
            same_identity = all(
                existing_session[field] == session[field]
                for field in ("capture_id", "space_id", "purpose", "source_kind")
            )
            if existing.get("source_sha256") == claimed_sha and same_identity:
                return existing_session
            raise CaptureMediaError(
                "capture_revision_conflict",
                "capture_id already refers to a different session",
                status=409,
            )
        state = {
            "session": session,
            "source_file": staged.name,
            "source_sha256": claimed_sha,
            "mime_type": actual_mime,
            "normalized_file": None,
            "normalized_sha256": None,
            "transform": None,
            "transform_sha256": None,
            "transcription": None,
        }
        self._write_state(capture_id, state)
        return session

    def normalize(self, raw_transform: Any) -> dict[str, Any]:
        try:
            transform = validate_capture_transform(raw_transform)
        except StudyCaptureContractError as exc:
            raise CaptureMediaError("capture_invalid_image", str(exc)) from exc
        capture_id = transform["capture_id"]
        state = self._read_state(capture_id)
        transform_sha = hashlib.sha256(_canonical_bytes(transform)).hexdigest()
        if state.get("transform_sha256") == transform_sha and state["session"][
            "status"
        ] in {"normalized", "transcribed", "drafted"}:
            return self._public(state)
        if state["session"]["revision"] != transform["expected_revision"]:
            raise CaptureMediaError(
                "capture_revision_conflict", "capture revision changed", status=409
            )
        source = self._capture_dir(capture_id) / state["source_file"]
        destination = self._capture_dir(capture_id) / "normalized.jpg"
        temporary = destination.with_suffix(".tmp.jpg")
        try:
            with Image.open(source) as opened:
                image = opened.convert("RGB")
                width, height = image.size
                crop = transform["crop"]
                left = max(0, math.floor(crop["x"] * width))
                top = max(0, math.floor(crop["y"] * height))
                right = min(width, math.ceil((crop["x"] + crop["width"]) * width))
                bottom = min(
                    height, math.ceil((crop["y"] + crop["height"]) * height)
                )
                if right <= left or bottom <= top:
                    raise ValueError("empty crop")
                image = image.crop((left, top, right, bottom))
                transpose = {
                    90: Image.Transpose.ROTATE_270,
                    180: Image.Transpose.ROTATE_180,
                    270: Image.Transpose.ROTATE_90,
                }.get(transform["rotation"])
                if transpose is not None:
                    image = image.transpose(transpose)
                if transform["grayscale"]:
                    image = image.convert("L").convert("RGB")
                max_edge = transform["max_edge"]
                if max(image.size) > max_edge:
                    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                image.save(temporary, format="JPEG", quality=92, optimize=True)
                normalized_size = image.size
            os.replace(temporary, destination)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise CaptureMediaError(
                "capture_invalid_image", "capture transform failed"
            ) from exc
        state["normalized_file"] = destination.name
        state["normalized_sha256"] = _sha256(destination)
        state["transform"] = transform
        state["transform_sha256"] = transform_sha
        state["session"]["status"] = "normalized"
        state["session"]["revision"] += 1
        state["session"]["preview"] = {
            "width": normalized_size[0],
            "height": normalized_size[1],
        }
        self._write_state(capture_id, state)
        return self._public(state)

    async def transcribe(
        self,
        capture_id: str,
        *,
        expected_revision: int,
        service: StudyCaptureService,
        question_context: str = "",
    ) -> dict[str, Any]:
        state = self._read_state(capture_id)
        if state.get("transcription") is not None:
            return validate_study_transcription(state["transcription"])
        if state["session"]["revision"] != expected_revision:
            raise CaptureMediaError(
                "capture_revision_conflict", "capture revision changed", status=409
            )
        normalized_name = state.get("normalized_file")
        if state["session"]["status"] != "normalized" or not normalized_name:
            raise CaptureMediaError(
                "capture_invalid_image", "capture must be normalized before transcription"
            )
        transcription = await service.transcribe(
            self._capture_dir(capture_id) / normalized_name,
            capture_id=capture_id,
            purpose=state["session"]["purpose"],
            question_context=question_context,
        )
        state["transcription"] = transcription
        state["session"]["status"] = "transcribed"
        state["session"]["revision"] += 1
        self._write_state(capture_id, state)
        return transcription

    def transcription_for_reasoning(
        self, capture_id: str, *, expected_revision: int
    ) -> dict[str, Any]:
        """Load frozen JSON for text reasoning without reopening the image."""
        state = self._read_state(capture_id)
        if state["session"]["revision"] != expected_revision:
            raise CaptureMediaError(
                "capture_revision_conflict", "capture revision changed", status=409
            )
        if state["session"]["status"] not in {"transcribed", "drafted"}:
            raise CaptureMediaError(
                "capture_invalid_image", "capture transcription is unavailable"
            )
        try:
            return validate_study_transcription(state["transcription"])
        except (TypeError, StudyCaptureContractError) as exc:
            raise CaptureMediaError(
                "vision_contract_invalid", "capture transcription is invalid"
            ) from exc

    def confirm(self, capture_id: str, body: Any) -> dict[str, Any]:
        if not isinstance(body, dict) or not set(body).issubset(
            {"expected_revision", "transcription", "decision", "wrongbook"}
        ):
            raise CaptureMediaError("capture_invalid_image", "confirm fields are invalid")
        if "expected_revision" not in body:
            raise CaptureMediaError(
                "capture_revision_conflict", "expected_revision is required", status=409
            )
        if body.get("decision") == "wrong":
            managed = self._read_managed_manifest(capture_id)
            if managed is not None:
                return validate_capture_session(managed["capture"])
        state = self._read_state(capture_id)
        if state["session"]["revision"] != body["expected_revision"]:
            raise CaptureMediaError(
                "capture_revision_conflict", "capture revision changed", status=409
            )
        if "transcription" in body:
            try:
                transcription = validate_study_transcription(body["transcription"])
            except StudyCaptureContractError as exc:
                raise CaptureMediaError("vision_contract_invalid", str(exc)) from exc
            if (
                transcription["capture_id"] != capture_id
                or transcription["purpose"] != state["session"]["purpose"]
            ):
                raise CaptureMediaError(
                    "vision_contract_invalid", "transcription identity changed"
                )
            state["transcription"] = transcription
            state["session"]["status"] = "drafted"
            state["session"]["revision"] += 1
            self._write_state(capture_id, state)
            return self._public(state)

        decision = body.get("decision")
        if decision not in {"wrong", "correct", "unreadable"}:
            raise CaptureMediaError(
                "capture_invalid_image", "decision must be wrong, correct, or unreadable"
            )
        if decision == "wrong":
            if not state.get("transcription") or not state.get("normalized_file"):
                raise CaptureMediaError(
                    "capture_invalid_image", "confirmed wrong capture needs a transcription"
                )
            transcription = validate_study_transcription(state["transcription"])
            if transcription["question_match"] == "different":
                raise CaptureMediaError(
                    "capture_question_mismatch",
                    "photographed work belongs to a different question",
                    status=409,
                )
            sha = state["normalized_sha256"]
            managed_dir = self.managed_root / capture_id
            managed_dir.mkdir(parents=True, exist_ok=True)
            media_name = f"{sha}.jpg"
            managed_image = managed_dir / media_name
            normalized = self._capture_dir(capture_id) / state["normalized_file"]
            if managed_image.exists() and _sha256(managed_image) != sha:
                raise CaptureMediaError(
                    "wrongbook_idempotency_conflict",
                    "managed media identity conflicts",
                    status=409,
                )
            if not managed_image.exists():
                os.replace(normalized, managed_image)
            state["session"]["status"] = "confirmed"
            state["session"]["revision"] += 1
            public = self._public(state)
            _atomic_json(
                managed_dir / "manifest.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "media_id": f"{capture_id}/{media_name}",
                    "sha256": sha,
                    "source_sha256": state["source_sha256"],
                    "capture": public,
                    "transcription": state["transcription"],
                },
            )
        else:
            state["session"]["status"] = "abandoned"
            state["session"]["revision"] += 1
            public = self._public(state)
        shutil.rmtree(self._capture_dir(capture_id), ignore_errors=True)
        return public

    def abandon(self, capture_id: str, expected_revision: int | None = None) -> dict[str, Any]:
        state = self._read_state(capture_id)
        if expected_revision is not None and state["session"]["revision"] != expected_revision:
            raise CaptureMediaError(
                "capture_revision_conflict", "capture revision changed", status=409
            )
        state["session"]["status"] = "abandoned"
        state["session"]["revision"] += 1
        public = self._public(state)
        shutil.rmtree(self._capture_dir(capture_id), ignore_errors=True)
        return public

    def discard_failed_transcription(self, capture_id: str) -> None:
        shutil.rmtree(self._capture_dir(capture_id), ignore_errors=True)

    def cleanup_orphans(self, *, older_than_seconds: int = 24 * 60 * 60) -> dict[str, int]:
        cutoff = time.time() - max(0, older_than_seconds)
        removed_temp = 0
        removed_managed = 0
        if self.temp_root.exists():
            for directory in self.temp_root.iterdir():
                if directory.is_dir() and directory.stat().st_mtime < cutoff:
                    shutil.rmtree(directory, ignore_errors=True)
                    removed_temp += 1
        if self.managed_root.exists():
            for directory in self.managed_root.iterdir():
                if not directory.is_dir():
                    directory.unlink(missing_ok=True)
                    removed_managed += 1
                    continue
                manifest = directory / "manifest.json"
                valid = False
                try:
                    value = json.loads(manifest.read_text(encoding="utf-8"))
                    media_id = str(value["media_id"])
                    image = self.managed_root / media_id
                    valid = image.is_file() and _sha256(image) == value["sha256"]
                except Exception:
                    valid = False
                if not valid:
                    shutil.rmtree(directory, ignore_errors=True)
                    removed_managed += 1
        return {"removed_temp": removed_temp, "removed_managed": removed_managed}


__all__ = ["CaptureMediaError", "StudyCaptureMediaStore"]
