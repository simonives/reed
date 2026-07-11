# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import logging
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

_FEED_MIME_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/feed+json",
    "application/json",
}


class _FeedLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self._base_url = base_url
        self.feeds: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        attr = dict(attrs)
        if (attr.get("rel") or "").lower() != "alternate":
            return
        mime = (attr.get("type") or "").lower().split(";")[0].strip()
        href = attr.get("href")
        if mime not in _FEED_MIME_TYPES or not href:
            return
        self.feeds.append(
            {
                "url": urljoin(self._base_url, href),
                "title": attr.get("title") or "",
                "type": mime,
            }
        )


def _looks_like_feed(content_type: str, body: str) -> bool:
    if "xml" in content_type and ("<rss" in body[:2000] or "<feed" in body[:2000]):
        return True
    return "<rss" in body[:500] or "<feed" in body[:500]


async def discover_feeds(url: str, http: httpx.AsyncClient) -> list[dict[str, str]]:
    """Given a website URL, return feed URL(s) advertised in its HTML head.

    If the URL is itself a feed, it is returned as the single result.
    """
    response = await http.get(url)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    body = response.text

    if _looks_like_feed(content_type, body):
        return [{"url": str(response.url), "title": "", "type": content_type or "feed"}]

    parser = _FeedLinkParser(str(response.url))
    parser.feed(body)

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for feed in parser.feeds:
        if feed["url"] not in seen:
            seen.add(feed["url"])
            unique.append(feed)
    return unique
