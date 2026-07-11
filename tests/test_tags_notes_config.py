# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations


def _first_item_id(authed):
    return authed.get("/api/v1/items").json()["data"][0]["id"]


class TestTags:
    def test_empty_list(self, authed):
        assert authed.get("/api/v1/tags").json()["data"] == []

    def test_create_and_list(self, authed):
        r = authed.post("/api/v1/tags", json={"name": "research"})
        assert r.status_code == 201
        tags = authed.get("/api/v1/tags").json()["data"]
        assert tags[0]["name"] == "research"
        assert tags[0]["item_count"] == 0

    def test_create_is_idempotent(self, authed):
        first = authed.post("/api/v1/tags", json={"name": "research"}).json()["data"]
        second = authed.post("/api/v1/tags", json={"name": "research"}).json()["data"]
        assert first["id"] == second["id"]

    def test_empty_name_returns_422(self, authed):
        r = authed.post("/api/v1/tags", json={"name": "   "})
        assert r.status_code == 422

    def test_delete_tag(self, authed):
        tag = authed.post("/api/v1/tags", json={"name": "research"}).json()["data"]
        assert authed.delete(f"/api/v1/tags/{tag['id']}").status_code == 204
        assert authed.get("/api/v1/tags").json()["data"] == []

    def test_delete_unknown_returns_404(self, authed):
        assert authed.delete("/api/v1/tags/no-such-id").status_code == 404

    def test_tag_item_and_filter(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        r = authed.post(f"/api/v1/items/{item_id}/tags", json={"name": "starmarked"})
        assert r.status_code == 201

        tagged = authed.get("/api/v1/items?tag=starmarked").json()["data"]
        assert len(tagged) == 1
        assert tagged[0]["id"] == item_id
        assert tagged[0]["tags"] == ["starmarked"]

        counts = authed.get("/api/v1/tags").json()["data"]
        assert counts[0]["item_count"] == 1

    def test_untag_item(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        tag = authed.post(f"/api/v1/items/{item_id}/tags", json={"name": "t"}).json()["data"]
        assert authed.delete(f"/api/v1/items/{item_id}/tags/{tag['id']}").status_code == 204
        assert authed.get("/api/v1/items?tag=t").json()["data"] == []

    def test_untag_not_applied_returns_404(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        tag = authed.post("/api/v1/tags", json={"name": "unused"}).json()["data"]
        r = authed.delete(f"/api/v1/items/{item_id}/tags/{tag['id']}")
        assert r.status_code == 404

    def test_deleting_tag_removes_from_items(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        tag = authed.post(f"/api/v1/items/{item_id}/tags", json={"name": "gone"}).json()["data"]
        authed.delete(f"/api/v1/tags/{tag['id']}")
        item = authed.get(f"/api/v1/items/{item_id}").json()["data"]
        assert item["tags"] == []


class TestNotes:
    def test_no_note_returns_404(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        assert authed.get(f"/api/v1/items/{item_id}/note").status_code == 404

    def test_put_creates_note(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        r = authed.put(f"/api/v1/items/{item_id}/note", json={"body": "Worth rereading."})
        assert r.status_code == 200
        note = r.json()["data"]
        assert note["body"] == "Worth rereading."
        assert note["created_at"] == note["updated_at"]

    def test_put_replaces_note(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        authed.put(f"/api/v1/items/{item_id}/note", json={"body": "v1"})
        r = authed.put(f"/api/v1/items/{item_id}/note", json={"body": "v2"})
        assert r.json()["data"]["body"] == "v2"

    def test_note_appears_in_item_detail(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        authed.put(f"/api/v1/items/{item_id}/note", json={"body": "annotated"})
        detail = authed.get(f"/api/v1/items/{item_id}").json()["data"]
        assert detail["note"]["body"] == "annotated"

    def test_delete_note(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        authed.put(f"/api/v1/items/{item_id}/note", json={"body": "x"})
        assert authed.delete(f"/api/v1/items/{item_id}/note").status_code == 204
        assert authed.get(f"/api/v1/items/{item_id}/note").status_code == 404

    def test_delete_missing_note_returns_404(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        assert authed.delete(f"/api/v1/items/{item_id}/note").status_code == 404

    def test_note_on_unknown_item_returns_404(self, authed):
        assert authed.put("/api/v1/items/nope/note", json={"body": "x"}).status_code == 404


class TestConfig:
    def test_defaults(self, authed):
        config = authed.get("/api/v1/config").json()["data"]
        assert config == {
            "default_poll_interval_minutes": 60,
            "reader_mode_enabled": True,
            "default_theme": "system",
            "items_per_page": 50,
            "mark_read_on_open": True,
        }

    def test_patch_persists(self, authed):
        r = authed.patch(
            "/api/v1/config",
            json={"default_theme": "dark", "items_per_page": 25},
        )
        assert r.status_code == 200
        config = authed.get("/api/v1/config").json()["data"]
        assert config["default_theme"] == "dark"
        assert config["items_per_page"] == 25
        assert config["mark_read_on_open"] is True  # untouched

    def test_invalid_theme_returns_400(self, authed):
        r = authed.patch("/api/v1/config", json={"default_theme": "sepia"})
        assert r.status_code == 400

    def test_empty_patch_returns_422(self, authed):
        r = authed.patch("/api/v1/config", json={})
        assert r.status_code == 422
