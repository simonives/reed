# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import kuzu
import pytest

from reed.graph import GraphService
from reed.http import UnsafeURLError, safe_get


def _first_item_id(authed):
    return authed.get("/api/v1/items").json()["data"][0]["id"]


class TestExtractEndpoint:
    def test_extract_stores_reader_content(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        with patch(
            "reed.api.items.extract_article",
            AsyncMock(return_value="<p>Clean article body</p>"),
        ):
            r = authed.post(f"/api/v1/items/{item_id}/extract")

        assert r.status_code == 200
        assert r.json()["data"]["reader_content"] == "<p>Clean article body</p>"

        # Persisted, not just returned
        detail = authed.get(f"/api/v1/items/{item_id}").json()["data"]
        assert detail["reader_content"] == "<p>Clean article body</p>"

    def test_extraction_failure_returns_422(self, authed, subscribed_feed):
        item_id = _first_item_id(authed)
        with patch("reed.api.items.extract_article", AsyncMock(return_value=None)):
            r = authed.post(f"/api/v1/items/{item_id}/extract")
        assert r.status_code == 422

    def test_unknown_item_returns_404(self, authed):
        r = authed.post("/api/v1/items/no-such-id/extract")
        assert r.status_code == 404


class TestSSRFGuard:
    async def test_rejects_loopback(self):
        with pytest.raises(UnsafeURLError):
            await safe_get(AsyncMock(), "http://127.0.0.1/admin")

    async def test_rejects_link_local_metadata(self):
        with pytest.raises(UnsafeURLError):
            await safe_get(AsyncMock(), "http://169.254.169.254/latest/meta-data/")

    async def test_rejects_private_range(self):
        with pytest.raises(UnsafeURLError):
            await safe_get(AsyncMock(), "http://192.168.1.1/")

    async def test_rejects_non_http_scheme(self):
        with pytest.raises(UnsafeURLError):
            await safe_get(AsyncMock(), "file:///etc/passwd")

    async def test_rejects_private_redirect_hop(self):
        """A public URL that 302s to a private address must be blocked."""
        import httpx

        redirect = httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/"},
            request=httpx.Request("GET", "https://example.com/"),
        )
        client = AsyncMock()
        client.get = AsyncMock(return_value=redirect)
        resolve_public = AsyncMock(side_effect=lambda host: host == "example.com")
        with (
            patch("reed.http._resolve_is_safe", resolve_public),
            pytest.raises(UnsafeURLError),
        ):
            await safe_get(client, "https://example.com/")

    async def test_allows_public_host(self):
        import httpx

        ok = httpx.Response(200, request=httpx.Request("GET", "https://example.com/"))
        client = AsyncMock()
        client.get = AsyncMock(return_value=ok)
        with patch("reed.http._resolve_is_safe", AsyncMock(return_value=True)):
            response = await safe_get(client, "https://example.com/")
        assert response.status_code == 200

    async def test_extract_article_blocks_ssrf(self):
        """extract_article returns None (not an error) for a blocked URL."""
        from reed.reader import extract_article

        result = await extract_article("http://169.254.169.254/", http=AsyncMock())
        assert result is None


class TestRefreshEndpoint:
    def test_refresh_polls_feed(self, authed, subscribed_feed):
        with patch("reed.poller.FeedPoller._poll_feed", AsyncMock()) as mock_poll:
            r = authed.post(f"/api/v1/feeds/{subscribed_feed['id']}/refresh")
        assert r.status_code == 202
        mock_poll.assert_awaited_once()

    def test_refresh_unknown_feed_returns_404(self, authed):
        r = authed.post("/api/v1/feeds/no-such-id/refresh")
        assert r.status_code == 404


class TestPollerReaderExtraction:
    async def test_extracts_new_items_when_enabled(self, tmp_path):
        graph = GraphService(str(tmp_path / "poller.kuzu"))
        try:
            from reed.poller import FeedPoller

            graph.create_feed(
                url="https://example.com/feed.rss",
                title="Feed",
                description="",
                site_url="",
            )
            item_id = graph.create_item(
                feed_url="https://example.com/feed.rss",
                guid="g1",
                url="https://example.com/article",
                title="T",
                summary="",
                content="",
                author="",
                word_count=0,
                published_at=None,
                fetched_at=datetime.now(UTC),
            )
            poller = FeedPoller(graph)
            with patch(
                "reed.poller.extract_article", AsyncMock(return_value="extracted")
            ) as mock_extract:
                await poller._extract_new_items(
                    [(item_id, "https://example.com/article")], http=AsyncMock()
                )

            mock_extract.assert_awaited_once()
            assert graph.get_item(item_id)["reader_content"] == "extracted"
        finally:
            graph.close()


class TestM1Migration:
    """A database created with the M1 schema must open cleanly under M2."""

    M1_FEED_DDL = """
        CREATE NODE TABLE Feed(
            url STRING, title STRING, description STRING, site_url STRING,
            poll_interval_minutes INT64, last_fetched_at TIMESTAMP,
            error_state STRING, etag STRING, last_modified STRING,
            PRIMARY KEY (url)
        )
    """
    M1_ITEM_DDL = """
        CREATE NODE TABLE Item(
            guid STRING, url STRING, title STRING, summary STRING, content STRING,
            published_at TIMESTAMP, fetched_at TIMESTAMP, read BOOLEAN, starred BOOLEAN,
            PRIMARY KEY (guid)
        )
    """

    def test_m1_database_migrates(self, tmp_path):
        db_path = str(tmp_path / "m1.kuzu")
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        conn.execute(self.M1_FEED_DDL)
        conn.execute(self.M1_ITEM_DDL)
        conn.execute("CREATE REL TABLE HAS_ITEM(FROM Feed TO Item)")
        conn.execute(
            """CREATE (:Feed {url: 'https://old.example/feed', title: 'Old Feed',
               description: '', site_url: '', poll_interval_minutes: 60})"""
        )
        conn.execute(
            """CREATE (:Item {guid: 'old-guid', url: 'https://old.example/1',
               title: 'Old Item', summary: '', content: '', read: false, starred: false,
               fetched_at: timestamp('2026-01-01 00:00:00')})"""
        )
        conn.execute(
            """MATCH (f:Feed {url: 'https://old.example/feed'}), (i:Item {guid: 'old-guid'})
               CREATE (f)-[:HAS_ITEM]->(i)"""
        )
        conn.close()
        db.close()

        graph = GraphService(db_path)
        try:
            feeds = graph.list_feeds()
            assert len(feeds) == 1
            feed = feeds[0]
            assert feed["id"]  # backfilled
            assert feed["is_active"] is True
            assert feed["consecutive_errors"] == 0
            assert feed["subscribed_at"] is not None

            items, total = graph.list_items()
            assert total == 1
            assert items[0]["id"]  # backfilled
        finally:
            graph.close()
