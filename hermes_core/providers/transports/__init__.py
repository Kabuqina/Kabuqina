"""Transport layer types and registry for provider response normalization.

Usage:
    from providers.transports import get_transport
    transport = get_transport("anthropic_messages")
    result = transport.normalize_response(raw_response)
"""

from providers.transports.types import NormalizedResponse, ToolCall, Usage, build_tool_call, map_finish_reason  # noqa: F401

_REGISTRY: dict = {}


def register_transport(api_mode: str, transport_cls: type) -> None:
    """Register a transport class for an api_mode string."""
    _REGISTRY[api_mode] = transport_cls


def get_transport(api_mode: str):
    """Get a transport instance for the given api_mode.

    Returns None if no transport is registered for this api_mode.
    This allows gradual migration — call sites can check for None
    and fall back to the legacy code path.
    """
    cls = _REGISTRY.get(api_mode)
    if cls is None:
        # The registry can be partially populated when a specific transport
            # module was imported directly. Discover on misses, not only when
            # the registry is empty, so
        # test/order-dependent imports do not make valid api_modes unavailable.
        _discover_transports()
        cls = _REGISTRY.get(api_mode)
    if cls is None:
        return None
    return cls()


def _discover_transports() -> None:
    """Import all transport modules to trigger auto-registration."""
    try:
        import providers.transports.anthropic  # noqa: F401
    except ImportError:
        pass
    try:
        import providers.transports.chat_completions  # noqa: F401
    except ImportError:
        pass
