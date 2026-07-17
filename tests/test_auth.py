import json
import time

from twitch_miner_scraper.auth import TwitchTokenManager


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "access_token": "generated-token",
            "expires_in": 3600,
            "token_type": "bearer",
        }


class Session:
    def __init__(self):
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        self.args, self.kwargs = args, kwargs
        return Response()


def test_fetches_and_persists_token(tmp_path):
    session = Session()
    path = tmp_path / "twitch-app-token.json"
    manager = TwitchTokenManager(session, "client", "secret", path)

    assert manager.get_token() == "generated-token"
    cached = json.loads(path.read_text(encoding="utf-8"))
    assert cached["client_id"] == "client"
    assert cached["expires_at"] > time.time()
    assert path.stat().st_mode & 0o777 == 0o600
    assert session.kwargs["data"]["client_secret"] == "secret"


def test_reuses_unexpired_token_without_secret(tmp_path):
    path = tmp_path / "twitch-app-token.json"
    path.write_text(
        json.dumps(
            {
                "access_token": "cached-token",
                "client_id": "client",
                "expires_at": time.time() + 3600,
            }
        ),
        encoding="utf-8",
    )
    session = Session()

    assert TwitchTokenManager(session, "client", None, path).get_token() == "cached-token"
    assert session.calls == 0
