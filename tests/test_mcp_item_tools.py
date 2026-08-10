# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import create_test_item


class TestItemTools:
    async def test_get_items_returns_paginated_summaries(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="One",
        )
        async with Client(server) as client:
            result = await client.call_tool("get_items", {"limit": 10})
            assert len(result.data["items"]) == 1
            assert "next_cursor" in result.data

    async def test_get_item_includes_similar_items(self, mcp_server):
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
            result = await client.call_tool("get_item", {"item_id": item_id})
            assert result.data["id"] == item_id
            assert "similar_items" in result.data

    async def test_get_item_unknown_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("get_item", {"item_id": "nonexistent"})

    async def test_get_items_malformed_cursor_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Invalid cursor"):
                await client.call_tool("get_items", {"cursor": "not-a-valid-cursor"})

    async def test_get_items_invalid_since_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Invalid since"):
                await client.call_tool("get_items", {"since": "not-a-valid-date"})

    async def test_mark_read_invalid_before_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Invalid before"):
                await client.call_tool("mark_read", {"before": "not-a-valid-date"})

    async def test_mark_read_with_item_ids(self, mcp_server):
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
            await client.call_tool("mark_read", {"item_ids": [item_id]})
        assert graph.get_item(item_id)["read"] is True

    async def test_mark_read_with_no_args_marks_everything(self, mcp_server):
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
            await client.call_tool("mark_read", {})
        assert graph.get_item(item_id)["read"] is True

    async def test_mark_starred(self, mcp_server):
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
            await client.call_tool("mark_starred", {"item_id": item_id, "starred": True})
        assert graph.get_item(item_id)["starred"] is True

    async def test_tag_item_add_and_remove(self, mcp_server):
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
                "tag_item", {"item_id": item_id, "tag": "reading", "action": "add"}
            )
            assert graph.get_item(item_id)["tags"] == ["reading"]
            await client.call_tool(
                "tag_item", {"item_id": item_id, "tag": "reading", "action": "remove"}
            )
            assert graph.get_item(item_id)["tags"] == []

    async def test_annotate_item_creates_and_clears_note(self, mcp_server):
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
            await client.call_tool("annotate_item", {"item_id": item_id, "content": "My note."})
            assert graph.get_note(item_id)["body"] == "My note."
            await client.call_tool("annotate_item", {"item_id": item_id, "content": None})
            assert graph.get_note(item_id) is None

    async def test_mark_starred_unknown_item_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("mark_starred", {"item_id": "nonexistent", "starred": True})

    async def test_tag_item_add_unknown_item_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool(
                    "tag_item", {"item_id": "nonexistent", "tag": "reading", "action": "add"}
                )

    async def test_annotate_item_unknown_item_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool(
                    "annotate_item", {"item_id": "nonexistent", "content": "note"}
                )

    async def test_get_items_filters_by_topic(self, mcp_server):
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
            result = await client.call_tool("get_items", {"topic": "AI Governance"})
            assert len(result.data["items"]) == 1
            assert result.data["items"][0]["id"] == item_id

    async def test_get_items_unknown_topic_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Topic not found"):
                await client.call_tool("get_items", {"topic": "Nonexistent Topic"})

    async def test_get_items_limit_zero_raises_clean_tool_error(self, mcp_server):
        """limit=0 previously raised a raw IndexError from
        encode_cursor(items[-1]) when len(items) == limit == 0, instead of a
        clean ToolError."""
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="limit"):
                await client.call_tool("get_items", {"limit": 0})

    async def test_get_items_negative_limit_raises_clean_tool_error(self, mcp_server):
        """limit=-1 previously leaked a raw Kuzu driver exception ('Runtime
        exception: The number of rows to skip/limit must be a non-negative
        integer.') instead of a clean ToolError."""
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("get_items", {"limit": -1})
            assert "limit" in str(exc_info.value)
            assert "Runtime exception" not in str(exc_info.value)

    async def test_mark_read_unknown_feed_id_raises_tool_error(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Feed not found"):
                await client.call_tool(
                    "mark_read", {"item_ids": ["whatever"], "feed_id": "nonexistent"}
                )

    async def test_annotate_item_clear_note_unknown_item_raises_tool_error(self, mcp_server):
        """annotate_item(content=None) previously skipped the existence check
        entirely on the clear-note path, silently succeeding on an unknown
        item_id instead of raising ToolError like every other not-found path
        across the MCP surface."""
        server, graph, poller = mcp_server
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("annotate_item", {"item_id": "nonexistent", "content": None})
