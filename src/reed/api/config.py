# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..config import effective_config
from ..graph import GraphService
from .deps import get_graph, require_api_key
from .schemas import envelope

router = APIRouter(
    prefix="/api/v1/config",
    tags=["config"],
    dependencies=[Depends(require_api_key)],
)


class ConfigUpdate(BaseModel):
    default_poll_interval_minutes: int | None = Field(default=None, ge=1)
    reader_mode_enabled: bool | None = None
    default_theme: str | None = Field(default=None, pattern="^(system|light|dark)$")
    items_per_page: int | None = Field(default=None, ge=1, le=200)
    mark_read_on_open: bool | None = None


@router.get("")
async def get_config(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    return envelope(effective_config(graph))


@router.patch("")
async def update_config(
    body: ConfigUpdate, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No config values provided"
        )
    for key, value in updates.items():
        graph.set_config_value(key, value)
    return envelope(effective_config(graph))
