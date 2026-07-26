# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from reed.graph import GraphService, _rows


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    g.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
    yield g
    g.close()


def _make_item(graph, guid, title, published_at):
    return graph.create_item(
        feed_url="https://example.com/feed",
        guid=guid,
        url=f"https://example.com/{guid}",
        title=title,
        summary="",
        content="",
        author="",
        word_count=10,
        published_at=published_at,
        fetched_at=published_at,
    )


class TestSimilarTo:
    def test_two_items_sharing_two_topics_get_similar_to_edge(self, graph):
        now = datetime.now(UTC)
        i1 = _make_item(graph, "i1", "One", now)
        i2 = _make_item(graph, "i2", "Two", now)
        graph.enrich_item(i1, [("machine learning", 0.05), ("neural networks", 0.06)])
        graph.enrich_item(i2, [("machine learning", 0.05), ("neural networks", 0.06)])

        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)

        rows = _rows(
            graph._execute(
                "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) "
                "RETURN r.score AS score",
                {"i1": i1, "i2": i2},
            )
        )
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(1.0)  # identical topic sets

    def test_items_outside_window_are_not_linked(self, graph):
        now = datetime.now(UTC)
        old = now - timedelta(days=200)
        i1 = _make_item(graph, "i1", "One", old)
        i2 = _make_item(graph, "i2", "Two", old)
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])

        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)

        rows = _rows(
            graph._execute(
                "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) RETURN r",
                {"i1": i1, "i2": i2},
            )
        )
        assert rows == []

    def test_mark_and_sweep_removes_edge_when_items_age_out(self, graph):
        # Simulates the exact bug the adversarial review caught: an edge computed
        # while items were in-window must be swept once they age out, even though
        # its computed_at was refreshed on a prior run.
        t0 = datetime.now(UTC)
        published = t0 - timedelta(days=85)  # inside a 90-day window at t0
        i1 = _make_item(graph, "i1", "One", published)
        i2 = _make_item(graph, "i2", "Two", published)
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])

        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=t0)
        edge_exists = _rows(
            graph._execute(
                "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) RETURN r",
                {"i1": i1, "i2": i2},
            )
        )
        assert len(edge_exists) == 1

        # 10 days later: published (85 days before t0) is now 95 days before t1 — outside window
        t1 = t0 + timedelta(days=10)
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=t1)
        edge_after = _rows(
            graph._execute(
                "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) RETURN r",
                {"i1": i1, "i2": i2},
            )
        )
        assert edge_after == [], "edge must be swept once its items age out of the window"

    def test_edge_removed_when_score_drops_below_threshold_after_item_deletion(self, graph):
        now = datetime.now(UTC)
        i1 = _make_item(graph, "i1", "One", now)
        i2 = _make_item(graph, "i2", "Two", now)
        _i3 = _make_item(graph, "i3", "Three", now)
        # i1/i2 share 3 topics via a bridge through i3 style overlap isn't needed —
        # simpler: give i1/i2 exactly 2 shared topics, then remove one item's topic
        # link to drop shared_topics below the >=2 threshold.
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)
        assert _rows(
            graph._execute(
                "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) RETURN r",
                {"i1": i1, "i2": i2},
            )
        )

        # Remove one shared ABOUT edge so only 1 topic is shared (below >=2 threshold)
        graph._execute(
            "MATCH (i:Item {id: $id})-[r:ABOUT]->(t:Topic {name: 'topic b'}) DELETE r",
            {"id": i1},
        )
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)
        assert (
            _rows(
                graph._execute(
                    "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) RETURN r",
                    {"i1": i1, "i2": i2},
                )
            )
            == []
        )


class TestRelatedTo:
    def test_two_topics_co_occurring_get_related_to_edge(self, graph):
        now = datetime.now(UTC)
        i1 = _make_item(graph, "i1", "One", now)
        i2 = _make_item(graph, "i2", "Two", now)
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])

        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)

        rows = _rows(
            graph._execute(
                "MATCH (t1:Topic {name: 'topic a'})-[r:RELATED_TO]-(t2:Topic {name: 'topic b'}) "
                "RETURN r.weight AS weight"
            )
        )
        assert len(rows) == 1

    def test_related_to_edge_removed_when_item_deleted(self, graph):
        now = datetime.now(UTC)
        i1 = _make_item(graph, "i1", "One", now)
        i2 = _make_item(graph, "i2", "Two", now)
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)
        assert _rows(
            graph._execute(
                "MATCH (:Topic {name: 'topic a'})-[r:RELATED_TO]-(:Topic {name: 'topic b'}) "
                "RETURN r"
            )
        )

        # Deleting i2 entirely drops co-occurrence of topic a/topic b to 1 (< 2 threshold)
        graph._execute("MATCH (i:Item {id: $id}) DETACH DELETE i", {"id": i2})
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)
        assert (
            _rows(
                graph._execute(
                    "MATCH (:Topic {name: 'topic a'})-[r:RELATED_TO]-(:Topic {name: 'topic b'}) "
                    "RETURN r"
                )
            )
            == []
        )
