import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from twitch_miner_scraper.app import Application, _record_success, _verify_output_dir


def test_verify_output_dir_creates_directory(tmp_path):
    output = tmp_path / "data"
    _verify_output_dir(output)
    assert output.is_dir()
    assert not (output / ".tcpms-write-test").exists()


def test_verify_output_dir_reports_permission_problem(monkeypatch, tmp_path):
    def deny_write(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("pathlib.Path.write_text", deny_write)
    with pytest.raises(OSError, match="container UID 10001"):
        _verify_output_dir(tmp_path)


def test_record_success_preserves_other_job_and_event_timestamps(tmp_path):
    monitor_path = tmp_path / "scraper-monitor.json"

    _record_success(monitor_path, "drops", "scrape")
    first = json.loads(monitor_path.read_text(encoding="utf-8"))
    scrape_at = first["jobs"]["drops"]["last_successful_scrape_at"]
    _record_success(monitor_path, "drops", "upload")
    _record_success(monitor_path, "badges", "scrape")

    monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
    assert monitor["version"] == 1
    assert monitor["jobs"]["drops"]["last_successful_scrape_at"] == scrape_at
    assert "last_successful_upload_at" in monitor["jobs"]["drops"]
    assert "last_successful_scrape_at" in monitor["jobs"]["badges"]
    assert "last_successful_upload_at" not in monitor["jobs"]["badges"]
    for status in monitor["jobs"].values():
        for timestamp in status.values():
            assert datetime.fromisoformat(timestamp).utcoffset().total_seconds() == 0


def test_record_success_does_not_replace_invalid_monitor(tmp_path):
    monitor_path = tmp_path / "scraper-monitor.json"
    monitor_path.write_text("not json", encoding="utf-8")

    assert _record_success(monitor_path, "drops", "scrape") is False

    assert monitor_path.read_text(encoding="utf-8") == "not json"
    assert not monitor_path.with_suffix(".json.tmp").exists()


def test_record_success_does_not_replace_non_utf8_monitor(tmp_path):
    monitor_path = tmp_path / "scraper-monitor.json"
    content = b"\xff\xfe"
    monitor_path.write_bytes(content)

    assert _record_success(monitor_path, "drops", "scrape") is False

    assert monitor_path.read_bytes() == content


def test_record_success_does_not_replace_deeply_nested_monitor(tmp_path):
    monitor_path = tmp_path / "scraper-monitor.json"
    content = "[" * 10000 + "]" * 10000
    monitor_path.write_text(content, encoding="utf-8")

    assert _record_success(monitor_path, "drops", "scrape") is False

    assert monitor_path.read_text(encoding="utf-8") == content


def test_record_success_does_not_replace_unreadable_monitor(monkeypatch, tmp_path):
    monitor_path = tmp_path / "scraper-monitor.json"

    def deny_read(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("pathlib.Path.read_text", deny_read)

    assert _record_success(monitor_path, "drops", "scrape") is False


def test_record_success_write_failure_does_not_raise(monkeypatch, tmp_path):
    def deny_write(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("twitch_miner_scraper.app._write_snapshot", deny_write)

    assert _record_success(tmp_path / "monitor.json", "drops", "scrape") is False


def test_record_success_rejects_unknown_event(tmp_path):
    with pytest.raises(ValueError, match="unknown success event"):
        _record_success(tmp_path / "monitor.json", "drops", "download")


def test_failed_upload_does_not_record_upload_success(monkeypatch, tmp_path):
    class FakeDropsScraper:
        def __init__(self, *args):
            pass

        def scrape(self, previous=None):
            return {"version": 1}

    class FailingPublisher:
        def __init__(self, *args):
            pass

        def publish(self, *args):
            raise RuntimeError("upload failed")

    monkeypatch.setattr("twitch_miner_scraper.app.DropsScraper", FakeDropsScraper)
    monkeypatch.setattr("twitch_miner_scraper.app.GistPublisher", FailingPublisher)
    settings = SimpleNamespace(
        output_dir=tmp_path,
        drops_gist_filename="drops.json",
        drops_gist_id="gist-id",
        request_timeout=30,
        request_delay=0,
        github_token="token",
        validate_job=lambda *args: None,
    )
    app = Application.__new__(Application)
    app.settings = settings
    app.upload = True
    app.session = object()

    with pytest.raises(RuntimeError, match="upload failed"):
        app.run_job("drops")

    monitor = json.loads(
        (tmp_path / "scraper-monitor.json").read_text(encoding="utf-8")
    )
    assert "last_successful_scrape_at" in monitor["jobs"]["drops"]
    assert "last_successful_upload_at" not in monitor["jobs"]["drops"]
