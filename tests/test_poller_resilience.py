# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from reed.graph import GraphService
from reed.poller import FeedPoller


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


async def _yield_sleep(*_: object) -> None:
    """Yields once to the event loop without calling asyncio.sleep (avoids recursive patch)."""
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[None] = loop.create_future()
    loop.call_soon(fut.set_result, None)
    await fut


class TestPollerSupervision:
    """#127 — poller loop must survive exceptions in _poll_due_feeds."""

    async def test_exception_in_poll_cycle_does_not_kill_loop(self, graph):
        poller = FeedPoller(graph)
        call_count = 0
        resumed = asyncio.Event()

        async def mock_poll_due():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated transient error")
            resumed.set()

        poller._poll_due_feeds = mock_poll_due

        with patch("reed.poller.asyncio.sleep", side_effect=_yield_sleep):
            task = asyncio.create_task(poller.start())
            await asyncio.wait_for(resumed.wait(), timeout=5.0)
            await poller.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        assert call_count >= 2

    async def test_exception_in_recompute_does_not_kill_loop(self, graph):
        """#160 — a recompute failure must not permanently kill the poller loop."""
        poller = FeedPoller(graph)
        poll_count = 0
        resumed = asyncio.Event()

        async def mock_poll_due():
            pass

        async def mock_maybe_recompute():
            nonlocal poll_count
            poll_count += 1
            if poll_count == 1:
                raise RuntimeError("simulated recompute failure")
            resumed.set()

        poller._poll_due_feeds = mock_poll_due
        poller._maybe_recompute_edges = mock_maybe_recompute

        with patch("reed.poller.asyncio.sleep", side_effect=_yield_sleep):
            task = asyncio.create_task(poller.start())
            await asyncio.wait_for(resumed.wait(), timeout=5.0)
            await poller.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        assert poll_count >= 2

    async def test_backfill_exception_does_not_prevent_polling(self, graph):
        poller = FeedPoller(graph)
        polled = asyncio.Event()

        async def mock_poll_due():
            polled.set()

        poller._poll_due_feeds = mock_poll_due
        poller._backfill_topics = AsyncMock(side_effect=RuntimeError("backfill failed"))

        with patch("reed.poller.asyncio.sleep", side_effect=_yield_sleep):
            task = asyncio.create_task(poller.start())
            await asyncio.wait_for(polled.wait(), timeout=5.0)
            await poller.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        assert polled.is_set()


class TestParallelPolling:
    """#130 — due feeds must be polled concurrently, not sequentially."""

    async def test_multiple_feeds_polled_concurrently(self, graph):
        for i in range(3):
            graph.create_feed(
                url=f"https://feed{i}.example.com/rss",
                title=f"Feed {i}",
                description="",
                site_url="",
            )

        poller = FeedPoller(graph)
        poll_times: list[float] = []

        async def slow_poll(feed, now, http, config):
            await asyncio.sleep(0.05)
            poll_times.append(time.monotonic())

        poller._poll_feed = slow_poll

        with patch.object(poller, "_http", new=AsyncMock()):
            start = time.monotonic()
            await poller._poll_due_feeds()
            elapsed = time.monotonic() - start

        assert len(poll_times) == 3
        # Concurrent: total time should be much less than 3 × 0.05s sequential
        assert elapsed < 0.12


class TestGuidTitleFallback:
    """#129 — title-fallback guid must be feed-scoped to prevent cross-feed merges."""

    def test_same_title_different_feeds_creates_separate_items(self, graph):
        graph.create_feed(url="https://a.example/rss", title="A", description="", site_url="")
        graph.create_feed(url="https://b.example/rss", title="B", description="", site_url="")

        def rss(link: str) -> bytes:
            return (
                b'<?xml version="1.0"?><rss version="2.0"><channel>'
                b"<title>Feed</title><link>" + link.encode() + b"</link>"
                b"<item><title>Untitled</title><description>Content</description></item>"
                b"</channel></rss>"
            )

        poller = FeedPoller(graph)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        poller._ingest_entries("https://a.example/rss", rss("https://a.example"), now)
        poller._ingest_entries("https://b.example/rss", rss("https://b.example"), now)

        _, total = graph.list_items()
        assert total == 2, f"Expected 2 distinct items (one per feed), got {total}"


class TestSubscribeFeedValidation:
    """#128 — POST /feeds must reject non-feed URLs."""

    def test_html_page_returns_422(self, authed):
        from .conftest import mock_http_response, patched_feed_fetch

        html = b"<!DOCTYPE html><html><body><h1>My Homepage</h1></body></html>"
        with patched_feed_fetch(response=mock_http_response(content=html)):
            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/"})
        assert r.status_code == 422

    def test_empty_response_returns_422(self, authed):
        from .conftest import mock_http_response, patched_feed_fetch

        with patched_feed_fetch(response=mock_http_response(content=b"")):
            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/"})
        assert r.status_code == 422

    def test_valid_rss_still_returns_201(self, authed):
        from .conftest import patched_feed_fetch

        with patched_feed_fetch():
            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})
        assert r.status_code == 201
