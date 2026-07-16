# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ..config import FONT_FAMILY_STACKS, effective_config
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
    accent_color: str | None = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    font_size_base: int | None = Field(default=None, ge=12, le=24)
    reading_width: int | None = Field(default=None, ge=480, le=1200)
    line_height: float | None = Field(default=None, ge=1.2, le=2.2)
    font_family_reading: str | None = None

    @field_validator("font_family_reading")
    @classmethod
    def _valid_font_family(cls, v: str | None) -> str | None:
        if v is not None and v not in FONT_FAMILY_STACKS:
            raise ValueError("unsupported font family")
        return v


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
