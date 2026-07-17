"""GitHub Gist publishing."""

from __future__ import annotations

import json

import requests


class GistPublisher:
    def __init__(self, token: str, session: requests.Session, timeout: float = 30):
        self.token = token
        self.session = session
        self.timeout = timeout

    def publish(self, gist_id: str, filename: str, data: dict) -> None:
        response = self.session.patch(
            f"https://api.github.com/gists/{gist_id}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "files": {
                    filename: {
                        "content": json.dumps(data, indent=2, ensure_ascii=False) + "\n"
                    }
                }
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
