# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..graph import GraphService
from .deps import get_graph, require_api_key
from .schemas import envelope, paginated

router = APIRouter(
    prefix="/api/v1/topics",
    tags=["topics"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
async def list_topics(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    topics, total = graph.get_topics(limit=limit, offset=offset)
    return paginated(topics, total, offset)


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    topic = graph.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return envelope(topic)
