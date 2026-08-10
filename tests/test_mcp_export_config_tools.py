# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from fastmcp import Client


class TestExportOpmlTool:
    async def test_returns_opml_string(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        async with Client(server) as client:
            result = await client.call_tool("export_opml", {})
            assert "<opml" in result.data["opml"]
            assert "https://f.example.com/rss" in result.data["opml"]


class TestTriggerRecomputeTool:
    async def test_returns_job_status(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("trigger_recompute", {})
            assert result.data["status"] == "queued"
            assert "job_id" in result.data
