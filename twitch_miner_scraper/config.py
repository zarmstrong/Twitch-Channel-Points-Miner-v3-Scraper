"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _positive_float(name: str, default: str) -> float:
    try:
        value = float(os.getenv(name, default))
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    drops_gist_id: str | None
    badges_gist_id: str | None
    twitch_client_id: str | None
    twitch_client_secret: str | None
    twitch_oauth_token: str | None
    drops_gist_filename: str
    badges_gist_filename: str
    drops_interval: float
    badges_interval: float
    request_delay: float
    request_timeout: float
    output_dir: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        delay = float(os.getenv("TCPMS_REQUEST_DELAY_SECONDS", "0.25"))
        if delay < 0:
            raise ValueError("TCPMS_REQUEST_DELAY_SECONDS cannot be negative")
        log_level = os.getenv("TCPMS_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in LOG_LEVELS:
            raise ValueError(
                "TCPMS_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )
        return cls(
            github_token=os.getenv("TCPMS_GITHUB_TOKEN"),
            drops_gist_id=os.getenv("TCPMS_DROPS_GIST_ID"),
            badges_gist_id=os.getenv("TCPMS_BADGES_GIST_ID"),
            twitch_client_id=os.getenv("TCPMS_TWITCH_CLIENT_ID"),
            twitch_client_secret=os.getenv("TCPMS_TWITCH_CLIENT_SECRET"),
            twitch_oauth_token=os.getenv("TCPMS_TWITCH_OAUTH_TOKEN"),
            drops_gist_filename=os.getenv(
                "TCPMS_DROPS_GIST_FILENAME", "twitch-drops.json"
            ),
            badges_gist_filename=os.getenv(
                "TCPMS_BADGES_GIST_FILENAME", "twitch-badges.json"
            ),
            drops_interval=_positive_float("TCPMS_DROPS_INTERVAL_SECONDS", "900"),
            badges_interval=_positive_float("TCPMS_BADGES_INTERVAL_SECONDS", "1200"),
            request_delay=delay,
            request_timeout=_positive_float("TCPMS_REQUEST_TIMEOUT_SECONDS", "30"),
            output_dir=Path(os.getenv("TCPMS_OUTPUT_DIR", "/data")),
            log_level=log_level,
        )

    def validate_job(self, job: str, upload: bool = True) -> None:
        missing = []
        if job == "badges":
            if not self.twitch_client_id:
                missing.append("TCPMS_TWITCH_CLIENT_ID")
            if not self.twitch_oauth_token and not self.twitch_client_secret:
                missing.append(
                    "TCPMS_TWITCH_CLIENT_SECRET (or TCPMS_TWITCH_OAUTH_TOKEN)"
                )
        if upload:
            if not self.github_token:
                missing.append("TCPMS_GITHUB_TOKEN")
            gist_id = self.drops_gist_id if job == "drops" else self.badges_gist_id
            if not gist_id:
                missing.append(f"TCPMS_{job.upper()}_GIST_ID")
        if missing:
            raise ValueError("missing required configuration: " + ", ".join(missing))
