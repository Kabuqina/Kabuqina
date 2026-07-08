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

_OPTIONAL_EXPORTS = []
try:
    from .yuanbao import YuanbaoAdapter
except ModuleNotFoundError as exc:
    if exc.name != f"{__name__}.yuanbao":
        raise
else:
    _OPTIONAL_EXPORTS.append("YuanbaoAdapter")

__all__ = [
    "BasePlatformAdapter",
    "MessageEvent",
    "SendResult",
    "QQAdapter",
] + _OPTIONAL_EXPORTS
