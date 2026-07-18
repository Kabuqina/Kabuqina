# Learning Layer

> Status: **Domain architecture reference; product-surface wording superseded**
> Last updated: 2026-07-18
>
> 本文关于 Learning 与 document/report pipeline 不应互相吞并的领域原则继续有效；
> “second product surface”不再决定 v0.5 的一级 IA。当前 Study-first 产品承诺、
> Chat/Create 角色、共同对象和跨面往返以
> [v0.5.0 产品全景与体验架构计划](superpowers/plans/2026-07-18-v0.5.0-product-experience-architecture-plan.md)
> 为准。

Kabuqina should not collapse into a pure academic document generator.

Academic workflows are easier to standardize because they have visible formats
and external rules: papers, reports, citations, LaTeX, formulas, slides,
templates, and rubrics. Those standards are useful engineering anchors, but they
are not the whole student need.

Learning is broader and more personal. A student may need help understanding,
practicing, debugging, remembering, explaining, or recovering confidence before
they need a final deliverable.

The Learning Layer captures this second product surface.

## Position

Current generation pipeline:

```text
Read Layer
  -> Material Index
    -> Planner
      -> Writer
```

Current live chat display surface:

```text
Read Layer / Agent Output
  -> Chat Display Layer
```

Proposed learning surface:

```text
Read Layer / Agent Output / Student State
  -> Chat Display Layer
    -> Learning Interaction Layer
```

The Learning Layer does not replace the academic/document pipeline. It uses the
same reliable Read and Display foundations to create interactions that help the
student learn.

## Product Principle

Build academic-standard capabilities as the foundation, but use them to support
learning rather than only generating submissions.

```text
Academic standard capabilities = reliability and structure
Learning interactions = student-facing value and identity
```

Examples of foundation capabilities:

- PDF and DOCX reading;
- formula extraction and LaTeX rendering;
- citations and page references;
- code reading;
- tables and figures;
- PPT/DOCX/PDF writing;
- material indexing.

Examples of learning interactions:

- explain this paragraph;
- derive this formula step by step;
- convert formula to code;
- convert code to formula;
- quiz me;
- give me a hint instead of the answer;
- find my knowledge gaps;
- turn this into review cards;
- help me prepare to present this;
- help me debug my project while explaining the concept.

## Boundary With Academic Tools

| Surface | Main question | Output |
|---------|---------------|--------|
| Academic/document tools | "Can Kabuqina process and produce standard student artifacts?" | structured materials and files |
| Learning Layer | "Can Kabuqina help the student understand and practice?" | guided conversation and learning actions |

Academic tools tend to be deterministic or format-driven. Learning interactions
are adaptive and conversational. Mixing the two too early risks making every
learning workflow look like a file-generation workflow.

## Boundary With Writer

Writer produces deliverables:

- PPTX;
- DOCX;
- PDF;
- spreadsheets;
- LaTeX projects.

Learning Layer produces interaction:

- explanations;
- hints;
- checks for understanding;
- practice questions;
- step-by-step derivations;
- feedback on student attempts;
- reflective summaries.

If the output is a file to submit, it belongs in Writer. If the output is a
conversation that helps the student learn, it belongs in Learning Layer.

## Boundary With Chat Display

Chat Display renders content clearly:

- Markdown;
- LaTeX;
- code;
- tables;
- warnings;
- source references.

Learning Layer decides the interaction pattern:

- whether to explain, quiz, hint, compare, or guide;
- whether to ask the student to try first;
- whether to reveal a full answer;
- how to adapt to the student's current understanding.

Chat Display is the screen. Learning Layer is the teaching behavior.

## Non-Responsibilities

The Learning Layer should not:

- parse files directly;
- own PDF/OCR/formula extraction;
- render final deliverable files;
- fabricate facts not present in the source material;
- hide uncertainty from the Read layer;
- become a monolithic "education brain" detached from tools and evidence.

It should orchestrate reliable lower layers and make pedagogical choices in the
conversation.

## Candidate Interaction Modes

These can start as prompt patterns or quick actions before becoming formal tools.

### Explain

User intent:

- "Explain this paper section."
- "I do not understand this paragraph."
- "Explain this formula in plain language."

Behavior:

- restate the concept;
- define prerequisites;
- use analogies carefully;
- preserve source references;
- ask if the student wants more depth.

### Step-By-Step Derivation

User intent:

- "Derive this formula."
- "Why does this step follow?"

Behavior:

- show one transformation at a time;
- keep formulas rendered with LaTeX;
- label assumptions;
- avoid skipping algebraic steps;
- let the student ask about a specific step.

### Hint Mode

User intent:

- "Do not give me the answer directly."
- "Give me a hint."

Behavior:

- ask a leading question;
- reveal partial structure;
- withhold final answer unless requested;
- encourage student attempt.

### Quiz / Check Understanding

User intent:

- "Test me."
- "Ask me questions from this PDF."

Behavior:

- generate bounded questions from source material;
- wait for student answer;
- give feedback;
- explain mistakes;
- track weak points for the current session.

### Formula-Code Bridge

User intent:

- "Convert this formula to Python."
- "Explain this code as a formula."

Behavior:

- preserve the original formula/code;
- explain variable mapping;
- produce runnable code when appropriate;
- warn when mathematical assumptions are missing.

### Review Cards

User intent:

- "Turn this into flashcards."
- "Help me review before class."

Behavior:

- extract concepts from Read/Material Index output;
- generate question-answer pairs;
- keep source references;
- support quick self-testing in chat.

### Presentation Practice

User intent:

- "Help me prepare to present this."
- "Ask likely teacher questions."

Behavior:

- summarize the story;
- generate likely questions;
- check the student's answer;
- connect to the generated PPT/report when available.

## Student State

Eventually the Learning Layer may use lightweight state:

- current course/project/topic;
- concepts the student struggled with;
- preferred explanation depth;
- whether the student wants hints before answers;
- recent mistakes and corrections;
- upcoming assignment context.

This state should be transparent and editable. It must not quietly overfit the
student into a fixed ability label.

## Safety and Academic Integrity

The Learning Layer should avoid becoming an answer mill.

Useful defaults:

- offer hints before full solutions when the user is doing homework;
- distinguish "explain" from "solve for me";
- cite source material when using uploaded files;
- show uncertainty;
- encourage the student to verify generated derivations or code;
- support teacher-facing deliverables without pretending the student did work
  they did not understand.

This does not mean refusing help. It means shaping help so the student can learn
and still produce work responsibly.

## Implementation Path

### Phase 1: Prompted Modes

Start with quick actions and prompt conventions:

- Explain;
- Step-by-step;
- Hint mode;
- Quiz me;
- Formula to code;
- Code to formula;
- Review cards.

No new heavy module is required yet.

### Phase 2: Reusable Interaction Templates

Move stable prompts into `hermes_core` so web child and gateway child share the
same behavior.

Avoid keeping canonical learning behavior only in `web/src/chat/WorkspacePanel.tsx`.

### Phase 3: Structured Learning Artifacts

Introduce structured outputs when useful:

- quiz items;
- flashcards;
- derivation steps;
- formula-code mappings;
- weak-point summaries.

These should still render through Chat Display and remain grounded in Read-layer
sources when available.

### Phase 4: Optional Memory Integration

Use memory only for durable, user-approved learning preferences or recurring
weak points. Keep per-session mistakes and quiz results local unless the user
wants them remembered.

## Design Rule

If the feature makes Kabuqina better at parsing source material, it belongs in
Read Layer.

If the feature makes Kabuqina better at rendering live answers, it belongs in
Chat Display Layer.

If the feature makes Kabuqina better at producing final files, it belongs in
Writer.

If the feature makes Kabuqina better at helping a student understand, practice,
or reflect, it belongs in Learning Layer.

The long-term goal is not "academic agent" only. It is a student workbench:

- reliable enough for academic standards;
- flexible enough for everyday learning;
- warm enough to feel like help, not just automation.
