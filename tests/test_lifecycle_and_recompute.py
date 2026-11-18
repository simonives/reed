"""Graceful shutdown, thread cap and recompute scheduling (#347, #348, #349)."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest

from reed.graph import GraphService, _rows
from reed.poller import FeedPoller
from tests.conftest import create_test_item


def _gs(tmp_path, **kw):
    return GraphService(str(tmp_path / "t.kuzu"), **kw)


class TestClose:
    def test_use_after_close_raises_cleanly(self, tmp_path):
        g = _gs(tmp_path)
        g.close()
        with pytest.raises(RuntimeError, match="closed"):
            g.list_feeds()

    def test_close_is_idempotent(self, tmp_path):
        g = _gs(tmp_path)
        g.close()
        g.close()

    def test_data_survives_close_and_reopen(self, tmp_path):
        g = _gs(tmp_path)
        g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
        g.close()
        g2 = _gs(tmp_path)
        assert [f["url"] for f in g2.list_feeds()] == ["https://f.example/rss"]
        g2.close()

    def test_close_waits_for_a_statement_in_flight(self, tmp_path):
        g = _gs(tmp_path)
        started, results = threading.Event(), []

        def worker():
            with g._conn_lock:
                started.set()
                threading.Event().wait(0.3)
                results.append(g.list_feeds())

        t = threading.Thread(target=worker)
        t.start()
        started.wait()
        g.close()  # blocks on the lock until the worker releases it
        t.join()
        assert results == [[]]


def test_max_threads_option_is_accepted(tmp_path):
    g = _gs(tmp_path, buffer_pool_mb=256, max_threads=2)
    g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
    assert len(g.list_feeds()) == 1
    g.close()


class TestPollerShutdown:
    async def test_wait_idle_returns_when_nothing_is_running(self, tmp_path):
        g = _gs(tmp_path)
        await FeedPoller(g).wait_idle(timeout=1)
        g.close()

    async def test_wait_idle_waits_for_thread_work(self, tmp_path):
        g = _gs(tmp_path)
        poller = FeedPoller(g)
        done = threading.Event()

        def slow():
            done.wait(0.3)
            return 1

        task = asyncio.create_task(poller._in_thread(slow))
        await asyncio.sleep(0.05)
        assert poller._threads_in_flight == 1
        await poller.wait_idle(timeout=3)
        assert poller._threads_in_flight == 0
        await task
        g.close()

    async def test_wait_idle_gives_up_after_timeout(self, tmp_path):
        g = _gs(tmp_path)
        poller = FeedPoller(g)
        poller._threads_in_flight = 1  # simulate stuck work
        await poller.wait_idle(timeout=0.2)
        g.close()


class TestRecomputeSchedule:
    def test_last_derived_edge_time_none_without_edges(self, tmp_path):
        g = _gs(tmp_path)
        assert g.last_derived_edge_time() is None
        g.close()

    async def test_restart_does_not_force_a_recompute(self, tmp_path):
        g = _gs(tmp_path)
        g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
        a = create_test_item(g, feed_url="https://f.example/rss", guid="a", url="u1", title="a")
        b = create_test_item(g, feed_url="https://f.example/rss", guid="b", url="u2", title="b")
        now = datetime.now(UTC)
        g._execute("MATCH (i:Item) SET i.published_at = $t", {"t": now})
        g._execute(
            "MATCH (x:Item {id: $a}), (y:Item {id: $b}) "
            "CREATE (x)-[:SIMILAR_TO {score: 0.5, computed_at: $t}]->(y)",
            {"a": a, "b": b, "t": now},
        )
        stamp = g.last_derived_edge_time()
        assert stamp is not None
        assert abs((stamp - now).total_seconds()) < 1

        poller = FeedPoller(g)
        poller._last_recompute = stamp  # what start() does
        calls = []
        poller.recompute_derived_edges = lambda config=None: calls.append(1) or asyncio.sleep(0)
        await poller._maybe_recompute_edges()
        assert calls == []
        g.close()


class TestDominanceCapUsesWindow:
    def test_old_items_do_not_inflate_the_cap(self, tmp_path):
        """With 400 old items and 20 recent ones, a topic on 15 recent items must
        be judged against the 20 in-window items, not all 420 (#246)."""
        g = _gs(tmp_path)
        g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
        now = datetime.now(UTC)
        ids = []
        for n in range(20):
            ids.append(
                create_test_item(
                    g, feed_url="https://f.example/rss", guid=f"new{n}", url=f"u{n}", title="t"
                )
            )
        g._execute("MATCH (i:Item) SET i.published_at = $t", {"t": now})
        for n in range(400):
            create_test_item(
                g, feed_url="https://f.example/rss", guid=f"old{n}", url=f"o{n}", title="t"
            )
        g._execute(
            "MATCH (i:Item) WHERE i.guid STARTS WITH 'old' SET i.published_at = $t",
            {"t": now - timedelta(days=400)},
        )
        for iid in ids[:15]:
            g.enrich_item(iid, [("dominant", 0.9), ("rare", 0.5)])
        g.recompute_derived_edges(
            window_days=90, score_threshold=0.0, max_topic_share=0.5, topic_share_floor=1
        )
        # cap = max(1, int(20 * 0.5)) = 10 < 15 items on "dominant": it is excluded, so
        # no SIMILAR_TO edges form. Using all 420 items the cap would be 210 and it
        # would be included.
        n = _rows(g._execute("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n"))[0]["n"]
        assert n == 0
        g.close()
