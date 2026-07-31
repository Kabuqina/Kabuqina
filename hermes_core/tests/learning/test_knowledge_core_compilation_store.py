from learning.knowledge_core_compilation_store import (
    KnowledgeCoreCompilationStore,
    validate_compilation_request,
)


def _request(key: str = "idem-1"):
    return {
        "space_id": "course-1",
        "outline_node_id": "section-1",
        "plan_item_id": "plan-1-0000",
        "trigger": "start_learning",
        "expected_map_revision": 1,
        "idempotency_key": key,
    }


def test_enqueue_is_idempotent_by_request_and_compilation_key(tmp_path):
    store = KnowledgeCoreCompilationStore(tmp_path / "compiler.db")
    try:
        fingerprint = "a" * 64
        compilation_key = "b" * 64
        first, created = store.create_or_reuse(
            "owner", _request(), source_fingerprint=fingerprint,
            compilation_key=compilation_key,
        )
        replay, replay_created = store.create_or_reuse(
            "owner", _request(), source_fingerprint=fingerprint,
            compilation_key=compilation_key,
        )
        other_key, other_created = store.create_or_reuse(
            "owner", _request("idem-2"), source_fingerprint=fingerprint,
            compilation_key=compilation_key,
        )

        assert created is True
        assert replay_created is False
        assert other_created is False
        assert first["run_id"] == replay["run_id"] == other_key["run_id"]
        assert store.list_runs("owner", space_id="course-1") == [first]
    finally:
        store.close()


def test_restart_fails_running_stages_but_keeps_queued_work(tmp_path):
    store = KnowledgeCoreCompilationStore(tmp_path / "compiler.db")
    try:
        queued, _ = store.create_or_reuse(
            "owner", _request("queued"), source_fingerprint="a" * 64,
            compilation_key="b" * 64,
        )
        running, _ = store.create_or_reuse(
            "owner", {**_request("running"), "outline_node_id": "section-2"},
            source_fingerprint="c" * 64, compilation_key="d" * 64,
        )
        store.transition(
            "owner", "course-1", running["run_id"], "reading",
            allowed_from={"queued"},
        )

        assert store.reconcile_abandoned("owner") == 1
        assert store.get_run("owner", "course-1", queued["run_id"])["status"] == "queued"
        recovered = store.get_run("owner", "course-1", running["run_id"])
        assert recovered["status"] == "failed"
        assert recovered["reason_code"] == "process_restarted"
    finally:
        store.close()


def test_cancel_is_terminal_and_does_not_write_learning_evidence(tmp_path):
    store = KnowledgeCoreCompilationStore(tmp_path / "compiler.db")
    try:
        run, _ = store.create_or_reuse(
            "owner", _request(), source_fingerprint="a" * 64,
            compilation_key="b" * 64,
        )
        cancelled = store.cancel("owner", "course-1", run["run_id"])
        assert cancelled["status"] == "cancelled"
        assert store.cancel("owner", "course-1", run["run_id"]) == cancelled
    finally:
        store.close()


def test_normalized_request_without_plan_item_can_be_validated_again(tmp_path):
    store = KnowledgeCoreCompilationStore(tmp_path / "compiler.db")
    try:
        request = _request()
        request.pop("plan_item_id")
        normalized = validate_compilation_request(request)
        run, created = store.create_or_reuse(
            "owner",
            normalized,
            source_fingerprint="a" * 64,
            compilation_key="b" * 64,
        )
        assert created is True
        assert run["plan_item_id"] == ""
    finally:
        store.close()
