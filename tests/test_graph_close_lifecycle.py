# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from reed.graph import GraphService
from reed.main import _shutdown_graph


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    with g._conn_lock:
        pass


@pytest.mark.asyncio
async def test_shutdown_graph_closes_off_the_event_loop_thread(graph):
    """#162 — main.py's shutdown must close the graph off the event-loop
    thread, so a recompute still holding _conn_lock in a background thread
    can't stall the whole event loop during app shutdown. Asserted
    structurally (asyncio.to_thread is used) rather than via wall-clock
    timing, which is prone to false failures on a loaded CI runner."""
    with patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread:
        await _shutdown_graph(graph)
    mock_to_thread.assert_called_once_with(graph.close)


def test_buffer_pool_limit_is_passed_to_kuzu_in_bytes(tmp_path, monkeypatch):
    import kuzu

    captured = {}
    real_database = kuzu.Database

    def spy(path, **kwargs):
        captured.update(kwargs)
        return real_database(path, **kwargs)

    monkeypatch.setattr("reed.graph.kuzu.Database", spy)
    g = GraphService(str(tmp_path / "pool.kuzu"), buffer_pool_mb=64)
    g.close()
    assert captured["buffer_pool_size"] == 64 * 1024 * 1024


def test_no_buffer_pool_limit_keeps_kuzu_default(tmp_path, monkeypatch):
    import kuzu

    captured = {}
    real_database = kuzu.Database

    def spy(path, **kwargs):
        captured.update(kwargs)
        return real_database(path, **kwargs)

    monkeypatch.setattr("reed.graph.kuzu.Database", spy)
    g = GraphService(str(tmp_path / "default.kuzu"))
    g.close()
    assert "buffer_pool_size" not in captured
