"""Tool handlers for the bundled Spotify plugin."""

from __future__ import annotations

import json
from typing import Any, Callable

from hermes_cli.auth import get_spotify_auth_status

from .client import (
    CURRENTLY_PLAYING_EMPTY_MESSAGE,
    SpotifyAPIError,
    SpotifyClient,
    normalize_spotify_uri,
)


def _spotify_client() -> SpotifyClient:
    return SpotifyClient()


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def _error(exc: Exception) -> str:
    return _json({"success": False, "error": str(exc)})


def _check_spotify_available() -> bool:
    try:
        return bool(get_spotify_auth_status().get("logged_in"))
    except Exception:
        return False


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _track_uris(args: dict[str, Any]) -> list[str]:
    raw = args.get("uris") or args.get("track_ids") or args.get("ids") or []
    return [normalize_spotify_uri(str(item), "track") for item in _as_list(raw)]


def _album_uris(args: dict[str, Any]) -> list[str]:
    raw = args.get("uris") or args.get("album_ids") or args.get("ids") or []
    return [normalize_spotify_uri(str(item), "album") for item in _as_list(raw)]


def _ok(action: str, payload: Any = None, **extra: Any) -> str:
    body = {"success": True, "action": action}
    if payload is not None:
        body["payload"] = payload
    body.update(extra)
    return _json(body)


def _handle_spotify_playback(args: dict[str, Any], **_: Any) -> str:
    try:
        client = _spotify_client()
        action = str(args.get("action") or "").strip()
        if action == "get_state":
            return _ok(action, client.get_playback_state(market=args.get("market")))
        if action == "get_currently_playing":
            payload = client.get_currently_playing(market=args.get("market"))
            if isinstance(payload, dict) and payload.get("empty"):
                return _json({
                    "success": True,
                    "action": action,
                    "is_playing": False,
                    "status_code": payload.get("status_code", 204),
                    "message": payload.get("message", CURRENTLY_PLAYING_EMPTY_MESSAGE),
                })
            return _ok(action, payload, is_playing=bool(isinstance(payload, dict) and payload.get("is_playing")))
        if action == "recently_played":
            return _ok(action, client.get_recently_played(
                limit=args.get("limit"),
                before=args.get("before"),
                after=args.get("after"),
            ))
        if action == "play":
            return _ok(action, client.play(
                device_id=args.get("device_id"),
                context_uri=args.get("context_uri"),
                uris=args.get("uris"),
                offset=args.get("offset"),
                position_ms=args.get("position_ms"),
            ))
        if action == "pause":
            return _ok(action, client.pause(device_id=args.get("device_id")))
        if action == "next":
            return _ok(action, client.next_track(device_id=args.get("device_id")))
        if action == "previous":
            return _ok(action, client.previous_track(device_id=args.get("device_id")))
        if action == "seek":
            return _ok(action, client.seek(
                position_ms=int(args.get("position_ms")),
                device_id=args.get("device_id"),
            ))
        if action == "set_repeat":
            return _ok(action, client.set_repeat(
                state=str(args.get("state") or "off"),
                device_id=args.get("device_id"),
            ))
        if action == "set_shuffle":
            return _ok(action, client.set_shuffle(
                state=bool(args.get("state")),
                device_id=args.get("device_id"),
            ))
        if action == "set_volume":
            return _ok(action, client.set_volume(
                volume_percent=int(args.get("volume_percent")),
                device_id=args.get("device_id"),
            ))
        return _json({"success": False, "error": f"Unknown spotify_playback action: {action}"})
    except Exception as exc:
        return _error(exc)


def _handle_spotify_devices(args: dict[str, Any], **_: Any) -> str:
    try:
        client = _spotify_client()
        action = str(args.get("action") or "list").strip()
        if action == "list":
            return _ok(action, client.get_devices())
        if action == "transfer":
            return _ok(action, client.transfer_playback(
                device_id=str(args.get("device_id") or ""),
                play=args.get("play"),
            ))
        return _json({"success": False, "error": f"Unknown spotify_devices action: {action}"})
    except Exception as exc:
        return _error(exc)


def _handle_spotify_queue(args: dict[str, Any], **_: Any) -> str:
    try:
        client = _spotify_client()
        action = str(args.get("action") or "").strip()
        if action == "get":
            return _ok(action, client.get_queue())
        if action == "add":
            return _ok(action, client.add_to_queue(
                uri=str(args.get("uri") or ""),
                device_id=args.get("device_id"),
            ))
        return _json({"success": False, "error": f"Unknown spotify_queue action: {action}"})
    except Exception as exc:
        return _error(exc)


def _handle_spotify_search(args: dict[str, Any], **_: Any) -> str:
    try:
        payload = _spotify_client().search(
            query=str(args.get("query") or ""),
            types=args.get("types"),
            limit=args.get("limit"),
            offset=args.get("offset"),
            market=args.get("market"),
        )
        return _ok("search", payload)
    except Exception as exc:
        return _error(exc)


def _handle_spotify_playlists(args: dict[str, Any], **_: Any) -> str:
    try:
        client = _spotify_client()
        action = str(args.get("action") or "").strip()
        if action == "list":
            return _ok(action, client.get_playlists(limit=args.get("limit"), offset=args.get("offset")))
        if action == "get":
            return _ok(action, client.get_playlist(playlist_id=str(args.get("playlist_id") or ""), market=args.get("market")))
        if action == "create":
            return _ok(action, client.create_playlist(
                name=str(args.get("name") or ""),
                description=args.get("description"),
                public=args.get("public"),
                collaborative=args.get("collaborative"),
            ))
        if action == "add_items":
            return _ok(action, client.add_playlist_items(
                playlist_id=str(args.get("playlist_id") or ""),
                uris=list(args.get("uris") or []),
                position=args.get("position"),
            ))
        if action == "remove_items":
            return _ok(action, client.remove_playlist_items(
                playlist_id=str(args.get("playlist_id") or ""),
                uris=list(args.get("uris") or []),
                snapshot_id=args.get("snapshot_id"),
            ))
        if action == "update_details":
            return _ok(action, client.update_playlist_details(
                playlist_id=str(args.get("playlist_id") or ""),
                name=args.get("name"),
                description=args.get("description"),
                public=args.get("public"),
                collaborative=args.get("collaborative"),
            ))
        return _json({"success": False, "error": f"Unknown spotify_playlists action: {action}"})
    except Exception as exc:
        return _error(exc)


def _handle_spotify_albums(args: dict[str, Any], **_: Any) -> str:
    try:
        client = _spotify_client()
        action = str(args.get("action") or "").strip()
        album_id = str(args.get("album_id") or args.get("id") or "")
        if action == "get":
            return _ok(action, client.get_album(album_id=album_id, market=args.get("market")))
        if action == "tracks":
            return _ok(action, client.get_album_tracks(
                album_id=album_id,
                limit=args.get("limit"),
                offset=args.get("offset"),
                market=args.get("market"),
            ))
        return _json({"success": False, "error": f"Unknown spotify_albums action: {action}"})
    except Exception as exc:
        return _error(exc)


def _handle_spotify_library(args: dict[str, Any], **_: Any) -> str:
    try:
        client = _spotify_client()
        kind = str(args.get("kind") or "").strip()
        action = str(args.get("action") or "").strip()
        if kind not in {"tracks", "albums"}:
            return _json({"success": False, "error": "spotify_library requires kind: tracks or albums"})

        if action == "list":
            if kind == "tracks":
                payload = client.get_saved_tracks(limit=args.get("limit"), offset=args.get("offset"), market=args.get("market"))
            else:
                payload = client.get_saved_albums(limit=args.get("limit"), offset=args.get("offset"), market=args.get("market"))
            return _ok(action, payload, kind=kind)
        if action == "contains":
            payload = client.library_contains(uris=_track_uris(args) if kind == "tracks" else _album_uris(args))
            return _ok(action, payload, kind=kind)
        if action == "save":
            payload = client.save_to_library(uris=_track_uris(args) if kind == "tracks" else _album_uris(args))
            return _ok(action, payload, kind=kind)
        if action == "remove":
            payload = client.remove_from_library(uris=_track_uris(args) if kind == "tracks" else _album_uris(args))
            return _ok(action, payload, kind=kind)
        return _json({"success": False, "error": f"Unknown spotify_library action: {action}"})
    except Exception as exc:
        return _error(exc)


def _schema(description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


SPOTIFY_PLAYBACK_SCHEMA = _schema(
    "Control and inspect Spotify playback.",
    {
        "action": {"type": "string"},
        "device_id": {"type": "string"},
        "context_uri": {"type": "string"},
        "uris": {"type": "array", "items": {"type": "string"}},
        "offset": {"type": "object"},
        "position_ms": {"type": "integer"},
        "state": {},
        "volume_percent": {"type": "integer"},
        "limit": {"type": "integer"},
        "before": {"type": "integer"},
        "after": {"type": "integer"},
        "market": {"type": "string"},
    },
    ["action"],
)

SPOTIFY_DEVICES_SCHEMA = _schema(
    "List Spotify Connect devices or transfer playback.",
    {
        "action": {"type": "string"},
        "device_id": {"type": "string"},
        "play": {"type": "boolean"},
    },
    ["action"],
)

SPOTIFY_QUEUE_SCHEMA = _schema(
    "Read or add to the Spotify queue.",
    {
        "action": {"type": "string"},
        "uri": {"type": "string"},
        "device_id": {"type": "string"},
    },
    ["action"],
)

SPOTIFY_SEARCH_SCHEMA = _schema(
    "Search the Spotify catalog.",
    {
        "query": {"type": "string"},
        "types": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer"},
        "offset": {"type": "integer"},
        "market": {"type": "string"},
    },
    ["query"],
)

SPOTIFY_PLAYLISTS_SCHEMA = _schema(
    "Manage Spotify playlists.",
    {
        "action": {"type": "string"},
        "playlist_id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "public": {"type": "boolean"},
        "collaborative": {"type": "boolean"},
        "uris": {"type": "array", "items": {"type": "string"}},
        "position": {"type": "integer"},
        "snapshot_id": {"type": "string"},
        "limit": {"type": "integer"},
        "offset": {"type": "integer"},
        "market": {"type": "string"},
    },
    ["action"],
)

SPOTIFY_ALBUMS_SCHEMA = _schema(
    "Read Spotify albums and album tracks.",
    {
        "action": {"type": "string"},
        "album_id": {"type": "string"},
        "id": {"type": "string"},
        "limit": {"type": "integer"},
        "offset": {"type": "integer"},
        "market": {"type": "string"},
    },
    ["action"],
)

SPOTIFY_LIBRARY_SCHEMA = _schema(
    "Manage saved Spotify tracks and albums.",
    {
        "kind": {"type": "string"},
        "action": {"type": "string"},
        "uris": {"type": "array", "items": {"type": "string"}},
        "ids": {"type": "array", "items": {"type": "string"}},
        "track_ids": {"type": "array", "items": {"type": "string"}},
        "album_ids": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer"},
        "offset": {"type": "integer"},
        "market": {"type": "string"},
    },
    ["kind", "action"],
)


def register(ctx) -> None:
    registrations: list[tuple[str, dict[str, Any], Callable[..., str]]] = [
        ("spotify_playback", SPOTIFY_PLAYBACK_SCHEMA, _handle_spotify_playback),
        ("spotify_devices", SPOTIFY_DEVICES_SCHEMA, _handle_spotify_devices),
        ("spotify_queue", SPOTIFY_QUEUE_SCHEMA, _handle_spotify_queue),
        ("spotify_search", SPOTIFY_SEARCH_SCHEMA, _handle_spotify_search),
        ("spotify_playlists", SPOTIFY_PLAYLISTS_SCHEMA, _handle_spotify_playlists),
        ("spotify_albums", SPOTIFY_ALBUMS_SCHEMA, _handle_spotify_albums),
        ("spotify_library", SPOTIFY_LIBRARY_SCHEMA, _handle_spotify_library),
    ]
    for name, schema, handler in registrations:
        ctx.register_tool(
            name=name,
            toolset="spotify",
            schema=schema,
            handler=handler,
            check_fn=_check_spotify_available,
            description=schema["description"],
        )
