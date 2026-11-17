# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

"""Polling calls create_item for every entry of every feed on every cycle.

Kuzu leaks native memory on each write transaction but not on reads, so an entry
that is already stored and linked must be decided by a read and issue no writes.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService

FEED_A = "https://a.example.com/rss"
FEED_B = "https://b.example.com/rss"
_WRITE_VERBS = ("CREATE", "MERGE", "SET ", "DELETE")


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    g.create_feed(FEED_A, "Feed A", "", "https://a.example.com")
    g.create_feed(FEED_B, "Feed B", "", "https://b.example.com")
    yield g
    g.close()


def _create(graph: GraphService, feed_url: str, guid: str = "guid-1") -> str | None:
    now = datetime.now(UTC)
    return graph.create_item(
        feed_url=feed_url,
        guid=guid,
        url=f"https://example.com/{guid}",
        title=f"Title {guid}",
        summary="summary",
        content="content",
        author="",
        word_count=1,
        published_at=now,
        fetched_at=now,
    )


def _record_statements(graph: GraphService, monkeypatch) -> list[str]:
    statements: list[str] = []
    real = graph._execute

    def spy(query, params=None):
        statements.append(query)
        return real(query, params) if params is not None else real(query)

    monkeypatch.setattr(graph, "_execute", spy)
    return statements


def _writes(statements: list[str]) -> list[str]:
    return [s for s in statements if any(v in s.upper() for v in _WRITE_VERBS)]


class TestCreateItemWrites:
    def test_new_item_is_created_and_linked_once(self, graph):
        item_id = _create(graph, FEED_A)
        assert item_id is not None
        assert graph.feed_has_item(FEED_A, "guid-1")
        assert graph.item_exists("guid-1")

    def test_existing_linked_item_returns_none(self, graph):
        _create(graph, FEED_A)
        assert _create(graph, FEED_A) is None

    def test_existing_linked_item_issues_no_write_statements(self, graph, monkeypatch):
        _create(graph, FEED_A)
        statements = _record_statements(graph, monkeypatch)

        for _ in range(5):
            assert _create(graph, FEED_A) is None

        assert statements, "the existence check should still run"
        assert _writes(statements) == []

    def test_item_shared_with_second_feed_is_still_linked(self, graph):
        first = _create(graph, FEED_A)
        assert first is not None
        assert not graph.feed_has_item(FEED_B, "guid-1")

        # The item already exists, so no new id is returned, but feed B must be linked.
        assert _create(graph, FEED_B) is None
        assert graph.feed_has_item(FEED_B, "guid-1")

    def test_shared_item_link_is_written_only_once(self, graph, monkeypatch):
        _create(graph, FEED_A)
        _create(graph, FEED_B)
        statements = _record_statements(graph, monkeypatch)

        assert _create(graph, FEED_B) is None

        assert _writes(statements) == []

    def test_feed_has_item_is_false_for_unknown_guid(self, graph):
        assert not graph.feed_has_item(FEED_A, "missing")


class TestPreparedStatementCache:
    """Connection.execute(query, params) prepares a new statement per call and leaks
    about 40 KB of native memory each time, so Reed prepares each query text once."""

    def test_repeated_parameterised_query_is_prepared_once(self, graph, monkeypatch):
        _create(graph, FEED_A)
        prepared: list[str] = []
        real = graph._conn._prepare

        def spy(query, *args, **kwargs):
            prepared.append(query)
            return real(query, *args, **kwargs)

        monkeypatch.setattr(graph._conn, "_prepare", spy)
        for _ in range(50):
            assert graph.feed_has_item(FEED_A, "guid-1")

        assert len(prepared) <= 1

    def test_cached_statement_uses_each_calls_parameters(self, graph):
        _create(graph, FEED_A, "guid-1")
        _create(graph, FEED_B, "guid-2")
        for _ in range(3):
            assert graph.feed_has_item(FEED_A, "guid-1")
            assert not graph.feed_has_item(FEED_A, "guid-2")
            assert graph.feed_has_item(FEED_B, "guid-2")
            assert not graph.feed_has_item(FEED_B, "guid-1")

    def test_cache_is_bounded(self, graph, monkeypatch):
        import reed.graph as graph_module

        monkeypatch.setattr(graph_module, "_PREPARED_CACHE_SIZE", 8)
        for i in range(40):
            graph._execute(f"RETURN $x AS v{i}", {"x": i})
        assert len(graph._prepared) <= 8

    def test_schema_change_clears_cached_statements(self, graph):
        graph._execute("MATCH (i:Item {guid: $g}) RETURN count(i) AS cnt", {"g": "x"})
        assert graph._prepared

        graph._execute("DROP TABLE SIMILAR_TO")
        assert not graph._prepared

        graph._execute(
            "CREATE REL TABLE IF NOT EXISTS SIMILAR_TO"
            "(FROM Item TO Item, score DOUBLE, computed_at TIMESTAMP)"
        )
        rows = graph._execute("MATCH (i:Item {guid: $g}) RETURN count(i) AS cnt", {"g": "x"})
        assert rows.get_next() == [0]

    def test_close_clears_the_cache(self, tmp_path):
        g = GraphService(str(tmp_path / "close.kuzu"))
        g._execute("MATCH (i:Item {guid: $g}) RETURN count(i) AS cnt", {"g": "x"})
        assert g._prepared
        g.close()
        assert not g._prepared
