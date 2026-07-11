# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import logging
from typing import Any

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from ..config import effective_config
from ..discovery import discover_feeds
from ..graph import GraphService
from ..http import http_client
from ..poller import FeedPoller
from .deps import get_graph, get_poller, require_api_key
from .schemas import envelope, feed_response, item_list_response, paginated

logger = logging.getLogger(__name__)

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
    if graph.feed_exists(body.url):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feed already subscribed")

    try:
        async with http_client() as client:
            response = await client.get(body.url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch feed: {exc}",
        ) from exc

    parsed = feedparser.parse(response.content)
    feed_meta = parsed.feed

    feed = graph.create_feed(
        url=body.url,
        title=feed_meta.get("title", body.url),
        description=feed_meta.get("description", ""),
        site_url=feed_meta.get("link", ""),
        display_name=body.display_name,
        poll_interval_minutes=body.poll_interval_minutes,
        tags=body.tags,
    )
    return envelope(feed_response(feed, effective_config(graph)))


@router.post("/discover")
async def discover(body: DiscoverRequest) -> dict[str, Any]:
    try:
        async with http_client() as client:
            feeds = await discover_feeds(body.url, client)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch URL: {exc}",
        ) from exc
    return envelope(feeds)


@router.get("")
async def list_feeds(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    config = effective_config(graph)
    return envelope([feed_response(f, config) for f in graph.list_feeds()])


@router.get("/{feed_id}")
async def get_feed(feed_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    feed = _feed_or_404(graph, feed_id)
    return envelope(feed_response(feed, effective_config(graph)))


@router.patch("/{feed_id}")
async def update_feed(
    feed_id: str, body: FeedUpdate, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    updated = graph.update_feed(feed_id, body.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return envelope(feed_response(updated, effective_config(graph)))


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(feed_id: str, graph: GraphService = Depends(get_graph)) -> None:
    if not graph.delete_feed(feed_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")


@router.post("/{feed_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_feed(
    feed_id: str,
    graph: GraphService = Depends(get_graph),
    poller: FeedPoller = Depends(get_poller),
) -> dict[str, Any]:
    feed = _feed_or_404(graph, feed_id)
    await poller.refresh_feed(feed)
    refreshed = graph.get_feed(feed_id)
    assert refreshed is not None
    return envelope(feed_response(refreshed, effective_config(graph)))


@router.get("/{feed_id}/items")
async def feed_items(
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
