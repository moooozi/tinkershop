"""Unit tests for tinkershop.tools.web_search."""

from __future__ import annotations

import pytest

from tinkershop.tools.web_search import (
    DuckDuckGoSearcher,
    RateLimiter,
    SafeSearchMode,
    SearchResult,
)


class DummyContext:
    """Stand-in for FastMCP ``Context`` — records info/error calls."""

    def __init__(self) -> None:
        self.info_calls: list[str] = []
        self.error_calls: list[str] = []

    async def info(self, message: str) -> None:
        self.info_calls.append(message)

    async def error(self, message: str) -> None:
        self.error_calls.append(message)


def _results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Example",
            link="https://example.com",
            snippet="hi",
            position=1,
        ),
    ]


def test_format_results_includes_title_url_snippet() -> None:
    searcher = DuckDuckGoSearcher()
    out = searcher.format_results_for_llm(_results())
    assert "Example" in out
    assert "https://example.com" in out
    assert "hi" in out
    assert "Found 1 search results" in out


def test_format_results_handles_empty() -> None:
    searcher = DuckDuckGoSearcher()
    text = searcher.format_results_for_llm([])
    assert "No results" in text
    # Should not leak references to optional backends we don't ship.
    assert "browser backend" not in text


def test_safe_search_modes_are_distinct() -> None:
    values = {m.value for m in SafeSearchMode}
    assert len(values) == 3


@pytest.mark.asyncio
async def test_rate_limiter_does_not_block_under_limit() -> None:
    limiter = RateLimiter(requests_per_minute=5)
    for _ in range(3):
        await limiter.acquire()


@pytest.mark.asyncio
async def test_search_returns_empty_on_block_202(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 202 from httpx (DDG fingerprint block) silently yields zero results."""
    searcher = DuckDuckGoSearcher()
    ctx = DummyContext()

    async def fake_request(_data: dict) -> str:
        return ""

    monkeypatch.setattr(searcher, "_request", fake_request)
    results = await searcher.search("anything", ctx, max_results=5)
    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network errors degrade gracefully to zero results, not exceptions."""
    searcher = DuckDuckGoSearcher()
    ctx = DummyContext()

    async def fake_request(_data: dict) -> str:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(searcher, "_request", fake_request)
    results = await searcher.search("anything", ctx, max_results=5)
    assert results == []
    assert ctx.error_calls, "expected an error to be logged via ctx.error"
