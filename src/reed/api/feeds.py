# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings
from ..graph import GraphService
from .deps import get_graph, require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/feeds",
    tags=["feeds"],
    dependencies=[Depends(require_api_key)],
)


class FeedCreate(BaseModel):
    url: str
    poll_interval_minutes: int = 0  # 0 = use server default


class FeedResponse(BaseModel):
    url: str
    title: str
    description: str
    site_url: str
    poll_interval_minutes: int
    last_fetched_at: datetime | None
    error_state: str | None
    etag: str | None
    last_modified: str | None


@router.post("", response_model=FeedResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(body: FeedCreate, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    if graph.feed_exists(body.url):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feed already subscribed")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(body.url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch feed: {exc}",
        ) from exc

    parsed = feedparser.parse(response.content)
    feed_meta = parsed.feed

    settings = get_settings()
    interval = body.poll_interval_minutes or settings.poll_default_interval

    return graph.create_feed(
        url=body.url,
        title=feed_meta.get("title", body.url),
        description=feed_meta.get("description", ""),
        site_url=feed_meta.get("link", ""),
        poll_interval_minutes=interval,
    )


@router.get("", response_model=list[FeedResponse])
async def list_feeds(graph: GraphService = Depends(get_graph)) -> list[dict[str, Any]]:
    return graph.list_feeds()


@router.get("/{feed_url:path}", response_model=FeedResponse)
async def get_feed(feed_url: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    feed = graph.get_feed(feed_url)
    if feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return feed


@router.delete("/{feed_url:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(feed_url: str, graph: GraphService = Depends(get_graph)) -> None:
    if not graph.delete_feed(feed_url):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
