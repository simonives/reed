# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService
from reed.poller import FeedPoller
from reed.topics import extract_keywords, item_text, make_extractor

TECH_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
  <title>Tech Feed</title>
  <item>
    <title>Machine learning and neural networks advance in 2026</title>
    <link>https://tech.example.com/1</link>
    <guid>https://tech.example.com/1</guid>
    <description>Deep learning transformer models are reshaping natural language
    processing</description>
  </item>
</channel></rss>"""


@pytest.fixture
def enriched(authed, reed_client):
    """authed client with a subscribed feed, ingested items, and topic enrichment applied."""
    from .conftest import mock_http_response, patched_feed_fetch

    with patched_feed_fetch(response=mock_http_response(TECH_RSS)):
        authed.post("/api/v1/feeds", json={"url": "https://tech.example.com/feed.rss"})

    graph: GraphService = reed_client.app.state.graph
    poller = FeedPoller(graph)
    poller._ingest_entries("https://tech.example.com/feed.rss", TECH_RSS, datetime.now(UTC))

    extractor = make_extractor()
    for item in graph.get_unenriched_items():
        text = item_text(
            item.get("title") or "",
            item.get("summary") or "",
            item.get("content") or "",
        )
        graph.enrich_item(item["id"], extract_keywords(text, extractor))

    return authed


class TestListTopics:
    def test_empty_on_fresh_instance(self, authed):
        r = authed.get("/api/v1/topics")
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []

    def test_returns_topics_after_enrichment(self, enriched):
        r = enriched.get("/api/v1/topics")
        assert r.status_code == 200
        topics = r.json()["data"]
        assert len(topics) > 0

    def test_topic_shape(self, enriched):
        topics = enriched.get("/api/v1/topics").json()["data"]
        t = topics[0]
        assert "id" in t
        assert "name" in t
        assert "item_count" in t
        assert isinstance(t["item_count"], int)

    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/topics")
        assert r.status_code == 401

    def test_meta_present(self, authed):
        r = authed.get("/api/v1/topics")
        assert "meta" in r.json()
        assert "total" in r.json()["meta"]


class TestGetTopic:
    def test_returns_topic_detail(self, enriched):
        topic_id = enriched.get("/api/v1/topics").json()["data"][0]["id"]
        r = enriched.get(f"/api/v1/topics/{topic_id}")
        assert r.status_code == 200
        topic = r.json()["data"]
        assert topic["id"] == topic_id
        assert "name" in topic
        assert "items" in topic
        assert isinstance(topic["items"], list)

    def test_topic_items_have_expected_shape(self, enriched):
        topic_id = enriched.get("/api/v1/topics").json()["data"][0]["id"]
        topic = enriched.get(f"/api/v1/topics/{topic_id}").json()["data"]
        assert topic["items"], "expected at least one item in topic detail"
        item = topic["items"][0]
        assert "id" in item
        assert "title" in item
        assert "url" in item

    def test_returns_404_for_unknown(self, authed):
        r = authed.get("/api/v1/topics/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/topics/some-id")
        assert r.status_code == 401


class TestItemDetailTopics:
    def test_item_detail_includes_topics_field(self, enriched):
        items = enriched.get("/api/v1/items").json()["data"]
        item_id = items[0]["id"]
        r = enriched.get(f"/api/v1/items/{item_id}")
        assert r.status_code == 200
        detail = r.json()["data"]
        assert "topics" in detail
        assert isinstance(detail["topics"], list)

    def test_item_detail_topics_have_expected_shape(self, enriched):
        items = enriched.get("/api/v1/items").json()["data"]
        item_id = items[0]["id"]
        detail = enriched.get(f"/api/v1/items/{item_id}").json()["data"]
        assert detail["topics"], "expected at least one topic in enriched item detail"
        t = detail["topics"][0]
        assert "id" in t
        assert "name" in t
        assert "score" in t
        assert isinstance(t["score"], float)

    def test_item_list_topics_is_empty_list(self, enriched):
        items = enriched.get("/api/v1/items").json()["data"]
        assert "topics" in items[0]
        assert items[0]["topics"] == []
