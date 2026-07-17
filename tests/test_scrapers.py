from twitch_miner_scraper.badges import BadgeScraper
from twitch_miner_scraper.drops import parse_front_page, parse_game_page


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"set_id": "subscriber", "versions": [{"id": "1"}]}]}


class Session:
    def get(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        return Response()


def test_badges_preserve_helix_shape():
    session = Session()
    report = BadgeScraper(session, "client", "oauth:token").scrape()
    assert report["counts"] == {"sets": 1, "versions": 1}
    assert session.kwargs["headers"]["Authorization"] == "Bearer token"


def test_parse_front_page_ignores_expired_and_duplicates():
    source = """
    <a class="game-card" data-slug="one" data-game="One" href="/game/one" data-start="a" data-end="b" data-drops="2">
    <a class="game-card" data-slug="one" data-game="One" href="/game/one">
    <a class="game-card game-card--expired" data-slug="old" href="/game/old">
    """
    assert parse_front_page(source) == [{"slug": "one", "game": "One", "url": "https://twitchdrops.app/game/one", "starts_at": "a", "ends_at": "b", "upcoming": False, "drop_count": 2}]


def test_parse_game_page_assigns_single_campaign_drop():
    source = """
    <main><h1>Example Game</h1>
      <div class="drop-card"><div class="drop-name">Hat</div><div class="drop-time">Watch 30 minutes</div><img src="hat.png"></div>
      <h2>Active Campaigns</h2>
      <div class="campaign-banner" data-end-ts="1893456000000"><span class="cb-name">Launch</span><div class="cb-channels">All Channels</div></div>
      <h2>Past Drops</h2>
    </main>
    """
    report = parse_game_page(source, "https://twitchdrops.app/game/example")
    assert report["campaign_count"] == 1
    assert report["campaigns"][0]["drops"][0]["name"] == "Hat"
