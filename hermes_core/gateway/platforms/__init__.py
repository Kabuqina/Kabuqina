"""
Platform adapters for messaging integrations.

Each adapter handles:
- Receiving messages from a platform
- Sending messages/responses back
- Platform-specific authentication
- Message formatting and media handling
"""

from .base import BasePlatformAdapter, MessageEvent, SendResult
from .qqbot import QQAdapter


def __getattr__(name):
    """Keep the legacy Yuanbao export lazy until CTL-C03 removes it."""
    if name == "YuanbaoAdapter":
        from .yuanbao import YuanbaoAdapter
        return YuanbaoAdapter
    raise AttributeError(name)

__all__ = [
    "BasePlatformAdapter",
    "MessageEvent",
    "SendResult",
    "QQAdapter",
    "YuanbaoAdapter",
]
