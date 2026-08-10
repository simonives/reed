# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    g.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
    yield g
    g.close()


def _make_item(graph, guid, title, **kw):
    now = datetime.now(UTC)
    return graph.create_item(
        feed_url="https://example.com/feed",
        guid=guid,
        url=f"https://example.com/{guid}",
        title=title,
        summary=kw.get("summary", ""),
        content="",
        author=kw.get("author", ""),
        word_count=10,
        published_at=kw.get("published_at", now),
        fetched_at=now,
    )


class TestGetSimilarItems:
    def test_returns_none_for_nonexistent_item(self, graph):
        assert graph.get_similar_items("00000000-0000-0000-0000-000000000000") is None

    def test_returns_empty_list_for_existing_item_with_no_similar(self, graph):
        i1 = _make_item(graph, "i1", "Solo item")
        assert graph.get_similar_items(i1) == []

    def test_returns_similar_items_with_score_and_shared_topics(self, graph):
        i1 = _make_item(graph, "i1", "One")
        i2 = _make_item(graph, "i2", "Two")
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        results = graph.get_similar_items(i1)
        assert len(results) == 1
        result = results[0]
        assert result["id"] == i2
        assert result["title"] == "Two"
        assert result["score"] == pytest.approx(1.0)
        assert set(result["shared_topics"]) == {"topic a", "topic b"}
        assert "tags" in result
        assert result["tags"] == []


class TestGetAdjacentToStarred:
    def test_empty_when_no_starred_items(self, graph):
        assert graph.get_adjacent_to_starred() == []

    def test_excludes_read_candidates(self, graph):
        starred = _make_item(graph, "s1", "Starred")
        graph._execute("MATCH (i:Item {id: $id}) SET i.starred = true", {"id": starred})
        read_candidate = _make_item(graph, "c1", "Read candidate")
        graph._execute("MATCH (i:Item {id: $id}) SET i.read = true", {"id": read_candidate})
        graph.enrich_item(starred, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(read_candidate, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        assert graph.get_adjacent_to_starred() == []

    def test_excludes_already_starred_candidates(self, graph):
        starred = _make_item(graph, "s1", "Starred")
        graph._execute("MATCH (i:Item {id: $id}) SET i.starred = true", {"id": starred})
        also_starred_unread = _make_item(graph, "c1", "Also starred")
        graph._execute("MATCH (i:Item {id: $id}) SET i.starred = true", {"id": also_starred_unread})
        graph.enrich_item(starred, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(also_starred_unread, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        assert graph.get_adjacent_to_starred() == []

    def test_returns_unread_unstarred_items_similar_to_starred(self, graph):
        starred = _make_item(graph, "s1", "Starred")
        graph._execute("MATCH (i:Item {id: $id}) SET i.starred = true", {"id": starred})
        candidate = _make_item(graph, "c1", "Candidate")
        graph.enrich_item(starred, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(candidate, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        results = graph.get_adjacent_to_starred()
        assert len(results) == 1
        assert results[0]["id"] == candidate
        assert "score" in results[0]


class TestGetAuthorItems:
    def test_returns_items_matching_author_exactly(self, graph):
        _make_item(graph, "i1", "By Jane", author="Jane Author")
        _make_item(graph, "i2", "By John", author="John Author")
        results = graph.get_author_items("Jane Author")
        assert len(results) == 1
        assert results[0]["title"] == "By Jane"

    def test_empty_for_unknown_author(self, graph):
        _make_item(graph, "i1", "By Jane", author="Jane Author")
        assert graph.get_author_items("Nobody") == []

    def test_author_with_slash_in_name(self, graph):
        _make_item(graph, "i1", "AC/DC anthology", author="AC/DC")
        results = graph.get_author_items("AC/DC")
        assert len(results) == 1

    def test_cursor_pagination_returns_remaining_page(self, graph):
        from datetime import timedelta

        base = datetime.now(UTC)
        for n in range(3):
            _make_item(
                graph,
                f"i{n}",
                f"Item {n}",
                author="Prolific Author",
                published_at=base - timedelta(days=n),
            )
        first_page = graph.get_author_items("Prolific Author", limit=2)
        assert len(first_page) == 2
        last = first_page[-1]
        second_page = graph.get_author_items(
            "Prolific Author",
            cursor_ts=last["published_at"],
            cursor_guid=last["guid"],
            limit=2,
        )
        assert len(second_page) == 1
        assert {i["guid"] for i in first_page} & {i["guid"] for i in second_page} == set()


class TestGetTopicTimeline:
    def test_returns_none_for_nonexistent_topic(self, graph):
        assert graph.get_topic_timeline("00000000-0000-0000-0000-000000000000") is None

    def test_returns_empty_list_for_topic_with_no_items(self, graph):
        topic_id = graph._upsert_topic("orphan topic")
        assert graph.get_topic_timeline(topic_id) == []

    def test_buckets_items_by_week(self, graph):
        i1 = _make_item(graph, "i1", "One")
        graph.enrich_item(i1, [("weekly topic", 0.05)])
        topics, _ = graph.get_topics()
        topic_id = next(t["id"] for t in topics if t["name"] == "weekly topic")

        timeline = graph.get_topic_timeline(topic_id)
        assert len(timeline) == 1
        assert timeline[0]["count"] == 1
        assert "period" in timeline[0]


class TestGetFeedHealth:
    def test_empty_for_healthy_feed(self, graph):
        assert graph.get_feed_health() == []

    def test_includes_feed_with_high_consecutive_errors(self, graph):
        graph._execute(
            "MATCH (f:Feed {url: $url}) SET f.consecutive_errors = 11",
            {"url": "https://example.com/feed"},
        )
        results = graph.get_feed_health()
        assert len(results) == 1
        assert results[0]["consecutive_errors"] == 11

    def test_includes_never_polled_feed_past_30_days(self, graph):
        from datetime import timedelta

        old = datetime.now(UTC) - timedelta(days=31)
        graph._execute(
            "MATCH (f:Feed {url: $url}) SET f.subscribed_at = $old, f.last_fetched_at = NULL",
            {"url": "https://example.com/feed", "old": old},
        )
        results = graph.get_feed_health()
        assert len(results) == 1

    def test_excludes_inactive_feeds(self, graph):
        graph._execute(
            "MATCH (f:Feed {url: $url}) SET f.is_active = false, f.consecutive_errors = 20",
            {"url": "https://example.com/feed"},
        )
        assert graph.get_feed_health() == []
