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
from starlette.middleware import Middleware
from starlette.routing import Route

from .api.config import router as config_router
from .api.errors import register_error_handlers
from .api.export import router as export_router
from .api.feeds import router as feeds_router
from .api.graph import router as graph_router
from .api.import_ import router as import_router
from .api.items import router as items_router
from .api.search import router as search_router
from .api.share import router as share_router
from .api.tags import router as tags_router
from .api.topics import router as topics_router
from .config import get_settings
from .graph import GraphService
from .mcp_server import ApiKeyMiddleware, create_mcp_server
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

    mcp = create_mcp_server(_graph, _poller)
    mcp_app = mcp.http_app(path="/mcp", middleware=[Middleware(ApiKeyMiddleware)])
    # A Starlette Mount always compiles its path regex as "<prefix>/{path}"
    # (see starlette.routing.Mount.__init__), so Mount("/mcp", ...) can only
    # ever match "/mcp/..." — never the bare "/mcp" itself. That's normally
    # invisible (Router.redirect_slashes 307s "/mcp" -> "/mcp/"), but the
    # frontend catch-all StaticFiles Mount("/") added in create_app fully
    # matches every path unconditionally, including the bare "/mcp", and
    # Starlette's router dispatches on the first full match in route order
    # — so the redirect fallback never triggers and the frontend mount
    # (405, since StaticFiles only serves GET/HEAD) shadows /mcp entirely.
    # Registering a plain Route instead of a Mount avoids the trailing-slash
    # requirement: Route matches the literal "/mcp" path exactly and, since
    # its endpoint is a class instance (not a function), Starlette treats it
    # as an ASGI app and dispatches straight into mcp_app — auth middleware
    # and all — without any of Mount's path-rewriting behaviour. Inserted at
    # index 0 so it is checked (and wins) before the frontend catch-all.
    app.router.routes.insert(0, Route("/mcp", endpoint=mcp_app, methods=None, name="mcp"))
    async with mcp_app.router.lifespan_context(mcp_app):
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
    app.include_router(export_router)
    app.include_router(import_router)
    app.include_router(search_router)
    app.include_router(topics_router)
    app.include_router(share_router)

    frontend_dist = Path(get_settings().frontend_path)
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
