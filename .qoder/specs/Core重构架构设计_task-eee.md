# Kabuqina Core Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `hermes_core/` 从上游冻结快照逐步演进为 Kabuqina 自有 core，同时保证桌面 chat、gateway、cron、工具调用、bundle 构建和用户数据迁移不中断。

**Architecture:** 本计划采用“兼容门面优先、叶子模块先拆、核心热路径后拆、删除最后做”的迁移方式。新命名与新模块先通过 adapter/facade 引入，旧 import path、旧环境变量和旧用户目录在完整迁移期内继续可用，避免一次性全局替换造成不可定位的回归。

**Tech Stack:** Python 3.11、Hermes/Kabuqina core、FastAPI desktop API、Tauri 2/Rust、React/Vite、Windows Credential Manager、PowerShell 7。

---

## 当前判断

这份重构方向成立：当前 `hermes_core/` 仍包含上游大量非桌面学生助手所需的目录，例如 TUI、ACP、website、plugins、RL/benchmark 环境和多余 gateway 平台；同时 `run_agent.py`、`hermes_cli/config.py`、`hermes_cli/web_server.py`、`tools/document_tools.py` 等文件已经大到不利于长期演进。

但原计划的执行顺序风险过高，尤其是第一步同时做包重命名、环境变量重命名、路径迁移、Python overlay 改写和 bundle 脚本改写。当前仓库中 `run_agent`、`AIAgent`、`hermes_cli`、`HERMES_HOME`、`HERMESDESK_*` 等引用覆盖 core、Python desktop layer、Rust shell、web shell、测试和构建脚本。第一步全局替换会让失败点过多，难以判断是 import、配置、bundle、用户数据还是运行时路径导致的故障。

新的计划把“目标架构”和“可执行迁移路径”分开：目标结构仍以 `kabuqina_core`、`agent/`、`providers/`、`context/`、`prompts/`、`tools/academic/` 等为长期方向；实际提交按兼容层、低风险拆分、核心拆分、删除、最终重命名推进。

## 不变量

整个重构期间必须保持以下契约可用：

- `from run_agent import AIAgent` 继续可用，直到所有 desktop/gateway/test 入口改完并完成一个版本周期。
- `AIAgent.run_conversation(...)` 的外部行为不因文件拆分改变。
- `desktop_entrypoint.py` 在 overlay 安装顺序不变的前提下启动 Hermes/Kabuqina web server。
- gateway child 与 web child 仍是两个进程，不依赖共享内存。
- `HERMES_HOME`、`HERMES_WORKSPACE`、`HERMES_TIMEZONE`、`HERMESDESK_*` 在迁移期继续被读取；新变量 `KABUQINA_HOME`、`KABUQINA_WORKSPACE`、`KABUQINA_TIMEZONE`、`KABUQINA_*` 只作为优先值。
- 旧用户目录 `%LOCALAPPDATA%\com.kabuqina.app\hermes-home\` 在迁移期继续可读。
- Cron、gateway、chat、file/web/document tools 的 smoke path 每个阶段都能跑通。

## 目标模块结构

长期目标可以仍然是下面的结构，但不要通过一次性移动完成：

```text
kabuqina_core/
├── kq_constants.py
├── kq_logging.py
├── kq_state.py
├── kq_time.py
├── agent/
│   ├── __init__.py
│   ├── loop.py
│   ├── tool_dispatch.py
│   ├── message_manager.py
│   ├── response_handler.py
│   ├── openai_client.py
│   └── usage.py
├── providers/
├── context/
├── prompts/
├── tools/
│   ├── file/
│   ├── web/
│   ├── terminal/
│   ├── document/
│   ├── academic/
│   ├── media/
│   ├── system/
│   ├── skill/
│   └── mcp/
├── gateway/
├── cron/
├── web_server/
├── config/
├── skills/
├── environments/
└── tests/
```

迁移期间允许同时存在旧路径和新路径。每个旧路径模块应在对应新路径稳定后变成薄 wrapper，并明确删除条件。

## 阶段边界

### Phase 0: Baseline 与兼容策略

本阶段不做大规模移动，只建立测试护栏和兼容规则。

**Files:**
- Create: `hermes_core/tests/kabuqina/test_compat_imports.py`
- Create: `python/tests/test_env_compat.py`
- Modify: `python/src/desktop_entrypoint.py`
- Modify: `python/src/desk_server/chat_core.py`
- Modify: `python/overlays/desktop_llm_config.py`
- Modify: `python/overlays/default_toolset.py`
- Modify: `python/overlays/workspace_jail.py`
- Modify: `tauri/src/main.rs` or the current Tauri command/supervisor modules that set Python child env
- Modify: `DECISIONS.md`

- [ ] **Step 1: Record the compatibility decision**

Append this decision to `DECISIONS.md`:

```markdown
## 2026-06-16: Kabuqina core refactor compatibility window

Kabuqina will introduce new `KABUQINA_*` environment variables, `kabuqina_core` naming, and smaller core modules behind compatibility wrappers. During the migration window, old `HERMES_*`, `HERMESDESK_*`, `run_agent`, and `hermes_cli` entrypoints remain supported so desktop chat, gateway, cron, tests, and bundled runtime can be migrated independently.

Deletion of old names requires:
- one complete green regression pass after all internal callers use the new names;
- a user-data migration dry run;
- explicit removal notes in this file.
```

- [ ] **Step 2: Add import compatibility tests**

Create `hermes_core/tests/kabuqina/test_compat_imports.py`:

```python
def test_run_agent_still_exports_ai_agent():
    from run_agent import AIAgent

    assert AIAgent.__name__ == "AIAgent"


def test_legacy_core_modules_still_import():
    import hermes_constants
    import hermes_logging
    import hermes_state
    import hermes_time

    assert hermes_constants is not None
    assert hermes_logging is not None
    assert hermes_state is not None
    assert hermes_time is not None
```

- [ ] **Step 3: Run the compatibility tests**

Run:

```powershell
cd hermes_core
python -m pytest tests/kabuqina/test_compat_imports.py -q
cd ..
```

Expected: PASS before and after each later phase.

- [ ] **Step 4: Add env precedence tests**

Create `python/tests/test_env_compat.py`:

```python
import os
import unittest
from unittest.mock import patch


def read_preferred_env(new_name: str, old_name: str, default: str | None = None) -> str | None:
    return os.environ.get(new_name) or os.environ.get(old_name) or default


class EnvCompatTests(unittest.TestCase):
    def test_new_env_wins_over_old_env(self):
        with patch.dict(os.environ, {"KABUQINA_HOME": "new-home", "HERMES_HOME": "old-home"}, clear=True):
            self.assertEqual(read_preferred_env("KABUQINA_HOME", "HERMES_HOME"), "new-home")

    def test_old_env_is_still_supported(self):
        with patch.dict(os.environ, {"HERMES_HOME": "old-home"}, clear=True):
            self.assertEqual(read_preferred_env("KABUQINA_HOME", "HERMES_HOME"), "old-home")

    def test_default_is_used_when_neither_exists(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(read_preferred_env("KABUQINA_HOME", "HERMES_HOME", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Replace duplicated env reads with a helper**

Implement a shared helper in the most local existing Python policy/config module, preferably `python/src/gateway_policy.py` if it already owns platform feature flags, or create `python/src/env_compat.py` if no suitable helper exists:

```python
from __future__ import annotations

import os


def get_env(new_name: str, old_name: str, default: str | None = None) -> str | None:
    return os.environ.get(new_name) or os.environ.get(old_name) or default


def get_bool_env(new_name: str, old_name: str, default: bool = False) -> bool:
    value = get_env(new_name, old_name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
```

Update Python desktop/overlay env reads to call this helper for:

```text
KABUQINA_HOME / HERMES_HOME
KABUQINA_WORKSPACE / HERMES_WORKSPACE
KABUQINA_TIMEZONE / HERMES_TIMEZONE
KABUQINA_POWER_USER / HERMESDESK_POWER_USER
KABUQINA_OVERLAY_LENIENT / HERMESDESK_OVERLAY_LENIENT
```

- [ ] **Step 6: Run Phase 0 verification**

Run:

```powershell
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
cd hermes_core; python -m pytest tests/kabuqina/test_compat_imports.py -q; cd ..
cd tauri; cargo check; cd ..
```

Expected: all commands pass. If `pytest` is unavailable in the active environment, use the existing project test runner that already executes `hermes_core/tests`.

- [ ] **Step 7: Commit Phase 0**

```powershell
git add DECISIONS.md hermes_core/tests/kabuqina/test_compat_imports.py python/tests/test_env_compat.py python/src python/overlays tauri/src
git commit -m "chore: add core refactor compatibility guards"
```

### Phase 1: Kabuqina Facade Without Moving Core

Introduce new names without deleting old names.

**Files:**
- Create: `hermes_core/kabuqina_core/__init__.py`
- Create: `hermes_core/kabuqina_core/agent/__init__.py`
- Create: `hermes_core/kabuqina_core/config/__init__.py`
- Create: `hermes_core/kabuqina_core/web_server/__init__.py`
- Test: `hermes_core/tests/kabuqina/test_kabuqina_facade.py`

- [ ] **Step 1: Add facade package**

Create `hermes_core/kabuqina_core/__init__.py`:

```python
"""Kabuqina-owned facade over the legacy Hermes core during migration."""

__all__ = ["agent"]
```

Create `hermes_core/kabuqina_core/agent/__init__.py`:

```python
"""Agent facade for Kabuqina callers."""

from run_agent import AIAgent

__all__ = ["AIAgent"]
```

Create `hermes_core/kabuqina_core/config/__init__.py`:

```python
"""Config facade for Kabuqina callers."""

from hermes_cli.config import load_config, save_config

__all__ = ["load_config", "save_config"]
```

Create `hermes_core/kabuqina_core/web_server/__init__.py`:

```python
"""Web server facade for Kabuqina callers."""

from hermes_cli.web_server import app

__all__ = ["app"]
```

- [ ] **Step 2: Add facade tests**

Create `hermes_core/tests/kabuqina/test_kabuqina_facade.py`:

```python
def test_kabuqina_agent_facade_exports_ai_agent():
    from kabuqina_core.agent import AIAgent
    from run_agent import AIAgent as LegacyAIAgent

    assert AIAgent is LegacyAIAgent


def test_kabuqina_config_facade_exports_config_functions():
    from kabuqina_core.config import load_config, save_config

    assert callable(load_config)
    assert callable(save_config)
```

- [ ] **Step 3: Run facade tests**

Run:

```powershell
cd hermes_core
python -m pytest tests/kabuqina/test_kabuqina_facade.py tests/kabuqina/test_compat_imports.py -q
cd ..
```

Expected: PASS.

- [ ] **Step 4: Commit Phase 1**

```powershell
git add hermes_core/kabuqina_core hermes_core/tests/kabuqina
git commit -m "feat: add kabuqina core facade"
```

### Phase 2: Document Tools Split

Split `tools/document_tools.py` first because it is a leafier module than the agent loop and directly supports the academic assistant roadmap.

**Files:**
- Create: `hermes_core/tools/document/__init__.py`
- Create: `hermes_core/tools/document/pdf_writer.py`
- Create: `hermes_core/tools/document/pptx_writer.py`
- Create: `hermes_core/tools/document/docx_writer.py`
- Create: `hermes_core/tools/document/templates.py`
- Modify: `hermes_core/tools/document_tools.py`
- Test: existing document tool tests under `hermes_core/tests/` plus any Kabuqina PPT/document tests already present

- [ ] **Step 1: Identify top-level symbols in document_tools**

Run:

```powershell
cd hermes_core
python -c "import ast; from pathlib import Path; tree = ast.parse(Path('tools/document_tools.py').read_text(encoding='utf-8')); [print(type(node).__name__, node.name, node.lineno) for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]"
cd ..
```

Expected: a symbol inventory used to decide which symbols move to `pdf_writer.py`, `pptx_writer.py`, `docx_writer.py`, and `templates.py`.

- [ ] **Step 2: Move template-only data first**

Move PDF/PPTX template constants and small template helper classes to `hermes_core/tools/document/templates.py`. Keep the old imports in `document_tools.py`:

```python
from tools.document.templates import _PDF_TEMPLATES, _PptxTheme
```

If a moved symbol is intentionally private, keep its original name during the first split to avoid unrelated behavior changes.

- [ ] **Step 3: Move one output format at a time**

Move PDF generation helpers to `pdf_writer.py`, then run tests. Move PPTX helpers to `pptx_writer.py`, then run tests. Move DOCX helpers to `docx_writer.py`, then run tests.

Each moved module should expose only the symbols `document_tools.py` already used:

```python
from tools.document.pdf_writer import create_pdf_document
from tools.document.pptx_writer import create_pptx_document
from tools.document.docx_writer import create_docx_document
```

Use the real existing function names from the inventory step; do not rename public functions during this phase.

- [ ] **Step 4: Keep document_tools as wrapper**

After moving implementation, `hermes_core/tools/document_tools.py` should remain import-compatible and re-export the public tool functions currently registered by the tool registry.

- [ ] **Step 5: Run Phase 2 verification**

Run:

```powershell
cd hermes_core
python -m pytest tests -q -k "document or ppt or pdf or docx"
python -m pytest tests/kabuqina/test_compat_imports.py -q
cd ..
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
```

Expected: document-related tests and compatibility tests pass.

- [ ] **Step 6: Commit Phase 2**

```powershell
git add hermes_core/tools/document hermes_core/tools/document_tools.py hermes_core/tests
git commit -m "refactor: split document tool writers"
```

### Phase 3: Provider Package Extraction

Move provider adapters out of the agent area before touching `run_agent.py` internals.

**Files:**
- Create: `hermes_core/providers/__init__.py`
- Create: `hermes_core/providers/base.py`
- Create: `hermes_core/providers/chat_completions.py`
- Create: `hermes_core/providers/anthropic.py`
- Create: `hermes_core/providers/gemini.py`
- Create: `hermes_core/providers/model_metadata.py`
- Create: `hermes_core/providers/credential_pool.py`
- Create: `hermes_core/providers/retry.py`
- Create: `hermes_core/providers/error_classifier.py`
- Create: `hermes_core/providers/image_routing.py`
- Modify: old provider files under `hermes_core/agent/` to re-export from `providers`
- Test: provider and run_agent tests under `hermes_core/tests/`

- [ ] **Step 1: Build provider inventory**

Run:

```powershell
rg -n "anthropic_adapter|gemini_native_adapter|model_metadata|credential_pool|credential_sources|retry_utils|nous_rate_guard|rate_limit_tracker|error_classifier|image_routing|image_gen_provider|image_gen_registry|transports" hermes_core -g "*.py"
```

Expected: list of imports that must remain valid through wrappers.

- [ ] **Step 2: Move files without renaming symbols**

Move files mechanically, then leave wrappers at old paths. Example wrapper:

```python
from providers.anthropic import *  # noqa: F401,F403
```

Do not combine `credential_pool.py` with `credential_sources.py` until both files have tests passing in their new location.

- [ ] **Step 3: Update internal imports gradually**

Change imports in `run_agent.py` and nearby modules from old provider locations to new `providers.*` locations only after wrappers pass tests.

- [ ] **Step 4: Run Phase 3 verification**

Run:

```powershell
cd hermes_core
python -m pytest tests/run_agent tests/agent -q
python -m pytest tests/kabuqina -q
cd ..
```

Expected: run_agent and provider-adjacent tests pass.

- [ ] **Step 5: Commit Phase 3**

```powershell
git add hermes_core/providers hermes_core/agent hermes_core/run_agent.py hermes_core/tests
git commit -m "refactor: extract provider adapters"
```

### Phase 4: Config and Web Server Package Split

Split large CLI modules into packages while keeping `hermes_cli.config` and `hermes_cli.web_server` import-compatible.

**Files:**
- Create: `hermes_core/config/__init__.py`
- Create: `hermes_core/config/loader.py`
- Create: `hermes_core/config/env_loader.py`
- Create: `hermes_core/config/paths.py`
- Create: `hermes_core/config/profiles.py`
- Create: `hermes_core/config/models.py`
- Create: `hermes_core/web_server/__init__.py`
- Create: `hermes_core/web_server/app.py`
- Create: `hermes_core/web_server/chat_api.py`
- Create: `hermes_core/web_server/desk_api.py`
- Create: `hermes_core/web_server/session_api.py`
- Create: `hermes_core/web_server/voice_api.py`
- Create: `hermes_core/web_server/static_server.py`
- Modify: `hermes_core/hermes_cli/config.py`
- Modify: `hermes_core/hermes_cli/web_server.py`
- Modify: Python desktop imports after wrappers are green

- [ ] **Step 1: Split config read/write first**

Move YAML load/save and merge logic to `config/loader.py`. Keep this wrapper in `hermes_cli/config.py`:

```python
from config.loader import load_config, save_config
```

Only move additional config responsibilities after `load_config` and `save_config` tests pass.

- [ ] **Step 2: Split path/env/profile/model responsibilities**

Move path helpers to `config/paths.py`, `.env` loading to `config/env_loader.py`, profile logic to `config/profiles.py`, and model catalog/normalization logic to `config/models.py`. Keep old names re-exported from `hermes_cli/config.py`.

- [ ] **Step 3: Split web server by route group**

Move FastAPI app construction to `web_server/app.py`. Move route groups without changing URL paths:

```text
/api/chat/*      -> web_server/chat_api.py
/api/desk/*      -> web_server/desk_api.py
session CRUD     -> web_server/session_api.py
voice endpoints  -> web_server/voice_api.py
SPA serving      -> web_server/static_server.py
```

Keep `hermes_cli/web_server.py` exporting the same `app` object or factory currently used by `desktop_entrypoint.py`.

- [ ] **Step 4: Run Phase 4 verification**

Run:

```powershell
cd hermes_core
python -m pytest tests -q -k "config or web_server or session"
python -m pytest tests/kabuqina -q
cd ..
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
```

Expected: config/web server tests and desktop Python tests pass.

- [ ] **Step 5: Commit Phase 4**

```powershell
git add hermes_core/config hermes_core/web_server hermes_core/hermes_cli/config.py hermes_core/hermes_cli/web_server.py python/src python/tests hermes_core/tests
git commit -m "refactor: split config and web server packages"
```

### Phase 5: Agent Loop Decomposition

Only start this phase after Phases 0-4 are green. This phase changes the hottest path.

**Files:**
- Create: `hermes_core/agent/loop.py`
- Create: `hermes_core/agent/tool_dispatch.py`
- Create: `hermes_core/agent/message_manager.py`
- Create: `hermes_core/agent/response_handler.py`
- Create: `hermes_core/agent/openai_client.py`
- Create: `hermes_core/agent/usage.py`
- Modify: `hermes_core/run_agent.py`
- Test: `hermes_core/tests/run_agent/`

- [ ] **Step 1: Snapshot public behavior**

Run:

```powershell
cd hermes_core
python -m pytest tests/run_agent -q
cd ..
```

Expected: current run_agent tests pass before extraction. If failures exist before extraction, record them in the commit message and do not hide them with refactor changes.

- [ ] **Step 2: Extract OpenAI client wrapper**

Move lazy OpenAI import/client construction to `agent/openai_client.py`. Keep `run_agent.OpenAI` patch patterns working by assigning the same importable symbol in `run_agent.py`.

Compatibility check:

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_create_openai_client_reuse.py -q
cd ..
```

- [ ] **Step 3: Extract usage helpers**

Move token counting, pricing and usage aggregation helpers to `agent/usage.py`. Keep public helper names imported into `run_agent.py` if tests or callers patch them there.

- [ ] **Step 4: Extract message management**

Move pure message-history helpers to `agent/message_manager.py`. Do not move methods that depend on large mutable `AIAgent` state until their inputs are explicit and covered by tests.

- [ ] **Step 5: Extract response handling**

Move streaming/non-streaming response parsing and tool-call repair helpers to `agent/response_handler.py`. Preserve tests that patch `run_agent` symbols by keeping compatibility imports in `run_agent.py`.

- [ ] **Step 6: Extract tool dispatch**

Move tool call argument parsing, execution dispatch, and result shaping to `agent/tool_dispatch.py`. Keep tool registry import paths stable.

- [ ] **Step 7: Extract conversation loop last**

Move the outer turn loop to `agent/loop.py` only after the previous extractions are green. `AIAgent.run_conversation` should delegate to the new loop function while remaining the public method.

- [ ] **Step 8: Run Phase 5 verification**

Run:

```powershell
cd hermes_core
python -m pytest tests/run_agent tests/agent tests/kabuqina -q
cd ..
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
```

Expected: all run_agent, agent and desktop Python tests pass.

- [ ] **Step 9: Commit Phase 5 in small commits**

Use one commit per extraction:

```powershell
git add hermes_core/run_agent.py hermes_core/agent/openai_client.py hermes_core/tests
git commit -m "refactor: extract agent OpenAI client"

git add hermes_core/run_agent.py hermes_core/agent/usage.py hermes_core/tests
git commit -m "refactor: extract agent usage helpers"
```

Repeat the same pattern for message manager, response handler, tool dispatch and loop extraction.

### Phase 6: Tools and Academic Package

Move tool files into focused subpackages only after registry compatibility is pinned.

**Files:**
- Create: `hermes_core/tools/academic/__init__.py`
- Create: `hermes_core/tools/academic/material_index.py`
- Create: `hermes_core/tools/academic/citation.py`
- Create: `hermes_core/tools/academic/formula_code.py`
- Modify: `hermes_core/tools/material_index_tools.py`
- Modify: `hermes_core/tools/math_expression_tools.py`
- Modify: `hermes_core/tools/registry.py` or current tool registration module
- Test: `hermes_core/tests/test_tools/` or current equivalent tests

- [ ] **Step 1: Add academic package wrappers**

Create `tools/academic/material_index.py` as a wrapper around the current material index implementation. Create `tools/academic/citation.py` and `tools/academic/formula_code.py` only with tested public functions as they are implemented.

- [ ] **Step 2: Pin registry compatibility**

Add a test that the existing tool names still register after files move:

```python
def test_existing_tool_names_still_register():
    from tools.registry import discover_builtin_tools, registry

    discover_builtin_tools()
    names = set(registry.get_all_tool_names())
    assert "material_index" in names
    assert "math_expression" in names
```

If these names differ from the current registered tool names, first inspect the current registrations with `python -c "from tools.registry import discover_builtin_tools, registry; discover_builtin_tools(); print(registry.get_all_tool_names())"` and pin the names that existing users can call today.

- [ ] **Step 3: Move one tool family at a time**

Move file, web, terminal, media, system, skill and mcp tools only after the registry test passes for that family. Leave old modules as wrappers until all internal callers use new paths.

- [ ] **Step 4: Run Phase 6 verification**

Run:

```powershell
cd hermes_core
python -m pytest tests -q -k "tool or material or math or document"
python -m pytest tests/kabuqina -q
cd ..
```

Expected: tool tests and compatibility tests pass.

- [ ] **Step 5: Commit Phase 6 by tool family**

```powershell
git add hermes_core/tools/academic hermes_core/tools/material_index_tools.py hermes_core/tools/math_expression_tools.py hermes_core/tests
git commit -m "refactor: introduce academic tools package"
```

### Phase 7: Quarantine and Delete Unused Upstream Components

Deletion happens after import inventory and runtime smoke tests, not before.

**Files:**
- Create: `docs/core-removal-inventory.md`
- Modify/Delete: selected unused directories under `hermes_core/`
- Modify: `DECISIONS.md`

- [ ] **Step 1: Build removal inventory**

Run:

```powershell
rg -n "acp_adapter|acp_registry|ui-tui|tui_gateway|website|plugins|mcp_serve|batch_runner|mini_swe_runner|discord|slack|signal|matrix|homeassistant|mattermost|bluebubbles|yuanbao" hermes_core python tauri web scripts -S --glob "!**/node_modules/**" --glob "!**/target/**" > docs/core-removal-inventory.md
```

Expected: every proposed deletion has zero production references or a documented replacement.

- [ ] **Step 2: Quarantine before delete**

For each candidate directory, first remove it from build/bundle inclusion and keep the source in the worktree. Run full verification. Delete source only after the bundled runtime still works.

- [ ] **Step 3: Correct gateway platform count**

The retained platform list is:

```text
weixin, qqbot, feishu, wecom, dingtalk, email, whatsapp, telegram, webhook
```

This is nine platform families, not eight. Keep the count consistent in docs and tests.

- [ ] **Step 4: Run Phase 7 verification**

Run:

```powershell
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
cd hermes_core; python -m pytest tests/kabuqina tests/gateway tests/cron -q; cd ..
cd web; npm run build; cd ..
cd tauri; cargo check; cd ..
```

Expected: desktop tests, gateway tests, cron tests, web build and Rust check pass.

- [ ] **Step 5: Commit Phase 7**

```powershell
git add docs/core-removal-inventory.md DECISIONS.md hermes_core
git commit -m "chore: remove unused upstream components"
```

### Phase 8: User Data and Environment Migration

Only run this phase after new names are already supported and old names still work.

**Files:**
- Create: `python/src/user_data_migration.py`
- Create: `python/tests/test_user_data_migration.py`
- Modify: Tauri supervisor/env setup files
- Modify: docs/troubleshooting.md
- Modify: docs/architecture.md

- [ ] **Step 1: Implement dry-run migration**

Create `python/src/user_data_migration.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MigrationPlan:
    source: Path
    target: Path
    should_copy: bool
    reason: str


def plan_home_migration(source: Path, target: Path) -> MigrationPlan:
    if not source.exists():
        return MigrationPlan(source, target, False, "source_missing")
    if target.exists():
        return MigrationPlan(source, target, False, "target_exists")
    return MigrationPlan(source, target, True, "copy_required")
```

- [ ] **Step 2: Add migration tests**

Create `python/tests/test_user_data_migration.py`:

```python
import tempfile
import unittest
from pathlib import Path

from src.user_data_migration import plan_home_migration


class UserDataMigrationTests(unittest.TestCase):
    def test_missing_source_does_not_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "missing"
            target = Path(tmp) / "home"
            plan = plan_home_migration(source, target)
            self.assertFalse(plan.should_copy)
            self.assertEqual(plan.reason, "source_missing")

    def test_existing_target_does_not_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "hermes-home"
            target = Path(tmp) / "home"
            source.mkdir()
            target.mkdir()
            plan = plan_home_migration(source, target)
            self.assertFalse(plan.should_copy)
            self.assertEqual(plan.reason, "target_exists")

    def test_existing_source_and_missing_target_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "hermes-home"
            target = Path(tmp) / "home"
            source.mkdir()
            plan = plan_home_migration(source, target)
            self.assertTrue(plan.should_copy)
            self.assertEqual(plan.reason, "copy_required")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Use the real current Windows app data path**

Migration source must include the path currently documented by the repo:

```text
%LOCALAPPDATA%\com.kabuqina.app\hermes-home\
```

Do not migrate from `%LOCALAPPDATA%\Kabuqina\hermes-home\` unless code inspection proves that path exists in shipped builds.

- [ ] **Step 4: Run Phase 8 verification**

Run:

```powershell
cd python; python -m unittest tests.test_user_data_migration -v; cd ..
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
```

Expected: migration tests and desktop Python tests pass.

- [ ] **Step 5: Commit Phase 8**

```powershell
git add python/src/user_data_migration.py python/tests/test_user_data_migration.py docs/troubleshooting.md docs/architecture.md
git commit -m "feat: add dry-run user data migration"
```

### Phase 9: Final Rename and Wrapper Removal

This phase is intentionally last. It should happen after at least one full green pass with new names used internally.

**Files:**
- Modify: `hermes_core/pyproject.toml`
- Modify: `python/build_bundle.ps1`
- Modify: `scripts/dev.ps1`
- Modify: `tauri/src/**`
- Modify: `web/src/**`
- Modify: docs under `docs/`
- Delete: old wrappers only after internal callers no longer need them

- [ ] **Step 1: Switch internal callers to new imports**

Replace internal imports gradually:

```text
from run_agent import AIAgent
```

with:

```text
from kabuqina_core.agent import AIAgent
```

Only do this in production code after `kabuqina_core.agent` facade is green.

- [ ] **Step 2: Switch env writers to new names**

Rust/Tauri should set both names during the compatibility window:

```text
KABUQINA_HOME and HERMES_HOME
KABUQINA_WORKSPACE and HERMES_WORKSPACE
KABUQINA_TIMEZONE and HERMES_TIMEZONE
KABUQINA_POWER_USER and HERMESDESK_POWER_USER
```

Python readers should prefer the new names and fall back to old names.

- [ ] **Step 3: Rename package metadata**

Update package metadata from `hermes-agent` to `kabuqina-core` only after bundle scripts have tests covering the new wheel/package name.

- [ ] **Step 4: Remove old wrappers**

Delete old wrappers only when this command returns no production hits:

```powershell
rg -n "from run_agent|import run_agent|from hermes_cli|import hermes_cli|HERMES_HOME|HERMESDESK_" python tauri web hermes_core scripts -S --glob "!**/tests/**" --glob "!**/node_modules/**" --glob "!**/target/**"
```

Expected: zero production hits. Test references may remain if they explicitly verify compatibility removal.

- [ ] **Step 5: Run final full regression**

Run:

```powershell
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
cd hermes_core; python -m pytest tests -q; cd ..
cd web; npm run build; cd ..
cd tauri; cargo check; cd ..
```

Then run the manual smoke path:

```powershell
.\scripts\dev.ps1
```

Verify manually:

```text
Python child starts and reports a loopback port
Shell chat sends one message and receives one response
File read/write tool works inside workspace
Web/search tool works through the allowed policy
PPT or DOCX generation works
Cron tick triggers a test job
Gateway optional child starts when enabled
```

- [ ] **Step 6: Commit Phase 9**

```powershell
git add hermes_core python tauri web scripts docs DECISIONS.md
git commit -m "refactor: complete kabuqina core rename"
```

## Deletion Candidates

Deletion candidates must pass Phase 7 inventory before removal:

| Component | Original Path | Deletion Condition |
|---|---|---|
| RL/training and benchmark environments | `hermes_core/environments/` subsets, benchmark helpers | no production imports; local/docker environment retained if still used |
| TUI | `hermes_core/ui-tui/`, `hermes_core/tui_gateway/` | desktop web shell and gateway tests do not import TUI modules |
| ACP adapters | `hermes_core/acp_adapter/`, `hermes_core/acp_registry/` | no production imports |
| Hermes standalone CLI-only entrypoints | `hermes_core/hermes_cli/main.py`, parser, curses/banner files | desktop entrypoint and bundle do not invoke them |
| Cloud/provider adapters not supported by product | Bedrock, Google Cloud Code, Copilot ACP modules | provider inventory shows no configured route |
| Nous subscription/auth surface | `hermes_cli/nous_subscription.py`, upstream OAuth/auth modules | desktop credential flow does not import them |
| Plugin system | `hermes_core/plugins/`, plugin CLI files | skills/tooling do not depend on plugin loader |
| Website/docs site | `hermes_core/website/` | not included in bundle |
| Extra gateway platforms | Discord, Slack, Signal, Matrix, Home Assistant, Mattermost, SMS, BlueBubbles, Yuanbao | gateway config and platform registry tests cover retained platforms |
| MCP server exposure | `hermes_core/mcp_serve.py` | product does not expose Kabuqina as MCP server |

## Naming Migration Map

Use this map only after compatibility wrappers exist:

| Legacy Name | New Name | Compatibility Rule |
|---|---|---|
| `hermes_core/` | `kabuqina_core/` | introduce facade first; physical rename last |
| `hermes_constants` | `kq_constants` | wrapper remains until imports are gone |
| `hermes_logging` | `kq_logging` | wrapper remains until imports are gone |
| `hermes_state` | `kq_state` | wrapper remains until session tests are green |
| `hermes_time` | `kq_time` | wrapper remains until cron/timezone tests are green |
| `hermes_cli` | `config/`, `web_server/`, desktop-specific entrypoints | split by responsibility; keep old package wrappers |
| `HERMES_HOME` | `KABUQINA_HOME` | new wins, old fallback |
| `HERMES_WORKSPACE` | `KABUQINA_WORKSPACE` | new wins, old fallback |
| `HERMES_TIMEZONE` | `KABUQINA_TIMEZONE` | new wins, old fallback |
| `HERMESDESK_*` | `KABUQINA_*` | new wins, old fallback |
| `~/.hermes/` | `~/.kabuqina/` | dry-run migration first; do not delete old data automatically |
| `%LOCALAPPDATA%\com.kabuqina.app\hermes-home\` | `%LOCALAPPDATA%\com.kabuqina.app\home\` | copy only when target missing |

## Verification Matrix

Run the narrowest relevant tests inside each phase, plus the compatibility tests. Before merging a phase branch, run:

```powershell
cd python; python -m unittest discover -s tests -p "test_*.py" -v; cd ..
cd hermes_core; python -m pytest tests/kabuqina -q; cd ..
cd web; npm run build; cd ..
cd tauri; cargo check; cd ..
```

Before the final rename/removal phase, also run:

```powershell
cd hermes_core; python -m pytest tests -q; cd ..
.\scripts\dev.ps1
```

Manual smoke checklist:

- Python child starts without overlay failures.
- Tauri receives Python loopback port.
- `/chat` can send and receive a message.
- File, web/search and document generation tools work.
- Cron test job fires.
- Gateway optional child starts and stops cleanly.
- Existing user data is detected from the old home path.

## Execution Notes

- Prefer one branch per phase, named with the `codex/` prefix when created by Codex.
- Prefer one commit per extraction unit; avoid a single mega-commit.
- Do not remove wrappers in the same commit that introduces a new path.
- Do not combine behavior changes with file moves.
- If a phase uncovers pre-existing failing tests, record the exact failing command and failure in the commit message or phase notes before proceeding.
- If any dynamic import path is uncertain, add a compatibility test before moving the file.

Plan complete and saved in `.qoder/specs/Core重构架构设计_task-eee.md`. Recommended execution mode: subagent-driven phase by phase, with review after each phase.
