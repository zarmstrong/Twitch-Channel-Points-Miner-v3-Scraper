"""Fetch and parse the active/upcoming TwitchDrops.app catalog."""

from __future__ import annotations

import hashlib
import html
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

HOME_URL = "https://twitchdrops.app/"
LOG = logging.getLogger(__name__)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _match(pattern: str, value: str, default=None):
    found = re.search(pattern, value, re.I | re.S)
    return _clean(found.group(1)) if found else default


def _div_blocks(source: str, class_name: str):
    opening = re.compile(
        rf'<div\b[^>]*class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>',
        re.I,
    )
    tags = re.compile(r"</?div\b[^>]*>", re.I)
    for start in opening.finditer(source):
        depth = 1
        for tag in tags.finditer(source, start.end()):
            depth += -1 if tag.group(0).startswith("</") else 1
            if depth == 0:
                yield source[start.start() : tag.end()]
                break


def _section(source: str, heading: str, following: list[str]) -> str:
    start = re.search(rf"<h2[^>]*>\s*{re.escape(heading)}\s*</h2>", source, re.I)
    if not start:
        return ""
    end = len(source)
    for name in following:
        match = re.search(
            rf"<h2[^>]*>\s*{re.escape(name)}\s*</h2>", source[start.end() :], re.I
        )
        if match:
            end = min(end, start.end() + match.start())
    return source[start.end() : end]


def parse_front_page(source: str) -> list[dict]:
    games = []
    seen = set()
    cards = re.findall(
        r'<a\b[^>]*class=["\'][^"\']*\bgame-card\b[^"\']*["\'][^>]*>',
        source,
        re.I,
    )
    for card in cards:
        if "game-card--expired" in card:
            continue

        def attribute(name):
            found = re.search(rf'\b{name}=["\']([^"\']*)["\']', card, re.I)
            return html.unescape(found.group(1)) if found else None

        slug, href = attribute("data-slug"), attribute("href")
        if not slug or not href or slug in seen:
            continue
        seen.add(slug)
        count = attribute("data-drops")
        games.append(
            {
                "slug": slug,
                "game": attribute("data-game"),
                "url": f"https://twitchdrops.app{href}",
                "starts_at": attribute("data-start"),
                "ends_at": attribute("data-end"),
                "upcoming": " upcoming" in card,
                "drop_count": int(count) if str(count or "").isdigit() else None,
            }
        )
    return games


def _parse_drop(block: str) -> dict:
    image = re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)', block, re.I)
    return {
        "name": _match(r'class=["\'][^"\']*\bdrop-name\b[^"\']*["\'][^>]*>(.*?)</div>', block),
        "requirement": _match(r'class=["\'][^"\']*\bdrop-time\b[^"\']*["\'][^>]*>(.*?)</div>', block),
        "campaign": _match(r'class=["\'][^"\']*\bdrop-campaign\b[^"\']*["\'][^>]*>(.*?)</div>', block),
        "image_url": html.unescape(image.group(1)) if image else None,
    }


def _parse_campaign(block: str, game: str, starts_at=None) -> dict:
    name = _match(r'class=["\'][^"\']*\bcb-name\b[^"\']*["\'][^>]*>(.*?)</span>', block)
    timestamp = re.search(r'\bdata-end-ts=["\'](\d+)["\']', block, re.I)
    end = int(timestamp.group(1)) if timestamp else None
    channels = re.findall(
        r'href=["\']https?://(?:www\.)?twitch\.tv/([^?"\'/#]+)[^"\']*["\']',
        block,
        re.I,
    )
    all_channels = "All Channels" in block
    identity = f"{game}|{name}|{end or ''}"
    return {
        "id": "twitchdrops-app-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
        "name": name,
        "owner": _match(r'class=["\'][^"\']*\bcb-owner\b[^"\']*["\'][^>]*>(.*?)</span>', block),
        "dates": _match(r'class=["\'][^"\']*\bcb-dates\b[^"\']*["\'][^>]*>(.*?)</span>', block),
        "starts_at": starts_at,
        "ends_at": datetime.fromtimestamp(end / 1000, timezone.utc).isoformat() if end else None,
        "all_channels": all_channels,
        "channels": [] if all_channels else list(dict.fromkeys(x.lower() for x in channels)),
        "description": _match(r'class=["\'][^"\']*\bcb-desc\b[^"\']*["\'][^>]*>(.*?)</div>', block),
        "drops": [],
    }


def parse_game_page(source: str, url: str) -> dict:
    game = _match(r"<main\b.*?<h1[^>]*>(.*?)</h1>", source)
    if not game:
        raise ValueError(f"{url} does not contain a game heading")
    active = _section(source, "Active Campaigns", ["How to get these drops", "Upcoming Campaigns", "Past Drops", "Past Campaigns"])
    upcoming = _section(source, "Upcoming Campaigns", ["Past Drops", "Past Campaigns", "Frequently Asked Questions"])
    boundary = re.search(r"<h2[^>]*>\s*(?:Active Campaigns|How to get these drops|Upcoming Campaigns|Past Drops|Past Campaigns)\s*</h2>", source, re.I)
    viewer = source[: boundary.start()] if boundary else source
    drops = [drop for block in _div_blocks(viewer, "drop-card") if (drop := _parse_drop(block))["name"]]
    campaigns = [_parse_campaign(block, game) for block in _div_blocks(active, "campaign-banner")]
    page_path = urlparse(url).path.rstrip("/")
    timing = re.search(rf'<a\b[^>]*href=["\']{re.escape(page_path)}["\'][^>]*data-end=["\']([^"\']+)["\'][^>]*data-start=["\']([^"\']+)["\']', source, re.I)
    upcoming_campaigns = [_parse_campaign(block, game, timing.group(2) if timing else None) for block in _div_blocks(upcoming, "campaign-banner")]
    watch = lambda drop: (drop.get("requirement") or "").casefold().startswith("watch ")
    unassigned = [drop for drop in drops if not drop["campaign"] and watch(drop)]
    if len(campaigns) == 1:
        for drop in unassigned:
            drop["campaign"] = campaigns[0]["name"]
    watch_names = {(drop["campaign"] or "").casefold() for drop in drops if drop["campaign"] and watch(drop)}
    for campaign in campaigns:
        campaign["drops"] = [drop for drop in drops if (drop["campaign"] or "").casefold() == (campaign["name"] or "").casefold()]
    active_campaigns = [campaign for campaign in campaigns if (campaign["name"] or "").casefold() in watch_names]
    for campaign in active_campaigns:
        campaign["drops"] = [drop for drop in campaign["drops"] if watch(drop)]
    if len(upcoming_campaigns) == 1:
        upcoming_campaigns[0]["drops"] = [drop for drop in drops if watch(drop)]
    return {
        "source": url,
        "game": game,
        "campaign_count": len(active_campaigns),
        "non_watch_campaign_count": len(campaigns) - len(active_campaigns),
        "drop_count": len(drops),
        "campaigns": active_campaigns,
        "upcoming_campaigns": upcoming_campaigns,
        "non_watch_campaigns": [x for x in campaigns if x not in active_campaigns],
        "drops": drops,
    }


class DropsScraper:
    def __init__(self, session: requests.Session, timeout=30, request_delay=0.25):
        self.session, self.timeout, self.request_delay = session, timeout, request_delay

    def scrape(self) -> dict:
        LOG.debug("Requesting TwitchDrops.app index from %s", HOME_URL)
        response = self.session.get(HOME_URL, headers={"Accept": "text/html"}, timeout=self.timeout)
        response.raise_for_status()
        indexed = parse_front_page(response.text)
        LOG.info("TwitchDrops.app index contains %d active/upcoming games", len(indexed))
        reports = []
        for index, game in enumerate(indexed):
            LOG.debug(
                "Scraping game %d/%d: slug=%s url=%s",
                index + 1,
                len(indexed),
                game.get("slug"),
                game.get("url"),
            )
            response = self.session.get(game["url"], headers={"Accept": "text/html"}, timeout=self.timeout)
            response.raise_for_status()
            report = parse_game_page(response.text, game["url"])
            reports.append(report)
            LOG.debug(
                "Parsed %s: campaigns=%d upcoming=%d drops=%d",
                report.get("game"),
                len(report["campaigns"]),
                len(report["upcoming_campaigns"]),
                len(report["drops"]),
            )
            if self.request_delay and index + 1 < len(indexed):
                LOG.debug("Waiting %ss before the next game request", self.request_delay)
                time.sleep(self.request_delay)
        return {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": HOME_URL,
            "counts": {
                "games": len(reports),
                "campaigns": sum(len(x["campaigns"]) + len(x["upcoming_campaigns"]) for x in reports),
                "drops": sum(len(x["drops"]) for x in reports),
            },
            "indexed_games": indexed,
            "games": reports,
        }
