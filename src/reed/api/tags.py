# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..graph import GraphService
from .deps import get_graph, require_api_key
from .schemas import envelope

router = APIRouter(
    prefix="/api/v1/tags",
    tags=["tags"],
    dependencies=[Depends(require_api_key)],
)


class TagCreate(BaseModel):
    name: str


@router.get("")
async def list_tags(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    return envelope(graph.list_tags())


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tag(body: TagCreate, graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag name is empty"
        )
    return envelope(graph.ensure_tag(name))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: str, graph: GraphService = Depends(get_graph)) -> None:
    if not graph.delete_tag(tag_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
