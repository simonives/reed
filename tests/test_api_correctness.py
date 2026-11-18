"""Small API correctness fixes (#352, #353)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from reed.api.feeds import FeedAlreadySubscribedError, discover_and_create_feed
from reed.graph import GraphService
from reed.poller import FeedPoller

ATOM_UPDATED_ONLY = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>A</title><id>urn:a</id><updated>2026-11-01T00:00:00Z</updated>
  <entry><title>Only updated</title><id>urn:a:1</id>
    <link href="https://a.example/1"/><updated>2026-11-01T10:20:30Z</updated>
    <summary>s</summary></entry>
</feed>"""


def test_atom_updated_is_used_when_published_missing(tmp_path):
    g = GraphService(str(tmp_path / "t.kuzu"))
    g.create_feed(url="https://a.example/atom", title="A", description="", site_url="")
    FeedPoller(g)._ingest_entries("https://a.example/atom", ATOM_UPDATED_ONLY, datetime.now(UTC))
    items, _ = g.list_items(limit=5)
    item = items[0]
    assert item["published_at"] is not None
    assert str(item["published_at"]).startswith("2026-11-01")
    g.close()


def test_pk_conflict_on_subscribe_maps_to_already_subscribed(tmp_path):
    """The loser of a concurrent subscribe gets a conflict, not a raw RuntimeError."""
    g = GraphService(str(tmp_path / "t.kuzu"))
    url = "https://a.example/rss"
    g.create_feed(url=url, title="A", description="", site_url="")

    class FakeResponse:
        content = (
            b'<rss version="2.0"><channel><title>A</title><link>https://a.example</link>'
            b"</channel></rss>"
        )

        def raise_for_status(self):
            pass

    calls = {"n": 0}
    real_exists = g.feed_exists

    def exists_first_false(u):
        calls["n"] += 1
        return False if calls["n"] == 1 else real_exists(u)

    async def fake_get(client, u, **kw):
        return FakeResponse()

    with (
        patch.object(g, "feed_exists", side_effect=exists_first_false),
        patch("reed.api.feeds.safe_get", fake_get),
        pytest.raises(FeedAlreadySubscribedError),
    ):
        asyncio.run(discover_and_create_feed(g, url))
    g.close()
