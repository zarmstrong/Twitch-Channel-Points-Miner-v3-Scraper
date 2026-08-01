import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-scraper-health.sh"


@pytest.fixture
def healthchecks_server():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            requests.append(
                (
                    self.path,
                    self.rfile.read(length).decode(),
                    self.headers.get("User-Agent"),
                )
            )
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/ping-id", requests
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def run_healthcheck(tmp_path, monitor, healthchecks_url, **environment):
    monitor_path = tmp_path / "scraper-monitor.json"
    if isinstance(monitor, bytes):
        monitor_path.write_bytes(monitor)
    elif monitor is not None:
        monitor_path.write_text(json.dumps(monitor), encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "TCPMS_MONITOR_FILE": str(monitor_path),
            "TCPMS_DROPS_INTERVAL_SECONDS": "900",
            "TCPMS_BADGES_INTERVAL_SECONDS": "1200",
            "TCPMS_HEALTH_GRACE_SECONDS": "300",
            "TCPMS_HEALTHCHECKS_URL": healthchecks_url,
            **environment,
        }
    )
    return subprocess.run(
        [str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def monitor_at(timestamp):
    value = timestamp.isoformat()
    return {
        "version": 1,
        "jobs": {
            job: {
                "last_successful_scrape_at": value,
                "last_successful_upload_at": value,
            }
            for job in ("drops", "badges")
        },
    }


def test_healthcheck_reports_fresh_jobs_as_healthy(tmp_path, healthchecks_server):
    url, requests = healthchecks_server
    result = run_healthcheck(tmp_path, monitor_at(datetime.now(timezone.utc)), url)

    assert result.returncode == 0
    assert result.stdout.startswith("healthy: drops(scrape=")
    assert "badges(scrape=" in result.stdout
    assert requests[0][0] == "/ping-id"
    assert requests[0][1].startswith("healthy: drops(scrape=")
    assert requests[0][2] == "twitch-miner-scraper-healthcheck/1.0"


def test_healthcheck_reports_stale_job_as_unhealthy(tmp_path, healthchecks_server):
    url, requests = healthchecks_server
    timestamp = datetime.now(timezone.utc) - timedelta(seconds=1501)
    result = run_healthcheck(tmp_path, monitor_at(timestamp), url)

    assert result.returncode == 1
    assert "unhealthy: drops scrape is stale" in result.stderr
    assert requests[0][0] == "/ping-id/fail"
    assert requests[0][1].startswith("unhealthy: drops scrape is stale")


def test_healthcheck_can_ignore_uploads_for_no_upload_runs(
    tmp_path, healthchecks_server
):
    url, requests = healthchecks_server
    monitor = monitor_at(datetime.now(timezone.utc))
    del monitor["jobs"]["badges"]["last_successful_upload_at"]

    required = run_healthcheck(tmp_path, monitor, url)
    ignored = run_healthcheck(
        tmp_path, monitor, url, TCPMS_HEALTH_REQUIRE_UPLOAD="false"
    )

    assert required.returncode == 1
    assert "badges.last_successful_upload_at is missing" in required.stderr
    assert ignored.returncode == 0
    assert [request[0] for request in requests] == ["/ping-id/fail", "/ping-id"]


def test_healthcheck_reports_missing_monitor(tmp_path, healthchecks_server):
    url, requests = healthchecks_server
    result = run_healthcheck(tmp_path, None, url)

    assert result.returncode == 1
    assert "monitor file does not exist" in result.stderr
    assert requests[0][0] == "/ping-id/fail"


def test_healthcheck_reports_non_utf8_monitor(tmp_path, healthchecks_server):
    url, requests = healthchecks_server
    result = run_healthcheck(tmp_path, b"\xff\xfe", url)

    assert result.returncode == 1
    assert "monitor file is not valid UTF-8" in result.stderr
    assert requests[0][0] == "/ping-id/fail"
    assert "monitor file is not valid UTF-8" in requests[0][1]


def test_healthcheck_reports_deeply_nested_monitor(tmp_path, healthchecks_server):
    url, requests = healthchecks_server
    content = "[" * 10000 + "]" * 10000
    monitor_path = tmp_path / "scraper-monitor.json"
    monitor_path.write_text(content, encoding="utf-8")

    result = run_healthcheck(tmp_path, None, url)

    assert result.returncode == 1
    assert "monitor file JSON nesting is too deep" in result.stderr
    assert requests[0][0] == "/ping-id/fail"
    assert "monitor file JSON nesting is too deep" in requests[0][1]


def test_healthcheck_requires_ping_url(tmp_path):
    result = run_healthcheck(
        tmp_path,
        monitor_at(datetime.now(timezone.utc)),
        "",
        TCPMS_HEALTHCHECKS_URL="",
    )

    assert result.returncode == 2
    assert "usage:" in result.stderr
