# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from fastmcp import FastMCP

from .graph import GraphService

mcp: FastMCP = FastMCP("Reed")


def create_mcp_server(graph: GraphService) -> FastMCP:
    """Return the configured MCP server. Tools registered in M6."""
    _ = graph  # graph service injected here in M6
    return mcp
