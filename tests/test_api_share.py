# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx


class TestListShareTargets:
    def test_includes_seeded_copy_targets(self, authed):
        r = authed.get("/api/v1/share/targets")
        assert r.status_code == 200
        types = sorted(t["type"] for t in r.json()["data"])
        assert types == ["copy_link", "copy_markdown"]

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/share/targets")
        assert r.status_code == 401

    def test_list_redacts_secret_and_token(self, authed):
        """Code-review finding: GET /share/targets returned config verbatim,
        including webhook secrets and Raindrop tokens, even though the
        frontend never reads those fields — pure unnecessary exposure."""
        authed.post(
            "/api/v1/share/targets",
            json={
                "type": "webhook",
                "name": "Signed hook",
                "config": {"url": "https://example.com/hook", "secret": "topsecret"},
            },
        )
        authed.post(
            "/api/v1/share/targets",
            json={
                "type": "raindrop",
                "name": "Raindrop",
                "config": {"token": "tok-abc", "collection_id": "123"},
            },
        )
        r = authed.get("/api/v1/share/targets")
        assert r.status_code == 200
        serialized = str(r.json())
        assert "topsecret" not in serialized
        assert "tok-abc" not in serialized
        for target in r.json()["data"]:
            assert "secret" not in target["config"]
            assert "token" not in target["config"]


class TestCreateShareTarget:
    def test_creates_webhook_target(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "webhook",
                "name": "My hook",
                "config": {"url": "https://example.com/hook"},
            },
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["type"] == "webhook"
        assert data["config"] == {"url": "https://example.com/hook"}

    def test_creates_raindrop_target(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "raindrop",
                "name": "Raindrop",
                "config": {"token": "tok", "collection_id": "123"},
            },
        )
        assert r.status_code == 201

    def test_raindrop_numeric_string_collection_id_is_coerced_to_int(self, authed):
        """#172/#174 — collection_id arrives as a JSON string (e.g. from a
        form input) but Raindrop's API expects a numeric $id. The
        Pydantic-coerced value, not the raw request dict, must be what gets
        persisted, so a later GET reflects the corrected type."""
        r = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "raindrop",
                "name": "Raindrop",
                "config": {"token": "tok", "collection_id": "123"},
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["config"]["collection_id"] == 123

    def test_raindrop_non_numeric_collection_id_returns_422(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "raindrop",
                "name": "Raindrop",
                "config": {"token": "tok", "collection_id": "not-a-number"},
            },
        )
        assert r.status_code == 422

    def test_creates_webhook_target_with_optional_signing_secret(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "webhook",
                "name": "Signed hook",
                "config": {"url": "https://example.com/hook", "secret": "shh"},
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["config"]["secret"] == "shh"

    def test_creates_webhook_target_without_secret(self, authed):
        """secret is optional — omitting it must not be a validation error."""
        r = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "webhook",
                "name": "Unsigned hook",
                "config": {"url": "https://example.com/hook"},
            },
        )
        assert r.status_code == 201

    def test_webhook_missing_url_returns_422(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={"type": "webhook", "name": "Bad", "config": {}},
        )
        assert r.status_code == 422

    def test_raindrop_missing_token_returns_422(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={"type": "raindrop", "name": "Bad", "config": {"collection_id": "123"}},
        )
        assert r.status_code == 422

    def test_copy_target_with_nonempty_config_returns_422(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={"type": "copy_link", "name": "Bad", "config": {"unexpected": "value"}},
        )
        assert r.status_code == 422

    def test_copy_link_creation_is_rejected(self, authed):
        """Code-review finding: the delete-protection 409 guard keys off
        `type` alone, so any user-created copy_link/copy_markdown target
        becomes permanently undeletable. The spec's stated intent is that
        copy types "aren't user-creatable beyond the seeded pair" — closing
        this at creation time closes the bypass with no schema change."""
        r = authed.post(
            "/api/v1/share/targets",
            json={"type": "copy_link", "name": "Another copy target", "config": {}},
        )
        assert r.status_code == 422

    def test_copy_markdown_creation_is_rejected(self, authed):
        r = authed.post(
            "/api/v1/share/targets",
            json={"type": "copy_markdown", "name": "Another copy target", "config": {}},
        )
        assert r.status_code == 422

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.post(
            "/api/v1/share/targets",
            json={"type": "webhook", "name": "W", "config": {"url": "https://x.com"}},
        )
        assert r.status_code == 401


class TestUpdateShareTarget:
    def test_updates_name_and_enabled(self, authed):
        created = authed.post(
            "/api/v1/share/targets",
            json={"type": "webhook", "name": "W", "config": {"url": "https://example.com"}},
        ).json()["data"]
        r = authed.patch(
            f"/api/v1/share/targets/{created['id']}",
            json={"name": "Renamed", "enabled": False},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "Renamed"
        assert data["enabled"] is False

    def test_returns_404_for_unknown_id(self, authed):
        r = authed.patch(
            "/api/v1/share/targets/00000000-0000-0000-0000-000000000000",
            json={"name": "X"},
        )
        assert r.status_code == 404

    def test_patch_raindrop_numeric_string_collection_id_is_coerced_to_int(self, authed):
        """Code-review finding on PR #183 — create_share_target's int
        coercion was tested, but update_share_target's (the path a user
        actually hits when correcting an existing target) wasn't."""
        created = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "raindrop",
                "name": "R",
                "config": {"token": "tok", "collection_id": "111"},
            },
        ).json()["data"]
        r = authed.patch(
            f"/api/v1/share/targets/{created['id']}",
            json={"config": {"token": "tok", "collection_id": "456"}},
        )
        assert r.status_code == 200
        assert r.json()["data"]["config"]["collection_id"] == 456

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.patch("/api/v1/share/targets/some-id", json={"name": "X"})
        assert r.status_code == 401


class TestDeleteShareTarget:
    def test_deletes_target(self, authed):
        created = authed.post(
            "/api/v1/share/targets",
            json={"type": "webhook", "name": "W", "config": {"url": "https://example.com"}},
        ).json()["data"]
        r = authed.delete(f"/api/v1/share/targets/{created['id']}")
        assert r.status_code == 204
        assert authed.get("/api/v1/share/targets/does-not-matter").status_code in (404, 405)

    def test_returns_404_for_unknown_id(self, authed):
        r = authed.delete("/api/v1/share/targets/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_seeded_copy_link_cannot_be_deleted(self, authed):
        """Adversarial review finding: the seeded copy targets have no
        recreate path in the UI, so deleting one via the API must be
        rejected rather than silently permitted."""
        targets = authed.get("/api/v1/share/targets").json()["data"]
        copy_target = next(t for t in targets if t["type"] == "copy_link")
        r = authed.delete(f"/api/v1/share/targets/{copy_target['id']}")
        assert r.status_code == 409
        # And it must still be there afterwards.
        remaining = {t["id"] for t in authed.get("/api/v1/share/targets").json()["data"]}
        assert copy_target["id"] in remaining

    def test_seeded_copy_markdown_cannot_be_deleted(self, authed):
        targets = authed.get("/api/v1/share/targets").json()["data"]
        copy_target = next(t for t in targets if t["type"] == "copy_markdown")
        r = authed.delete(f"/api/v1/share/targets/{copy_target['id']}")
        assert r.status_code == 409

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.delete("/api/v1/share/targets/some-id")
        assert r.status_code == 401


class TestShareDelivery:
    def _webhook_target(self, authed):
        return authed.post(
            "/api/v1/share/targets",
            json={
                "type": "webhook",
                "name": "W",
                "config": {"url": "https://hooks.example.com/in"},
            },
        ).json()["data"]

    def _raindrop_target(self, authed):
        return authed.post(
            "/api/v1/share/targets",
            json={
                "type": "raindrop",
                "name": "R",
                "config": {"token": "tok", "collection_id": "123"},
            },
        ).json()["data"]

    def test_share_item_offloads_graph_reads_to_thread(self, authed, subscribed_feed):
        """Security review on PR #183 — share_item is the one async def
        endpoint in share.py that made synchronous graph.* calls directly
        on the event-loop thread. With recompute_derived_edges (#168) now
        holding _conn_lock across its full body, an un-offloaded call here
        could block the whole ASGI event loop behind an in-flight recompute
        rather than just this request."""
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(200, request=httpx.Request("POST", "https://hooks.example.com/in"))
        with (
            patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread,
            patch("reed.api.share.safe_post", AsyncMock(return_value=ok)),
        ):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 200
        graph = authed.app.state.graph
        offloaded = [c.args[0] for c in mock_to_thread.call_args_list]
        assert graph.get_share_target in offloaded
        assert graph.get_item in offloaded
        assert graph.get_item_topics in offloaded

    def test_webhook_delivery_success(self, authed, subscribed_feed):
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(200, request=httpx.Request("POST", "https://hooks.example.com/in"))
        with patch("reed.api.share.safe_post", AsyncMock(return_value=ok)):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 200
        assert r.json()["data"] == {"shared": True}

    def test_webhook_payload_shape(self, authed, subscribed_feed):
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(200, request=httpx.Request("POST", "https://hooks.example.com/in"))
        mock_post = AsyncMock(return_value=ok)
        with patch("reed.api.share.safe_post", mock_post):
            authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["event"] == "share"
        assert set(payload["item"].keys()) >= {
            "title",
            "url",
            "excerpt",
            "author",
            "published_at",
            "feed",
            "tags",
            "topics",
        }
        assert "shared_at" in payload

    def test_webhook_payload_feed_url_is_actual_feed_url_not_uuid(self, authed, subscribed_feed):
        """Deviation from brief: `feed` must carry the feed's URL, not its
        opaque UUID primary key (feed_id). get_item now returns feed_url."""
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(200, request=httpx.Request("POST", "https://hooks.example.com/in"))
        mock_post = AsyncMock(return_value=ok)
        with patch("reed.api.share.safe_post", mock_post):
            authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        _, kwargs = mock_post.call_args
        feed = kwargs["json"]["item"]["feed"]
        assert feed["url"] == subscribed_feed["url"]

    def test_webhook_without_secret_sends_no_signature_header(self, authed, subscribed_feed):
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(200, request=httpx.Request("POST", "https://hooks.example.com/in"))
        mock_post = AsyncMock(return_value=ok)
        with patch("reed.api.share.safe_post", mock_post):
            authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        _, kwargs = mock_post.call_args
        assert "X-Reed-Signature" not in (kwargs.get("headers") or {})

    def test_webhook_with_secret_sends_hmac_signature_header(self, authed, subscribed_feed):
        """Judgement call 2: an optional signing secret lets a receiver verify
        the payload actually came from this Reed instance."""
        import hashlib
        import hmac
        import json as jsonlib

        target = authed.post(
            "/api/v1/share/targets",
            json={
                "type": "webhook",
                "name": "Signed",
                "config": {"url": "https://hooks.example.com/in", "secret": "topsecret"},
            },
        ).json()["data"]
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(200, request=httpx.Request("POST", "https://hooks.example.com/in"))
        mock_post = AsyncMock(return_value=ok)
        with patch("reed.api.share.safe_post", mock_post):
            authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        _, kwargs = mock_post.call_args
        payload_bytes = jsonlib.dumps(
            kwargs["json"], separators=(",", ":"), sort_keys=True
        ).encode()
        expected = hmac.new(b"topsecret", payload_bytes, hashlib.sha256).hexdigest()
        assert kwargs["headers"]["X-Reed-Signature"] == expected

    def test_raindrop_delivery_coerces_legacy_string_collection_id(self, authed, subscribed_feed):
        """#172 remaining gap — a target created before this fix (or seeded
        directly at the graph layer, bypassing API validation) can still
        have a string collection_id persisted. Delivery must coerce it to
        numeric regardless of what's stored, not just at creation time."""
        graph = authed.app.state.graph
        legacy_target = graph.create_share_target(
            "raindrop", "Legacy", {"token": "tok", "collection_id": "123"}
        )
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(
            200,
            json={"result": True},
            request=httpx.Request("POST", "https://api.raindrop.io/rest/v1/raindrop"),
        )
        mock_post = AsyncMock(return_value=ok)
        with patch("reed.api.share.safe_post", mock_post):
            r = authed.post(
                "/api/v1/share", json={"item_id": item_id, "target_id": legacy_target["id"]}
            )
        assert r.status_code == 200
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["collection"] == {"$id": 123}

    def test_raindrop_delivery_non_numeric_legacy_collection_id_returns_422(
        self, authed, subscribed_feed
    ):
        """Code-review finding on PR #183 — the delivery-time coercion for
        legacy targets (test above) fixes the numeric-string case, but a
        legacy target whose collection_id is genuinely non-numeric (valid
        under the old str-typed RaindropConfig) hits a bare int() call and
        must not escape as an uncaught 500."""
        graph = authed.app.state.graph
        legacy_target = graph.create_share_target(
            "raindrop", "Legacy", {"token": "tok", "collection_id": "not-a-number"}
        )
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        r = authed.post(
            "/api/v1/share", json={"item_id": item_id, "target_id": legacy_target["id"]}
        )
        assert r.status_code == 422
        assert "error" in r.json()

    def test_raindrop_delivery_success(self, authed, subscribed_feed):
        target = self._raindrop_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(
            200,
            json={"result": True},
            request=httpx.Request("POST", "https://api.raindrop.io/rest/v1/raindrop"),
        )
        with patch("reed.api.share.safe_post", AsyncMock(return_value=ok)):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 200

    def test_raindrop_request_shape(self, authed, subscribed_feed):
        target = self._raindrop_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        ok = httpx.Response(
            200,
            json={"result": True},
            request=httpx.Request("POST", "https://api.raindrop.io/rest/v1/raindrop"),
        )
        mock_post = AsyncMock(return_value=ok)
        with patch("reed.api.share.safe_post", mock_post):
            authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        args, kwargs = mock_post.call_args
        assert args[1] == "https://api.raindrop.io/rest/v1/raindrop"
        # #172 — Raindrop's REST v1 $id field is numeric; a string collection_id
        # sent as "123" instead of 123 can be rejected or silently mis-filed.
        assert kwargs["json"]["collection"] == {"$id": 123}
        assert kwargs["headers"]["Authorization"] == "Bearer tok"

    def test_unknown_target_returns_404(self, authed, subscribed_feed):
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        r = authed.post(
            "/api/v1/share",
            json={"item_id": item_id, "target_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert r.status_code == 404

    def test_disabled_target_returns_404(self, authed, subscribed_feed):
        target = self._webhook_target(authed)
        authed.patch(f"/api/v1/share/targets/{target['id']}", json={"enabled": False})
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 404

    def test_copy_target_returns_422(self, authed, subscribed_feed):
        copy_target = next(
            t
            for t in authed.get("/api/v1/share/targets").json()["data"]
            if t["type"] == "copy_link"
        )
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": copy_target["id"]})
        assert r.status_code == 422

    def test_unknown_item_returns_404(self, authed):
        target = self._webhook_target(authed)
        r = authed.post(
            "/api/v1/share",
            json={"item_id": "00000000-0000-0000-0000-000000000000", "target_id": target["id"]},
        )
        assert r.status_code == 404

    def test_unsafe_url_returns_502_with_bad_gateway_code(self, authed, subscribed_feed):
        """Adversarial review: delivery failures now split 4xx-from-upstream
        (422, a misconfigured target) from network/5xx/blocked-redirect
        failures (502, an infra-level problem). A blocked SSRF-unsafe URL is
        an infra-level refusal, not the target's fault, so it stays 502."""
        from reed.http import UnsafeURLError

        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        with patch("reed.api.share.safe_post", AsyncMock(side_effect=UnsafeURLError("blocked"))):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "BAD_GATEWAY"

    def test_redirect_response_is_treated_as_delivery_failure(self, authed, subscribed_feed):
        """safe_post no longer follows redirects (Task 3) — a 3xx response
        must be surfaced as a failure, not silently treated as success. It's
        classified as 422 (a target configuration problem — wrong URL,
        service moved), the same bucket as a bad token, not 502 (an
        infra-level failure like a dropped connection)."""
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        redirect = httpx.Response(
            302,
            headers={"Location": "https://attacker.example/steal"},
            request=httpx.Request("POST", "https://hooks.example.com/in"),
        )
        with patch("reed.api.share.safe_post", AsyncMock(return_value=redirect)):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 422

    def test_raindrop_4xx_error_surfaces_as_422_not_502(self, authed, subscribed_feed):
        """Adversarial review finding: flattening every failure to 502 masks
        a misconfigured target (bad token) behind the same code as a real
        network/infra failure. A 401 from Raindrop means "fix your config,"
        which is a 422, not a 502."""
        target = self._raindrop_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        fail = httpx.Response(
            401,
            json={"result": False, "errorMessage": "Invalid token"},
            request=httpx.Request("POST", "https://api.raindrop.io/rest/v1/raindrop"),
        )
        with patch("reed.api.share.safe_post", AsyncMock(return_value=fail)):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 422
        assert "Invalid token" in r.json()["error"]["message"]

    def test_raindrop_5xx_error_surfaces_as_502(self, authed, subscribed_feed):
        target = self._raindrop_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        fail = httpx.Response(
            503,
            json={"result": False, "errorMessage": "Service unavailable"},
            request=httpx.Request("POST", "https://api.raindrop.io/rest/v1/raindrop"),
        )
        with patch("reed.api.share.safe_post", AsyncMock(return_value=fail)):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 502

    def test_connection_error_returns_502(self, authed, subscribed_feed):
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        with patch(
            "reed.api.share.safe_post",
            AsyncMock(side_effect=httpx.ConnectError("connection refused")),
        ):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 502

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.post("/api/v1/share", json={"item_id": "x", "target_id": "y"})
        assert r.status_code == 401

    def test_non_dict_json_error_body_does_not_crash(self, authed, subscribed_feed):
        """Code-review finding: _classify_response called body.get(...)
        without confirming the parsed JSON was a dict. A delivery target
        returning a valid-but-non-object JSON error body (e.g. a bare list)
        raised an uncaught AttributeError, surfacing as an unhandled 500
        instead of the intended 422/502 classification."""
        target = self._webhook_target(authed)
        item_id = authed.get("/api/v1/items").json()["data"][0]["id"]
        fail = httpx.Response(
            400,
            json=["bad request"],
            request=httpx.Request("POST", "https://hooks.example.com/in"),
        )
        with patch("reed.api.share.safe_post", AsyncMock(return_value=fail)):
            r = authed.post("/api/v1/share", json={"item_id": item_id, "target_id": target["id"]})
        assert r.status_code == 422
