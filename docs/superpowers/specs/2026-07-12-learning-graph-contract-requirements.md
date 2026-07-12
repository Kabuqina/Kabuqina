# Learning Graph Contracts：LG1 / LG2 / H2

> **Status:** requirements-only contract review (2026-07-12, G2 opened)
>
> **Scope:** Define v0.5.0 tutor-loop interface shapes and invariants. This
> document authorizes **no** graph-engine, checkpoint, interrupt, or legacy-loop
> implementation work in v0.4.0.

## Decision

The tutoring runtime will be a distinct structured activity, not an inference
layer over ordinary chat. Its durable boundary is a learning space; its pause
boundary is a learner check; and its successful explanation boundary is an
explicit handoff to the learner. Normal chat remains a normal agent turn.

These contracts supplement
[learning-runtime alignment](../../learning-runtime-alignment.md). They do not
change the existing `graph` agent engine or its currently released persistence
format.

## LG1 — checkpoint identity is owner + learning space

### Required request shape

```text
LearningActivityRequest {
  owner_id: string
  space_id: string
  activity_kind: "tutor" | "review" | "practice"
  activity_id?: opaque string
  resume?: boolean
}
```

`owner_id` and `space_id` are required. `chat_session_id`, gateway chat id, and
browser tab id are never checkpoint keys. `activity_kind` keeps separately
structured activities inside one space from colliding; ordinary chat supplies
none of these fields and therefore never acquires a learning checkpoint.

### Required persistence port

```text
LearningCheckpointStore.load(key) -> Checkpoint | None
LearningCheckpointStore.save(key, checkpoint, expected_revision) -> Checkpoint
LearningCheckpointStore.clear(key, expected_revision) -> None
```

The concrete key is opaque outside the store, but it must be deterministically
derived from `owner_id`, `space_id`, `activity_kind`, and an optional explicit
`activity_id`. Store implementations must reject a key whose owner or space is
not authorized for the request. The revision is mandatory optimistic
concurrency: a stale browser or resumed child must not overwrite a newer
learner turn.

### Invariants

- A completed or cancelled activity can be reopened only by an explicit new
  activity request; no background cron wake resumes it.
- A checkpoint may contain graph state needed for the structured activity, but
  must not become a second learning database. Durable student state, plans,
  evaluations, and evidence remain in `learning.db` through their existing
  services.
- Checkpoint retention and deletion follow the owner/space lifecycle. A space
  deletion clears its checkpoints; one owner cannot enumerate another owner's
  checkpoint presence.
- Checkpoint serialization must not include API keys, tool credentials, raw
  source documents, or gateway identifiers.

## LG2 — learner checks are first-class interrupts

### Required interrupt shape

```text
LearningInterrupt {
  interrupt_id: opaque string
  kind: "learner_check"
  owner_id: string
  space_id: string
  activity_id: opaque string
  checkpoint_revision: integer
  prompt: structured learner-facing check
  expected_input: "free_text" | "choice" | "step"
  created_at: ISO-8601 timestamp
}
```

This is not a tool-approval interrupt. It neither grants a side effect nor
shares approval ids, approval UI, or approval timeout semantics. A learner
answer resumes only the matching owner, space, activity, interrupt id, and
checkpoint revision. A duplicate, stale, cross-space, or cross-owner answer is
rejected without advancing the graph.

### Lifecycle contract

```text
explain small unit → emit learner_check interrupt → persist checkpoint
→ learner answer → validate binding/revision → resume exactly once
```

At most one unresolved learner-check interrupt exists for one activity. A
disconnect leaves that interrupt pending; it does not cause an automatic model
turn, delivery, or retry. An explicit abandon/cancel operation resolves it as
cancelled and makes later answers invalid.

## H2 — teaching stop condition is structural

The tutoring graph requires a `handoff_to_learner` edge. An explanation node
may end only by either:

1. emitting a valid `learner_check` interrupt after one bounded concept unit; or
2. returning a terminal structured outcome (`completed`, `cancelled`, or
   `blocked`) with a user-visible reason.

It may not continue freely because a model considers its answer complete. The
edge is the runtime form of “explain one idea, then ask a check question.” A
future policy function may decide whether a learner answer advances, remediates,
or asks for a hint, but the function must be deterministic for a supplied
evaluation/weak-point projection and record its chosen branch in checkpoint
metadata.

### Non-goals and compatibility

- No H2 behavior is added to `_run_conversation_loop`; the legacy loop stays
  untouched until Task 11 Step 5.
- No generic chat turn is converted into a tutor activity by intent detection.
  The user explicitly chooses a structured activity.
- LG3/LG4/H4 implementation remains v0.5.0 tutor-loop work. This document
  defines only enough shape to keep their future interfaces compatible.
- Any later implementation must add graph-engine contract tests under
  `hermes_core/tests/` and record a decision before changing persistence.
