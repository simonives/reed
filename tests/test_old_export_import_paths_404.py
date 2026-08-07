# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/data/export"),
        ("POST", "/api/v1/data/restore"),
        ("GET", "/api/v1/opml/export"),
        ("POST", "/api/v1/opml/import"),
        ("POST", "/api/v1/opml/preview"),
    ],
)
def test_old_path_returns_404(authed, method, path):
    r = authed.request(method, path)
    assert r.status_code == 404
