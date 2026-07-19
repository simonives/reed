# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from ..graph import GraphService
from .deps import get_graph, require_api_key
from .schemas import envelope

MAX_RESTORE_BYTES = 50 * 1024 * 1024  # 50 MB

_REQUIRED_KEYS = {"version", "feeds", "items", "notes", "tags", "config"}

router = APIRouter(
    prefix="/api/v1/data",
    tags=["data"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/export")
def export_data(graph: GraphService = Depends(get_graph)) -> Response:
    now = datetime.now(UTC)
    backup = graph.export_data()
    body = {"data": backup, "meta": {"exported_at": now.isoformat()}}
    content = json.dumps(body, ensure_ascii=False).encode("utf-8")
    filename = f"reed-backup-{now.date().isoformat()}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/restore")
async def restore_data(
    file: UploadFile = File(...),
    graph: GraphService = Depends(get_graph),
) -> dict[str, Any]:
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
    # Guard: if "data" key exists but is not a dict, treat the whole parsed value as the backup
    # so malformed envelopes get a clean 400 rather than an AttributeError.
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
