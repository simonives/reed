# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

import feedparser
import httpx

from .graph import GraphService

logger = logging.getLogger(__name__)

_USER_AGENT = "Reed RSS Reader/0.1 (+https://github.com/simonives/reed)"


class FeedPoller:
    """Async background worker that polls subscribed feeds on schedule."""

    def __init__(self, graph: GraphService) -> None:
        self._graph = graph
        self._running = False
        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._running = True
        self._http = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
        logger.info("Feed poller started")
        try:
            while self._running:
                await self._poll_due_feeds()
                await asyncio.sleep(60)
        finally:
            await self._http.aclose()

    async def stop(self) -> None:
        self._running = False

    async def _poll_due_feeds(self) -> None:
        now = datetime.now(UTC)
        feeds = self._graph.list_feeds_for_polling()
        due = [f for f in feeds if self._is_due(f, now)]
        if not due:
            return
        logger.debug("Polling %d due feed(s)", len(due))
        for feed in due:
            await self._poll_feed(feed, now)

    def _is_due(self, feed: dict[str, object], now: datetime) -> bool:
        last_fetched = feed.get("last_fetched_at")
        if last_fetched is None:
            return True
        assert isinstance(last_fetched, datetime)
        # Kuzu returns timezone-naive datetimes; treat as UTC
        if last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=UTC)
        interval_min = feed.get("poll_interval_minutes")
        interval = timedelta(minutes=int(str(interval_min)) if interval_min else 60)
        return bool(now >= last_fetched + interval)

    async def _poll_feed(self, feed: dict[str, object], now: datetime) -> None:
        assert self._http is not None
        url = str(feed["url"])
        headers: dict[str, str] = {}
        if feed.get("etag"):
            headers["If-None-Match"] = str(feed["etag"])
        if feed.get("last_modified"):
            headers["If-Modified-Since"] = str(feed["last_modified"])

        try:
            response = await self._http.get(url, headers=headers)

            if response.status_code == 304:
                self._graph.update_feed_poll_metadata(
                    url,
                    now,
                    str(feed["etag"]) if feed.get("etag") else None,
                    str(feed["last_modified"]) if feed.get("last_modified") else None,
                    None,
                )
                logger.debug("Not modified: %s", url)
                return

            response.raise_for_status()

            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")

            new_count = self._ingest_entries(url, response.content, now)
            self._graph.update_feed_poll_metadata(url, now, etag, last_modified, None)
            logger.info("Polled %s: %d new item(s)", url, new_count)

        except Exception as exc:
            error = str(exc)[:500]
            logger.warning("Poll failed for %s: %s", url, error)
            self._graph.update_feed_poll_metadata(
                url,
                now,
                str(feed["etag"]) if feed.get("etag") else None,
                str(feed["last_modified"]) if feed.get("last_modified") else None,
                error,
            )

    def _ingest_entries(self, feed_url: str, content: bytes, fetched_at: datetime) -> int:
        parsed = feedparser.parse(content)
        new_count = 0
        for entry in parsed.entries:
            guid = entry.get("id") or entry.get("link") or entry.get("title", "")
            if not guid:
                continue
            item_url = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            content_html = ""
            if entry.get("content"):
                content_html = entry.content[0].get("value", "")
            published_at: datetime | None = None
            if entry.get("published_parsed"):
                tp = entry.published_parsed
                with contextlib.suppress(ValueError, TypeError):
                    published_at = datetime(tp[0], tp[1], tp[2], tp[3], tp[4], tp[5], tzinfo=UTC)

            created = self._graph.create_item(
                feed_url=feed_url,
                guid=guid,
                url=item_url,
                title=title,
                summary=summary,
                content=content_html,
                published_at=published_at,
                fetched_at=fetched_at,
            )
            if created:
                new_count += 1
        return new_count
