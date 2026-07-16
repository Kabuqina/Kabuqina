#!/usr/bin/env python3
"""
Memory Tool Module - Persistent Curated Memory

Provides bounded, file-backed memory that persists across sessions. Two stores:
  - MEMORY.md: agent's personal notes and observations (environment facts, project
    conventions, tool quirks, things learned)
  - USER.md: what the agent knows about the user (preferences, communication style,
    expectations, workflow habits)

Both are injected into the system prompt as a frozen snapshot at session start.
Mid-session writes update files on disk immediately (durable) but do NOT change
the system prompt -- this preserves the prefix cache for the entire session.
The snapshot refreshes on the next session start.

Entry delimiter: § (section sign). Entries can be multiline.
Character limits (not tokens) because char counts are model-independent.

Every entry is tagged with metadata on write::

    [src:<platform>] [ts:<epoch>] [scope:<private|shared>] content here

Tags are parsed out on read and used for cross-platform filtering so that
gateway bots (weixin, telegram, etc.) only see own-source and ``scope:shared``
entries within a configurable time window.  The LLM never sees tags — they
are stripped before system prompt injection and before tool-response return.

Design:
- Single `memory` tool with action parameter: add, replace, remove, read
- replace/remove use short unique substring matching (not full text or IDs)
- Behavioral guidance lives in the tool schema description
- Frozen snapshot pattern: system prompt is stable, tool responses show live state
- Tags managed by ``_strip_entry_tags()`` and ``_make_tagged_entry()``
"""

import json
import logging
import os
import re
import tempfile
import time as _time
from contextlib import contextmanager
from pathlib import Path
from kabuqina_constants import get_kabuqina_home
from typing import Dict, Any, List, Optional

from utils import atomic_replace

# fcntl is Unix-only; on Windows use msvcrt for file locking
msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None
    try:
        import msvcrt
    except ImportError:
        pass

logger = logging.getLogger(__name__)

# Where memory files live — resolved dynamically so profile overrides
# (HERMES_HOME env var changes) are always respected.  The old module-level
# constant was cached at import time and could go stale if a profile switch
# happened after the first import.
def get_memory_dir() -> Path:
    """Return the profile-scoped memories directory."""
    return get_kabuqina_home() / "memories"

ENTRY_DELIMITER = "\n§\n"

# Tag prefix regex for entry metadata: [key:value] [key:value] ... content
_TAG_RE = re.compile(r'^\[(\w+):([^\]]*)\]\s*')


# ---------------------------------------------------------------------------
# Entry tagging helpers — source platform, timestamp, and scope metadata.
# ---------------------------------------------------------------------------

def _strip_entry_tags(entry: str) -> tuple[Dict[str, str], str]:
    """Parse leading tag prefix from an entry.

    Returns (tags_dict, content_without_tags).
    Untagged entries return ({}, entry) with src="legacy".
    """
    tags: Dict[str, str] = {}
    rest = entry.strip()
    while True:
        m = _TAG_RE.match(rest)
        if not m:
            break
        tags[m.group(1)] = m.group(2)
        rest = rest[m.end():]
    if not tags:
        tags["src"] = "legacy"
    return tags, rest.strip()


def _make_tagged_entry(content: str, source_platform: str) -> str:
    """Build a tag-prefixed entry string for storage.

    Desktop (cli) entries default to scope=shared — visible across all platforms.
    Gateway entries default to scope=private — visible only on the same platform.
    """
    ts = int(_time.time())
    scope = "shared" if source_platform == "cli" else "private"
    return f"[src:{source_platform}] [ts:{ts}] [scope:{scope}] {content.strip()}"


# ---------------------------------------------------------------------------
# Memory content scanning — lightweight check for injection/exfiltration
# in content that gets injected into the system prompt.
# ---------------------------------------------------------------------------

_MEMORY_THREAT_PATTERNS = [
    # Prompt injection
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    # Exfiltration via curl/wget with secrets
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets"),
    # Persistence via shell rc
    (r'authorized_keys', "ssh_backdoor"),
    (r'\$HOME/\.ssh|\~/\.ssh', "ssh_access"),
    (r'\$HOME/\.(?:kabuqina|hermes)/\.env|\~/\.(?:kabuqina|hermes)/\.env', "kabuqina_env"),
]

# Subset of invisible chars for injection detection
_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


def _scan_memory_content(content: str) -> Optional[str]:
    """Scan memory content for injection/exfil patterns. Returns error string if blocked."""
    # Check invisible unicode
    for char in _INVISIBLE_CHARS:
        if char in content:
            return f"Blocked: content contains invisible unicode character U+{ord(char):04X} (possible injection)."

    # Check threat patterns
    for pattern, pid in _MEMORY_THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"Blocked: content matches threat pattern '{pid}'. Memory entries are injected into the system prompt and must not contain injection or exfiltration payloads."

    return None


class MemoryStore:
    """
    Bounded curated memory with file persistence. One instance per AIAgent.

    Maintains two parallel states:
      - _system_prompt_snapshot: frozen at load time, used for system prompt injection.
        Never mutated mid-session. Keeps prefix cache stable.
      - memory_entries / user_entries: live state, mutated by tool calls, persisted to disk.
        Tool responses always reflect this live state.
    """

    def __init__(self, memory_char_limit: int = 2200, user_char_limit: int = 1375,
                 source_platform: str = "cli", gateway_max_age_hours: int = 168,
                 chat_type: str = ""):
        self.memory_entries: List[str] = []
        self.user_entries: List[str] = []
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit
        self.source_platform = source_platform
        self._chat_type = chat_type
        self._is_group = (chat_type == "group")
        self.gateway_max_age_seconds: Optional[int] = (
            gateway_max_age_hours * 3600 if gateway_max_age_hours > 0 else None
        )
        # Frozen snapshot for system prompt -- set once at load_from_disk()
        self._system_prompt_snapshot: Dict[str, str] = {"memory": "", "user": ""}
        # Host preferences preamble (read-only, injected separately from memory).
        self._host_prefs: str = ""

    def _filter_entries(self, entries: List[str]) -> List[str]:
        """Filter entries by platform scope and recency.

        Desktop (source_platform=="cli") sees everything unfiltered.
        Gateway platforms see only own-source/scope:shared entries within the
        time window.  Legacy (untagged) entries are visible to all.
        """
        if self.source_platform == "cli":
            return list(entries)

        now = _time.time()
        result: List[str] = []
        for e in entries:
            tags, _content = _strip_entry_tags(e)
            src = tags.get("src", "legacy")
            scope = tags.get("scope", "private")
            ts = int(tags.get("ts", "0"))

            # Legacy (pre-tagging) entries are visible to everyone.
            if src == "legacy":
                result.append(e)
                continue

            # Visible if it's from the same platform or marked shared.
            if src != self.source_platform and scope != "shared":
                continue

            # Time-window check for gateway platforms.
            if self.gateway_max_age_seconds is not None and ts > 0:
                if (now - ts) >= self.gateway_max_age_seconds:
                    continue

            result.append(e)
        return result

    def load_from_disk(self):
        """Load entries from MEMORY.md, USER.md, and _host_prefs.md; capture system prompt snapshot."""
        mem_dir = get_memory_dir()
        mem_dir.mkdir(parents=True, exist_ok=True)

        self.memory_entries = self._read_file(mem_dir / "MEMORY.md")
        self.user_entries = self._read_file(mem_dir / "USER.md")

        # Deduplicate entries (preserves order, keeps first occurrence)
        self.memory_entries = list(dict.fromkeys(self.memory_entries))
        self.user_entries = list(dict.fromkeys(self.user_entries))

        # Load _host_prefs.md (host-shared preferences, read-only).
        # Not present in group chats (privacy).
        self._host_prefs = ""
        if not self._is_group:
            prefs_path = get_kabuqina_home() / "_host_prefs.md"
            try:
                raw = prefs_path.read_text(encoding="utf-8").strip()
                if raw:
                    self._host_prefs = raw
            except (OSError, IOError):
                pass

        # Apply platform-scope and age filters for the system prompt snapshot.
        # The in-memory state (self.memory_entries / self.user_entries) keeps ALL
        # entries so mutations (add/replace/remove) never lose cross-platform data.
        visible_mem = self._filter_entries(self.memory_entries)
        visible_user = self._filter_entries(self.user_entries)

        # In group chats, memory blocks are emptied (system prompt never leaks
        # user-specific data).  The in-memory state is NOT cleared — tool calls
        # still use it for internal decision-making — but the snapshot for the
        # LLM is blanked.
        if self._is_group:
            visible_mem = []
            visible_user = []

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "memory": self._render_block("memory", visible_mem),
            "user": self._render_block("user", visible_user),
        }

    @staticmethod
    @contextmanager
    def _file_lock(path: Path):
        """Acquire an exclusive file lock for read-modify-write safety.

        Uses a separate .lock file so the memory file itself can still be
        atomically replaced via os.replace().
        """
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        if fcntl is None and msvcrt is None:
            yield
            return

        if msvcrt and (not lock_path.exists() or lock_path.stat().st_size == 0):
            lock_path.write_text(" ", encoding="utf-8")

        fd = open(lock_path, "r+" if msvcrt else "a+")
        try:
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_EX)
            else:
                fd.seek(0)
                msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
            yield
        finally:
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_UN)
            elif msvcrt:
                try:
                    fd.seek(0)
                    msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
                except (OSError, IOError):
                    pass
            fd.close()

    @staticmethod
    def _path_for(target: str) -> Path:
        mem_dir = get_memory_dir()
        if target == "user":
            return mem_dir / "USER.md"
        return mem_dir / "MEMORY.md"

    def _reload_target(self, target: str):
        """Re-read entries from disk into in-memory state.

        Called under file lock to get the latest state before mutating.
        """
        fresh = self._read_file(self._path_for(target))
        fresh = list(dict.fromkeys(fresh))  # deduplicate
        self._set_entries(target, fresh)

    def save_to_disk(self, target: str):
        """Persist entries to the appropriate file. Called after every mutation."""
        get_memory_dir().mkdir(parents=True, exist_ok=True)
        self._write_file(self._path_for(target), self._entries_for(target))

    def _entries_for(self, target: str) -> List[str]:
        if target == "user":
            return self.user_entries
        return self.memory_entries

    def _set_entries(self, target: str, entries: List[str]):
        if target == "user":
            self.user_entries = entries
        else:
            self.memory_entries = entries

    def _char_count(self, target: str) -> int:
        entries = self._entries_for(target)
        if not entries:
            return 0
        # Count content without tag overhead to keep char budgets predictable.
        stripped_entries = [_strip_entry_tags(e)[1] for e in entries]
        return len(ENTRY_DELIMITER.join(stripped_entries))

    def _char_limit(self, target: str) -> int:
        if target == "user":
            return self.user_char_limit
        return self.memory_char_limit

    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Append a new entry. Returns error if group chat or would exceed limit."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        if self._is_group:
            return {
                "success": False,
                "error": "Memory writes are disabled in group/ multi-user chats to protect participant privacy.",
            }

        # Scan for injection/exfiltration before accepting
        scan_error = _scan_memory_content(content)
        if scan_error:
            return {"success": False, "error": scan_error}

        with self._file_lock(self._path_for(target)):
            # Re-read from disk under lock to pick up writes from other sessions
            self._reload_target(target)

            entries = self._entries_for(target)
            limit = self._char_limit(target)

            # Reject exact duplicates — match against stripped content
            stripped_entries = [_strip_entry_tags(e)[1] for e in entries]
            if content in stripped_entries:
                return self._success_response(target, "Entry already exists (no duplicate added).")

            # Tag the content before storing
            tagged = _make_tagged_entry(content, self.source_platform)

            # Calculate what the new total would be (char budget against content only)
            new_entries = entries + [tagged]
            stripped_new = stripped_entries + [content]
            new_total = len(ENTRY_DELIMITER.join(stripped_new))

            if new_total > limit:
                current = self._char_count(target)
                return {
                    "success": False,
                    "error": (
                        f"Memory at {current:,}/{limit:,} chars. "
                        f"Adding this entry ({len(content)} chars) would exceed the limit. "
                        f"Replace or remove existing entries first."
                    ),
                    "current_entries": stripped_entries,
                    "usage": f"{current:,}/{limit:,}",
                }

            entries.append(tagged)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry added.")

    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}

        if self._is_group:
            return {
                "success": False,
                "error": "Memory writes are disabled in group/ multi-user chats to protect participant privacy.",
            }

        # Scan replacement content for injection/exfiltration
        scan_error = _scan_memory_content(new_content)
        if scan_error:
            return {"success": False, "error": scan_error}

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            # Match old_text against stripped content (LLM never sees tags)
            stripped_pairs = [(i, e, _strip_entry_tags(e)[1]) for i, e in enumerate(entries)]
            matches = [(i, e) for i, e, s in stripped_pairs if old_text in s]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                # Check if all matches have the same stripped content
                unique_texts = set(s for _, _, s in stripped_pairs if old_text in s)
                if len(unique_texts) > 1:
                    previews = [s[:80] + ("..." if len(s) > 80 else "") for _, _, s in stripped_pairs if old_text in s]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }
                # All identical -- safe to replace just the first

            idx = matches[0][0]
            limit = self._char_limit(target)

            # Tag the replacement content
            tagged = _make_tagged_entry(new_content, self.source_platform)

            # Check budget against stripped content only
            stripped_all = [_strip_entry_tags(e)[1] for e in entries]
            stripped_all[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(stripped_all))

            if new_total > limit:
                return {
                    "success": False,
                    "error": (
                        f"Replacement would put memory at {new_total:,}/{limit:,} chars. "
                        f"Shorten the new content or remove other entries first."
                    ),
                }

            entries[idx] = tagged
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry replaced.")

    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, remove it."""
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}

        if self._is_group:
            return {
                "success": False,
                "error": "Memory writes are disabled in group/ multi-user chats to protect participant privacy.",
            }

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            # Match old_text against stripped content (LLM never sees tags)
            stripped_pairs = [(i, e, _strip_entry_tags(e)[1]) for i, e in enumerate(entries)]
            matches = [(i, e) for i, e, s in stripped_pairs if old_text in s]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                # Check if all matches have the same stripped content
                unique_texts = set(s for _, _, s in stripped_pairs if old_text in s)
                if len(unique_texts) > 1:
                    previews = [s[:80] + ("..." if len(s) > 80 else "") for _, _, s in stripped_pairs if old_text in s]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }
                # All identical -- safe to remove just the first

            idx = matches[0][0]
            entries.pop(idx)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry removed.")

    def format_for_system_prompt(self, target: str) -> Optional[str]:
        """
        Return the frozen snapshot for system prompt injection.

        This returns the state captured at load_from_disk() time, NOT the live
        state. Mid-session writes do not affect this. This keeps the system
        prompt stable across all turns, preserving the prefix cache.

        Supports targets: "memory", "user", "host_prefs".
        Returns None if the snapshot is empty (no entries at load time).
        """
        if target == "host_prefs":
            return self._host_prefs if self._host_prefs else None
        block = self._system_prompt_snapshot.get(target, "")
        return block if block else None

    # -- Internal helpers --

    def _success_response(self, target: str, message: str = None) -> Dict[str, Any]:
        entries = self._entries_for(target)
        # Strip tags so the LLM never sees metadata.
        stripped = [_strip_entry_tags(e)[1] for e in entries]
        current = self._char_count(target)
        limit = self._char_limit(target)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        resp = {
            "success": True,
            "target": target,
            "entries": stripped,
            "usage": f"{pct}% — {current:,}/{limit:,} chars",
            "entry_count": len(stripped),
        }
        if message:
            resp["message"] = message
        return resp

    def _render_block(self, target: str, entries: List[str]) -> str:
        """Render a system prompt block with header and usage indicator."""
        if not entries:
            return ""

        limit = self._char_limit(target)
        # Strip tags so metadata is never visible to the LLM.
        stripped = [_strip_entry_tags(e)[1] for e in entries]
        content = ENTRY_DELIMITER.join(stripped)
        current = len(content)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        if target == "user":
            header = f"USER PROFILE (who the user is) [{pct}% — {current:,}/{limit:,} chars]"
        else:
            header = f"MEMORY (your personal notes) [{pct}% — {current:,}/{limit:,} chars]"

        separator = "═" * 46
        return f"{separator}\n{header}\n{separator}\n{content}"

    @staticmethod
    def _read_file(path: Path) -> List[str]:
        """Read a memory file and split into entries.

        No file locking needed: _write_file uses atomic rename, so readers
        always see either the previous complete file or the new complete file.
        """
        if not path.exists():
            return []
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, IOError):
            return []

        if not raw.strip():
            return []

        # Use ENTRY_DELIMITER for consistency with _write_file. Splitting by "§"
        # alone would incorrectly split entries that contain "§" in their content.
        entries = [e.strip() for e in raw.split(ENTRY_DELIMITER)]
        return [e for e in entries if e]

    @staticmethod
    def _write_file(path: Path, entries: List[str]):
        """Write entries to a memory file using atomic temp-file + rename.

        Previous implementation used open("w") + flock, but "w" truncates the
        file *before* the lock is acquired, creating a race window where
        concurrent readers see an empty file. Atomic rename avoids this:
        readers always see either the old complete file or the new one.
        """
        content = ENTRY_DELIMITER.join(entries) if entries else ""
        try:
            # Write to temp file in same directory (same filesystem for atomic rename)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix=".mem_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                atomic_replace(tmp_path, path)
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except (OSError, IOError) as e:
            raise RuntimeError(f"Failed to write memory file {path}: {e}")


def memory_tool(
    action: str,
    target: str = "memory",
    content: str = None,
    old_text: str = None,
    store: Optional[MemoryStore] = None,
) -> str:
    """
    Single entry point for the memory tool. Dispatches to MemoryStore methods.

    Returns JSON string with results.
    """
    if store is None:
        return tool_error("Memory is not available. It may be disabled in config or this environment.", success=False)

    if target not in ("memory", "user"):
        return tool_error(f"Invalid target '{target}'. Use 'memory' or 'user'.", success=False)

    if action == "add":
        if not content:
            return tool_error("Content is required for 'add' action.", success=False)
        result = store.add(target, content)

    elif action == "replace":
        if not old_text:
            return tool_error("old_text is required for 'replace' action.", success=False)
        if not content:
            return tool_error("content is required for 'replace' action.", success=False)
        result = store.replace(target, old_text, content)

    elif action == "remove":
        if not old_text:
            return tool_error("old_text is required for 'remove' action.", success=False)
        result = store.remove(target, old_text)

    else:
        return tool_error(f"Unknown action '{action}'. Use: add, replace, remove", success=False)

    return json.dumps(result, ensure_ascii=False)


def check_memory_requirements() -> bool:
    """Memory tool has no external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

MEMORY_SCHEMA = {
    "name": "memory",
    "description": (
        "Save durable information to persistent memory that survives across sessions. "
        "Memory is injected into future turns, so keep it compact and focused on facts "
        "that will still matter later.\n\n"
        "WHEN TO SAVE (do this proactively, don't wait to be asked):\n"
        "- User corrects you or says 'remember this' / 'don't do that again'\n"
        "- User shares a preference, habit, or personal detail (name, role, timezone, coding style)\n"
        "- You discover something about the environment (OS, installed tools, project structure)\n"
        "- You learn a convention, API quirk, or workflow specific to this user's setup\n"
        "- You identify a stable fact that will be useful again in future sessions\n\n"
        "PRIORITY: User preferences and corrections > environment facts > procedural knowledge. "
        "The most valuable memory prevents the user from having to repeat themselves.\n\n"
        "Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO "
        "state to memory; use session_search to recall those from past transcripts.\n"
        "If you've discovered a new way to do something, solved a problem that could be "
        "necessary later, save it as a skill with the skill tool.\n\n"
        "TWO TARGETS:\n"
        "- 'user': who the user is -- name, role, preferences, communication style, pet peeves\n"
        "- 'memory': your notes -- environment facts, project conventions, tool quirks, lessons learned\n\n"
        "ACTIONS: add (new entry), replace (update existing -- old_text identifies it), "
        "remove (delete -- old_text identifies it).\n\n"
        "SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, and temporary task state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove"],
                "description": "The action to perform."
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which memory store: 'memory' for personal notes, 'user' for user profile."
            },
            "content": {
                "type": "string",
                "description": "The entry content. Required for 'add' and 'replace'."
            },
            "old_text": {
                "type": "string",
                "description": "Short unique substring identifying the entry to replace or remove."
            },
        },
        "required": ["action", "target"],
    },
}


# --- Registry ---
from tools.registry import registry, tool_error

registry.register(
    name="memory",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=lambda args, **kw: memory_tool(
        action=args.get("action", ""),
        target=args.get("target", "memory"),
        content=args.get("content"),
        old_text=args.get("old_text"),
        store=kw.get("store")),
    check_fn=check_memory_requirements,
    emoji="🧠",
)



