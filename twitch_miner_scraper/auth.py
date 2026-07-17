"""Twitch app access-token acquisition and persistent caching."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TOKEN_CACHE_FILENAME = "twitch-app-token.json"
REFRESH_MARGIN_SECONDS = 300


class TwitchTokenManager:
    def __init__(
        self,
        session: requests.Session,
        client_id: str,
        client_secret: str | None,
        cache_path: Path,
        timeout: float = 30,
    ):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_path = cache_path
        self.timeout = timeout

    def get_token(self) -> str:
        cached = self._load_cache()
        if cached is not None:
            return cached["access_token"]
        if not self.client_secret:
            raise ValueError(
                "TCPMS_TWITCH_CLIENT_SECRET is required to refresh the Twitch token"
            )
        response = self.session.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not token or not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise ValueError("Twitch token response was missing token expiry data")
        cached = {
            "access_token": token,
            "client_id": self.client_id,
            "expires_at": time.time() + expires_in,
            "token_type": payload.get("token_type", "bearer"),
        }
        self._write_cache(cached)
        return token

    def _load_cache(self) -> dict | None:
        try:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if cached.get("client_id") != self.client_id:
            return None
        if not cached.get("access_token"):
            return None
        try:
            expires_at = float(cached.get("expires_at", 0))
        except (TypeError, ValueError):
            return None
        if expires_at <= time.time() + REFRESH_MARGIN_SECONDS:
            return None
        return cached

    def _write_cache(self, data: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.cache_path)
