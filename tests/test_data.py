# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import threading
import time
import types
from datetime import UTC, datetime

import pytest

from reed.graph import _SCHEMA_VERSION, GraphService


@pytest.fixture
def graph_with_data(tmp_path):
    """A graph with one feed and one item, ready for enrichment tests."""
    g = GraphService(str(tmp_path / "test.kuzu"))
    g.create_feed(
        url="https://example.com/feed",
        title="Example Feed",
        description="desc",
        site_url="https://example.com",
    )
    g.create_item(
        feed_url="https://example.com/feed",
        guid="https://example.com/1",
        url="https://example.com/1",
        title="Hello world",
        summary="machine learning advances",
        content="<p>Hello world</p>",
        author="Jane",
        word_count=3,
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
        fetched_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    yield g
    g.close()


def _make_gs(tmp_path):
    return GraphService(str(tmp_path / "test.kuzu"))


def _seed(gs):
    """Insert one feed, one item, one note, one tag; return ids."""
    feed = gs.create_feed(
        url="https://example.com/feed",
        title="Example Feed",
        description="desc",
        site_url="https://example.com",
        display_name="My Example",
        poll_interval_minutes=60,
        tags=["tech"],
    )
    item_id = gs.create_item(
        feed_url="https://example.com/feed",
        guid="https://example.com/1",
        url="https://example.com/1",
        title="Hello world",
        summary="",
        content="<p>Hello world</p>",
        author="Jane",
        word_count=2,
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
        fetched_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    gs.tag_item(item_id, "tech")
    gs.put_note(item_id, "Important note.")
    return feed["id"], item_id


class TestExportData:
    def test_returns_required_keys(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        backup = gs.export_data()
        assert set(backup.keys()) >= {
            "version",
            "exported_at",
            "feeds",
            "items",
            "notes",
            "tags",
            "config",
        }

    def test_version_is_1(self, tmp_path):
        gs = _make_gs(tmp_path)
        backup = gs.export_data()
        assert backup["version"] == 1

    def test_feeds_include_tags(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        backup = gs.export_data()
        assert len(backup["feeds"]) == 1
        assert backup["feeds"][0]["tags"] == ["tech"]

    def test_items_are_metadata_only(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        backup = gs.export_data()
        item = backup["items"][0]
        assert "content" not in item
        assert "summary" not in item
        assert "reader_content" not in item
        assert item["title"] == "Hello world"
        assert item["read"] is False

    def test_items_include_feed_url(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        backup = gs.export_data()
        assert backup["items"][0]["feed_url"] == "https://example.com/feed"

    def test_notes_exported(self, tmp_path):
        gs = _make_gs(tmp_path)
        _, item_id = _seed(gs)
        backup = gs.export_data()
        assert len(backup["notes"]) == 1
        assert backup["notes"][0]["item_id"] == item_id
        assert backup["notes"][0]["body"] == "Important note."

    def test_schema_version_excluded_from_config(self, tmp_path):
        gs = _make_gs(tmp_path)
        backup = gs.export_data()
        assert "schema_version" not in backup["config"]

    def test_empty_instance_exports_empty_lists(self, tmp_path):
        gs = _make_gs(tmp_path)
        backup = gs.export_data()
        assert backup["feeds"] == []
        assert backup["items"] == []
        assert backup["notes"] == []
        assert backup["tags"] == []


class TestRestoreData:
    def test_round_trip_preserves_counts(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        backup = gs.export_data()
        gs.restore_data(backup)
        after = gs.export_data()
        assert len(after["feeds"]) == len(backup["feeds"])
        assert len(after["items"]) == len(backup["items"])
        assert len(after["notes"]) == len(backup["notes"])
        assert len(after["tags"]) == len(backup["tags"])

    def test_restore_clears_existing_data(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        empty_backup = {
            "version": 1,
            "exported_at": "2026-01-01T00:00:00+00:00",
            "feeds": [],
            "items": [],
            "notes": [],
            "tags": [],
            "config": {},
        }
        gs.restore_data(empty_backup)
        assert gs.list_feeds() == []

    def test_restore_preserves_read_and_starred(self, tmp_path):
        gs = _make_gs(tmp_path)
        _, item_id = _seed(gs)
        gs.update_item_state(item_id, read=True, starred=True)
        backup = gs.export_data()
        gs.restore_data(backup)
        after = gs.export_data()
        item = after["items"][0]
        assert item["read"] is True
        assert item["starred"] is True

    def test_restore_syncs_note_body_for_fts(self, tmp_path):
        gs = _make_gs(tmp_path)
        _, item_id = _seed(gs)
        backup = gs.export_data()
        # Find the item's id in the backup then restore
        gs.restore_data(backup)
        # After restore, note_body on Item should be populated
        from reed.graph import _rows

        rows = _rows(gs._conn.execute("MATCH (i:Item) RETURN i.note_body AS note_body"))
        assert rows[0]["note_body"] == "Important note."

    def test_restore_preserves_schema_version(self, tmp_path):
        gs = _make_gs(tmp_path)
        backup = gs.export_data()
        gs.restore_data(backup)
        config = gs.get_config_values()
        assert config["schema_version"] == _SCHEMA_VERSION

    def test_restore_returns_summary_counts(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        backup = gs.export_data()
        gs2 = _make_gs(tmp_path / "fresh")
        summary = gs2.restore_data(backup)
        assert summary == {"feeds": 1, "items": 1, "notes": 1, "tags": 1}

    def test_restore_failed_backup_leaves_data_intact(self, tmp_path):
        gs = _make_gs(tmp_path)
        _seed(gs)
        original_feed_count = len(gs.list_feeds())
        bad_backup = {
            "version": 1,
            "exported_at": "2026-07-17T00:00:00+00:00",
            "feeds": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "url": "https://bad.example.com/feed",
                    "title": "Bad",
                    "display_name": None,
                    "description": "",
                    "site_url": "",
                    "poll_interval_minutes": None,
                    "reader_mode_enabled": None,
                    "subscribed_at": "not-a-valid-timestamp",  # raises ValueError
                    "tags": [],
                }
            ],
            "items": [],
            "notes": [],
            "tags": [],
            "config": {},
        }
        with pytest.raises(ValueError):
            gs.restore_data(bad_backup)
        # Transaction should have rolled back — original data must still be present
        assert len(gs.list_feeds()) == original_feed_count


class TestExportRestoreTopics:
    def test_export_includes_topics_and_about_edges(self, graph_with_data):
        g = graph_with_data
        # Enrich an item so there are topics to export
        items = g.get_unenriched_items()
        assert items, "fixture must have at least one item"
        item = items[0]
        g.enrich_item(item["id"], [("rss feeds", 0.1), ("open source", 0.2)])
        backup = g.export_data()
        assert "topics" in backup
        assert "about_edges" in backup
        assert len(backup["topics"]) >= 1
        assert len(backup["about_edges"]) >= 1
        # topics must not include item_count (derived)
        for t in backup["topics"]:
            assert "item_count" not in t
            assert "id" in t and "name" in t
        # about_edges must use natural keys
        for e in backup["about_edges"]:
            assert "item_guid" in e
            assert "topic_name" in e
            assert "score" in e

    def test_restore_round_trips_topics(self, graph_with_data, tmp_path):
        g = graph_with_data
        items = g.get_unenriched_items()
        item = items[0]
        g.enrich_item(item["id"], [("machine learning", 0.15)])
        backup = g.export_data()
        # Restore into a fresh graph
        g2 = GraphService(str(tmp_path / "restore_test.kuzu"))
        g2.restore_data(backup)
        topics = g2.get_item_topics(item["id"])
        assert any(t["name"] == "machine learning" for t in topics)
        g2.close()

    def test_restore_clears_ghost_topics(self, graph_with_data, tmp_path):
        g = graph_with_data
        # Enrich to create topics
        items = g.get_unenriched_items()
        item = items[0]
        g.enrich_item(item["id"], [("ghost topic", 0.5)])
        backup_before = g.export_data()
        # Take a backup WITHOUT topics (simulate old backup)
        backup_no_topics = {
            k: v for k, v in backup_before.items() if k not in ("topics", "about_edges")
        }
        g.restore_data(backup_no_topics)
        # Ghost topics must be gone
        all_topics, _ = g.get_topics()
        assert all_topics == []

    def test_restore_recomputes_item_count(self, graph_with_data, tmp_path):
        g = graph_with_data
        items = g.get_unenriched_items()
        item = items[0]
        g.enrich_item(item["id"], [("test topic", 0.3)])
        backup = g.export_data()
        g.restore_data(backup)
        topics, _ = g.get_topics()
        assert any(t["name"] == "test topic" and t["item_count"] >= 1 for t in topics)

    def test_restore_returns_verified_counts(self, graph_with_data):
        g = graph_with_data
        backup = g.export_data()
        result = g.restore_data(backup)
        # Result must reflect actual DB counts, not input lengths
        assert "feeds" in result and "items" in result
        actual_feeds = g.list_feeds()
        assert result["feeds"] == len(actual_feeds)


class TestExportOrphanedItems:
    """#125 — export_data must include starred/tagged items whose feed was deleted."""

    def _make_gs(self, tmp_path):
        return GraphService(str(tmp_path / "test.kuzu"))

    def _seed_item(self, gs, starred=False, tag=None):
        feed = gs.create_feed(
            url="https://example.com/feed",
            title="Feed",
            description="",
            site_url="https://example.com",
        )
        item_id = gs.create_item(
            feed_url="https://example.com/feed",
            guid="g1",
            url="https://example.com/1",
            title="Article",
            summary="",
            content="",
            author="",
            word_count=0,
            published_at=None,
            fetched_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        if starred:
            gs.update_item_state(item_id, starred=True)
        if tag:
            gs.tag_item(item_id, tag)
        gs.delete_feed(feed["id"])
        return item_id

    def test_starred_item_included_after_feed_deleted(self, tmp_path):
        gs = self._make_gs(tmp_path)
        try:
            self._seed_item(gs, starred=True)
            backup = gs.export_data()
            assert any(i["guid"] == "g1" for i in backup["items"])
        finally:
            gs.close()

    def test_tagged_item_included_after_feed_deleted(self, tmp_path):
        gs = self._make_gs(tmp_path)
        try:
            gs.ensure_tag("tech")
            self._seed_item(gs, tag="tech")
            backup = gs.export_data()
            assert any(i["guid"] == "g1" for i in backup["items"])
        finally:
            gs.close()

    def test_orphaned_item_feed_url_is_none_or_empty(self, tmp_path):
        gs = self._make_gs(tmp_path)
        try:
            self._seed_item(gs, starred=True)
            backup = gs.export_data()
            item = next(i for i in backup["items"] if i["guid"] == "g1")
            # feed_url may be None or absent for orphans — must not crash restore
            assert "feed_url" in item
        finally:
            gs.close()

    def test_orphaned_item_survives_restore_roundtrip(self, tmp_path):
        gs = self._make_gs(tmp_path)
        try:
            self._seed_item(gs, starred=True)
            backup = gs.export_data()
            gs.restore_data(backup)
            items = gs.list_items_cursor(starred_only=True)
            assert any(i["guid"] == "g1" for i in items)
        finally:
            gs.close()

    def test_note_on_orphaned_item_survives_export_and_restore(self, tmp_path):
        """A note on an item whose feed was deleted must not be silently
        dropped: it must be exported, and restore must be able to attach it
        (the item it references must also have been exported, per #125).
        """
        gs = self._make_gs(tmp_path)
        try:
            item_id = self._seed_item(gs, starred=True)
            gs.put_note(item_id, "Important note.")
            backup = gs.export_data()
            assert any(n["item_id"] == item_id for n in backup["notes"])

            gs.restore_data(backup)
            restored = gs.export_data()
            assert any(n["item_id"] == item_id for n in restored["notes"])
            assert any(i["guid"] == "g1" for i in restored["items"])
        finally:
            gs.close()


class TestRestoreTransactionIsolation:
    """#124 — restore_data must hold the connection lock for the whole
    transaction, so a concurrent write from another thread cannot execute
    against the connection while the restore transaction is open (it would
    otherwise interleave into the open BEGIN/COMMIT and either get silently
    rolled back with the restore, get committed as part of it, or abort the
    transaction outright).
    """

    def test_concurrent_write_is_blocked_until_restore_completes(self, tmp_path):
        gs = GraphService(str(tmp_path / "test.kuzu"))
        try:
            # Enough statements to give a concurrent thread a realistic
            # window to interleave if the lock were released between them.
            backup = {
                "version": 1,
                "feeds": [],
                "items": [],
                "notes": [],
                "tags": [{"id": str(i), "name": f"tag{i}"} for i in range(3000)],
                "topics": [],
                "about_edges": [],
                "config": {},
            }

            timestamps: dict[str, float] = {}

            def run_restore() -> None:
                timestamps["restore_start"] = time.monotonic()
                gs.restore_data(backup)
                timestamps["restore_end"] = time.monotonic()

            restore_thread = threading.Thread(target=run_restore)
            restore_thread.start()
            time.sleep(0.05)  # let the restore transaction open

            timestamps["concurrent_start"] = time.monotonic()
            gs.create_feed(
                url="https://concurrent.example/feed",
                title="Concurrent",
                description="",
                site_url="",
            )
            timestamps["concurrent_end"] = time.monotonic()

            restore_thread.join(timeout=10)
            assert not restore_thread.is_alive()

            # The concurrent write must not have completed while the restore
            # transaction was still open — it must have blocked on the lock
            # until restore_data released it.
            assert timestamps["concurrent_end"] >= timestamps["restore_end"], (
                "concurrent write completed before the restore transaction "
                "finished — it interleaved into the open restore transaction "
                "instead of waiting for the whole-transaction lock"
            )
        finally:
            gs.close()

    def test_old_per_statement_locking_would_have_let_the_write_interleave(self, tmp_path):
        """Control case: reproduces the pre-fix restore_data (BEGIN/COMMIT run
        through the normal per-statement-locking _execute, with no lock held
        across the whole transaction) to prove the assertion above actually
        distinguishes correct from buggy behaviour, rather than passing
        unconditionally.
        """
        gs = GraphService(str(tmp_path / "test.kuzu"))
        try:
            backup = {
                "version": 1,
                "feeds": [],
                "items": [],
                "notes": [],
                "tags": [{"id": str(i), "name": f"tag{i}"} for i in range(3000)],
                "topics": [],
                "about_edges": [],
                "config": {},
            }

            def unlocked_restore_data(self, backup):
                self._execute("BEGIN TRANSACTION")
                try:
                    result = self._restore_data_inner(backup)
                    self._execute("COMMIT")
                    return result
                except Exception:
                    self._execute("ROLLBACK")
                    raise

            gs.restore_data = types.MethodType(unlocked_restore_data, gs)

            timestamps: dict[str, float] = {}

            def run_restore() -> None:
                timestamps["restore_start"] = time.monotonic()
                gs.restore_data(backup)
                timestamps["restore_end"] = time.monotonic()

            restore_thread = threading.Thread(target=run_restore)
            restore_thread.start()
            time.sleep(0.05)

            timestamps["concurrent_start"] = time.monotonic()
            gs.create_feed(
                url="https://concurrent.example/feed",
                title="Concurrent",
                description="",
                site_url="",
            )
            timestamps["concurrent_end"] = time.monotonic()

            restore_thread.join(timeout=10)
            assert not restore_thread.is_alive()

            assert timestamps["concurrent_end"] < timestamps["restore_end"], (
                "expected the unlocked control implementation to let the "
                "concurrent write interleave — if it didn't, this test's "
                "timing assumptions no longer hold and it should be revisited"
            )
        finally:
            gs.close()


class TestShareTargetExportExclusion:
    def test_share_targets_absent_from_export(self, graph_with_data):
        graph_with_data.create_share_target(
            "webhook", "Secret hook", {"url": "https://x.com", "token": "super-secret-token"}
        )
        backup = graph_with_data.export_data()
        serialized = str(backup)
        assert "super-secret-token" not in serialized
        assert "share" not in serialized.lower()


class TestExportDataIncludeConfig:
    def test_include_config_true_is_default_and_has_config_key(self, graph_with_data):
        backup = graph_with_data.export_data()
        assert "config" in backup

    def test_include_config_false_omits_config_key_entirely(self, graph_with_data):
        backup = graph_with_data.export_data(include_config=False)
        assert "config" not in backup

    def test_other_keys_unaffected_by_include_config(self, graph_with_data):
        with_config = graph_with_data.export_data(include_config=True)
        without_config = graph_with_data.export_data(include_config=False)
        shared_keys = set(with_config.keys()) & set(without_config.keys())
        for key in ("version", "feeds", "items", "notes", "tags", "topics", "about_edges"):
            assert key in shared_keys
