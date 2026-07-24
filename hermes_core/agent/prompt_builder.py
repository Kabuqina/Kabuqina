"""System prompt assembly -- identity, platform hints, skills index, context files.

All functions are stateless. AIAgent._build_system_prompt() calls these to
assemble pieces, then combines them with memory and ephemeral prompts.
"""

import json
import logging
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path

from kabuqina_constants import get_kabuqina_home, get_skills_dir, is_wsl
from typing import Optional

from agent.skill_utils import (
    extract_skill_conditions,
    extract_skill_description,
    get_all_skills_dirs,
    get_disabled_skill_names,
    iter_skill_index_files,
    parse_frontmatter,
    skill_matches_platform,
)
from utils import atomic_json_write

from kabuqina_cli.default_soul import DEFAULT_SOUL_MD as DEFAULT_AGENT_IDENTITY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context file scanning — detect prompt injection in AGENTS.md, .cursorrules,
# SOUL.md before they get injected into the system prompt.
# ---------------------------------------------------------------------------

_CONTEXT_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    (r'<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->', "html_comment_injection"),
    (r'<\s*div\s+style\s*=\s*["\'][\s\S]*?display\s*:\s*none', "hidden_div"),
    (r'translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)', "translate_execute"),
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)', "read_secrets"),
]

_CONTEXT_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


def _scan_context_content(content: str, filename: str) -> str:
    """Scan context file content for injection. Returns sanitized content."""
    findings = []

    # Check invisible unicode
    for char in _CONTEXT_INVISIBLE_CHARS:
        if char in content:
            findings.append(f"invisible unicode U+{ord(char):04X}")

    # Check threat patterns
    for pattern, pid in _CONTEXT_THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(pid)

    if findings:
        logger.warning("Context file %s blocked: %s", filename, ", ".join(findings))
        return f"[BLOCKED: {filename} contained potential prompt injection ({', '.join(findings)}). Content not loaded.]"

    return content


def _find_git_root(start: Path) -> Optional[Path]:
    """Walk *start* and its parents looking for a ``.git`` directory.

    Returns the directory containing ``.git``, or ``None`` if we hit the
    filesystem root without finding one.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


_HERMES_MD_NAMES = (".hermes.md", "HERMES.md")


def _find_hermes_md(cwd: Path) -> Optional[Path]:
    """Discover the nearest ``.hermes.md`` or ``HERMES.md``.

    Search order: *cwd* first, then each parent directory up to (and
    including) the git repository root.  Returns the first match, or
    ``None`` if nothing is found.
    """
    stop_at = _find_git_root(cwd)
    current = cwd.resolve()

    for directory in [current, *current.parents]:
        for name in _HERMES_MD_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        # Stop walking at the git root (or filesystem root).
        if stop_at and directory == stop_at:
            break
    return None


def _strip_yaml_frontmatter(content: str) -> str:
    """Remove optional YAML frontmatter (``---`` delimited) from *content*.

    The frontmatter may contain structured config (model overrides, tool
    settings) that will be handled separately in a future PR.  For now we
    strip it so only the human-readable markdown body is injected into the
    system prompt.
    """
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            # Skip past the closing --- and any trailing newline
            body = content[end + 4:].lstrip("\n")
            return body if body else content
    return content


# =========================================================================
# Constants
# =========================================================================
# DEFAULT_AGENT_IDENTITY is imported from kabuqina_cli.default_soul (single source with seeded SOUL.md).

HERMES_AGENT_HELP_GUIDANCE = (
    "If the user asks about configuring, setting up, or using Kabuqina "
    "itself, load the `kabuqina-agent` skill with skill_view(name='kabuqina-agent') "
    "before answering. Docs: https://hermes-agent.nousresearch.com/docs"
)

# Learning-conduct layer. Always injected right after the identity slot so the
# teaching behavior survives a user-customized SOUL.md: the persona is
# user-editable, the conduct contract is canonical and lives here (see
# docs/immersive-learning-redesign.md — the four design rules).
#
# The rules are self-scoping: the rhythm contract applies to explanatory turns
# only, so plain task/tool requests keep normal agent efficiency. The kq-kp
# trailer is split into its own surface-gated section because only the desktop
# web shell currently strips and renders it; messaging gateway users must never
# see the raw machine-readable block.
LEARNING_CONDUCT_GUIDANCE = (
    "# Learning conduct\n"
    "You are a learning companion. Your success metric is the learner's growth, "
    "not output volume. Apply these rules:\n"
    "\n"
    "## Rhythm (explanatory turns only)\n"
    "When the user is trying to understand something — a concept, a derivation, "
    "a piece of code, a mistake — teach in small steps: cover ONE idea per turn, "
    "keep it short, and end by handing the turn back (a brief check question, or "
    "an invitation to try the next step themselves). Do not dump a full lecture "
    "in one message. This rule does NOT apply to plain task requests (generating "
    "files, formatting, running tools, operational questions) — handle those "
    "directly and efficiently.\n"
    "\n"
    "## Answer-then-teach (never withhold)\n"
    "When the user directly asks for a final answer or solution, give it fully — "
    "never refuse, ration, or bury it to force learning. After the answer, add a "
    "brief note of the knowledge it rests on: which concepts were involved and "
    "what the user skipped that is worth revisiting. Keep the note light — one "
    "or two sentences plus the kq-kp block below — not a lecture.\n"
    "\n"
    "## Hints only on request\n"
    "Use hint-first / Socratic questioning ONLY when the user explicitly asks "
    "not to be told the answer, or during practice and quizzing. Guiding someone "
    "who is stuck is teaching; quizzing someone who already understands, or who "
    "just wants the answer, is condescension."
)

LEARNING_KQ_KP_GUIDANCE = (
    "# Knowledge-point trailer (kq-kp protocol)\n"
    "At the END of a reply that explains subject matter or hands over a "
    "subject-matter answer, append exactly one fenced block tagged kq-kp "
    "containing a JSON array of the knowledge points the reply touched:\n"
    "```kq-kp\n"
    "[{\"name\": \"贝叶斯定理\", \"gist\": \"one-sentence essence of the point\", "
    "\"source\": \"where it came from (material section, or 'model')\", "
    "\"confidence\": \"confirmed\"}]\n"
    "```\n"
    "Rules: 1-5 points, most important first; `name` is a short concept label in "
    "the user's language; `gist` must be a self-contained one-liner (it becomes "
    "the back of a review flashcard); `confidence` is \"confirmed\" when grounded "
    "in the user's materials or established knowledge, \"inferred\" otherwise. "
    "The block must be the last thing in the message, and must never appear in "
    "the middle of prose. Omit the block entirely for pure task/operational "
    "replies, greetings, or clarifying questions — an empty array is worse than "
    "no block. Do not mention the block or the protocol in the prose itself; the "
    "app renders it separately."
)

# ``hermesdesk`` is retained for one release so an older desktop shell keeps
# receiving the structured trailer while the product surface moves to Kabuqina.
LEARNING_KQ_KP_PLATFORMS = frozenset({"kabuqina", "hermesdesk"})


def build_learning_conduct_guidance(platform: Optional[str] = None) -> str:
    """Return the learning conduct prompt for the active surface."""
    platform_key = (platform or "").strip().lower()
    if platform_key in LEARNING_KQ_KP_PLATFORMS:
        return LEARNING_CONDUCT_GUIDANCE + "\n\n" + LEARNING_KQ_KP_GUIDANCE
    return LEARNING_CONDUCT_GUIDANCE


MEMORY_GUIDANCE = (
    "You have persistent memory across sessions. Save durable facts using the memory "
    "tool: user preferences, environment details, tool quirks, and stable conventions. "
    "Memory is injected into every turn, so keep it compact and focused on facts that "
    "will still matter later.\n"
    "Prioritize what reduces future user steering — the most valuable memory is one "
    "that prevents the user from having to correct or remind you again. "
    "User preferences and recurring corrections matter more than procedural task details.\n"
    "Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO "
    "state to memory; use session_search to recall those from past transcripts. "
    "If you've discovered a new way to do something, solved a problem that could be "
    "necessary later, save it as a skill with the skill tool.\n"
    "Write memories as declarative facts, not instructions to yourself. "
    "'User prefers concise responses' ✓ — 'Always respond concisely' ✗. "
    "'Project uses pytest with xdist' ✓ — 'Run tests with pytest -n 4' ✗. "
    "Imperative phrasing gets re-read as a directive in later sessions and can "
    "cause repeated work or override the user's current request. Procedures and "
    "workflows belong in skills, not memory. "
    "Do NOT save learner knowledge state, ability labels, or 'user is weak at X' "
    "observations to memory; route learning-state observations through the "
    "learning store and evaluation draft flow."
)

SESSION_SEARCH_GUIDANCE = (
    "When the user references something from a past conversation or you suspect "
    "relevant cross-session context exists, use session_search to recall it before "
    "asking them to repeat themselves."
)

SKILLS_GUIDANCE = (
    "After completing a complex task (5+ tool calls), fixing a tricky error, "
    "or discovering a non-trivial workflow, save the approach as a "
    "skill with skill_manage so you can reuse it next time.\n"
    "When using a skill and finding it outdated, incomplete, or wrong, "
    "patch it immediately with skill_manage(action='patch') — don't wait to be asked. "
    "Skills that aren't maintained become liabilities."
)

TOOL_USE_ENFORCEMENT_GUIDANCE = (
    "# Tool-use enforcement\n"
    "You MUST use your tools to take action — do not describe what you would do "
    "or plan to do without actually doing it. When you say you will perform an "
    "action (e.g. 'I will run the tests', 'Let me check the file', 'I will create "
    "the project'), you MUST immediately make the corresponding tool call in the same "
    "response. Never end your turn with a promise of future action — execute it now.\n"
    "Keep working until the task is actually complete. Do not stop with a summary of "
    "what you plan to do next time. If you have tools available that can accomplish "
    "the task, use them instead of telling the user what you would do.\n"
    "Every response should either (a) contain tool calls that make progress, or "
    "(b) deliver a final result to the user. Responses that only describe intentions "
    "without acting are not acceptable."
)

# Model name substrings that trigger tool-use enforcement guidance.
# Add new patterns here when a model family needs explicit steering.
TOOL_USE_ENFORCEMENT_MODELS = ("gpt", "gemini", "gemma", "grok")

# OpenAI GPT-specific execution guidance.  Addresses known failure modes
# where GPT models abandon work on partial results, skip prerequisite lookups,
# hallucinate instead of using tools, and declare "done" without verification.
# Inspired by patterns from OpenAI's GPT-5.4 prompting guide & OpenClaw PR #38953.
OPENAI_MODEL_EXECUTION_GUIDANCE = (
    "# Execution discipline\n"
    "<tool_persistence>\n"
    "- Use tools whenever they improve correctness, completeness, or grounding.\n"
    "- Do not stop early when another tool call would materially improve the result.\n"
    "- If a tool returns empty or partial results, retry with a different query or "
    "strategy before giving up.\n"
    "- Keep calling tools until: (1) the task is complete, AND (2) you have verified "
    "the result.\n"
    "</tool_persistence>\n"
    "\n"
    "<mandatory_tool_use>\n"
    "NEVER answer these from memory or mental computation — ALWAYS use a tool:\n"
    "- Arithmetic, math, calculations → use terminal or execute_code\n"
    "- Hashes, encodings, checksums → use terminal (e.g. sha256sum, base64)\n"
    "- Current time, date, timezone → use get_current_time (or terminal `date` if available)\n"
    "- System state: OS, CPU, memory, disk, ports, processes → use terminal\n"
    "- File contents, sizes, line counts → use read_file, search_files, or terminal\n"
    "- Git history, branches, diffs → use terminal\n"
    "- Current facts (weather, news, versions) → use web_search\n"
    "Your memory and user profile describe the USER, not the system you are "
    "running on. The execution environment may differ from what the user profile "
    "says about their personal setup.\n"
    "</mandatory_tool_use>\n"
    "\n"
    "<act_dont_ask>\n"
    "When a question has an obvious default interpretation, act on it immediately "
    "instead of asking for clarification. Examples:\n"
    "- 'Is port 443 open?' → check THIS machine (don't ask 'open where?')\n"
    "- 'What OS am I running?' → check the live system (don't use user profile)\n"
    "- 'What time is it?' → call get_current_time (don't guess)\n"
    "Only ask for clarification when the ambiguity genuinely changes what tool "
    "you would call.\n"
    "</act_dont_ask>\n"
    "\n"
    "<prerequisite_checks>\n"
    "- Before taking an action, check whether prerequisite discovery, lookup, or "
    "context-gathering steps are needed.\n"
    "- Do not skip prerequisite steps just because the final action seems obvious.\n"
    "- If a task depends on output from a prior step, resolve that dependency first.\n"
    "</prerequisite_checks>\n"
    "\n"
    "<verification>\n"
    "Before finalizing your response:\n"
    "- Correctness: does the output satisfy every stated requirement?\n"
    "- Grounding: are factual claims backed by tool outputs or provided context?\n"
    "- Formatting: does the output match the requested format or schema?\n"
    "- Safety: if the next step has side effects (file writes, commands, API calls), "
    "confirm scope before executing.\n"
    "</verification>\n"
    "\n"
    "<missing_context>\n"
    "- If required context is missing, do NOT guess or hallucinate an answer.\n"
    "- Use the appropriate lookup tool when missing information is retrievable "
    "(search_files, web_search, read_file, etc.).\n"
    "- Ask a clarifying question only when the information cannot be retrieved by tools.\n"
    "- If you must proceed with incomplete information, label assumptions explicitly.\n"
    "</missing_context>"
)

# Gemini/Gemma-specific operational guidance, adapted from OpenCode's gemini.txt.
# Injected alongside TOOL_USE_ENFORCEMENT_GUIDANCE when the model is Gemini or Gemma.
GOOGLE_MODEL_OPERATIONAL_GUIDANCE = (
    "# Google model operational directives\n"
    "Follow these operational rules strictly:\n"
    "- **Absolute paths:** Always construct and use absolute file paths for all "
    "file system operations. Combine the project root with relative paths.\n"
    "- **Verify first:** Use read_file/search_files to check file contents and "
    "project structure before making changes. Never guess at file contents.\n"
    "- **Dependency checks:** Never assume a library is available. Check "
    "package.json, requirements.txt, Cargo.toml, etc. before importing.\n"
    "- **Conciseness:** Keep explanatory text brief — a few sentences, not "
    "paragraphs. Focus on actions and results over narration.\n"
    "- **Parallel tool calls:** When you need to perform multiple independent "
    "operations (e.g. reading several files), make all the tool calls in a "
    "single response rather than sequentially.\n"
    "- **Non-interactive commands:** Use flags like -y, --yes, --non-interactive "
    "to prevent CLI tools from hanging on prompts.\n"
    "- **Keep going:** Work autonomously until the task is fully resolved. "
    "Don't stop with a plan — execute it.\n"
)

# Model name substrings that should use the 'developer' role instead of
# 'system' for the system prompt.  OpenAI's newer GPT models
# give stronger instruction-following weight to the 'developer' role.
# The swap happens at the API boundary in _build_api_kwargs() so internal
# message representation stays consistent ("system" everywhere).
DEVELOPER_ROLE_MODELS = ("gpt-5",)

PLATFORM_HINTS = {
    "whatsapp": (
        "You are on a text messaging communication platform, WhatsApp. "
        "Please do not use markdown as it does not render. "
        "You can send media files natively: to deliver a file to the user, "
        "include MEDIA:/absolute/path/to/file in your response. The file "
        "will be sent as a native WhatsApp attachment — images (.jpg, .png, "
        ".webp) appear as photos, videos (.mp4, .mov) play inline, and other "
        "files arrive as downloadable documents. You can also include image "
        "URLs in markdown format ![alt](url) and they will be sent as photos."
    ),
    "telegram": (
        "You are on a text messaging communication platform, Telegram. "
        "Standard markdown is automatically converted to Telegram format. "
        "Supported: **bold**, *italic*, ~~strikethrough~~, ||spoiler||, "
        "`inline code`, ```code blocks```, [links](url), and ## headers. "
        "Telegram has NO table syntax — prefer bullet lists or labeled "
        "key: value pairs over pipe tables (any tables you do emit are "
        "auto-rewritten into row-group bullets, which you can produce "
        "directly for cleaner output). "
        "You can send media files natively: to deliver a file to the user, "
        "include MEDIA:/absolute/path/to/file in your response. Images "
        "(.png, .jpg, .webp) appear as photos, audio (.ogg) sends as voice "
        "bubbles, and videos (.mp4) play inline. You can also include image "
        "URLs in markdown format ![alt](url) and they will be sent as native photos."
    ),
    "email": (
        "You are communicating via email. Write clear, well-structured responses "
        "suitable for email. Use plain text formatting (no markdown). "
        "Keep responses concise but complete. You can send file attachments — "
        "include MEDIA:/absolute/path/to/file in your response. The subject line "
        "is preserved for threading. Do not include greetings or sign-offs unless "
        "contextually appropriate."
    ),
    "cron": (
        "You are running as a scheduled cron job. There is no user present — you "
        "cannot ask questions, request clarification, or wait for follow-up. Execute "
        "the task fully and autonomously, making reasonable decisions where needed. "
        "Your final response is automatically delivered to the job's configured "
        "destination — put the primary content directly in your response."
    ),
    "cli": (
        "You are a CLI AI Agent. Try not to use markdown but simple text "
        "renderable inside a terminal. "
        "File delivery: there is no attachment channel — the user reads your "
        "response directly in their terminal. Do NOT emit MEDIA:/path tags "
        "(those are only intercepted on messaging platforms like Telegram, "
        "Discord, Slack, etc.; on the CLI they render as literal text). "
        "When referring to a file you created or changed, just state its "
        "absolute path in plain text; the user can open it from there."
    ),
    "weixin": (
        "You are on Weixin/WeChat. Markdown formatting is supported, so you may use it when "
        "it improves readability, but keep the message compact and chat-friendly. You can send media files natively: "
        "include MEDIA:/absolute/path/to/file in your response. Images are sent as native "
        "photos, videos play inline when supported, and other files arrive as downloadable "
        "documents. You can also include image URLs in markdown format ![alt](url) and they "
        "will be downloaded and sent as native media when possible."
    ),
    "qqbot": (
        "You are on QQ, a popular Chinese messaging platform. QQ supports markdown formatting "
        "and emoji. You can send media files natively: include MEDIA:/absolute/path/to/file in "
        "your response. Images are sent as native photos, and other files arrive as downloadable "
        "documents."
    ),

}

# ---------------------------------------------------------------------------
# Environment hints — execution-environment awareness for the agent.
# Unlike PLATFORM_HINTS (which describe the messaging channel), these describe
# the machine/OS the agent's tools actually run on.
# ---------------------------------------------------------------------------

WSL_ENVIRONMENT_HINT = (
    "You are running inside WSL (Windows Subsystem for Linux). "
    "The Windows host filesystem is mounted under /mnt/ — "
    "/mnt/c/ is the C: drive, /mnt/d/ is D:, etc. "
    "The user's Windows files are typically at "
    "/mnt/c/Users/<username>/Desktop/, Documents/, Downloads/, etc. "
    "When the user references Windows paths or desktop files, translate "
    "to the /mnt/c/ equivalent. You can list /mnt/c/Users/ to discover "
    "the Windows username if needed."
)


def build_environment_hints() -> str:
    """Return environment-specific guidance for the system prompt.

    Detects WSL, and can be extended for Termux, Docker, etc.
    Returns an empty string when no special environment is detected.
    """
    hints: list[str] = []
    if is_wsl():
        hints.append(WSL_ENVIRONMENT_HINT)
    return "\n\n".join(hints)


CONTEXT_FILE_MAX_CHARS = 20_000
CONTEXT_TRUNCATE_HEAD_RATIO = 0.7
CONTEXT_TRUNCATE_TAIL_RATIO = 0.2


# =========================================================================
# Skills prompt cache
# =========================================================================

_SKILLS_PROMPT_CACHE_MAX = 8
_SKILLS_PROMPT_CACHE: OrderedDict[tuple, str] = OrderedDict()
_SKILLS_PROMPT_CACHE_LOCK = threading.Lock()
_SKILLS_SNAPSHOT_VERSION = 1


def _skills_prompt_snapshot_path() -> Path:
    return get_kabuqina_home() / ".skills_prompt_snapshot.json"


def clear_skills_system_prompt_cache(*, clear_snapshot: bool = False) -> None:
    """Drop the in-process skills prompt cache (and optionally the disk snapshot)."""
    with _SKILLS_PROMPT_CACHE_LOCK:
        _SKILLS_PROMPT_CACHE.clear()
    if clear_snapshot:
        try:
            _skills_prompt_snapshot_path().unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Could not remove skills prompt snapshot: %s", e)


def _build_skills_manifest(skills_dir: Path) -> dict[str, list[int]]:
    """Build an mtime/size manifest of all SKILL.md and DESCRIPTION.md files."""
    manifest: dict[str, list[int]] = {}
    for filename in ("SKILL.md", "DESCRIPTION.md"):
        for path in iter_skill_index_files(skills_dir, filename):
            try:
                st = path.stat()
            except OSError:
                continue
            manifest[str(path.relative_to(skills_dir))] = [st.st_mtime_ns, st.st_size]
    return manifest


def _load_skills_snapshot(skills_dir: Path) -> Optional[dict]:
    """Load the disk snapshot if it exists and its manifest still matches."""
    snapshot_path = _skills_prompt_snapshot_path()
    if not snapshot_path.exists():
        return None
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("version") != _SKILLS_SNAPSHOT_VERSION:
        return None
    if snapshot.get("manifest") != _build_skills_manifest(skills_dir):
        return None
    return snapshot


def _write_skills_snapshot(
    skills_dir: Path,
    manifest: dict[str, list[int]],
    skill_entries: list[dict],
    category_descriptions: dict[str, str],
) -> None:
    """Persist skill metadata to disk for fast cold-start reuse."""
    payload = {
        "version": _SKILLS_SNAPSHOT_VERSION,
        "manifest": manifest,
        "skills": skill_entries,
        "category_descriptions": category_descriptions,
    }
    try:
        atomic_json_write(_skills_prompt_snapshot_path(), payload)
    except Exception as e:
        logger.debug("Could not write skills prompt snapshot: %s", e)


def _build_snapshot_entry(
    skill_file: Path,
    skills_dir: Path,
    frontmatter: dict,
    description: str,
) -> dict:
    """Build a serialisable metadata dict for one skill."""
    rel_path = skill_file.relative_to(skills_dir)
    parts = rel_path.parts
    if len(parts) >= 2:
        skill_name = parts[-2]
        category = "/".join(parts[:-2]) if len(parts) > 2 else parts[0]
    else:
        category = "general"
        skill_name = skill_file.parent.name

    platforms = frontmatter.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]

    return {
        "skill_name": skill_name,
        "category": category,
        "frontmatter_name": str(frontmatter.get("name", skill_name)),
        "description": description,
        "platforms": [str(p).strip() for p in platforms if str(p).strip()],
        "conditions": extract_skill_conditions(frontmatter),
    }


# =========================================================================
# Skills index
# =========================================================================

def _parse_skill_file(skill_file: Path) -> tuple[bool, dict, str]:
    """Read a SKILL.md once and return platform compatibility, frontmatter, and description.

    Returns (is_compatible, frontmatter, description). On any error, returns
    (True, {}, "") to err on the side of showing the skill.
    """
    try:
        raw = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(raw)

        if not skill_matches_platform(frontmatter):
            return False, frontmatter, ""

        return True, frontmatter, extract_skill_description(frontmatter)
    except Exception as e:
        logger.warning("Failed to parse skill file %s: %s", skill_file, e)
        return True, {}, ""


def _skill_should_show(
    conditions: dict,
    available_tools: "set[str] | None",
    available_toolsets: "set[str] | None",
) -> bool:
    """Return False if the skill's conditional activation rules exclude it."""
    if available_tools is None and available_toolsets is None:
        return True  # No filtering info — show everything (backward compat)

    at = available_tools or set()
    ats = available_toolsets or set()

    # fallback_for: hide when the primary tool/toolset IS available
    for ts in conditions.get("fallback_for_toolsets", []):
        if ts in ats:
            return False
    for t in conditions.get("fallback_for_tools", []):
        if t in at:
            return False

    # requires: hide when a required tool/toolset is NOT available
    for ts in conditions.get("requires_toolsets", []):
        if ts not in ats:
            return False
    for t in conditions.get("requires_tools", []):
        if t not in at:
            return False

    return True


def build_skills_system_prompt(
    available_tools: "set[str] | None" = None,
    available_toolsets: "set[str] | None" = None,
) -> str:
    """Build a compact skill index for the system prompt.

    Two-layer cache:
      1. In-process LRU dict keyed by (skills_dir, tools, toolsets)
      2. Disk snapshot (``.skills_prompt_snapshot.json``) validated by
         mtime/size manifest — survives process restarts

    Falls back to a full filesystem scan when both layers miss.

    External skill directories (``skills.external_dirs`` in config.yaml) are
    scanned alongside the local ``~/.kabuqina/skills/`` directory.  External dirs
    are read-only — they appear in the index but new skills are always created
    in the local dir.  Local skills take precedence when names collide.
    """
    skills_dir = get_skills_dir()
    external_dirs = get_all_skills_dirs()[1:]  # skip local (index 0)

    if not skills_dir.exists() and not external_dirs:
        return ""

    # ── Layer 1: in-process LRU cache ─────────────────────────────────
    # Include the resolved platform so per-platform disabled-skill lists
    # produce distinct cache entries (gateway serves multiple platforms).
    from gateway.session_context import get_session_env
    _platform_hint = (
        os.environ.get("HERMES_PLATFORM")
        or get_session_env("HERMES_SESSION_PLATFORM")
        or ""
    )
    disabled = get_disabled_skill_names()
    cache_key = (
        str(skills_dir.resolve()),
        tuple(str(d) for d in external_dirs),
        tuple(sorted(str(t) for t in (available_tools or set()))),
        tuple(sorted(str(ts) for ts in (available_toolsets or set()))),
        _platform_hint,
        tuple(sorted(disabled)),
    )
    with _SKILLS_PROMPT_CACHE_LOCK:
        cached = _SKILLS_PROMPT_CACHE.get(cache_key)
        if cached is not None:
            _SKILLS_PROMPT_CACHE.move_to_end(cache_key)
            return cached

    # ── Layer 2: disk snapshot ────────────────────────────────────────
    snapshot = _load_skills_snapshot(skills_dir)

    skills_by_category: dict[str, list[tuple[str, str]]] = {}
    category_descriptions: dict[str, str] = {}

    if snapshot is not None:
        # Fast path: use pre-parsed metadata from disk
        for entry in snapshot.get("skills", []):
            if not isinstance(entry, dict):
                continue
            skill_name = entry.get("skill_name") or ""
            category = entry.get("category") or "general"
            frontmatter_name = entry.get("frontmatter_name") or skill_name
            platforms = entry.get("platforms") or []
            if not skill_matches_platform({"platforms": platforms}):
                continue
            if frontmatter_name in disabled or skill_name in disabled:
                continue
            if not _skill_should_show(
                entry.get("conditions") or {},
                available_tools,
                available_toolsets,
            ):
                continue
            skills_by_category.setdefault(category, []).append(
                (frontmatter_name, entry.get("description", ""))
            )
        category_descriptions = {
            str(k): str(v)
            for k, v in (snapshot.get("category_descriptions") or {}).items()
        }
    else:
        # Cold path: full filesystem scan + write snapshot for next time
        skill_entries: list[dict] = []
        for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
            is_compatible, frontmatter, desc = _parse_skill_file(skill_file)
            entry = _build_snapshot_entry(skill_file, skills_dir, frontmatter, desc)
            skill_entries.append(entry)
            if not is_compatible:
                continue
            skill_name = entry["skill_name"]
            if entry["frontmatter_name"] in disabled or skill_name in disabled:
                continue
            if not _skill_should_show(
                extract_skill_conditions(frontmatter),
                available_tools,
                available_toolsets,
            ):
                continue
            skills_by_category.setdefault(entry["category"], []).append(
                (entry["frontmatter_name"], entry["description"])
            )

        # Read category-level DESCRIPTION.md files
        for desc_file in iter_skill_index_files(skills_dir, "DESCRIPTION.md"):
            try:
                content = desc_file.read_text(encoding="utf-8")
                fm, _ = parse_frontmatter(content)
                cat_desc = fm.get("description")
                if not cat_desc:
                    continue
                rel = desc_file.relative_to(skills_dir)
                cat = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "general"
                category_descriptions[cat] = str(cat_desc).strip().strip("'\"")
            except Exception as e:
                logger.debug("Could not read skill description %s: %s", desc_file, e)

        _write_skills_snapshot(
            skills_dir,
            _build_skills_manifest(skills_dir),
            skill_entries,
            category_descriptions,
        )

    # ── External skill directories ─────────────────────────────────────
    # Scan external dirs directly (no snapshot caching — they're read-only
    # and typically small).  Local skills already in skills_by_category take
    # precedence: we track seen names and skip duplicates from external dirs.
    seen_skill_names: set[str] = set()
    for cat_skills in skills_by_category.values():
        for name, _desc in cat_skills:
            seen_skill_names.add(name)

    for ext_dir in external_dirs:
        if not ext_dir.exists():
            continue
        for skill_file in iter_skill_index_files(ext_dir, "SKILL.md"):
            try:
                is_compatible, frontmatter, desc = _parse_skill_file(skill_file)
                if not is_compatible:
                    continue
                entry = _build_snapshot_entry(skill_file, ext_dir, frontmatter, desc)
                skill_name = entry["skill_name"]
                frontmatter_name = entry["frontmatter_name"]
                if frontmatter_name in seen_skill_names:
                    continue
                if frontmatter_name in disabled or skill_name in disabled:
                    continue
                if not _skill_should_show(
                    extract_skill_conditions(frontmatter),
                    available_tools,
                    available_toolsets,
                ):
                    continue
                seen_skill_names.add(frontmatter_name)
                skills_by_category.setdefault(entry["category"], []).append(
                    (frontmatter_name, entry["description"])
                )
            except Exception as e:
                logger.debug("Error reading external skill %s: %s", skill_file, e)

        # External category descriptions
        for desc_file in iter_skill_index_files(ext_dir, "DESCRIPTION.md"):
            try:
                content = desc_file.read_text(encoding="utf-8")
                fm, _ = parse_frontmatter(content)
                cat_desc = fm.get("description")
                if not cat_desc:
                    continue
                rel = desc_file.relative_to(ext_dir)
                cat = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "general"
                category_descriptions.setdefault(cat, str(cat_desc).strip().strip("'\""))
            except Exception as e:
                logger.debug("Could not read external skill description %s: %s", desc_file, e)

    if not skills_by_category:
        result = ""
    else:
        index_lines = []
        for category in sorted(skills_by_category.keys()):
            cat_desc = category_descriptions.get(category, "")
            if cat_desc:
                index_lines.append(f"  {category}: {cat_desc}")
            else:
                index_lines.append(f"  {category}:")
            # Deduplicate and sort skills within each category
            seen = set()
            for name, desc in sorted(skills_by_category[category], key=lambda x: x[0]):
                if name in seen:
                    continue
                seen.add(name)
                if desc:
                    index_lines.append(f"    - {name}: {desc}")
                else:
                    index_lines.append(f"    - {name}")

        result = (
            "## Skills (mandatory)\n"
            "Before replying, scan the skills below. If a skill matches or is even partially relevant "
            "to your task, you MUST load it with skill_view(name) and follow its instructions. "
            "Err on the side of loading — it is always better to have context you don't need "
            "than to miss critical steps, pitfalls, or established workflows. "
            "Skills contain specialized knowledge — API endpoints, tool-specific commands, "
            "and proven workflows that outperform general-purpose approaches. Load the skill "
            "even if you think you could handle the task with basic tools like web_search or terminal. "
            "Skills also encode the user's preferred approach, conventions, and quality standards "
            "for tasks like code review, planning, and testing — load them even for tasks you "
            "already know how to do, because the skill defines how it should be done here.\n"
            "Whenever the user asks you to configure, set up, install, enable, disable, modify, "
            "or troubleshoot Kabuqina itself — its CLI, config, models, providers, tools, "
            "skills, voice, gateway, plugins, or any feature — load the `kabuqina-agent` skill "
            "first. It has the actual commands (e.g. `kabuqina config set …`, `kabuqina tools`, "
            "`kabuqina setup`) so you don't have to guess or invent workarounds.\n"
            "If a skill has issues, fix it with skill_manage(action='patch').\n"
            "After difficult/iterative tasks, offer to save as a skill. "
            "If a skill you loaded was missing steps, had wrong commands, or needed "
            "pitfalls you discovered, update it before finishing.\n"
            "\n"
            "<available_skills>\n"
            + "\n".join(index_lines) + "\n"
            "</available_skills>\n"
            "\n"
            "Only proceed without loading a skill if genuinely none are relevant to the task."
        )

    # ── Store in LRU cache ────────────────────────────────────────────
    with _SKILLS_PROMPT_CACHE_LOCK:
        _SKILLS_PROMPT_CACHE[cache_key] = result
        _SKILLS_PROMPT_CACHE.move_to_end(cache_key)
        while len(_SKILLS_PROMPT_CACHE) > _SKILLS_PROMPT_CACHE_MAX:
            _SKILLS_PROMPT_CACHE.popitem(last=False)

    return result


def build_nous_subscription_prompt(valid_tool_names: "set[str] | None" = None) -> str:
    """Build a compact Nous subscription capability block for the system prompt."""
    try:
        from kabuqina_cli.nous_subscription import get_nous_subscription_features
        from tools.tool_backend_helpers import managed_nous_tools_enabled
    except Exception as exc:
        logger.debug("Failed to import Nous subscription helper: %s", exc)
        return ""

    if not managed_nous_tools_enabled():
        return ""

    valid_names = set(valid_tool_names or set())
    relevant_tool_names = {
        "web_search",
        "web_extract",
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_scroll",
        "browser_console",
        "browser_press",
        "browser_get_images",
        "browser_vision",
        "image_generate",
        "text_to_speech",
        "terminal",
        "process",
        "execute_code",
    }

    if valid_names and not (valid_names & relevant_tool_names):
        return ""

    features = get_nous_subscription_features()

    def _status_line(feature) -> str:
        if feature.managed_by_nous:
            return f"- {feature.label}: active via Nous subscription"
        if feature.active:
            current = feature.current_provider or "configured provider"
            return f"- {feature.label}: currently using {current}"
        if feature.included_by_default and features.nous_auth_present:
            return f"- {feature.label}: included with Nous subscription, not currently selected"
        if feature.key == "modal" and features.nous_auth_present:
            return f"- {feature.label}: optional via Nous subscription"
        return f"- {feature.label}: not currently available"

    lines = [
        "# Nous Subscription",
        "Nous subscription includes managed web tools (Firecrawl), image generation (FAL), OpenAI TTS, and browser automation (Browser Use) by default. Modal execution is optional.",
        "Current capability status:",
    ]
    lines.extend(_status_line(feature) for feature in features.items())
    lines.extend(
        [
            "When a Nous-managed feature is active, do not ask the user for Firecrawl, FAL, OpenAI TTS, or Browser-Use API keys.",
            "If the user is not subscribed and asks for a capability that Nous subscription would unlock or simplify, suggest Nous subscription as one option alongside direct setup or local alternatives.",
            "Do not mention subscription unless the user asks about it or it directly solves the current missing capability.",
            "Useful commands: kabuqina setup, kabuqina setup tools, kabuqina setup terminal, kabuqina status.",
        ]
    )
    return "\n".join(lines)


def build_deliverable_planner_prompt(valid_tool_names: "set[str] | None" = None) -> str:
    """Canonical planner guidance for student deliverables (PPT / PDF / HTML).

    This is the **planner layer of the file-generation pipeline**, sunk into the
    agent core so the web (desk) child and the gateway (messaging) child plan
    identically. It is self-gated on the presence of the writer tools, so a
    vanilla Kabuqina session without these tools gets nothing.

    The vocabulary (slide types, layouts, per-structure outlines) is imported
    from ``tools/deliverable_contract.py`` — the same source the writer
    normalizes against — so the planner can never be told to emit a slide type
    the writer would silently rewrite.
    """
    try:
        from tools.deliverable_contract import (
            DELIVERABLE_WRITER_TOOLS,
            PPTX_SLIDE_LAYOUTS,
            PPTX_SLIDE_TYPES,
            PPTX_STRUCTURES,
        )
    except Exception as exc:  # pragma: no cover - defensive import
        logger.debug("Failed to import deliverable contract: %s", exc)
        return ""

    valid_names = set(valid_tool_names or set())
    present = {tool for tool in DELIVERABLE_WRITER_TOOLS if tool in valid_names}
    # Emit only when at least one deliverable writer is actually available — an
    # empty or writer-free tool list means there is nothing to plan toward.
    if not present:
        return ""

    lines: list[str] = [
        "# Student deliverable generation (file-generation pipeline)",
        "When the user asks for a generated file (PPT, PDF, or HTML report / notes), "
        "plan through the four-layer pipeline and never skip a layer:",
        "0. Clarify intent (only when the request is ambiguous and the answer would change the "
        "plan) — before reading, confirm at most one or two of: audience / scenario (course "
        "report vs defense vs self-study), goal (drive one conclusion vs full coverage), and any "
        "chapter / method / metric to emphasize. If the request or the quick-action already "
        "specifies these (e.g. structure / template / visual_master are present, or the user "
        "stated audience and goal), do NOT re-ask — proceed with sensible defaults. Never block a "
        "specific request with questions; ask in one consolidated message, not a chain.",
        "1. Read — use pdf_read_precise / document_read_precise / file tools to read the source material.",
        "2. Material index — call material_index_build to organize already-read material into "
        "reusable evidence (sections / tables / figures / screenshots / code_files / evidence / "
        "uncertain_parts / generation_hints). It is a general layer, not PPT-specific.",
        "3. Plan — turn the material index into a structured outline. Choose what evidence matters; "
        "do not invent screenshots, charts, citations, or results that the material index did not produce.",
        "4. Review then write — call review_outline so the user can approve / amend / edit, and only "
        "after confirmation call the writer tool and return the saved file path.",
        "Quality bar: produce a high-quality deliverable, not a plain-text summary. When real "
        "screenshots or charts are missing, do not pretend material was inserted — use a placeholder "
        "and state what real asset should replace it.",
        "The source format and the deliverable format are independent — compose these layers freely. "
        "Any reader can feed any writer (e.g. read a .docx or .pdf and emit .html, or read a .pdf and "
        "emit .docx). The reader normalizes every input to text/markdown, the material index and the "
        "outline are format-agnostic, and PDF / HTML / Word writers share one sections/blocks contract, "
        "so the same reviewed outline can be written to whichever format the user asked for. Match the "
        "writer to the requested *output*, not to the input file type, and do not force the output "
        "format to match the source.",
    ]

    if "pptx_write" in present:
        slide_types = " / ".join(PPTX_SLIDE_TYPES)
        layouts = " / ".join(PPTX_SLIDE_LAYOUTS)
        lines.append("")
        lines.append("## PPT decks (pptx_write)")
        lines.append(
            "Every slide must declare slide_type (one of: "
            f"{slide_types}), a title, 3-5 bullets, speaker-note `notes`, and an evidence object "
            "or placeholder note. Use screenshot_placeholder / chart_placeholder instead of faking "
            "assets. Include at least one qa_backup slide. Layout is auto-selected per content; to "
            f"force one, set a slide `layout` (one of: {layouts})."
        )
        lines.append(
            "Layout cues (the renderer also auto-selects, but you may set `layout` to steer): "
            "stat_callout / big_number_grid for metric-centric slides — write bullets as "
            "`标签: 数值` (e.g. `准确率: 84%`) so the number renders large; pull_quote for a single "
            "thesis / contribution line; image_text_split to pair a screenshot or chart with "
            "explaining bullets; timeline for phased milestones; icon_grid for 3-6 short parallel "
            "items (modules / features)."
        )
        lines.append(
            "Design intent (optional, emitted on the same pptx_write call — no extra model cost): "
            "for metric slides set `metrics` as an array of {value, label} (e.g. "
            "{\"value\": \"84%\", \"label\": \"准确率\"}) so the number renders large; set `emphasis` "
            "{kind: \"stat\"|\"quote\", value, label} to spotlight the single key number or the core "
            "thesis / contribution line. Prefer structured `metrics` over burying numbers in prose."
        )
        lines.append(
            "Slide content quality — the bar this deck is judged on:\n"
            "- Substance over definitions: every bullet must carry THIS source's specific claim, "
            "finding, number, named method, or result. Cut textbook definitions and generic "
            "background that any deck on the topic could contain.\n"
            "- Thin source: if the material lacks results/experiments (e.g. a survey or short "
            "review), say so plainly and present the paper's organizing argument and contribution "
            "instead of padding with 101-level background. Do not inflate length to hit a slide count.\n"
            "- No redundancy: exactly one agenda slide. Put author / affiliation / date / citation in "
            "the pptx_write `meta` object (it renders on the cover) — never in an agenda or content "
            "slide. An overview slide that lists items must NOT be followed by slides that only "
            "re-list the same items — choose overview OR per-item expansion. Each slide must add "
            "information the previous ones did not.\n"
            "- Placeholder discipline: a slide must never be ONLY a placeholder. Pair every "
            "placeholder with real bullets stating what the asset shows and the takeaway; if you have "
            "no substance for a figure, fold it into a neighbouring content slide rather than spend a "
            "whole slide on an empty frame.\n"
            "- Structured visuals: chart_placeholder must include numeric clues in bullets or "
            "placeholder.caption whenever the source gives numbers (for example `样本数: 500`, "
            "`FMM-MR: 42`, `FMM: 68`). For experiment / evidence slides, prefer a table "
            "or comparison_cards or table with headers/rows over plain bullets so the renderer can "
            "turn them into designed evidence cards instead of generic text columns.\n"
            "- Even depth: give each method / section comparable detail; never leave one listed "
            "method or module as a bare title or placeholder while its siblings get full bullets."
        )
        lines.append(
            "After review_outline passes, call pptx_write with both template and visual_master "
            "(the user's selection arrives in the request). If the student uploaded a school / "
            "course .pptx template, also pass its workspace path as `template_path` — its colours "
            "and fonts are applied so the deck matches the required look. Structure outlines:"
        )
        for structure_id, structure in PPTX_STRUCTURES.items():
            must_cover = "；".join(str(item) for item in structure.get("must_cover") or [])
            lines.append(f"- {structure_id} ({structure.get('title')}): {must_cover}。")

    doc_writers = [name for name in ("pdf_write", "html_write", "docx_write") if name in present]
    if doc_writers:
        lines.append("")
        lines.append("## PDF / HTML / Word reports (" + ", ".join(doc_writers) + ")")
        lines.append(
            "Build a structured document of sections or blocks (block types: heading, paragraph, "
            "bullets, table, code, formula, image_placeholder, page_break) from the material index, "
            "review it, then call the writer. Pass `document` as a real JSON object — never as a "
            "stringified / hand-escaped JSON blob; stringifying it (especially when the source text "
            "contains quotation marks) corrupts the structure and dumps raw JSON onto the page. The "
            "same reviewed outline can target any of these formats: pdf_write renders a print-ready "
            "PDF plus an HTML inspection sidecar; html_write produces a standalone responsive page "
            "(renderer standalone_html_v1); docx_write produces an editable Word file (renderer "
            "python_docx_v1)."
        )

    return "\n".join(lines)


def deliverable_planner_is_active(valid_tool_names: "set[str] | None" = None) -> bool:
    """Whether the Deliverable Planner applies for the given tool set.

    Mirrors the self-gating inside :func:`build_deliverable_planner_prompt`
    (which returns ``""`` when no deliverable writer is present) as a standalone
    predicate, so the STUDY Planner registry can declare activation without
    duplicating the gating logic — both read the same
    ``DELIVERABLE_WRITER_TOOLS`` source, so they cannot drift. This does not
    change the prompt output.
    """
    try:
        from tools.deliverable_contract import DELIVERABLE_WRITER_TOOLS
    except Exception as exc:  # pragma: no cover - defensive import
        logger.debug("Failed to import deliverable contract: %s", exc)
        return False
    valid_names = set(valid_tool_names or set())
    return any(tool in valid_names for tool in DELIVERABLE_WRITER_TOOLS)


# =========================================================================
# Context files (SOUL.md, AGENTS.md, .cursorrules)
# =========================================================================

def _truncate_content(content: str, filename: str, max_chars: int = CONTEXT_FILE_MAX_CHARS) -> str:
    """Head/tail truncation with a marker in the middle."""
    if len(content) <= max_chars:
        return content
    head_chars = int(max_chars * CONTEXT_TRUNCATE_HEAD_RATIO)
    tail_chars = int(max_chars * CONTEXT_TRUNCATE_TAIL_RATIO)
    head = content[:head_chars]
    tail = content[-tail_chars:]
    marker = f"\n\n[...truncated {filename}: kept {head_chars}+{tail_chars} of {len(content)} chars. Use file tools to read the full file.]\n\n"
    return head + marker + tail


def load_soul_md() -> Optional[str]:
    """Load SOUL.md from HERMES_HOME and return its content, or None.

    Used as the agent identity (slot #1 in the system prompt).  When this
    returns content, ``build_context_files_prompt`` should be called with
    ``skip_soul=True`` so SOUL.md isn't injected twice.
    """
    try:
        from kabuqina_cli.config import ensure_kabuqina_home
        ensure_kabuqina_home()
    except Exception as e:
        logger.debug("Could not ensure HERMES_HOME before loading SOUL.md: %s", e)

    soul_path = get_kabuqina_home() / "SOUL.md"
    if not soul_path.exists():
        return None
    try:
        content = soul_path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        content = _scan_context_content(content, "SOUL.md")
        content = _truncate_content(content, "SOUL.md")
        return content
    except Exception as e:
        logger.debug("Could not read SOUL.md from %s: %s", soul_path, e)
        return None


def _load_hermes_md(cwd_path: Path) -> str:
    """.hermes.md / HERMES.md — walk to git root."""
    hermes_md_path = _find_hermes_md(cwd_path)
    if not hermes_md_path:
        return ""
    try:
        content = hermes_md_path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        content = _strip_yaml_frontmatter(content)
        rel = hermes_md_path.name
        try:
            rel = str(hermes_md_path.relative_to(cwd_path))
        except ValueError:
            pass
        content = _scan_context_content(content, rel)
        result = f"## {rel}\n\n{content}"
        return _truncate_content(result, ".hermes.md")
    except Exception as e:
        logger.debug("Could not read %s: %s", hermes_md_path, e)
        return ""


def _load_agents_md(cwd_path: Path) -> str:
    """AGENTS.md — top-level only (no recursive walk)."""
    for name in ["AGENTS.md", "agents.md"]:
        candidate = cwd_path / name
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    content = _scan_context_content(content, name)
                    result = f"## {name}\n\n{content}"
                    return _truncate_content(result, "AGENTS.md")
            except Exception as e:
                logger.debug("Could not read %s: %s", candidate, e)
    return ""


def _load_claude_md(cwd_path: Path) -> str:
    """CLAUDE.md / claude.md — cwd only."""
    for name in ["CLAUDE.md", "claude.md"]:
        candidate = cwd_path / name
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    content = _scan_context_content(content, name)
                    result = f"## {name}\n\n{content}"
                    return _truncate_content(result, "CLAUDE.md")
            except Exception as e:
                logger.debug("Could not read %s: %s", candidate, e)
    return ""


def _load_cursorrules(cwd_path: Path) -> str:
    """.cursorrules + .cursor/rules/*.mdc — cwd only."""
    cursorrules_content = ""
    cursorrules_file = cwd_path / ".cursorrules"
    if cursorrules_file.exists():
        try:
            content = cursorrules_file.read_text(encoding="utf-8").strip()
            if content:
                content = _scan_context_content(content, ".cursorrules")
                cursorrules_content += f"## .cursorrules\n\n{content}\n\n"
        except Exception as e:
            logger.debug("Could not read .cursorrules: %s", e)

    cursor_rules_dir = cwd_path / ".cursor" / "rules"
    if cursor_rules_dir.exists() and cursor_rules_dir.is_dir():
        mdc_files = sorted(cursor_rules_dir.glob("*.mdc"))
        for mdc_file in mdc_files:
            try:
                content = mdc_file.read_text(encoding="utf-8").strip()
                if content:
                    content = _scan_context_content(content, f".cursor/rules/{mdc_file.name}")
                    cursorrules_content += f"## .cursor/rules/{mdc_file.name}\n\n{content}\n\n"
            except Exception as e:
                logger.debug("Could not read %s: %s", mdc_file, e)

    if not cursorrules_content:
        return ""
    return _truncate_content(cursorrules_content, ".cursorrules")


def build_context_files_prompt(cwd: Optional[str] = None, skip_soul: bool = False) -> str:
    """Discover and load context files for the system prompt.

    Priority (first found wins — only ONE project context type is loaded):
      1. .hermes.md / HERMES.md  (walk to git root)
      2. AGENTS.md / agents.md   (cwd only)
      3. CLAUDE.md / claude.md   (cwd only)
      4. .cursorrules / .cursor/rules/*.mdc  (cwd only)

    SOUL.md from HERMES_HOME is independent and always included when present.
    Each context source is capped at 20,000 chars.

    When *skip_soul* is True, SOUL.md is not included here (it was already
    loaded via ``load_soul_md()`` for the identity slot).
    """
    if cwd is None:
        cwd = os.getcwd()

    cwd_path = Path(cwd).resolve()
    sections = []

    # Priority-based project context: first match wins
    project_context = (
        _load_hermes_md(cwd_path)
        or _load_agents_md(cwd_path)
        or _load_claude_md(cwd_path)
        or _load_cursorrules(cwd_path)
    )
    if project_context:
        sections.append(project_context)

    # SOUL.md from HERMES_HOME only — skip when already loaded as identity
    if not skip_soul:
        soul_content = load_soul_md()
        if soul_content:
            sections.append(soul_content)

    if not sections:
        return ""
    return "# Project Context\n\nThe following project context files have been loaded and should be followed:\n\n" + "\n".join(sections)
