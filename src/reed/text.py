# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from html.parser import HTMLParser
from io import StringIO


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._out = StringIO()

    def handle_data(self, data: str) -> None:
        self._out.write(data)

    def text(self) -> str:
        return self._out.getvalue()


def strip_html(html: str) -> str:
    """Return the plain text content of an HTML fragment."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    return " ".join(parser.text().split())


def word_count(html: str) -> int:
    return len(strip_html(html).split())


def snippet(html: str, length: int = 300) -> str:
    text = strip_html(html)
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "…"
