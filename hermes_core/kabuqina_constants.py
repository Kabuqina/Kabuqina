"""Shared constants for Kabuqina's owned agent core.

Import-safe module with no dependencies — can be imported from anywhere
without risk of circular imports.
"""

import os
import tempfile
from pathlib import Path


def _safe_user_home() -> Path:
    try:
        return Path.home()
    except RuntimeError:
        return Path(tempfile.gettempdir())


def _configured_home() -> Path | None:
    """Return an explicit home while preserving new-key precedence.

    Presence of ``KABUQINA_HOME`` is authoritative, including an explicitly
    empty value. An empty new value selects the new default and must not revive
    a stale ``HERMES_HOME`` inherited from an older launcher.
    """
    if "KABUQINA_HOME" in os.environ:
        value = os.environ["KABUQINA_HOME"].strip()
        return Path(value) if value else _safe_user_home() / ".kabuqina"
    legacy = os.environ.get("HERMES_HOME", "").strip()
    return Path(legacy) if legacy else None


def get_kabuqina_home() -> Path:
    """Return the canonical Kabuqina home directory.

    Resolution order is ``KABUQINA_HOME``, deprecated ``HERMES_HOME``, the new
    ``~/.kabuqina`` directory, then an existing ``~/.hermes`` directory. The
    final fallback is ``~/.kabuqina``. Reading the legacy directory for one
    release avoids silently hiding existing sessions and configuration.
    """
    configured = _configured_home()
    if configured is not None:
        return configured
    user_home = _safe_user_home()
    current = user_home / ".kabuqina"
    legacy = user_home / ".hermes"
    return legacy if legacy.exists() and not current.exists() else current


def get_default_kabuqina_root() -> Path:
    """Return the root Kabuqina directory for profile-level operations.

    In standard deployments this is ``~/.kabuqina`` (or an existing legacy
    ``~/.hermes`` directory during the compatibility release).

    In Docker or custom deployments where the configured home points outside
    the native default (e.g. ``/opt/data``), returns that home directly
    — that IS the root.

    In profile mode where the home is ``<root>/profiles/<name>``,
    returns ``<root>`` so that ``profile list`` can see all profiles.
    Works both for standard (``~/.kabuqina/profiles/coder``) and Docker
    (``/opt/data/profiles/coder``) layouts.

    Import-safe — no dependencies beyond stdlib.
    """
    user_home = _safe_user_home()
    native_roots = (user_home / ".kabuqina", user_home / ".hermes")
    env_path = _configured_home()
    if env_path is None:
        return get_kabuqina_home()
    for native_root in native_roots:
        try:
            env_path.resolve().relative_to(native_root.resolve())
            return native_root
        except ValueError:
            continue

    # Docker / custom deployment.
    # Check if this is a profile path: <root>/profiles/<name>
    # If the immediate parent dir is named "profiles", the root is
    # the grandparent — this covers Docker profiles correctly.
    if env_path.parent.name == "profiles":
        return env_path.parent.parent

    # Not a profile path — the configured home itself is the root.
    return env_path


def get_optional_skills_dir(default: Path | None = None) -> Path:
    """Return the optional-skills directory, honoring package-manager wrappers.

    Packaged installs may ship ``optional-skills`` outside the Python package
    tree and expose it via ``KABUQINA_OPTIONAL_SKILLS``. The old environment
    name remains readable for one release.
    """
    override = os.getenv("KABUQINA_OPTIONAL_SKILLS", "").strip()
    if not override:
        override = os.getenv("HERMES_OPTIONAL_SKILLS", "").strip()
    if override:
        return Path(override)
    if default is not None:
        return default
    return get_kabuqina_home() / "optional-skills"


def get_kabuqina_dir(new_subpath: str, old_name: str) -> Path:
    """Resolve a Kabuqina subdirectory with backward compatibility.

    New installs get the consolidated layout (e.g. ``cache/images``).
    Existing installs that already have the old path (e.g. ``image_cache``)
    keep using it — no migration required.

    Args:
        new_subpath: Preferred path relative to the Kabuqina home.
        old_name: Legacy path relative to the Kabuqina home.

    Returns:
        Absolute ``Path`` — old location if it exists on disk, otherwise the new one.
    """
    home = get_kabuqina_home()
    old_path = home / old_name
    if old_path.exists():
        return old_path
    return home / new_subpath


def display_kabuqina_home() -> str:
    """Return a user-friendly display string for the current Kabuqina home.

    Uses ``~/`` shorthand for readability::

        default:  ``~/.kabuqina``
        profile:  ``~/.kabuqina/profiles/coder``
        custom:   ``/opt/kabuqina-custom``

    Use this in **user-facing** print/log messages instead of hardcoding
    ``~/.kabuqina``. For code that needs a real ``Path``, use
    :func:`get_kabuqina_home` instead.
    """
    home = get_kabuqina_home()
    try:
        return "~/" + str(home.relative_to(_safe_user_home()))
    except ValueError:
        return str(home)


def get_subprocess_home() -> str | None:
    """Return a per-profile HOME directory for subprocesses, or None.

    When ``{KABUQINA_HOME}/home/`` exists on disk, subprocesses should use it
    as ``HOME`` so system tools (git, ssh, gh, npm …) write their configs
    inside the Kabuqina data directory instead of the OS-level ``/root`` or
    ``~/``.  This provides:

    * **Docker persistence** — tool configs land inside the persistent volume.
    * **Profile isolation** — each profile gets its own git identity, SSH
      keys, gh tokens, etc.

    The Python process's own ``os.environ["HOME"]`` and ``Path.home()`` are
    **never** modified — only subprocess environments should inject this value.
    Activation is directory-based: if the ``home/`` subdirectory doesn't
    exist, returns ``None`` and behavior is unchanged.
    """
    if "KABUQINA_HOME" in os.environ:
        kabuqina_home = os.environ["KABUQINA_HOME"]
    else:
        kabuqina_home = os.getenv("HERMES_HOME")
    if not kabuqina_home:
        return None
    profile_home = os.path.join(kabuqina_home, "home")
    if os.path.isdir(profile_home):
        return profile_home
    return None


VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")


def parse_reasoning_effort(effort: str) -> dict | None:
    """Parse a reasoning effort level into a config dict.

    Valid levels: "none", "minimal", "low", "medium", "high", "xhigh".
    Returns None when the input is empty or unrecognized (caller uses default).
    Returns {"enabled": False} for "none".
    Returns {"enabled": True, "effort": <level>} for valid effort levels.
    """
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None


def is_termux() -> bool:
    """Return True when running inside a Termux (Android) environment.

    Checks ``TERMUX_VERSION`` (set by Termux) or the Termux-specific
    ``PREFIX`` path.  Import-safe — no heavy deps.
    """
    prefix = os.getenv("PREFIX", "")
    return bool(os.getenv("TERMUX_VERSION") or "com.termux/files/usr" in prefix)


_wsl_detected: bool | None = None


def is_wsl() -> bool:
    """Return True when running inside WSL (Windows Subsystem for Linux).

    Checks ``/proc/version`` for the ``microsoft`` marker that both WSL1
    and WSL2 inject.  Result is cached for the process lifetime.
    Import-safe — no heavy deps.
    """
    global _wsl_detected
    if _wsl_detected is not None:
        return _wsl_detected
    try:
        with open("/proc/version", "r") as f:
            _wsl_detected = "microsoft" in f.read().lower()
    except Exception:
        _wsl_detected = False
    return _wsl_detected


_container_detected: bool | None = None


def is_container() -> bool:
    """Return True when running inside a Docker/Podman container.

    Checks ``/.dockerenv`` (Docker), ``/run/.containerenv`` (Podman),
    and ``/proc/1/cgroup`` for container runtime markers.  Result is
    cached for the process lifetime.  Import-safe — no heavy deps.
    """
    global _container_detected
    if _container_detected is not None:
        return _container_detected
    if os.path.exists("/.dockerenv"):
        _container_detected = True
        return True
    if os.path.exists("/run/.containerenv"):
        _container_detected = True
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup = f.read()
            if "docker" in cgroup or "podman" in cgroup or "/lxc/" in cgroup:
                _container_detected = True
                return True
    except OSError:
        pass
    _container_detected = False
    return False


# ─── Well-Known Paths ─────────────────────────────────────────────────────────


def get_config_path() -> Path:
    """Return the path to ``config.yaml`` under the Kabuqina home.

    Replaces repeated inline home/path construction.
    """
    return get_kabuqina_home() / "config.yaml"


def get_skills_dir() -> Path:
    """Return the path to the skills directory under the Kabuqina home."""
    return get_kabuqina_home() / "skills"



def get_env_path() -> Path:
    """Return the path to the ``.env`` file under the Kabuqina home."""
    return get_kabuqina_home() / ".env"


# One-release source compatibility. Canonical code must use the Kabuqina
# spellings; the deprecated module exposes these aliases to older consumers.
get_hermes_home = get_kabuqina_home
get_default_hermes_root = get_default_kabuqina_root
get_hermes_dir = get_kabuqina_dir
display_hermes_home = display_kabuqina_home


# ─── Network Preferences ─────────────────────────────────────────────────────


def apply_ipv4_preference(force: bool = False) -> None:
    """Monkey-patch ``socket.getaddrinfo`` to prefer IPv4 connections.

    On servers with broken or unreachable IPv6, Python tries AAAA records
    first and hangs for the full TCP timeout before falling back to IPv4.
    This affects httpx, requests, urllib, the OpenAI SDK — everything that
    uses ``socket.getaddrinfo``.

    When *force* is True, patches ``getaddrinfo`` so that calls with
    ``family=AF_UNSPEC`` (the default) resolve as ``AF_INET`` instead,
    skipping IPv6 entirely.  If no A record exists, falls back to the
    original unfiltered resolution so pure-IPv6 hosts still work.

    Safe to call multiple times — only patches once.
    Set ``network.force_ipv4: true`` in ``config.yaml`` to enable.
    """
    if not force:
        return

    import socket

    # Guard against double-patching
    if getattr(socket.getaddrinfo, "_kabuqina_ipv4_patched", False):
        return

    _original_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0:  # AF_UNSPEC — caller didn't request a specific family
            try:
                return _original_getaddrinfo(
                    host, port, socket.AF_INET, type, proto, flags
                )
            except socket.gaierror:
                # No A record — fall back to full resolution (pure-IPv6 hosts)
                return _original_getaddrinfo(host, port, family, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    _ipv4_getaddrinfo._kabuqina_ipv4_patched = True  # type: ignore[attr-defined]
    socket.getaddrinfo = _ipv4_getaddrinfo  # type: ignore[assignment]


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
