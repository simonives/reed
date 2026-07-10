# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from reed.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def reed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("REED_API_KEY", "test-key")
    monkeypatch.setenv("REED_DATA_PATH", str(tmp_path / "test.kuzu"))
    monkeypatch.setenv("REED_FRONTEND_PATH", "/nonexistent")
    get_settings.cache_clear()

    from reed.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture
def authed(reed_client):
    """TestClient with the API key header pre-set."""
    reed_client.headers.update({"X-API-Key": "test-key"})
    return reed_client
