# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""科大讯飞（iFlytek）WebSocket v2 接口共享工具：鉴权 URL 生成 + 凭据读取。

讯飞在线语音合成 (TTS, ``wss://tts-api.xfyun.cn/v2/tts``) 与语音听写
(IAT, ``wss://iat-api.xfyun.cn/v2/iat``) 使用同一套 HMAC-SHA256 URL 鉴权方案：
用 APISecret 对 ``host`` / ``date`` / ``request-line`` 三行做签名，拼进 wss URL
的 ``authorization`` / ``date`` / ``host`` 查询参数。

凭据（APPID / APIKey / APISecret）来源于讯飞开放平台，存放在 Windows 凭据管理器
或 hermes-home 的 .env 中，绝不硬编码；遵循讯飞开放平台服务条款。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
from datetime import datetime
from time import mktime
from typing import Any, Awaitable, Callable, Tuple, TypeVar
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

_T = TypeVar("_T")


def get_xfyun_credentials() -> Tuple[str, str, str]:
    """Return ``(app_id, api_key, api_secret)`` from .env / process env.

    Reads through ``hermes_cli.config.get_env_value`` (which also refreshes
    ``os.environ`` when the wizard saves keys) with a plain ``os.getenv``
    fallback. Missing values come back as empty strings so callers can raise a
    friendly "凭据未配置" error instead of crashing.
    """
    try:
        from hermes_cli.config import get_env_value as _gev
    except Exception:  # pragma: no cover - config module always present at runtime
        _gev = None

    def _read(name: str) -> str:
        value = _gev(name) if _gev is not None else None
        if not value:
            value = os.getenv(name, "")
        return (value or "").strip()

    return _read("XFYUN_APPID"), _read("XFYUN_API_KEY"), _read("XFYUN_API_SECRET")


def build_xfyun_ws_url(host: str, path: str, api_key: str, api_secret: str) -> str:
    """Build a signed ``wss://`` URL for an iFlytek v2 WebSocket endpoint.

    Args:
        host: API host, e.g. ``tts-api.xfyun.cn`` or ``iat-api.xfyun.cn``.
        path: request path, e.g. ``/v2/tts`` or ``/v2/iat``.
        api_key / api_secret: from the iFlytek open platform console.
    """
    date = format_date_time(mktime(datetime.now().timetuple()))
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    params = {"authorization": authorization, "date": date, "host": host}
    return f"wss://{host}{path}?{urlencode(params)}"


def run_ws_coroutine(make_coro: Callable[[], Awaitable[_T]], timeout: float = 180.0) -> _T:
    """Run an async iFlytek WS coroutine from synchronous tool code.

    Mirrors the Edge-TTS pattern in ``tts_tool``: run inside a dedicated
    thread's event loop (safe whether or not the caller already has a running
    loop), falling back to a plain ``asyncio.run`` if the executor can't be
    used. ``make_coro`` is a thunk so a retry always gets a fresh coroutine.
    """
    import concurrent.futures

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(make_coro())).result(timeout=timeout)
    except RuntimeError:
        return asyncio.run(make_coro())
