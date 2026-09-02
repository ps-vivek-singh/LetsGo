"""News tool — wraps NewsAPI (preferred), Google News RSS (location-specific), and static RSS fallbacks.

get_headlines(location, query) → list of dicts:
    [{ "title": str, "source": str, "url": str | None, "published_at": str | None }, ...]

Returns structured dicts with real URLs and publisher attribution.
"""
from __future__ import annotations

import re
import urllib.parse
import requests
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from fastmcp import FastMCP
from services.config import Config

mcp = FastMCP("news-server")

# RSS feeds tried in order when NewsAPI and location search are unavailable
_RSS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/rss.xml",              "BBC News"),
    ("https://feeds.feedburner.com/ndtvnews-top-stories",   "NDTV"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "NYT"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_search_term(term: str) -> str:
    """Clean conversational noise from news location/query search terms."""
    if not term:
        return ""
    t = term.strip()
    noise_patterns = [
        r"\b(?:news|headlines|headline|latest|updates|update|top)\s+(?:in|for|about|at|of|near)\b",
        r"\b(?:in|for|about|at|of|near)\s+(?:the\s+)?(?:city\s+of\s+)?",
        r"\b(?:news|headlines|headline|latest|updates|update|top)\b",
        r"\b(?:current\s+location|my\s+location|here)\b",
    ]
    cleaned = t
    for pat in noise_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip(" .,!?")
    return cleaned if cleaned else t


def _parse_rss(url: str, source_name: str) -> list[dict]:
    """Fetch an RSS feed and return structured article dicts with URLs."""
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LetsGo/1.0"})
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
            source_el = (
                entry.find("source")
                or entry.find("{http://www.w3.org/2005/Atom}source")
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

            # Dynamic source name (e.g. from Google News RSS feed)
            actual_source = source_el.text.strip() if source_el is not None and source_el.text else source_name

            items.append({
                "title":        title,
                "source":       actual_source,
                "url":          link,
                "published_at": pub,
            })
            if len(items) >= 5:
                break
        if items:
            break

    return items


@mcp.tool(name="get_headlines", description="Fetch recent news headlines for a location or topic with source and URL")
def get_headlines(location: str = "", query: str = "") -> list:
    search_term = _clean_search_term(location or query)

    # ── Path 1: NewsAPI path ────────────────────────────────────────────────
    api_key = Config.NEWSAPI_API_KEY
    if api_key:
        try:
            endpoint = "https://newsapi.org/v2/everything" if search_term else "https://newsapi.org/v2/top-headlines"
            params: dict[str, Any] = {"pageSize": 5, "apiKey": api_key}
            if search_term:
                params["q"] = search_term
                params["sortBy"] = "publishedAt"
            else:
                params["country"] = "us"

            r = requests.get(endpoint, params=params, timeout=10)
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

    # ── Path 2: Google News RSS for location-specific search ───────────────
    if search_term and search_term.lower() not in ("current location", "location"):
        try:
            encoded_q = urllib.parse.quote(search_term)
            google_rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
            items = _parse_rss(google_rss_url, f"Google News ({search_term.title()})")
            if items:
                return items
        except Exception:
            pass

    # ── Path 3: Standard RSS fallback — try feeds in order ────────────────
    for feed_url, feed_name in _RSS_FEEDS:
        try:
            items = _parse_rss(feed_url, feed_name)
            if items:
                return items
        except Exception:
            continue

    return [{"title": "News unavailable right now.", "source": "—", "url": None, "published_at": _now_iso()}]


class NewsTool:
    def get_headlines(self, location: str = "", query: str = "") -> list:
        return get_headlines(location=location, query=query)


if __name__ == "__main__":
    mcp.run()

