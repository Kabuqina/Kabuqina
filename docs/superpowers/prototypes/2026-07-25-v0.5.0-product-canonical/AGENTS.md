# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Kabuqina v0.5.0 product prototype decisions

- Materiality-first (owner direction, 2026-07-25): design must be guided by 物化 —
  interface elements are desk objects with position, material, and small behaviors —
  not deferred to a later art pass. The 2026-07-07 `notebook-ia.html` prototype is the
  object-vocabulary source of truth (bookend course tabs, lamp, bookmark, looseleaf,
  card stack, branded Nana cup); this canonical prototype remains the IA and boundary
  source of truth. Reconcile the two rather than choosing one.
- Desk lamp = theme switch (owner confirmed): the lamp sits top-right in the shell and
  toggles light/dark; dark mode reads as "night with the lamp on" (warm glow falls on
  the desk from the lamp corner). Settings carries an equivalent mirror control. All
  colors must go through the dual-theme design tokens in `src/styles.css` — no new
  hardcoded hex values in either theme.
- Agreed in principle, awaiting their own design pass (do not implement casually):
  bookend course tabs replacing the permanent left course/material rail (this amends
  the frozen Study desk master); a 杂记本 course-less Study container for reviewed
  saves that fit no course yet (explicit save only, narrowly defined); restoring the
  branded CSS Nana cup art; Anki key bindings in review; looseleaf physicality for
  pencil drafts; a per-object truth-source table as an engineering norm.

- Preserve the 2026-07-23 Study desk composition and warm paper / muted purple
  visual language as the source of truth; this prototype extends it rather than
  replacing it.
- Study and Studio are the two product domains and primary destinations:
  Study owns input/internalization and learning evidence; Studio owns
  output/expression and projects. Chat is a cross-domain interaction layer and
  Activity is a cross-domain state layer.
- Full Chat is an intentionally minimal free-conversation space. Opening Chat
  from global navigation starts an unbound free conversation; Study and Studio
  conversations only appear as ordinary, low-emphasis items in one unified
  history and enter their scoped context only after explicit selection.
- Study and Studio both use the bottom-right Nana cup to open the same lightweight
  contextual chat panel without leaving the current workspace. The panel and
  full Chat share session, context, transcript, and composer truth; opening the
  full view is always explicit.
- Do not use prominent Study / Studio / General scope tabs, domain dashboards,
  context rails, or special sections in full Chat. For a selected scoped
  conversation, show only the minimal provenance and return action required for
  the current conversation.
- The prototype demonstrates J1-J5 end to end: first course, Study to Chat and
  back, Chat to a reviewable Study draft, Study to a reviewed Studio
  SourceSnapshot, and honest Study/Studio recovery.
- Studio is intentionally limited to the overall shell, Project container,
  source boundary, and cross-domain connection. Do not make it a PPT generator
  or freeze its detailed authoring surface before a separate Studio design pass.
- Prototype simulations are labelled. They must not imply that Tutor,
  SourceSnapshot persistence, Studio authoring, gateway profiles, or release
  validation already exist in production.
