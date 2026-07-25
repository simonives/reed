# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

"""#136 — graph.py and http.py must share a single scheme allowlist and parser.

Before the fix, graph.py's `_safe_url()` extracted the scheme with a naive
`str.split('://', 1)` and kept its own `_SAFE_URL_SCHEMES` constant, while
http.py's SSRF guard (`_require_safe_url`) parsed the scheme with `httpx.URL`
against its own inline allowlist. Two allowlists and two parsers can drift,
and disagree on edge cases such as a scheme with no `//` (valid URI syntax,
e.g. `http:example.com`), which `httpx.URL` parses as scheme `http` but the
naive split treats as one unmatched blob and rejects.
"""

from __future__ import annotations

import httpx

from reed import http as reed_http
from reed.graph import _safe_url


class TestSchemeAllowlistConsolidation:
    def test_safe_url_is_imported_from_http_not_reimplemented(self):
        """graph.py must not define its own copy of the scheme sanitiser —
        it must import http.py's single source of truth directly.
        """
        assert _safe_url is reed_http.safe_url

    def test_safe_url_agrees_with_httpx_url_parsing_on_edge_cases(self):
        """A scheme with no '//' is valid URI syntax; httpx.URL parses its
        scheme correctly (e.g. 'http') where a naive str.split('://') does
        not. graph.py's _safe_url must use the same parser as http.py, so it
        must accept this URL rather than rejecting it as an unmatched scheme.
        """
        url = "http:example.com"
        assert httpx.URL(url).scheme == "http"
        assert _safe_url(url) == url

    def test_safe_url_rejects_disallowed_schemes_consistently(self):
        assert _safe_url("javascript:alert(1)") == ""
        assert _safe_url("ftp://example.com/file") == ""

    def test_safe_url_accepts_http_and_https(self):
        assert _safe_url("http://example.com") == "http://example.com"
        assert _safe_url("https://example.com") == "https://example.com"

    def test_safe_url_and_require_safe_url_agree_on_scheme_rejection(self):
        """graph.py's sanitiser and http.py's SSRF guard must reject the same
        set of schemes — drift here means one path is stricter than the
        other with no shared source of truth.
        """
        for scheme in ("javascript", "ftp", "data", "file"):
            url = f"{scheme}://example.com"
            assert _safe_url(url) == ""
            assert url.split("://", 1)[0] not in reed_http.SAFE_URL_SCHEMES
