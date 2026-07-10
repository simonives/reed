# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .graph import GraphService
from .poller import FeedPoller

logger = logging.getLogger(__name__)

_graph: GraphService | None = None
_poller: FeedPoller | None = None
_poller_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _graph, _poller, _poller_task
    settings = get_settings()

    _graph = GraphService(settings.data_path)
    _poller = FeedPoller(_graph)
    _poller_task = asyncio.create_task(_poller.start())

    logger.info("Reed started")
    yield

    if _poller:
        await _poller.stop()
    if _poller_task:
        _poller_task.cancel()
    if _graph:
        _graph.close()
    logger.info("Reed stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Reed",
        description="A self-hosted, open-source RSS reader with a graph-native data model.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # API routers registered in M1

    frontend_dist = Path(get_settings().frontend_path)
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
