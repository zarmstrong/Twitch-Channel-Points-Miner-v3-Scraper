import importlib.util
import stat
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools" / "configure.py"
SPEC = importlib.util.spec_from_file_location("configure", MODULE_PATH)
configure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure)


def test_write_env_uses_owner_only_permissions(tmp_path):
    output = tmp_path / ".env"
    configure.write_env(output, {"TCPMS_EXAMPLE": "value"})
    assert output.read_text(encoding="utf-8") == "TCPMS_EXAMPLE=value\n"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_env_text_rejects_newlines():
    with pytest.raises(ValueError, match="newline"):
        configure.env_text({"TCPMS_EXAMPLE": "first\nsecond"})


def test_merge_env_text_updates_only_selected_values():
    existing = "# Keep this comment\nTCPMS_GITHUB_TOKEN=old\nTCPMS_TWITCH_CLIENT_ID=keep\n"
    merged = configure.merge_env_text(
        existing,
        {"TCPMS_GITHUB_TOKEN": "new", "TCPMS_DROPS_GIST_ID": "drops"},
    )
    assert "# Keep this comment" in merged
    assert "TCPMS_GITHUB_TOKEN=new" in merged
    assert "TCPMS_TWITCH_CLIENT_ID=keep" in merged
    assert "TCPMS_DROPS_GIST_ID=drops" in merged
