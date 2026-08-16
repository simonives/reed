# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from reed.graph import GraphService
from reed.poller import FeedPoller


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


@pytest.mark.asyncio
async def test_maybe_recompute_runs_when_never_run_before(graph):
    poller = FeedPoller(graph)
    assert poller._last_recompute is None
    with patch.object(poller, "recompute_derived_edges") as mock_recompute:
        mock_recompute.return_value = None
        await poller._maybe_recompute_edges()
    mock_recompute.assert_called_once()


@pytest.mark.asyncio
async def test_maybe_recompute_skips_when_interval_not_elapsed(graph, monkeypatch):
    monkeypatch.setenv("REED_DERIVED_EDGE_INTERVAL", "360")
    from reed.config import get_settings

    get_settings.cache_clear()
    poller = FeedPoller(graph)
    poller._last_recompute = datetime.now(UTC)  # just ran
    with patch.object(poller, "recompute_derived_edges") as mock_recompute:
        await poller._maybe_recompute_edges()
    mock_recompute.assert_not_called()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_maybe_recompute_runs_when_interval_elapsed(graph, monkeypatch):
    monkeypatch.setenv("REED_DERIVED_EDGE_INTERVAL", "360")
    from reed.config import get_settings

    get_settings.cache_clear()
    poller = FeedPoller(graph)
    poller._last_recompute = datetime.now(UTC) - timedelta(minutes=361)
    with patch.object(poller, "recompute_derived_edges") as mock_recompute:
        mock_recompute.return_value = None
        await poller._maybe_recompute_edges()
    mock_recompute.assert_called_once()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_recompute_derived_edges_calls_graph_with_config_values(graph):
    graph.set_config_value("similarity_window_days", 45)
    graph.set_config_value("similarity_score_threshold", 0.2)
    graph.set_config_value("similarity_max_topic_share", 0.1)
    graph.set_config_value("similarity_topic_share_floor", 25)
    poller = FeedPoller(graph)
    with patch.object(graph, "recompute_derived_edges") as mock_graph_recompute:
        await poller.recompute_derived_edges()
    mock_graph_recompute.assert_called_once()
    _, kwargs = mock_graph_recompute.call_args
    assert kwargs["window_days"] == 45
    assert kwargs["score_threshold"] == pytest.approx(0.2)
    assert kwargs["max_topic_share"] == pytest.approx(0.1)
    assert kwargs["topic_share_floor"] == 25


@pytest.mark.asyncio
async def test_recompute_derived_edges_is_noop_while_already_in_progress(graph):
    poller = FeedPoller(graph)
    poller._recompute_in_progress = True
    with patch.object(graph, "recompute_derived_edges") as mock_graph_recompute:
        await poller.recompute_derived_edges()
    mock_graph_recompute.assert_not_called()


@pytest.mark.asyncio
async def test_recompute_derived_edges_updates_last_recompute_timestamp(graph):
    poller = FeedPoller(graph)
    with patch.object(graph, "recompute_derived_edges"):
        before = datetime.now(UTC)
        await poller.recompute_derived_edges()
        after = datetime.now(UTC)
    assert poller._last_recompute is not None
    assert before <= poller._last_recompute <= after
