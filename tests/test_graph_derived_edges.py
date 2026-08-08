# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import threading
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


def test_recompute_derived_edges_holds_conn_lock_across_full_body(graph):
    """#168 — recompute_derived_edges issues four _execute calls; each one
    independently acquires and releases _conn_lock, so unlike restore_data
    (which wraps its whole transaction in a single `with self._conn_lock:`
    per #124), a concurrent thread can slip in and acquire the lock in the
    gap between two of this method's statements — the same gap close()
    could use to tear down the connection mid-recompute (see #124, #162).

    This test proves every inter-statement gap is closed: before each of
    the 2nd/3rd/4th _execute calls, a separate thread attempts a
    non-blocking acquire of the same RLock and must fail. The `t.join()`
    below is a strict synchronisation barrier, not a timing race — the main
    thread cannot proceed past it until the probing thread's (near-instant,
    non-blocking) acquire attempt has completed, so this doesn't depend on
    hitting a narrow scheduling window. `assert not t.is_alive()` turns a
    pathological failure to complete within the join timeout into a loud
    failure rather than a silently-skipped probe.
    """
    now = datetime.now(UTC)
    i1 = _make_item(graph, "i1", "One", now)
    i2 = _make_item(graph, "i2", "Two", now)
    graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
    graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])

    original_execute = GraphService._execute
    call_count = 0
    acquired_elsewhere = threading.Event()

    def spying_execute(self, query, params=None):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:

            def try_acquire():
                got = self._conn_lock.acquire(blocking=False)
                if got:
                    acquired_elsewhere.set()
                    self._conn_lock.release()

            t = threading.Thread(target=try_acquire)
            t.start()
            t.join(timeout=1)
            assert not t.is_alive(), "probing thread failed to complete within 1s"
        return original_execute(self, query, params)

    graph._execute = spying_execute.__get__(graph, GraphService)
    try:
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1, now=now)
    finally:
        del graph._execute

    assert call_count == 4
    assert not acquired_elsewhere.is_set(), (
        "a concurrent thread acquired _conn_lock in a gap between "
        "recompute_derived_edges's statements — the method isn't holding "
        "the lock across its full body"
    )
