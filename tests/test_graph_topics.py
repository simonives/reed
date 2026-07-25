# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


@pytest.fixture
def seeded(graph):
    """A graph with one feed and one item. Returns (graph, item_id)."""
    graph.create_feed(
        url="https://example.com/feed",
        title="Test Feed",
        description="",
        site_url="",
    )
    item_id = graph.create_item(
        feed_url="https://example.com/feed",
        guid="item-1",
        url="https://example.com/1",
        title="Machine learning advances in 2026",
        summary="Neural networks show remarkable promise in language tasks",
        content="",
        author="",
        word_count=8,
        published_at=None,
        fetched_at=datetime.now(UTC),
    )
    return graph, item_id


class TestUpsertTopic:
    def test_creates_topic_and_returns_id(self, graph):
        topic_id = graph._upsert_topic("machine learning")
        assert isinstance(topic_id, str)
        assert len(topic_id) == 36  # UUID

    def test_same_name_returns_same_id(self, graph):
        id1 = graph._upsert_topic("machine learning")
        id2 = graph._upsert_topic("machine learning")
        assert id1 == id2

    def test_increments_item_count_on_second_call(self, graph):
        graph._upsert_topic("machine learning")
        graph._upsert_topic("machine learning")
        topics, _ = graph.get_topics()
        assert topics[0]["item_count"] == 2

    def test_different_names_create_different_topics(self, graph):
        id1 = graph._upsert_topic("machine learning")
        id2 = graph._upsert_topic("neural networks")
        assert id1 != id2
        _, total = graph.get_topics()
        assert total == 2


class TestEnrichItem:
    def test_creates_about_edges(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("neural networks", 0.05), ("deep learning", 0.08)])
        topics = graph.get_item_topics(item_id)
        names = {t["name"] for t in topics}
        assert "neural networks" in names
        assert "deep learning" in names

    def test_idempotent_no_duplicate_edges(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        topics = graph.get_item_topics(item_id)
        assert len([t for t in topics if t["name"] == "neural networks"]) == 1

    def test_idempotent_item_count_does_not_drift(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        topics, _ = graph.get_topics()
        assert topics[0]["item_count"] == 1

    def test_empty_keywords_is_noop(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [])
        assert graph.get_item_topics(item_id) == []

    def test_topic_ids_are_uuids(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("machine learning", 0.03)])
        topics = graph.get_item_topics(item_id)
        assert len(topics[0]["id"]) == 36


class TestGetUnenrichedItems:
    def test_returns_items_with_no_about_edges(self, seeded):
        graph, item_id = seeded
        unenriched = graph.get_unenriched_items()
        assert any(r["id"] == item_id for r in unenriched)

    def test_excludes_enriched_items(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("test topic", 0.1)])
        unenriched = graph.get_unenriched_items()
        assert not any(r["id"] == item_id for r in unenriched)

    def test_returns_text_fields(self, seeded):
        graph, item_id = seeded
        unenriched = graph.get_unenriched_items()
        row = next(r for r in unenriched if r["id"] == item_id)
        assert "title" in row
        assert "summary" in row
        assert "content" in row


class TestGetTopics:
    def test_empty_when_no_topics(self, graph):
        results, total = graph.get_topics()
        assert results == []
        assert total == 0

    def test_pagination(self, graph):
        for name in ["topic a", "topic b", "topic c"]:
            graph._upsert_topic(name)
        results, total = graph.get_topics(limit=2, offset=0)
        assert total == 3
        assert len(results) == 2

    def test_sorted_by_item_count_desc(self, graph):
        graph._upsert_topic("popular")
        graph._upsert_topic("popular")
        graph._upsert_topic("rare")
        results, _ = graph.get_topics()
        assert results[0]["name"] == "popular"

    def test_response_shape(self, graph):
        graph._upsert_topic("machine learning")
        results, _ = graph.get_topics()
        assert "id" in results[0]
        assert "name" in results[0]
        assert "item_count" in results[0]


class TestGetTopic:
    def test_returns_none_for_unknown_id(self, graph):
        result = graph.get_topic("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_returns_topic_with_items(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        topics, _ = graph.get_topics()
        topic = graph.get_topic(topics[0]["id"])
        assert topic is not None
        assert topic["name"] == "neural networks"
        assert len(topic["items"]) == 1
        assert topic["items"][0]["id"] == item_id

    def test_items_sorted_by_score_asc(self, graph):
        graph.create_feed(url="https://f.com/feed", title="F", description="", site_url="")
        now = datetime.now(UTC)
        id_high = graph.create_item(
            feed_url="https://f.com/feed",
            guid="g1",
            url="https://f.com/1",
            title="A",
            summary="",
            content="",
            author="",
            word_count=1,
            published_at=None,
            fetched_at=now,
        )
        id_low = graph.create_item(
            feed_url="https://f.com/feed",
            guid="g2",
            url="https://f.com/2",
            title="B",
            summary="",
            content="",
            author="",
            word_count=1,
            published_at=None,
            fetched_at=now,
        )
        graph.enrich_item(id_high, [("topic x", 0.9)])
        graph.enrich_item(id_low, [("topic x", 0.01)])
        topics, _ = graph.get_topics()
        topic = graph.get_topic(topics[0]["id"])
        # get_topic's items don't expose score, but order should be ascending —
        # verify the lower-score item appears first by checking item order.
        assert topic["items"][0]["id"] == id_low


class TestGetItemTopics:
    def test_returns_topics_sorted_by_score_asc(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("high confidence", 0.01), ("low confidence", 0.9)])
        topics = graph.get_item_topics(item_id)
        scores = [t["score"] for t in topics]
        assert scores == sorted(scores)

    def test_returns_empty_for_unenriched_item(self, seeded):
        graph, item_id = seeded
        assert graph.get_item_topics(item_id) == []

    def test_response_shape(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("machine learning", 0.03)])
        topics = graph.get_item_topics(item_id)
        t = topics[0]
        assert "id" in t
        assert "name" in t
        assert "score" in t
        assert t["name"] == "machine learning"
        assert isinstance(t["score"], float)


class TestEnrichedAt:
    def test_schema_v6_has_enriched_at(self, graph):
        # enriched_at should exist and default to None
        item_id = graph.create_item(
            feed_url="https://example.com/feed",
            guid="test-ea-1",
            url="https://example.com/1",
            title="Test",
            summary="",
            content="",
            author="",
            word_count=0,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        item = graph.get_item(item_id)
        assert "enriched_at" in item
        assert item["enriched_at"] is None

    def test_enrich_item_sets_enriched_at(self, graph):
        feed_url = "https://example.com/feed"
        item_id = graph.create_item(
            feed_url=feed_url,
            guid="test-ea-2",
            url="https://example.com/2",
            title="NLP",
            summary="machine learning",
            content="",
            author="",
            word_count=2,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        graph.enrich_item(item_id, [("machine learning", 0.1)])
        item = graph.get_item(item_id)
        assert item["enriched_at"] is not None

    def test_enrich_item_empty_keywords_sets_enriched_at(self, graph):
        feed_url = "https://example.com/feed"
        item_id = graph.create_item(
            feed_url=feed_url,
            guid="test-ea-3",
            url="https://example.com/3",
            title=".",
            summary="",
            content="",
            author="",
            word_count=0,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        graph.enrich_item(item_id, [])
        item = graph.get_item(item_id)
        assert item["enriched_at"] is not None

    def test_get_unenriched_excludes_enriched_items(self, graph):
        feed_url = "https://example.com/feed"
        item_id = graph.create_item(
            feed_url=feed_url,
            guid="test-ea-4",
            url="https://example.com/4",
            title="AI",
            summary="neural networks",
            content="",
            author="",
            word_count=2,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        assert any(r["id"] == item_id for r in graph.get_unenriched_items())
        graph.enrich_item(item_id, [("neural networks", 0.1)])
        assert not any(r["id"] == item_id for r in graph.get_unenriched_items())

    def test_get_unenriched_includes_zero_keyword_before_enrich(self, graph):
        feed_url = "https://example.com/feed"
        item_id = graph.create_item(
            feed_url=feed_url,
            guid="test-ea-5",
            url="https://example.com/5",
            title=".",
            summary="",
            content="",
            author="",
            word_count=0,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        assert any(r["id"] == item_id for r in graph.get_unenriched_items())
        graph.enrich_item(item_id, [])
        assert not any(r["id"] == item_id for r in graph.get_unenriched_items())
