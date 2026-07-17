import pytest

from twitch_miner_scraper.config import Settings


def test_defaults_and_job_validation(monkeypatch, tmp_path):
    for name in (
        "TCPMS_GITHUB_TOKEN",
        "TCPMS_DROPS_GIST_ID",
        "TCPMS_BADGES_GIST_ID",
        "TCPMS_TWITCH_CLIENT_ID",
        "TCPMS_TWITCH_CLIENT_SECRET",
        "TCPMS_TWITCH_OAUTH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TCPMS_OUTPUT_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert settings.drops_interval == 900
    assert settings.badges_interval == 1200
    assert settings.log_level == "INFO"
    settings.validate_job("drops", upload=False)
    with pytest.raises(ValueError, match="TCPMS_TWITCH_CLIENT_ID"):
        settings.validate_job("badges", upload=False)


def test_badges_accept_client_credentials(monkeypatch):
    monkeypatch.setenv("TCPMS_TWITCH_CLIENT_ID", "client")
    monkeypatch.setenv("TCPMS_TWITCH_CLIENT_SECRET", "secret")
    monkeypatch.delenv("TCPMS_TWITCH_OAUTH_TOKEN", raising=False)
    Settings.from_env().validate_job("badges", upload=False)


def test_invalid_interval(monkeypatch):
    monkeypatch.setenv("TCPMS_DROPS_INTERVAL_SECONDS", "0")
    with pytest.raises(ValueError, match="greater than zero"):
        Settings.from_env()


def test_log_level_is_normalized_and_validated(monkeypatch):
    monkeypatch.setenv("TCPMS_LOG_LEVEL", "debug")
    assert Settings.from_env().log_level == "DEBUG"
    monkeypatch.setenv("TCPMS_LOG_LEVEL", "verbose")
    with pytest.raises(ValueError, match="TCPMS_LOG_LEVEL"):
        Settings.from_env()
