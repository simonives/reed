# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from reed.config import get_settings

SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
      <title>First Post</title>
      <link>https://example.com/1</link>
      <guid>https://example.com/1</guid>
      <author>Jane Author</author>
      <description>Summary of the first post</description>
      <pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/2</link>
      <guid>https://example.com/2</guid>
    </item>
  </channel>
</rss>"""


def mock_http_response(content: bytes = SAMPLE_RSS, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.is_redirect = False  # safe_get returns non-redirects directly
    resp.raise_for_status = MagicMock()
    return resp


@contextmanager
def patched_feed_fetch(response=None, side_effect=None, module="reed.api.feeds"):
    """Patch the outbound HTTP fetch used by POST /feeds, /feeds/discover, and
    POST /import (pass module="reed.api.import_" for the latter).

    safe_get resolves the host before fetching, so the SSRF resolver is stubbed
    to keep these tests hermetic (no real DNS); the host-blocking behaviour is
    exercised separately in TestSSRFGuard.
    """
    mock_client = AsyncMock()
    if side_effect is not None:
        mock_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_client.get = AsyncMock(return_value=response or mock_http_response())
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    with (
        patch(f"{module}.http_client", return_value=cm),
        patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])),
    ):
        yield mock_client


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def reed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("REED_API_KEY", "test-key")
    monkeypatch.setenv("REED_DATA_PATH", str(tmp_path / "test.kuzu"))
    monkeypatch.setenv("REED_FRONTEND_PATH", "/nonexistent")
    get_settings.cache_clear()

    from reed.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture
def authed(reed_client):
    """TestClient with the API key header pre-set."""
    reed_client.headers.update({"X-API-Key": "test-key"})
    return reed_client


@pytest.fixture
def subscribed_feed(authed, reed_client):
    """Subscribe to a feed and ingest SAMPLE_RSS; returns the feed object."""
    from reed.poller import FeedPoller

    with patched_feed_fetch():
        r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})
    feed = r.json()["data"]

    poller = FeedPoller(reed_client.app.state.graph)
    poller._ingest_entries(feed["url"], SAMPLE_RSS, datetime.now(UTC))
    return feed
