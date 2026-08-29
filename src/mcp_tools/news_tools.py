"""News tool — wraps NewsAPI (preferred) and RSS fallback.

get_headlines() → list of dicts:
    [{ "title": str, "source": str, "url": str | None, "published_at": str | None }, ...]

Previously returned plain strings; now returns structured dicts so the
agent can pass real URLs to the UI.  The agent layer (news_agent.py) still
exposes a plain-text run() for CLI compatibility.
"""
from __future__ import annotations

import requests
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from fastmcp import FastMCP
from services.config import Config

mcp = FastMCP("news-server")

# RSS feeds tried in order when NewsAPI is unavailable
_RSS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/rss.xml",              "BBC News"),
    ("https://feeds.feedburner.com/ndtvnews-top-stories",   "NDTV"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "NYT"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rss(url: str, source_name: str) -> list[dict]:
    """Fetch an RSS feed and return structured article dicts with URLs."""
    r = requests.get(url, timeout=10, headers={"User-Agent": "CommuteCommander/1.0"})
    r.raise_for_status()

    # Strip any BOM or leading whitespace that can break the XML parser
    text = r.text.strip().lstrip("\ufeff")
    root = ET.fromstring(text)

    items: list[dict] = []
    # Both Atom (<entry>) and RSS (<item>) shapes
    for tag in ("item", "{http://www.w3.org/2005/Atom}entry"):
        for entry in root.iter(tag):
            title_el = (
                entry.find("title")
                or entry.find("{http://www.w3.org/2005/Atom}title")
            )
            link_el = (
                entry.find("link")
                or entry.find("{http://www.w3.org/2005/Atom}link")
            )
            pub_el = (
                entry.find("pubDate")
                or entry.find("{http://www.w3.org/2005/Atom}published")
            )

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            if not title:
                continue

            # <link> in RSS is text; in Atom it's an attribute
            link: str | None = None
            if link_el is not None:
                link = (link_el.text or "").strip() or link_el.get("href", "")
                link = link or None

            pub = pub_el.text.strip() if pub_el is not None and pub_el.text else _now_iso()

            items.append({
                "title":        title,
                "source":       source_name,
                "url":          link,
                "published_at": pub,
            })
            if len(items) >= 5:
                break
        if items:
            break

    return items


@mcp.tool(name="get_headlines", description="Fetch recent news headlines with source and URL")
def get_headlines() -> list:
    # ── NewsAPI path ────────────────────────────────────────────────────────
    api_key = Config.NEWSAPI_API_KEY
    if api_key:
        try:
            r = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "pageSize": 5, "apiKey": api_key},
                timeout=10,
            )
            r.raise_for_status()
            articles = r.json().get("articles", [])
            items: list[dict] = []
            for a in articles[:5]:
                title = (a.get("title") or "").strip()
                if not title or title == "[Removed]":
                    continue
                source_name = (a.get("source") or {}).get("name") or "NewsAPI"
                items.append({
                    "title":        title,
                    "source":       source_name,
                    "url":          a.get("url"),
                    "published_at": a.get("publishedAt") or _now_iso(),
                })
            if items:
                return items
        except Exception:
            pass

    # ── RSS fallback — try feeds in order ──────────────────────────────────
    for feed_url, feed_name in _RSS_FEEDS:
        try:
            items = _parse_rss(feed_url, feed_name)
            if items:
                return items
        except Exception:
            continue

    return [{"title": "News unavailable right now.", "source": "—", "url": None, "published_at": _now_iso()}]


class NewsTool:
    def get_headlines(self) -> list:
        return get_headlines()


if __name__ == "__main__":
    mcp.run()
