# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desktop timezone bootstrap for Kabuqina web + gateway children.

Kabuqina resolves wall clock via ``KABUQINA_TIMEZONE`` env, then ``config.yaml``
``timezone``, then server-local. Kabuqina users often have a stale
``config.yaml`` or English placeholder ``timezone: America/New_York`` in
``shared/USER_PREFS.md`` while the PC is set to China Standard Time.

Resolution order when seeding ``KABUQINA_TIMEZONE`` (only if not already set
in the process environment, e.g. from ``.env``):

  1. ``shared/USER_PREFS.md`` ``timezone:`` line (Settings → Shared prefs)
  2. Windows system IANA zone (registry / ``astimezone().key``)
  3. ``config.yaml`` ``timezone`` key

Also copies non-empty ``USER_PREFS.md`` → ``_host_prefs.md`` under host
``KABUQINA_HOME`` so the web child agent sees the same prefs as gateway bots.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

from kabuqina_env import home as kabuqina_home_env

log = logging.getLogger("kabuqina.timezone")

_TZ_LINE = re.compile(r"^\s*timezone\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

# English UI placeholder — not a deliberate user choice for most CN installs.
_PLACEHOLDER_TZ = frozenset({"America/New_York"})

def _windows_tz_lookup() -> dict[str, str]:
    """Full Windows registry name → IANA map (vendored from tzlocal)."""
    try:
        from windows_registry_tz import WIN_TZ

        return WIN_TZ
    except ImportError:
        return {}


_WIN_TZ_FALLBACK_SUFFIX = " Standard Time"


def parse_timezone_from_prefs(text: str) -> str:
    """Extract ``timezone:`` from USER_PREFS / _host_prefs markdown."""
    if not text or not text.strip():
        return ""
    m = _TZ_LINE.search(text)
    if not m:
        return ""
    raw = m.group(1).strip().strip("\"'")
    return raw if raw else ""


def _validate_iana(name: str) -> str:
    """Return *name* if it is a valid IANA zone, else ``""``."""
    if not name or not name.strip():
        return ""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(name.strip())
        return name.strip()
    except Exception:
        return ""


def windows_iana_timezone() -> str:
    """Best-effort IANA timezone for the Windows system clock."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation",
            ) as key:
                win_name, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
            win_name = str(win_name).split("\x00", 1)[0].strip()
            tz_map = _windows_tz_lookup()
            mapped = tz_map.get(win_name, "")
            if not mapped and not win_name.endswith(_WIN_TZ_FALLBACK_SUFFIX):
                mapped = tz_map.get(win_name + _WIN_TZ_FALLBACK_SUFFIX, "")
            if mapped and _validate_iana(mapped):
                return mapped
        except Exception:
            pass

    try:
        from datetime import datetime

        now = datetime.now().astimezone()
        key = getattr(now.tzinfo, "key", None)
        if isinstance(key, str) and key and _validate_iana(key):
            return key
    except Exception:
        pass
    return ""


def _read_config_timezone(hermes_home: Path) -> str:
    try:
        import yaml

        path = hermes_home / "config.yaml"
        if not path.is_file():
            return ""
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        tz = cfg.get("timezone", "")
        if isinstance(tz, str):
            return _validate_iana(tz)
    except Exception:
        pass
    return ""


def _write_config_timezone(hermes_home: Path, iana: str) -> None:
    if not iana:
        return
    try:
        from kabuqina_cli.config import load_config, save_config

        cfg = load_config() or {}
        if (cfg.get("timezone") or "").strip() == iana:
            return
        cfg["timezone"] = iana
        save_config(cfg)
        log.info("config.yaml timezone -> %s", iana)
    except Exception:
        log.exception("failed to write config.yaml timezone")


def sync_host_prefs_from_shared(hermes_home: Path) -> None:
    """Copy ``shared/USER_PREFS.md`` → ``_host_prefs.md`` for the web child."""
    src = hermes_home / "shared" / "USER_PREFS.md"
    dst = hermes_home / "_host_prefs.md"
    if not src.is_file():
        if dst.is_file():
            try:
                dst.unlink()
            except OSError:
                pass
        return
    try:
        content = src.read_text(encoding="utf-8")
    except OSError:
        return
    if not content.strip():
        if dst.is_file():
            try:
                dst.unlink()
            except OSError:
                pass
        return
    try:
        dst.write_text(content, encoding="utf-8")
        log.debug("synced USER_PREFS.md -> _host_prefs.md")
    except OSError:
        log.warning("failed to write _host_prefs.md", exc_info=True)


def _reset_kabuqina_time_cache() -> None:
    try:
        import kabuqina_time

        if hasattr(kabuqina_time, "reset_cache"):
            kabuqina_time.reset_cache()
            return
        kabuqina_time._cached_tz = None
        kabuqina_time._cached_tz_name = None
        kabuqina_time._cache_resolved = False
    except Exception:
        pass


def resolve_desktop_timezone(kabuqina_home: Path) -> str:
    """Pick IANA timezone without mutating the environment."""
    if "KABUQINA_TIMEZONE" in os.environ:
        configured = os.environ["KABUQINA_TIMEZONE"].strip()
    else:
        configured = os.environ.get("HERMES_TIMEZONE", "").strip()
    if configured:
        return _validate_iana(configured)

    prefs_tz = ""
    prefs_path = kabuqina_home / "shared" / "USER_PREFS.md"
    if prefs_path.is_file():
        try:
            prefs_tz = parse_timezone_from_prefs(prefs_path.read_text(encoding="utf-8"))
            prefs_tz = _validate_iana(prefs_tz)
        except OSError:
            prefs_tz = ""

    win_tz = windows_iana_timezone()
    cfg_tz = _read_config_timezone(kabuqina_home)

    if prefs_tz and prefs_tz not in _PLACEHOLDER_TZ:
        return prefs_tz
    if prefs_tz in _PLACEHOLDER_TZ and win_tz and prefs_tz != win_tz:
        log.info(
            "ignoring placeholder prefs timezone %s; using system %s",
            prefs_tz,
            win_tz,
        )
        return win_tz
    if win_tz:
        return win_tz
    if prefs_tz:
        return prefs_tz
    return cfg_tz


def apply_desktop_timezone(kabuqina_home: Path | None = None) -> str:
    """Seed Kabuqina timezone env, sync prefs, and align ``config.yaml``."""
    home_s = kabuqina_home_env().strip()
    home = kabuqina_home or (Path(home_s) if home_s else None)
    if home is None:
        log.debug("apply_desktop_timezone: KABUQINA_HOME unset")
        return ""

    sync_host_prefs_from_shared(home)

    existing = (
        os.environ["KABUQINA_TIMEZONE"].strip()
        if "KABUQINA_TIMEZONE" in os.environ
        else os.environ.get("HERMES_TIMEZONE", "").strip()
    )
    if existing:
        iana = _validate_iana(existing)
        if iana:
            _reset_kabuqina_time_cache()
            os.environ["KABUQINA_TIMEZONE"] = iana
            os.environ["HERMES_TIMEZONE"] = iana
            log.info("KABUQINA_TIMEZONE already set: %s", iana)
            return iana
        log.warning("KABUQINA_TIMEZONE invalid (%r); re-resolving", existing)
        os.environ.pop("KABUQINA_TIMEZONE", None)
        os.environ.pop("HERMES_TIMEZONE", None)

    iana = resolve_desktop_timezone(home)
    if not iana:
        _reset_kabuqina_time_cache()
        log.info("desktop timezone: none configured; using server-local clock")
        return ""

    os.environ["KABUQINA_TIMEZONE"] = iana
    os.environ["HERMES_TIMEZONE"] = iana
    _write_config_timezone(home, iana)
    _reset_kabuqina_time_cache()
    log.info("KABUQINA_TIMEZONE -> %s (wall clock for agent/cron)", iana)
    return iana
