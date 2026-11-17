# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from reed import poller as poller_module
from reed.graph import GraphService
from reed.poller import FeedPoller


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


class _Gauge:
    """Tracks the highest number of overlapping calls."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0
        self.total = 0

    async def hold(self) -> None:
        self.current += 1
        self.total += 1
        self.peak = max(self.peak, self.current)
        await asyncio.sleep(0.01)
        self.current -= 1


class TestPollConcurrency:
    async def test_due_feeds_are_polled_with_bounded_concurrency(self, graph):
        poller = FeedPoller(graph)
        poller._http = object()  # type: ignore[assignment]
        feeds = [
            {"url": f"https://example.com/{i}.xml", "last_fetched_at": None} for i in range(30)
        ]
        gauge = _Gauge()

        async def fake_poll_feed(*_args: object, **_kwargs: object) -> None:
            await gauge.hold()

        with (
            patch.object(graph, "list_feeds_for_polling", return_value=feeds),
            patch.object(poller, "_poll_feed", side_effect=fake_poll_feed),
        ):
            await poller._poll_due_feeds()

        assert gauge.total == 30, "every due feed is still polled"
        assert gauge.peak <= poller_module._POLL_CONCURRENCY

    async def test_one_failing_feed_does_not_stop_the_others(self, graph):
        poller = FeedPoller(graph)
        poller._http = object()  # type: ignore[assignment]
        feeds = [{"url": f"https://example.com/{i}.xml", "last_fetched_at": None} for i in range(8)]
        polled: list[str] = []

        async def fake_poll_feed(feed: dict, *_args: object, **_kwargs: object) -> None:
            polled.append(feed["url"])
            if feed["url"].endswith("/3.xml"):
                raise RuntimeError("boom")

        with (
            patch.object(graph, "list_feeds_for_polling", return_value=feeds),
            patch.object(poller, "_poll_feed", side_effect=fake_poll_feed),
        ):
            await poller._poll_due_feeds()

        assert len(polled) == 8


class TestExtractionConcurrency:
    async def test_extraction_limit_is_shared_across_feeds(self, graph):
        poller = FeedPoller(graph)
        gauge = _Gauge()

        async def fake_extract(*_args: object, **_kwargs: object) -> None:
            await gauge.hold()
            return None

        def batch(prefix: str) -> list[tuple[str, str, str]]:
            return [(f"{prefix}-{i}", f"https://example.com/{prefix}/{i}", "") for i in range(6)]

        with patch.object(poller_module, "extract_article", side_effect=fake_extract):
            # Ten feeds extract at the same moment, as after a restart.
            await asyncio.gather(
                *(poller._extract_new_items(batch(f"f{n}"), object()) for n in range(10))  # type: ignore[arg-type]
            )

        assert gauge.total == 60
        assert gauge.peak <= poller_module._EXTRACTION_CONCURRENCY


class TestBackfillBatching:
    def _make_items(self, graph: GraphService, n: int) -> list[str]:
        graph.create_feed("https://example.com/feed.xml", "Feed", "", "https://example.com")
        ids = []
        for i in range(n):
            item_id = graph.create_item(
                feed_url="https://example.com/feed.xml",
                guid=f"guid-{i}",
                url=f"https://example.com/{i}",
                title=f"Title {i}",
                summary="summary",
                content="content",
                author="",
                word_count=1,
                published_at=datetime.now(UTC),
                fetched_at=datetime.now(UTC),
            )
            assert item_id is not None
            ids.append(item_id)
        return ids

    def test_unenriched_ids_exclude_enriched_items(self, graph):
        ids = self._make_items(graph, 3)
        graph.enrich_item(ids[0], [])
        assert set(graph.get_unenriched_item_ids()) == set(ids[1:])

    def test_items_for_enrichment_returns_text_for_requested_ids(self, graph):
        ids = self._make_items(graph, 3)
        rows = graph.get_items_for_enrichment(ids[:2])
        assert {r["id"] for r in rows} == set(ids[:2])
        assert all(r["content"] == "content" for r in rows)
        assert graph.get_items_for_enrichment([]) == []

    async def test_backfill_loads_text_in_batches_and_enriches_everything(self, graph):
        ids = self._make_items(graph, 7)
        poller = FeedPoller(graph)
        batch_sizes: list[int] = []
        real = graph.get_items_for_enrichment

        def spy(batch_ids: list[str]):
            batch_sizes.append(len(batch_ids))
            return real(batch_ids)

        def fake_enrich(item_id: str, _text: str) -> None:
            graph.enrich_item(item_id, [])

        with (
            patch.object(poller_module, "_BACKFILL_BATCH", 3),
            patch.object(graph, "get_items_for_enrichment", side_effect=spy),
            patch.object(poller, "_enrich_item", side_effect=fake_enrich),
        ):
            await poller._backfill_topics()

        assert batch_sizes == [3, 3, 1]
        assert graph.get_unenriched_item_ids() == []
        assert len(ids) == 7

    async def test_backfill_with_nothing_to_do_loads_nothing(self, graph):
        poller = FeedPoller(graph)
        with patch.object(graph, "get_items_for_enrichment") as loader:
            await poller._backfill_topics()
        loader.assert_not_called()
