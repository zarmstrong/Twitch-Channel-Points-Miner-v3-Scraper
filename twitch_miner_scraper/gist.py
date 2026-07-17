"""GitHub Gist publishing."""

from __future__ import annotations

import json
import logging

import requests

LOG = logging.getLogger(__name__)


class GistPublisher:
    def __init__(self, token: str, session: requests.Session, timeout: float = 30):
        self.token = token
        self.session = session
        self.timeout = timeout

    def publish(self, gist_id: str, filename: str, data: dict) -> None:
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        LOG.debug(
            "Updating Gist %s file %s with %d UTF-8 bytes",
            gist_id,
            filename,
            len(content.encode("utf-8")),
        )
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
                        "content": content
                    }
                }
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        LOG.debug("GitHub accepted update for Gist %s", gist_id)
