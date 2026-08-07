# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations


class TestExportOpml:
    def test_returns_xml_content_type(self, authed, subscribed_feed):
        r = authed.get("/api/v1/export/opml")
        assert r.status_code == 200
        assert "application/xml" in r.headers["content-type"]

    def test_returns_attachment_disposition_with_filename(self, authed, subscribed_feed):
        r = authed.get("/api/v1/export/opml")
        disposition = r.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "reed-feeds-" in disposition
        assert ".opml" in disposition

    def test_body_contains_subscribed_feed(self, authed, subscribed_feed):
        r = authed.get("/api/v1/export/opml")
        assert b"<opml" in r.content
        assert b"https://example.com/feed.rss" in r.content

    def test_export_with_no_feeds_is_valid_opml(self, authed):
        r = authed.get("/api/v1/export/opml")
        assert r.status_code == 200
        assert b"<opml" in r.content

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/export/opml")
        assert r.status_code == 401


class TestExportBackup:
    def test_returns_200(self, authed):
        r = authed.get("/api/v1/export/backup")
        assert r.status_code == 200

    def test_content_disposition_is_attachment(self, authed):
        r = authed.get("/api/v1/export/backup")
        assert "attachment" in r.headers["content-disposition"]
        assert "reed-backup-" in r.headers["content-disposition"]
        assert ".json" in r.headers["content-disposition"]

    def test_response_is_envelope(self, authed):
        r = authed.get("/api/v1/export/backup")
        body = r.json()
        assert "data" in body
        assert "meta" in body

    def test_data_key_contains_backup_fields_including_config(self, authed):
        r = authed.get("/api/v1/export/backup")
        data = r.json()["data"]
        for key in ("version", "feeds", "items", "notes", "tags", "config"):
            assert key in data

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/export/backup")
        assert r.status_code == 401


class TestExportJson:
    def test_returns_200(self, authed):
        r = authed.get("/api/v1/export/json")
        assert r.status_code == 200

    def test_content_disposition_is_attachment(self, authed):
        r = authed.get("/api/v1/export/json")
        assert "attachment" in r.headers["content-disposition"]
        assert ".json" in r.headers["content-disposition"]

    def test_response_omits_config_key(self, authed):
        r = authed.get("/api/v1/export/json")
        data = r.json()["data"]
        assert "config" not in data
        for key in ("version", "feeds", "items", "notes", "tags"):
            assert key in data

    def test_backup_and_json_differ_only_by_config(self, authed):
        backup_data = authed.get("/api/v1/export/backup").json()["data"]
        json_data = authed.get("/api/v1/export/json").json()["data"]
        assert set(backup_data.keys()) - set(json_data.keys()) == {"config"}

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/export/json")
        assert r.status_code == 401
