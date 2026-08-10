# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..graph import GraphService
from ..reader import extract_article
from .deps import get_graph, require_api_key
from .schemas import (
    cursor_paginated,
    decode_cursor,
    encode_cursor,
    envelope,
    item_detail_response,
    item_list_response,
)

router = APIRouter(
    prefix="/api/v1/items",
    tags=["items"],
    dependencies=[Depends(require_api_key)],
)


class ItemUpdate(BaseModel):
    read: bool | None = None
    starred: bool | None = None


class MarkReadRequest(BaseModel):
    feed_id: str | None = None
    before: datetime | None = None


class TagApply(BaseModel):
    name: str


class NoteBody(BaseModel):
    body: str


def _item_or_404(graph: GraphService, item_id: str) -> dict[str, Any]:
    item = graph.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def _item_envelope(item: dict[str, Any], topics: list[dict[str, Any]]) -> dict[str, Any]:
    response = item_detail_response(item)
    response["topics"] = topics
    return envelope(response)


@router.get("")
def list_items(
    feed_id: str | None = None,
    tag: str | None = None,
    unread: bool = False,
    starred: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    cursor_ts: datetime | None = None
    cursor_guid: str | None = None
    if cursor is not None:
        try:
            cursor_ts, cursor_guid = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
            ) from exc
    items = graph.list_items_cursor(
        feed_id=feed_id,
        tag=tag,
        unread_only=unread,
        starred=True if starred else None,
        since=since,
        until=until,
        limit=limit,
        cursor_ts=cursor_ts,
        cursor_guid=cursor_guid,
    )
    next_cursor = encode_cursor(items[-1]) if len(items) == limit else None
    return cursor_paginated([item_list_response(i) for i in items], next_cursor)


@router.post("/mark-read")
def mark_read(body: MarkReadRequest, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    if body.feed_id is not None and not graph.feed_exists_by_id(body.feed_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    count = graph.mark_read_bulk(feed_id=body.feed_id, before=body.before)
    return envelope({"marked_read": count})


@router.get("/{item_id}")
def get_item(item_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    item = _item_or_404(graph, item_id)
    return _item_envelope(item, graph.get_item_topics(item["id"]))


@router.patch("/{item_id}")
def update_item(
    item_id: str, body: ItemUpdate, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    updated = graph.update_item_state(item_id, read=body.read, starred=body.starred)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return _item_envelope(updated, graph.get_item_topics(updated["id"]))


@router.post("/{item_id}/extract")
async def extract_item(item_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    item = await asyncio.to_thread(_item_or_404, graph, item_id)
    if not item.get("url"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Item has no URL to extract from",
        )
    content = await extract_article(item["url"])
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract article content",
        )
    await asyncio.to_thread(graph.save_reader_content, item_id, content, datetime.now(UTC))
    refreshed = await asyncio.to_thread(graph.get_item, item_id)
    assert refreshed is not None
    topics = await asyncio.to_thread(graph.get_item_topics, refreshed["id"])
    return _item_envelope(refreshed, topics)


# --- Item tags ---


@router.post("/{item_id}/tags", status_code=status.HTTP_201_CREATED)
def tag_item(
    item_id: str, body: TagApply, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    if not body.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag name is empty"
        )
    tag = graph.tag_item(item_id, body.name)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return envelope(tag)


@router.delete("/{item_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def untag_item(item_id: str, tag_id: str, graph: GraphService = Depends(get_graph)) -> None:
    if not graph.untag_item(item_id, tag_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item or tag not found")


# --- Item note ---


@router.get("/{item_id}/note")
def get_note(item_id: str, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    note = graph.get_note(item_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No note for this item")
    return envelope(note)


@router.put("/{item_id}/note")
def put_note(
    item_id: str, body: NoteBody, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    note = graph.put_note(item_id, body.body)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return envelope(note)


@router.delete("/{item_id}/note", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(item_id: str, graph: GraphService = Depends(get_graph)) -> None:
    if not graph.delete_note(item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No note for this item")
