"""Tiny aiohttp stub for gateway unit tests.

The gateway suite exercises adapter logic without requiring optional network
extras to be installed in the developer environment.
"""

from __future__ import annotations

import types
import sys
from types import SimpleNamespace


class FormData:
    def __init__(self):
        self.fields = []

    def add_field(self, *args, **kwargs):
        self.fields.append((args, kwargs))


class Response:
    def __init__(self, *, status=200, text="", body=None, content_type=None):
        self.status = status
        self.text = text
        self.body = body
        self.content_type = content_type


class StreamResponse:
    async def prepare(self, request):
        return None

    async def write(self, data):
        return None

    async def write_eof(self):
        return None


class Application:
    def __init__(self):
        self.router = SimpleNamespace(
            add_get=lambda *args, **kwargs: None,
            add_post=lambda *args, **kwargs: None,
        )


class AppRunner:
    def __init__(self, app):
        self.app = app

    async def setup(self):
        return None

    async def cleanup(self):
        return None


class TCPSite:
    def __init__(self, runner, host, port):
        self.runner = runner
        self.host = host
        self.port = port

    async def start(self):
        return None


class ClientSession:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.closed = False

    async def close(self):
        self.closed = True


class ClientError(Exception):
    pass


class ClientConnectionError(ClientError):
    pass


class WSServerHandshakeError(ClientError):
    def __init__(self, *args, status=None, **kwargs):
        super().__init__(*args)
        self.status = status


def ClientTimeout(*, total=None, **kwargs):  # noqa: N802 - mirrors aiohttp API
    return SimpleNamespace(total=total, **kwargs)


def json_response(data=None, *, status=200, **kwargs):
    return Response(status=status, body=data, content_type="application/json")


def make_aiohttp_stub():
    aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")
    web.Response = Response
    web.StreamResponse = StreamResponse
    web.Application = Application
    web.AppRunner = AppRunner
    web.TCPSite = TCPSite
    web.json_response = json_response
    web.middleware = lambda func: func

    aiohttp.__path__ = []
    aiohttp.web = web
    aiohttp.ClientSession = ClientSession
    aiohttp.ClientTimeout = ClientTimeout
    aiohttp.FormData = FormData
    aiohttp.ClientError = ClientError
    aiohttp.ClientConnectionError = ClientConnectionError
    aiohttp.WSServerHandshakeError = WSServerHandshakeError
    return aiohttp, web


def install_aiohttp_stub(monkeypatch):
    aiohttp, web = make_aiohttp_stub()
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp)
    monkeypatch.setitem(sys.modules, "aiohttp.web", web)

    api_server = sys.modules.get("gateway.platforms.api_server")
    if api_server is not None:
        monkeypatch.setattr(api_server, "web", web, raising=False)
        monkeypatch.setattr(api_server, "AIOHTTP_AVAILABLE", True, raising=False)

    return aiohttp
