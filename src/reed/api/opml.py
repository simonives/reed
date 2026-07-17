# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from ..graph import GraphService
from ..opml import build_opml, parse_opml
from .deps import get_graph, require_api_key
from .schemas import envelope

MAX_OPML_BYTES = 2 * 1024 * 1024  # 2 MB

router = APIRouter(
    prefix="/api/v1/opml",
    tags=["opml"],
    dependencies=[Depends(require_api_key)],
)


class ImportFeedItem(BaseModel):
    url: str
    title: str
    tags: list[str] = []


class ImportBody(BaseModel):
    feeds: list[ImportFeedItem] = []


@router.post("/preview")
async def preview_opml(
    file: UploadFile = File(...),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    data = await file.read(MAX_OPML_BYTES + 1)
    if len(data) > MAX_OPML_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"OPML file exceeds {MAX_OPML_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        result = parse_opml(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    candidates = [
        {
            "url": c.url,
            "title": c.title,
            "tags": c.tags,
            "already_subscribed": graph.feed_exists(c.url),
        }
        for c in result.candidates
    ]
    return envelope({"candidates": candidates, "unparseable": result.unparseable})


@router.post("/import")
async def import_opml(
    body: ImportBody,
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    added = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    for item in body.feeds:
        if graph.feed_exists(item.url):
            skipped += 1
            continue
        try:
            graph.create_feed(
                url=item.url,
                title=item.title,
                description="",
                site_url="",
                tags=item.tags,
            )
            added += 1
        except Exception as exc:
            failed.append({"url": item.url, "reason": str(exc)})
    return envelope({"added": added, "skipped": skipped, "failed": failed})


@router.get("/export")
async def export_opml(graph: GraphService = Depends(get_graph)) -> Response:
    feeds = graph.list_feeds()
    content = build_opml(feeds)
    filename = f"reed-feeds-{date.today().isoformat()}.opml"
    return Response(
        content=content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
