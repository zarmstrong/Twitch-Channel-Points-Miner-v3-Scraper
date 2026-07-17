"""Shared, retrying HTTP client."""

from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOG = logging.getLogger(__name__)


def build_session(user_agent: str = "TwitchMinerScraper/0.1") -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "PATCH", "POST"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({"User-Agent": user_agent})
    LOG.debug(
        "Created HTTP session: user_agent=%s retries=%d backoff=%s",
        user_agent,
        retries.total,
        retries.backoff_factor,
    )
    return session
