"""Jobs and scheduling for scraper runs."""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from pathlib import Path

from .badges import BadgeScraper
from .config import Settings
from .drops import DropsScraper
from .gist import GistPublisher
from .http import build_session

LOG = logging.getLogger(__name__)


def _write_snapshot(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class Application:
    def __init__(self, settings: Settings, upload=True):
        self.settings, self.upload = settings, upload
        self.session = build_session()

    def run_job(self, job: str) -> dict:
        self.settings.validate_job(job, self.upload)
        LOG.info("Starting %s scrape", job)
        if job == "drops":
            data = DropsScraper(self.session, self.settings.request_timeout, self.settings.request_delay).scrape()
            gist_id, filename = self.settings.drops_gist_id, self.settings.drops_gist_filename
        elif job == "badges":
            data = BadgeScraper(self.session, self.settings.twitch_client_id, self.settings.twitch_oauth_token, self.settings.request_timeout).scrape()
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
            wait = max(0.0, min(deadlines.values()) - time.monotonic())
            stop.wait(min(wait, 60.0))
        LOG.info("Scheduler stopped")
