# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
    </item>
  </channel>
</rss>"""


def _mock_http_response(content: bytes = SAMPLE_RSS, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


class TestAuth:
    def test_no_key_returns_403(self, reed_client):
        r = reed_client.get("/api/v1/feeds")
        assert r.status_code == 403

    def test_wrong_key_returns_403(self, reed_client):
        r = reed_client.get("/api/v1/feeds", headers={"X-API-Key": "wrong"})
        assert r.status_code == 403

    def test_correct_key_passes(self, authed):
        r = authed.get("/api/v1/feeds")
        assert r.status_code == 200


class TestSubscribe:
    def test_subscribe_returns_201(self, authed):
        with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_http_response())

            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})

        assert r.status_code == 201
        data = r.json()
        assert data["url"] == "https://example.com/feed.rss"
        assert data["title"] == "Test Feed"
        assert data["site_url"] == "https://example.com"

    def test_subscribe_duplicate_returns_409(self, authed):
        with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_http_response())

            authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})
            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})

        assert r.status_code == 409

    def test_unreachable_feed_returns_422(self, authed):
        import httpx as _httpx

        with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("timeout"))

            r = authed.post("/api/v1/feeds", json={"url": "https://unreachable.example/feed"})

        assert r.status_code == 422


class TestListFeeds:
    def test_empty_list(self, authed):
        r = authed.get("/api/v1/feeds")
        assert r.status_code == 200
        assert r.json() == []

    def test_shows_subscribed_feed(self, authed):
        with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_http_response())

            authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})

        r = authed.get("/api/v1/feeds")
        assert r.status_code == 200
        feeds = r.json()
        assert len(feeds) == 1
        assert feeds[0]["title"] == "Test Feed"


class TestDeleteFeed:
    def test_delete_existing_feed(self, authed):
        with patch("reed.api.feeds.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_http_response())

            authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})

        r = authed.delete("/api/v1/feeds/https://example.com/feed.rss")
        assert r.status_code == 204

        feeds = authed.get("/api/v1/feeds").json()
        assert feeds == []

    def test_delete_nonexistent_returns_404(self, authed):
        r = authed.delete("/api/v1/feeds/https://example.com/nonexistent")
        assert r.status_code == 404
