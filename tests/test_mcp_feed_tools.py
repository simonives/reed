# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest
from fastmcp import Client

from reed.api.feeds import FeedAlreadySubscribedError, FeedInvalidError, discover_and_create_feed
from reed.graph import GraphService


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


class TestDiscoverAndCreateFeed:
    async def test_creates_feed_from_valid_url(self, graph, monkeypatch):
        from tests.conftest import SAMPLE_RSS, mock_http_response, patched_feed_fetch

        with patched_feed_fetch(response=mock_http_response(SAMPLE_RSS), module="reed.api.feeds"):
            feed = await discover_and_create_feed(graph, "https://example.com/feed.rss")
        assert feed["url"] == "https://example.com/feed.rss"

    async def test_raises_already_subscribed(self, graph):
        graph.create_feed(
            url="https://dup.example.com/feed.rss", title="Dup", description="", site_url=""
        )
        with pytest.raises(FeedAlreadySubscribedError):
            await discover_and_create_feed(graph, "https://dup.example.com/feed.rss")

    async def test_raises_invalid_on_non_feed_response(self, graph):
        from tests.conftest import mock_http_response, patched_feed_fetch

        with (
            patched_feed_fetch(
                response=mock_http_response(b"<html>not a feed</html>"), module="reed.api.feeds"
            ),
            pytest.raises(FeedInvalidError),
        ):
            await discover_and_create_feed(graph, "https://notafeed.example.com/")


class TestFeedTools:
    async def test_list_feeds_empty(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("list_feeds", {})
            assert result.data == []

    async def test_subscribe_feed_creates_and_list_feeds_returns_it(self, mcp_server):
        from tests.conftest import SAMPLE_RSS, mock_http_response, patched_feed_fetch

        server, graph, poller = mcp_server
        async with Client(server) as client:
            with patched_feed_fetch(
                response=mock_http_response(SAMPLE_RSS), module="reed.api.feeds"
            ):
                created = await client.call_tool(
                    "subscribe_feed", {"url": "https://example.com/feed.rss"}
                )
            assert created.data["url"] == "https://example.com/feed.rss"
            listed = await client.call_tool("list_feeds", {})
            assert len(listed.data) == 1

    async def test_get_feed_returns_404_equivalent_tool_error(self, mcp_server):
        from fastmcp.exceptions import ToolError

        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("get_feed", {"feed_id": "nonexistent"})

    async def test_refresh_feed_triggers_poll(self, mcp_server):
        from unittest.mock import AsyncMock

        from tests.conftest import SAMPLE_RSS, mock_http_response, patched_feed_fetch

        server, graph, poller = mcp_server
        async with Client(server) as client:
            with patched_feed_fetch(
                response=mock_http_response(SAMPLE_RSS), module="reed.api.feeds"
            ):
                created = await client.call_tool(
                    "subscribe_feed", {"url": "https://example.com/feed.rss"}
                )
            poller.refresh_feed = AsyncMock()
            await client.call_tool("refresh_feed", {"feed_id": created.data["id"]})
            poller.refresh_feed.assert_awaited_once()

    async def test_refresh_feed_offloads_graph_get_feed_to_a_thread(self, mcp_server):
        """#post-#168 — with _conn_lock held for a recompute's full duration,
        a synchronous graph.get_feed call directly on the event loop thread
        can block the whole loop. refresh_feed must run both graph.get_feed
        calls via asyncio.to_thread, matching api/feeds.py's REST route for
        the identical problem. Proven here by recording the thread each
        graph.get_feed call actually executes on and asserting neither is
        the event loop's own thread."""
        import threading
        from unittest.mock import AsyncMock

        from tests.conftest import SAMPLE_RSS, mock_http_response, patched_feed_fetch

        server, graph, poller = mcp_server
        main_thread = threading.current_thread()
        call_threads: list[threading.Thread] = []
        original_get_feed = graph.get_feed

        def spying_get_feed(feed_id):
            call_threads.append(threading.current_thread())
            return original_get_feed(feed_id)

        async with Client(server) as client:
            with patched_feed_fetch(
                response=mock_http_response(SAMPLE_RSS), module="reed.api.feeds"
            ):
                created = await client.call_tool(
                    "subscribe_feed", {"url": "https://example.com/feed.rss"}
                )
            poller.refresh_feed = AsyncMock()
            graph.get_feed = spying_get_feed
            try:
                await client.call_tool("refresh_feed", {"feed_id": created.data["id"]})
            finally:
                graph.get_feed = original_get_feed

        assert len(call_threads) == 2
        assert all(t is not main_thread for t in call_threads), (
            "refresh_feed called graph.get_feed directly on the event loop "
            "thread instead of via asyncio.to_thread"
        )
