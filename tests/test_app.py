import pytest

from twitch_miner_scraper.app import _verify_output_dir


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
