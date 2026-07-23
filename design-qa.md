# Design QA — Kabuqina v0.5.0 学习书桌原型

## Comparison target

- Source visual truth: `D:\project\Kabuqina\docs\superpowers\prototypes\Style Tile.html` and the four frozen desk experience/vision documents named in the task.
- Source screenshot: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\source-style-tile.png`.
- Rendered implementation: `D:\project\Kabuqina\docs\superpowers\prototypes\2026-07-18-v0.5.0-study-chat-low-fi.html`.
- Implementation overview screenshot: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\00-desk-overview.png`.
- Same-input full-view comparison: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\comparison-style-tile-desk.png`.
- Focused flow evidence: `01-feedback-fixed-action.png`, `02-structured-full-explanation.png`, `03-exact-return.png`, and `04-completed-next-visible.png` in `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\`.
- Combined focused comparison: `D:\project\Kabuqina\.test-output\design-qa\v0.5.0-desk\verification-flow-montage.png`.
- Responsive evidence: `05-narrow-200-percent.png` and `06-narrow-feedback-action.png` in the same folder.
- Viewports: `1280 × 720` logical wide frame rendered in the in-app browser at `1440 × 900`; `360 × 450` CSS frame at `2×`, representing a `720px / 200%` window.
- State: full canonical path `C-D0 → C-N0 → C-A1 → C-K0 → C-F0 → C-C0 → C-H1 → C-H2 → C-R0 → C-A1 → C-K0 → C-F1`.

## Findings

No actionable P0, P1, or P2 findings remain.

- Fonts and typography: body text is at least `14px`, status/meta text `13px`, feedback text `14px`, and learner handwriting `17px / 1.65`. Segoe UI/Microsoft YaHei provide the UI fallback; KaiTi/STKaiti is limited to the learner-owned answer. No body, feedback, annotation, or state copy is sacrificed for skeuomorphic styling.
- Spacing and layout rhythm: the wide desk is height-bound. `#c-canvas` measured `clientHeight = scrollHeight = 668` with `scrollTop = 0`; the furniture does not scroll. The notebook owns the overflow: in `C-F0`, `#c-task-scroll` measured `381px` visible against `603px` content. The page action rail remained inside the viewport with a `49px` bottom buffer.
- Colors and visual tokens: the rendered desk uses the Style Tile light tokens (`#e8dfd2` desk, `#fbf8f1` paper, `#49385e/#5a4a6a` ink, `#6b5580/#8f75a8` accent, `#d4b080` latte), approved paper noise, glass chrome, double soft shadows, and a consistent upper-left light source. The same-input comparison shows the palette and material distinction carried across without reducing contrast.
- Image quality and asset fidelity: this screen's source contract calls for CSS/DOM/lightweight vector surfaces, not raster product imagery. All interface icons use Lucide; no emoji or placeholder imagery appears. Paper texture is the approved Style Tile noise token rather than a low-quality bitmap.
- Copy and content: the three-part feedback remains exactly “已经说明清楚 / 还差一步 / 接下来试试”. The prefilled answer now reads “已保存的草稿” and the entry reads “继续作答”. Page-side help says “让小娜陪我补这一步”, while the right-bottom cup visibly changes to “咖啡杯已接住这一步”. Full explanation is split into three numbered units.
- Interaction states: `C-F0` and `C-R0` each expose one primary action, “修改答案”; `C-F1` exposes one primary action, “继续下一步”. On exact return, the original answer, feedback, and page-edge hint are preserved. Completion clears the hint and returns the cup to “安静陪着你”. Clicking “继续下一步” now opens `练习 3 · 第 3 步`, clears the answer, and reports “尚未开始”.
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

## Open questions

- None for this iteration. Motion refinement can remain a later P3 art pass; it does not block the frozen learning loop.

## Implementation checklist

- Keep `#c-canvas` non-scrolling on wide canonical frames.
- Keep phase-specific unique primary actions in `#c-task-actions`.
- Preserve answer ownership, three-part feedback, explicit help escalation, exact return, and completion cleanup in production implementation.

## Follow-up polish

- [P3] A later motion pass may add a restrained cup “receiving” motion and page-return transition while respecting reduced motion.

final result: passed
