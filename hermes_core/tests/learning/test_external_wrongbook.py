from learning.external_wrongbook import ExternalWrongbookService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningConflictError, LearningStore
from learning.output_writer import OutputWriter
from learning.wrongbook import WrongbookService


def _transcription(capture_id: str = "capture-1", *, question_match: str = "same"):
    return {
        "schema_version": 1,
        "capture_id": capture_id,
        "purpose": "review",
        "question_text": "Solve x + 1 = 3",
        "student_work": "x = 3",
        "lines": [],
        "unreadable_regions": [],
        "confidence_band": "high",
        "question_match": question_match,
        "provider": "quality-provider",
        "model": "quality-model",
    }


def _context(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, "owner")
    context.create_space(title="Course", space_id="space-1")
    return store, context


def test_external_wrongbook_is_idempotent_and_retryable(tmp_path):
    store, context = _context(tmp_path)
    try:
        service = ExternalWrongbookService(context)
        args = {
            "capture_id": "capture-1",
            "media_id": "capture-1/" + "a" * 64 + ".jpg",
            "media_sha256": "a" * 64,
            "transcription": _transcription(),
            "details": {
                "correct_work": "x = 2",
                "knowledge_points": ["inverse operations"],
                "review": {
                    "deviation_start": "the subtraction step",
                    "basis": "1 was not removed from both sides",
                    "uncertain_items": [],
                },
            },
        }
        first = service.activate(**args)
        second = service.activate(**args)
        assert second == first
        assert first["status"] == "active"
        assert len(context.list_items(item_type="external_wrongbook")) == 1
        activities = [
            row
            for row in context.list_activities()
            if row["activity_type"] == "external_wrongbook.confirmed"
        ]
        assert len(activities) == 1

        projection = WrongbookService(context).projection()
        assert projection["count"] == 1
        assert projection["weak_points"] == ["inverse operations"]
        evidence = projection["evidence"][0]
        assert evidence["question_text"] == "Solve x + 1 = 3"
        assert "quality-provider" not in str(projection)
        assert WrongbookService(context).retry_target(evidence["activity_id"]) == {
            "source_kind": "external_wrongbook",
            "capture_id": "capture-1",
            "item_ids": ["external-wrongbook:capture-1"],
            "media_id": args["media_id"],
        }
    finally:
        store.close()


def test_external_and_quiz_wrongbook_are_one_bounded_projection(tmp_path):
    store, context = _context(tmp_path)
    try:
        quiz_id = OutputWriter(context).write_artifact(
            kind="quiz",
            title="Quiz",
            payload={
                "questions": [
                    {
                        "type": "choice",
                        "prompt": "q",
                        "options": ["a", "b"],
                        "answer": 0,
                    }
                ]
            },
        )["artifact_id"]
        context.set_artifact_status(quiz_id, "active")
        quiz_activity = context.record_activity(
            activity_type="quiz.attempt",
            artifact_id=quiz_id,
            detail={
                "score": 0,
                "maxScore": 1,
                "percent": 0,
                "weakTags": ["algebra"],
                "perQuestion": [{"item_id": "q-1", "correct": False}],
            },
        )
        ExternalWrongbookService(context).activate(
            capture_id="capture-1",
            media_id="capture-1/" + "b" * 64 + ".jpg",
            media_sha256="b" * 64,
            transcription=_transcription(),
        )

        projection = WrongbookService(context).projection(limit=1)
        assert projection["count"] == 2
        assert projection["returned"] == 1
        assert projection["truncated"] is True
        assert WrongbookService(context).retry_target(quiz_activity) == {
            "artifact_id": quiz_id,
            "item_ids": ["q-1"],
        }
    finally:
        store.close()


def test_external_wrongbook_rejects_conflicting_replay_and_mismatch(tmp_path):
    store, context = _context(tmp_path)
    try:
        service = ExternalWrongbookService(context)
        base = {
            "capture_id": "capture-1",
            "media_id": "capture-1/" + "c" * 64 + ".jpg",
            "media_sha256": "c" * 64,
            "transcription": _transcription(),
        }
        service.activate(**base)
        try:
            service.activate(
                **{
                    **base,
                    "media_id": "capture-1/" + "d" * 64 + ".jpg",
                    "media_sha256": "d" * 64,
                }
            )
        except LearningConflictError as exc:
            assert str(exc) == "wrongbook_idempotency_conflict"
        else:
            raise AssertionError("conflicting capture replay must fail")

        try:
            service.activate(
                capture_id="capture-other",
                media_id="capture-other/" + "e" * 64 + ".jpg",
                media_sha256="e" * 64,
                transcription=_transcription(
                    "capture-other", question_match="different"
                ),
            )
        except ValueError as exc:
            assert str(exc) == "capture_question_mismatch"
        else:
            raise AssertionError("question mismatch must not become active")
    finally:
        store.close()
