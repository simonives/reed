# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from ..config import get_settings
from ..graph import GraphService
from ..poller import FeedPoller

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_scheme)) -> None:
    settings = get_settings()
    if not settings.api_key:
        return  # No key configured — open access (dev mode)
    if api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def get_graph(request: Request) -> GraphService:
    return request.app.state.graph  # type: ignore[no-any-return]


def get_poller(request: Request) -> FeedPoller:
    return request.app.state.poller  # type: ignore[no-any-return]
