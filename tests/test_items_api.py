# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

from reed.poller import FeedPoller

from .conftest import SAMPLE_RSS, patched_feed_fetch


def _items(authed, query=""):
    return authed.get(f"/api/v1/items{query}").json()["data"]


class TestListItems:
    def test_empty_when_no_feeds(self, authed):
        r = authed.get("/api/v1/items")
        assert r.status_code == 200
        assert r.json()["data"] == []
        assert r.json()["meta"]["total"] == 0

    def test_items_appear_after_ingest(self, authed, subscribed_feed):
        items = _items(authed)
        assert {i["title"] for i in items} == {"First Post", "Second Post"}

    def test_list_item_shape(self, authed, subscribed_feed):
        first = next(i for i in _items(authed) if i["title"] == "First Post")
        assert first["id"]
        assert first["read"] is False
        assert first["starred"] is False
        assert first["feed"]["id"] == subscribed_feed["id"]
        assert first["feed"]["title"] == "Test Feed"
        assert first["author"] == {"name": "Jane Author"}
        assert first["summary"] == "Summary of the first post"
        assert "content" not in first  # detail-only field

    def test_filter_by_feed_id(self, authed, subscribed_feed):
        r = authed.get(f"/api/v1/items?feed_id={subscribed_feed['id']}")
        assert len(r.json()["data"]) == 2

    def test_filter_by_unknown_feed_returns_empty(self, authed, subscribed_feed):
        r = authed.get("/api/v1/items?feed_id=no-such-id")
        assert r.json()["data"] == []

    def test_unread_filter(self, authed, subscribed_feed):
        items = _items(authed)
        authed.patch(f"/api/v1/items/{items[0]['id']}", json={"read": True})
        unread = _items(authed, "?unread=true")
        assert len(unread) == 1
        assert unread[0]["id"] != items[0]["id"]

    def test_pagination_meta(self, authed, subscribed_feed):
        r = authed.get("/api/v1/items?limit=1&offset=0")
        body = r.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 2
        assert body["meta"]["has_more"] is True

        second = authed.get("/api/v1/items?limit=1&offset=1").json()
        assert second["data"][0]["id"] != body["data"][0]["id"]
        assert second["meta"]["has_more"] is False

    def test_invalid_limit_returns_400(self, authed):
        r = authed.get("/api/v1/items?limit=-1")
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_resubscribe_reattaches_items(self, authed, reed_client, subscribed_feed):
        """Items orphaned by delete_feed must reappear after resubscription."""
        graph = reed_client.app.state.graph
        authed.delete(f"/api/v1/feeds/{subscribed_feed['id']}")
        assert _items(authed) == []

        with patched_feed_fetch():
            authed.post("/api/v1/feeds", json={"url": subscribed_feed["url"]})

        poller = FeedPoller(graph)
        poller._ingest_entries(subscribed_feed["url"], SAMPLE_RSS, datetime.now(UTC))
        assert len(_items(authed)) == 2


class TestItemDetail:
    def test_get_item_detail(self, authed, subscribed_feed):
        item_id = _items(authed)[0]["id"]
        r = authed.get(f"/api/v1/items/{item_id}")
        assert r.status_code == 200
        detail = r.json()["data"]
        assert "content" in detail
        assert detail["note"] is None
        assert detail["reader_content"] is None

    def test_unknown_item_returns_404(self, authed):
        r = authed.get("/api/v1/items/no-such-id")
        assert r.status_code == 404


class TestItemState:
    def test_mark_read(self, authed, subscribed_feed):
        item_id = _items(authed)[0]["id"]
        r = authed.patch(f"/api/v1/items/{item_id}", json={"read": True})
        assert r.status_code == 200
        assert r.json()["data"]["read"] is True

    def test_star_and_unstar(self, authed, subscribed_feed):
        item_id = _items(authed)[0]["id"]
        assert authed.patch(f"/api/v1/items/{item_id}", json={"starred": True}).json()["data"][
            "starred"
        ]
        assert (
            authed.patch(f"/api/v1/items/{item_id}", json={"starred": False}).json()["data"][
                "starred"
            ]
            is False
        )

    def test_starred_filter(self, authed, subscribed_feed):
        item_id = _items(authed)[0]["id"]
        authed.patch(f"/api/v1/items/{item_id}", json={"starred": True})
        starred = _items(authed, "?starred=true")
        assert len(starred) == 1
        assert starred[0]["id"] == item_id


class TestBulkMarkRead:
    def test_mark_all_read(self, authed, subscribed_feed):
        r = authed.post("/api/v1/items/mark-read", json={})
        assert r.status_code == 200
        assert r.json()["data"]["marked_read"] == 2
        assert _items(authed, "?unread=true") == []

    def test_mark_read_for_feed(self, authed, subscribed_feed):
        r = authed.post("/api/v1/items/mark-read", json={"feed_id": subscribed_feed["id"]})
        assert r.json()["data"]["marked_read"] == 2

    def test_mark_read_before_date(self, authed, subscribed_feed):
        # Only "First Post" has a published date (2026-01-01); "Second Post"
        # falls back to fetched_at (now), which is after the cutoff.
        r = authed.post("/api/v1/items/mark-read", json={"before": "2026-02-01T00:00:00Z"})
        assert r.json()["data"]["marked_read"] == 1
        unread = _items(authed, "?unread=true")
        assert unread[0]["title"] == "Second Post"

    def test_unknown_feed_returns_404(self, authed):
        r = authed.post("/api/v1/items/mark-read", json={"feed_id": "no-such-id"})
        assert r.status_code == 404

    def test_idempotent(self, authed, subscribed_feed):
        authed.post("/api/v1/items/mark-read", json={})
        r = authed.post("/api/v1/items/mark-read", json={})
        assert r.json()["data"]["marked_read"] == 0


class TestOrphanedItems:
    """Starred and tagged items stay visible after their feed is removed."""

    def test_starred_and_tagged_survive_feed_delete(self, authed, subscribed_feed):
        items = _items(authed)
        starred_id, tagged_id = items[0]["id"], items[1]["id"]
        authed.patch(f"/api/v1/items/{starred_id}", json={"starred": True})
        authed.post(f"/api/v1/items/{tagged_id}/tags", json={"name": "keep"})

        authed.delete(f"/api/v1/feeds/{subscribed_feed['id']}")

        # Feed-derived views drop orphans; curated views keep them
        assert _items(authed) == []
        starred = _items(authed, "?starred=true")
        assert [i["id"] for i in starred] == [starred_id]
        assert starred[0]["feed"] is None
        assert [i["id"] for i in _items(authed, "?tag=keep")] == [tagged_id]


class TestListProjection:
    def test_list_items_omits_body_columns(self, subscribed_feed, reed_client):
        graph = reed_client.app.state.graph
        items, total = graph.list_items()
        assert total >= 1
        assert "content" not in items[0]
        assert "reader_content" not in items[0]
        # sanity: the lean row still carries what the tag join and list serialiser need
        assert "guid" in items[0]
        assert "id" in items[0]

    def test_get_item_includes_body_columns(self, subscribed_feed, reed_client):
        graph = reed_client.app.state.graph
        items, _ = graph.list_items()
        full = graph.get_item(items[0]["id"])
        assert "content" in full
        assert "reader_content" in full
