# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import logging

from .graph import GraphService

logger = logging.getLogger(__name__)


class FeedPoller:
    """Async background worker that polls subscribed feeds on schedule.

    Runs inside the same process as FastAPI via asyncio.create_task().
    Full implementation in M1.
    """

    def __init__(self, graph: GraphService) -> None:
        self._graph = graph
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Feed poller started")
        while self._running:
            await self._poll_due_feeds()
            await asyncio.sleep(60)

    async def stop(self) -> None:
        self._running = False

    async def _poll_due_feeds(self) -> None:
        pass  # implemented in M1
