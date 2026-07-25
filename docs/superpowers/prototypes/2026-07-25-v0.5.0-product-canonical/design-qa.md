# Design QA · Kabuqina v0.5.0 Study / Studio 产品重构

## Evidence

- Product architecture truth:
  - `D:\project\Kabuqina\docs\superpowers\plans\2026-07-25-v0.5.0-study-studio-product-architecture.md`
- Frozen visual truth:
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-23-v0.5.0-desk-canonical.html`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\source-reference-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-wide.png`
- Rendered implementation:
  - `http://127.0.0.1:4174/`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-flyleaf-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-plan-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-learn-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-practice-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-evaluate-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-lifecycle-narrow.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\source-chat-before-minimal-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-chat-minimal-course-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-chat-minimal-general-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-chat-minimal-studio-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-chat-minimal-narrow.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\source-studio-before-cup-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-cup-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-cup-connected-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-study-studio-shell-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-empty-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-project-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-chat-wide.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-narrow.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\implementation-studio-narrow-boundary.png`
- Combined comparison:
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-study-lifecycle.html`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-study-lifecycle.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-chat-minimal-studio-cup.html`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-chat-minimal-studio-cup.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-study-studio.html`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-study-studio.png`
  - `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-25-v0.5.0-product-canonical\qa\comparison-studio-focused.png`

## Viewport and normalization

- Desktop judgment uses the default in-app browser viewport at device scale factor `1`; the product canvas remains capped at the prototype’s `1280 px` logical width.
- Responsive judgment uses an explicit `390 × 844` CSS viewport at device scale factor `1`.
- The frozen Study desk is the visual baseline. Prototype journey controls and browser scrollbars are surrounding review evidence, not part of the product shell.
- Wide screenshots compare the same paper, desk, purple accent, border, shadow, type, and icon language. Narrow evidence separately confirms the lower SourceSnapshot and write-boundary rail.

## Product states checked

- Study flyleaf: pencil draft versus active ink; course goal, preference, constraint, and explicit activation.
- Study plan: active plan, resumable bookmark, completion state, and skip state.
- Study learn: traceable concept, local course resources, tutoring-note review boundary, and no grading.
- Study practice: current question, answer draft, check feedback, course Chat handoff, and dirty-leave protection.
- Study evaluate: bounded assessment, next adjustment, wrongbook retry, source return, and read-only activity log.
- Studio empty: Project is the container; the entry point is an expression goal rather than a file format.
- Studio connected: Project Brief, audience, goal, undecided format, current stage, SourceSnapshot, and write boundary.
- Course Chat: bound course, source provenance, and exact return location.
- Studio Chat: bound Project, explicit source scope, expression-only responsibility, and no Study-truth mutation.
- General Chat: no implicit Study or Studio write; saving and handoff require review.
- Minimal Chat shell: centered conversation paper, on-demand unified session-history drawer (no scope tabs), low-emphasis origin tags, sparse messages, and persistent composer.
- Studio Nana anchor: empty and connected Project states show the same lower-right cup language as Study and open Studio-scoped Chat.
- Activity and recovery: Study and Studio resumable activities coexist without overwriting one another.

## Findings

Iterations 1–4 closed with no remaining P0/P1/P2 findings for their scope. Iteration 5
(unified-history Chat + Nana context panel) fixed a blocking styling gap and is awaiting
rebuild + browser re-verification; see the iteration log.

- Information architecture: Study and Studio are the two business domains. Chat and Activity are cross-domain utility/state layers, not peer content containers.
- Domain semantics: Study owns input, internalization, learning state, and learning evidence. Studio owns output, expression, Projects, versions, and deliverables.
- Cross-domain connection: Study hands selected sources to Studio through an explicit, reviewed, read-only `SourceSnapshot`; Studio never infers an implicit current course.
- Studio boundary: the prototype deliberately stops at overall layout, Project container, Brief, sources, stage, and write boundary. It does not pretend that Studio is a PPT generator or prematurely freeze its editor/canvas/tool model.
- Fonts and typography: Segoe UI / Microsoft YaHei stack, purple hierarchy, wrapping, and label density remain consistent with the frozen Study source.
- Spacing and materials: the warm desk gradient, ivory paper, compact header, book/project rails, central work surface, borders, radii, and shadows reuse the existing visual system.
- Colors and icons: Studio uses the established purple family rather than introducing a new domain color. Functional icons remain Lucide; there are no emoji, placeholder illustrations, or custom icon drawings.
- Copy: “input / output”, Project, SourceSnapshot, current scope, return location, and write boundary are explicit; simulated backend behavior remains honestly labeled.
- Responsiveness: at `390 × 844`, Study summary cards, wrongbook rows, and logs collapse to one column while the five notebook tabs stay horizontally reachable; Studio moves SourceSnapshot and the write boundary below the Project workspace. Neither domain introduces horizontal page overflow.
- Chat density: removing both side rails and card-like assistant messages gives Chat materially more negative space than Study or Studio without hiding scope, provenance, return, save, or handoff semantics.
- Accessibility: primary controls use semantic buttons, dialog names, labelled inputs, visible focus treatment, practical targets, and reduced-motion support.

## Comparison history

### Iteration 1 — blocked

- [P2] Studio initially introduced a green domain accent not present in the frozen visual source.
  - Fix: mapped Studio navigation, cards, empty state, Project Brief, and context treatment back to the existing Kabuqina purple palette.
  - Post-fix evidence: `qa/implementation-studio-empty-wide.png`, `qa/implementation-studio-project-wide.png`.

- [P2] The first narrow layout hid the SourceSnapshot / write-boundary rail.
  - Fix: at `≤ 860 px`, the Studio source rail now moves below the Project workspace; at `≤ 560 px`, it collapses to one column.
  - Post-fix evidence: `qa/implementation-studio-narrow-boundary.png`.

### Iteration 2 — passed

- Study keeps the frozen desk composition while exposing Study / Studio as the stable product shell.
- Studio empty and connected states share the same project-container model; neither defaults to PPT.
- Studio Chat shows Project scope, selected sources, and the no-Study-write boundary.
- Wide and narrow post-fix inspection found no remaining P0/P1/P2 mismatch.

### Iteration 3 — Study lifecycle passed

- Replaced the five label-only notebook tabs with complete flyleaf, plan, learn, practice, and evaluate states based on the 0.4.0 functional contract.
- Preserved the 0.5.0 warm desk, ivory paper, purple pencil, Lucide icon, and three-column Study composition.
- [P2] The first narrow evaluation capture rendered the primary “再试一次” action as white text on a white button because `.wrongbook-row button` overrode `.primary-action`.
  - Fix: added a scoped `.wrongbook-row button.primary-action` color/background override and verified the computed colors after rebuilding.
  - Post-fix evidence: `qa/implementation-study-evaluate-wide.png`, `qa/implementation-study-lifecycle-narrow.png`.
- Desktop, `390 × 844`, dirty-leave, wrongbook retry, and Study → Chat → exact return inspection found no remaining P0/P1/P2 issue.

### Iteration 4 — Chat simplification / Studio Nana passed

- Replaced the three-column Chat workbench with one centered conversation paper; ordinary, course, and Studio scopes now live in a compact top switcher.
- Reduced the persistent context card to one provenance line and flattened assistant messages and hint actions to restore whitespace.
- Added the Study-style lower-right “碰杯问小娜” anchor to empty and connected Studio states. It opens Chat with the Studio scope selected.
- [P2] The first simplified course Chat repeated “一级提示” in both the assistant metadata and hint footer.
  - Fix: changed the footer label to the quieter “还需要帮助？” prompt.
- [P2] At `390 × 844`, the first responsive pass placed the composer just below the initial viewport.
  - Fix: constrained the narrow Chat paper height so the message list scrolls internally and the composer bottom remains at `836 px` inside the `844 px` viewport.
  - Post-fix evidence: `qa/implementation-chat-minimal-course-wide.png`, `qa/implementation-chat-minimal-narrow.png`.
- Final scope controls measure `40 px` high, all three remain reachable, and no horizontal page overflow remains.

### Iteration 5 — unified-history Chat + Nana context panel (styles landed, re-QA pending)

- Direction change after iteration 4: per the revised architecture (§2.3) and AGENTS.md, full
  Chat must not present ordinary / course / Studio as parallel scope tabs. The fifth-generation
  JSX replaced the switcher with one unified session-history drawer (`SessionHistory`), a minimal
  paper header (history toggle, low-emphasis origin tag, single return action), an explicit
  free-conversation empty state, and the shared lower-right Nana context panel
  (`ContextChatPanel`) for Study and Studio.
- [P0] The fifth-generation markup shipped without any styling: `chat-history`, `session-list`,
  `new-chat-action`, `history-toggle`, `chat-session-title`, `chat-empty-state`,
  `chat-paper--minimal`, `message-list--empty`, and the entire `context-chat-panel` /
  `mini-message` family existed in `src/App.jsx` but not in `src/styles.css`; `dist/` was built
  from the previous generation, and the iteration-4 screenshots still show the removed scope
  switcher.
  - Fix: authored the missing styles in the frozen visual language (ivory paper, purple family,
    Lucide icons), including wide and `≤ 860 px` / `≤ 560 px` behavior; removed the superseded
    `chat-rail` / `chat-scope-tabs` / `context-strip` / `hint-ladder` / `composer-scope` /
    `session-search` / `narrow-chat-tools` CSS so the forbidden pattern cannot be revived by
    copy-paste.
- Alignment fixes applied in the same pass:
  - Deleted the dead legacy-J4 `WorkFolderModal` and `ResultPreviewModal` components (PPT-first
    flow superseded by the SourceSnapshot handoff) and their unused icon imports; renamed
    `work-folder-tab` to `send-studio-tab` to match its actual "选择内容，发送到 Studio" action.
  - Removed the evaluate page's read-only activity log per the P2 budget in
    `2026-07-25-v0.5.0-interface-information-principles.md` (§3, §5.1).
  - `ModalShell` now traps Tab focus inside the dialog; the closed history drawer is removed
    from the tab order and accessibility tree via `visibility`.
- Post-fix verification (same day, after the environment outage cleared):
  - `npm run build`: passed; `dist/` regenerated from the fifth generation
    (`index-BeL-jfer.css` now contains `chat-history` and `context-chat-panel`, replacing the
    stale fourth-generation bundle).
  - `npm run test:sites`: 4 / 4 passed.
  - Live walkthrough at `http://localhost:5173`, no console errors. Global Chat opens an unbound
    free conversation ("和小娜聊聊"); the history drawer holds all four sessions in one list with
    low-emphasis Study / Studio origin tags and no tag on free conversations; no scope tabs
    remain. Closed drawer computes `visibility: hidden` (inherited by its buttons), so it leaves
    the tab order and the accessibility tree. The Study Nana panel renders `330 × 378` anchored
    bottom-right inside the app frame, with scope line, transcript, composer, and the explicit
    "在完整 Chat 中打开" action. No horizontal page overflow at `1280 × 900` or `800 × 455`.
- Still pending: fresh wide / narrow QA captures for the drawer, empty state, scoped sessions,
  and both Nana panel states (the review browser pane was not compositing frames, so screenshots
  could not be taken; geometry was verified numerically instead).

## Primary interactions tested

- J1: empty first run → create course → enter Study.
- J2: Study → course Chat → exact return to the original answer and learning position.
- Five-page Study navigation: flyleaf activation, plan completion/skip, learning-to-practice handoff, dirty-practice leave confirmation, and wrongbook retry.
- J3: general Chat → reviewed course draft → Study activation.
- J4: Study source selection → SourceSnapshot review → Studio Project → Studio Chat.
- J5: restart recovery offers both the Study position and Studio Project.
- Chat-to-Studio handoff uses the same reviewed SourceSnapshot contract.
- Studio lower-right Nana anchor → Studio-scoped minimal Chat.
- Minimal Chat scope switching preserves ordinary save/handoff actions, course exact return, and Studio write boundaries.
- Escape closes open modal states.
- Browser walkthrough after the redesign: no console errors.
- `npm run build`: passed.
- `npm run test:sites`: passed.

## Open questions

- Studio’s detailed internal work surface remains intentionally open: editor/canvas/timeline/tool selection, output-format choice, version comparison, publishing, and export should be designed after the overall layout is accepted.
- Production persistence, real artifact generation, provider behavior, and Tauri integration remain implementation work outside this prototype.

## Implementation checklist

- [x] Write the Study / Studio product architecture before changing the prototype.
- [x] Establish Study and Studio as business domains.
- [x] Redesign Chat as a scoped cross-domain interaction layer.
- [x] Simplify Chat to a centered, high-whitespace conversation surface.
- [x] Add a Study-consistent lower-right Nana entry to Studio.
- [x] Separate learning evidence from Projects and deliverables.
- [x] Complete the five Study notebook pages using the v0.4.0 responsibilities inside the v0.5.0 shell.
- [x] Protect unchecked practice drafts when changing Study lifecycle pages.
- [x] Replace the old PPT-first J4 with an explicit SourceSnapshot handoff.
- [x] Define Studio’s overall layout without prematurely designing its detailed tool surface.
- [x] Verify desktop, narrow, modal, Activity, and recovery states.
- [x] Build and run the prototype packaging tests.

## Follow-up polish

- [P3] Remove the prototype-only J1–J5 review rail when integrating the shell into production.
- [P3] Once the overall layout is accepted, begin a dedicated Studio concept phase based on Project types and expression workflows rather than file formats.
- [P3] De-prototyping checklist for implementation slices: strip in-frame P3 copy (the Studio
  boundary-note card, "整体布局阶段" pill, write-boundary explainer cards) and translate internal
  object names (`SourceSnapshot`, `revision`) out of user-facing copy; keep only the §4-exempt
  safety confirmations, reworded in user language.
- [P3] Purge the now-dead CSS left behind by the removed legacy-J4 modals (`folder-tabs`,
  `create-flow`, `generation-card`, `result-*`, `activity-timeline`, etc.).

final result: iteration 5 passed build, packaging tests, and live walkthrough; QA captures pending
