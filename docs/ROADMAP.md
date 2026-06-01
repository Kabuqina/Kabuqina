# Kabuqina roadmap

**Last updated:** 2026-05-31

This file tracks **intentional, product-level** work. Bugfix triage lives in issues and changelogs (for example `CHANGES_*.md` in the repo root).

---

## 1. Shell chat + messaging gateway (**shipped baseline**)

**Status:** baseline delivered (ongoing polish)

Kabuqina today includes:

- **Dedicated shell chat** at **`/chat`** (`web/src/chat/*`), backed by Tauri **`invoke`** commands that proxy to the embedded Hermes loopback (`tauri/src/chat.rs`). Sessions list / messages / stop mirror Hermes desk APIs.
- **Messaging gateway** as a **second supervised Python process** (`python -m gateway.run`, `tauri/src/gateway_supervisor.rs`), auto-start optional on cold launch when `hermes-home/.env` contains messaging credentials, manual controls in Settings.
- **Onboarding / Settings UX** for **Weixin**, **QQ Bot**, **Feishu/Lark**, and **Telegram** (token), plus pairing helpers where Hermes requires them (`pairing.rs`, shell blocks).

The **`strip_shims`** overlay still stubs **`gateway.run.main`** inside the **Hermes web child** so the dashboard never accidentally hosts the gateway entrypoint; the **real** gateway module loads only in the **separate** gateway OS process. See `docs/architecture.md` §Process model.

**Remaining themes on this track** (examples — not ordered backlog):

- UX polish for `/chat` (streaming surfaces, attachments edge cases, error copy).
- Keep gateway flows aligned when **`hermes/`** submodule moves (re-run `python/build_bundle.ps1`; watch upstream adapter breaks).
- Optional deeper Hermes-web parity only where product asks for it — **without** folding unrelated onboarding fixes into chat regressions.

**References**

- `docs/architecture.md` — processes, `/chat` proxy, gateway boundaries.
- `README.md` — user-facing gateway summary.

---

## 2. Other ongoing themes (not a full backlog)

- **Onboarding & provider validation** — Tauri IPC vs post-`location.replace` behavior; keep validation on a path that can reach Rust or a trusted local proxy (`CHANGES_2026-04-21.md`).
- **“Configured” detection** — align keyring, `settings.json`, and UI so users are not sent past onboarding with stale state.
- **Build / Windows** — file locks during `cargo` + bundled Python (e.g. `os error 32`); antivirus exclusions; `build_bundle.ps1` hardening (see `CHANGES_2026-04-21.md` notes).

---

## 3. Student Workbench Priority Order

**Status:** active product direction

Kabuqina should grow as a student workbench, not only as an academic document
generator. The near-term priority order is:

```text
1. Live Presentation
2. Generated Deliverables
3. Learning
```

### Phase 1 — Live Presentation

Live Presentation is the user's first trust surface. Before generated files or
learning modes can feel reliable, chat must clearly display what the agent reads
and says.

Focus areas:

- Markdown quality in chat.
- LaTeX/math rendering for inline and block formulas.
- Code and table rendering.
- Source references: file, page, slide, sheet, `read_id`.
- Parser warnings and uncertainty display.
- Long-running tool progress and resilient in-flight turn display.
- Copy affordances for formulas, code, tables, citations, and snippets.

Reference: `docs/chat-display-layer.md`.

### Phase 2 — Generated Deliverables

Generated Deliverables turn reliable source material into files. This phase
builds on Live Presentation because users need to inspect materials, warnings,
outlines, formulas, and evidence before trusting a generated artifact.

Focus areas:

- Read cache and Material Index handoff.
- PPT workflow and outline review.
- Future DOCX/report workflow.
- Formula, table, figure, screenshot, citation reuse.
- Writer branches for concrete file formats.
- Optional advanced academic plugins such as LaTeX/MiKTeX adapters.

Reference: `docs/file-generation-pipeline.md`, `docs/read-layer-plan.md`,
`docs/material-index.md`.

### Phase 3 — Learning

Learning is the broadest and most personal surface. It should come after the
display and deliverable foundations because learning interactions depend on
accurate reading, clear rendering, source references, and trustworthy outputs.

Focus areas:

- Explain.
- Step-by-step derivation.
- Hint mode.
- Quiz / check understanding.
- Formula-to-code and code-to-formula bridges.
- Review cards.
- Presentation practice.
- Lightweight, transparent student state.

Reference: `docs/learning-layer.md`.

This order does not make Learning less important. It treats Learning as the
highest-level product behavior, built on top of reliable Read, Display, and
Deliverable foundations.

---

## 简体中文摘要

**壳内 `/chat` 与消息网关** 已在当前桌面产品中落地：`invoke` → Rust → Hermes loopback；网关为独立 **`gateway.run`** 子进程；微信 / QQ / 飞书·Lark / Telegram 的配置入口在引导与设置中。**strip_shims** 仅阻止「Hermes Web 主进程」误跑网关入口，与第二条网关进程并存——详见 **`docs/architecture.md`**。

当前学生工作台方向按三阶段推进：**Live Presentation → Generated Deliverables → Learning**。先把聊天里的 Markdown、公式、代码、表格、来源引用、读取警告与长任务展示做好；再推进 PPT / 报告 / 文档生成；最后在可靠展示和生成基础上发展解释、提示、测验、推导、公式代码互转等学习交互。不要把 onboarding / Keyring 等问题与 chat / gateway 缺陷混成同一类「顺带修」。

上方英文小节为正式范围说明；本文件与 `docs/architecture.md` 随实现更新。
