"""Jobs and scheduling for scraper runs."""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from pathlib import Path

from .auth import TOKEN_CACHE_FILENAME, TwitchTokenManager
from .badges import BadgeScraper
from .config import Settings
from .drops import DropsScraper
from .gist import GistPublisher
from .http import build_session

LOG = logging.getLogger(__name__)


def _verify_output_dir(path: Path) -> None:
    LOG.debug("Verifying output directory %s", path)
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".tcpms-write-test"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        LOG.debug("Output directory is writable: %s", path)
    except OSError as error:
        raise OSError(
            f"output directory is not writable: {path}; ensure the mounted "
            "volume is writable by container UID 10001"
        ) from error


def _write_snapshot(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    LOG.debug(
        "Writing snapshot %s via %s (%d UTF-8 bytes)",
        path,
        temporary,
        len(content.encode("utf-8")),
    )
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)
    LOG.debug("Snapshot replaced atomically: %s", path)


def _load_snapshot(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        LOG.debug("No previous snapshot at %s; a full scrape is required", path)
        return None
    except (OSError, json.JSONDecodeError) as error:
        LOG.warning("Unable to load previous snapshot %s: %s", path, error)
        return None
    if not isinstance(data, dict) or data.get("version") != 1:
        LOG.warning("Ignoring incompatible previous snapshot at %s", path)
        return None
    return data


class Application:
    def __init__(self, settings: Settings, upload=True):
        self.settings, self.upload = settings, upload
        self.session = build_session()
        _verify_output_dir(self.settings.output_dir)
        LOG.debug(
            "Application initialized: upload=%s drops_interval=%ss "
            "badges_interval=%ss timeout=%ss request_delay=%ss",
            self.upload,
            self.settings.drops_interval,
            self.settings.badges_interval,
            self.settings.request_timeout,
            self.settings.request_delay,
        )

    def run_job(self, job: str) -> dict:
        self.settings.validate_job(job, self.upload)
        LOG.info("Starting %s scrape", job)
        if job == "drops":
            snapshot_path = self.settings.output_dir / self.settings.drops_gist_filename
            previous = _load_snapshot(snapshot_path)
            data = DropsScraper(
                self.session,
                self.settings.request_timeout,
                self.settings.request_delay,
            ).scrape(previous=previous)
            gist_id, filename = self.settings.drops_gist_id, self.settings.drops_gist_filename
        elif job == "badges":
            token = self.settings.twitch_oauth_token
            if not token:
                LOG.debug("No static Twitch token configured; using token manager")
                token = TwitchTokenManager(
                    self.session,
                    self.settings.twitch_client_id,
                    self.settings.twitch_client_secret,
                    self.settings.output_dir / TOKEN_CACHE_FILENAME,
                    self.settings.request_timeout,
                ).get_token()
            else:
                LOG.debug("Using statically configured Twitch OAuth token")
            data = BadgeScraper(
                self.session,
                self.settings.twitch_client_id,
                token,
                self.settings.request_timeout,
            ).scrape()
            gist_id, filename = self.settings.badges_gist_id, self.settings.badges_gist_filename
        else:
            raise ValueError(f"unknown job: {job}")
        _write_snapshot(self.settings.output_dir / filename, data)
        if self.upload:
            GistPublisher(self.settings.github_token, self.session, self.settings.request_timeout).publish(gist_id, filename, data)
            LOG.info("Published %s to Gist %s", job, gist_id)
        LOG.info("Completed %s scrape", job)
        return data

    def run_all(self) -> bool:
        success = True
        for job in ("drops", "badges"):
            try:
                self.run_job(job)
            except Exception:
                success = False
                LOG.exception("%s scrape failed", job)
        return success

    def serve(self) -> None:
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda _signum, _frame: stop.set())
        deadlines = {"drops": 0.0, "badges": 0.0}
        intervals = {"drops": self.settings.drops_interval, "badges": self.settings.badges_interval}
        LOG.info("Scheduler started (drops=%ss, badges=%ss)", intervals["drops"], intervals["badges"])
        while not stop.is_set():
            now = time.monotonic()
            for job in ("drops", "badges"):
                if now < deadlines[job]:
                    continue
                try:
                    self.run_job(job)
                except Exception:
                    LOG.exception("%s scrape failed; retaining the previous snapshot/Gist", job)
                deadlines[job] = time.monotonic() + intervals[job]
                LOG.debug(
                    "Next %s scrape scheduled in %ss", job, intervals[job]
                )
            wait = max(0.0, min(deadlines.values()) - time.monotonic())
            LOG.debug("Scheduler waiting up to %.1fs", min(wait, 60.0))
            stop.wait(min(wait, 60.0))
        LOG.info("Scheduler stopped")
