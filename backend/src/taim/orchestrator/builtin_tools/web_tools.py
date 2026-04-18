"""web_search, web_fetch — web interaction tools."""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_SEARCH_TIMEOUT = 15.0
_FETCH_TIMEOUT = 15.0
_MAX_FETCH_CHARS = 8000


async def web_search(args: dict[str, Any], context: dict[str, Any]) -> str:
    """Search the web using configured search API. Returns top results."""
    query = args.get("query", "")
    max_results = args.get("max_results", 5)

    # Check for search API key
    api_key = os.environ.get("TAIM_SEARCH_API_KEY", "")
    if not api_key:
        return (
            "Web search is not available — no search API key configured. "
            "Set TAIM_SEARCH_API_KEY environment variable (Tavily API key)."
        )

    try:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            # Tavily API
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        answer = data.get("answer", "")

        lines = []
        if answer:
            lines.append(f"Summary: {answer}\n")
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("content", "")[:200]
            lines.append(f"{i}. [{title}]({url})\n   {snippet}")

        return "\n\n".join(lines) if lines else "No results found."

    except httpx.HTTPStatusError as e:
        return f"Search API error: {e.response.status_code} — check your API key."
    except httpx.TimeoutException:
        return "Search request timed out. Try again or use a more specific query."
    except Exception as e:
        return f"Search failed: {e}"


async def web_fetch(args: dict[str, Any], context: dict[str, Any]) -> str:
    """Fetch a URL and return its text content (HTML stripped)."""
    url = args.get("url", "")
    if not url:
        return "No URL provided."

    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "tAIm/0.1 (AI agent fetcher)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")

        if "text/html" in content_type:
            text = _strip_html(resp.text)
        elif "text/" in content_type or "json" in content_type or "xml" in content_type:
            text = resp.text
        else:
            return f"Cannot read content type: {content_type}. Only text/HTML supported."

        if len(text) > _MAX_FETCH_CHARS:
            text = (
                text[:_MAX_FETCH_CHARS] + "\n\n[truncated — content exceeds 8000 character limit]"
            )

        return text if text.strip() else "Page returned empty content."

    except httpx.HTTPStatusError as e:
        return f"HTTP {e.response.status_code} error fetching {url}"
    except httpx.TimeoutException:
        return f"Request timed out fetching {url}"
    except Exception as e:
        return f"Failed to fetch {url}: {e}"


def _strip_html(html: str) -> str:
    """Basic HTML → plain text. Strips tags, decodes entities, collapses whitespace."""
    import re

    # Remove script and style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
