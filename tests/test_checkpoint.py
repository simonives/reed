"""Periodic CHECKPOINT keeps Kuzu's un-flushed write data from accumulating (#355)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from reed.graph import GraphService
from reed.poller import FeedPoller
from tests.conftest import fake_stream, mock_http_response


def _gs(tmp_path):
    return GraphService(str(tmp_path / "t.kuzu"))


def test_checkpoint_keeps_data_and_is_safe_after_close(tmp_path):
    g = _gs(tmp_path)
    g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
    g.checkpoint()
    assert len(g.list_feeds()) == 1
    g.close()
    g.checkpoint()  # no error once closed


def test_checkpoint_failure_is_logged_not_raised(tmp_path):
    g = _gs(tmp_path)
    with patch.object(g._conn, "execute", side_effect=RuntimeError("boom")):
        g.checkpoint()
    g.close()


async def test_poll_cycle_checkpoints_once_after_the_batch_write(tmp_path):
    g = _gs(tmp_path)
    g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
    poller = FeedPoller(g)
    client = AsyncMock()
    client.stream = fake_stream(lambda url, **kw: mock_http_response())
    poller._http = client
    order: list[str] = []
    real_batch = g.update_feed_poll_metadata_batch
    with (
        patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])),
        patch.object(
            g,
            "update_feed_poll_metadata_batch",
            side_effect=lambda u: (order.append("batch"), real_batch(u))[1],
        ),
        patch.object(g, "checkpoint", side_effect=lambda: order.append("checkpoint")),
    ):
        await poller._poll_due_feeds()
    assert order == ["batch", "checkpoint"]
    g.close()


async def test_idle_cycle_does_not_checkpoint(tmp_path):
    g = _gs(tmp_path)  # no feeds, nothing to write
    poller = FeedPoller(g)
    poller._http = AsyncMock()
    with patch.object(g, "checkpoint") as cp:
        await poller._poll_due_feeds()
    cp.assert_not_called()
    g.close()
