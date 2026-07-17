"""Twitch Helix global badge catalog scraper."""

from __future__ import annotations

from datetime import datetime, timezone

import requests

GLOBAL_BADGES_URL = "https://api.twitch.tv/helix/chat/badges/global"


class BadgeScraper:
    def __init__(self, session: requests.Session, client_id: str, token: str, timeout=30):
        self.session, self.client_id, self.token, self.timeout = session, client_id, token, timeout

    def scrape(self) -> dict:
        response = self.session.get(
            GLOBAL_BADGES_URL,
            headers={"Authorization": f"Bearer {self.token.removeprefix('oauth:')}", "Client-Id": self.client_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        sets = response.json().get("data")
        if not isinstance(sets, list):
            raise ValueError("Twitch global badge response did not contain a data list")
        return {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": GLOBAL_BADGES_URL,
            "counts": {"sets": len(sets), "versions": sum(len(x.get("versions", [])) for x in sets)},
            "sets": sets,
        }
