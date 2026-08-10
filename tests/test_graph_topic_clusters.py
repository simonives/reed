# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest

from .conftest import create_test_item


@pytest.fixture
def graph(tmp_path):
    from reed.graph import GraphService

    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


class TestTopicsSortCentrality:
    def test_sort_centrality_ranks_connected_topic_above_isolated_topic(self, graph):
        """Regression guard against a vacuous centrality test: the original
        version of this test created two topics ("Hub"/"Leaf") that
        co-occurred only once — below recompute_derived_edges's
        `co_occurrences >= 2` threshold — so no RELATED_TO edge was ever
        created, and the test only asserted total count and name presence.
        It would have passed identically whether PageRank computed real
        centrality or nothing at all.

        This version creates a genuine RELATED_TO edge (A/B co-occur twice)
        plus a third topic (C) that never co-occurs with anything and so
        gets zero RELATED_TO edges, then asserts the centrality-sorted
        result ranks a topic from the real edge above the zero-edge one.

        Note (see #206): RELATED_TO's canonical direction (t1.id < t2.id)
        is arbitrary UUID ordering, and Kuzu's PageRank is directed, so
        *which* of A/B ends up ranked first is not deterministic — verified
        empirically that a topic that's a pure *source* in its only edge
        scores identically to a fully isolated topic (both hit PageRank's
        base/teleport floor; only the canonical *target* of an edge scores
        above it). So this test asserts the property that holds regardless
        of that bias: whichever of A/B became the canonical target
        outranks C, which has no edges at all. It does not assert a
        specific A-vs-B ordering, since #206 means that ordering isn't
        meaningful yet.
        """
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        ab1 = create_test_item(
            graph, "https://f.example.com/rss", "ab1", "https://f.example.com/ab1", "AB1"
        )
        ab2 = create_test_item(
            graph, "https://f.example.com/rss", "ab2", "https://f.example.com/ab2", "AB2"
        )
        c_item = create_test_item(
            graph, "https://f.example.com/rss", "c", "https://f.example.com/c", "C-only"
        )
        graph.enrich_item(ab1, [("A", 0.9), ("B", 0.8)])
        graph.enrich_item(ab2, [("A", 0.9), ("B", 0.8)])
        graph.enrich_item(c_item, [("C", 0.9)])
        graph.recompute_derived_edges(window_days=365, score_threshold=0.0)

        topics, total = graph.get_topics(sort="centrality")

        assert total == 3
        names = [t["name"] for t in topics]
        assert set(names) == {"A", "B", "C"}
        # C has zero RELATED_TO edges; A and B share exactly one. Whichever
        # of A/B is the canonical PageRank target of that edge must rank
        # strictly above C, which sits at the base/teleport floor.
        assert names[0] != "C"

    def test_invalid_sort_raises(self, graph):
        with pytest.raises(ValueError):
            graph.get_topics(sort="alphabetical")


class TestCentralityDirectionalBias:
    """Locks in the known, documented #206 limitation so a future fix is a
    deliberate, visible change to this test rather than a silent behaviour
    shift. Uses graph._execute directly to construct an unambiguous
    topology (bypassing recompute_derived_edges's arbitrary canonical
    direction), since the point here is to test Kuzu's PageRank/project_graph
    behaviour itself, not the derived-edge computation pipeline.
    """

    def test_pure_source_topic_ranks_identically_to_isolated_topic(self, graph):
        graph._execute("CREATE (:Topic {id: '1', name: 'Source', item_count: 1})")
        graph._execute("CREATE (:Topic {id: '2', name: 'Sink', item_count: 1})")
        graph._execute("CREATE (:Topic {id: '3', name: 'Isolated', item_count: 1})")
        graph._execute(
            "MATCH (a:Topic {id: '1'}), (b:Topic {id: '2'}) "
            "CREATE (a)-[:RELATED_TO {weight: 0.5}]->(b)"
        )

        topics, total = graph.get_topics(sort="centrality")

        assert total == 3
        by_name = {t["name"]: i for i, t in enumerate(topics)}
        # Sink (the canonical target) ranks strictly above both Source and
        # Isolated. Source and Isolated are not asserted to be in any
        # particular relative order — they score identically under #206's
        # current bias — only that both rank at/below Sink.
        assert by_name["Sink"] < by_name["Source"]
        assert by_name["Sink"] < by_name["Isolated"]


class TestGetTopicClusters:
    def test_returns_cluster_groupings(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph, "https://f.example.com/rss", "a", "https://f.example.com/a", "A"
        )
        b = create_test_item(
            graph, "https://f.example.com/rss", "b", "https://f.example.com/b", "B"
        )
        graph.enrich_item(a, [("Topic1", 0.9), ("Topic2", 0.8)])
        graph.enrich_item(b, [("Topic1", 0.9), ("Topic2", 0.8)])
        graph.recompute_derived_edges(window_days=365, score_threshold=0.0)
        clusters = graph.get_topic_clusters()
        assert len(clusters) >= 1

    def test_empty_on_fresh_instance(self, graph):
        assert graph.get_topic_clusters() == []
