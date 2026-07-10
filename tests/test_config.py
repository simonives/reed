# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

import pytest

from reed.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert s.poll_default_interval == 60
    assert s.derived_edge_interval == 360
    assert s.topic_backend == "yake"
    assert s.host == "0.0.0.0"
    assert s.port == 8000


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REED_API_KEY", "secret")
    monkeypatch.setenv("REED_PORT", "9000")
    s = Settings()
    assert s.api_key == "secret"
    assert s.port == 9000
