# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import feedparser
import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from starlette.datastructures import UploadFile as StarletteUploadFile

from ..graph import GraphService
from ..http import UnsafeURLError, http_client, safe_get
from ..opml import parse_opml
from .deps import get_graph, require_api_key
from .schemas import envelope

logger = logging.getLogger(__name__)

MAX_OPML_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_RESTORE_BYTES = 50 * 1024 * 1024  # 50 MB

# "config" is intentionally not required: /export/json omits it deliberately
# (see the content-split decision above), and a restore without it is well
# defined — restore_data() already treats a missing "config" key as "restore
# no config overrides," leaving every setting at its CONFIG_DEFAULTS value via
# effective_config()'s merge. Requiring it here would mean a /export/json
# backup could never be restored at all, permanently locking a user out of
# their own data if that was the only export they kept (adversarial review
# finding, judgement call 1 — resolved by relaxing this set rather than by a
# documentation-only warning).
_REQUIRED_KEYS = {"version", "feeds", "items", "notes", "tags"}

router = APIRouter(
    prefix="/api/v1/import",
    tags=["import"],
    dependencies=[Depends(require_api_key)],
)


class ImportFeedItem(BaseModel):
    url: str
    title: str
    tags: list[str] = []


class ImportBody(BaseModel):
    feeds: list[ImportFeedItem] = []


def _fetch_fail_reason(exc: Exception) -> str:
    """Mirror subscribe()'s outbound-fetch error mapping (feeds.py's
    _fetch_error_422) as a plain string for the failed[] report: an
    UnsafeURLError is an SSRF refusal, any other httpx.HTTPError is a plain
    fetch failure.
    """
    prefix = "Refusing to fetch" if isinstance(exc, UnsafeURLError) else "Could not fetch"
    return f"{prefix}: {exc}"


@router.post("/opml/preview")
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


@router.post("/opml")
async def import_opml(
    body: ImportBody,
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    # Deviation from the task brief's draft (2026-07-24): the draft called
    # graph.create_feed directly per submitted item with no fetch/validation
    # step, which would regress #139 (OPML import bypassing feed validation
    # and silently creating broken feed nodes). This mirrors the fetch +
    # feedparser version check that subscribe() (feeds.py) and the old
    # api/opml.py's import_opml both perform, and also folds in #155's fix:
    # description/site_url are populated from the fetched feed's own
    # metadata instead of being hardcoded to "".
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
        feed_meta = parsed.feed

        try:
            await asyncio.to_thread(
                graph.create_feed,
                url=item.url,
                title=item.title or feed_meta.get("title") or item.url,
                description=feed_meta.get("description", ""),
                site_url=feed_meta.get("link", ""),
                tags=item.tags,
            )
            added += 1
        except Exception:
            logger.exception("create_feed failed during OPML import for %s", item.url)
            failed.append({"url": item.url, "reason": "Could not create feed"})
    return envelope({"added": added, "skipped": skipped, "failed": failed})


@router.post("/backup")
async def import_backup(
    request: Request,
    x_confirm_destructive: str | None = Header(default=None),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
    # The header is checked BEFORE the multipart body is touched. Declaring
    # `file: UploadFile = File(...)` as a function parameter (the original
    # draft of this route) makes FastAPI parse and spool the entire multipart
    # body as part of resolving that parameter, before the function body ever
    # runs — so a request missing the header would still pay the full
    # upload-parsing cost before being rejected (adversarial review finding).
    # Taking `request: Request` instead and calling `request.form()`
    # ourselves, only after this check, defers that parse until it's known to
    # be worth doing.
    if x_confirm_destructive != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This operation replaces all instance data. "
            "Retry with the X-Confirm-Destructive: true header to proceed.",
        )
    form = await request.form()
    file = form.get("file")
    # request.form() (a Starlette Request method, unlike the fastapi.File()
    # dependency used elsewhere in this module) yields Starlette's base
    # UploadFile, not fastapi's UploadFile subclass — isinstance against the
    # fastapi type would reject every real upload, so check the base class.
    if not isinstance(file, StarletteUploadFile):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Expected a file upload named 'file'"
        )
    raw = await file.read(MAX_RESTORE_BYTES + 1)
    if len(raw) > MAX_RESTORE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Backup file exceeds {MAX_RESTORE_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        ) from exc
    # Accept both envelope format {"data": {...backup...}} and legacy raw format.
    unwrapped = parsed.get("data") if isinstance(parsed, dict) else None
    backup = unwrapped if isinstance(unwrapped, dict) else parsed
    if not isinstance(backup, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup must be a JSON object",
        )
    missing = _REQUIRED_KEYS - set(backup.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backup missing required keys: {sorted(missing)}",
        )
    summary = await asyncio.to_thread(graph.restore_data, backup)
    return envelope(summary)
