# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from pathlib import Path

import pytest

from reed.opml import parse_opml

from .conftest import mock_http_response, patched_feed_fetch

NON_FEED_HTML = b"<html><body><h1>Page moved</h1></body></html>"

SIMPLE_OPML = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline text="Tech">
      <outline type="rss" text="HN" xmlUrl="https://news.ycombinator.com/rss"/>
    </outline>
    <outline type="rss" text="New Feed" xmlUrl="https://new.com/feed.rss"/>
    <outline text="orphan leaf"/>
  </body>
</opml>"""


class TestPreview:
    def test_returns_candidates_and_unparseable(self, authed):
        r = authed.post(
            "/api/v1/opml/preview",
            files={"file": ("feeds.opml", SIMPLE_OPML, "application/xml")},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["unparseable"] == 1
        assert len(data["candidates"]) == 2
        urls = {c["url"] for c in data["candidates"]}
        assert "https://news.ycombinator.com/rss" in urls
        assert "https://new.com/feed.rss" in urls

    def test_folder_tags_included_in_candidate(self, authed):
        r = authed.post(
            "/api/v1/opml/preview",
            files={"file": ("feeds.opml", SIMPLE_OPML, "application/xml")},
        )
        data = r.json()["data"]
        hn = next(c for c in data["candidates"] if c["url"] == "https://news.ycombinator.com/rss")
        assert hn["tags"] == ["Tech"]

    def test_already_subscribed_flagged(self, authed, subscribed_feed):
        opml = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline type="rss" text="Example" xmlUrl="https://example.com/feed.rss"/>
    <outline type="rss" text="New" xmlUrl="https://new.com/feed.rss"/>
  </body>
</opml>"""
        r = authed.post(
            "/api/v1/opml/preview",
            files={"file": ("feeds.opml", opml, "application/xml")},
        )
        by_url = {c["url"]: c for c in r.json()["data"]["candidates"]}
        assert by_url["https://example.com/feed.rss"]["already_subscribed"] is True
        assert by_url["https://new.com/feed.rss"]["already_subscribed"] is False

    def test_invalid_opml_returns_422(self, authed):
        r = authed.post(
            "/api/v1/opml/preview",
            files={"file": ("bad.opml", b"not xml at all", "application/xml")},
        )
        assert r.status_code == 422

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.post(
            "/api/v1/opml/preview",
            files={"file": ("feeds.opml", SIMPLE_OPML, "application/xml")},
        )
        assert r.status_code == 401

    def test_preview_over_size_limit_returns_413(self, authed, monkeypatch):
        import reed.api.opml as opml_module

        monkeypatch.setattr(opml_module, "MAX_OPML_BYTES", 10)
        r = authed.post(
            "/api/v1/opml/preview",
            files={"file": ("feeds.opml", b"<opml>" + b"x" * 11, "application/xml")},
        )
        assert r.status_code == 413


class TestImport:
    def test_adds_new_feed_with_tags(self, authed):
        body = {
            "feeds": [
                {"url": "https://new.com/feed.rss", "title": "New Feed", "tags": ["tech", "news"]},
            ]
        }
        with patched_feed_fetch(module="reed.api.opml"):
            r = authed.post("/api/v1/opml/import", json=body)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["added"] == 1
        assert data["skipped"] == 0
        assert data["failed"] == []
        feeds = authed.get("/api/v1/feeds").json()["data"]
        feed = next((f for f in feeds if f["url"] == "https://new.com/feed.rss"), None)
        assert feed is not None
        assert set(feed["tags"]) == {"tech", "news"}

    def test_skips_existing_feed(self, authed, subscribed_feed):
        body = {
            "feeds": [
                {"url": "https://example.com/feed.rss", "title": "Example", "tags": []},
            ]
        }
        r = authed.post("/api/v1/opml/import", json=body)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["added"] == 0
        assert data["skipped"] == 1

    def test_empty_selection_returns_all_zero(self, authed):
        r = authed.post("/api/v1/opml/import", json={"feeds": []})
        assert r.status_code == 200
        assert r.json()["data"] == {"added": 0, "skipped": 0, "failed": []}

    def test_continues_after_one_failure(self, authed, reed_client):
        original = reed_client.app.state.graph.create_feed

        def _patched(*args, **kwargs):
            if kwargs.get("url") == "https://fail.com/feed.rss":
                raise RuntimeError("Simulated DB error")
            return original(*args, **kwargs)

        reed_client.app.state.graph.create_feed = _patched
        try:
            body = {
                "feeds": [
                    {"url": "https://fail.com/feed.rss", "title": "Fail", "tags": []},
                    {"url": "https://good.com/feed.rss", "title": "Good", "tags": []},
                ]
            }
            with patched_feed_fetch(module="reed.api.opml"):
                r = authed.post("/api/v1/opml/import", json=body)
        finally:
            reed_client.app.state.graph.create_feed = original

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["added"] == 1
        assert len(data["failed"]) == 1
        assert data["failed"][0]["url"] == "https://fail.com/feed.rss"

    def test_skips_and_reports_url_that_is_not_a_feed(self, authed):
        """#139: OPML import must validate each URL is a real feed before
        creating a Feed node, mirroring the validation subscribe() got in #138.
        A URL that returns non-feed HTML (e.g. moved/stale, common in OPML
        exports from other readers) must be skipped and reported in failed[],
        not silently turned into a Feed node the poller can never ingest.
        """

        def _fetch(url, **kwargs):
            if "bad.com" in str(url):
                return mock_http_response(content=NON_FEED_HTML)
            return mock_http_response()

        body = {
            "feeds": [
                {"url": "https://good.com/feed.rss", "title": "Good", "tags": []},
                {"url": "https://bad.com/moved", "title": "Bad", "tags": []},
            ]
        }
        with patched_feed_fetch(module="reed.api.opml", side_effect=_fetch):
            r = authed.post("/api/v1/opml/import", json=body)

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["added"] == 1
        assert data["skipped"] == 0
        assert len(data["failed"]) == 1
        assert data["failed"][0]["url"] == "https://bad.com/moved"

        feeds = authed.get("/api/v1/feeds").json()["data"]
        urls = {f["url"] for f in feeds}
        assert "https://good.com/feed.rss" in urls
        assert "https://bad.com/moved" not in urls

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.post("/api/v1/opml/import", json={"feeds": []})
        assert r.status_code == 401


class TestExport:
    def test_returns_xml_content_type(self, authed, subscribed_feed):
        r = authed.get("/api/v1/opml/export")
        assert r.status_code == 200
        assert "application/xml" in r.headers["content-type"]

    def test_returns_attachment_disposition_with_filename(self, authed, subscribed_feed):
        r = authed.get("/api/v1/opml/export")
        disposition = r.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "reed-feeds-" in disposition
        assert ".opml" in disposition

    def test_body_contains_subscribed_feed(self, authed, subscribed_feed):
        r = authed.get("/api/v1/opml/export")
        assert b"<opml" in r.content
        assert b"https://example.com/feed.rss" in r.content

    def test_export_with_no_feeds_is_valid_opml(self, authed):
        r = authed.get("/api/v1/opml/export")
        assert r.status_code == 200
        assert b"<opml" in r.content

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/opml/export")
        assert r.status_code == 401


# --- Feedly integration (skipped when fixture unavailable) ---

_FEEDLY_INBOX = Path.home() / "Documents/Obsidian/Simon's Garden/Inbox"
_FEEDLY_OPML = next(_FEEDLY_INBOX.glob("*.opml"), None) if _FEEDLY_INBOX.exists() else None


@pytest.mark.skipif(_FEEDLY_OPML is None, reason="Feedly OPML fixture not in Simon's Garden Inbox")
class TestFeedlyIntegration:
    def test_feedly_preview_parses_successfully(self, authed):
        r = authed.post(
            "/api/v1/opml/preview",
            files={"file": (_FEEDLY_OPML.name, _FEEDLY_OPML.read_bytes(), "application/xml")},
        )
        assert r.status_code == 200
        assert len(r.json()["data"]["candidates"]) > 0

    def test_feedly_import_and_export_round_trip(self, authed):
        preview = authed.post(
            "/api/v1/opml/preview",
            files={"file": (_FEEDLY_OPML.name, _FEEDLY_OPML.read_bytes(), "application/xml")},
        ).json()["data"]
        candidates = [c for c in preview["candidates"] if not c["already_subscribed"]][:5]

        r = authed.post(
            "/api/v1/opml/import",
            json={
                "feeds": [
                    {"url": c["url"], "title": c["title"], "tags": c["tags"]} for c in candidates
                ]
            },
        )
        assert r.status_code == 200
        assert r.json()["data"]["added"] >= 1

        xml = authed.get("/api/v1/opml/export").content
        result = parse_opml(xml)
        exported_urls = {c.url for c in result.candidates}
        for c in candidates:
            assert c["url"] in exported_urls
