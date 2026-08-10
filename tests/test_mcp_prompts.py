# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from fastmcp import Client


class TestTraversalPrompts:
    async def test_three_prompts_registered(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            prompts = await client.list_prompts()
            names = {p.name for p in prompts}
            assert {"deep_reading_session", "weekly_digest", "research_thread"} <= names
