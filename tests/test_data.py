# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService, _SCHEMA_VERSION


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
        assert set(backup.keys()) >= {"version", "exported_at", "feeds", "items", "notes", "tags", "config"}

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
            "version": 1, "exported_at": "2026-01-01T00:00:00+00:00",
            "feeds": [], "items": [], "notes": [], "tags": [], "config": {},
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
        rows = _rows(gs._conn.execute(
            "MATCH (i:Item) RETURN i.note_body AS note_body"
        ))
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
        with pytest.raises(Exception):
            gs.restore_data(bad_backup)
        # Transaction should have rolled back — original data must still be present
        assert len(gs.list_feeds()) == original_feed_count
