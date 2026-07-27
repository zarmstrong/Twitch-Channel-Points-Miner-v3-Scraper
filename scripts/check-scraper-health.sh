#!/usr/bin/env bash

set -euo pipefail

healthchecks_url="${1:-${TCPMS_HEALTHCHECKS_URL:-}}"
monitor_file="${2:-${TCPMS_MONITOR_FILE:-${TCPMS_OUTPUT_DIR:-/data}/scraper-monitor.json}}"

if [[ -z "${healthchecks_url}" ]]; then
    echo "usage: $0 HEALTHCHECKS_URL [MONITOR_FILE]" >&2
    echo "or set TCPMS_HEALTHCHECKS_URL and TCPMS_MONITOR_FILE" >&2
    exit 2
fi

exec python3 - "${healthchecks_url}" "${monitor_file}" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


def positive_seconds(name: str, default: str) -> float:
    try:
        value = float(os.getenv(name, default))
    except ValueError:
        raise ValueError(f"{name} must be a number") from None
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def require_upload() -> bool:
    value = os.getenv("TCPMS_HEALTH_REQUIRE_UPLOAD", "true").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        "TCPMS_HEALTH_REQUIRE_UPLOAD must be true/false, yes/no, on/off, or 1/0"
    )


def parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} is missing")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} is not a valid ISO 8601 timestamp") from None
    if timestamp.tzinfo is None:
        raise ValueError(f"{field} is not timezone-aware")
    return timestamp.astimezone(timezone.utc)


def ping_url(url: str, failed: bool) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Healthchecks URL must be an HTTP or HTTPS URL")
    if not failed:
        return url
    path = parsed.path.rstrip("/") + "/fail"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def ping(url: str, message: str, failed: bool) -> None:
    timeout = positive_seconds("TCPMS_HEALTHCHECKS_TIMEOUT_SECONDS", "10")
    request = Request(
        ping_url(url, failed),
        data=(message + "\n").encode(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise ValueError(
                    f"Healthchecks ping returned HTTP {response.status}"
                )
    except URLError as error:
        raise ValueError(f"Healthchecks ping failed: {error.reason}") from None


def check() -> str:
    path = Path(sys.argv[2])
    intervals = {
        "drops": positive_seconds("TCPMS_DROPS_INTERVAL_SECONDS", "900"),
        "badges": positive_seconds("TCPMS_BADGES_INTERVAL_SECONDS", "1200"),
    }
    grace = positive_seconds("TCPMS_HEALTH_GRACE_SECONDS", "300")
    check_upload = require_upload()

    try:
        monitor = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"monitor file does not exist: {path}") from None
    except OSError as error:
        raise ValueError(f"cannot read monitor file {path}: {error}") from None
    except UnicodeDecodeError:
        raise ValueError(f"monitor file is not valid UTF-8: {path}") from None
    except json.JSONDecodeError:
        raise ValueError(f"monitor file is not valid JSON: {path}") from None

    if not isinstance(monitor, dict) or monitor.get("version") != 1:
        raise ValueError("monitor file has an unsupported schema version")
    jobs = monitor.get("jobs")
    if not isinstance(jobs, dict):
        raise ValueError("monitor file has no jobs object")

    now = datetime.now(timezone.utc)
    summaries = []
    events = ["scrape", "upload"] if check_upload else ["scrape"]
    for job, interval in intervals.items():
        status = jobs.get(job)
        if not isinstance(status, dict):
            raise ValueError(f"{job} has no recorded status")
        event_ages = []
        for event in events:
            field = f"last_successful_{event}_at"
            timestamp = parse_timestamp(status.get(field), f"{job}.{field}")
            age = (now - timestamp).total_seconds()
            if age < -grace:
                raise ValueError(f"{job} {event} timestamp is in the future")
            maximum_age = interval + grace
            if age > maximum_age:
                raise ValueError(
                    f"{job} {event} is stale: {int(age)}s old "
                    f"(maximum {int(maximum_age)}s)"
                )
            event_ages.append(f"{event}={max(0, int(age))}s")
        summaries.append(f"{job}({', '.join(event_ages)})")

    return "healthy: " + "; ".join(summaries)


try:
    healthchecks_url = sys.argv[1]
    ping_url(healthchecks_url, failed=False)
    message = check()
except ValueError as error:
    message = f"unhealthy: {error}"
    print(message, file=sys.stderr)
    try:
        ping(healthchecks_url, message, failed=True)
    except ValueError as ping_error:
        print(f"unhealthy: {ping_error}", file=sys.stderr)
    raise SystemExit(1)
else:
    try:
        ping(healthchecks_url, message, failed=False)
    except ValueError as error:
        print(f"unhealthy: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(message)
PY
