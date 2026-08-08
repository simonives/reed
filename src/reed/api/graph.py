# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from ..graph import GraphService
from ..poller import FeedPoller
from .deps import get_graph, get_poller, require_api_key
from .schemas import cursor_paginated, decode_cursor, encode_cursor, envelope, item_list_response

router = APIRouter(
    prefix="/api/v1/graph",
    tags=["graph"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/similar/{item_id}")
def similar_items(item_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    results = graph.get_similar_items(item_id)
    if results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return envelope(
        [
            {
                "item": item_list_response(r),
                "score": r["score"],
                "shared_topics": r["shared_topics"],
            }
            for r in results
        ]
    )


@router.get("/adjacent-to-starred")
def adjacent_to_starred(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    results = graph.get_adjacent_to_starred()
    return envelope([{"item": item_list_response(r), "score": r["score"]} for r in results])


@router.get("/author/{author_id:path}")
def author_items(
    author_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    cursor_ts, cursor_guid = None, None
    if cursor is not None:
        try:
            cursor_ts, cursor_guid = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
            ) from exc
    items = graph.get_author_items(author_id, cursor_ts, cursor_guid, limit)
    next_cursor = encode_cursor(items[-1]) if len(items) == limit else None
    return cursor_paginated([item_list_response(i) for i in items], next_cursor)


@router.get("/topic/{topic_id}/timeline")
def topic_timeline(topic_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    results = graph.get_topic_timeline(topic_id)
    if results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return envelope(results)


@router.get("/feed-health")
def feed_health(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    now = datetime.now(UTC)
    inactive_cutoff = now - timedelta(days=30)
    results = graph.get_feed_health(now)
    inactive = []
    erroring = []
    for f in results:
        feed_ref = {"id": f["id"], "url": f["url"], "title": f["title"]}
        last_fetched = f.get("last_fetched_at")
        subscribed_at = f.get("subscribed_at")
        # Kuzu returns timezone-naive TIMESTAMP values; treat as UTC. Same fix
        # as poller.py's _is_due, for the same underlying reason.
        if last_fetched is not None and last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=UTC)
        if subscribed_at is not None and subscribed_at.tzinfo is None:
            subscribed_at = subscribed_at.replace(tzinfo=UTC)
        # Mirror the query's own coalesce(last_fetched_at, subscribed_at): a
        # feed included here purely for erroring (high consecutive_errors)
        # that hasn't been polled yet is not "inactive" just because it has
        # no last_fetched_at — it's only inactive if that coalesced instant
        # itself predates the cutoff.
        effective_last = last_fetched or subscribed_at
        if effective_last is None or effective_last < inactive_cutoff:
            days_since = (now - effective_last).days if effective_last else None
            inactive.append(
                {
                    "feed": feed_ref,
                    "last_fetched_at": last_fetched,
                    "days_since_last_item": days_since,
                }
            )
        if f["consecutive_errors"] > 10:
            erroring.append(
                {
                    "feed": feed_ref,
                    "consecutive_errors": f["consecutive_errors"],
                    "last_error": f["last_error"],
                }
            )
    return envelope({"inactive": inactive, "erroring": erroring})


@router.post("/recompute", status_code=status.HTTP_202_ACCEPTED)
async def trigger_recompute(
    background_tasks: BackgroundTasks, poller: FeedPoller = Depends(get_poller)
) -> dict[str, Any]:
    # BackgroundTasks (not a bare asyncio.create_task) so the task is held by
    # Starlette until it completes, rather than being an unreferenced task the
    # event loop is free to garbage-collect mid-flight (#161).
    background_tasks.add_task(poller.recompute_derived_edges)
    return envelope({"triggered": True})
