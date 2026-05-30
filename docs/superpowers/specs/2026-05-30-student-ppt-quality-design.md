# Student PPT Quality Upgrade Design

## Context

Kabuqina currently exposes three student PPT quick actions from the workspace panel:

- `course_report`: course notes or learning material to course report PPT.
- `paper_report`: paper, literature PDF, or pasted paper content to paper/literature presentation PPT.
- `code_defense`: code project or course-design material to defense PPT.

The current pipeline asks the agent to read material, produce a Markdown outline, call `review_outline`, then call `pptx_write`. The first generated `paper_report` sample had a reasonable chapter spine, but the output was mostly title plus dense bullets: no screenshots, charts, diagrams, tables, or backup slides. For a student user, that is a useful draft but not a reliably deliverable deck.

This design upgrades the default output target from "summary slides" to "student-ready presentation deck." The first implementation priority is `pptx_write` structural capability. Quality rules for the three PPT workflows will be defined now, but kept light enough to adjust later.

## Goals

1. Make generated PPTX decks visually and structurally richer than title-plus-bullet summaries.
2. Preserve backward compatibility with the current `slides: [{ title, bullets, notes }]` schema.
3. Support the three student PPT modes with distinct quality expectations.
4. Let agents request richer slide structures explicitly, without needing fragile prompt-only layout hacks.
5. Keep implementation inside `hermes_core` where PPT generation semantics belong.

## Non-Goals

- Do not build a full presentation design engine in this phase.
- Do not require real screenshots when the user has not provided them.
- Do not block generation on strict quality validation yet.
- Do not add desktop-only overlay logic for PPT semantics.
- Do not replace the existing `review_outline` interaction flow.

## Recommended Approach

Implement `pptx_write` support for structured slide types first, then update the three workspace quick-action prompts to ask for those structures and apply lightweight quality rules before `review_outline`.

This balances product value and risk:

- Core generation becomes physically capable of diagrams, tables, placeholders, and backup slides.
- Existing calls keep working.
- The quality rules are visible and adjustable through prompts before they become harder product policy.

## Architecture

### Core Tool

File: `hermes_core/tools/document_tools.py`

`pptx_write` remains the public tool. Its schema will accept the existing fields and add optional structured fields:

- `slide_type`: one of `title`, `agenda`, `claim_bullets`, `diagram`, `table`, `chart_placeholder`, `screenshot_placeholder`, `qa_backup`, `closing`.
- `subtitle`: optional short context line.
- `bullets`: existing bullet list, still supported.
- `notes`: existing speaker notes, still supported.
- `diagram`: optional object for simple node/edge or step-flow rendering.
- `table`: optional object with `headers` and `rows`.
- `placeholder`: optional object for screenshot/chart placeholders, with `label`, `caption`, and `source_hint`.
- `tags`: optional labels such as `evidence`, `backup`, `quality_required`.

The renderer should dispatch per `slide_type` and fall back to `claim_bullets` when type is missing or unknown. This keeps old agents and old tests valid.

### Prompt Entrypoints

File: `web/src/chat/WorkspacePanel.tsx`

The three quick-action prompts will be updated to ask for a "high-quality deliverable outline" before `review_outline`. They should request:

- slide titles written as claims where appropriate;
- each slide marked with a `slide_type`;
- evidence objects or placeholders;
- speaker notes;
- backup slides;
- final call to `pptx_write` using the matching template.

The prompt should not pretend unavailable assets exist. If no screenshots or charts are present, it should request explicit placeholders.

### Quality Rules

Rules are advisory in phase one. The agent should use them before calling `review_outline`, but the tool does not yet reject decks that miss a rule.

`paper_report` required structure:

- Cover and agenda.
- Research background or problem framing.
- Research method, system architecture, or framework diagram.
- Key implementation or analysis evidence.
- Result/test/experiment summary.
- Innovation or contribution slide.
- Limitations and future work.
- At least one backup slide for likely teacher questions.

`course_report` required structure:

- Cover and agenda.
- Knowledge map or chapter structure.
- Key concept explanation.
- Case, example, or application scene.
- Comparison table or process diagram when the material supports it.
- Learning summary or reflection.
- Backup slide for difficult concepts or common mistakes.

`code_defense` required structure:

- Cover and agenda.
- Project background and objective.
- Architecture/module diagram.
- Core implementation flow or data flow.
- Feature evidence or screenshot placeholder.
- Testing and result summary.
- Problems encountered and solutions.
- Deployment/run instructions or backup slide.

## Data Flow

1. User clicks one of the three PPT quick actions.
2. Frontend sends a high-quality workflow prompt.
3. Agent reads uploaded or referenced material.
4. Agent drafts a structured Markdown outline with slide types and evidence requirements.
5. Agent checks the outline against the relevant lightweight quality rules.
6. Agent calls `review_outline`.
7. After user approval, agent calls `pptx_write` with structured slide objects.
8. `pptx_write` renders the deck with the chosen template and returns the output path.

## Rendering Behavior

### Bullets

`claim_bullets` should keep text readable:

- Prefer 3 to 5 bullets.
- Render no more than 7 visible bullets.
- Preserve notes for longer explanation instead of putting every sentence on the slide.

### Diagrams

`diagram` should support simple flow diagrams and architecture diagrams using boxes and arrows. It is enough for phase one to support horizontal and vertical flows.

### Tables

`table` should support compact headers and rows. It should be used for tests, comparisons, role permissions, database tables, and course concept comparisons.

### Placeholders

`screenshot_placeholder` and `chart_placeholder` should render as polished framed placeholders, not plain text bullets. They should include:

- a clear label;
- a caption;
- an optional source hint in speaker notes.

The placeholder must not claim that a real screenshot or chart was inserted.

### Backup Slides

`qa_backup` slides should be normal slides tagged as backup. They should have clear titles such as "备用：核心接口说明" or "备用：老师可能追问". Phase one does not need hidden-slide behavior; visible backup slides are acceptable and easier for students to edit.

## Error Handling

- Unknown templates continue falling back to `course_report`.
- Unknown slide types fall back to `claim_bullets`.
- Invalid `table` or `diagram` payloads render a readable fallback slide instead of failing the whole deck.
- Missing optional fields are ignored.
- If `python-pptx` is unavailable, existing error behavior remains.

## Testing

Add or update tests in `hermes_core/tests/tools/test_document_tools.py`:

- Existing simple `title + bullets` slides still create an openable deck.
- Each new slide type creates an openable deck.
- Unknown slide type falls back without error.
- `table` slides include header and row text.
- `diagram` slides include node labels.
- Placeholder slides include label and caption without pretending assets exist.
- `qa_backup` slides preserve backup text and speaker notes.
- Three templates still produce distinct backgrounds.

Update frontend tests in `web/src/chat/chatUx.test.mjs` to assert that the workspace prompts mention high-quality deliverables, `slide_type`, placeholders, backup slides, `review_outline`, and `pptx_write`.

## Rollout

Phase 1:

- Extend `pptx_write` schema and renderer.
- Add tests for structured slide types.
- Update quick-action prompts with quality rules.
- Keep quality rules advisory.

Phase 2:

- Add stricter outline self-checking if real-world outputs still miss required sections.
- Add automatic image insertion when workspace screenshots or result images are available.
- Consider hidden backup slides or appendix sections if students prefer shorter main decks.

## Open Decisions

- Backup slides will be visible in phase one.
- Screenshot and chart placeholders will be allowed when real assets are missing.
- Quality rules are prompt-level guidance in phase one, not hard tool validation.
- `pptx_write` remains in `hermes_core` because PPT generation semantics should work consistently for web child and gateway child.
