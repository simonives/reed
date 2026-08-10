# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

"""Thin stdio<->HTTP bridge for local MCP clients (Claude Desktop, Cursor).

Never opens a Kuzu Database() handle — Kuzu takes an OS-level file lock, so
a second process (this one) cannot open the same database file the main
`reed serve` process already holds open (verified empirically during M6
design). This process only speaks MCP-over-stdio to its parent and forwards
every call to the main process's /mcp HTTP endpoint over 127.0.0.1
(explicitly loopback, never whatever REED_HOST the public listener binds
to — this is same-container traffic and never leaves the host).
"""

from __future__ import annotations

from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy

from .config import get_settings


def build_bridge():  # type: ignore[no-untyped-def]
    settings = get_settings()
    transport = StreamableHttpTransport(
        f"http://127.0.0.1:{settings.port}/mcp",
        headers={"X-API-Key": settings.api_key},
    )
    return create_proxy(transport, name="Reed")


def main() -> None:
    proxy = build_bridge()
    proxy.run()


if __name__ == "__main__":
    main()
