# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import json


MINIMAL_BACKUP = {
    "version": 1,
    "exported_at": "2026-07-17T00:00:00+00:00",
    "feeds": [],
    "items": [],
    "notes": [],
    "tags": [],
    "config": {},
}


class TestExportEndpoint:
    def test_returns_200(self, authed):
        r = authed.get("/api/v1/data/export")
        assert r.status_code == 200

    def test_content_disposition_is_attachment(self, authed):
        r = authed.get("/api/v1/data/export")
        assert "attachment" in r.headers["content-disposition"]
        assert "reed-backup-" in r.headers["content-disposition"]
        assert ".json" in r.headers["content-disposition"]

    def test_response_has_required_keys(self, authed):
        r = authed.get("/api/v1/data/export")
        body = r.json()
        for key in ("version", "feeds", "items", "notes", "tags", "config"):
            assert key in body

    def test_no_auth_returns_401(self, reed_client):
        r = reed_client.get("/api/v1/data/export")
        assert r.status_code == 401


class TestRestoreEndpoint:
    def test_valid_backup_returns_summary(self, authed):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = authed.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", payload, "application/json")},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data == {"feeds": 0, "items": 0, "notes": 0, "tags": 0}

    def test_missing_version_key_returns_400(self, authed):
        bad = {k: v for k, v in MINIMAL_BACKUP.items() if k != "version"}
        payload = json.dumps(bad).encode()
        r = authed.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", payload, "application/json")},
        )
        assert r.status_code == 400

    def test_missing_feeds_key_returns_400(self, authed):
        bad = {k: v for k, v in MINIMAL_BACKUP.items() if k != "feeds"}
        payload = json.dumps(bad).encode()
        r = authed.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", payload, "application/json")},
        )
        assert r.status_code == 400

    def test_invalid_json_returns_400(self, authed):
        r = authed.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", b"not json{{{", "application/json")},
        )
        assert r.status_code == 400

    def test_file_over_limit_returns_413(self, authed, monkeypatch):
        import reed.api.data as data_module
        monkeypatch.setattr(data_module, "MAX_RESTORE_BYTES", 10)
        payload = b"x" * 12
        r = authed.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", payload, "application/json")},
        )
        assert r.status_code == 413

    def test_no_auth_returns_401(self, reed_client):
        payload = json.dumps(MINIMAL_BACKUP).encode()
        r = reed_client.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", payload, "application/json")},
        )
        assert r.status_code == 401

    def test_round_trip_with_data(self, authed, reed_client):
        graph = reed_client.app.state.graph
        from datetime import UTC, datetime
        graph.create_feed(
            url="https://example.com/feed",
            title="Example",
            description="",
            site_url="",
        )
        # Export
        export_r = authed.get("/api/v1/data/export")
        assert export_r.status_code == 200
        backup_bytes = export_r.content
        # Restore
        restore_r = authed.post(
            "/api/v1/data/restore",
            files={"file": ("backup.json", backup_bytes, "application/json")},
        )
        assert restore_r.status_code == 200
        summary = restore_r.json()["data"]
        assert summary["feeds"] == 1
