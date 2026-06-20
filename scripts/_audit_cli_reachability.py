"""One-off audit: which hermes_cli / cli modules are reachable from the
retained desktop+gateway+cron runtime. Static AST import trace (includes lazy
imports inside functions). Conservative: anything imported anywhere in a
reachable module counts as reachable (kept). The complement is delete-safe.

Run from repo root: python scripts/_audit_cli_reachability.py

Supports docs/superpowers/specs/2026-06-20-upstream-cli-deletion-plan.md (re-run
at step 5 to confirm the cluster is unreachable after the hooks are severed).
"""
from __future__ import annotations
import ast
import os
import sys
from pathlib import Path

CORE = Path("hermes_core").resolve()

# Runtime entrypoints actually launched by the desktop product, the gateway
# child, and cron — plus the specific hermes_core modules the out-of-tree
# desk_server (python/src) imports directly.
ROOTS = [
    "run_agent", "toolsets", "model_tools", "tools.registry",
    "gateway.run", "cron.scheduler",
    "hermes_cli.config", "hermes_cli.tools_config", "hermes_cli.skills_config",
    "hermes_cli.plugins", "tools.document_tools", "tools.skills_tool",
    "desktop_contract", "hermes_constants", "hermes_logging", "hermes_state", "hermes_time",
]


def mod_to_file(mod: str) -> Path | None:
    p = CORE / (mod.replace(".", "/") + ".py")
    if p.exists():
        return p
    pkg = CORE / mod.replace(".", "/") / "__init__.py"
    if pkg.exists():
        return pkg
    return None


def file_to_mod(path: Path) -> str:
    rel = path.resolve().relative_to(CORE)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def imported_modules(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return set()
    cur_pkg = file_to_mod(path).rsplit(".", 1)[0] if "." in file_to_mod(path) else ""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = cur_pkg
                for _ in range(node.level - 1):
                    base = base.rsplit(".", 1)[0] if "." in base else ""
                mod = (base + "." + node.module) if node.module else base
                out.add(mod)
            elif node.module:
                out.add(node.module)
    return out


# Entrypoints we intend to delete — do NOT traverse into them, so we see what
# the runtime needs *without* the upstream CLI god-modules. Reaching one of
# these from a kept module is a "hook to sever".
BLOCK = {"cli", "hermes_cli.main", "hermes_cli.setup", "hermes_cli.web_server"}


def main() -> None:
    reachable: set[str] = set()
    queue = [r for r in ROOTS if r not in BLOCK]
    while queue:
        mod = queue.pop()
        f = mod_to_file(mod)
        if f is None or mod in reachable:
            continue
        reachable.add(mod)
        if mod in BLOCK:
            continue  # recorded as reachable-edge target but not traversed
        for imp in imported_modules(f):
            if mod_to_file(imp) is not None and imp not in reachable and imp not in BLOCK:
                queue.append(imp)

    # Universe of CLI-cluster candidates
    cli_mods = ["cli"] + [
        "hermes_cli." + p.stem
        for p in sorted((CORE / "hermes_cli").glob("*.py"))
        if p.stem != "__init__"
    ]
    kept = [m for m in cli_mods if m in reachable]
    deletable = [m for m in cli_mods if m not in reachable]

    delset = set(deletable) | BLOCK
    total_del_lines = 0
    print(f"reachable core modules (CLI entrypoints blocked): {len(reachable)}")
    print(f"\n=== KEEP: hermes_cli modules the runtime truly needs [{len(kept)}] ===")
    print("   " + ", ".join(m.replace("hermes_cli.", "") for m in kept))
    print(f"\n=== DELETABLE cluster once hooks severed [{len(deletable)}] ===")
    for m in deletable:
        f = mod_to_file(m)
        n = len(f.read_text(encoding='utf-8', errors='replace').splitlines()) if f else 0
        total_del_lines += n
        print(f"   {n:6d}  {m}")
    print(f"   ----> ~{total_del_lines} lines deletable (cli.py extra:)")
    cf = mod_to_file("cli")
    print(f"   {len(cf.read_text(encoding='utf-8',errors='replace').splitlines())}  cli  (entrypoint, blocked)")

    print("\n=== HOOKS to sever (kept runtime module -> deletable cluster) ===")
    seen = set()
    for m in sorted(reachable):
        if m in delset:
            continue
        f = mod_to_file(m)
        if not f:
            continue
        for imp in sorted(imported_modules(f)):
            if (imp in delset) and mod_to_file(imp) is not None:
                key = (m, imp)
                if key not in seen:
                    seen.add(key)
                    print(f"   {m}  ->  {imp}")


if __name__ == "__main__":
    main()
