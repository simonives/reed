# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from reed.poller import FeedPoller

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
      <pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/2</link>
      <guid>https://example.com/2</guid>
    </item>
  </channel>
</rss>"""


def _mock_http(content: bytes = SAMPLE_RSS):
    resp = MagicMock()
    resp.status_code = 200
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


def _subscribe_and_poll(authed, graph_service, url="https://example.com/feed.rss"):
    """Subscribe to a feed and directly ingest entries via GraphService."""
    with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_http())
        authed.post("/api/v1/feeds", json={"url": url})

    # Ingest entries directly without going through the async poller
    poller = FeedPoller(graph_service)
    now = datetime.now(UTC)
    poller._ingest_entries(url, SAMPLE_RSS, now)
    return url


class TestListItems:
    def test_empty_when_no_feeds(self, authed):
        r = authed.get("/api/v1/items")
        assert r.status_code == 200
        assert r.json() == []

    def test_items_appear_after_ingest(self, authed, reed_client):
        graph = reed_client.app.state.graph
        _subscribe_and_poll(authed, graph)

        r = authed.get("/api/v1/items")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 2
        titles = {i["title"] for i in items}
        assert titles == {"First Post", "Second Post"}

    def test_filter_by_feed_url(self, authed, reed_client):
        graph = reed_client.app.state.graph
        feed_url = _subscribe_and_poll(authed, graph)

        r = authed.get(f"/api/v1/items?feed_url={feed_url}")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_filter_by_unknown_feed_returns_empty(self, authed):
        r = authed.get("/api/v1/items?feed_url=https://unknown.example/feed")
        assert r.status_code == 200
        assert r.json() == []

    def test_items_have_required_fields(self, authed, reed_client):
        graph = reed_client.app.state.graph
        _subscribe_and_poll(authed, graph)

        items = authed.get("/api/v1/items").json()
        for item in items:
            assert "guid" in item
            assert "url" in item
            assert "title" in item
            assert "read" in item
            assert "starred" in item
            assert item["read"] is False
            assert item["starred"] is False

    def test_pagination(self, authed, reed_client):
        graph = reed_client.app.state.graph
        _subscribe_and_poll(authed, graph)

        first = authed.get("/api/v1/items?limit=1&offset=0").json()
        second = authed.get("/api/v1/items?limit=1&offset=1").json()
        assert len(first) == 1
        assert len(second) == 1
        assert first[0]["guid"] != second[0]["guid"]

    def test_negative_limit_returns_422(self, authed):
        r = authed.get("/api/v1/items?limit=-1")
        assert r.status_code == 422

    def test_negative_offset_returns_422(self, authed):
        r = authed.get("/api/v1/items?offset=-1")
        assert r.status_code == 422

    def test_resubscribe_reattaches_items(self, authed, reed_client):
        """Items orphaned by delete_feed must reappear after resubscription."""
        graph = reed_client.app.state.graph
        feed_url = _subscribe_and_poll(authed, graph)

        authed.delete(f"/api/v1/feeds/{feed_url}")
        assert authed.get("/api/v1/items").json() == []

        # Resubscribe and re-ingest the same guids
        with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_http())
            authed.post("/api/v1/feeds", json={"url": feed_url})

        poller = FeedPoller(graph)
        poller._ingest_entries(feed_url, SAMPLE_RSS, datetime.now(UTC))

        items = authed.get("/api/v1/items").json()
        assert len(items) == 2
