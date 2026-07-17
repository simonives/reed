# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

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
async def export_data(graph: GraphService = Depends(get_graph)) -> Response:
    backup = graph.export_data()
    content = json.dumps(backup, ensure_ascii=False).encode("utf-8")
    filename = f"reed-backup-{datetime.now(UTC).date().isoformat()}.json"
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
        backup = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        ) from exc
    missing = _REQUIRED_KEYS - set(backup.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backup missing required keys: {sorted(missing)}",
        )
    summary = graph.restore_data(backup)
    return envelope(summary)
