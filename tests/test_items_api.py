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
        assert r.json()["meta"]["next_cursor"] is None

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
        # With 2 items and limit=1, first page has a next_cursor
        r = authed.get("/api/v1/items?limit=1")
        body = r.json()
        assert len(body["data"]) == 1
        assert body["meta"]["next_cursor"] is not None

        next_cursor = body["meta"]["next_cursor"]
        second = authed.get(f"/api/v1/items?limit=1&cursor={next_cursor}").json()
        assert second["data"][0]["id"] != body["data"][0]["id"]
        # With all items retrieved, a large-limit fetch yields no next_cursor
        all_items = authed.get("/api/v1/items?limit=200").json()
        assert all_items["meta"]["next_cursor"] is None

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


class TestItemEnvelope:
    def test_patch_response_includes_topics(self, authed, subscribed_feed):
        items = authed.get("/api/v1/items").json()["data"]
        assert items, "need at least one item"
        item_id = items[0]["id"]
        resp = authed.patch(
            f"/api/v1/items/{item_id}",
            json={"read": True},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "topics" in data
        assert isinstance(data["topics"], list)

    def test_extract_response_includes_topics(self, authed, subscribed_feed):
        from unittest.mock import patch

        items = authed.get("/api/v1/items").json()["data"]
        assert items
        item_id = items[0]["id"]
        with patch("reed.api.items.extract_article", return_value="<p>Extracted</p>"):
            resp = authed.post(f"/api/v1/items/{item_id}/extract")
        assert resp.status_code == 200, resp.text
        assert "topics" in resp.json()["data"]
        assert isinstance(resp.json()["data"]["topics"], list)


class TestItemDeduplication:
    def test_item_with_two_feed_edges_appears_once(self, authed):
        graph = authed.app.state.graph
        # Create two feeds
        feed1_url = "https://feed1.example.com/rss"
        feed2_url = "https://feed2.example.com/rss"
        graph.create_feed(url=feed1_url, title="Feed 1", description="", site_url="")
        graph.create_feed(url=feed2_url, title="Feed 2", description="", site_url="")
        # Create one item linked to both feeds
        item_id = graph.create_item(
            feed_url=feed1_url,
            guid="shared-item-guid",
            url="https://example.com/article",
            title="Shared Article",
            summary="",
            content="",
            author="",
            word_count=0,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        # Directly add second HAS_ITEM edge
        graph._execute(
            "MATCH (f:Feed {url: $url}), (i:Item {id: $id}) CREATE (f)-[:HAS_ITEM]->(i)",
            {"url": feed2_url, "id": item_id},
        )
        resp = authed.get("/api/v1/items")
        assert resp.status_code == 200
        body = resp.json()
        ids = [item["id"] for item in body["data"]]
        assert ids.count(item_id) == 1, f"expected 1 occurrence, got {ids.count(item_id)}"


class TestCursorPagination:
    def test_first_page_no_cursor_returns_items(self, authed, subscribed_feed, reed_client):
        resp = reed_client.get("/api/v1/items?limit=10", headers=authed.headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert "next_cursor" in body["meta"]

    def test_offset_param_is_removed(self, authed, subscribed_feed, reed_client):
        # offset is no longer a recognised param — FastAPI silently ignores it
        # Verify it does not paginate (same result with or without offset=1)
        resp_no_offset = reed_client.get("/api/v1/items", headers=authed.headers)
        resp_with_offset = reed_client.get("/api/v1/items?offset=1", headers=authed.headers)
        assert resp_no_offset.status_code == 200
        assert resp_with_offset.status_code == 200
        assert "next_cursor" in resp_with_offset.json()["meta"]
        assert resp_no_offset.json()["data"] == resp_with_offset.json()["data"]

    def test_invalid_cursor_returns_400(self, authed, reed_client):
        resp = reed_client.get("/api/v1/items?cursor=notbase64!!", headers=authed.headers)
        assert resp.status_code == 400

    def test_malformed_cursor_json_returns_400(self, authed, reed_client):
        import base64
        bad = base64.b64encode(b"not json").decode()
        resp = reed_client.get(f"/api/v1/items?cursor={bad}", headers=authed.headers)
        assert resp.status_code == 400

    def test_next_cursor_is_null_on_last_page(self, authed, subscribed_feed, reed_client):
        resp = reed_client.get("/api/v1/items?limit=200", headers=authed.headers)
        assert resp.status_code == 200
        assert resp.json()["meta"]["next_cursor"] is None

    def test_cursor_handles_null_published_at(self, authed, reed_client):
        from datetime import UTC, datetime
        graph = reed_client.app.state.graph
        feed_url = "https://null-pub.example.com/rss"
        graph.create_feed(url=feed_url, title="Null Pub", description="", site_url="")
        # Create 4 items ALL with published_at=None, with distinct fetched_at timestamps.
        # After page 1, cursor_ts encodes the last item's fetched_at. The buggy WHERE
        # compares cursor_ts against i.published_at (NULL), which is always NULL/falsy,
        # so page 2 returns nothing. The fix uses coalesce(i.published_at, i.fetched_at).
        for i in range(4):
            graph.create_item(
                feed_url=feed_url,
                guid=f"null-pub-{i}",
                url=f"https://null-pub.example.com/{i}",
                title=f"Item {i}",
                summary="", content="", author="", word_count=0,
                published_at=None,
                fetched_at=datetime(2026, 1, i + 1, 12, 0, 0, tzinfo=UTC),
            )
        # Page through all items with limit=2
        page1 = reed_client.get("/api/v1/items?limit=2", headers=authed.headers).json()
        page1_ids = [item["id"] for item in page1["data"]]
        cursor = page1["meta"]["next_cursor"]
        assert cursor is not None
        page2 = reed_client.get("/api/v1/items", params={"limit": 2, "cursor": cursor}, headers=authed.headers).json()
        page2_ids = [item["id"] for item in page2["data"]]
        all_ids = page1_ids + page2_ids
        assert len(all_ids) == 4, f"expected 4 items across 2 pages, got {len(all_ids)}: {all_ids}"
        assert len(set(all_ids)) == 4, "duplicate items across pages"

    def test_cursor_pagination_no_skipped_items(self, authed, reed_client):
        from datetime import UTC, datetime, timedelta
        graph = reed_client.app.state.graph
        feed_url = "https://cursor.example.com/rss"
        graph.create_feed(url=feed_url, title="Cursor Test", description="", site_url="")
        for i in range(5):
            graph.create_item(
                feed_url=feed_url,
                guid=f"cursor-item-{i}",
                url=f"https://cursor.example.com/{i}",
                title=f"Item {i}",
                summary="",
                content="",
                author="",
                word_count=0,
                published_at=datetime.now(UTC) - timedelta(minutes=i),
                fetched_at=datetime.now(UTC),
            )
        # Page 1
        resp1 = reed_client.get("/api/v1/items?limit=3", headers=authed.headers)
        body1 = resp1.json()
        page1_ids = [i["id"] for i in body1["data"]]
        next_cursor = body1["meta"]["next_cursor"]
        assert next_cursor is not None
        # Page 2
        resp2 = reed_client.get(
            "/api/v1/items", params={"limit": 3, "cursor": next_cursor}, headers=authed.headers
        )
        body2 = resp2.json()
        page2_ids = [i["id"] for i in body2["data"]]
        # No overlaps, no gaps
        assert not set(page1_ids) & set(page2_ids), "pages must not overlap"
        assert len(page1_ids) + len(page2_ids) == 5

    def test_cursor_pagination_starred_view(self, authed, reed_client):
        """Starred view pagination must not 500 on page 2."""
        from datetime import UTC, datetime
        graph = reed_client.app.state.graph
        feed_url = "https://starred-cursor.example.com/rss"
        graph.create_feed(url=feed_url, title="Starred Cursor", description="", site_url="")
        for i in range(4):
            item_id = graph.create_item(
                feed_url=feed_url,
                guid=f"starred-cur-{i}",
                url=f"https://starred-cursor.example.com/{i}",
                title=f"Item {i}", summary="", content="", author="", word_count=0,
                published_at=datetime(2026, 1, i + 1, tzinfo=UTC),
                fetched_at=datetime(2026, 1, i + 1, 12, 0, 0, tzinfo=UTC),
            )
            reed_client.patch(f"/api/v1/items/{item_id}", json={"starred": True}, headers=authed.headers)
        page1 = reed_client.get("/api/v1/items", params={"starred": "true", "limit": 2}, headers=authed.headers)
        assert page1.status_code == 200, page1.text
        cursor = page1.json()["meta"]["next_cursor"]
        assert cursor is not None
        page2 = reed_client.get("/api/v1/items", params={"starred": "true", "limit": 2, "cursor": cursor}, headers=authed.headers)
        assert page2.status_code == 200, page2.text
        page2_data = page2.json()["data"]
        assert len(page2_data) == 2
        all_ids = [i["id"] for i in page1.json()["data"]] + [i["id"] for i in page2_data]
        assert len(set(all_ids)) == 4

    def test_cursor_pagination_tag_unread_view(self, authed, reed_client):
        """Tag+unread view pagination must not 500 on page 2."""
        from datetime import UTC, datetime
        graph = reed_client.app.state.graph
        feed_url = "https://tag-unread-cursor.example.com/rss"
        graph.create_feed(url=feed_url, title="Tag Unread Cursor", description="", site_url="")
        for i in range(4):
            item_id = graph.create_item(
                feed_url=feed_url,
                guid=f"tag-unread-cur-{i}",
                url=f"https://tag-unread-cursor.example.com/{i}",
                title=f"Item {i}", summary="", content="", author="", word_count=0,
                published_at=datetime(2026, 1, i + 1, tzinfo=UTC),
                fetched_at=datetime(2026, 1, i + 1, 12, 0, 0, tzinfo=UTC),
            )
            graph.tag_item(item_id, "cursor-test-tag")
        page1 = reed_client.get("/api/v1/items", params={"tag": "cursor-test-tag", "unread": "true", "limit": 2}, headers=authed.headers)
        assert page1.status_code == 200, page1.text
        cursor = page1.json()["meta"]["next_cursor"]
        assert cursor is not None
        page2 = reed_client.get("/api/v1/items", params={"tag": "cursor-test-tag", "unread": "true", "limit": 2, "cursor": cursor}, headers=authed.headers)
        assert page2.status_code == 200, page2.text
        all_ids = [i["id"] for i in page1.json()["data"]] + [i["id"] for i in page2.json()["data"]]
        assert len(set(all_ids)) == 4
