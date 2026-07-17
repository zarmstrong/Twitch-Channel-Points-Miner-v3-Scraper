import pytest

from twitch_miner_scraper.config import Settings


def test_defaults_and_job_validation(monkeypatch, tmp_path):
    for name in ("GITHUB_TOKEN", "DROPS_GIST_ID", "BADGES_GIST_ID", "TWITCH_CLIENT_ID", "TWITCH_OAUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert settings.drops_interval == 900
    assert settings.badges_interval == 1200
    settings.validate_job("drops", upload=False)
    with pytest.raises(ValueError, match="TWITCH_CLIENT_ID"):
        settings.validate_job("badges", upload=False)


def test_invalid_interval(monkeypatch):
    monkeypatch.setenv("DROPS_INTERVAL_SECONDS", "0")
    with pytest.raises(ValueError, match="greater than zero"):
        Settings.from_env()
