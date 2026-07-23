# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Read/write helpers for the user ``~/.kabuqina/.env`` file.

Extracted from ``kabuqina_cli/config.py``: env-file load/save/sanitize, secret
persistence, value lookup/redaction, plus the env-only constants they use. Sits
on top of ``config_managed`` (is_managed/managed_error) and ``config_home``
(ensure_kabuqina_home/_secure_file); reads the schema from ``config_env_schema``.
``kabuqina_cli.config`` re-exports every name so existing imports and test
monkeypatches keep working.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from kabuqina_constants import get_kabuqina_home
from kabuqina_cli.colors import Colors, color
from kabuqina_cli.config_managed import is_managed, managed_error
from kabuqina_cli.config_home import ensure_kabuqina_home, _secure_file
from kabuqina_cli.config_env_schema import OPTIONAL_ENV_VARS
from utils import atomic_replace

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"

_ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_EXTRA_ENV_KEYS = frozenset({
    "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN",
    "TELEGRAM_HOME_CHANNEL", "TELEGRAM_HOME_CHANNEL_NAME",
    "SLACK_HOME_CHANNEL", "SLACK_HOME_CHANNEL_NAME",
    "SIGNAL_ACCOUNT", "SIGNAL_HTTP_URL",
    "SIGNAL_ALLOWED_USERS", "SIGNAL_GROUP_ALLOWED_USERS",
    "SIGNAL_HOME_CHANNEL", "SIGNAL_HOME_CHANNEL_NAME",
    "SMS_HOME_CHANNEL", "SMS_HOME_CHANNEL_NAME",
    "DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET",
    "DINGTALK_HOME_CHANNEL", "DINGTALK_HOME_CHANNEL_NAME",
    "YUANBAO_HOME_CHANNEL", "YUANBAO_HOME_CHANNEL_NAME",
    "WECOM_BOT_ID", "WECOM_SECRET",
    "WECOM_CALLBACK_CORP_ID", "WECOM_CALLBACK_CORP_SECRET", "WECOM_CALLBACK_AGENT_ID",
    "WECOM_CALLBACK_TOKEN", "WECOM_CALLBACK_ENCODING_AES_KEY",
    "WECOM_CALLBACK_HOST", "WECOM_CALLBACK_PORT",
    "WECOM_HOME_CHANNEL", "WECOM_HOME_CHANNEL_NAME",
    "WEIXIN_ACCOUNT_ID", "WEIXIN_TOKEN", "WEIXIN_BASE_URL", "WEIXIN_CDN_BASE_URL",
    "WEIXIN_HOME_CHANNEL", "WEIXIN_HOME_CHANNEL_NAME", "WEIXIN_DM_POLICY", "WEIXIN_GROUP_POLICY",
    "WEIXIN_ALLOWED_USERS", "WEIXIN_GROUP_ALLOWED_USERS", "WEIXIN_ALLOW_ALL_USERS",
    "BLUEBUBBLES_SERVER_URL", "BLUEBUBBLES_PASSWORD",
    "BLUEBUBBLES_HOME_CHANNEL", "BLUEBUBBLES_HOME_CHANNEL_NAME",
    "QQ_APP_ID", "QQ_CLIENT_SECRET", "QQBOT_HOME_CHANNEL", "QQBOT_HOME_CHANNEL_NAME",
    "QQ_HOME_CHANNEL", "QQ_HOME_CHANNEL_NAME",  # legacy aliases (pre-rename, still read for back-compat)
    "QQ_ALLOWED_USERS", "QQ_GROUP_ALLOWED_USERS", "QQ_ALLOW_ALL_USERS", "QQ_MARKDOWN_SUPPORT",
    "QQ_STT_API_KEY", "QQ_STT_BASE_URL", "QQ_STT_MODEL",
    "IRC_SERVER", "IRC_PORT", "IRC_NICKNAME", "IRC_CHANNEL",
    "IRC_USE_TLS", "IRC_SERVER_PASSWORD", "IRC_NICKSERV_PASSWORD",
    "TERMINAL_ENV", "TERMINAL_SSH_KEY", "TERMINAL_SSH_PORT",
    "WHATSAPP_MODE", "WHATSAPP_ENABLED",
    "MATTERMOST_HOME_CHANNEL", "MATTERMOST_HOME_CHANNEL_NAME", "MATTERMOST_REPLY_MODE",
    "MATRIX_PASSWORD", "MATRIX_ENCRYPTION", "MATRIX_DEVICE_ID", "MATRIX_HOME_ROOM",
    "MATRIX_REQUIRE_MENTION", "MATRIX_FREE_RESPONSE_ROOMS", "MATRIX_AUTO_THREAD", "MATRIX_DM_AUTO_THREAD",
    "MATRIX_RECOVERY_KEY",
    # Langfuse observability plugin — optional tuning keys + standard SDK vars.
    # Activation is via plugins.enabled (opt-in through `kabuqina plugins enable
    # observability/langfuse` or `kabuqina tools → Langfuse`); credentials gate
    # the plugin at runtime.
    "HERMES_LANGFUSE_ENV",
    "HERMES_LANGFUSE_RELEASE",
    "HERMES_LANGFUSE_SAMPLE_RATE",
    "HERMES_LANGFUSE_MAX_CHARS",
    "HERMES_LANGFUSE_DEBUG",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
})



def get_env_path() -> Path:
    """Get the .env file path (for API keys)."""
    return get_kabuqina_home() / ".env"

def load_env() -> Dict[str, str]:
    """Load environment variables from ~/.kabuqina/.env.

    Sanitizes lines before parsing so that corrupted files (e.g.
    concatenated KEY=VALUE pairs on a single line) are handled
    gracefully instead of producing mangled values such as duplicated
    bot tokens.  See #8908.
    """
    env_path = get_env_path()
    env_vars = {}
    
    if env_path.exists():
        # On Windows, open() defaults to the system locale (cp1252) which can
        # fail on UTF-8 .env files. Use explicit UTF-8 only on Windows.
        open_kw = {"encoding": "utf-8", "errors": "replace"} if _IS_WINDOWS else {}
        with open(env_path, **open_kw) as f:
            raw_lines = f.readlines()
        # Sanitize before parsing: split concatenated lines & drop stale
        # placeholders so corrupted .env files don't produce invalid tokens.
        lines = _sanitize_env_lines(raw_lines)
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                env_vars[key.strip()] = value.strip().strip('"\'')
    
    return env_vars

def _sanitize_env_lines(lines: list) -> list:
    """Fix corrupted .env lines before reading or writing.

    Handles two known corruption patterns:
    1. Concatenated KEY=VALUE pairs on a single line (missing newline between
       entries, e.g. ``ANTHROPIC_API_KEY=sk-...OPENAI_BASE_URL=https://...``).
    2. Stale ``KEY=***`` placeholder entries left by incomplete setup runs.

    Uses a known-keys set (OPTIONAL_ENV_VARS + _EXTRA_ENV_KEYS) so we only
    split on real Kabuqina env var names, avoiding false positives from values
    that happen to contain uppercase text with ``=``.
    """
    # Build the known keys set lazily from OPTIONAL_ENV_VARS + extras.
    # Done inside the function so OPTIONAL_ENV_VARS is guaranteed to be defined.
    known_keys = set(OPTIONAL_ENV_VARS.keys()) | _EXTRA_ENV_KEYS

    sanitized: list[str] = []
    for line in lines:
        raw = line.rstrip("\r\n")
        stripped = raw.strip()

        # Preserve blank lines and comments
        if not stripped or stripped.startswith("#"):
            sanitized.append(raw + "\n")
            continue

        # Detect concatenated KEY=VALUE pairs on one line.
        # Search for known KEY= patterns at any position in the line.
        # We collect full needle ranges so we can drop matches that are
        # fully contained within a longer overlapping needle. Without this,
        # suffix collisions corrupt the file: e.g. LM_API_KEY= inside
        # GLM_API_KEY= would otherwise split the line into "G\nLM_API_KEY=...".
        match_ranges: list[tuple[int, int]] = []
        for key_name in known_keys:
            needle = key_name + "="
            idx = stripped.find(needle)
            while idx >= 0:
                match_ranges.append((idx, idx + len(needle)))
                idx = stripped.find(needle, idx + len(needle))

        split_positions = sorted({
            s for s, e in match_ranges
            if not any(
                s2 <= s and e2 >= e and (s2, e2) != (s, e)
                for s2, e2 in match_ranges
            )
        })

        if len(split_positions) > 1:
            for i, pos in enumerate(split_positions):
                end = split_positions[i + 1] if i + 1 < len(split_positions) else len(stripped)
                part = stripped[pos:end].strip()
                if part:
                    sanitized.append(part + "\n")
        else:
            sanitized.append(stripped + "\n")

    return sanitized

def sanitize_env_file() -> int:
    """Read, sanitize, and rewrite ~/.kabuqina/.env in place.

    Returns the number of lines that were fixed (concatenation splits +
    placeholder removals).  Returns 0 when no changes are needed.
    """
    env_path = get_env_path()
    if not env_path.exists():
        return 0

    read_kw = {"encoding": "utf-8", "errors": "replace"} if _IS_WINDOWS else {}
    write_kw = {"encoding": "utf-8"} if _IS_WINDOWS else {}

    with open(env_path, **read_kw) as f:
        original_lines = f.readlines()

    sanitized = _sanitize_env_lines(original_lines)

    if sanitized == original_lines:
        return 0

    # Count fixes: difference in line count (from splits) + removed lines
    fixes = abs(len(sanitized) - len(original_lines))
    if fixes == 0:
        # Lines changed content (e.g. *** removal) even if count is same
        fixes = sum(1 for a, b in zip(original_lines, sanitized) if a != b)
        fixes += abs(len(sanitized) - len(original_lines))

    fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix=".tmp", prefix=".env_")
    try:
        with os.fdopen(fd, "w", **write_kw) as f:
            f.writelines(sanitized)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp_path, env_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    _secure_file(env_path)
    return fixes

def _check_non_ascii_credential(key: str, value: str) -> str:
    """Warn and strip non-ASCII characters from credential values.

    API keys and tokens must be pure ASCII — they are sent as HTTP header
    values which httpx/httpcore encode as ASCII.  Non-ASCII characters
    (commonly introduced by copy-pasting from rich-text editors or PDFs
    that substitute lookalike Unicode glyphs for ASCII letters) cause
    ``UnicodeEncodeError: 'ascii' codec can't encode character`` at
    request time.

    Returns the sanitized (ASCII-only) value.  Prints a warning if any
    non-ASCII characters were found and removed.
    """
    try:
        value.encode("ascii")
        return value  # all ASCII — nothing to do
    except UnicodeEncodeError:
        pass

    # Build a readable list of the offending characters
    bad_chars: list[str] = []
    for i, ch in enumerate(value):
        if ord(ch) > 127:
            bad_chars.append(f"  position {i}: {ch!r} (U+{ord(ch):04X})")
    sanitized = value.encode("ascii", errors="ignore").decode("ascii")

    print(
        f"\n  Warning: {key} contains non-ASCII characters that will break API requests.\n"
        f"  This usually happens when copy-pasting from a PDF, rich-text editor,\n"
        f"  or web page that substitutes lookalike Unicode glyphs for ASCII letters.\n"
        f"\n"
        + "\n".join(f"  {line}" for line in bad_chars[:5])
        + ("\n  ... and more" if len(bad_chars) > 5 else "")
        + f"\n\n  The non-ASCII characters have been stripped automatically.\n"
        f"  If authentication fails, re-copy the key from the provider's dashboard.\n",
        file=sys.stderr,
    )
    return sanitized

def save_env_value(key: str, value: str):
    """Save or update a value in ~/.kabuqina/.env."""
    if is_managed():
        managed_error(f"set {key}")
        return
    if not _ENV_VAR_NAME_RE.match(key):
        raise ValueError(f"Invalid environment variable name: {key!r}")
    value = value.replace("\n", "").replace("\r", "")
    # API keys / tokens must be ASCII — strip non-ASCII with a warning.
    value = _check_non_ascii_credential(key, value)
    ensure_kabuqina_home()
    env_path = get_env_path()

    # On Windows, open() defaults to the system locale (cp1252) which can
    # cause OSError errno 22 on UTF-8 .env files.
    read_kw = {"encoding": "utf-8", "errors": "replace"} if _IS_WINDOWS else {}
    write_kw = {"encoding": "utf-8"} if _IS_WINDOWS else {}

    lines = []
    if env_path.exists():
        with open(env_path, **read_kw) as f:
            lines = f.readlines()
        # Sanitize on every read: split concatenated keys, drop stale placeholders
        lines = _sanitize_env_lines(lines)

    # Find and update or append
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        # Ensure there's a newline at the end of the file before appending
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")
    
    fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix='.tmp', prefix='.env_')
    # Preserve original permissions so Docker volume mounts aren't clobbered.
    original_mode = None
    if env_path.exists():
        try:
            original_mode = stat.S_IMODE(env_path.stat().st_mode)
        except OSError:
            pass
    try:
        with os.fdopen(fd, 'w', **write_kw) as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp_path, env_path)
        # Restore original permissions before _secure_file may tighten them.
        if original_mode is not None:
            try:
                os.chmod(env_path, original_mode)
            except OSError:
                pass
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    _secure_file(env_path)

    os.environ[key] = value

def remove_env_value(key: str) -> bool:
    """Remove a key from ~/.kabuqina/.env and os.environ.

    Returns True if the key was found and removed, False otherwise.
    """
    if is_managed():
        managed_error(f"remove {key}")
        return False
    if not _ENV_VAR_NAME_RE.match(key):
        raise ValueError(f"Invalid environment variable name: {key!r}")
    env_path = get_env_path()
    if not env_path.exists():
        os.environ.pop(key, None)
        return False

    read_kw = {"encoding": "utf-8", "errors": "replace"} if _IS_WINDOWS else {}
    write_kw = {"encoding": "utf-8"} if _IS_WINDOWS else {}

    with open(env_path, **read_kw) as f:
        lines = f.readlines()
    lines = _sanitize_env_lines(lines)

    new_lines = [line for line in lines if not line.strip().startswith(f"{key}=")]
    found = len(new_lines) < len(lines)

    if found:
        fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix='.tmp', prefix='.env_')
        # Preserve original permissions so Docker volume mounts aren't clobbered.
        original_mode = None
        try:
            original_mode = stat.S_IMODE(env_path.stat().st_mode)
        except OSError:
            pass
        try:
            with os.fdopen(fd, 'w', **write_kw) as f:
                f.writelines(new_lines)
                f.flush()
                os.fsync(f.fileno())
            atomic_replace(tmp_path, env_path)
            if original_mode is not None:
                try:
                    os.chmod(env_path, original_mode)
                except OSError:
                    pass
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        _secure_file(env_path)

    os.environ.pop(key, None)
    return found

def save_anthropic_oauth_token(value: str, save_fn=None):
    """Persist an Anthropic OAuth/setup token and clear the API-key slot."""
    writer = save_fn or save_env_value
    writer("ANTHROPIC_TOKEN", value)
    writer("ANTHROPIC_API_KEY", "")

def use_anthropic_claude_code_credentials(save_fn=None):
    """Use Claude Code's own credential files instead of persisting env tokens."""
    writer = save_fn or save_env_value
    writer("ANTHROPIC_TOKEN", "")
    writer("ANTHROPIC_API_KEY", "")

def save_anthropic_api_key(value: str, save_fn=None):
    """Persist an Anthropic API key and clear the OAuth/setup-token slot."""
    writer = save_fn or save_env_value
    writer("ANTHROPIC_API_KEY", value)
    writer("ANTHROPIC_TOKEN", "")

def save_env_value_secure(key: str, value: str) -> Dict[str, Any]:
    save_env_value(key, value)
    return {
        "success": True,
        "stored_as": key,
        "validated": False,
    }

def reload_env() -> int:
    """Re-read ~/.kabuqina/.env into os.environ. Returns count of vars updated.

    Adds/updates vars that changed and removes vars that were deleted from
    the .env file (but only vars known to Kabuqina — OPTIONAL_ENV_VARS and
    _EXTRA_ENV_KEYS — to avoid clobbering unrelated environment).
    """
    env_vars = load_env()
    known_keys = set(OPTIONAL_ENV_VARS.keys()) | _EXTRA_ENV_KEYS
    count = 0
    for key, value in env_vars.items():
        if os.environ.get(key) != value:
            os.environ[key] = value
            count += 1
    # Remove known Kabuqina vars that are no longer in .env
    for key in known_keys:
        if key not in env_vars and key in os.environ:
            del os.environ[key]
            count += 1
    return count

def _current_load_env():
    """Return the active dotenv loader, honoring config facade monkeypatches."""
    facade = sys.modules.get("kabuqina_cli.config")
    facade_loader = getattr(facade, "load_env", None)
    if facade_loader is not None and facade_loader is not load_env:
        return facade_loader
    return load_env

def get_env_value(key: str) -> Optional[str]:
    """Get a value from ~/.kabuqina/.env or environment."""
    # Check environment first
    if key in os.environ:
        return os.environ[key]
    
    # Then check .env file
    env_vars = _current_load_env()()
    return env_vars.get(key)

def redact_key(key: str) -> str:
    """Redact an API key for display.

    Thin wrapper over :func:`agent.redact.mask_secret` — preserves the
    "(not set)" placeholder in dim color for the empty case.
    """
    from agent.redact import mask_secret
    return mask_secret(key, empty=color("(not set)", Colors.DIM))
