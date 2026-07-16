# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Auth-store persistence layer for ``~/.kabuqina/auth.json``.

The provider-runtime-safe core of the credential store: file-path resolution,
cross-process locking, load/save, per-provider state, the credential pool, and
source-suppression markers. It deliberately has **no** dependency on the CLI
command surface or the provider registry, so provider runtime code can import
it without pulling in argparse/printing wiring.

``kabuqina_cli.auth`` re-exports every public name here for backward
compatibility, so existing ``kabuqina_cli.auth.*`` imports and test monkeypatches
keep hitting the same object.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from kabuqina_cli.config import get_kabuqina_home
from utils import atomic_replace

logger = logging.getLogger(__name__)

try:
    import fcntl
except Exception:
    fcntl = None
try:
    import msvcrt
except Exception:
    msvcrt = None


AUTH_STORE_VERSION = 1
AUTH_LOCK_TIMEOUT_SECONDS = 15.0


def _auth_file_path() -> Path:
    path = get_kabuqina_home() / "auth.json"
    # Seat belt: if pytest resolves to a real current or legacy user store,
    # user's auth store, refuse rather than silently corrupt it. This catches
    # tests that forgot to monkeypatch HERMES_HOME, tests invoked without the
    # hermetic conftest, or sandbox escapes via threads/subprocesses. In
    # production (no PYTEST_CURRENT_TEST) this is a single dict lookup.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        real_home_auth = {
            (Path.home() / name / "auth.json").resolve(strict=False)
            for name in (".kabuqina", ".hermes")
        }
        try:
            resolved = path.resolve(strict=False)
        except Exception:
            resolved = path
        if resolved in real_home_auth:
            raise RuntimeError(
                f"Refusing to touch real user auth store during test run: {path}. "
                "Set KABUQINA_HOME to a tmp_path in your test fixture, or run "
                "via scripts/run_tests.sh for hermetic CI-parity env."
            )
    return path

def _auth_lock_path() -> Path:
    return _auth_file_path().with_suffix(".lock")

_auth_lock_holder = threading.local()

@contextmanager
def _auth_store_lock(timeout_seconds: float = AUTH_LOCK_TIMEOUT_SECONDS):
    """Cross-process advisory lock for auth.json reads+writes.  Reentrant."""
    # Reentrant: if this thread already holds the lock, just yield.
    if getattr(_auth_lock_holder, "depth", 0) > 0:
        _auth_lock_holder.depth += 1
        try:
            yield
        finally:
            _auth_lock_holder.depth -= 1
        return

    lock_path = _auth_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if fcntl is None and msvcrt is None:
        _auth_lock_holder.depth = 1
        try:
            yield
        finally:
            _auth_lock_holder.depth = 0
        return

    # On Windows, msvcrt.locking needs the file to have content and the
    # file pointer at position 0.  Ensure the lock file has at least 1 byte.
    if msvcrt and (not lock_path.exists() or lock_path.stat().st_size == 0):
        lock_path.write_text(" ", encoding="utf-8")

    with lock_path.open("r+" if msvcrt else "a+") as lock_file:
        deadline = time.time() + max(1.0, timeout_seconds)
        while True:
            try:
                if fcntl:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except (BlockingIOError, OSError, PermissionError):
                if time.time() >= deadline:
                    raise TimeoutError("Timed out waiting for auth store lock")
                time.sleep(0.05)

        _auth_lock_holder.depth = 1
        try:
            yield
        finally:
            _auth_lock_holder.depth = 0
            if fcntl:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                try:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except (OSError, IOError):
                    pass

def _load_auth_store(auth_file: Optional[Path] = None) -> Dict[str, Any]:
    auth_file = auth_file or _auth_file_path()
    if not auth_file.exists():
        return {"version": AUTH_STORE_VERSION, "providers": {}}

    try:
        raw = json.loads(auth_file.read_text())
    except Exception as exc:
        corrupt_path = auth_file.with_suffix(".json.corrupt")
        try:
            import shutil
            shutil.copy2(auth_file, corrupt_path)
        except Exception:
            pass
        logger.warning(
            "auth: failed to parse %s (%s) — starting with empty store. "
            "Corrupt file preserved at %s",
            auth_file, exc, corrupt_path,
        )
        return {"version": AUTH_STORE_VERSION, "providers": {}}

    if isinstance(raw, dict) and (
        isinstance(raw.get("providers"), dict)
        or isinstance(raw.get("credential_pool"), dict)
    ):
        raw.setdefault("providers", {})
        return raw

    # Migrate from PR's "systems" format if present
    if isinstance(raw, dict) and isinstance(raw.get("systems"), dict):
        systems = raw["systems"]
        providers = {}
        if "nous_portal" in systems:
            providers["nous"] = systems["nous_portal"]
        return {"version": AUTH_STORE_VERSION, "providers": providers,
                "active_provider": "nous" if providers else None}

    return {"version": AUTH_STORE_VERSION, "providers": {}}

def _save_auth_store(auth_store: Dict[str, Any]) -> Path:
    auth_file = _auth_file_path()
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_store["version"] = AUTH_STORE_VERSION
    auth_store["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(auth_store, indent=2) + "\n"
    tmp_path = auth_file.with_name(f"{auth_file.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        atomic_replace(tmp_path, auth_file)
        try:
            dir_fd = os.open(str(auth_file.parent), os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
    # Restrict file permissions to owner only
    try:
        auth_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return auth_file

def _load_provider_state(auth_store: Dict[str, Any], provider_id: str) -> Optional[Dict[str, Any]]:
    providers = auth_store.get("providers")
    if not isinstance(providers, dict):
        return None
    state = providers.get(provider_id)
    return dict(state) if isinstance(state, dict) else None

def _save_provider_state(auth_store: Dict[str, Any], provider_id: str, state: Dict[str, Any]) -> None:
    providers = auth_store.setdefault("providers", {})
    if not isinstance(providers, dict):
        auth_store["providers"] = {}
        providers = auth_store["providers"]
    providers[provider_id] = state
    auth_store["active_provider"] = provider_id

def _store_provider_state(
    auth_store: Dict[str, Any],
    provider_id: str,
    state: Dict[str, Any],
    *,
    set_active: bool = True,
) -> None:
    providers = auth_store.setdefault("providers", {})
    if not isinstance(providers, dict):
        auth_store["providers"] = {}
        providers = auth_store["providers"]
    providers[provider_id] = state
    if set_active:
        auth_store["active_provider"] = provider_id

def read_credential_pool(provider_id: Optional[str] = None) -> Dict[str, Any]:
    """Return the persisted credential pool, or one provider slice."""
    auth_store = _load_auth_store()
    pool = auth_store.get("credential_pool")
    if not isinstance(pool, dict):
        pool = {}
    if provider_id is None:
        return dict(pool)
    provider_entries = pool.get(provider_id)
    return list(provider_entries) if isinstance(provider_entries, list) else []

def write_credential_pool(provider_id: str, entries: List[Dict[str, Any]]) -> Path:
    """Persist one provider's credential pool under auth.json."""
    with _auth_store_lock():
        auth_store = _load_auth_store()
        pool = auth_store.get("credential_pool")
        if not isinstance(pool, dict):
            pool = {}
            auth_store["credential_pool"] = pool
        pool[provider_id] = list(entries)
        return _save_auth_store(auth_store)

def suppress_credential_source(provider_id: str, source: str) -> None:
    """Mark a credential source as suppressed so it won't be re-seeded."""
    with _auth_store_lock():
        auth_store = _load_auth_store()
        suppressed = auth_store.setdefault("suppressed_sources", {})
        provider_list = suppressed.setdefault(provider_id, [])
        if source not in provider_list:
            provider_list.append(source)
        _save_auth_store(auth_store)

def is_source_suppressed(provider_id: str, source: str) -> bool:
    """Check if a credential source has been suppressed by the user."""
    try:
        auth_store = _load_auth_store()
        suppressed = auth_store.get("suppressed_sources", {})
        return source in suppressed.get(provider_id, [])
    except Exception:
        return False

def unsuppress_credential_source(provider_id: str, source: str) -> bool:
    """Clear a suppression marker so the source will be re-seeded on the next load.

    Returns True if a marker was cleared, False if no marker existed.
    """
    with _auth_store_lock():
        auth_store = _load_auth_store()
        suppressed = auth_store.get("suppressed_sources")
        if not isinstance(suppressed, dict):
            return False
        provider_list = suppressed.get(provider_id)
        if not isinstance(provider_list, list) or source not in provider_list:
            return False
        provider_list.remove(source)
        if not provider_list:
            suppressed.pop(provider_id, None)
        if not suppressed:
            auth_store.pop("suppressed_sources", None)
        _save_auth_store(auth_store)
        return True

def get_provider_auth_state(provider_id: str) -> Optional[Dict[str, Any]]:
    """Return persisted auth state for a provider, or None."""
    auth_store = _load_auth_store()
    return _load_provider_state(auth_store, provider_id)

def get_active_provider() -> Optional[str]:
    """Return the currently active provider ID from auth store."""
    auth_store = _load_auth_store()
    return auth_store.get("active_provider")

def clear_provider_auth(provider_id: Optional[str] = None) -> bool:
    """
    Clear auth state for a provider. Used by `kabuqina logout`.
    If provider_id is None, clears the active provider.
    Returns True if something was cleared.
    """
    with _auth_store_lock():
        auth_store = _load_auth_store()
        target = provider_id or auth_store.get("active_provider")
        if not target:
            return False

        providers = auth_store.get("providers", {})
        if not isinstance(providers, dict):
            providers = {}
            auth_store["providers"] = providers

        pool = auth_store.get("credential_pool")
        if not isinstance(pool, dict):
            pool = {}
            auth_store["credential_pool"] = pool

        cleared = False
        if target in providers:
            del providers[target]
            cleared = True
        if target in pool:
            del pool[target]
            cleared = True

        if auth_store.get("active_provider") == target:
            auth_store["active_provider"] = None
            cleared = True

        if not cleared:
            return False
        _save_auth_store(auth_store)
    return True

def deactivate_provider() -> None:
    """
    Clear active_provider in auth.json without deleting credentials.
    Used when the user switches to a non-OAuth provider (OpenRouter, custom)
    so auto-resolution doesn't keep picking the OAuth provider.
    """
    with _auth_store_lock():
        auth_store = _load_auth_store()
        auth_store["active_provider"] = None
        _save_auth_store(auth_store)
