# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from reed.config import get_settings


@pytest.fixture
def mcp_client(tmp_path, monkeypatch):
    monkeypatch.setenv("REED_API_KEY", "test-key")
    monkeypatch.setenv("REED_DATA_PATH", str(tmp_path / "test.kuzu"))
    monkeypatch.setenv("REED_FRONTEND_PATH", "/nonexistent")
    get_settings.cache_clear()

    from reed.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


class TestMcpAuth:
    def test_missing_api_key_rejected(self, mcp_client):
        r = mcp_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert r.status_code == 401

    def test_wrong_api_key_rejected(self, mcp_client):
        r = mcp_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-API-Key": "wrong",
            },
        )
        assert r.status_code == 401

    def test_correct_api_key_accepted(self, mcp_client):
        r = mcp_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-API-Key": "test-key",
            },
        )
        assert r.status_code != 401


@pytest.fixture
def mcp_client_with_frontend(tmp_path, monkeypatch):
    """Like mcp_client, but with a real REED_FRONTEND_PATH so create_app()
    mounts the frontend catch-all StaticFiles("/") — reproducing the
    conditions under which a Mount("/mcp", ...) gets shadowed by it."""
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html>frontend</html>")

    monkeypatch.setenv("REED_API_KEY", "test-key")
    monkeypatch.setenv("REED_DATA_PATH", str(tmp_path / "test.kuzu"))
    monkeypatch.setenv("REED_FRONTEND_PATH", str(frontend_dir))
    get_settings.cache_clear()

    from reed.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


class TestMcpMountWithFrontendPresent:
    """Regression test for a routing bug found during Task 1: Starlette's
    Mount always requires a trailing slash to match its own bare prefix
    (Mount("/mcp", ...) only ever matches "/mcp/...", never "/mcp" itself),
    so the frontend's catch-all StaticFiles Mount("/") — which fully
    matches every path unconditionally — shadows /mcp entirely whenever a
    real frontend directory is mounted. The bare "/mcp" request never
    reaches the MCP app; it gets a 405 from StaticFiles (GET/HEAD only)
    instead. Fixed by registering /mcp as a Route (exact-path match, no
    trailing-slash requirement) rather than a Mount. Every other test in
    this file sets REED_FRONTEND_PATH=/nonexistent, so none of them
    exercise this — this test is the one that does.
    """

    def test_mcp_reachable_with_frontend_mounted(self, mcp_client_with_frontend):
        r = mcp_client_with_frontend.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-API-Key": "test-key",
            },
        )
        assert r.status_code not in (404, 405)

    def test_frontend_still_served(self, mcp_client_with_frontend):
        r = mcp_client_with_frontend.get("/")
        assert r.status_code == 200
        assert "frontend" in r.text


class TestGetConfigTool:
    async def test_returns_effective_config(self, mcp_server):
        server, graph, poller = mcp_server
        async with Client(server) as client:
            result = await client.call_tool("get_config", {})
            assert "default_poll_interval_minutes" in result.data
