# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import json

from fastmcp import Client

from .conftest import create_test_item


class TestDiscoveryTools:
    async def test_list_topics_empty_on_fresh_instance(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("list_topics", {})
            assert result.data == []

    async def test_list_tags_empty_on_fresh_instance(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("list_tags", {})
            assert result.data == []

    async def test_list_authors_empty_on_fresh_instance(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("list_authors", {})
            assert result.data == []


class TestOverviewResource:
    async def test_overview_resource_returns_counts(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        async with Client(server) as client:
            result = await client.read_resource("reed://graph/overview")
            content = result[0]
            assert "feed_count" in content.text or "feed_count" in str(content)

    async def test_overview_resource_is_valid_json_with_author_last_seen(self, mcp_server):
        """Regression test for a real TypeError: list_authors' last_seen field
        is a datetime, and the overview resource serializes with json.dumps
        directly (not through FastMCP's own encoder), so a non-string
        datetime there breaks serialization. Guards both the isoformat fix
        in GraphService.list_authors and the default=str backstop in the
        resource itself."""
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(
            graph,
            "https://f.example.com/rss",
            "g1",
            "https://f.example.com/1",
            "One",
            author="Alice",
        )
        async with Client(server) as client:
            result = await client.read_resource("reed://graph/overview")
            content = result[0]
            data = json.loads(content.text)
            assert data["top_authors"][0]["author"] == "Alice"
            assert data["top_authors"][0]["last_seen"] is not None


class TestListTopicsCentrality:
    async def test_sort_centrality_accepted(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        graph.enrich_item(item, [("Topic", 0.9)])
        async with Client(server) as client:
            result = await client.call_tool("list_topics", {"sort": "centrality"})
            assert len(result.data) == 1


class TestGetTopicClustersTool:
    async def test_returns_clusters(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph, "https://f.example.com/rss", "a", "https://f.example.com/a", "A"
        )
        b = create_test_item(
            graph, "https://f.example.com/rss", "b", "https://f.example.com/b", "B"
        )
        graph.enrich_item(a, [("T1", 0.9), ("T2", 0.8)])
        graph.enrich_item(b, [("T1", 0.9), ("T2", 0.8)])
        graph.recompute_derived_edges(window_days=365, score_threshold=0.0)
        async with Client(server) as client:
            result = await client.call_tool("get_topic_clusters", {})
            assert len(result.data) >= 1
