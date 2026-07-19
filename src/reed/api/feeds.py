# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import logging
from typing import Any

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from ..config import effective_config
from ..discovery import discover_feeds
from ..graph import GraphService
from ..http import UnsafeURLError, http_client, safe_get
from ..poller import FeedPoller
from .deps import get_graph, get_poller, require_api_key
from .schemas import envelope, feed_response, item_list_response, paginated

logger = logging.getLogger(__name__)


def _fetch_error_422(exc: Exception) -> HTTPException:
    """One place to map an outbound-fetch failure to a 422.

    UnsafeURLError is an SSRF refusal ("Refusing to fetch"); any other
    httpx.HTTPError is a plain fetch failure ("Could not fetch"). Keeping the
    two endpoints on this single mapping means the next error class (timeout,
    size limit) is classified once, not per endpoint (#46).
    """
    prefix = "Refusing to fetch" if isinstance(exc, UnsafeURLError) else "Could not fetch"
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"{prefix}: {exc}",
    )


router = APIRouter(
    prefix="/api/v1/feeds",
    tags=["feeds"],
    dependencies=[Depends(require_api_key)],
)


def _clean_tags(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    cleaned = [t.strip() for t in v]
    if any(not t for t in cleaned):
        raise ValueError("tag names must not be empty or whitespace")
    return cleaned


class FeedCreate(BaseModel):
    url: str
    display_name: str | None = None
    tags: list[str] = []
    poll_interval_minutes: int | None = Field(default=None, ge=1)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        return _clean_tags(v) or []


class FeedUpdate(BaseModel):
    display_name: str | None = None
    poll_interval_minutes: int | None = Field(default=None, ge=1)
    reader_mode_enabled: bool | None = None
    is_active: bool | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        return _clean_tags(v)


class DiscoverRequest(BaseModel):
    url: str


def _feed_or_404(graph: GraphService, feed_id: str) -> dict[str, Any]:
    feed = graph.get_feed(feed_id)
    if feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return feed


@router.post("", status_code=status.HTTP_201_CREATED)
async def subscribe(body: FeedCreate, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    if await asyncio.to_thread(graph.feed_exists, body.url):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feed already subscribed")

    try:
        async with http_client() as client:
            response = await safe_get(client, body.url)
        response.raise_for_status()
    except (UnsafeURLError, httpx.HTTPError) as exc:
        raise _fetch_error_422(exc) from exc

    try:
        parsed = await asyncio.to_thread(feedparser.parse, response.content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Feed parse error: {exc}",
        ) from exc
    if not parsed.get("version"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL must point to a valid RSS or Atom feed",
        )
    feed_meta = parsed.feed

    feed = await asyncio.to_thread(
        graph.create_feed,
        url=body.url,
        title=feed_meta.get("title", body.url),
        description=feed_meta.get("description", ""),
        site_url=feed_meta.get("link", ""),
        display_name=body.display_name,
        poll_interval_minutes=body.poll_interval_minutes,
        tags=body.tags,
    )
    config = await asyncio.to_thread(effective_config, graph)
    return envelope(feed_response(feed, config))


@router.post("/discover")
async def discover(body: DiscoverRequest) -> dict[str, Any]:
    try:
        async with http_client() as client:
            feeds = await discover_feeds(body.url, client)
    except (UnsafeURLError, httpx.HTTPError) as exc:
        raise _fetch_error_422(exc) from exc
    return envelope(feeds)


@router.get("")
def list_feeds(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    config = effective_config(graph)
    return envelope([feed_response(f, config) for f in graph.list_feeds()])


@router.get("/{feed_id}")
def get_feed(feed_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    feed = _feed_or_404(graph, feed_id)
    return envelope(feed_response(feed, effective_config(graph)))


@router.patch("/{feed_id}")
def update_feed(
    feed_id: str, body: FeedUpdate, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    updated = graph.update_feed(feed_id, body.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return envelope(feed_response(updated, effective_config(graph)))


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(feed_id: str, graph: GraphService = Depends(get_graph)) -> None:
    if not graph.delete_feed(feed_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")


@router.post("/{feed_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_feed(
    feed_id: str,
    graph: GraphService = Depends(get_graph),
    poller: FeedPoller = Depends(get_poller),
) -> dict[str, Any]:
    feed = await asyncio.to_thread(_feed_or_404, graph, feed_id)
    await poller.refresh_feed(feed)
    refreshed = await asyncio.to_thread(graph.get_feed, feed_id)
    assert refreshed is not None
    config = await asyncio.to_thread(effective_config, graph)
    return envelope(feed_response(refreshed, config))


@router.get("/{feed_id}/items")
def feed_items(
    feed_id: str,
    unread: bool = False,
    starred: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    if not graph.feed_exists_by_id(feed_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    items, total = graph.list_items(
        feed_id=feed_id,
        unread_only=unread,
        starred_only=starred,
        limit=limit,
        offset=offset,
    )
    return paginated([item_list_response(i) for i in items], total, offset)
