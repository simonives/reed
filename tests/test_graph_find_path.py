# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest

from tests.conftest import create_test_item


@pytest.fixture
def graph(tmp_path):
    from reed.graph import GraphService

    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


class TestFindConnectionPath:
    def test_finds_path_between_items_sharing_a_topic(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        graph.enrich_item(a, [("Shared Topic", 0.9)])
        graph.enrich_item(b, [("Shared Topic", 0.9)])
        path = graph.find_connection_path(a, b)
        assert path is not None
        assert len(path) >= 2

    def test_returns_none_when_no_path_exists(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        # No shared topics — no ABOUT edges created at all
        path = graph.find_connection_path(a, b)
        assert path is None

    def test_returns_single_bounded_path_despite_hub_topic_fanout(self, graph):
        # NOTE on what this test can and can't prove: find_connection_path only
        # ever returns rows[0] regardless of the LIMIT clause's value, so no
        # return-value assertion here can distinguish "LIMIT 5" from "LIMIT 1"
        # or "no LIMIT at all" — that would require measuring Kuzu's internal
        # query cost, which isn't something this test suite exercises. What IS
        # worth verifying: a real fan-out scenario (many equally-short paths
        # between the same two items) doesn't break find_connection_path or
        # make it return something other than a single well-formed path. The
        # LIMIT clause's actual job — bounding how many equal-length paths Kuzu
        # enumerates internally before this method reads row 0 — is a query-cost
        # concern, not something observable through the returned data shape.
        #
        # A single shared topic gives only ONE shortest-path shape
        # (item-topic-item), so it can't exercise any fan-out regardless of
        # item count. To create genuine fan-out, link the same two items
        # through 20 *different* shared topics, giving 20 equally-short
        # (item-topicK-item) paths between them.
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        a = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="a",
            url="https://f.example.com/a",
            title="A",
        )
        b = create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="b",
            url="https://f.example.com/b",
            title="B",
        )
        for i in range(20):
            topic_name = f"Hub Topic {i}"
            graph.enrich_item(a, [(topic_name, 0.9)])
            graph.enrich_item(b, [(topic_name, 0.9)])

        # Confirm the fan-out is real: without a LIMIT, ALL SHORTEST would enumerate
        # all 20 equally-short paths between a and b.
        from reed.graph import _rows

        unbounded = _rows(
            graph._execute(
                "MATCH p = (x:Item {id: $a})"
                "-[:ABOUT|RELATED_TO* ALL SHORTEST 1..6]-(y:Item {id: $b}) "
                "RETURN nodes(p) AS path_nodes",
                {"a": a, "b": b},
            )
        )
        assert len(unbounded) == 20

        # find_connection_path must still return a single, well-formed 3-node path
        # (not error, not hang, not try to return all 20) despite that fan-out —
        # this is what the LIMIT 5 clause in the implementation guards against.
        path = graph.find_connection_path(a, b)
        assert path is not None
        assert len(path) == 3
