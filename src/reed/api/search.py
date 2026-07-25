# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..graph import GraphService
from .deps import get_graph, require_api_key

router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
    dependencies=[Depends(require_api_key)],
)


def _search_item_response(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "url": item["url"],
        "title": item["title"],
        "feed_id": item.get("feed_id"),
        "feed_title": item.get("feed_title"),
        "feed": (
            {"id": item["feed_id"], "title": item["feed_title"]} if item.get("feed_id") else None
        ),
        "published_at": item.get("published_at"),
        "fetched_at": item.get("fetched_at"),
        "read": bool(item["read"]),
        "starred": bool(item["starred"]),
        "author": {"name": item["author"]} if item.get("author") else None,
        "word_count": int(item.get("word_count") or 0),
        "score": float(item.get("score") or 0.0),
        "match_source": item.get("match_source", ["content"]),
        "excerpt": item.get("excerpt"),
        "note_excerpt": item.get("note_excerpt"),
    }


@router.get("")
def search(
    q: str | None = None,
    feed_id: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    unread: bool = False,
    starred: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="q is required and cannot be empty",
        )
    q = q.strip()
    results, total = graph.search_items(
        q=q,
        feed_id=feed_id,
        tag=tag,
        author=author,
        unread_only=unread,
        starred_only=starred,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [_search_item_response(r) for r in results],
        "meta": {
            "total": total,
            "q": q,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(results) < total,
        },
    }
