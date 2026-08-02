"""Unit tests for tinkershop.tools.web_search."""

from __future__ import annotations

import os

import pytest

from tinkershop.tools.web_search import (
    SUPPORTED_BACKENDS,
    DuckDuckGoSearcher,
    RateLimiter,
    SafeSearchMode,
    SearchResult,
    _build_searcher,
    _is_search_block,
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
            rank=1,
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


def test_format_results_mentions_browser_extra_when_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tinkershop.tools.web_search._curl_cffi_available", lambda: False)
    searcher = DuckDuckGoSearcher()
    text = searcher.format_results_for_llm([])
    assert "browser backend" in text
    assert "tinkershop[browser]" in text


def test_format_results_omits_browser_extra_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tinkershop.tools.web_search._curl_cffi_available", lambda: True)
    searcher = DuckDuckGoSearcher()
    text = searcher.format_results_for_llm([])
    assert "browser backend" not in text


def test_safe_search_modes_are_distinct() -> None:
    values = {m.value for m in SafeSearchMode}
    assert len(values) == 3


def test_supported_backends() -> None:
    assert SUPPORTED_BACKENDS == ("httpx", "curl", "auto")


def test_invalid_backend_raises() -> None:
    with pytest.raises(ValueError, match="Unknown backend"):
        DuckDuckGoSearcher(backend="invalid")


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


def test_is_search_block_detects_202() -> None:
    assert _is_search_block(202, "<html></html>")


def test_is_search_block_detects_403() -> None:
    assert _is_search_block(403, "<html></html>")


def test_is_search_block_detects_empty_200() -> None:
    assert _is_search_block(200, "   ")


def test_is_search_block_passes_real_results() -> None:
    assert not _is_search_block(200, "<div class='result'>ok</div>")


def test_build_searcher_defaults_to_curl_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tinkershop.tools.web_search._curl_cffi_available", lambda: True)
    monkeypatch.setenv("DDG_SAFE_SEARCH", "MODERATE")
    monkeypatch.setenv("DDG_REGION", "")
    if "DDG_SEARCH_BACKEND" in os.environ:
        monkeypatch.delenv("DDG_SEARCH_BACKEND")
    searcher = _build_searcher()
    assert searcher.backend == "curl"


def test_build_searcher_defaults_to_httpx_when_curl_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tinkershop.tools.web_search._curl_cffi_available", lambda: False)
    monkeypatch.setenv("DDG_SAFE_SEARCH", "MODERATE")
    monkeypatch.setenv("DDG_REGION", "")
    if "DDG_SEARCH_BACKEND" in os.environ:
        monkeypatch.delenv("DDG_SEARCH_BACKEND")
    searcher = _build_searcher()
    assert searcher.backend == "httpx"


def test_build_searcher_uses_env_backend_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DDG_SEARCH_BACKEND", "httpx")
    monkeypatch.setenv("DDG_SAFE_SEARCH", "MODERATE")
    monkeypatch.setenv("DDG_REGION", "")
    searcher = _build_searcher()
    assert searcher.backend == "httpx"


def test_build_searcher_falls_back_to_best_on_invalid_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tinkershop.tools.web_search._curl_cffi_available", lambda: True)
    monkeypatch.setenv("DDG_SEARCH_BACKEND", "invalid")
    monkeypatch.setenv("DDG_SAFE_SEARCH", "MODERATE")
    monkeypatch.setenv("DDG_REGION", "")
    searcher = _build_searcher()
    assert searcher.backend == "curl"
