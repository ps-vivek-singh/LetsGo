"""NewsAgent — wraps NewsTool and shapes output for UI cards.

The tool now returns list[dict] with title/source/url/published_at.
run()            → plain text  (CLI / legacy)
run_structured() → typed dict  (web API §3.2)
"""
from __future__ import annotations

from mcp_tools.news_tools import NewsTool


class NewsAgent:
    def __init__(self) -> None:
        self.tool = NewsTool()

    # ── CLI / legacy ───────────────────────────────────────────────────────
    def run(self) -> str:
        raw = self.tool.get_headlines()
        lines = []
        for item in raw[:3]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title', '')}")
            else:
                lines.append(f"- {item}")
        return "## News\n" + "\n".join(lines)

    # ── Structured (web API §3.2) ──────────────────────────────────────────
    def run_structured(self) -> dict:
        raw: list = self.tool.get_headlines()
        headlines: list[dict] = []

        for item in raw[:5]:
            if isinstance(item, dict):
                # Tool now returns structured dicts — use them directly
                headlines.append({
                    "title":     (item.get("title") or "").strip(),
                    "source":    item.get("source") or "News",
                    "url":       item.get("url"),           # real URL now present
                    "timestamp": item.get("published_at") or "",
                })
            else:
                # Defensive: handle legacy plain-string items
                title = str(item).strip()
                headlines.append({
                    "title":     title,
                    "source":    "News",
                    "url":       None,
                    "timestamp": "",
                })

        # Filter empty titles
        headlines = [h for h in headlines if h["title"]]

        return {
            "section": "news",
            "status":  "success" if headlines else "error",
            "data":    {"headlines": headlines},
        }
