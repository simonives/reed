# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import httpx

from .conftest import patched_feed_fetch


class TestAuth:
    def test_no_key_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/feeds")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    def test_wrong_key_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/feeds", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_correct_key_passes(self, authed):
        r = authed.get("/api/v1/feeds")
        assert r.status_code == 200


class TestSubscribe:
    def test_subscribe_returns_201(self, authed):
        with patched_feed_fetch():
            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})

        assert r.status_code == 201
        feed = r.json()["data"]
        assert feed["url"] == "https://example.com/feed.rss"
        assert feed["title"] == "Test Feed"
        assert feed["site_url"] == "https://example.com"
        assert feed["id"]
        assert feed["is_active"] is True
        assert feed["poll_interval_minutes"] is None
        assert feed["effective_poll_interval_minutes"] == 60

    def test_subscribe_with_options(self, authed):
        with patched_feed_fetch():
            r = authed.post(
                "/api/v1/feeds",
                json={
                    "url": "https://example.com/feed.rss",
                    "display_name": "My Feed",
                    "tags": ["tech", "ai"],
                    "poll_interval_minutes": 30,
                },
            )

        feed = r.json()["data"]
        assert feed["display_name"] == "My Feed"
        assert sorted(feed["tags"]) == ["ai", "tech"]
        assert feed["poll_interval_minutes"] == 30
        assert feed["effective_poll_interval_minutes"] == 30

    def test_subscribe_duplicate_returns_409(self, authed):
        with patched_feed_fetch():
            authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})
            r = authed.post("/api/v1/feeds", json={"url": "https://example.com/feed.rss"})

        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CONFLICT"

    def test_unreachable_feed_returns_422(self, authed):
        with patched_feed_fetch(side_effect=httpx.ConnectError("timeout")):
            r = authed.post("/api/v1/feeds", json={"url": "https://unreachable.example/feed"})

        assert r.status_code == 422

    def test_whitespace_tag_returns_400(self, authed):
        r = authed.post(
            "/api/v1/feeds",
            json={"url": "https://example.com/feed.rss", "tags": [" "]},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_negative_poll_interval_returns_400(self, authed):
        r = authed.post(
            "/api/v1/feeds",
            json={"url": "https://example.com/feed.rss", "poll_interval_minutes": -5},
        )
        assert r.status_code == 400

    def test_zero_poll_interval_returns_400(self, authed):
        r = authed.post(
            "/api/v1/feeds",
            json={"url": "https://example.com/feed.rss", "poll_interval_minutes": 0},
        )
        assert r.status_code == 400


class TestListFeeds:
    def test_empty_list(self, authed):
        r = authed.get("/api/v1/feeds")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_shows_subscribed_feed_with_counts(self, authed, subscribed_feed):
        r = authed.get("/api/v1/feeds")
        feeds = r.json()["data"]
        assert len(feeds) == 1
        assert feeds[0]["title"] == "Test Feed"
        assert feeds[0]["item_count"] == 2
        assert feeds[0]["unread_count"] == 2


class TestGetFeed:
    def test_get_by_id(self, authed, subscribed_feed):
        r = authed.get(f"/api/v1/feeds/{subscribed_feed['id']}")
        assert r.status_code == 200
        assert r.json()["data"]["url"] == subscribed_feed["url"]

    def test_unknown_id_returns_404(self, authed):
        r = authed.get("/api/v1/feeds/no-such-id")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"


class TestUpdateFeed:
    def test_patch_settings(self, authed, subscribed_feed):
        r = authed.patch(
            f"/api/v1/feeds/{subscribed_feed['id']}",
            json={
                "display_name": "Renamed",
                "poll_interval_minutes": 15,
                "reader_mode_enabled": False,
                "is_active": False,
                "tags": ["news"],
            },
        )
        assert r.status_code == 200
        feed = r.json()["data"]
        assert feed["display_name"] == "Renamed"
        assert feed["poll_interval_minutes"] == 15
        assert feed["reader_mode_enabled"] is False
        assert feed["effective_reader_mode_enabled"] is False
        assert feed["is_active"] is False
        assert feed["tags"] == ["news"]

    def test_partial_patch_leaves_other_fields(self, authed, subscribed_feed):
        authed.patch(f"/api/v1/feeds/{subscribed_feed['id']}", json={"display_name": "X"})
        feed = authed.get(f"/api/v1/feeds/{subscribed_feed['id']}").json()["data"]
        assert feed["display_name"] == "X"
        assert feed["is_active"] is True

    def test_patch_unknown_returns_404(self, authed):
        r = authed.patch("/api/v1/feeds/no-such-id", json={"display_name": "X"})
        assert r.status_code == 404

    def test_patch_whitespace_tag_returns_400(self, authed, subscribed_feed):
        r = authed.patch(
            f"/api/v1/feeds/{subscribed_feed['id']}", json={"tags": ["  "]}
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_patch_negative_poll_interval_returns_400(self, authed, subscribed_feed):
        r = authed.patch(
            f"/api/v1/feeds/{subscribed_feed['id']}", json={"poll_interval_minutes": -1}
        )
        assert r.status_code == 400


class TestDeleteFeed:
    def test_delete_existing_feed(self, authed, subscribed_feed):
        r = authed.delete(f"/api/v1/feeds/{subscribed_feed['id']}")
        assert r.status_code == 204
        assert authed.get("/api/v1/feeds").json()["data"] == []

    def test_delete_nonexistent_returns_404(self, authed):
        r = authed.delete("/api/v1/feeds/no-such-id")
        assert r.status_code == 404


class TestFeedItems:
    def test_lists_items_for_feed(self, authed, subscribed_feed):
        r = authed.get(f"/api/v1/feeds/{subscribed_feed['id']}/items")
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] == 2
        assert body["meta"]["has_more"] is False

    def test_unknown_feed_returns_404(self, authed):
        r = authed.get("/api/v1/feeds/no-such-id/items")
        assert r.status_code == 404


class TestDiscover:
    HTML = b"""<html><head>
      <link rel="alternate" type="application/rss+xml" title="RSS" href="/feed.xml">
      <link rel="alternate" type="application/atom+xml" title="Atom" href="https://example.com/atom.xml">
    </head><body></body></html>"""

    def test_discovers_feeds_from_html(self, authed):
        from unittest.mock import MagicMock

        resp = MagicMock()
        resp.status_code = 200
        resp.text = self.HTML.decode()
        resp.url = "https://example.com/"
        resp.headers = {"Content-Type": "text/html"}
        resp.raise_for_status = MagicMock()

        with patched_feed_fetch(response=resp):
            r = authed.post("/api/v1/feeds/discover", json={"url": "https://example.com"})

        assert r.status_code == 200
        feeds = r.json()["data"]
        assert {f["url"] for f in feeds} == {
            "https://example.com/feed.xml",
            "https://example.com/atom.xml",
        }

    def test_direct_feed_url_returns_itself(self, authed):
        from unittest.mock import MagicMock

        resp = MagicMock()
        resp.status_code = 200
        resp.text = '<?xml version="1.0"?><rss version="2.0"></rss>'
        resp.url = "https://example.com/feed.xml"
        resp.headers = {"Content-Type": "application/rss+xml"}
        resp.raise_for_status = MagicMock()

        with patched_feed_fetch(response=resp):
            r = authed.post(
                "/api/v1/feeds/discover", json={"url": "https://example.com/feed.xml"}
            )

        assert r.status_code == 200
        assert r.json()["data"][0]["url"] == "https://example.com/feed.xml"
