"""Make stripped Hermes subpackages importable as harmless no-ops.

# DEPRECATED: gateway_policy.remove_when=Phase4
# Target replacement: ``python/src/gateway_policy.py`` — feature-flag
# gating instead of stub-module injection.  When ``GatewayPolicy.enabled``
# is False, the web child should never attempt to import gateway code.

This applies to the **Hermes web child** (`desktop_entrypoint.py`), not to the
**separate messaging-gateway process** Tauri spawns (`python -m gateway.run`).

The bundled tree **does ship** upstream ``gateway/`` sources on disk; we only
prevent ``web_server`` / CLI dispatch paths from treating ``gateway.run.main``
as the live gateway entry inside **that** interpreter — messaging adapters run in
their **own** OS child with an unstubbed ``gateway.run``.

Fully removed from the desktop **import surface** (AttributeError guides users
upstream): ``tui_gateway``, ``acp_adapter``, ``acp_registry``, RL helpers, etc.
Some upstream code imports symbols unconditionally; rather than fragile forks we
register placeholders in ``sys.modules``.

Two flavours of placeholder exist:

* `_Stripped` -- attribute access raises ImportError with a clear message.
  Used for fully removed subsystems (e.g. RL training).
* `_StubModule` -- exposes a small set of pre-populated attributes
  (typically callables that return None). Used when upstream `web_server`
  / `main` code imports specific symbols at module load that we cannot
  let raise.
"""

from __future__ import annotations

import sys
import types
from importlib.machinery import ModuleSpec
from typing import Any, Dict


_STRIPPED = (
    "tui_gateway",
    "tui_gateway.entry",
    "acp_adapter",
    "acp_adapter.entry",
    "acp_registry",
    "rl_cli",
    "batch_runner",
    "mini_swe_runner",
    "tinker_atropos",
)


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


_STUBBED: Dict[str, Dict[str, Any]] = {
    # Do NOT stub the parent ``gateway`` package: ``tools/approval`` and
    # ``gateway.session_context`` must load the real modules (ContextVar session
    # keys for terminal approval). A full-package stub breaks
    # ``from gateway.session_context import get_session_env`` and can surface as
    # ``'function' object is not iterable`` when the stub's __getattr__ returns
    # no-op callables.
    #
    # Do NOT stub ``gateway.config`` either: ``gateway/__init__.py`` imports
    # real symbols from ``.config``; a pre-registered stub would make that import
    # load the wrong module.
    #
    # Do NOT stub ``gateway.platforms``: cron remote delivery imports
    # ``gateway.platforms.base`` (``BasePlatformAdapter.extract_media``). An empty
    # stub without ``__path__`` makes ``import gateway.platforms.base`` fail with
    # ``TypeError: 'function' object is not iterable``.
    #
    # web_server still needs no-op PIDs / status; keep only these leaf stubs:
    "gateway.status": {
        "get_running_pid": _noop,
        "read_runtime_status": _noop,
        "write_pid_file": _noop,
        "write_runtime_status": _noop,
        "terminate_pid": _noop,
    },
    "gateway.run": {
        "main": _noop,
    },
}


class _Stripped(types.ModuleType):
    """Module-shaped object whose attribute access raises a friendly error."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.__hermesdesk_stripped__ = True
        self.__file__ = f"<hermesdesk-stripped:{name}>"
        self.__package__ = name.rpartition(".")[0]
        self.__spec__ = ModuleSpec(name, loader=None)

    def __getattr__(self, attr: str):  # noqa: D401
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        raise ImportError(
            f"'{self.__name__}.{attr}' is not available in HermesDesk. "
            f"This feature was removed for the desktop build. "
            f"Use the upstream Hermes Agent CLI for full functionality."
        )


class _StubModule(types.ModuleType):
    """Module-shaped object with a fixed set of attributes pre-populated."""

    def __init__(self, name: str, attrs: Dict[str, Any]) -> None:
        super().__init__(name)
        self.__hermesdesk_stubbed__ = True
        self.__file__ = f"<hermesdesk-stub:{name}>"
        self.__package__ = name.rpartition(".")[0]
        self.__spec__ = ModuleSpec(name, loader=None)
        for k, v in attrs.items():
            setattr(self, k, v)

    def __getattr__(self, attr: str):  # noqa: D401
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        # Unknown attribute: return a no-op callable so .foo() doesn't crash.
        return _noop


def evict_gateway_platforms_stub() -> None:
    """Drop a stale ``gateway.platforms`` stub so real submodules can load.

    Cron ``_deliver_result`` and ``send_weixin_direct`` need
    ``gateway.platforms.*`` on the web-child path. Older builds registered an
    empty ``_StubModule`` here; evict it (and any stubbed children) on install
    and before remote cron delivery.
    """
    for key in list(sys.modules.keys()):
        if key != "gateway.platforms" and not key.startswith("gateway.platforms."):
            continue
        mod = sys.modules.get(key)
        if mod is not None and getattr(mod, "__hermesdesk_stubbed__", False):
            del sys.modules[key]


def _evict_legacy_full_gateway_stub() -> None:
    """Remove the old empty ``gateway`` stub (pre-2025-04) from ``sys.modules``.

    That stub had no ``__path__`` and broke ``import gateway.session_context``,
    which ``tools/approval`` needs for terminal command checks
    (``'function' object is not iterable`` from bogus submodule attrs).
    """
    m = sys.modules.get("gateway")
    if m is None:
        return
    if not getattr(m, "__hermesdesk_stubbed__", False):
        return
    if getattr(m, "__path__", None):
        return
    del sys.modules["gateway"]
    sys.modules.pop("gateway.session_context", None)


def install() -> None:
    _evict_legacy_full_gateway_stub()
    evict_gateway_platforms_stub()
    for name, attrs in _STUBBED.items():
        if name not in sys.modules:
            sys.modules[name] = _StubModule(name, attrs)

    for name in _STRIPPED:
        if name not in sys.modules:
            sys.modules[name] = _Stripped(name)
