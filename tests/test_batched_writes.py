"""One write per item enrichment and one per poll cycle (#338)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx

from reed.graph import GraphService, _rows
from reed.poller import FeedPoller
from tests.conftest import create_test_item, fake_stream, mock_http_response


def _gs(tmp_path):
    g = GraphService(str(tmp_path / "t.kuzu"))
    g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
    return g


def _item(g, n=1):
    return create_test_item(
        g,
        feed_url="https://f.example/rss",
        guid=f"g{n}",
        url=f"https://f.example/{n}",
        title=f"T{n}",
    )


def _topics(g):
    return {
        r["n"]: r["c"]
        for r in _rows(g._execute("MATCH (t:Topic) RETURN t.name AS n, t.item_count AS c"))
    }


class TestEnrichItem:
    def test_links_all_keywords_and_marks_enriched(self, tmp_path):
        g = _gs(tmp_path)
        iid = _item(g)
        g.enrich_item(iid, [("alpha", 0.9), ("beta", 0.5)])
        assert _topics(g) == {"alpha": 1, "beta": 1}
        assert g.get_unenriched_item_ids() == []
        g.close()

    def test_is_idempotent(self, tmp_path):
        g = _gs(tmp_path)
        iid = _item(g)
        g.enrich_item(iid, [("alpha", 0.9)])
        g.enrich_item(iid, [("alpha", 0.9), ("beta", 0.5)])
        assert _topics(g) == {"alpha": 1, "beta": 1}  # not double counted
        n = _rows(g._execute("MATCH ()-[a:ABOUT]->() RETURN count(a) AS n"))[0]["n"]
        assert n == 2
        g.close()

    def test_item_count_is_per_item(self, tmp_path):
        g = _gs(tmp_path)
        g.enrich_item(_item(g, 1), [("alpha", 0.9)])
        g.enrich_item(_item(g, 2), [("alpha", 0.4)])
        assert _topics(g) == {"alpha": 2}
        g.close()

    def test_duplicate_keywords_in_one_call_count_once(self, tmp_path):
        g = _gs(tmp_path)
        g.enrich_item(_item(g), [("alpha", 0.9), ("alpha", 0.2)])
        assert _topics(g) == {"alpha": 1}
        g.close()

    def test_no_keywords_still_marks_enriched(self, tmp_path):
        g = _gs(tmp_path)
        iid = _item(g)
        g.enrich_item(iid, [])
        assert g.get_unenriched_item_ids() == []
        g.close()

    def test_uses_one_write_statement(self, tmp_path):
        g = _gs(tmp_path)
        iid = _item(g)
        with patch.object(g, "_execute", wraps=g._execute) as spy:
            g.enrich_item(iid, [(f"kw{i}", 0.5) for i in range(10)])
        assert spy.call_count == 1
        g.close()


class TestPollMetadataBatch:
    def test_batch_matches_single_update_semantics(self, tmp_path):
        g = _gs(tmp_path)
        g.create_feed(url="https://g.example/rss", title="G", description="", site_url="")
        now = datetime.now(UTC)
        g.update_feed_poll_metadata_batch(
            [
                ("https://f.example/rss", now, "e1", "lm1", None),
                ("https://g.example/rss", now, None, None, "boom"),
            ]
        )
        g.update_feed_poll_metadata_batch([("https://g.example/rss", now, None, None, "boom")])
        feeds = {f["url"]: f for f in g.list_feeds()}
        assert feeds["https://f.example/rss"]["etag"] == "e1"
        assert feeds["https://f.example/rss"]["consecutive_errors"] == 0
        assert feeds["https://g.example/rss"]["consecutive_errors"] == 2
        assert feeds["https://g.example/rss"]["last_error"] == "boom"
        g.close()

    def test_empty_batch_is_a_noop(self, tmp_path):
        g = _gs(tmp_path)
        with patch.object(g, "_execute") as spy:
            g.update_feed_poll_metadata_batch([])
        spy.assert_not_called()
        g.close()

    async def test_poll_cycle_flushes_metadata_once(self, tmp_path):
        g = _gs(tmp_path)
        for i in range(3):
            g.create_feed(url=f"https://x{i}.example/rss", title="X", description="", site_url="")
        poller = FeedPoller(g)
        client = AsyncMock()
        client.stream = fake_stream(lambda url, **kw: mock_http_response())
        poller._http = client
        with (
            patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])),
            patch.object(
                g, "update_feed_poll_metadata_batch", wraps=g.update_feed_poll_metadata_batch
            ) as batch,
            patch.object(g, "update_feed_poll_metadata") as single,
        ):
            await poller._poll_due_feeds()
        assert batch.call_count == 1
        assert len(batch.call_args.args[0]) == 4
        single.assert_not_called()
        assert all(f["last_fetched_at"] is not None for f in g.list_feeds())
        g.close()

    async def test_failure_is_recorded_in_the_batch(self, tmp_path):
        g = _gs(tmp_path)
        poller = FeedPoller(g)
        client = AsyncMock()
        client.stream = fake_stream(httpx.ConnectError("down"))
        poller._http = client
        with patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])):
            await poller._poll_due_feeds()
        feed = g.list_feeds()[0]
        assert feed["consecutive_errors"] == 1
        assert "down" in feed["last_error"]
        g.close()
