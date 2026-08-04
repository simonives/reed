# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.config import router as config_router
from .api.data import router as data_router
from .api.errors import register_error_handlers
from .api.feeds import router as feeds_router
from .api.graph import router as graph_router
from .api.items import router as items_router
from .api.opml import router as opml_router
from .api.search import router as search_router
from .api.share import router as share_router
from .api.tags import router as tags_router
from .api.topics import router as topics_router
from .config import get_settings
from .graph import GraphService
from .poller import FeedPoller

logger = logging.getLogger(__name__)

_graph: GraphService | None = None
_poller: FeedPoller | None = None
_poller_task: asyncio.Task[None] | None = None


async def _shutdown_graph(graph: GraphService) -> None:
    # close() blocks on _conn_lock, a threading.RLock also held (via
    # asyncio.to_thread) by an in-flight recompute. Calling it directly here
    # would stall the whole event loop until that lock is free (#162), so run
    # it off-thread instead.
    await asyncio.to_thread(graph.close)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _graph, _poller, _poller_task
    settings = get_settings()

    _graph = GraphService(settings.data_path)
    app.state.graph = _graph

    _poller = FeedPoller(_graph)
    app.state.poller = _poller
    _poller_task = asyncio.create_task(_poller.start())

    logger.info("Reed started")
    yield

    if _poller:
        await _poller.stop()
    if _poller_task:
        _poller_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _poller_task
    if _graph:
        await _shutdown_graph(_graph)
    logger.info("Reed stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Reed",
        description="A self-hosted, open-source RSS reader with a graph-native data model.",
        version="0.1.0",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    app.include_router(feeds_router)
    app.include_router(graph_router)
    app.include_router(items_router)
    app.include_router(tags_router)
    app.include_router(config_router)
    app.include_router(opml_router)
    app.include_router(search_router)
    app.include_router(data_router)
    app.include_router(topics_router)
    app.include_router(share_router)

    frontend_dist = Path(get_settings().frontend_path)
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
