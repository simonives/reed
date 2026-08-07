# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from ..graph import GraphService
from ..opml import build_opml
from .deps import get_graph, require_api_key

router = APIRouter(
    prefix="/api/v1/export",
    tags=["export"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/opml")
def export_opml(graph: GraphService = Depends(get_graph)) -> Response:
    feeds = graph.list_feeds()
    content = build_opml(feeds)
    filename = f"reed-feeds-{date.today().isoformat()}.opml"
    return Response(
        content=content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/backup")
def export_backup(graph: GraphService = Depends(get_graph)) -> Response:
    now = datetime.now(UTC)
    backup = graph.export_data(include_config=True)
    body = {"data": backup, "meta": {"exported_at": now.isoformat()}}
    content = json.dumps(body, ensure_ascii=False).encode("utf-8")
    filename = f"reed-backup-{now.date().isoformat()}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/json")
def export_json(graph: GraphService = Depends(get_graph)) -> Response:
    """Personal-data export: identical to /export/backup minus 'config'.

    IS restorable via /import/backup (which doesn't require the 'config' key)
    — this endpoint is about what's included, not about restorability.
    """
    now = datetime.now(UTC)
    backup = graph.export_data(include_config=False)
    body = {"data": backup, "meta": {"exported_at": now.isoformat()}}
    content = json.dumps(body, ensure_ascii=False).encode("utf-8")
    filename = f"reed-export-{now.date().isoformat()}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
