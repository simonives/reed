# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

"""Security-review finding on PR #183 — recompute_derived_edges holding
_conn_lock across its full body (#168) means every graph.* call the poller
makes directly on the event-loop thread (not via asyncio.to_thread) can
block behind a long recompute, freezing the whole ASGI event loop rather
than just degrading gracefully in the worker threadpool. These tests assert
every graph.*/effective_config call the poller's async methods make is
routed through asyncio.to_thread."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from reed.config import effective_config
from reed.graph import GraphService
from reed.poller import FeedPoller


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


@pytest.mark.asyncio
async def test_maybe_recompute_edges_offloads_effective_config(graph):
    poller = FeedPoller(graph)
    with (
        patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread,
        patch.object(poller, "recompute_derived_edges"),
    ):
        await poller._maybe_recompute_edges()
    assert any(c.args[0] is effective_config for c in mock_to_thread.call_args_list)


@pytest.mark.asyncio
async def test_recompute_derived_edges_offloads_effective_config_when_no_config_passed(graph):
    poller = FeedPoller(graph)
    with patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread:
        await poller.recompute_derived_edges()
    assert any(c.args[0] is effective_config for c in mock_to_thread.call_args_list)


@pytest.mark.asyncio
async def test_refresh_feed_offloads_effective_config(graph):
    poller = FeedPoller(graph)
    poller._http = None
    feed = graph.create_feed(url="https://example.com/feed", title="F", description="", site_url="")
    with (
        patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread,
        patch.object(poller, "_poll_feed"),
    ):
        await poller.refresh_feed({"url": feed})
    assert any(c.args[0] is effective_config for c in mock_to_thread.call_args_list)


@pytest.mark.asyncio
async def test_poll_due_feeds_offloads_effective_config_and_list_feeds_for_polling(graph):
    poller = FeedPoller(graph)
    poller._http = object()
    with patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread:
        await poller._poll_due_feeds()
    offloaded = [c.args[0] for c in mock_to_thread.call_args_list]
    assert effective_config in offloaded
    assert graph.list_feeds_for_polling in offloaded


@pytest.mark.asyncio
async def test_poll_feed_offloads_update_feed_poll_metadata_on_not_modified(graph):
    poller = FeedPoller(graph)
    feed_url = graph.create_feed(
        url="https://example.com/feed", title="F", description="", site_url=""
    )
    feed = {"url": feed_url}
    now = datetime.now(UTC)
    config = effective_config(graph)

    class _NotModifiedResponse:
        status_code = 304
        headers: dict[str, str] = {}

    with (
        patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread,
        patch("reed.poller.safe_get", return_value=_NotModifiedResponse()),
    ):
        await poller._poll_feed(feed, now, object(), config)
    assert any(c.args[0] == graph.update_feed_poll_metadata for c in mock_to_thread.call_args_list)


@pytest.mark.asyncio
async def test_poll_feed_offloads_update_feed_poll_metadata_on_error(graph):
    poller = FeedPoller(graph)
    feed_url = graph.create_feed(
        url="https://example.com/feed", title="F", description="", site_url=""
    )
    feed = {"url": feed_url}
    now = datetime.now(UTC)
    config = effective_config(graph)

    with (
        patch.object(asyncio, "to_thread", wraps=asyncio.to_thread) as mock_to_thread,
        patch("reed.poller.safe_get", side_effect=RuntimeError("boom")),
    ):
        await poller._poll_feed(feed, now, object(), config)
    assert any(c.args[0] == graph.update_feed_poll_metadata for c in mock_to_thread.call_args_list)
