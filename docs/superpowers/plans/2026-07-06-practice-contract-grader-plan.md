# Practice Contract + Sandbox Grader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implement the v0.4.0 backend half of
[数学与代码练习系统](../specs/2026-07-05-study-math-code-practice-design.md)
§4/§5 — extend the `quiz` discriminated union with `code` and `derivation`
question types, and build the sandboxed deterministic grader. **Backend +
contract + tests only**; the practice UI (临摹/变式 panels, CodeMirror) is
slice B-3.

**Slice id:** B-2 of the
[v0.4.0 development plan](2026-07-06-v0.4.0-development-plan.md). Runs in
parallel with B-1 (different file surfaces).

**Tech Stack:** Python 3.11, subprocess sandboxing, pytest TDD.

## Progress Notes

**2026-07-10 — security review pause (Tasks 1-2 complete).** Contract tests
cover valid/invalid `code` and `derivation` members, including the 50-step and
20k-character limits, zero-based cloze indices, `expr_py` fallback shape, and
honest non-Python acceptance for later `gradable: false` materialization. The
standalone grader passes adversarial tests for isolated/minimal env, Unicode,
pass/fail/error, timeout, Windows process-tree kill, 64KB stream truncation,
temp cleanup, deterministic numeric equivalence, false equivalence, and
all-domain-error fallback. The test suite also demonstrates (rather than
hiding) that an absolute path remains readable under the current user.

Task 3 has not started. Owner sign-off is pending on the documented residual
risks: unrestricted network egress, current-user absolute-path access, process
creation before tree kill, and memory exhaustion before timeout. Public result
shape exposes only bounded pass/fail metadata and a ≤240-character sanitized
exception summary; stdout is never returned.

---

## Guardrails

- **Soak discipline: zero engine changes.** Everything lives in
  `hermes_core/learning/**` + contract + routes.
- **Trust boundary:** the grader is a trusted core service invoked by
  QuizService.submit paths. Model tools gain NO grading or execution
  capability; a model-authored quiz draft still requires user activation
  before any of its code can ever be executed by grading.
- **Never execute draft content.** Grading runs only against `active`
  quiz items (existing `submit_attempt` already enforces active status —
  keep that the single entry point).
- **Honesty rule:** release notes and docstrings must NOT claim full
  isolation — network egress is a documented residual risk (§ Task 2).
- Inherit M3 semantics untouched: questions are artifacts, attempts are
  activities, regeneration never rewrites history.
- Commit locally per task; do NOT push; stop for review at plan end.
- **This slice requires a security review pause:** after Task 2, STOP and
  present the threat-model checklist to the owner before wiring the grader
  into QuizService (Task 3).

---

### Task 1: Contract extension (`code` + `derivation` question types)

**Files:**
- Modify: `hermes_core/learning/learning_contract.py`
- Modify: `hermes_core/tests/learning/test_learning_contract.py`

- [ ] **Step 1: failing schema tests** for the two new members of the quiz
  question discriminated union:

```json
{
  "type": "code",
  "prompt": "实现 sigmoid",
  "language": "python",
  "mode": "solve | transcribe | variant",
  "starter": "def sigmoid(x):\n    ...",
  "target_code": "(mode=transcribe: the code to transcribe)",
  "test_code": "assert abs(sigmoid(0) - 0.5) < 1e-9",
  "reference": "(never sent to the frontend)",
  "variant_of": "(optional item ref)",
  "tags": ["激活函数"]
}
```

```json
{
  "type": "derivation",
  "prompt": "从定义推出方差展开式",
  "steps": [
    {"expr": "\\operatorname{Var}(X)=E[(X-E[X])^2]",
     "expr_py": "E_x2 - 2*mu*mu + mu*mu",
     "justification": "定义"}
  ],
  "cloze": [1],
  "check": "numeric-equivalence | normalized-match",
  "tags": ["方差"]
}
```

  Contract decisions locked here:
  - `language`: v1 accepts `"python"` only (grader scope); other languages
    validate but are marked `gradable: false` — no fake grading.
  - `derivation` steps carry display LaTeX (`expr`) and OPTIONAL
    `expr_py` (python-evaluable form). Numeric-equivalence grading requires
    `expr_py`; without it the step falls back to `normalized-match`
    (whitespace/case-normalized string compare). **Do not attempt LaTeX
    parsing** — that is the sympy load-package upgrade path, out of scope.
  - `justification` cloze steps grade like `short_answer` (via `accepted`
    list) when provided, else the step is recorded `ungraded` (partial
    scoring: graded steps only).
  - Size caps: `test_code`/`reference`/`starter` ≤ 20_000 chars each and
    count toward `MAX_ENVELOPE_BYTES`; ≤ 50 steps; existing quiz caps apply.
- [ ] **Step 2:** implement validators; valid/invalid samples for every rule.
- [ ] **Step 3: gate**

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_contract.py -o "addopts=" -p no:cacheprovider -q
```

### Task 2: Sandbox runner (security-critical, standalone module)

**Files:**
- Add: `hermes_core/learning/code_grader.py`
- Add: `hermes_core/tests/learning/test_code_grader.py`

- [ ] **Step 1: threat model paragraph in the module docstring** — who
  authors what runs (learner code + user-activated model code), what the
  sandbox does and does NOT protect against.
- [ ] **Step 2: implement `run_python_grading(source, test_code, *, timeout_s=5)`**:
  - executes `sys.executable -I` (isolated: no site, no env inheritance —
    pass a minimal env whitelist) in a fresh temp dir; the temp dir is the
    CWD and is deleted afterward;
  - hard timeout (default 5s, contract-tunable cap 30s) → kill the process
    **tree** (Windows: `CREATE_NEW_PROCESS_GROUP` + `taskkill /T /F`
    fallback);
  - stdout+stderr each truncated to 64KB;
  - result: `{"passed": bool, "failure_summary": str, "timed_out": bool,
    "truncated": bool}` — **raw output is summarized, never fed verbatim
    into model context** (prompt-injection guard);
  - `CREATE_NO_WINDOW` on Windows; non-zero exit or assertion failure =
    not passed with the first assertion/traceback line as summary.
  - **Documented residual risk:** no network egress blocking in v1
    (Windows lacks a per-process primitive). Roadmap note only.
- [ ] **Step 3: implement `check_numeric_equivalence(expr_py_a, expr_py_b,
  variables, *, samples=8)`** — runs INSIDE the same sandbox (one grading
  subprocess evaluates both expressions at shared random sample points with
  seeded RNG for determinism); relative tolerance 1e-9; domain errors at a
  sample point skip that point, all-points-skipped → not equivalent +
  `needs_human_check` flag.
- [ ] **Step 4: adversarial tests** — infinite loop (timeout kill),
  fork-bomb-ish spawn (tree kill), gigantic stdout (truncation), attempts to
  read outside temp cwd (no crash; document behavior), unicode source,
  passing/failing/erroring test_code, equivalence true/false/domain-error
  cases, determinism across runs.
- [ ] **Step 5: STOP — security review.** Present the checklist (threat
  model, kill semantics, env whitelist, output handling, residual risks)
  to the owner. Do not proceed to Task 3 without sign-off.

### Task 3: QuizService grading dispatch

**Files:**
- Modify: `hermes_core/learning/quizzes.py`
- Modify: `hermes_core/tests/learning/test_quizzes.py` (new cases in a new
  test class; do not rewrite existing ones)

- [ ] **Step 1:** `_initial_state` materializes the new types (strip
  `reference`/`test_code` from the no-answers view — extend the
  `include_answers=False` stripping so the frontend can never fetch them);
  `mode`/`variant_of` preserved in item state.
- [ ] **Step 2:** `_grade_question` dispatch:
  - `code` + `mode=solve|variant`: run learner source (starter merged) +
    `test_code` through the sandbox; `passed` → correct;
  - `code` + `mode=transcribe`: normalized text compare against
    `target_code` (strip trailing whitespace per line, collapse blank runs);
    NO execution needed;
  - `derivation`: per-cloze grading per Task 1 rules; question correct =
    all graded clozes correct; `ungraded` steps excluded from denominator
    and surfaced in the graded detail;
  - non-python `code` questions: recorded as `ungraded`, never fake-passed.
- [ ] **Step 3:** `quiz.attempt` detail gains per-question
  `{"mode", "timed_out", "ungraded_steps"}` fields — additive, existing
  consumers unaffected (assert M3 tests still green).
- [ ] **Step 4: gate**

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
```

### Task 4: Route passthrough + capability status

**Files:**
- Modify: `python/src/desk_server/routes/study_routes.py` (only if the
  submit payload shape needs the new response fields surfaced — expected:
  zero or trivial change; questions route must be verified to strip
  `test_code`/`reference`)
- Modify: `python/src/capability_registry.py` + drift tests: flip
  `math-formula-to-code` / `code-to-math-formula` from candidate to
  available ONLY if the D-class upgrade rule is now satisfied (executable
  pipeline + acceptance tests); otherwise record "criteria met at B-3"
  and leave candidates.
- Add: `python/tests/test_study_code_grading_routes.py` (submit a code
  question end-to-end through the desk route with a real sandbox run).

- [ ] **Step 1:** route test first, then verify/adjust stripping.
- [ ] **Step 2: gates**

```powershell
cd python
python -m pytest tests/test_study_code_grading_routes.py tests/test_study_routes.py tests/test_capability_registry.py -o "addopts=" -p no:cacheprovider -q
```

### Task 5: Docs and handoff

- [ ] Update the math-code design doc §4/§5 status (已实施 + deviations:
  `expr_py` fallback decision, python-only v1); DECISIONS.md entry with the
  residual-risk statement; note for B-3 (UI) listing the exact wire shapes
  it will consume.
- [ ] Full learning-suite re-run + commit locally, do not push, stop for
  review.

---

## Acceptance Criteria

- Contract validates/rejects the documented samples for both new types;
  caps enforced; python-only grading honest (`gradable: false`, `ungraded`
  — never fake results).
- Sandbox: timeout tree-kill, output truncation, temp-dir cleanup, minimal
  env, deterministic equivalence sampling — all covered by adversarial
  tests; security review sign-off recorded before dispatch wiring.
- Frontend can never fetch `reference`/`test_code`; grading only ever runs
  against user-activated quiz items.
- `quiz.attempt` history from M3 remains intact and its tests untouched.
- Work committed locally only; B-3 handoff note written.
