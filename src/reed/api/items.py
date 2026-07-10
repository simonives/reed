# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..graph import GraphService
from .deps import get_graph, require_api_key

router = APIRouter(
    prefix="/api/v1/items",
    tags=["items"],
    dependencies=[Depends(require_api_key)],
)


class ItemResponse(BaseModel):
    guid: str
    url: str
    title: str
    summary: str
    content: str
    published_at: datetime | None
    fetched_at: datetime
    read: bool
    starred: bool


@router.get("", response_model=list[ItemResponse])
async def list_items(
    feed_url: str | None = None,
    unread: bool = False,
    starred: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    graph: GraphService = Depends(get_graph),
) -> list[dict[str, Any]]:
    return graph.list_items(
        feed_url=feed_url,
        unread_only=unread,
        starred_only=starred,
        limit=limit,
        offset=offset,
    )
