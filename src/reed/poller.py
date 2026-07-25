# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser
import httpx

from .config import effective_config, effective_feed_settings
from .graph import GraphService, _safe_url
from .http import http_client, safe_get
from .reader import extract_article
from .text import word_count
from .topics import extract_keywords, item_text, make_extractor

logger = logging.getLogger(__name__)

# Caps on reader-mode extraction per feed per poll cycle, so one busy feed
# cannot stall the polling loop.
_MAX_EXTRACTIONS_PER_POLL = 10
_EXTRACTION_CONCURRENCY = 4


class FeedPoller:
    """Async background worker that polls subscribed feeds on schedule."""

    def __init__(self, graph: GraphService) -> None:
        self._graph = graph
        self._running = False
        self._http: httpx.AsyncClient | None = None
        self._extractor = make_extractor()

    async def start(self) -> None:
        self._running = True
        self._http = http_client()
        logger.info("Feed poller started")
        try:
            await self._backfill_topics()
        except Exception:
            logger.warning("Topic backfill failed on startup; continuing", exc_info=True)
        _backoff = 5
        try:
            while self._running:
                try:
                    await self._poll_due_feeds()
                    _backoff = 5
                except Exception:
                    logger.exception("Poll cycle failed; retrying in %ds", _backoff)
                    await asyncio.sleep(_backoff)
                    _backoff = min(_backoff * 2, 300)
                    continue
                await asyncio.sleep(60)
        finally:
            await self._http.aclose()

    async def stop(self) -> None:
        self._running = False

    async def refresh_feed(self, feed: dict[str, Any]) -> None:
        """Poll a single feed immediately (POST /feeds/{id}/refresh)."""
        config = effective_config(self._graph)
        now = datetime.now(UTC)
        if self._http is not None:
            await self._poll_feed(feed, now, self._http, config)
        else:
            async with http_client() as client:
                await self._poll_feed(feed, now, client, config)

    async def _poll_due_feeds(self) -> None:
        assert self._http is not None
        now = datetime.now(UTC)
        config = effective_config(self._graph)
        feeds = self._graph.list_feeds_for_polling()
        due = [f for f in feeds if self._is_due(f, now, config)]
        if not due:
            return
        logger.debug("Polling %d due feed(s)", len(due))
        await asyncio.gather(
            *(self._poll_feed(feed, now, self._http, config) for feed in due),
            return_exceptions=True,
        )

    def _is_due(self, feed: dict[str, Any], now: datetime, config: dict[str, Any]) -> bool:
        last_fetched = feed.get("last_fetched_at")
        if last_fetched is None:
            return True
        assert isinstance(last_fetched, datetime)
        # Kuzu returns timezone-naive datetimes; treat as UTC
        if last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=UTC)
        interval_min = effective_feed_settings(feed, config)["poll_interval_minutes"]
        return bool(now >= last_fetched + timedelta(minutes=interval_min))

    async def _poll_feed(
        self,
        feed: dict[str, Any],
        now: datetime,
        http: httpx.AsyncClient,
        config: dict[str, Any],
    ) -> None:
        url = str(feed["url"])
        headers: dict[str, str] = {}
        if feed.get("etag"):
            headers["If-None-Match"] = str(feed["etag"])
        if feed.get("last_modified"):
            headers["If-Modified-Since"] = str(feed["last_modified"])

        try:
            # safe_get blocks SSRF: a feed (or a redirect from one) must not
            # reach a private or link-local address such as cloud metadata.
            response = await safe_get(http, url, headers=headers)

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

            new_items = await asyncio.to_thread(self._ingest_entries, url, response.content, now)
            self._graph.update_feed_poll_metadata(url, now, etag, last_modified, None)
            logger.info("Polled %s: %d new item(s)", url, len(new_items))

            if new_items and effective_feed_settings(feed, config)["reader_mode_enabled"]:
                await self._extract_new_items(new_items, http)

            await self._enrich_new_items(new_items)

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

    async def _extract_new_items(
        self, new_items: list[tuple[str, str, str]], http: httpx.AsyncClient
    ) -> None:
        semaphore = asyncio.Semaphore(_EXTRACTION_CONCURRENCY)

        async def extract_one(item_id: str, item_url: str) -> None:
            async with semaphore:
                content = await extract_article(item_url, http)
            if content:
                self._graph.save_reader_content(item_id, content, datetime.now(UTC))

        await asyncio.gather(
            *(
                extract_one(item_id, item_url)
                for item_id, item_url, _ in new_items[:_MAX_EXTRACTIONS_PER_POLL]
                if item_url
            )
        )

    def _ingest_entries(
        self, feed_url: str, content: bytes, fetched_at: datetime
    ) -> list[tuple[str, str, str]]:
        """Ingest feed entries; returns (item_id, item_url, text) for each new item."""
        parsed = feedparser.parse(content)
        new_items: list[tuple[str, str, str]] = []
        for entry in parsed.entries:
            guid = entry.get("id") or entry.get("link")
            if not guid:
                title = entry.get("title", "")
                if not title:
                    continue
                # Namespace by feed URL so identical titles across feeds don't merge items.
                guid = f"{feed_url}|{title}"
            item_url = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            author = entry.get("author", "")
            content_html = ""
            if entry.get("content"):
                content_html = entry.content[0].get("value", "")
            published_at: datetime | None = None
            if entry.get("published_parsed"):
                tp = entry.published_parsed
                with contextlib.suppress(ValueError, TypeError):
                    published_at = datetime(tp[0], tp[1], tp[2], tp[3], tp[4], tp[5], tzinfo=UTC)

            item_id = self._graph.create_item(
                feed_url=feed_url,
                guid=guid,
                url=item_url,
                title=title,
                summary=summary,
                content=content_html,
                author=author,
                word_count=word_count(content_html or summary),
                published_at=published_at,
                fetched_at=fetched_at,
            )
            if item_id is not None:
                text = item_text(title, summary, content_html)
                new_items.append((item_id, _safe_url(item_url), text))
        return new_items

    def _enrich_item(self, item_id: str, text: str) -> None:
        keywords = extract_keywords(text, self._extractor)
        self._graph.enrich_item(item_id, keywords)

    async def _enrich_new_items(self, new_items: list[tuple[str, str, str]]) -> None:
        for item_id, _, text in new_items:
            try:
                await asyncio.to_thread(self._enrich_item, item_id, text)
            except Exception:
                logger.warning("Topic enrichment failed for item %s", item_id)

    async def _backfill_topics(self) -> None:
        unenriched = await asyncio.to_thread(self._graph.get_unenriched_items)
        if not unenriched:
            return
        logger.info("Backfilling topics for %d item(s)", len(unenriched))
        for item in unenriched:
            text = item_text(
                item.get("title") or "",
                item.get("summary") or "",
                item.get("content") or "",
            )
            try:
                await asyncio.to_thread(self._enrich_item, item["id"], text)
            except Exception:
                logger.warning("Topic backfill failed for item %s", item["id"])
