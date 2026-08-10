# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from fastmcp import Client

from tests.conftest import create_test_item


class TestCaptureExternalFinding:
    async def test_appends_finding_with_url_and_summary(self, mcp_server):
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
            await client.call_tool(
                "capture_external_finding",
                {
                    "item_id": item_id,
                    "url": "https://example.gov/reg-123",
                    "title": "New regulation text",
                    "summary": "Full text of the regulation referenced in this article.",
                },
            )
        note = graph.get_note(item_id)
        assert "https://example.gov/reg-123" in note["body"]
        assert "New regulation text" in note["body"]

    async def test_finding_is_searchable_afterwards(self, mcp_server):
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
            await client.call_tool(
                "capture_external_finding",
                {
                    "item_id": item_id,
                    "url": "https://example.gov/reg-123",
                    "title": "Unique Regulation Marker",
                    "summary": "Details.",
                },
            )
            result = await client.call_tool("search", {"query": "Unique Regulation Marker"})
            assert len(result.data["items"]) == 1


class TestBuildResearchBrief:
    async def test_returns_item_context_packet(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
            author="Alice",
        )
        graph.enrich_item(item_id, [("AI Governance", 0.9)])
        async with Client(server) as client:
            result = await client.call_tool("build_research_brief", {"item_id": item_id})
            assert result.data["item"]["id"] == item_id
            assert "topics" in result.data
            assert "similar_items" in result.data
            assert "same_author_items" in result.data
