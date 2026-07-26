# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Durable execution adapter for one Tutor start/resume segment."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import time
from typing import Any, Callable
import uuid

from agent.graph_engine.tutor_contracts import (
    TutorGraphStateV1,
    TutorProviderPlanV1,
    TutorProviderRequestV1,
    new_tutor_state,
    validate_tutor_state,
)
from agent.graph_engine.tutor_ports import (
    SingleAttemptTutorProvider,
    TutorGraphRuntimeContext,
    TutorGraphServices,
    TutorProviderBinding,
    TutorProviderError,
    TutorProviderPort,
    TutorProviderResolver,
    estimate_tutor_input_tokens,
)
from learning.checkpoint_store import LearningActivityRecordV1, LearningCheckpointV1
from learning.tutor_contract import (
    LearningActivityKeyV1,
    LearningActivityResumeV1,
    LearningActivityStartV1,
    TutorConflictError,
    TutorContractError,
)
from learning.tutor_runtime_store import (
    MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY,
    MAX_GRAPH_NODES_PER_ACTIVITY,
    MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY,
    MAX_RESERVED_INPUT_TOKENS_PER_ATTEMPT,
    MAX_RESERVED_OUTPUT_TOKENS_PER_ATTEMPT,
    MAX_RESERVED_WALL_MS_PER_ATTEMPT,
    ProviderAttemptReservationV1,
    TutorRuntimeStore,
)


SEGMENT_WALL_MS = 45_000
FINALIZE_RESERVE_MS = 10_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _TutorExecutionBlocked(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class TutorGraphEngine:
    def __init__(self) -> None:
        from agent.graph_engine.tutor_builder import build_tutor_graph

        self._graph = build_tutor_graph()

    def run_segment(
        self, state: TutorGraphStateV1, services: TutorGraphServices
    ) -> TutorGraphStateV1:
        context: TutorGraphRuntimeContext = {"services": services}
        result = self._graph.invoke(
            validate_tutor_state(state),
            {"recursion_limit": 32},
            context=context,
        )
        return validate_tutor_state(result)


class _RuntimeGraphServices:
    """Per-segment graph context backed only by B02 public store methods."""

    def __init__(
        self,
        *,
        store: TutorRuntimeStore,
        key: LearningActivityKeyV1,
        expected_revision: int,
        state: TutorGraphStateV1,
        resolver: TutorProviderResolver,
        provider_factory: Callable[[TutorProviderBinding], TutorProviderPort],
        binding: TutorProviderBinding | None,
        segment_kind: str,
        execution_id: str,
        monotonic: Callable[[], float],
        utc_now: Callable[[], str],
    ) -> None:
        self.store = store
        self.key = key
        self.expected_revision = expected_revision
        self.resolver = resolver
        self.provider_factory = provider_factory
        self.binding = binding
        self.segment_kind = segment_kind
        self.execution_id = execution_id
        self.monotonic = monotonic
        self.utc_now = utc_now
        self.started = monotonic()
        self.base_active_ms = int(state["budget"]["active_elapsed_ms"])
        self.base_nodes = int(state["budget"]["nodes_used"])
        self.last_state = copy.deepcopy(state)

    @property
    def segment_node_cap(self) -> int:
        return 6 if self.segment_kind == "start" else 4

    def _elapsed_ms(self) -> int:
        return max(0, int((self.monotonic() - self.started) * 1_000))

    def _with_elapsed(self, state: TutorGraphStateV1) -> TutorGraphStateV1:
        updated = copy.deepcopy(state)
        elapsed = self.base_active_ms + self._elapsed_ms()
        if elapsed > MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY:
            raise _TutorExecutionBlocked("budget_exhausted")
        updated["budget"] = {**updated["budget"], "active_elapsed_ms": elapsed}
        return validate_tutor_state(updated)

    def _check_nodes(self, state: TutorGraphStateV1) -> None:
        nodes = state["budget"]["nodes_used"]
        if (
            nodes > MAX_GRAPH_NODES_PER_ACTIVITY
            or nodes - self.base_nodes > self.segment_node_cap
        ):
            raise _TutorExecutionBlocked("budget_exhausted")

    @staticmethod
    def _copy_persisted_budget(
        target: TutorGraphStateV1, record: LearningActivityRecordV1
    ) -> None:
        if record.checkpoint is None:
            raise TutorConflictError("checkpoint_missing")
        persisted = record.checkpoint.state.get("budget")
        if not isinstance(persisted, dict):
            raise TutorContractError("checkpoint budget must be an object")
        target["budget"] = copy.deepcopy(persisted)

    def _save_running(self, state: TutorGraphStateV1) -> TutorGraphStateV1:
        updated = self._with_elapsed(state)
        self._check_nodes(updated)
        record = self.store.save(
            LearningCheckpointV1(
                key=self.key,
                revision=self.expected_revision,
                status="running",
                state=updated,
            ),
            expected_revision=self.expected_revision,
        )
        self.expected_revision = record.revision
        self.last_state = copy.deepcopy(record.checkpoint.state)
        return copy.deepcopy(self.last_state)

    def _provider(self, plan: TutorProviderPlanV1) -> TutorProviderPort:
        if self.binding is None:
            self.binding = self.resolver.bind_saved(plan)
        if self.binding.plan.plan_hash != plan.plan_hash:
            raise _TutorExecutionBlocked("provider_unavailable")
        return self.provider_factory(self.binding)

    def _remaining_provider_timeout(self) -> float:
        segment_remaining = SEGMENT_WALL_MS - self._elapsed_ms()
        activity_remaining = (
            MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY
            - self.base_active_ms
            - self._elapsed_ms()
        )
        usable = min(segment_remaining, activity_remaining) - FINALIZE_RESERVE_MS
        if usable <= 0:
            raise _TutorExecutionBlocked("budget_exhausted")
        return min(35.0, usable / 1_000)

    def _persist_failed_node(self, state: TutorGraphStateV1) -> None:
        try:
            self.last_state = self._save_running(state)
        except TutorConflictError:
            raise
        except Exception:
            # The caller will try a terminal commit from the latest durable
            # checkpoint. Never mask the stable provider/budget reason with
            # raw provider data.
            self.last_state = copy.deepcopy(state)

    def generate(self, state: TutorGraphStateV1, *, purpose: str) -> str:
        self.last_state = copy.deepcopy(state)
        self._check_nodes(state)
        if purpose not in {"explain", "remediate"}:
            raise _TutorExecutionBlocked("policy_rejected")
        attempts_used = state["budget"]["attempts_used"]
        if (purpose == "explain" and attempts_used != 0) or (
            purpose == "remediate" and attempts_used != 1
        ):
            self._persist_failed_node(state)
            raise _TutorExecutionBlocked("provider_attempt_exhausted")
        plan = TutorProviderPlanV1.from_checkpoint_dict(state["provider_plan"])
        previous = state.get("latest_output", {}).get("markdown")
        request = TutorProviderRequestV1(
            purpose=purpose,
            goal=state["goal"],
            input_refs=tuple(copy.deepcopy(state["input_refs"])),
            previous_output=previous if purpose == "remediate" else None,
        )
        input_reserve = estimate_tutor_input_tokens(request)
        if input_reserve > MAX_RESERVED_INPUT_TOKENS_PER_ATTEMPT:
            self._persist_failed_node(state)
            raise _TutorExecutionBlocked("budget_exhausted")
        timeout_s = self._remaining_provider_timeout()
        reservation = ProviderAttemptReservationV1(
            attempt_id=f"tatt_{uuid.uuid4().hex}",
            segment_id=f"tseg_{self.execution_id}",
            ordinal=attempts_used + 1,
            provider_id=plan.provider_id,
            model_id=plan.model_id,
            api_mode=plan.api_mode,
            reserved_input_tokens=input_reserve,
            reserved_output_tokens=MAX_RESERVED_OUTPUT_TOKENS_PER_ATTEMPT,
            reserved_wall_ms=MAX_RESERVED_WALL_MS_PER_ATTEMPT,
        )
        try:
            record = self.store.reserve_provider_attempt(
                self.key,
                expected_revision=self.expected_revision,
                reservation=reservation,
            )
        except TutorConflictError as exc:
            self._persist_failed_node(state)
            if exc.reason_code in {"provider_attempt_exhausted", "budget_exhausted"}:
                raise _TutorExecutionBlocked(exc.reason_code) from exc
            raise
        self.expected_revision = record.revision
        self._copy_persisted_budget(state, record)
        self.last_state = copy.deepcopy(state)

        try:
            result = self._provider(plan).execute_once(
                reservation, request, timeout_s=timeout_s
            )
        except TutorProviderError as exc:
            latency_ms = min(
                reservation.reserved_wall_ms,
                max(0, self._elapsed_ms()),
            )
            settled = self.store.settle_provider_attempt(
                self.key,
                attempt_id=reservation.attempt_id,
                expected_revision=self.expected_revision,
                status="failed",
                actual_latency_ms=latency_ms,
                reason_code=exc.reason_code,
            )
            self.expected_revision = settled.revision
            self._copy_persisted_budget(state, settled)
            self._persist_failed_node(state)
            raise
        settled = self.store.settle_provider_attempt(
            self.key,
            attempt_id=reservation.attempt_id,
            expected_revision=self.expected_revision,
            status="succeeded",
            actual_input_tokens=result.actual_input_tokens,
            actual_output_tokens=result.actual_output_tokens,
            actual_latency_ms=result.actual_latency_ms,
        )
        self.expected_revision = settled.revision
        self._copy_persisted_budget(state, settled)
        self.last_state = copy.deepcopy(state)
        return result.markdown

    def _interrupt(self, state: TutorGraphStateV1) -> dict[str, Any]:
        options = [
            {"id": "continue", "label": "Continue"},
        ]
        if state["branch"] == "check_1":
            options.append({"id": "explain_again", "label": "Explain again"})
        identity = state["identity"]
        return {
            "schema_version": 1,
            "interrupt_id": f"lint_{uuid.uuid4().hex}",
            "kind": "learner_check",
            "owner_id": identity["owner_id"],
            "space_id": identity["space_id"],
            "activity_kind": identity["activity_kind"],
            "activity_id": identity["activity_id"],
            "checkpoint_revision": self.expected_revision + 1,
            "prompt": {
                "schema_version": 1,
                "template": state["branch"],
                "message": "Continue, or request one more explanation.",
                "options": options,
            },
            "expected_input": "choice",
            "created_at": self.utc_now(),
        }

    def after_node(
        self, node_name: str, state: TutorGraphStateV1
    ) -> TutorGraphStateV1:
        self._check_nodes(state)
        if node_name == "learner_control_check":
            updated = self._with_elapsed(state)
            updated["pending_interrupt"] = self._interrupt(updated)
            record = self.store.save(
                LearningCheckpointV1(
                    key=self.key,
                    revision=self.expected_revision,
                    status="waiting_for_learner",
                    state=updated,
                ),
                expected_revision=self.expected_revision,
            )
            self.expected_revision = record.revision
            self.last_state = copy.deepcopy(record.checkpoint.state)
            return copy.deepcopy(self.last_state)
        if node_name == "complete":
            updated = self._with_elapsed(state)
            self.store.commit_terminal(
                self.key,
                expected_revision=self.expected_revision,
                outcome="completed",
                terminal_code="completed",
                completion_basis="participation_only",
                remediation_count=updated["remediation_count"],
                budget_summary=updated["budget"],
            )
            self.expected_revision += 1
            self.last_state = copy.deepcopy(updated)
            return updated
        return self._save_running(state)

    def block(self, reason_code: str) -> LearningActivityRecordV1:
        source = self.store.load_projection_source(self.key)
        if source is None:
            raise TutorConflictError("activity_not_found")
        record, _run = source
        if record.status in {"completed", "blocked", "cancelled"}:
            return record
        if record.checkpoint is None:
            raise TutorConflictError("checkpoint_missing")
        state = copy.deepcopy(record.checkpoint.state)
        try:
            state = self._with_elapsed(state)
            saved = self.store.save(
                LearningCheckpointV1(
                    key=self.key,
                    revision=record.revision,
                    status="running",
                    state=state,
                ),
                expected_revision=record.revision,
            )
            record = saved
            state = copy.deepcopy(saved.checkpoint.state)
        except _TutorExecutionBlocked:
            # Clamp only the active counter at its frozen cap; other counters
            # remain the durable store truth.
            state["budget"]["active_elapsed_ms"] = MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY
        return self.store.commit_terminal(
            self.key,
            expected_revision=record.revision,
            outcome="blocked",
            terminal_code=reason_code,
            completion_basis=None,
            remediation_count=int(state.get("remediation_count", 0)),
            budget_summary=state["budget"],
        )


class TutorActivityExecutor:
    """Create/claim/run adapter consumed by ``TutorActivityService``."""

    def __init__(
        self,
        store: TutorRuntimeStore,
        *,
        resolver: TutorProviderResolver | None = None,
        graph: TutorGraphEngine | None = None,
        provider_factory: Callable[[TutorProviderBinding], TutorProviderPort] = (
            SingleAttemptTutorProvider
        ),
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], str] = _utc_now,
    ) -> None:
        self.store = store
        self.resolver = resolver or TutorProviderResolver()
        self.graph = graph or TutorGraphEngine()
        self.provider_factory = provider_factory
        self.monotonic = monotonic
        self.utc_now = utc_now

    def _run(
        self,
        record: LearningActivityRecordV1,
        *,
        segment_kind: str,
        execution_id: str,
        binding: TutorProviderBinding | None = None,
    ) -> LearningActivityRecordV1:
        if record.checkpoint is None:
            raise TutorConflictError("checkpoint_missing")
        services = _RuntimeGraphServices(
            store=self.store,
            key=record.key,
            expected_revision=record.revision,
            state=validate_tutor_state(record.checkpoint.state),
            resolver=self.resolver,
            provider_factory=self.provider_factory,
            binding=binding,
            segment_kind=segment_kind,
            execution_id=execution_id,
            monotonic=self.monotonic,
            utc_now=self.utc_now,
        )
        try:
            self.graph.run_segment(record.checkpoint.state, services)
        except _TutorExecutionBlocked as exc:
            return services.block(exc.reason_code)
        except TutorProviderError as exc:
            return services.block(exc.reason_code)
        except TutorConflictError as exc:
            if exc.reason_code in {"provider_attempt_exhausted", "budget_exhausted"}:
                return services.block(exc.reason_code)
            raise
        except TutorContractError as exc:
            reason = getattr(exc, "reason_code", "internal_error")
            if reason not in {"checkpoint_too_large", "invalid_model_output"}:
                reason = "internal_error"
            return services.block(reason)
        except Exception:
            return services.block("internal_error")
        loaded = self.store.load(record.key)
        if loaded is None:
            raise TutorConflictError("activity_not_found")
        return loaded

    def start(self, request: LearningActivityStartV1) -> LearningActivityRecordV1:
        if request.key.activity_kind != "tutor":
            raise TutorContractError("B03 only executes activity_kind=tutor")
        binding = self.resolver.resolve_current()
        state = new_tutor_state(
            request.key,
            goal=request.goal,
            input_refs=request.input_refs,
            provider_plan=binding.plan,
        )
        record, created = self.store.create(
            request,
            LearningCheckpointV1(
                key=request.key,
                revision=0,
                status="created",
                state=state,
            ),
            provider_plan_hash=binding.plan.plan_hash,
        )
        if not created:
            return record
        execution_id = f"texec_{uuid.uuid4().hex}"
        claimed = self.store.claim_execution(
            request.key,
            expected_revision=record.revision,
            execution_id=execution_id,
        )
        return self._run(
            claimed,
            segment_kind="start",
            execution_id=execution_id,
            binding=binding,
        )

    def resume(
        self, key: LearningActivityKeyV1, request: LearningActivityResumeV1
    ) -> LearningActivityRecordV1:
        existing = self.store.load(key)
        if existing is None:
            raise TutorConflictError("activity_not_found")
        if existing.checkpoint is not None:
            # Fail closed before claiming execution. An unknown/future graph
            # checkpoint must not be left in a synthetic running state.
            validate_tutor_state(existing.checkpoint.state)
        execution_id = f"texec_{uuid.uuid4().hex}"
        if request.mode == "answer":
            claimed = self.store.claim_answer(
                key,
                expected_revision=request.expected_revision,
                execution_id=execution_id,
                interrupt_id=request.interrupt_id,
                answer=request.answer,
            )
        else:
            claimed = self.store.claim_execution(
                key,
                expected_revision=request.expected_revision,
                execution_id=execution_id,
            )
        return self._run(
            claimed,
            segment_kind="resume",
            execution_id=execution_id,
        )


__all__ = ["TutorActivityExecutor", "TutorGraphEngine"]
