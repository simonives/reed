# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import threading

import pytest

from reed.graph import GraphService

from .conftest import create_test_item


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


class TestItemFiltersStarredTriState:
    def test_starred_none_returns_all(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        create_test_item(graph, "https://f.example.com/rss", "g2", "https://f.example.com/2", "Two")
        graph.update_item_state(i1, starred=True)

        items = graph.list_items_cursor(starred=None)
        assert len(items) == 2

    def test_starred_true_returns_only_starred(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        create_test_item(graph, "https://f.example.com/rss", "g2", "https://f.example.com/2", "Two")
        graph.update_item_state(i1, starred=True)

        items = graph.list_items_cursor(starred=True)
        assert len(items) == 1 and items[0]["guid"] == "g1"

    def test_starred_false_returns_only_not_starred(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        create_test_item(graph, "https://f.example.com/rss", "g2", "https://f.example.com/2", "Two")
        graph.update_item_state(i1, starred=True)

        items = graph.list_items_cursor(starred=False)
        assert len(items) == 1 and items[0]["guid"] == "g2"


class TestItemFiltersByTopic:
    def test_topic_id_filters_items(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "AI piece"
        )
        create_test_item(
            graph, "https://f.example.com/rss", "g2", "https://f.example.com/2", "Unrelated"
        )
        graph.enrich_item(i1, [("AI", 0.9)])
        topics, _ = graph.get_topics()
        topic_id = topics[0]["id"]

        items = graph.list_items_cursor(topic_id=topic_id)
        assert len(items) == 1 and items[0]["guid"] == "g1"


class TestMarkReadByIds:
    def test_marks_only_specified_items(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        i1 = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        i2 = create_test_item(
            graph, "https://f.example.com/rss", "g2", "https://f.example.com/2", "Two"
        )

        count = graph.mark_read_by_ids([i1])
        assert count == 1
        assert graph.get_item(i1)["read"] is True
        assert graph.get_item(i2)["read"] is False

    def test_ignores_unknown_ids_without_error(self, graph):
        count = graph.mark_read_by_ids(["nonexistent-id"])
        assert count == 0

    def test_empty_list_is_a_noop(self, graph):
        assert graph.mark_read_by_ids([]) == 0


class TestListAuthors:
    def test_returns_authors_by_item_count(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(
            graph,
            "https://f.example.com/rss",
            "g1",
            "https://f.example.com/1",
            "One",
            author="Alice",
        )
        create_test_item(
            graph,
            "https://f.example.com/rss",
            "g2",
            "https://f.example.com/2",
            "Two",
            author="Alice",
        )
        create_test_item(
            graph,
            "https://f.example.com/rss",
            "g3",
            "https://f.example.com/3",
            "Three",
            author="Bob",
        )
        authors = graph.list_authors()
        assert authors[0]["author"] == "Alice"
        assert authors[0]["item_count"] == 2

    def test_excludes_items_without_author(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One")
        assert graph.list_authors() == []


class TestAppendNote:
    def test_appends_to_existing_note(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        graph.put_note(item_id, "Original note.")
        graph.append_note(item_id, "Found: new regulation text at example.gov/reg-123")
        note = graph.get_note(item_id)
        assert "Original note." in note["body"]
        assert "Found: new regulation text at example.gov/reg-123" in note["body"]

    def test_creates_note_if_none_exists(self, graph):
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        graph.append_note(item_id, "First finding.")
        note = graph.get_note(item_id)
        assert "First finding." in note["body"]

    def test_returns_none_for_unknown_item(self, graph):
        assert graph.append_note("nonexistent", "text") is None

    def test_holds_conn_lock_across_full_body(self, graph):
        """append_note's unlocked read-then-write (get_note, then put_note)
        was a real accumulate-semantics hazard: unlike put_note's replace
        semantics, where a race between two writers just picks a winner, a
        lost update here silently destroys a user's prior findings.

        Proven the same way #168's recompute_derived_edges regression test
        proves it: before each _execute call after the first, a separate
        thread attempts a non-blocking acquire of the same RLock and must
        fail. t.join() is a strict synchronisation barrier, not a timing
        race — the main thread cannot proceed until the probing thread's
        (near-instant, non-blocking) acquire attempt has completed."""
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        item_id = create_test_item(
            graph, "https://f.example.com/rss", "g1", "https://f.example.com/1", "One"
        )
        graph.put_note(item_id, "Original note.")

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
            graph.append_note(item_id, "Found: new regulation text.")
        finally:
            del graph._execute

        assert call_count >= 2
        assert not acquired_elsewhere.is_set(), (
            "a concurrent thread acquired _conn_lock in a gap between "
            "append_note's get_note/put_note calls — the method isn't "
            "holding the lock across its full body"
        )
