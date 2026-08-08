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

    def test_returns_topic_without_items_key(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        topics, _ = graph.get_topics()
        topic = graph.get_topic(topics[0]["id"])
        assert topic is not None
        assert topic["name"] == "neural networks"
        assert "items" not in topic

    def test_related_is_empty_list_when_no_related_edges(self, seeded):
        graph, item_id = seeded
        graph.enrich_item(item_id, [("neural networks", 0.05)])
        topics, _ = graph.get_topics()
        topic = graph.get_topic(topics[0]["id"])
        assert topic["related"] == []


class TestGetRelatedTopics:
    def test_returns_empty_for_topic_with_no_relations(self, graph):
        topic_id = graph._upsert_topic("solo topic")
        assert graph.get_related_topics(topic_id) == []

    def test_returns_related_topics_weight_desc(self, graph):
        t1 = graph._upsert_topic("topic one")
        t2 = graph._upsert_topic("topic two")
        t3 = graph._upsert_topic("topic three")
        now = datetime.now(UTC)
        graph._execute(
            "MATCH (a:Topic {id: $t1}), (b:Topic {id: $t2}) "
            "CREATE (a)-[:RELATED_TO {weight: 0.2, computed_at: $now}]->(b)",
            {"t1": t1, "t2": t2, "now": now},
        )
        graph._execute(
            "MATCH (a:Topic {id: $t1}), (b:Topic {id: $t3}) "
            "CREATE (a)-[:RELATED_TO {weight: 0.9, computed_at: $now}]->(b)",
            {"t1": t1, "t3": t3, "now": now},
        )
        related = graph.get_related_topics(t1)
        assert [r["id"] for r in related] == [t3, t2]
        assert related[0]["weight"] == 0.9

    def test_matches_either_direction(self, graph):
        t1 = graph._upsert_topic("alpha")
        t2 = graph._upsert_topic("beta")
        now = datetime.now(UTC)
        graph._execute(
            "MATCH (a:Topic {id: $t1}), (b:Topic {id: $t2}) "
            "CREATE (a)-[:RELATED_TO {weight: 0.5, computed_at: $now}]->(b)",
            {"t1": t1, "t2": t2, "now": now},
        )
        assert [r["id"] for r in graph.get_related_topics(t2)] == [t1]

    def test_response_shape(self, graph):
        t1 = graph._upsert_topic("alpha")
        t2 = graph._upsert_topic("beta")
        now = datetime.now(UTC)
        graph._execute(
            "MATCH (a:Topic {id: $t1}), (b:Topic {id: $t2}) "
            "CREATE (a)-[:RELATED_TO {weight: 0.5, computed_at: $now}]->(b)",
            {"t1": t1, "t2": t2, "now": now},
        )
        r = graph.get_related_topics(t1)[0]
        assert "id" in r
        assert "name" in r
        assert "weight" in r

    def test_equal_weight_ties_broken_by_id_for_deterministic_order(self, graph):
        """Adversarial review finding: ORDER BY weight alone is non-deterministic
        for tied weights. A tie-breaker on id makes repeated queries stable."""
        t1 = graph._upsert_topic("hub")
        t2 = graph._upsert_topic("aaa-tied")
        t3 = graph._upsert_topic("zzz-tied")
        now = datetime.now(UTC)
        for other in (t2, t3):
            graph._execute(
                "MATCH (a:Topic {id: $t1}), (b:Topic {id: $other}) "
                "CREATE (a)-[:RELATED_TO {weight: 0.5, computed_at: $now}]->(b)",
                {"t1": t1, "other": other, "now": now},
            )
        related = graph.get_related_topics(t1)
        assert [r["id"] for r in related] == sorted([t2, t3])


class TestTopicExists:
    def test_true_for_existing_topic(self, graph):
        topic_id = graph._upsert_topic("real topic")
        assert graph.topic_exists(topic_id) is True

    def test_false_for_unknown_id(self, graph):
        assert graph.topic_exists("00000000-0000-0000-0000-000000000000") is False


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


class TestGetTopicItems:
    def test_returns_items_about_topic(self, graph):
        graph.create_feed(url="https://f.com/feed", title="F", description="", site_url="")
        now = datetime.now(UTC)
        item_id = graph.create_item(
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
        graph.enrich_item(item_id, [("topic x", 0.5)])
        topics, _ = graph.get_topics()
        items = graph.get_topic_items(topics[0]["id"])
        assert len(items) == 1
        assert items[0]["id"] == item_id

    def test_excludes_items_not_about_topic(self, graph):
        graph.create_feed(url="https://f.com/feed", title="F", description="", site_url="")
        now = datetime.now(UTC)
        item_a = graph.create_item(
            feed_url="https://f.com/feed",
            guid="ga",
            url="https://f.com/a",
            title="A",
            summary="",
            content="",
            author="",
            word_count=1,
            published_at=None,
            fetched_at=now,
        )
        item_b = graph.create_item(
            feed_url="https://f.com/feed",
            guid="gb",
            url="https://f.com/b",
            title="B",
            summary="",
            content="",
            author="",
            word_count=1,
            published_at=None,
            fetched_at=now,
        )
        graph.enrich_item(item_a, [("topic x", 0.5)])
        graph.enrich_item(item_b, [("topic y", 0.5)])
        topics, _ = graph.get_topics()
        topic_x_id = next(t["id"] for t in topics if t["name"] == "topic x")
        items = graph.get_topic_items(topic_x_id)
        assert [i["id"] for i in items] == [item_a]

    def test_empty_for_topic_with_no_items(self, graph):
        topic_id = graph._upsert_topic("lonely topic")
        assert graph.get_topic_items(topic_id) == []

    def test_cursor_pagination_no_overlap_or_gaps(self, graph):
        graph.create_feed(url="https://f.com/feed", title="F", description="", site_url="")
        now = datetime.now(UTC)
        ids = []
        for i in range(5):
            item_id = graph.create_item(
                feed_url="https://f.com/feed",
                guid=f"g{i}",
                url=f"https://f.com/{i}",
                title=f"T{i}",
                summary="",
                content="",
                author="",
                word_count=1,
                published_at=None,
                fetched_at=now,
            )
            graph.enrich_item(item_id, [("shared topic", 0.5)])
            ids.append(item_id)
        topics, _ = graph.get_topics()
        topic_id = topics[0]["id"]

        page1 = graph.get_topic_items(topic_id, limit=2)
        assert len(page1) == 2
        last = page1[-1]
        page2 = graph.get_topic_items(
            topic_id,
            cursor_ts=last.get("published_at") or last.get("fetched_at"),
            cursor_guid=last["guid"],
            limit=2,
        )
        assert len(page2) == 2
        page1_ids = {i["id"] for i in page1}
        page2_ids = {i["id"] for i in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_tags_hydrated(self, graph):
        graph.create_feed(url="https://f.com/feed", title="F", description="", site_url="")
        now = datetime.now(UTC)
        item_id = graph.create_item(
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
        graph.enrich_item(item_id, [("topic x", 0.5)])
        graph.tag_item(item_id, "important")
        topics, _ = graph.get_topics()
        items = graph.get_topic_items(topics[0]["id"])
        assert items[0]["tags"] == ["important"]
