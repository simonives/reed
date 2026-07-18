# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService


@pytest.fixture
def gs(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


def _make_feed(gs, site_url="https://example.com"):
    gs.create_feed(
        url="https://example.com/feed",
        title="Test",
        description="",
        site_url=site_url,
    )


def _make_item(gs, url="https://example.com/1"):
    _make_feed(gs)
    gs.create_item(
        feed_url="https://example.com/feed",
        guid="guid-1",
        url=url,
        title="Title",
        summary="",
        content="",
        author="",
        word_count=0,
        published_at=None,
        fetched_at=datetime.now(UTC),
    )


class TestSafeUrlIngestion:
    """#121 — javascript: URIs must be stripped at ingestion time."""

    def test_create_item_strips_javascript_url(self, gs):
        _make_item(gs, url="javascript:alert(document.cookie)")
        items = gs.list_items_cursor()
        assert items[0]["url"] == ""

    def test_create_item_allows_https_url(self, gs):
        _make_item(gs, url="https://example.com/article")
        items = gs.list_items_cursor()
        assert items[0]["url"] == "https://example.com/article"

    def test_create_item_strips_data_uri(self, gs):
        _make_item(gs, url="data:text/html,<script>evil()</script>")
        items = gs.list_items_cursor()
        assert items[0]["url"] == ""

    def test_create_feed_strips_javascript_site_url(self, gs):
        _make_feed(gs, site_url="javascript:void(0)")
        feeds = gs.list_feeds()
        assert feeds[0]["site_url"] == ""

    def test_create_feed_allows_https_site_url(self, gs):
        _make_feed(gs, site_url="https://example.com")
        feeds = gs.list_feeds()
        assert feeds[0]["site_url"] == "https://example.com"


class TestRestoreDataSafeUrl:
    """#121 — javascript: URIs in backup must be stripped on restore."""

    def test_restore_strips_javascript_item_url(self, gs):
        backup = {
            "feeds": [
                {
                    "url": "https://example.com/feed",
                    "id": "f1",
                    "title": "Feed",
                    "description": "",
                    "site_url": "https://example.com",
                    "subscribed_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "items": [
                {
                    "id": "i1",
                    "guid": "g1",
                    "url": "javascript:steal()",
                    "title": "Bad",
                    "author": "",
                    "word_count": 0,
                    "read": False,
                    "starred": False,
                    "feed_url": "https://example.com/feed",
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "tags": [],
            "notes": [],
            "config": {},
        }
        gs.restore_data(backup)
        items = gs.list_items_cursor()
        assert items[0]["url"] == ""

    def test_restore_strips_javascript_feed_site_url(self, gs):
        backup = {
            "feeds": [
                {
                    "url": "https://example.com/feed",
                    "id": "f1",
                    "title": "Feed",
                    "description": "",
                    "site_url": "javascript:alert(1)",
                    "subscribed_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "items": [],
            "tags": [],
            "notes": [],
            "config": {},
        }
        gs.restore_data(backup)
        feeds = gs.list_feeds()
        assert feeds[0]["site_url"] == ""


class TestRestoreDataConfigAllowlist:
    """#92 — restore_data must not write unknown or reserved config keys."""

    def test_restore_ignores_unknown_config_key(self, gs):
        backup = {
            "feeds": [],
            "items": [],
            "tags": [],
            "notes": [],
            "config": {"__class__": "evil", "arbitrary_key": "injected"},
        }
        gs.restore_data(backup)
        stored = gs.get_config_values()
        assert "__class__" not in stored
        assert "arbitrary_key" not in stored

    def test_restore_ignores_schema_version_override(self, gs):
        from reed.graph import _SCHEMA_VERSION

        backup = {
            "feeds": [],
            "items": [],
            "tags": [],
            "notes": [],
            "config": {"schema_version": 999},
        }
        gs.restore_data(backup)
        stored = gs.get_config_values()
        assert stored.get("schema_version") == _SCHEMA_VERSION

    def test_restore_writes_allowed_config_keys(self, gs):
        backup = {
            "feeds": [],
            "items": [],
            "tags": [],
            "notes": [],
            "config": {"items_per_page": 25, "default_theme": "dark"},
        }
        gs.restore_data(backup)
        stored = gs.get_config_values()
        assert stored.get("items_per_page") == 25
        assert stored.get("default_theme") == "dark"
