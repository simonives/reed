# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from reed.mcp import build_bridge


class TestBuildBridge:
    def test_targets_loopback_not_public_bind(self, monkeypatch):
        monkeypatch.setenv("REED_API_KEY", "bridge-key")
        monkeypatch.setenv("REED_PORT", "9000")
        proxy = build_bridge()
        # FastMCPProxy has no direct attribute exposing its transport; it
        # stores a `client_factory` callable that builds a fresh Client per
        # call, and that Client's `.transport` is the exact ClientTransport
        # instance we constructed in build_bridge() (verified via direct
        # introspection of the installed fastmcp==3.4.4 package — there is
        # no `_backend` attribute on FastMCPProxy).
        transport = proxy.client_factory().transport
        assert "127.0.0.1:9000" in str(transport)

    def test_forwards_api_key_as_header(self, monkeypatch):
        monkeypatch.setenv("REED_API_KEY", "bridge-key")
        proxy = build_bridge()
        transport = proxy.client_factory().transport
        assert transport.headers.get("X-API-Key") == "bridge-key"
