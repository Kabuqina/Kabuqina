# STUDY M3 Quiz Slice Design

**Date:** 2026-07-04

**Status:** Approved for implementation

**Scope:** STUDY M3 only: quiz artifact lifecycle, deterministic quiz practice, legacy quiz migration, and the Web quiz surface. Gateway `/study` commands remain M5.

## Context

M1 already established the shared learning contract, including the `quiz` discriminated union. M2 closed the first user-facing slice with course spaces, `flashcard_deck` drafts, trusted activation/rejection, real practice activities, legacy flashcard migration, Tauri `cmd_study_*` proxies, and `learning.output.created` refresh events.

The current quiz UI still uses the old path: the model emits JSON, the student pastes it into the panel, the browser stores it in `localStorage`, and grading happens only in `quizStore.ts`. M3 moves quiz into the same durable learning pipeline as flashcards.

## Options Considered

1. **Recommended: deterministic quiz practice first.** Persist quiz artifacts, activate/reject through trusted APIs, materialize questions into `learning_items`, and grade attempts deterministically from stored answers. Short answers match the stored `answer` or `accepted` strings after normalization. This is reliable, testable, and keeps M3 bounded.
2. **LLM-assisted short-answer grading in M3.** This would feel richer, but it adds latency, budgets, reviewer/prompt failure modes, and ambiguity before the quality gate work exists.
3. **Keep quiz localStorage until the lifecycle UI milestone.** This avoids code now but fails the M3 acceptance criterion and keeps the copy/paste workflow alive.

M3 uses option 1. Semantic grading and reviewer-quality gates stay out of scope.

## Design

### Core

Add `hermes_core/learning/quizzes.py` with `QuizService`. It is the trusted practice layer for active `quiz` artifacts:

- `activate_quiz(artifact_id)` changes a draft quiz to `active` and materializes each question into a `learning_items` row with `item_type="quiz_question"`.
- `reject_quiz(artifact_id)` rejects a draft without materializing questions.
- `list_quizzes(status=None)` returns quiz artifacts.
- `list_questions(artifact_id=None)` returns materialized question rows without exposing answers to normal answering views unless the caller asks for a result/answer payload.
- `submit_attempt(artifact_id, responses)` grades one attempt, records a `quiz.attempt` activity, and returns score, per-question correctness, explanations, weak tags, and normalized responses.

The service keeps grading deterministic. Choice questions compare selected option indexes exactly. `true_false` compares booleans. `short_answer` compares normalized text against `answer` and `accepted`.

### Desk API

Extend `python/src/desk_server/routes/study_routes.py` instead of creating a second router. This keeps the trusted STUDY API surface grouped:

- `GET /api/desk/study/quizzes`
- `GET /api/desk/study/quizzes/{artifact_id}/questions`
- `POST /api/desk/study/quizzes/{artifact_id}/submit`
- `POST /api/desk/study/migrations/quizzes`

Existing generic draft, activate, and reject endpoints are extended to route `quiz` artifacts to `QuizService`. Legacy quiz migration uses migration key `localStorage:kabuqina.study.quiz.v1`, creates or uses the current/default course space, writes a `quiz` artifact, activates it, records the migration, and is idempotent.

### Tauri And Web API

Extend `tauri/src/study.rs` with thin commands:

- `cmd_study_quizzes`
- `cmd_study_quiz_questions`
- `cmd_study_quiz_submit`
- `cmd_study_migrate_quizzes`

Extend `web/src/chat/study/study-api.ts` with typed wrappers and quiz response types. Keep command payloads minimal and path ids validated by the existing `validate_study_path_id`.

### Web Quiz Panel

Replace the primary localStorage/paste flow with the durable backend flow:

- Load/create/select course space through the shared STUDY API.
- Display draft `quiz` artifacts with activate/reject controls.
- Display active quizzes, start a quiz, collect responses, submit through backend, and render returned results.
- Listen for `study-learning-event` and refresh when a `learning.output.created` event arrives.
- Run one-time legacy `kabuqina.study.quiz.v1` migration from localStorage; keep old quizStore read-only as fallback for migration and result formatting helpers during this release.

The prompt changes from "paste a JSON code block" to "use the STUDY learning tools to create a `kind=quiz` draft".

## Data Shape

Core contract quiz payload remains:

```json
{
  "questions": [
    {
      "type": "choice",
      "prompt": "Question",
      "options": ["A", "B"],
      "answer": 0,
      "explanation": "Optional",
      "tags": ["topic"]
    },
    {
      "type": "true_false",
      "prompt": "Statement",
      "answer": true
    },
    {
      "type": "short_answer",
      "prompt": "Name the concept",
      "answer": "gradient descent",
      "accepted": ["gradient descent", "GD"]
    }
  ]
}
```

Legacy web quiz types map as:

- `single` -> `choice` with scalar `answer`
- `multiple` -> `choice` with array `answer`
- `short` -> `short_answer` with `accepted`

## Error Handling

All trusted routes keep the M2 mapping: `ValueError` -> 400, `KeyError` -> 404, `ContractError` -> 409. Invalid submitted responses are normalized conservatively and graded as incorrect rather than crashing. Attempts against missing, rejected, or non-quiz artifacts fail.

## Testing

TDD coverage:

- Core quiz activation, rejection, deterministic grading, activity write, and owner/space scoping through existing store helpers.
- Desk API quiz activation/rejection, question listing, submission, and idempotent legacy migration.
- Web pure mapper tests for legacy migration payloads, backend question mapping, submit payloads, and result summary formatting.
- Rust command validation/registration via `cargo test study`.
- Final M3 gate: `hermes_core` learning tests, desk STUDY tests, web quiz mapper/store tests, `npm run build`, `cargo test study`, and `git diff --check`.

