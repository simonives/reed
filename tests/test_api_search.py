# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.poller import FeedPoller


CONTENT_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
      <title>AI Governance in HR</title>
      <link>https://example.com/1</link>
      <guid>https://example.com/1</guid>
      <author>Jane Smith</author>
      <description>Accountability frameworks for AI in enterprise HR systems.</description>
      <pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Supply Chain Optimisation</title>
      <link>https://example.com/2</link>
      <guid>https://example.com/2</guid>
      <description>Reducing costs through smarter procurement decisions.</description>
      <pubDate>Tue, 02 Jan 2026 12:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def search_feed(authed, reed_client):
    from .conftest import patched_feed_fetch, mock_http_response
    with patched_feed_fetch(response=mock_http_response(CONTENT_RSS)):
        r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})
    feed = r.json()["data"]
    poller = FeedPoller(reed_client.app.state.graph)
    poller._ingest_entries(feed["url"], CONTENT_RSS, datetime.now(UTC))
    return feed


class TestSearchEndpoint:
    def test_missing_q_returns_400(self, authed):
        r = authed.get("/api/v1/search")
        assert r.status_code == 400

    def test_empty_q_returns_400(self, authed):
        r = authed.get("/api/v1/search?q=")
        assert r.status_code == 400

    def test_whitespace_only_q_returns_400(self, authed):
        r = authed.get("/api/v1/search?q=   ")
        assert r.status_code == 400

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/search?q=governance")
        assert r.status_code == 401

    def test_valid_query_returns_envelope(self, authed, search_feed):
        r = authed.get("/api/v1/search?q=governance")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "meta" in body
        assert isinstance(body["data"], list)
        meta = body["meta"]
        assert "total" in meta
        assert "q" in meta
        assert meta["q"] == "governance"
        assert "limit" in meta
        assert "offset" in meta
        assert "has_more" in meta

    def test_matching_items_returned(self, authed, search_feed):
        r = authed.get("/api/v1/search?q=governance")
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["total"] >= 1
        assert len(body["data"]) >= 1

    def test_result_shape(self, authed, search_feed):
        r = authed.get("/api/v1/search?q=governance")
        assert r.status_code == 200
        item = r.json()["data"][0]
        assert "id" in item
        assert "title" in item
        assert "url" in item
        assert "read" in item
        assert "starred" in item
        assert "score" in item
        assert isinstance(item["score"], float)
        assert "match_source" in item
        assert isinstance(item["match_source"], list)
        assert "excerpt" in item
        assert "note_excerpt" in item
        assert "feed_title" in item
        assert isinstance(item.get("feed"), dict)
        assert "id" in item["feed"]
        assert "title" in item["feed"]

    def test_nonmatching_query_returns_empty(self, authed, search_feed):
        r = authed.get("/api/v1/search?q=zzznomatch")
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["total"] == 0
        assert body["data"] == []

    def test_limit_param(self, authed, search_feed):
        r = authed.get("/api/v1/search?q=governance&limit=1")
        assert r.status_code == 200
        assert len(r.json()["data"]) <= 1

    def test_limit_above_100_returns_400(self, authed):
        r = authed.get("/api/v1/search?q=governance&limit=200")
        assert r.status_code == 400

    def test_unread_filter(self, authed, search_feed):
        r_all = authed.get("/api/v1/search?q=governance")
        r_unread = authed.get("/api/v1/search?q=governance&unread=true")
        assert r_all.status_code == 200
        assert r_unread.status_code == 200
        # Unread count cannot exceed total
        assert r_unread.json()["meta"]["total"] <= r_all.json()["meta"]["total"]
