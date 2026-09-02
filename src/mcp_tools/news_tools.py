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


def _is_english(text: str) -> bool:
    """Verify that a headline title is English (Latin script)."""
    if not text:
        return False
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return True
    ascii_alpha = [c for c in alpha if c.isascii()]
    return (len(ascii_alpha) / len(alpha)) > 0.85


def _parse_rss(url: str, source_name: str, location_filter: str = "") -> list[dict]:
    """Fetch an RSS feed and return structured article dicts with URLs."""
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    r.raise_for_status()

    # Parse raw bytes directly so XML encoding declaration works natively
    root = ET.fromstring(r.content)

    items: list[dict] = []
    fallback_items: list[dict] = []
    loc_lower = location_filter.lower().strip() if location_filter else ""

    # Search for item elements in feed
    for entry in root.findall(".//item"):
        title_el = entry.find("title")
        link_el = entry.find("link")
        pub_el = entry.find("pubDate")
        source_el = entry.find("source")

        title = title_el.text.strip() if title_el is not None and title_el.text else None
        if not title:
            continue

        # Ensure headline is in English
        if not _is_english(title):
            continue

        link: str | None = None
        if link_el is not None:
            link = (link_el.text or "").strip() or link_el.get("href", "")
            link = link or None

        pub = pub_el.text.strip() if pub_el is not None and pub_el.text else _now_iso()
        actual_source = source_el.text.strip() if source_el is not None and source_el.text else source_name

        item_dict = {
            "title":        title,
            "source":       actual_source,
            "url":          link,
            "published_at": pub,
        }

        fallback_items.append(item_dict)

        # If location_filter is provided, prioritize headlines containing the location name or local keywords
        if loc_lower:
            if loc_lower in title.lower() or loc_lower in actual_source.lower():
                items.append(item_dict)
        else:
            items.append(item_dict)

        if len(items) >= 5:
            break

    return items if items else fallback_items[:5]


@mcp.tool(name="get_headlines", description="Fetch recent news headlines for a location or topic with source and URL")
def get_headlines(location: str = "", query: str = "") -> list:
    search_term = _clean_search_term(location or query)
    loc_lower = search_term.lower().strip() if search_term else ""

    # ── Path 1: Location-specific search via Google News RSS ───────────────
    if search_term and search_term.lower() not in ("current location", "location"):
        try:
            query_str = f"{search_term} news" if not search_term.lower().endswith("news") else search_term
            encoded_q = urllib.parse.quote(query_str)
            google_rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
            items = _parse_rss(google_rss_url, f"Google News ({search_term.title()})", location_filter=search_term)
            if items:
                return items
        except Exception:
            pass

    # ── Path 2: NewsAPI path for general headlines or topic queries ────────
    api_key = Config.NEWSAPI_API_KEY
    if api_key:
        try:
            endpoint = "https://newsapi.org/v2/everything" if search_term else "https://newsapi.org/v2/top-headlines"
            params: dict[str, Any] = {"pageSize": 15, "apiKey": api_key, "language": "en"}
            if search_term:
                params["q"] = search_term
                params["sortBy"] = "publishedAt"
            else:
                params["country"] = "us"

            r = requests.get(endpoint, params=params, timeout=10)
            r.raise_for_status()
            articles = r.json().get("articles", [])
            items: list[dict] = []
            for a in articles[:15]:
                title = (a.get("title") or "").strip()
                if not title or title == "[Removed]" or not _is_english(title):
                    continue
                # Require that title explicitly mentions the requested location
                if loc_lower and loc_lower not in title.lower():
                    continue
                source_name = (a.get("source") or {}).get("name") or "NewsAPI"
                items.append({
                    "title":        title,
                    "source":       source_name,
                    "url":          a.get("url"),
                    "published_at": a.get("publishedAt") or _now_iso(),
                })
                if len(items) >= 5:
                    break
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


