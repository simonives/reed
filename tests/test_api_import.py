# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import json
import os
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

MINIMAL_BACKUP = {
    "version": 1,
    "exported_at": "2026-07-17T00:00:00+00:00",
    "feeds": [],
    "items": [],
    "notes": [],
    "tags": [],
    "config": {},
}

CONFIRM_HEADER = {"X-Confirm-Destructive": "true"}


class TestPreview:
    def test_returns_candidates_and_unparseable(self, authed):
        r = authed.post(
            "/api/v1/import/opml/preview",
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
            "/api/v1/import/opml/preview",
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
            "/api/v1/import/opml/preview",
            files={"file": ("feeds.opml", opml, "application/xml")},
        )
        by_url = {c["url"]: c for c in r.json()["data"]["candidates"]}
        assert by_url["https://example.com/feed.rss"]["already_subscribed"] is True
        assert by_url["https://new.com/feed.rss"]["already_subscribed"] is False

    def test_invalid_opml_returns_422(self, authed):
        r = authed.post(
            "/api/v1/import/opml/preview",
            files={"file": ("bad.opml", b"not xml at all", "application/xml")},
        )
        assert r.status_code == 422

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.post(
            "/api/v1/import/opml/preview",
            files={"file": ("feeds.opml", SIMPLE_OPML, "application/xml")},
        )
        assert r.status_code == 401

    def test_preview_over_size_limit_returns_413(self, authed, monkeypatch):
        import reed.api.import_ as import_module

        monkeypatch.setattr(import_module, "MAX_OPML_BYTES", 10)
        r = authed.post(
            "/api/v1/import/opml/preview",
            files={"file": ("feeds.opml", b"<opml>" + b"x" * 11, "application/xml")},
        )
        assert r.status_code == 413

    def test_preview_over_1mb_under_configured_limit_is_accepted(self, authed):
        """Regression coverage at a realistic size: an OPML file between 1MB
        (Starlette's MultiPartParser default max_part_size) and
        MAX_OPML_BYTES (2MB) must be accepted and parsed, not just the tiny
        payloads the other tests in this class use."""
        big_opml = (
            b'<?xml version="1.0"?><opml version="2.0"><body>'
            + b'<outline type="rss" text="F" xmlUrl="https://x.example/f.rss"/>'
            + b"<!--"
            + b"x" * 1_200_000
            + b"-->"
            + b"</body></opml>"
        )
        assert len(big_opml) > 1_048_576
        r = authed.post(
            "/api/v1/import/opml/preview",
            files={"file": ("feeds.opml", big_opml, "application/xml")},
        )
        assert r.status_code == 200


class TestImportOpml:
    def test_adds_new_feed_with_tags(self, authed):
        body = {
            "feeds": [
                {"url": "https://new.com/feed.rss", "title": "New Feed", "tags": ["tech", "news"]},
            ]
        }
        with patched_feed_fetch(module="reed.api.import_"):
            r = authed.post("/api/v1/import/opml", json=body)
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
        r = authed.post("/api/v1/import/opml", json=body)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["added"] == 0
        assert data["skipped"] == 1

    def test_empty_selection_returns_all_zero(self, authed):
        r = authed.post("/api/v1/import/opml", json={"feeds": []})
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
            with patched_feed_fetch(module="reed.api.import_"):
                r = authed.post("/api/v1/import/opml", json=body)
        finally:
            reed_client.app.state.graph.create_feed = original

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["added"] == 1
        assert len(data["failed"]) == 1
        assert data["failed"][0]["url"] == "https://fail.com/feed.rss"

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.post("/api/v1/import/opml", json={"feeds": []})
        assert r.status_code == 401

    def test_skips_and_reports_url_that_is_not_a_feed(self, authed):
        """#139 regression guard: OPML import must validate each URL is a real
        feed before creating a Feed node, mirroring subscribe()'s validation
        and the old api/opml.py's import_opml. A URL that fetches successfully
        but returns non-feed HTML (e.g. moved/stale, common in OPML exports
        from other readers) must be skipped and reported in failed[], not
        silently turned into a Feed node the poller can never ingest.
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
        with patched_feed_fetch(module="reed.api.import_", side_effect=_fetch):
            r = authed.post("/api/v1/import/opml", json=body)

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

    def test_imported_feed_uses_fetched_metadata_for_description_and_site_url(self, authed):
        """#155 regression guard: OPML import previously discarded the parsed
        feed's metadata, hardcoding description="" and site_url="". The
        created feed must instead carry the fetched feed's actual description
        and link, matching subscribe()'s behaviour in feeds.py. Title priority
        stays with the OPML outline's own title (client-submitted), falling
        back to the feed's title, falling back to the URL, per #155's
        recommended fix — this is exercised separately by
        test_adds_new_feed_with_tags, which asserts the outline title wins.
        """
        body = {
            "feeds": [
                {"url": "https://new.com/feed.rss", "title": "Outline Title", "tags": []},
            ]
        }
        with patched_feed_fetch(module="reed.api.import_"):
            r = authed.post("/api/v1/import/opml", json=body)
        assert r.status_code == 200
        assert r.json()["data"]["added"] == 1

        feeds = authed.get("/api/v1/feeds").json()["data"]
        feed = next((f for f in feeds if f["url"] == "https://new.com/feed.rss"), None)
        assert feed is not None
        # SAMPLE_RSS (conftest's default mock response) declares these values.
        assert feed["description"] == "A test feed"
        assert feed["site_url"] == "https://example.com"
        # Outline title takes priority over the feed's own <title>Test Feed</title>.
        assert feed["title"] == "Outline Title"


class TestImportBackup:
    def test_valid_backup_with_confirm_header_returns_summary(self, authed):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data == {"feeds": 0, "items": 0, "notes": 0, "tags": 0}

    def test_missing_confirm_header_returns_400(self, authed):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
        )
        assert r.status_code == 400

    def test_confirm_header_wrong_value_returns_400(self, authed):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers={"X-Confirm-Destructive": "yes"},
        )
        assert r.status_code == 400

    def test_missing_file_field_returns_400(self, authed):
        """A valid X-Confirm-Destructive header but a multipart body with no
        'file' field must return a clean 400, not an unhandled 500 from
        Starlette's FormData.__getitem__ raising KeyError."""
        r = authed.post(
            "/api/v1/import/backup",
            files={"not_file": ("backup.json", b"{}", "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 400
        assert "file" in r.json()["error"]["message"].lower()

    def test_missing_version_key_returns_400(self, authed):
        bad = {k: v for k, v in MINIMAL_BACKUP.items() if k != "version"}
        payload = json.dumps(bad).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 400

    def test_missing_feeds_key_returns_400(self, authed):
        bad = {k: v for k, v in MINIMAL_BACKUP.items() if k != "feeds"}
        payload = json.dumps(bad).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 400

    def test_missing_config_key_restores_successfully(self, authed):
        """Judgement call 1: a /export/json-shaped backup (no 'config' key) must
        still be restorable, so a user who only ever kept the personal-data
        export isn't locked out of their own data."""
        no_config = {k: v for k, v in MINIMAL_BACKUP.items() if k != "config"}
        payload = json.dumps(no_config).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 200

    def test_missing_config_key_leaves_settings_at_defaults(self, authed):
        no_config = {k: v for k, v in MINIMAL_BACKUP.items() if k != "config"}
        payload = json.dumps(no_config).encode()
        authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        config = authed.get("/api/v1/config").json()["data"]
        # effective_config() merges stored (now empty) config with CONFIG_DEFAULTS,
        # so every key should read back as its documented default.
        assert config["reader_mode_enabled"] is True
        assert config["default_theme"] == "system"

    def test_invalid_json_returns_400(self, authed):
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", b"not json{{{", "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 400

    def test_file_over_limit_returns_413(self, authed, monkeypatch):
        import reed.api.import_ as import_module

        monkeypatch.setattr(import_module, "MAX_RESTORE_BYTES", 10)
        payload = b"x" * 12
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 413

    def test_backup_over_1mb_restores_successfully(self, authed):
        """Regression coverage: a backup file part over 1MB (Starlette's
        MultiPartParser default max_part_size, verified against the
        installed version — see Request._get_form()) must restore
        successfully as long as it's under MAX_RESTORE_BYTES (50MB). A
        realistic backup easily exceeds 1MB, so this guards the whole
        upload path at a realistic size rather than only the tiny payloads
        the other tests in this class use."""
        padded = {**MINIMAL_BACKUP, "_padding": "x" * 1_200_000}
        payload = json.dumps(padded).encode()
        assert len(payload) > 1_048_576
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 200

    def test_file_over_configured_limit_returns_413_at_realistic_size(self, authed, monkeypatch):
        """Same as test_file_over_limit_returns_413 but at a realistic size
        (MB-scale, not 10 bytes) so this exercises the same code path a real
        oversized upload would hit, not just the boundary check in isolation."""
        import reed.api.import_ as import_module

        monkeypatch.setattr(import_module, "MAX_RESTORE_BYTES", 2_000_000)
        payload = b"x" * 3_000_000
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 413

    def test_missing_header_rejected_before_oversized_file_is_checked(self, authed, monkeypatch):
        """Adversarial review finding: the confirm-header check must happen
        before the file is parsed/size-checked, not after. If an oversized
        file without the header still 413s, the header check ran too late
        (or not at all) — it must 400 instead, regardless of file size."""
        import reed.api.import_ as import_module

        monkeypatch.setattr(import_module, "MAX_RESTORE_BYTES", 10)
        payload = b"x" * 10_000
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            # no X-Confirm-Destructive header
        )
        assert r.status_code == 400

    def test_no_auth_returns_401(self, reed_client):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = reed_client.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 401

    def test_round_trip_with_data(self, authed, reed_client):
        graph = reed_client.app.state.graph
        graph.create_feed(
            url="https://example.com/feed",
            title="Example",
            description="",
            site_url="",
        )
        export_r = authed.get("/api/v1/export/backup")
        assert export_r.status_code == 200
        restore_r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", export_r.content, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert restore_r.status_code == 200
        assert restore_r.json()["data"]["feeds"] == 1

    def test_restore_accepts_legacy_raw_format(self, authed):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 200

    def test_restore_rejects_envelope_with_non_dict_data(self, authed):
        payload = json.dumps({"data": [1, 2, 3], "meta": {}}).encode()
        r = authed.post(
            "/api/v1/import/backup",
            files={"file": ("backup.json", payload, "application/json")},
            headers=CONFIRM_HEADER,
        )
        assert r.status_code == 400


# --- Feedly integration (skipped when fixture unavailable) ---
#
# A real Feedly OPML export exercises quirks synthetic fixtures don't
# reproduce. Point REED_FEEDLY_FIXTURE_DIR at a local directory containing
# one to run this locally; it's not part of CI or the repo.

_FEEDLY_INBOX = (
    Path(os.environ["REED_FEEDLY_FIXTURE_DIR"]) if "REED_FEEDLY_FIXTURE_DIR" in os.environ else None
)
_FEEDLY_OPML = (
    next(_FEEDLY_INBOX.glob("*.opml"), None) if _FEEDLY_INBOX and _FEEDLY_INBOX.exists() else None
)


@pytest.mark.skipif(_FEEDLY_OPML is None, reason="REED_FEEDLY_FIXTURE_DIR not set or has no .opml fixture")
class TestFeedlyIntegration:
    def test_feedly_preview_parses_successfully(self, authed):
        r = authed.post(
            "/api/v1/import/opml/preview",
            files={"file": (_FEEDLY_OPML.name, _FEEDLY_OPML.read_bytes(), "application/xml")},
        )
        assert r.status_code == 200
        assert len(r.json()["data"]["candidates"]) > 0

    def test_feedly_import_and_export_round_trip(self, authed):
        preview = authed.post(
            "/api/v1/import/opml/preview",
            files={"file": (_FEEDLY_OPML.name, _FEEDLY_OPML.read_bytes(), "application/xml")},
        ).json()["data"]
        candidates = [c for c in preview["candidates"] if not c["already_subscribed"]][:5]

        with patched_feed_fetch(module="reed.api.import_"):
            r = authed.post(
                "/api/v1/import/opml",
                json={
                    "feeds": [
                        {"url": c["url"], "title": c["title"], "tags": c["tags"]}
                        for c in candidates
                    ]
                },
            )
        assert r.status_code == 200
        assert r.json()["data"]["added"] >= 1

        xml = authed.get("/api/v1/export/opml").content
        result = parse_opml(xml)
        exported_urls = {c.url for c in result.candidates}
        for c in candidates:
            assert c["url"] in exported_urls
