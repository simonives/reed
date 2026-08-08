# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..graph import GraphService
from .deps import get_graph, require_api_key
from .schemas import (
    cursor_paginated,
    decode_cursor,
    encode_cursor,
    envelope,
    item_list_response,
    paginated,
)

router = APIRouter(
    prefix="/api/v1/topics",
    tags=["topics"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
def list_topics(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    topics, total = graph.get_topics(limit=limit, offset=offset)
    return paginated(topics, total, offset)


@router.get("/{topic_id}")
def get_topic(topic_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    topic = graph.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return envelope(topic)


@router.get("/{topic_id}/related")
def get_related_topics(topic_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    if not graph.topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return envelope(graph.get_related_topics(topic_id))


@router.get("/{topic_id}/items")
def get_topic_items(
    topic_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    if not graph.topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    cursor_ts, cursor_guid = None, None
    if cursor is not None:
        try:
            cursor_ts, cursor_guid = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
            ) from exc
    items = graph.get_topic_items(topic_id, cursor_ts, cursor_guid, limit)
    next_cursor = encode_cursor(items[-1]) if len(items) == limit else None
    return cursor_paginated([item_list_response(i) for i in items], next_cursor)
