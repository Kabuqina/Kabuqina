# Design QA — Kabuqina v0.5.0 学习书桌原型

## Comparison target

- Source visual truth: `D:\project\Kabuqina\docs\superpowers\prototypes\Style Tile.html` and the four frozen desk experience/vision documents named in the task.
- Source screenshot: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\source-style-tile.png`.
- Rendered implementation: `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-23-v0.5.0-desk-canonical.html`.
- Legacy regression archive: `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-18-v0.5.0-study-chat-legacy-regression-matrix.html`.
- Implementation overview screenshot: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\00-desk-overview.png`.
- Same-input full-view comparison: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\comparison-style-tile-desk.png`.
- Focused flow evidence: `01-feedback-fixed-action.png`, `02-structured-full-explanation.png`, `03-exact-return.png`, and `04-completed-next-visible.png` in `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\`.
- Combined focused comparison: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\verification-flow-montage.png`.
- Responsive evidence: `05-narrow-200-percent.png` and `06-narrow-feedback-action.png` in the same folder.
- Canonical review target: `D:\project\Kabuqina\docs\superpowers\handoffs\2026-07-23-v0.5.0-canonical-prototype-review.md`, especially section 6.
- Review evidence: `01-c-k0-static.png` through `10-legacy-timeout.png` in `D:\project\Kabuqina\.test-output\canonical-review-2026-07-23\`.
- Review evidence montage: `D:\project\Kabuqina\.test-output\canonical-review-2026-07-23\11-review-evidence-montage.jpg`.
- Post-split implementation evidence: `01-post-split-c-k0.png` through `07-post-split-narrow-return.png` in `D:\project\Kabuqina\.test-output\canonical-review-2026-07-23-post-split\`.
- Same-state pre/post split comparison: `D:\project\Kabuqina\.test-output\canonical-review-2026-07-23-post-split\08-pre-post-comparison.jpg`.
- Viewports: `1280 × 720` logical wide frame rendered in the in-app browser at `1440 × 900`; `360 × 450` CSS frame at `2×`, representing a `720px / 200%` window.
- Pixel and density normalization: both pre-split and post-split screenshots are `1440 × 900` pixels from the same in-app browser viewport. Wide comparisons use the same `1280 × 720` logical canvas and fit transform. Narrow comparisons use the same `360 × 450` CSS frame at `2×`; no resampling or cross-density normalization was required before the combined comparison.
- State: full canonical path `C-D0 → C-N0 → C-A1 → C-K0 → C-F0 → C-C0 → C-H1 → C-H2 → C-R0 → C-A1 → C-K0 → C-F1`.

## Findings

No actionable P0, P1, or P2 findings remain.

- Fonts and typography: body text is at least `14px`, status/meta text `13px`, feedback text `14px`, and learner handwriting `17px / 1.65`. Segoe UI/Microsoft YaHei provide the UI fallback; KaiTi/STKaiti is limited to the learner-owned answer. No body, feedback, annotation, or state copy is sacrificed for skeuomorphic styling.
- Spacing and layout rhythm: the wide desk is height-bound. `#c-canvas` measured `clientHeight = scrollHeight = 668` with `scrollTop = 0`; the furniture does not scroll. The notebook owns the overflow: in `C-F0`, `#c-task-scroll` measured `381px` visible against `603px` content. The page action rail remained inside the viewport with a `49px` bottom buffer.
- Colors and visual tokens: the rendered desk uses the Style Tile light tokens (`#e8dfd2` desk, `#fbf8f1` paper, `#49385e/#5a4a6a` ink, `#6b5580/#8f75a8` accent, `#d4b080` latte), approved paper noise, glass chrome, double soft shadows, and a consistent upper-left light source. The same-input comparison shows the palette and material distinction carried across without reducing contrast.
- Image quality and asset fidelity: this screen's source contract calls for CSS/DOM/lightweight vector surfaces, not raster product imagery. All interface icons use Lucide; no emoji or placeholder imagery appears. Paper texture is the approved Style Tile noise token rather than a low-quality bitmap.
- Copy and content: the three-part feedback remains exactly “已经说明清楚 / 还差一步 / 接下来试试”. The prefilled answer now reads “已保存的草稿” and the entry reads “继续作答”. Page-side help says “让小娜陪我补这一步”, while the right-bottom cup visibly changes to “咖啡杯已接住这一步”. Full explanation is split into three numbered units.
- Interaction states: `C-F0` and `C-R0` each expose one primary action, “修改答案”; `C-F1` exposes one primary action, “继续下一步”. On exact return, the original answer, feedback, and page-edge hint are preserved. Completion clears the hint and returns the cup to “安静陪着你”. Clicking “继续下一步” now opens `练习 3 · 第 3 步`, clears the answer, and reports “尚未开始”.
- Review semantics: `C-K0` is now an explicit static freeze frame: the saved answer remains unchanged and readonly, feedback stays hidden, and “正在检查…” is the disabled sole primary action. The scope ledger states that the phase enum is only a prototype fixture and that production must model orthogonal dimensions separately; it also states that canonical does not independently claim cancel/error/timeout coverage.
- Hint focus: after “再提示一点”, focus moves to the second hint message through a programmatically focusable `tabindex="-1"` target. All three H1 exits—“我先试试”, top “返回这一步”, and Escape—return to `C-R0`, focus the original answer, and preserve the page-edge hint.
- Legacy regression boundary: `W04` preserves the streamed partial response and draft when Stop is used. `W05B` preserves draft/session/return context through a network error and returns focus to the composer after same-session recovery. The new `W05D` timeout fixture preserves the same context and exposes “在同一会话重新请求”; recovery clears the fault and returns focus to the unchanged draft. `W05C` falls back to the course overview when the exact target is missing while keeping session and draft context.
- Split fidelity: the same-state combined comparison covers K0, wide F0, exact return, and 200% exact return. No visible typography, spacing, color, icon, control, paper, desk, focus-state, wrapping, crop, or composition drift was found between the combined pre-split harness and the independent canonical file.
- Responsiveness and accessibility: the `720px / 200%` frame measured `scrollWidth = clientWidth = 343`, so there is no horizontal overflow. After narrow feedback, the action rail is pinned to the visible bottom edge. Focus, readonly states, explicit labels, `aria-current`, live announcements, and reduced-motion handling remain present.
- Browser runtime: primary interactions were exercised in the in-app browser; console/runtime logs returned an empty list.

## Comparison history

### Pass 1 — blocked

- [P0] The entire desk could scroll when notebook content grew, which displaced the furniture map.
- [P0] Feedback and exact-return primary actions were part of the notebook content flow and could fall below the first viewport.
- [P1] A prefilled answer was labeled “尚未开始”.
- [P1] Page-side “问小娜” duplicated the cup entry without a clear handoff.
- [P1] The explicit full explanation rendered as one long paragraph.
- [P1] “提示已留在页边” persisted after the learner completed the step.
- [P1] The canonical flow still used warm grayscale placeholders rather than the approved Style Tile materials.

### Fixes applied

- Bound the canonical desk to `1280 × 720`, changed outer desk overflow to hidden, and moved scrolling into `.c-task-scroll`.
- Split `.c-page-main` into scrollable content plus a fixed action rail; phase rendering keeps one primary action visible.
- Derived answer state and entry copy from whether a saved draft exists.
- Renamed the page-side action and made it open the cup-owned invoke state with explicit cup status.
- Replaced the answer wall with three numbered explanation sections.
- Clear `canonicalLastHint` on successful completion and when advancing.
- Applied Style Tile paper, glass, desk, lavender ink, latte, light, noise, border, and shadow tokens.

### Pass 2 — blocked

- [P1] The visible “继续下一步” control reset the answer but left the task metadata on “第 2 步”, so the primary CTA did not fully honor its label.

### Fix applied

- Added explicit step state and updated bookmark, kicker, title, completion standard, prompt, answer state, and save status when advancing to “练习 3 · 第 3 步”.

### Pass 3 — passed

- Wide outer canvas: `668px client / 668px scroll / 0 scrollTop`.
- `C-F0`: feedback visible; “修改答案” is the sole primary action; page-side help is secondary and visible.
- `C-C0`: cup `aria-expanded=true`; status is “咖啡杯已接住这一步”; current question and answer context are preserved.
- `C-H1`: first response is a one-step hint; full explanation requires explicit selection.
- `C-H2`: three explanation sections render; hint paragraph is hidden; return action is visible.
- `C-R0`: original answer is unchanged; feedback and page hint are visible; primary action remains “修改答案”.
- `C-F1`: page hint is cleared; cup reads “安静陪着你”; the only primary action is “继续下一步”.
- Next-step CTA: bookmark/kicker/title all update to step 3; empty answer reads “尚未开始”.
- Narrow/200%: no horizontal overflow; feedback actions are visible at the viewport bottom.
- Browser console: no errors or warnings.

### Pass 4 — section 6 pre-split evidence gate passed

- Scope ledger now records both the prototype-modeling limitation and the canonical/legacy evidence boundary.
- `C-K0` is independently selectable and matches the static checking contract.
- Wide canonical path, explicit H2 request, exact answer return, completion cleanup, and step advance all passed.
- The H1 second-hint focus target and all three return exits passed keyboard/focus verification.
- `720px / 200%` path passed through feedback, cup handoff, H1/H2, and exact return with `0px` horizontal overflow.
- Legacy Stop, network error, timeout, and missing-target safe return passed with draft/session context preserved.
- Browser console: no errors or warnings.
- Per section 6, canonical/legacy file splitting and post-split smoke testing are intentionally waiting for owner confirmation of the behavior freeze.

### Pass 5 — post-split artifact gate passed

- Owner confirmed `BEHAVIOR FROZEN` for the canonical student flow and authorized structural extraction only.
- Canonical DOM/CSS/state rendering/events were extracted to `2026-07-23-v0.5.0-desk-canonical.html`; the original combined harness was archived as the legacy regression matrix.
- Same-state pre/post comparisons for K0, wide F0, exact return, and 200% exact return show no visible layout or copy drift.
- Wide `D0 → N0 → A1 → K0 → F0`, H1/H2, all three H1 exits, exact return, F1, and next-step advance passed.
- Narrow `A1 → F0 → C0 → H1/H2 → R0` passed with `0px` horizontal overflow at every sampled state.
- Focus targets, readonly/disabled states, live announcements, sole-primary-action contracts, answer preservation, hint cleanup, and step-advance semantics passed.
- Browser console: no errors or warnings.

## Open questions

- No P0, P1, or P2 design finding remains. Commit is intentionally pending separate owner authorization.
- Motion refinement can remain a later P3 art pass; it does not block the frozen learning loop.

## Implementation checklist

- Keep `#c-canvas` non-scrolling on wide canonical frames.
- Keep phase-specific unique primary actions in `#c-task-actions`.
- Preserve answer ownership, three-part feedback, explicit help escalation, exact return, and completion cleanup in production implementation.

## Follow-up polish

- [P3] A later motion pass may add a restrained cup “receiving” motion and page-return transition while respecting reduced motion.

final result: passed

---

## FE-01 rescue preview — 2026-07-23

### Comparison target

- Frozen source: `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-23-v0.5.0-desk-canonical.html`.
- React implementation: `D:\project\Kabuqina\web\src\study\desk\`.
- Development-only entry: `http://127.0.0.1:4175/__dev/desk`.
- Same-state product-canvas comparison: `D:\project\Kabuqina\.test-output\fe01-desk-rescue-2026-07-23\comparison-f0-product-1280x720.png`.
- Wide evidence: `05-react-d0-standalone.png`, `04-react-f1-standalone.png`, and `07-react-f0-canonical-1280x720.png` in `D:\project\Kabuqina\.test-output\fe01-desk-rescue-2026-07-23\`.
- Narrow evidence: `06-react-f0-narrow-720.png` in the same folder.
- Viewports: `1280 × 720` for canonical product-canvas comparison, `1440 × 900` for wide-window smoke, and `720 × 900` for the narrow contract.

### Findings and fixes

- [P1, fixed] The first preview entry rendered inside the existing main-window shell. This added a second title bar, loaded unrelated Tauri notification/approval listeners in a normal browser, and produced console errors. Direct loads of `/__dev/desk` now render a standalone dev-only surface; the existing `/study/*` product path is untouched.
- [P1, fixed] Handwritten SVG path components were replaced with the repository's existing Lucide icon set. The CSS-only paper noise remains the frozen material token, not product artwork.
- The `1280 × 720` same-state comparison preserves the frozen furniture map, notebook scale, paper/desk/glass palette, three-part feedback, fixed action rail, work folder, due box, and coffee-cup presence. No actionable P0, P1, or P2 visual drift remains in the Phase 1 preview.
- At `720 × 900`, `scrollWidth = clientWidth = 720`. “修改答案” and “让小娜陪我补这一步” remain uniquely addressable, and activating “修改答案” restores focus to the original textarea.
- A clean browser tab reported no console errors. The standalone surface begins at `top = 0` and does not contain the existing `.kq-titlebar`.
- Component coverage now exercises `overview → focused → dirty → checking → needs_revision` and the `completed → next step` transition. The full component baseline is `24 files / 108 tests`.
- Lint and production build pass. Because the preview import and direct entry are guarded by `import.meta.env.DEV`, DeskScene preview assets are absent from the production output.

### Scope boundary

This pass deliberately does not replace `StudyRoute`, connect the production study repository, or claim the full Chat/exact-return lifecycle. Those are Phase 2 integration tasks; the rescue preview is a controlled, testable implementation base.

final result: passed (Phase 1 preview only)

---

## FE-02 production Study integration — 2026-07-23

Control status: `CTL-A06a REVIEW · TAURI MATRIX DEFERRED TO PRE-ART GATE · NOT DONE`.
Independent code review has closed all P1/P2 findings. Production fixture cleanup
is complete. Real Tauri route/function acceptance remains required before `DONE`
or any higher-Gate claim and will run once after the pre-art frontend is complete.
Review scope and exit format are defined in
`docs/superpowers/handoffs/2026-07-23-v0.5.0-study-desk-production-review.md`.

### Comparison target

- Frozen visual source: `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-23-v0.5.0-desk-canonical.html`.
- Production route owner: `StudyRoute → StudyShell → StudyDeskPage → DeskScene`.
- Production data owner: the existing `StudyRepository`, quiz service, activity store, and `STUDY_LEARNING_EVENT`.
- Recovery-only draft cache: `kabuqina.study.desk-draft.v1:<spaceId>:<artifactId>`; it is not submitted learning evidence.
- Browser evidence: `01-desk-overview.png`, `02-desk-completed.png`, and `03-desk-overview-1280x720.png` in `D:\project\Kabuqina\.test-output\fe02-desk-integration-2026-07-23\`.
- Same-state, same-viewport comparison: `D:\project\Kabuqina\.test-output\fe02-desk-integration-2026-07-23\comparison-phase1-phase2-overview-1280x720.png`.

### Findings and integration checks

- The Phase 2 overview is visually unchanged from the Phase 1 standalone source at the same `1280 × 720` viewport. Furniture positions, notebook scale, paper/desk/glass palette, work folder, course books, card box, and coffee-cup placement show no actionable P0, P1, or P2 drift.
- `/study/:spaceId/practice` now gives the desk ownership of product chrome and suppresses the outer Tauri title bar on that route. Other Study pages retain the existing top bar and lifecycle navigation.
- Notebook page tabs, course books, Chat, Activity, Settings, materials, and “开新本” now route through the existing navigation and dirty-leave guard. Current course selection is disabled instead of producing a no-op announcement.
- Choice, true/false, short-answer, code, and derivation questions render through the desk. CodeMirror and derivation surfaces reuse the existing production Study components.
- “检查这一步” first flushes the current recovery draft and then submits only the current question ID. The optional backend `item_ids` subset is validated against the quiz; omitting it preserves full-quiz behavior. Future unanswered questions are not graded or recorded by the step check.
- A successful check records the existing Study activity, emits the existing learning event, keeps the learner answer visible, and renders the canonical completed page annotation. Failed save/check paths preserve the answer and expose a retry-safe inline error.
- Loads, saves, and checks are abortable and guarded against stale completion. The restored bookmark and drafts select the correct step; advancing records the new bookmark; completing the last step returns to the overview rather than looping on the same page.
- Browser path `overview → focused → dirty → checking → completed` passed. The final DOM exposed “本步学习证据已保存”, “页边批注 · 本步完成”, and “继续下一步”; browser error/warning logs were empty.

### Verification

- Web production build: passed.
- Web lint: passed.
- Web component suite: focused `4 files / 29 tests`; latest full `25 files / 116 tests` passed.
- Core quiz contract: `11 passed`.
- Desktop Study HTTP routes: `12 passed`.
- Rust Study bridge: `15 passed / 0 failed`.
- The first independent review reproduced a full-suite DeskScene timeout. After replacing timing-heavy interaction setup with contract-level events and avoiding Rust build-script contention, three consecutive standard full-Web runs passed; the final-code run is included.

### Remaining boundary

- Tutor conversation/exact-return remains a later integration phase. In Phase 2 the coffee cup uses the real `/chat` destination but does not yet carry a structured return context.
- Art resources and restrained motion remain later polish; neither blocks the real Study learning loop.

### Independent Review remediation

- [P1, fixed] Equal-value spaces revalidation no longer reconstructs the production adapter or clears completed feedback. Only a `completed` step removes its submitted answer from recovery before the learning event.
- [P1, second review fixed] Incorrect and ungraded results retain the original answer for reload and later modification. `needs_revision` now participates in dirty-leave and `beforeunload` protection, and the leave copy describes all unfinished answers rather than only unsubmitted ones.
- [P2, fixed] Duplicate `item_ids` fail closed before activity creation in Core and the Rust bridge; default full-quiz calls omit the field and explicit subsets serialize unchanged.
- [P2, fixed] Answer changes synchronously update recovery storage before the debounced save. Dirty/checking states restore `beforeunload`; confirmed navigation explicitly preserves the recovery draft in both Chinese and English copy.
- [P2, fixed] The standard Web component gate passed the earlier three consecutive full runs and the latest second-review run at `25 files / 116 tests`. Focused desk/route/shell coverage is `4 files / 29 tests`.
- Core quiz contract: `11 passed`; Desktop Study HTTP routes: `12 passed`; Rust Study bridge: `15 passed / 0 failed`.
- Web lint and production build passed; `/__dev/desk` remains absent from the production bundle.
- Real Tauri manual acceptance remains pending. The latest start attempt stopped during ignored-runtime synchronization after `1168 / 3658` files and never opened the application window; the next attempt must let synchronization finish. No manual route, five-question-type, restart, native 200%, or failure-injection claim is made here.
- [P3, closed 2026-07-24] `DeskScene` now requires a production adapter. The fixture adapter, fixture snapshots, fixture course IDs, and fixed completed answer live only behind the DEV preview module. `npm run build` scans all production JavaScript assets and fails if these markers or `/__dev/desk` leak back into the bundle.

final result: accepted for continued pre-art frontend development (the deferred real Tauri matrix blocks DONE and higher Gates)

---

## FE-03 pre-art complete frontend — 2026-07-24

Control status:
`CTL-A06b IMPLEMENTED · AUTHOR VERIFIED · UNCOMMITTED · REVIEW READY · NOT DONE`.
集中审查入口为
`docs/superpowers/handoffs/2026-07-24-v0.5.0-pre-art-frontend-review.md`。

### Product/interaction findings

- Course Chat 现在有可见、可解绑的上下文条；杯子与页内求助先显示学生可审核的问题，再把
  structured handoff 交给真实 Chat，不自动发送。
- exact return 在宽屏和窄屏恢复原课程、题目、答案、反馈和焦点；invalid target 安全回
  overview。未发送的 handoff/prompt 在真实 Tauri 重启后仍恢复。
- 制作工作夹要求显式选择真实课程材料；成果没有 typed truth 时显示空态，不从聊天文本或
  路径伪造。
- Activity 真实读取 Study activity；Chat 只展示有当前 course binding 的 sessions。两个
  read model 分别提供 loading/error/empty/retry。
- due-card surface 使用真实队列并支持 reveal/1–4/Space；失败保留当前卡。
- wide、720px 与 360px 下，Activity 不再被隐藏，utility actions 保持右对齐，工作夹和
  course invoke 可达。干净浏览器页面 console error/warning 为空。

### Verification

- TypeScript：passed。
- Web components：`30 files / 133 tests` passed。
- Lint：passed。
- Production build 与 fixture leakage gate：passed。
- Browser：wide / 720 / 360、work folder、Activity、card、invoke、exact return passed。
- Runtime sync：完整通过。
- 真实 Tauri：实际课程 route、真实 7-step quiz/10 due cards、Chat visible context/prompt、
  exact return、Activity/workfolder/card reveal、应用重启后 pending handoff recovery passed。

### Remaining acceptance boundary

- 为避免污染真实学习证据，作者未在人工 Tauri 轮中逐个提交五题型或真实卡片评分；
  自动化覆盖不能替代指定 reviewer 的真实数据矩阵。
- 未修改 Windows 系统缩放到原生 200%；360px 是 reflow proxy。
- 保存/检查失败和慢请求仍待人工故障注入。
- 最终插画、材质精修和克制动效不在 FE-03；现有 DOM/CSS surface 已可直接接入这些资产。

final result: pre-art frontend implementation passed author verification; durable commit and independent acceptance remain required

---

## FE-04 Study 小娜与材料阅读器 — 2026-07-30

### Comparison target

- Canonical source: `docs/superpowers/prototypes/2026-07-25-v0.5.0-product-canonical`.
- React preview: `/__dev/desk?fixture=f1&page=practice&panel=nana` and
  `/__dev/desk?fixture=f1&page=learn&panel=reader`.
- Same browser and same `1440 × 900` state comparisons were made for both the canonical source and React preview.

### Findings and fixes

- [P1, fixed] The first implementation made the lightweight Nana surface a full-height reader-shaped panel. It now matches the canonical cup behavior: a bounded paper panel at the lower page edge, while the current notebook remains visible and usable.
- The material reader keeps the canonical full-height right-side form, wrapped file directory, independent body scroll and notebook-visible relationship.
- Cup opening never sends automatically. Its transcript, streaming, clarification cards and session id are shared with full Chat; an unsent draft survives closing and is handed to full Chat.
- The reader resolves the local file from a trusted Study artifact, reads bounded windows, supports directory/page navigation and stores position per file without changing the learning cursor.
- The in-app browser exposed a minimum `1280 × 720` viewport despite a requested `720 × 520` override. Wide visual comparison passed; exact native minimum-window review remains part of the owner's visual pass and S11.
- Browser console contained no error or warning during the compared states.

### Verification

- Web production build: passed.
- Focused Study/Chat component tests: `5 files / 23 tests` passed after the final layout correction.
- Desktop Study route tests: `19 passed`.
- Rust `cargo check`: passed after the existing Tauri build-directory lock cleared. The separate temporary check had exhausted disk space while scanning bundled runtime resources; its exact temporary target was removed afterward.

final result: passed for S6/S9 implementation; exact 720 × 520 remains under S11

---

## FE-05 Study S3B 共享位置与继续书签 — 2026-07-30

### Comparison target

- Source visual truth: `docs/superpowers/prototypes/2026-07-25-v0.5.0-product-canonical`, live Study notebook header and its two-line continue bookmark.
- Implementation: `/__dev/desk?fixture=f0&page=practice&bookmark=revision`.
- In-app browser comparison at the same desktop viewport (`1280 × 720`, device scale 1); source and implementation captures were emitted together. The focused region was the notebook header containing the five page labels and bookmark because S3B does not change body layout or assets.

### Findings and comparison history

- [P2, fixed] First capture showed `继续：继续修改：0/0 是什么`. The state projection had included a verb already supplied by the notebook component, causing duplicated hierarchy and a longer first line.
- Fix: state-specific main copy is now `知识核 · 草稿/待修改/检查中`; the second line carries outline range, mode and state. Post-fix capture shows `继续：0/0 是什么 · 待修改` above `第一章 · 极限 · 练习 · 待修改`, with the five labels unchanged and no overlap.
- Typography, spacing, colors, paper/shadow tokens, icons and content density continue to use the existing canonical desk components. No image or brand asset changed.
- The implementation keeps the canonical warm bordered bookmark and right-aligned placement. Its state copy is intentionally more explicit than the static prototype because it projects real recovery state.

### Verification

- Full Web suite: `46 files / 226 tests` passed.
- Production Web build and fixture-leakage gate: passed.
- Focused S3B contracts cover cross-page shared core, per-core exercise recovery, honest no-exercise state, course isolation, stale-core degradation and bookmark state updates.

final result: passed

---

## FE-06 Study 练习页文案与批注收敛 — 2026-07-30

### Comparison target

- Source visual truth: `docs/superpowers/prototypes/2026-07-25-v0.5.0-product-canonical`,
  J2 的练习检查状态，并应用本次 owner override（题目直接作为标题、单条页边批注、保存答案）。
- Source capture: `artifacts/design-qa/study-practice-revision-source.png`.
- Implementation capture: `artifacts/design-qa/study-practice-revision-implementation.png`.
- Combined comparison: `artifacts/design-qa/study-practice-revision-comparison.png`.
- Viewport/state: both captures use `1280 × 720` CSS px, device scale `1.25`, and
  `1600 × 900` PNG pixels; both show the same exercise and `needs_revision` state.

### Findings and comparison history

- [P1, fixed] The implementation still led with the legacy paraphrase
  `解释为什么不能直接代入`, pushing the real question below the completion standard. The
  paraphrase is no longer rendered; the complete exercise prompt is now the only H2, followed by
  `完成标准` and `我的答案`.
- [P1, fixed] The prior feedback surface simultaneously rendered `已经说明清楚`, `还差一步`
  and `接下来试试`. It now renders exactly one annotation selected by the check result. Completed,
  revision and next-step states remain distinct contract values, but only the current one is visible.
- [P1, fixed] `修改答案` described an unlock action rather than the user's intended commit. In a
  revision state the answer remains editable; `保存答案` flushes the current draft, then exposes
  `检查这一步`. Saving does not submit, grade or mark the exercise correct.
- [P2, fixed] The canonical source still had a second `小娜留在页边` note above the answer in the
  same state. It was removed so the single `页边批注` remains the only feedback object.
- Fonts/typography: the question is the largest exercise-page text and retains the canonical display
  hierarchy. Spacing/layout: question → standard → answer → one annotation remains readable without
  overflow at the compared viewport. Colors/tokens and icons stay on the existing Shell desk system.
  No raster, logo or decorative asset changed. Copy now matches the owner decision.
- Focused-region evidence was required because the decisive differences are all inside the exercise
  body; the combined image compares that region at identical CSS size and density. The production
  Shell intentionally omits the older prototype's duplicate course heading and retains the existing
  right-side reader and review objects.

### Interaction and verification

- Edited the answer while `needs_revision`; the chosen margin annotation stayed visible.
- Activated `保存答案`; the draft persisted and the UI moved to `检查这一步` without grading.
- In-app browser console errors/warnings: none.
- Full Web component suite: `46 files / 227 tests` passed with two workers.
- Web production build and fixture-leakage gate: passed.
- Canonical prototype build: passed.

final result: passed

---

## FE-07 Study 练习页提示收敛 — 2026-07-30

### Comparison target

- Source visual truth: `docs/superpowers/prototypes/2026-07-25-v0.5.0-product-canonical`,
  combined with the owner override that the auxiliary fold is named `提示` and contains only one clue.
- Source capture: `artifacts/design-qa/study-practice-revision-source.png`.
- Implementation capture: `artifacts/design-qa/study-practice-hint-implementation.png`.
- Combined comparison: `artifacts/design-qa/study-practice-hint-comparison.png`.
- Implementation viewport/state: `1280 × 720` CSS px, device scale `1.25`, `1280 × 720`
  PNG capture, practice page in `needs_revision` with the hint expanded.

### Findings and fixes

- [P1, fixed] The answer block repeated the state as `我的草稿` beside `我的答案`. The answer
  block now has one stable heading, `我的答案`; persistence remains communicated by the existing
  status line below the editor.
- [P1, fixed] `本题参考` implied a solution or explanatory reference. It is now `提示`, and its
  expanded body contains exactly one short clue: `x² − 1 = (x − 1)(x + 1)`.
- [P1, fixed] The data contract no longer carries a reference summary. Real exercises project a
  short tag-based clue (or a neutral keyword fallback) and never expose the worked explanation,
  answer or rubric through this fold.
- Typography, paper tokens, spacing and the existing right-side fold placement remain within the
  established Shell/Study desk system. No visual asset changed.

### Interaction and verification

- In-app browser: `我的草稿` count `0`, `提示` count `1`, `本题参考` count `0`.
- Expanded `提示`: concise clue count `1`; worked-explanation count `0`.
- Browser console errors/warnings: none (Vite debug and React development-info messages only).
- Focused Study desk tests: `2 files / 19 tests` passed.
- Previously flaky Nana panel test rerun in isolation: `1 file / 1 test` passed.
- Web production build and fixture-leakage gate: passed.

final result: passed

---

## FE-08 Study 练习页去考核化与单一求助入口 — 2026-07-30

### Comparison target

- Source visual truth: `docs/superpowers/prototypes/2026-07-25-v0.5.0-product-canonical`,
  with owner overrides: remove the completion-standard block, rename the feedback heading to
  `小娜批注`, and keep `碰杯问小娜` as the only Nana entry on the practice page.
- Source capture: `artifacts/design-qa/study-practice-revision-source.png`.
- Implementation capture: `artifacts/design-qa/study-practice-clean-answer-implementation.png`.
- Combined comparison: `artifacts/design-qa/study-practice-clean-answer-comparison.png`.
- Viewport/state: `1280 × 720` CSS px at device scale `1.25`, practice `needs_revision` state.

### Findings and fixes

- [P1, fixed] The assessment-like `完成标准` block sat between a single exercise and its answer.
  It has been removed from rendering, the front-end `StudyStep` contract, fixture projection,
  adapter projection and CSS; grading metadata remains internal to the checker.
- [P1, fixed] The generic heading `页边批注` is now `小娜批注`, including its accessible name
  and Chat-return location copy, so the feedback has a clear speaker.
- [P1, fixed] `让小娜陪我补这一步` duplicated the desk cup. The inline button and notebook prop
  were removed; `碰杯问小娜` remains visible and successfully opens the Nana surface with the
  current exercise, answer and feedback context.
- The result reads as question → answer → Nana annotation, with no empty space left by the removed
  standard and no second conversation action competing with save/check.

### Interaction and verification

- In-app browser counts: completion standard `0`, old annotation heading `0`, `小娜批注` `1`,
  inline tutor action `0`, cup entry `1`.
- Activated `碰杯问小娜`; the Nana panel opened and retained the current practice context.
- Browser console errors/warnings: none (Vite debug and React development-info messages only).
- Focused Study desk tests: `2 files / 19 tests` passed.
- Web production build and fixture-leakage gate: passed.

final result: passed
