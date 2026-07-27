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

> **Corrected 2026-07-27.** Everything below this heading that cites `390 × 844` is stale, and
> so is every "390 × 844 passed" line in the iteration log. This is a Windows desktop app:
> `tauri/tauri.conf.json` fixes the main window at 1100 × 760 with **`minWidth: 720`,
> `minHeight: 520`**, and the only other window is an 87 × 76 always-on-top mascot pill
> (`tauri/src/companion.rs`), which does not carry this UI. There is no phone target.
> **The narrow viewport is therefore 720 × 520 — a dragged-narrow desktop window — and the
> architecture doc's wording (「窄窗」, not 移动端) already said so.** The `≤ 560px` breakpoint
> was unreachable and has been deleted; `≤ 860px` now serves the real 720–860 band.

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

### Iteration 6 — desk lamp / dual-theme tokens (implementation landed, owner walkthrough pending)

- Owner direction: materiality guides design (not deferred to art); the desk lamp from the
  2026-07-07 notebook-ia prototype is confirmed as the light/dark switch.
- Token consolidation: all ~140 hardcoded hex values in `src/styles.css` were mapped onto a
  ~45-token semantic palette (`:root`, uppercase hex) — ink scale, paper/surface scale, four
  line weights, purple family, manila/tan warm family, semantic status colors, desk gradient
  stops, and veils. Zero color literals remain outside the token definitions (verified by
  regex sweep).
- Dark theme: a single `[data-theme="dark"]` token block restyles the whole product — warm
  dark desk, ink-on-dark paper, lightened purple family, `color-scheme: dark`. The app-frame
  swaps its daylight wash for a warm lamp glow anchored at the top-right (lamp corner), and
  `--shadow` / `--shadow-soft` deepen.
- Lamp object: `LampDesk` button in the shell utility area toggles the theme
  (`aria-pressed`, state-dependent labels 开台灯/台灯已开); when on, the icon warms and glows
  (`--lamp-glow`). Settings gains a mirror row (台灯 · 外观, 开灯/关灯). Theme persists via
  `localStorage` with a pre-paint script in `index.html` (respects `prefers-color-scheme` on
  first visit); `prefers-reduced-motion` suppresses the transitions.
- Verified so far: page renders with zero console errors after all changes (HMR); the lamp
  button is present with correct semantics; token sweep is clean.
- Pending: interactive owner walkthrough of both themes across Study / Studio / Chat / modals
  (the review browser pane was not compositing frames, so synthetic clicks and screenshots
  were unreliable in the authoring session), dark-mode contrast spot-checks, `npm run build`
  + `npm run test:sites`, and refreshed QA captures in both themes.

### Iteration 7 — Study learn page: reader → reconstruction loop

- Upstream: the owner's mechanism revision (architecture doc §0.1) — Study is not mechanical
  input; the learner rebuilds knowledge in their own mind. The learn page must therefore lead
  with one knowledge core and then guide a generative act, not present readable prose.
- Redesign: the page is now one loop — **知识核 → 我自己的说法 → 对照**.
  - The knowledge core is a single sentence with its source, and it is the page heading; the
    old `page-intro` (which restated the core and explained the page's own role) was deleted
    as a duplication and P3 leak.
  - The generative prompt ("先别看解释——用你自己的话说说…") plus the learner's own field is
    the P0 body. The field reuses the practice `answer-field` (KaiTi — the learner's own hand).
  - After they write, the reference is revealed **beside** their words, never replacing them:
    「我自己的说法」/「教材 §2.3 的说法」side by side, with a margin note reading
    "这里只对照，不判分" and a self-check question. The learn page still does not grade.
  - Escape hatch honors answer-then-teach: 「先看教材的说法」 reveals the reference without
    writing, and the primary action then becomes 「现在用自己的话说一遍」 — the answer is given,
    the reconstruction is still invited.
  - Materials dropped from a permanent two-card grid to one quiet on-demand line
    (`material-call`), per "材料只作按需参考，不作铺开的主线".
  - The pending tutoring-note draft renders only when one exists; the previous "还没有待审核
    笔记" placeholder was cut as P2.
- Verified live at `http://localhost:5173` (React-faithful input events; the review pane does
  not composite frames, so synthetic clicks/screenshots were not usable): seed → contrast shows
  the learner's words verbatim; 补一句 returns to writing with the draft preserved (learn state
  lives in `App`, so flipping notebook pages does not discard it); 对照看看 stays disabled while
  empty; the reveal path shows the invitation copy and the reconstruct-first primary action. At
  `390 × 844` the contrast pair collapses to one column with no horizontal overflow.
- `npm run build` and `npm run test:sites` (4/4) pass.

### Iteration 8 — bookend course tabs (amends the frozen Study desk master)

- Owner-level change: course identity moves from a permanent left rail onto the notebook's own
  tabs, restoring the 2026-07-07 notebook-ia object vocabulary. 换课＝换一本本子.
- Desk layout: `.desk-scene` drops from three columns to two, with a `bookend` row above the
  notebook and the review rail spanning both rows (`gap: 0 18px` so the tabs meet the paper).
  The active tab uses the notebook's own paper color and overlaps its top border by `1px`, so
  it reads as attached to the book; idle tabs sit lower with an inset shadow and a muted spine.
- Deletions this enables (both previously failed the principles' own tests): the permanent
  「我的课程本」card, and the 「本课材料」card, which duplicated the learn page's on-demand
  material line. The notebook header no longer repeats the course name — the tab carries
  identity, the header carries position (`极限与连续 · 最近保存 …`).
- Narrow: the bookend stays visible and horizontally scrollable (it is the course switcher, not
  a rail), so the narrow tool bar drops its 课程 button and collapses to two.
- Verified at `1280 × 900`: active tab background equals notebook paper exactly
  (`rgb(251,248,241)`), tab-to-notebook gap is `-1px`, left rail gone, no horizontal overflow.
  In dark theme the same identity holds (`rgb(50,45,54)` on both) with idle tabs distinguished
  by a darker fill and muted text. At `390 × 844` all three tabs remain reachable with no
  overflow. `npm run build` and `npm run test:sites` (4/4) pass.
- Consequence for the plans: `2026-07-25-v0.5.0-study-studio-product-architecture.md` §3.2 still
  describes the left rail as 课程本与材料 and must be updated when this amendment is accepted.

### Iteration 9 — copy density pass across the five Study pages

- Owner: every one of the five notebook pages was still information-dense; the copy needs
  cutting, not restyling.
- Removed the `page-intro` block (eyebrow + heading + explanatory paragraph) from 扉页, 计划,
  and 评估. In each case the paragraph explained the page's own scope rules ("这里只保存课程目标
  ……不会写进扉页", "计划只描述下一步学习动作……不伪装成草稿", "不给学习者贴人格或能力标签")
  — P3 product commentary aimed at reviewers, not learners. The notebook tab already names the
  page; the sheets already name themselves. `.page-intro` CSS deleted with its last use.
- De-duplicated against the new bookend/notebook header: the flyleaf's 「高等数学 · 极限与连续」
  heading and the plan's 「极限与未定式」 heading both restated identity the tab and header now
  carry.
- Removed doubled state signals: 铅笔草稿 sheet no longer also carries a 待确认 pill (dashed
  pencil styling plus the header already say it); 已落墨 sheet no longer also carries an
  Active pill.
- Practice page: 我的答案 lost its redundant sub-label; save status shortened to 「草稿已保存」/
  「回到原处，答案没被改动」 (was prototype-proving copy about return targets); the feedback card
  header dropped 「· 需要修改」 (the 还差一步 pill says it) and its third row 「接下来试试……」
  (the 修改答案 button is that action).
- Fixed a real duplication the trim exposed: 小娜's margin note and the feedback card printed
  the *same sentence* ("0/0 是未定式，不是极限值"). The margin note is now a method hint
  (「试试把“未定式”这个词，放进你原来那句话里」) and the card keeps the diagnostic, so the two
  divide labor instead of repeating.
- Measured body copy per page after the pass (notebook page innerText, whitespace stripped):
  扉页 134, 计划 96, 评估 103, 练习 191 (feedback state, the heaviest), 学习 already lean from
  iteration 7. `npm run build` and `npm run test:sites` (4/4) pass.

### Iteration 10 — 杂记本 as 留白

- Owner correction to the earlier proposal: 杂记本 is **留白**, not a triage inbox. The first
  design gave every item an outbound 归本 action and worried about hoarding — that was still
  manufacturing tasks, just in a new place. A desk cannot be courses, plans, and evidence
  everywhere; one book has to ask nothing of you.
- Built accordingly: a kraft-paper book at the end of the bookend. Selecting it replaces the
  course notebook with **one page** — a free writing pad (KaiTi, the learner's own hand) plus
  whatever landed there from Chat. Explicitly absent: the five lifecycle tabs, any plan,
  any count or badge, any 待整理 label, the card box (a scratch pad has no flashcards), and the
  notebook header. 小娜 stays.
- Filing is quiet and optional: one low-emphasis 「归到某一本」 per note reveals the course books
  inline (plus 算了); choosing one removes the note and toasts that it still awaits review in
  that course, so invariant 1 holds. Nothing pushes the user to empty the book.
- Write path: the J3 review modal's 保存到 list now offers 「杂记本 · 还不属于哪门课」, so a
  reviewed save no longer has to be forced into a course it does not belong to.
- Verified: kraft tab and kraft page share one color (`rgb(245,234,216)`) so the active book
  merges with its tab, distinct from the ivory course books; no lifecycle tabs and no card box
  in scratch; filing empties the page to genuine blank; switching back to 高等数学 restores the
  five pages, the card box, and the 极限与连续 header. In dark theme scratch (`rgb(73,61,45)`)
  stays distinguishable from course books (`rgb(43,39,49)`). No horizontal overflow.
  `npm run build` and `npm run test:sites` (4/4) pass.
- Deliberately not built: search, tags, sorting, bulk actions, counts, and any pressure to
  file. Open: whether 保存到 should *default* to 杂记本 for unbound conversations (the honest
  option — the system would stop guessing a course), which would change the scripted J3 demo.

### Iteration 11 — message actions: appearance conditions defined

- The two per-message buttons had no designed trigger: `canSave: true` was hardcoded on one
  seeded assistant reply. Owner asked what should govern them; auto-detection ("小娜 spots a
  knowledge point and offers to save") was rejected — it manufactures input accumulation, takes
  the categorization judgment away from the learner, and its cost is asymmetric (a missed
  capture is recoverable from history; a false prompt interrupts thinking). Rule adopted:
  **detection may speed up an action the user has already started, never start one.**
- Appearance: actions rest at `opacity: 0` and appear on `.message:hover` or
  `.message-actions:focus-within`. Deliberately not `display: none` — the buttons stay in the
  DOM, the tab order, and the accessibility tree, so keyboard and screen-reader users keep the
  capability that hover-only would deny them.
- Availability: every message now carries them, **including the learner's own** — under the
  reconstruction thesis the learner's own sentence is the more valuable evidence, and the old
  code offered saving only on 小娜's replies.
- Scope rules: 自由会话 and 课程会话 show both actions; **Studio 会话 shows neither** — 留到本子里
  would cross the write boundary in §2.3, and 发送到 Studio is meaningless inside a project.
- Renamed 「保存到课程」 → 「留到本子里」: the destination can be 杂记本, which is not a course, and
  both destinations are 本子 in the notebook metaphor.
- Fixed two modeling defects the rule exposed:
  - Course chat was not merely skipping the course picker, it was **blocked** — `openDraftReview`
    returned a toast and saved nothing. It now saves, skipping only the course step; the modal
    reads 「审核后留进高等数学」 and keeps the type review.
  - Saved state was one global boolean, so saving anything disabled the button on every message.
    It is now per-message (`savedMessages`).
- Verified live: 自由会话 shows both actions on both roles at resting opacity 0 while remaining
  focusable; focus-within computes `opacity: 1` (confirmed with transitions disabled — the
  review pane does not composite frames, so an in-flight transition otherwise reads as 0);
  Studio 会话 renders zero action nodes; course chat opens the bound-course modal with only the
  type selector; after saving, only the saved message shows 「已留下，待审核」.
  `npm run build` and `npm run test:sites` (4/4) pass.

### Iteration 12 — 杂记本 moves right; Study loses its outbound exit

- Bookend order: the scratch book leaves the course group and is pushed to the far right
  (`margin-left: auto`), so 「高等数学 大学物理 開新本 ⟶gap⟶ 杂记本」. Its right inset is now an
  explicit `padding-right: 16px` clearing the notebook's top-right radius, replacing the
  accidental 15px that came from a reserved scrollbar gutter (0 on overlay-scrollbar
  platforms, so the tab would otherwise have collided with the corner there). Verified the
  active tab still overlaps the paper by `-1px`.
- Owner decision: **Study has no outbound exit.** 学习就是纯粹的学习; Studio already pulls what
  it needs. Removed the notebook's 「选择内容，发送到 Studio」 tab (and its CSS), the narrow
  toolbar's Studio button, and — same reasoning, since a course conversation is Study — the
  「发送到 Studio」 action in course chat. The Study desk now contains zero occurrences of the
  word "Studio".
- Sourcing therefore only starts from Studio's existing 「从 Study 选择来源」; the transfer modal
  is retitled 「从 Study 取素材」 when it opens from there. J4 was rewritten to start on the
  Studio surface, since its old Study-side entry point no longer exists.
- Free Chat keeps 「发送到 Studio」 — it is not Study.
- Bonus fix while editing the narrow toolbar: it offered 课程/卡片/Studio but never 小娜, who is
  otherwise unreachable at ≤860px because the whole review rail is hidden. It is now 卡片 + 小娜
  (卡片 alone drops out in 杂记本, which has no cards), laid out with flex so one or two buttons
  both fill the bar.
- Plans updated to match: §2.1 (Study is a source Studio may draw from, not a pusher), §3.2
  (bookend master, no outbound exit), §4.1 (renamed 显式取材, direction reversed, free-Chat
  exception stated). `npm run build` and `npm run test:sites` (4/4) pass.

### Iteration 13 — Studio materialized on the four-layer framework

- Grounded in the real framework rather than a guess: `DECISIONS.md` defines
  `Read → Material Index → Deliverable Planner → File Writer`, with a *parallel* learning path
  (`Learning Index → Learning Planner → Output Writer`). Both domains share the skeleton — but
  Study never exposes its four layers as destinations, so Studio must not either. Weighting
  adopted: 素材 is a place, the index is a label on the pile, Planner is the only work surface,
  Writer is an action.
- Vertical folder tabs (owner): projects are tabs down the left edge, radius on the left, the
  active one taking the folder's own paper colour and overlapping its edge by `-1px`. Same
  merge technique as Study's bookend, mirrored — 本立着露顶边，夹插着露侧边. The desk grid's
  column gap had to go to 0 (a gap breaks the merge); the sources rail now offsets itself.
- Work surface: a Brief slip clipped at the front (always visible, because every ordering
  judgement returns to 讲给谁/要他们明白什么), then 观点卡 — **one card = one thing I want to
  say**, with its backing source beneath it — in a movable sequence where **the order is the
  structure**. Bottom bar binds: 「按这个顺序成件」 with 「形式到这一步才选」, so choosing a format
  early is physically impossible.
- SourceSnapshot is now a **photocopy** — 复印件, not 复写件: a carbon copy is made *with* the
  original, whereas a snapshot is taken later from an original that already exists, and carries
  a revision ("this is the copy as of when you took it"). Rendered as a dashed edge plus
  原件在高等数学, which let the P3
  「写入边界」 explainer card be deleted — the read-only semantics are carried by the material.
  The 「Studio 不等于 PPT」 card and 「整体布局阶段」 pill went with it.
- Removed a name collision: the deleted legacy work-folder modal had left a `.folder-tabs`
  rule behind, which the new vertical tabs would have inherited.
- Verified at 1280×900: tabs stack vertically, active tab background equals the workspace paper
  in both themes (`rgb(251,248,241)` / `rgb(50,45,54)`), merge gap `-1px`, reordering renumbers
  correctly and disables the boundary buttons, the pile index opens with per-entry provenance,
  carbon copies compute `dashed`. At 390×844 the tabs turn into a scrollable row with no
  horizontal overflow. `npm run build` and `npm run test:sites` (4/4) pass.
- **Documented**: all of the above, plus the Study vocabulary accumulated this session, is now
  registered in `docs/superpowers/plans/2026-07-25-v0.5.0-materiality-vocabulary.md` — the
  prototype alone cannot tell a reader that a dashed border means "carbon copy".

### Iteration 14 — planner review as pencil cards; 书堆 for course materials

- **Planner review.** The existing 0.4.0 interaction (`review_outline` in
  `hermes_core/tools/user_interaction_tool.py`) hands the whole outline over as one Markdown
  blob with 通过 / 补充要求 / 自行编辑 — all-or-nothing, nothing manipulable. Replaced with
  per-card participation: Nana's proposals arrive as **pencil cards** (dashed, lavender, hollow
  order number, muted text) carrying 落墨 / 改写 / 抽走; only inked cards join the sequence, and
  inked cards are the only ones that get reorder arrows. Binding is **disabled while any pencil
  card remains** ("还有 N 张铅笔卡要你过目") — you cannot bind an outline nobody confirmed.
  「让小娜再拟几条」 adds more proposals, still in pencil, which re-locks binding. This reuses
  Study's pencil/ink law rather than inventing a second review language, and it gives
  「内容是小娜制作，项目是用户参与的」 a concrete shape. The Brief gained 「和小娜一起理清」,
  covering review_outline's 补充要求 path. Nothing on the cards is format-specific.
- **Dark-theme token fix found while verifying.** Pencil and ink cards were nearly identical in
  dark (`rgb(59,49,69)` vs `rgb(58,52,64)` — 5/255 on the widest channel), because low-lightness
  surfaces swallow hue shifts. `--purple-faint` dark went `#3B3145 → #413352`, widening the blue
  channel delta to 18. This is not a Studio-only fix: `.study-sheet--pencil` uses the same token,
  so **Study's pencil draft had the same defect in dark mode** and is fixed too.
- **书堆.** Course materials return as **standing spines** in the Study right rail, with
  vertical Chinese text (which is how real Chinese spines are set). Measured 30×96 — it stands
  up. The point is posture: 参考书立着（需要时抽一本），笔记本摊开着（天天写）. Deliberately not
  a browsable knowledge base — that is the most seductive input-accumulation surface and it
  fails the delete test. Its Learning Index is a foldout labelled 「这些书里有什么」 with
  per-entry provenance, matching how Studio's Material Index is treated one layer over.
  Absent in 杂记本, which has no course materials.
- Narrow: the review rail is hidden at ≤860px, which would have made the stack unreachable, so
  the narrow tool bar is now 参考 / 卡片 / 小娜 (dropping to just 小娜 in 杂记本).
- Verified at 1280×900 and 390×844, light and dark: inking moves a card into the sequence and
  decrements the counter, discarding removes it, clearing all pencil unlocks binding, a new
  proposal re-locks it, the stack index opens with provenance, spines stay distinct from the
  rail in dark, no horizontal overflow. `npm run build` and `npm run test:sites` (4/4) pass.

### Iteration 15 — flashcard grading: four levels down to one honest question

- Owner noticed the 1 忘了 / 2 困难 / 3 记得 / 4 熟练 row looked purposeless. It is not — SM-2
  needs a grade to set the next interval, and the prototype merely toasted it. But the right
  question was never "do we need grading", it was **"why four levels"**, and four is inherited
  from Anki rather than designed.
- The cost of four: the learner must make a *second* judgement after recalling — "was that 困难
  or 记得?" — which is slow, low-confidence (people confuse *slow to recall* with *poorly known*),
  and paid dozens of times a day. By this session's own standard it is also not a reconstruction
  trace; it is an opinion about one.
- Now two: **想起来了 / 没想起来**, the only judgement a learner can make reliably and instantly,
  plus a low-emphasis 「这张太简单了，别再常来」 preserving the genuine "let this one go" need
  without a third peer button.
- **The two buttons are deliberately equal weight** — same fill, size, and border. Styling
  「想起来了」 as the primary action would make it read as the good answer and pressure dishonest
  self-report, and the scheduler would be fed garbage. Verified equal in the DOM.
- **Difficulty is measured, not asked**: time from card shown to answer revealed is captured and
  passed with the grade. It is a real behavioural signal, consistent with 「真实行为直接记录」,
  and costs the learner nothing. It surfaces only in the prototype review rail, never in the
  product UI.
- Verified at 1280×900 and 390×844, light and dark: buttons compute identical styles, the
  two-column layout holds at narrow, elapsed time is captured, no horizontal overflow. The old
  `.grade-grid` rules (including its narrow override) are deleted. `npm run build` and
  `npm run test:sites` (4/4) pass.

### Iteration 16 — flashcard grade contract; Study copy and contrast pass

- **Caught a latent integration bug.** A background search that finished late surfaced
  `docs/superpowers/plans/2026-07-04-study-m2-course-space-flashcards.md`: `review_card` accepts
  exactly `again | hard | good | easy`, and **an invalid grade falls back conservatively to
  `again`**. Iteration 15 was submitting the Chinese labels verbatim, so wiring it to the real
  backend would have silently scored *every* card as forgotten. Labels and grades are now
  separated (`RECALL_GRADES` / `GRADE_LABELS`): the UI says 想起来了, the payload says `good`.
  `hard` is intentionally never produced — that is the unreliable self-report the redesign
  removed, and measured reveal time replaces its signal.
- Plan page: dropped 「继续上次」. It duplicated the notebook header's bookmark, which is the
  established object for "where you left off" — the plan page does not need a second one.
- Learn page copy: the prompt's lead-in 「先别看解释——用你自己的话说说：」 is gone (the field
  below already says whose words these are), and 「我自己的说法」 is now 「我的想法」 throughout,
  including the return actions (补一句我的想法 / 写下我的想法).
- Contrast page reworked: the reference sits on the **left** and 我的想法 on the right; both are
  now `16px` in equal-height panels, since they are the point of the page (previously the
  reference was `.quiet-copy` at 13px, which undercut it). When 我的想法 is empty the panel is
  simply **left blank** — the old 「这一步你先看了教材……」 nudge is deleted; an empty panel next to
  a filled one says it without copy.
- Removed the now-dead `.plan-bookmark` rules; `.contrast-pair` collapses to one column at
  ≤860px with its min-height released. Verified at 1280×900 and 390×844: order, empty state,
  equal heights, KaiTi on the learner's own words, no horizontal overflow. `npm run build` and
  `npm run test:sites` (4/4) pass.

### Iteration 17 — practice page: the question becomes the page

- The page led with 「解释为什么不能直接代入」 at the largest size on screen — a paraphrase of the
  question sitting below it in body text. It carried nothing the question did not, so it fails
  the duplication test and it pushed the actual task into third place. Deleted.
- New order, per owner: **题目 → 完成标准 → 我的答案**. The question is now the h2 (25px desktop,
  the largest thing on the page), the completion standard follows at 14px as the constraint you
  check yourself against, then the answer field. Verified the DOM order and that the hierarchy
  holds in both the draft and feedback states.
- The formula is set in a serif face (`.formula`, Georgia) so it reads as mathematics rather
  than emphasis inside a bold heading, and `white-space: nowrap` keeps an expression from
  breaking mid-formula.
- **Two specificity defects found while measuring, both mine.** `.practice-question`
  (0,1,0) was losing to the pre-existing `.practice-sheet h2` (0,2,0), so *none* of the
  question's declared sizing ever applied — desktop was 28px from the old rule, not the 25px
  written, and the narrow safety override did nothing. Both rules are now
  `.practice-sheet h2.practice-question`. Separately, a `font-size: 13px` added to
  `.completion-standard` was dead for the same reason and has been removed rather than left in.
- Narrow safety: with the formula set to `nowrap`, a longer expression would burst the measure.
  At ≤560px the question drops to 19px, taking clearance from 28px to 66px at 390 wide.
  `npm run build` and `npm run test:sites` (4/4) pass.

### Iteration 18 — narrow layout retargeted at the real minimum window

- Owner asked what the narrow layout is for. Answer, from the config rather than from habit:
  the main window is 1100 × 760 with **min 720 × 520**, and the companion is an 87 × 76 mascot
  pill that carries none of this UI. So "narrow" means a dragged-narrow desktop window, never a
  phone — and the frozen architecture already said 「窄窗」.
- **Deleted the `≤ 560px` block entirely (244 lines).** It could never fire: the window will not
  go below 720. It also still carried rules for the legacy J4 modals deleted days ago. CSS
  61.7 kB → 58.0 kB.
- **Retargeted every height that had been sized for a tall phone.** At 720 × 520 the shell alone
  demanded 760px, so the page scrolled permanently and, worse, the chat composer sat at 781px —
  below the fold, meaning you could not type without scrolling. `app-frame` 760 → 480,
  desks 696 → 400, surfaces gained a **bounded** height (`min(660px, calc(100vh − 165px))`)
  instead of only a min-height, so content scrolls inside the paper rather than pushing the
  shell past the window. Study subtracts 205px instead of 165 because it carries the bookend row.
- **Fixed a second phone-shaped assumption:** the material panel had a narrow override making it
  full-width, written on the reasoning that "a phone has no beside". 720 does have a beside — the
  override made the panel 702px of a 720px window and buried the notebook. It is now
  `min(340px, 52%)`, giving 340 : 352 side by side.
- Verified at **720 × 520** with the prototype-only review rail hidden (it is 159px and does not
  exist in the product): Study fits with **zero scroll** across all five pages and the narrow tool
  bar stays in view; Chat fits with the composer at 400px, well inside the fold; Studio still
  scrolls vertically (911px) but nothing is unreachable — it has no fixed bottom bar and the
  sources rail simply sits below the work surface. No horizontal overflow anywhere.
  `npm run build` and `npm run test:sites` (4/4) pass.
- **Evidence note:** prior iterations' "390 × 844 passed" claims verified a layout no user can
  reach. They should be read as unverified for the narrow band until re-checked at 720 × 520.

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

final result: iteration 5 passed build, packaging tests, and live walkthrough (QA captures
pending); iteration 6 (lamp + dual-theme tokens) implemented, awaiting owner walkthrough,
rebuild, and captures
