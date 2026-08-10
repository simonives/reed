# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import create_test_item


class TestGraphTraversalTools:
    async def test_find_similar_items_unknown_item_raises(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("find_similar_items", {"item_id": "nonexistent"})

    async def test_find_similar_items_returns_similar_item_with_score(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="i1",
            url="https://f.example.com/i1",
            title="One",
        )
        i2 = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="i2",
            url="https://f.example.com/i2",
            title="Two",
        )
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        async with Client(server) as client:
            result = await client.call_tool("find_similar_items", {"item_id": i1})
            assert len(result.data) == 1
            assert result.data[0]["id"] == i2
            assert "score" in result.data[0]

    async def test_find_similar_items_unread_only_filters_read_items(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="i1",
            url="https://f.example.com/i1",
            title="One",
        )
        i2 = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="i2",
            url="https://f.example.com/i2",
            title="Two",
        )
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)
        graph.update_item_state(i2, read=True)

        async with Client(server) as client:
            result = await client.call_tool(
                "find_similar_items", {"item_id": i1, "unread_only": True}
            )
            assert result.data == []

    async def test_find_adjacent_to_starred_empty_on_fresh_instance(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("find_adjacent_to_starred", {})
            assert result.data == []

    async def test_find_adjacent_to_starred_returns_candidate_with_score(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        starred = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="s1",
            url="https://f.example.com/s1",
            title="Starred",
        )
        graph.update_item_state(starred, starred=True)
        candidate = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="c1",
            url="https://f.example.com/c1",
            title="Candidate",
        )
        graph.enrich_item(starred, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(candidate, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        async with Client(server) as client:
            result = await client.call_tool("find_adjacent_to_starred", {})
            assert len(result.data) == 1
            assert result.data[0]["id"] == candidate
            assert "score" in result.data[0]

    async def test_find_adjacent_to_starred_min_score_filters_out_candidate(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        starred = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="s1",
            url="https://f.example.com/s1",
            title="Starred",
        )
        graph.update_item_state(starred, starred=True)
        candidate = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="c1",
            url="https://f.example.com/c1",
            title="Candidate",
        )
        graph.enrich_item(starred, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(candidate, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        async with Client(server) as client:
            result = await client.call_tool("find_adjacent_to_starred", {"min_score": 2.0})
            assert result.data == []

    async def test_explore_topic_unknown_name_raises(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("explore_topic", {"topic_name": "Nonexistent"})

    async def test_explore_topic_returns_items_and_related(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
        )
        graph.enrich_item(item_id, [("AI Governance", 0.9)])
        async with Client(server) as client:
            result = await client.call_tool("explore_topic", {"topic_name": "AI Governance"})
            assert result.data["topic"]["name"] == "AI Governance"
            assert len(result.data["items"]) == 1
            assert "related_topics" in result.data

    async def test_get_author_items_empty_for_unknown_author(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("get_author_items", {"author_name": "Nobody"})
            assert result.data == []

    async def test_get_author_items_returns_items_by_author(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="By Jane",
            author="Jane Author",
        )
        async with Client(server) as client:
            result = await client.call_tool("get_author_items", {"author_name": "Jane Author"})
            assert len(result.data) == 1
            assert result.data[0]["title"] == "By Jane"

    async def test_get_topic_timeline_unknown_name_raises(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("get_topic_timeline", {"topic_name": "Nonexistent"})

    async def test_get_topic_timeline_returns_bucketed_counts(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
        )
        graph.enrich_item(item_id, [("weekly topic", 0.05)])
        async with Client(server) as client:
            result = await client.call_tool("get_topic_timeline", {"topic_name": "weekly topic"})
            assert len(result.data) == 1
            assert result.data[0]["count"] == 1
            assert "period" in result.data[0]

    async def test_get_feed_health_empty_on_fresh_instance(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("get_feed_health", {})
            assert result.data == {"inactive": [], "erroring": []}

    async def test_get_feed_health_splits_erroring_and_inactive(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(
            url="https://erroring.example.com/rss",
            title="Erroring",
            description="",
            site_url="",
        )
        graph.create_feed(
            url="https://stale.example.com/rss",
            title="Stale",
            description="",
            site_url="",
        )
        graph._execute(
            "MATCH (f:Feed {url: $url}) SET f.consecutive_errors = 11",
            {"url": "https://erroring.example.com/rss"},
        )
        old = datetime.now(UTC) - timedelta(days=31)
        graph._execute(
            "MATCH (f:Feed {url: $url}) SET f.subscribed_at = $old, f.last_fetched_at = NULL",
            {"url": "https://stale.example.com/rss", "old": old},
        )

        async with Client(server) as client:
            result = await client.call_tool("get_feed_health", {})
            erroring_urls = {f["url"] for f in result.data["erroring"]}
            inactive_urls = {f["url"] for f in result.data["inactive"]}
            assert erroring_urls == {"https://erroring.example.com/rss"}
            assert inactive_urls == {"https://stale.example.com/rss"}

    async def test_search_finds_matching_items(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="Machine learning breakthrough",
        )
        async with Client(server) as client:
            result = await client.call_tool("search", {"query": "machine learning"})
            assert len(result.data["items"]) == 1


class TestBoundsValidation:
    """Every MCP tool taking limit/offset must reject out-of-range values
    with a clean ToolError, matching the REST API's Query(ge=..., le=...)
    bounds — instead of leaking a raw Kuzu driver exception."""

    async def test_explore_topic_negative_limit_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
        )
        graph.enrich_item(item_id, [("AI Governance", 0.9)])
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(
                    "explore_topic", {"topic_name": "AI Governance", "limit": -5}
                )
            assert "limit" in str(exc_info.value)
            assert "Runtime exception" not in str(exc_info.value)

    async def test_list_authors_negative_limit_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("list_authors", {"limit": -1})
            assert "limit" in str(exc_info.value)
            assert "Runtime exception" not in str(exc_info.value)

    async def test_find_similar_items_negative_limit_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
        )
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("find_similar_items", {"item_id": item_id, "limit": -1})
            assert "limit" in str(exc_info.value)

    async def test_find_adjacent_to_starred_negative_limit_raises_clean_tool_error(
        self, mcp_server
    ):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("find_adjacent_to_starred", {"limit": -1})
            assert "limit" in str(exc_info.value)

    async def test_get_author_items_negative_limit_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("get_author_items", {"author_name": "Nobody", "limit": -1})
            assert "limit" in str(exc_info.value)

    async def test_search_negative_limit_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("search", {"query": "x", "limit": -1})
            assert "limit" in str(exc_info.value)

    async def test_list_topics_negative_offset_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("list_topics", {"offset": -1})
            assert "offset" in str(exc_info.value)

    async def test_get_topic_clusters_negative_limit_raises_clean_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("get_topic_clusters", {"limit": -1})
            assert "limit" in str(exc_info.value)

    async def test_list_topics_offset_beyond_200_is_not_rejected(self, mcp_server):
        """offset has no upper bound, matching REST's /topics route
        (Query(default=0, ge=0), no le=) — only limit is capped at 200."""
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("list_topics", {"offset": 401})
            assert result.data == []


class TestEnumValidationErrorsTranslated:
    """graph.get_topics(sort=...) and graph.get_topic_timeline(bucket=...)
    raise ValueError on a bad enum value; the MCP tools must translate that
    into a clean ToolError rather than letting it escape unhandled, matching
    get_items' existing decode_cursor/datetime.fromisoformat pattern."""

    async def test_list_topics_bad_sort_raises_tool_error_not_value_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="sort"):
                await client.call_tool("list_topics", {"sort": "bogus"})

    async def test_get_topic_timeline_bad_bucket_raises_tool_error_not_value_error(
        self, mcp_server
    ):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
        )
        graph.enrich_item(item_id, [("weekly topic", 0.05)])
        async with Client(server) as client:
            with pytest.raises(ToolError, match="bucket"):
                await client.call_tool(
                    "get_topic_timeline", {"topic_name": "weekly topic", "bucket": "fortnight"}
                )


class TestFindPathTool:
    async def test_find_path_between_related_items(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        graph.enrich_item(a, [("Shared", 0.9)])
        graph.enrich_item(b, [("Shared", 0.9)])
        async with Client(server) as client:
            result = await client.call_tool("find_path", {"from_id": a, "to_id": b})
            assert len(result.data["path"]) >= 2

    async def test_find_path_no_connection_returns_empty(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        async with Client(server) as client:
            result = await client.call_tool("find_path", {"from_id": a, "to_id": b})
            assert result.data["path"] == []

    async def test_find_path_rejects_zero_max_topic_hops(self, mcp_server):
        # FastMCP wraps ANY exception raised inside a tool as a ToolError at
        # the Client boundary, so pytest.raises(ToolError) alone would pass
        # identically whether we validate cleanly or let Kuzu's raw binder
        # exception leak through unhandled — assert on the message content
        # to prove it's *our* validation error, not a leaked driver error.
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("find_path", {"from_id": a, "to_id": b, "max_topic_hops": 0})
            assert "max_topic_hops" in str(exc_info.value)
            assert "Binder exception" not in str(exc_info.value)

    async def test_find_path_rejects_negative_max_topic_hops(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(
                    "find_path", {"from_id": a, "to_id": b, "max_topic_hops": -1}
                )
            assert "max_topic_hops" in str(exc_info.value)
            assert "Binder exception" not in str(exc_info.value)
