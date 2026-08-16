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
    """#168 — recompute_derived_edges issues five _execute calls (a
    total_items count query added by #241's topic-dominance cap, plus the
    four RELATED_TO/SIMILAR_TO merge/sweep statements); each one
    independently acquires and releases _conn_lock, so unlike restore_data
    (which wraps its whole transaction in a single `with self._conn_lock:`
    per #124), a concurrent thread can slip in and acquire the lock in the
    gap between two of this method's statements — the same gap close()
    could use to tear down the connection mid-recompute (see #124, #162).

    This test proves every inter-statement gap is closed: before each of
    the 2nd through 5th _execute calls, a separate thread attempts a
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

    assert call_count == 5
    assert not acquired_elsewhere.is_set(), (
        "a concurrent thread acquired _conn_lock in a gap between "
        "recompute_derived_edges's statements — the method isn't holding "
        "the lock across its full body"
    )


class TestTopicDominanceCap:
    def test_items_sharing_only_a_dominant_topic_get_no_similar_to_edge(self, graph):
        """A topic touching most of the library (a 'hub' topic, e.g. boilerplate
        repeated across every item of one feed — the real case that motivated
        this: 'hosted on acast' with item_count=1444 in a 4,751-item library,
        issue #241) must never by itself produce a SIMILAR_TO edge — it isn't
        a meaningful similarity signal, it's noise."""
        now = datetime.now(UTC)
        # Five items, all sharing ONLY a dominant topic — with topic_share_floor=2
        # and max_topic_share=0.5, a topic touching 3+ of 5 items (60%) exceeds
        # both floor and percentage and must be excluded.
        items = [_make_item(graph, f"hub{i}", f"Item {i}", now) for i in range(5)]
        for item_id in items:
            graph.enrich_item(item_id, [("hosted on acast", 0.05)])

        graph.recompute_derived_edges(
            window_days=90,
            score_threshold=0.1,
            max_topic_share=0.5,
            topic_share_floor=2,
            now=now,
        )

        rows = _rows(graph._execute("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n"))
        assert rows[0]["n"] == 0

    def test_items_sharing_dominant_and_genuine_topics_get_correctly_scored_edge(self, graph):
        """The dominant-topic exclusion must apply consistently to the shared-
        topic count AND both items' individual topic-count denominators — not
        just the numerator. This test distinguishes three possible outcomes
        (all numerically distinct) so a partial/incorrect implementation is
        caught, not just a missing one:
          - correct (hub excluded everywhere):      2/(3+2-2) = 0.667
          - buggy (hub excluded from numerator only): 2/(4+3-2) = 0.4
          - naive (hub not excluded at all):          3/(4+3-3) = 0.75
        """
        now = datetime.now(UTC)
        # Item A: hub + X + Y + Z (4 topics). Item B: hub + X + Y (3 topics).
        # Both share the hub (dominant) plus genuine topics X and Y.
        a = _make_item(graph, "a", "A", now)
        b = _make_item(graph, "b", "B", now)
        # 3 filler items also carrying the hub topic, so it crosses the
        # floor/percentage threshold (5 items total touch "hub" out of 5 items
        # in the library — 100% share, well past floor=2/share=0.5).
        fillers = [_make_item(graph, f"filler{i}", f"Filler {i}", now) for i in range(3)]
        for item_id in [a, b, *fillers]:
            graph.enrich_item(item_id, [("hub", 0.05)])
        graph.enrich_item(a, [("x", 0.05), ("y", 0.05), ("z", 0.05)])
        graph.enrich_item(b, [("x", 0.05), ("y", 0.05)])

        graph.recompute_derived_edges(
            window_days=90,
            score_threshold=0.1,
            max_topic_share=0.5,
            topic_share_floor=2,
            now=now,
        )

        rows = _rows(
            graph._execute(
                "MATCH (a:Item {id: $a})-[r:SIMILAR_TO]-(b:Item {id: $b}) RETURN r.score AS score",
                {"a": a, "b": b},
            )
        )
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(2 / 3)

    def test_topic_below_both_thresholds_is_not_excluded(self, graph):
        """Regression guard: a topic that does NOT cross both the floor and
        the percentage threshold must behave exactly as before this fix —
        the cap must not become accidentally over-aggressive."""
        now = datetime.now(UTC)
        i1 = _make_item(graph, "i1", "One", now)
        i2 = _make_item(graph, "i2", "Two", now)
        graph.enrich_item(i1, [("machine learning", 0.05), ("neural networks", 0.06)])
        graph.enrich_item(i2, [("machine learning", 0.05), ("neural networks", 0.06)])

        # Default-sized thresholds — with only 2 items in the whole library,
        # nothing crosses topic_share_floor=50.
        graph.recompute_derived_edges(
            window_days=90,
            score_threshold=0.1,
            max_topic_share=0.05,
            topic_share_floor=50,
            now=now,
        )

        rows = _rows(
            graph._execute(
                "MATCH (a:Item {id: $i1})-[r:SIMILAR_TO]-(b:Item {id: $i2}) "
                "RETURN r.score AS score",
                {"i1": i1, "i2": i2},
            )
        )
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(1.0)

    def test_dominant_topic_exclusion_activates_on_recompute_with_stricter_threshold(self, graph):
        """The sweep statement re-derives shared_topics/n1/n2/jaccard
        independently of the MERGE statement to decide whether to prune an
        edge — if its topic-dominance filtering doesn't match the MERGE's,
        the two statements disagree about which topics count, breaking the
        mark-and-sweep design's own stated invariant.

        Symmetric data run twice with IDENTICAL thresholds can't distinguish
        "sweep applies the filter" from "sweep ignores it entirely" — if
        every item shares the same topic set, an unfiltered shared_topics
        count and a filtered one can land on the same jaccard score by
        coincidence, and the edge survives either way. So instead: run once
        with a threshold so high the hub topic is NOT excluded (establishing
        an edge scored using the hub-inclusive computation), then run again
        with the real, stricter threshold that DOES exclude the hub. Item a
        and b share {hub, x}; hub is also carried by 3 filler items so it
        crosses the floor/percentage threshold in the second pass (5 items
        touch "hub" out of 5 total). Once hub is excluded, a and b share
        only {x} — a single shared topic, below the shared_topics >= 2 gate
        both statements apply — so the edge must be deleted. If the sweep's
        three filter points were dropped, the sweep would still see
        shared_topics=2 (hub+x) and keep the edge, so this genuinely
        exercises the sweep's independent re-application of the cap under
        changed capping criteria, not just a repeat of the same computation.
        """
        now = datetime.now(UTC)
        a = _make_item(graph, "a", "A", now)
        b = _make_item(graph, "b", "B", now)
        fillers = [_make_item(graph, f"filler{i}", f"Filler {i}", now) for i in range(3)]
        for item_id in [a, b, *fillers]:
            graph.enrich_item(item_id, [("hub", 0.05)])
        graph.enrich_item(a, [("x", 0.05)])
        graph.enrich_item(b, [("x", 0.05)])

        # Pass 1: floor so high the hub topic (item_count=5) is NOT excluded.
        # shared_topics={hub,x}=2, n1=n2=2 -> jaccard=2/(2+2-2)=1.0.
        graph.recompute_derived_edges(
            window_days=90,
            score_threshold=0.1,
            max_topic_share=0.5,
            topic_share_floor=10_000,
            now=now,
        )
        rows = _rows(
            graph._execute(
                "MATCH (a:Item {id: $a})-[r:SIMILAR_TO]-(b:Item {id: $b}) RETURN r.score AS score",
                {"a": a, "b": b},
            )
        )
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(1.0)

        # Pass 2: same data, but the real (strict) threshold now excludes
        # hub (item_count=5 > max(2, int(5*0.5))=2). a and b then share only
        # {x} -- shared_topics=1, below the shared_topics >= 2 gate -- so
        # the sweep must delete the edge the first pass created.
        graph.recompute_derived_edges(
            window_days=90,
            score_threshold=0.1,
            max_topic_share=0.5,
            topic_share_floor=2,
            now=now,
        )
        rows = _rows(
            graph._execute(
                "MATCH (a:Item {id: $a})-[r:SIMILAR_TO]-(b:Item {id: $b}) RETURN r.score AS score",
                {"a": a, "b": b},
            )
        )
        assert rows == []
