"""Spotify Web API client used by the bundled Spotify tools."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from hermes_cli.auth import resolve_spotify_runtime_credentials


CURRENTLY_PLAYING_EMPTY_MESSAGE = (
    "Spotify is not currently playing anything. Start playback in Spotify and try again."
)


class SpotifyAPIError(RuntimeError):
    """A Spotify API error with a user-facing message."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def normalize_spotify_uri(value: str, expected_type: str) -> str:
    """Normalize a Spotify URI, open.spotify.com URL, or bare ID to a URI."""
    raw = str(value or "").strip()
    expected_type = str(expected_type or "").strip()
    if not raw:
        raise ValueError("Spotify ID/URI is required")
    if not expected_type:
        raise ValueError("Spotify entity type is required")

    prefix = f"spotify:{expected_type}:"
    if raw.startswith("spotify:"):
        parts = raw.split(":")
        if len(parts) != 3 or parts[1] != expected_type or not parts[2]:
            raise ValueError(f"Expected a Spotify {expected_type} URI")
        return raw

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc != "open.spotify.com":
            raise ValueError("Expected an open.spotify.com URL")
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) < 2 or path_parts[0] != expected_type:
            raise ValueError(f"Expected a Spotify {expected_type} URL")
        return prefix + path_parts[1]

    return prefix + raw


def _error_payload(response) -> Any:
    content_type = (
        response.headers.get("content-type")
        or response.headers.get("Content-Type")
        or ""
    )
    if "json" in content_type.lower():
        try:
            return response.json()
        except Exception:
            return response.text
    try:
        return response.json()
    except Exception:
        return response.text


def _message_from_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
            if message:
                return message
        message = str(payload.get("message") or "").strip()
        if message:
            return message
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return ""


def _retry_after(headers: dict[str, str]) -> str:
    return (
        headers.get("Retry-After")
        or headers.get("retry-after")
        or headers.get("x-ratelimit-reset")
        or ""
    )


def _friendly_error_message(
    status_code: int,
    path: str,
    payload: Any,
    headers: dict[str, str],
) -> str:
    if status_code == 403 and path.startswith("/me/player"):
        return (
            "Spotify rejected this playback request. Playback control usually "
            "requires a Spotify Premium account and an active Spotify Connect device."
        )
    if status_code == 404 and path.startswith("/me/player"):
        return "Spotify could not find an active playback device or player session for this request."
    if status_code == 429:
        retry_after = _retry_after(headers)
        if retry_after:
            return f"Spotify rate limit exceeded. Retry after {retry_after} seconds."
        return "Spotify rate limit exceeded. Retry later."

    detail = _message_from_payload(payload)
    if detail:
        return f"Spotify API error {status_code}: {detail}"
    return f"Spotify API error {status_code}"


class SpotifyClient:
    """Thin Spotify Web API wrapper with auth refresh retry."""

    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self._credentials: dict[str, Any] | None = None

    def _resolve_credentials(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if self._credentials is None or force_refresh:
            self._credentials = resolve_spotify_runtime_credentials(
                force_refresh=force_refresh
            )
        return self._credentials

    def _base_url(self, credentials: dict[str, Any]) -> str:
        return str(credentials.get("base_url") or "https://api.spotify.com/v1").rstrip("/")

    def _auth_headers(self, credentials: dict[str, Any]) -> dict[str, str]:
        token = str(credentials.get("access_token") or credentials.get("api_key") or "").strip()
        token_type = str(credentials.get("token_type") or "Bearer").strip() or "Bearer"
        return {
            "Authorization": f"{token_type} {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        empty_message: str | None = None,
        _retry_on_401: bool = True,
    ) -> Any:
        credentials = self._resolve_credentials(force_refresh=False)
        clean_path = "/" + str(path or "").lstrip("/")
        url = self._base_url(credentials) + clean_path
        response = httpx.request(
            method.upper(),
            url,
            headers=self._auth_headers(credentials),
            params=params,
            json=json,
            timeout=self.timeout,
        )

        if response.status_code == 401 and _retry_on_401:
            credentials = self._resolve_credentials(force_refresh=True)
            url = self._base_url(credentials) + clean_path
            response = httpx.request(
                method.upper(),
                url,
                headers=self._auth_headers(credentials),
                params=params,
                json=json,
                timeout=self.timeout,
            )

        if response.status_code == 204:
            payload = {"status_code": 204, "empty": True}
            if empty_message:
                payload["message"] = empty_message
            return payload

        payload = _error_payload(response)
        if response.status_code >= 400:
            raise SpotifyAPIError(
                _friendly_error_message(
                    response.status_code,
                    clean_path,
                    payload,
                    dict(response.headers or {}),
                ),
                status_code=response.status_code,
                payload=payload,
            )
        return payload

    def get_devices(self) -> Any:
        return self.request("GET", "/me/player/devices")

    def transfer_playback(self, *, device_id: str, play: bool | None = None) -> Any:
        body: dict[str, Any] = {"device_ids": [device_id]}
        if play is not None:
            body["play"] = bool(play)
        return self.request("PUT", "/me/player", json=body)

    def get_playback_state(self, *, market: str | None = None) -> Any:
        params = {"market": market} if market else None
        return self.request("GET", "/me/player", params=params)

    def get_currently_playing(self, *, market: str | None = None) -> Any:
        params = {"market": market} if market else None
        return self.request(
            "GET",
            "/me/player/currently-playing",
            params=params,
            empty_message=CURRENTLY_PLAYING_EMPTY_MESSAGE,
        )

    def play(
        self,
        *,
        device_id: str | None = None,
        context_uri: str | None = None,
        uris: list[str] | None = None,
        offset: dict[str, Any] | None = None,
        position_ms: int | None = None,
    ) -> Any:
        params = {"device_id": device_id} if device_id else None
        body: dict[str, Any] = {}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = uris
        if offset:
            body["offset"] = offset
        if position_ms is not None:
            body["position_ms"] = position_ms
        return self.request("PUT", "/me/player/play", params=params, json=body or None)

    def pause(self, *, device_id: str | None = None) -> Any:
        params = {"device_id": device_id} if device_id else None
        return self.request("PUT", "/me/player/pause", params=params)

    def next_track(self, *, device_id: str | None = None) -> Any:
        params = {"device_id": device_id} if device_id else None
        return self.request("POST", "/me/player/next", params=params)

    def previous_track(self, *, device_id: str | None = None) -> Any:
        params = {"device_id": device_id} if device_id else None
        return self.request("POST", "/me/player/previous", params=params)

    def seek(self, *, position_ms: int, device_id: str | None = None) -> Any:
        params: dict[str, Any] = {"position_ms": position_ms}
        if device_id:
            params["device_id"] = device_id
        return self.request("PUT", "/me/player/seek", params=params)

    def set_repeat(self, *, state: str, device_id: str | None = None) -> Any:
        params: dict[str, Any] = {"state": state}
        if device_id:
            params["device_id"] = device_id
        return self.request("PUT", "/me/player/repeat", params=params)

    def set_shuffle(self, *, state: bool, device_id: str | None = None) -> Any:
        params: dict[str, Any] = {"state": str(bool(state)).lower()}
        if device_id:
            params["device_id"] = device_id
        return self.request("PUT", "/me/player/shuffle", params=params)

    def set_volume(self, *, volume_percent: int, device_id: str | None = None) -> Any:
        params: dict[str, Any] = {"volume_percent": volume_percent}
        if device_id:
            params["device_id"] = device_id
        return self.request("PUT", "/me/player/volume", params=params)

    def get_recently_played(
        self,
        *,
        limit: int | None = None,
        before: int | None = None,
        after: int | None = None,
    ) -> Any:
        params = {k: v for k, v in {
            "limit": limit,
            "before": before,
            "after": after,
        }.items() if v is not None}
        return self.request("GET", "/me/player/recently-played", params=params or None)

    def get_queue(self) -> Any:
        return self.request("GET", "/me/player/queue")

    def add_to_queue(self, *, uri: str, device_id: str | None = None) -> Any:
        params: dict[str, Any] = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        return self.request("POST", "/me/player/queue", params=params)

    def search(
        self,
        *,
        query: str,
        types: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        market: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "q": query,
            "type": ",".join(types or ["track"]),
        }
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if market:
            params["market"] = market
        return self.request("GET", "/search", params=params)

    def get_playlists(self, *, limit: int | None = None, offset: int | None = None) -> Any:
        params = {k: v for k, v in {"limit": limit, "offset": offset}.items() if v is not None}
        return self.request("GET", "/me/playlists", params=params or None)

    def get_playlist(self, *, playlist_id: str, market: str | None = None) -> Any:
        params = {"market": market} if market else None
        return self.request("GET", f"/playlists/{playlist_id}", params=params)

    def create_playlist(
        self,
        *,
        name: str,
        description: str | None = None,
        public: bool | None = None,
        collaborative: bool | None = None,
    ) -> Any:
        me = self.request("GET", "/me")
        user_id = me.get("id") if isinstance(me, dict) else None
        if not user_id:
            raise SpotifyAPIError("Spotify user id was not available.")
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if public is not None:
            body["public"] = bool(public)
        if collaborative is not None:
            body["collaborative"] = bool(collaborative)
        return self.request("POST", f"/users/{user_id}/playlists", json=body)

    def add_playlist_items(
        self,
        *,
        playlist_id: str,
        uris: list[str],
        position: int | None = None,
    ) -> Any:
        body: dict[str, Any] = {"uris": uris}
        if position is not None:
            body["position"] = position
        return self.request("POST", f"/playlists/{playlist_id}/tracks", json=body)

    def remove_playlist_items(
        self,
        *,
        playlist_id: str,
        uris: list[str],
        snapshot_id: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {"tracks": [{"uri": uri} for uri in uris]}
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        return self.request("DELETE", f"/playlists/{playlist_id}/tracks", json=body)

    def update_playlist_details(self, *, playlist_id: str, **fields: Any) -> Any:
        body = {k: v for k, v in fields.items() if v is not None}
        return self.request("PUT", f"/playlists/{playlist_id}", json=body)

    def get_album(self, *, album_id: str, market: str | None = None) -> Any:
        params = {"market": market} if market else None
        return self.request("GET", f"/albums/{album_id}", params=params)

    def get_album_tracks(
        self,
        *,
        album_id: str,
        limit: int | None = None,
        offset: int | None = None,
        market: str | None = None,
    ) -> Any:
        params = {k: v for k, v in {
            "limit": limit,
            "offset": offset,
            "market": market,
        }.items() if v is not None}
        return self.request("GET", f"/albums/{album_id}/tracks", params=params or None)

    def get_saved_tracks(self, *, limit: int | None = None, offset: int | None = None, market: str | None = None) -> Any:
        params = {k: v for k, v in {"limit": limit, "offset": offset, "market": market}.items() if v is not None}
        return self.request("GET", "/me/tracks", params=params or None)

    def get_saved_albums(self, *, limit: int | None = None, offset: int | None = None, market: str | None = None) -> Any:
        params = {k: v for k, v in {"limit": limit, "offset": offset, "market": market}.items() if v is not None}
        return self.request("GET", "/me/albums", params=params or None)

    def library_contains(self, *, uris: list[str]) -> Any:
        return self.request("GET", "/me/library/contains", params={"uris": ",".join(uris)})

    def save_to_library(self, *, uris: list[str]) -> Any:
        return self.request("PUT", "/me/library", params={"uris": ",".join(uris)})

    def remove_from_library(self, *, uris: list[str]) -> Any:
        return self.request("DELETE", "/me/library", params={"uris": ",".join(uris)})

    def remove_saved_tracks(self, *, track_ids: list[str]) -> Any:
        uris = [normalize_spotify_uri(item, "track") for item in track_ids]
        return self.remove_from_library(uris=uris)

    def remove_saved_albums(self, *, album_ids: list[str]) -> Any:
        uris = [normalize_spotify_uri(item, "album") for item in album_ids]
        return self.remove_from_library(uris=uris)
