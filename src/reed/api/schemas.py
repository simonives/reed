# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..config import effective_feed_settings
from ..text import snippet


def envelope(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"data": data}
    if meta is not None:
        body["meta"] = meta
    return body


def paginated(items: list[dict[str, Any]], total: int, offset: int) -> dict[str, Any]:
    return envelope(items, meta={"total": total, "has_more": offset + len(items) < total})


def feed_response(feed: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    effective = effective_feed_settings(feed, config)
    effective_interval = effective["poll_interval_minutes"]
    last_fetched = feed.get("last_fetched_at")
    next_poll = (
        last_fetched + timedelta(minutes=effective_interval)
        if isinstance(last_fetched, datetime)
        else None
    )
    return {
        "id": feed["id"],
        "url": feed["url"],
        "title": feed["title"],
        "display_name": feed.get("display_name"),
        "site_url": feed.get("site_url"),
        "description": feed.get("description"),
        "subscribed_at": feed.get("subscribed_at"),
        "last_fetched_at": last_fetched,
        "next_poll_at": next_poll,
        "consecutive_errors": int(feed.get("consecutive_errors") or 0),
        "last_error": feed.get("last_error"),
        "is_active": bool(feed.get("is_active", True)),
        "effective_poll_interval_minutes": effective_interval,
        "poll_interval_minutes": feed.get("poll_interval_minutes"),
        "reader_mode_enabled": feed.get("reader_mode_enabled"),
        "effective_reader_mode_enabled": effective["reader_mode_enabled"],
        "tags": feed.get("tags", []),
        "item_count": int(feed.get("item_count") or 0),
        "unread_count": int(feed.get("unread_count") or 0),
    }


def item_list_response(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "url": item["url"],
        "title": item["title"],
        "summary": snippet(item.get("summary") or item.get("content") or ""),
        "published_at": item.get("published_at"),
        "fetched_at": item.get("fetched_at"),
        "read": bool(item["read"]),
        "starred": bool(item["starred"]),
        "word_count": int(item.get("word_count") or 0),
        "feed": (
            {"id": item["feed_id"], "title": item["feed_title"]} if item.get("feed_id") else None
        ),
        "author": {"name": item["author"]} if item.get("author") else None,
        "tags": item.get("tags", []),
        "topics": [],  # populated from M4
    }


def item_detail_response(item: dict[str, Any]) -> dict[str, Any]:
    detail = item_list_response(item)
    detail["content"] = item.get("content") or ""
    detail["reader_content"] = item.get("reader_content")
    detail["note"] = item.get("note")
    return detail
