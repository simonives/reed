# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import feedparser
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from ..graph import GraphService
from ..http import UnsafeURLError, http_client, safe_get
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
        result = await asyncio.to_thread(parse_opml, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    candidates = await asyncio.to_thread(
        lambda: [
            {
                "url": c.url,
                "title": c.title,
                "tags": c.tags,
                "already_subscribed": graph.feed_exists(c.url),
            }
            for c in result.candidates
        ]
    )
    return envelope({"candidates": candidates, "unparseable": result.unparseable})


def _fetch_fail_reason(exc: Exception) -> str:
    """Mirror subscribe()'s outbound-fetch error mapping (see feeds.py's
    _fetch_error_422) as a plain string for the failed[] report: an
    UnsafeURLError is an SSRF refusal, any other httpx.HTTPError is a plain
    fetch failure.
    """
    prefix = "Refusing to fetch" if isinstance(exc, UnsafeURLError) else "Could not fetch"
    return f"{prefix}: {exc}"


@router.post("/import")
async def import_opml(
    body: ImportBody,
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    added = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    for item in body.feeds:
        if await asyncio.to_thread(graph.feed_exists, item.url):
            skipped += 1
            continue

        try:
            async with http_client() as client:
                response = await safe_get(client, item.url)
            response.raise_for_status()
        except (UnsafeURLError, httpx.HTTPError) as exc:
            failed.append({"url": item.url, "reason": _fetch_fail_reason(exc)})
            continue

        try:
            parsed = await asyncio.to_thread(feedparser.parse, response.content)
        except Exception as exc:
            failed.append({"url": item.url, "reason": f"Feed parse error: {exc}"})
            continue
        if not parsed.get("version"):
            failed.append(
                {"url": item.url, "reason": "URL does not point to a valid RSS or Atom feed"}
            )
            continue

        try:
            await asyncio.to_thread(
                graph.create_feed,
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
def export_opml(graph: GraphService = Depends(get_graph)) -> Response:
    feeds = graph.list_feeds()
    content = build_opml(feeds)
    filename = f"reed-feeds-{date.today().isoformat()}.opml"
    return Response(
        content=content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
