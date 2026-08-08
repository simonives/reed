# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import base64

import pytest

from reed.api.schemas import decode_cursor


class TestDecodeCursor:
    def test_deeply_nested_json_array_raises_clean_value_error(self):
        """Security review on PR #199 — CPython's json scanner raises
        RecursionError on deeply nested input, which decode_cursor's except
        clause didn't catch, so a crafted cursor produced an uncaught 500
        instead of a clean 400. Verified threshold ~1000 nesting levels;
        use 2000 for margin."""
        payload = b"[" * 2000
        cursor = base64.urlsafe_b64encode(payload).decode()
        with pytest.raises(ValueError):
            decode_cursor(cursor)

    def test_oversized_cursor_raises_clean_value_error(self):
        """Belt-and-braces: reject an implausibly large cursor before even
        attempting to decode it, rather than relying solely on catching
        whatever exception deep nesting happens to raise."""
        cursor = base64.urlsafe_b64encode(b"x" * 10_000).decode()
        with pytest.raises(ValueError):
            decode_cursor(cursor)
