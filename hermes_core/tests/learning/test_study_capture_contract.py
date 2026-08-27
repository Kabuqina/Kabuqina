from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from learning.study_capture import (
    StudyCaptureService,
    StudyQuestionMismatch,
    StudyReasoningContractInvalid,
    StudyReasoningService,
    StudyVisionContractInvalid,
)
from learning.study_capture_contract import (
    StudyCaptureContractError,
    validate_capture_session,
    validate_capture_transform,
    validate_study_assistance,
    validate_study_review_draft,
    validate_study_transcription,
)


def transcription(**overrides):
    value = {
        "schema_version": 1,
        "capture_id": "capture-1",
        "purpose": "stuck",
        "question_text": "Solve x + 1 = 3",
        "student_work": "x = 3 - 1",
        "lines": [
            {
                "line_no": 1,
                "text": "x = 3 - 1",
                "region": {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.1},
                "annotations": [],
            }
        ],
        "unreadable_regions": [],
        "confidence_band": "high",
        "question_match": "same",
        "provider": "fake",
        "model": "fake-v1",
    }
    value.update(overrides)
    return value


def test_capture_session_and_transform_are_exact():
    session = {
        "schema_version": 1,
        "capture_id": "capture-1",
        "space_id": "course-1",
        "purpose": "review",
        "source_kind": "camera",
        "status": "temporary",
        "revision": 1,
        "preview": {"width": 1280, "height": 960},
    }
    assert validate_capture_session(session) == session
    with pytest.raises(StudyCaptureContractError):
        validate_capture_session({**session, "managed_path": "C:/private.jpg"})

    transform = {
        "schema_version": 1,
        "capture_id": "capture-1",
        "expected_revision": 1,
        "crop": {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.6},
        "rotation": 90,
        "grayscale": False,
        "max_edge": 1280,
    }
    assert validate_capture_transform(transform) == transform
    with pytest.raises(StudyCaptureContractError):
        validate_capture_transform(
            {**transform, "crop": {"x": 0.8, "y": 0.2, "width": 0.7, "height": 0.6}}
        )


def test_transcription_rejects_unknown_fields_and_unordered_lines():
    with pytest.raises(StudyCaptureContractError):
        validate_study_transcription({**transcription(), "score": 0.99})
    second = dict(transcription()["lines"][0], line_no=2)
    first = dict(transcription()["lines"][0], line_no=1)
    with pytest.raises(StudyCaptureContractError):
        validate_study_transcription(transcription(lines=[second, first]))


def test_critical_unreadable_region_cannot_claim_high_confidence():
    unreadable = [
        {
            "region": {"x": 0.4, "y": 0.4, "width": 0.2, "height": 0.1},
            "reason": "denominator is obscured",
            "critical": True,
        }
    ]
    with pytest.raises(StudyCaptureContractError):
        validate_study_transcription(
            transcription(unreadable_regions=unreadable, confidence_band="high")
        )
    value = validate_study_transcription(
        transcription(unreadable_regions=unreadable, confidence_band="low")
    )
    assert value["unreadable_regions"][0]["critical"] is True


def test_service_pins_capture_identity_and_actual_provider():
    class FakeVision:
        provider = "trusted-provider"
        model = "trusted-model"

        async def transcribe(self, _path: Path, **_kwargs):
            return transcription(
                capture_id="provider-invented",
                purpose="review",
                provider="provider-invented",
                model="provider-invented",
            )

    value = asyncio.run(
        StudyCaptureService(FakeVision()).transcribe(
            Path("unused.jpg"), capture_id="capture-1", purpose="stuck"
        )
    )
    assert value["capture_id"] == "capture-1"
    assert value["purpose"] == "stuck"
    assert value["provider"] == "trusted-provider"
    assert value["model"] == "trusted-model"


def test_service_fails_closed_on_malformed_provider_contract():
    class FakeVision:
        provider = "fake"
        model = "fake-v1"

        async def transcribe(self, _path: Path, **_kwargs):
            return {"schema_version": 1, "analysis": "probably x = 2"}

    with pytest.raises(StudyVisionContractInvalid):
        asyncio.run(
            StudyCaptureService(FakeVision()).transcribe(
                Path("unused.jpg"), capture_id="capture-1", purpose="stuck"
            )
        )


def test_assistance_and_review_contracts_are_mode_exact():
    assert validate_study_assistance(
        {"mode": "next_step", "hint": "Subtract 1 from both sides."}
    )["mode"] == "next_step"
    with pytest.raises(StudyCaptureContractError):
        validate_study_assistance(
            {
                "mode": "next_step",
                "hint": "Subtract 1.",
                "answer": "x = 2",
            }
        )
    assert validate_study_review_draft(
        {
            "deviation_start": "x = 3",
            "basis": "the left side still contains +1",
            "uncertain_items": [],
        }
    )["uncertain_items"] == []


def test_reasoning_uses_only_transcription_and_blocks_question_mismatch():
    class FakeReasoning:
        def __init__(self):
            self.calls = []

        async def generate(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs["kind"] == "review":
                return {
                    "deviation_start": "x = 3",
                    "basis": "1 was not subtracted",
                    "uncertain_items": [],
                }
            if kwargs["mode"] == "full_answer":
                return {
                    "mode": "full_answer",
                    "answer": "x = 2",
                    "knowledge_points": ["inverse operations"],
                    "skipped_items": [],
                }
            return {"mode": "next_step", "hint": "Subtract 1 from both sides."}

    port = FakeReasoning()
    service = StudyReasoningService(port)
    hint = asyncio.run(service.assistance(transcription()))
    answer = asyncio.run(service.assistance(transcription(), mode="full_answer"))
    review = asyncio.run(service.review(transcription()))
    assert set(hint) == {"mode", "hint"}
    assert answer["mode"] == "full_answer"
    assert review["deviation_start"] == "x = 3"
    assert all("image" not in str(call).casefold() for call in port.calls)
    with pytest.raises(StudyQuestionMismatch):
        asyncio.run(
            service.assistance(transcription(question_match="different"))
        )


def test_critical_unreadable_work_must_remain_explicit_in_reasoning():
    critical = [
        {
            "region": {"x": 0.4, "y": 0.4, "width": 0.2, "height": 0.1},
            "reason": "line is covered",
            "critical": True,
        }
    ]

    class UnsafeReasoning:
        async def generate(self, *, kind, **_kwargs):
            if kind == "review":
                return {
                    "deviation_start": "line 1",
                    "basis": "guessed",
                    "uncertain_items": [],
                }
            return {
                "mode": "full_answer",
                "answer": "x = 2",
                "knowledge_points": [],
                "skipped_items": [],
            }

    service = StudyReasoningService(UnsafeReasoning())
    low = transcription(unreadable_regions=critical, confidence_band="low")
    with pytest.raises(StudyReasoningContractInvalid):
        asyncio.run(service.review(low))
    with pytest.raises(StudyReasoningContractInvalid):
        asyncio.run(service.assistance(low, mode="full_answer"))
