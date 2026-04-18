"""Tests for web tools."""

from __future__ import annotations

import os

import pytest

from taim.orchestrator.builtin_tools.web_tools import _strip_html, web_fetch, web_search


class TestStripHtml:
    def test_removes_tags(self) -> None:
        assert _strip_html("<p>hello</p>") == "hello"

    def test_removes_script(self) -> None:
        assert "alert" not in _strip_html("<script>alert('x')</script>content")

    def test_decodes_entities(self) -> None:
        assert _strip_html("a &amp; b") == "a & b"


@pytest.mark.asyncio
class TestWebSearch:
    async def test_no_api_key_returns_message(self, monkeypatch) -> None:
        monkeypatch.delenv("TAIM_SEARCH_API_KEY", raising=False)
        result = await web_search({"query": "test"}, {})
        assert "not available" in result.lower() or "api key" in result.lower()


@pytest.mark.asyncio
class TestWebFetch:
    async def test_no_url_returns_error(self) -> None:
        result = await web_fetch({"url": ""}, {})
        assert "no url" in result.lower()

    async def test_invalid_url_returns_error(self) -> None:
        result = await web_fetch({"url": "http://nonexistent.invalid.test"}, {})
        assert "failed" in result.lower() or "error" in result.lower()
