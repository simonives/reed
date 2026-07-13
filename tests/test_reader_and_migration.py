# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import kuzu
import pytest

from reed.graph import _SCHEMA_VERSION, GraphService
from reed.http import (
    UnsafeURLError,
    _PinnedResolverBackend,
    _PinnedTransport,
    _require_safe_url,
    _resolve_safe_ips,
    http_client,
    safe_get,
)


def _first_item_id(authed):
    return authed.get("/api/v1/items").json()["data"][0]["id"]


def test_http_client_does_not_follow_redirects():
    """The raw client must not auto-follow; safe_get drives redirects manually
    so each hop is SSRF-revalidated (#45)."""
    from reed.http import http_client

    client = http_client()
    try:
        assert client.follow_redirects is False
    finally:
        # httpx.AsyncClient created outside an async context; close its transport.
        import anyio

        anyio.run(client.aclose)


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

        async def resolve(host):
            if host == "example.com":
                return ["93.184.216.34"]
            raise UnsafeURLError(f"Host resolves to a private or reserved address: {host}")

        with (
            patch("reed.http._resolve_safe_ips", resolve),
            pytest.raises(UnsafeURLError),
        ):
            await safe_get(client, "https://example.com/")

    async def test_allows_public_host(self):
        import httpx

        ok = httpx.Response(200, request=httpx.Request("GET", "https://example.com/"))
        client = AsyncMock()
        client.get = AsyncMock(return_value=ok)
        with patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])):
            response = await safe_get(client, "https://example.com/")
        assert response.status_code == 200

    async def test_require_safe_url_propagates_specific_message(self):
        with (
            patch(
                "reed.http._resolve_safe_ips",
                AsyncMock(side_effect=UnsafeURLError("Host did not resolve: x.example")),
            ),
            pytest.raises(UnsafeURLError, match="Host did not resolve"),
        ):
            await _require_safe_url(httpx.URL("https://x.example/"))

    async def test_extract_article_blocks_ssrf(self):
        """extract_article returns None (not an error) for a blocked URL."""
        from reed.reader import extract_article

        result = await extract_article("http://169.254.169.254/", http=AsyncMock())
        assert result is None


class TestPinnedResolver:
    """The connection-level DNS-rebinding guard (#29) and its follow-ups."""

    async def test_resolve_safe_ips_returns_public_literal(self):
        assert await _resolve_safe_ips("8.8.8.8") == ["8.8.8.8"]

    async def test_resolve_safe_ips_rejects_loopback(self):
        with pytest.raises(UnsafeURLError):
            await _resolve_safe_ips("127.0.0.1")

    async def test_resolve_safe_ips_rejects_private(self):
        with pytest.raises(UnsafeURLError):
            await _resolve_safe_ips("10.0.0.1")

    async def test_resolve_safe_ips_rejects_if_any_address_private(self):
        # Split-horizon: one public + one private answer is refused wholesale.
        infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0)),
        ]

        async def fake_getaddrinfo(*args, **kwargs):
            return infos

        loop = asyncio.get_running_loop()
        with (
            patch.object(loop, "getaddrinfo", fake_getaddrinfo),
            pytest.raises(UnsafeURLError),
        ):
            await _resolve_safe_ips("rebind.example")

    async def test_pinned_client_blocks_private_at_connect(self):
        """The pooled client refuses a private host at the connection layer,
        even without going through safe_get's pre-check."""
        async with http_client() as client:
            with pytest.raises(UnsafeURLError):
                await client.get("http://127.0.0.1:9/")

    async def test_connect_tcp_tries_each_validated_address(self):
        """#47: fall back across validated addresses. The first raises a connect
        *timeout* (the dead-AAAA-on-IPv4-only symptom) and the second a connect
        *error* — both are siblings that must be skipped, not just ConnectError.
        """
        import httpcore

        backend = _PinnedResolverBackend()
        candidates = ["93.184.216.34", "93.184.216.35", "93.184.216.36"]
        attempts: list[str] = []
        sentinel = object()

        async def fake_super_connect(self, host, port, **kwargs):
            attempts.append(host)
            if host == candidates[0]:
                raise httpcore.ConnectTimeout("timed out")
            if host == candidates[1]:
                raise httpcore.ConnectError("Network is unreachable")
            return sentinel

        with (
            patch("reed.http._resolve_safe_ips", AsyncMock(return_value=candidates)),
            patch("httpcore.AnyIOBackend.connect_tcp", fake_super_connect),
        ):
            result = await backend.connect_tcp("example.com", 443, timeout=5)

        assert result is sentinel
        assert attempts == candidates

    async def test_resolve_safe_ips_rejects_ipv6_loopback(self):
        with pytest.raises(UnsafeURLError):
            await _resolve_safe_ips("::1")

    async def test_pinned_transport_connects_to_validated_ip(self):
        """End-to-end through http_client()'s transport -> pool -> backend: the
        connection targets the exact IP _resolve_safe_ips returned, not a
        re-resolved hostname. This is the core anti-rebinding guarantee, and it
        exercises the real transport wiring (not the backend in isolation)."""
        import httpcore

        connected: list[str] = []

        async def fake_connect(self, host, port, **kwargs):
            connected.append(host)
            raise httpcore.ConnectError("stop before opening a real socket")

        with (
            patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])),
            patch("httpcore.AnyIOBackend.connect_tcp", fake_connect),
        ):
            async with http_client() as client:
                with pytest.raises(httpx.ConnectError):
                    await client.get("https://feed.example/")

        assert connected == ["93.184.216.34"]

    async def test_connect_tcp_times_out_slow_resolver(self):
        """#48: a resolver that never answers is bounded by the connect timeout."""
        import httpcore

        async def never_answers(host):
            await asyncio.sleep(10)
            return ["93.184.216.34"]

        backend = _PinnedResolverBackend()
        with (
            patch("reed.http._resolve_safe_ips", never_answers),
            pytest.raises(httpcore.ConnectTimeout),
        ):
            await backend.connect_tcp("slow.example", 443, timeout=0.05)

    async def test_env_proxy_honoured_direct_stays_pinned(self, monkeypatch):
        """#49: HTTP_PROXY routes through an unpinned proxy transport; NO_PROXY
        hosts fall back to the pinned direct transport."""
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.internal:3128")
        monkeypatch.setenv("NO_PROXY", "direct.example")
        async with http_client() as client:
            assert isinstance(client._transport, _PinnedTransport)
            direct = client._transport_for_url(httpx.URL("http://direct.example/"))
            proxied = client._transport_for_url(httpx.URL("http://feed.example/"))
            assert isinstance(direct, _PinnedTransport)  # NO_PROXY -> pinned
            assert proxied is not client._transport  # goes via the proxy mount
            assert not isinstance(proxied, _PinnedTransport)


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
            assert graph.get_config_values()["schema_version"] == _SCHEMA_VERSION
        finally:
            graph.close()


class TestV2ToV3Migration:
    """A v2 database (Note keyed by item_id) migrates to a HAS_NOTE edge."""

    def _build_v2_db(self, db_path):
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        conn.execute(
            "CREATE NODE TABLE Feed(url STRING, id STRING, title STRING, PRIMARY KEY(url))"
        )
        conn.execute(
            "CREATE NODE TABLE Item(guid STRING, id STRING, title STRING, "
            "read BOOLEAN, starred BOOLEAN, PRIMARY KEY(guid))"
        )
        conn.execute(
            "CREATE NODE TABLE Note(item_id STRING, body STRING, "
            "created_at TIMESTAMP, updated_at TIMESTAMP, PRIMARY KEY(item_id))"
        )
        conn.execute("CREATE NODE TABLE Config(key STRING, value STRING, PRIMARY KEY(key))")
        conn.execute(
            "CREATE (:Item {guid: 'g1', id: 'item-1', title: 'T', read: false, starred: false})"
        )
        conn.execute(
            "CREATE (:Note {item_id: 'item-1', body: 'kept note', "
            "created_at: timestamp('2026-02-01 00:00:00'), "
            "updated_at: timestamp('2026-02-02 00:00:00')})"
        )
        conn.execute('MERGE (c:Config {key: "schema_version"}) ON CREATE SET c.value = "2"')
        conn.close()
        db.close()

    def test_v2_note_becomes_edge(self, tmp_path):
        db_path = str(tmp_path / "v2.kuzu")
        self._build_v2_db(db_path)

        graph = GraphService(db_path)
        try:
            assert graph.get_config_values()["schema_version"] == 3
            # Note table restructured: no item_id column, legacy table gone
            assert "item_id" not in graph._column_names("Note")
            assert "_NoteLegacy" not in graph._table_names()
            # The note survived, reachable through the edge by item id
            note = graph.get_note("item-1")
            assert note is not None
            assert note["body"] == "kept note"
        finally:
            graph.close()

    def test_orphaned_legacy_note_is_warned_and_discarded(self, tmp_path, caplog):
        db_path = str(tmp_path / "v2_orphan.kuzu")
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        conn.execute(
            "CREATE NODE TABLE Feed(url STRING, id STRING, title STRING, PRIMARY KEY(url))"
        )
        conn.execute(
            "CREATE NODE TABLE Item(guid STRING, id STRING, title STRING, "
            "read BOOLEAN, starred BOOLEAN, PRIMARY KEY(guid))"
        )
        conn.execute(
            "CREATE NODE TABLE Note(item_id STRING, body STRING, "
            "created_at TIMESTAMP, updated_at TIMESTAMP, PRIMARY KEY(item_id))"
        )
        conn.execute("CREATE NODE TABLE Config(key STRING, value STRING, PRIMARY KEY(key))")
        # Item with id 'item-real'; orphan note references a non-existent 'item-gone'
        conn.execute(
            "CREATE (:Item {guid: 'g1', id: 'item-real', title: 'T', read: false, starred: false})"
        )
        conn.execute(
            "CREATE (:Note {item_id: 'item-gone', body: 'orphan note', "
            "created_at: timestamp('2026-02-01 00:00:00'), "
            "updated_at: timestamp('2026-02-02 00:00:00')})"
        )
        conn.execute('MERGE (c:Config {key: "schema_version"}) ON CREATE SET c.value = "2"')
        conn.close()
        db.close()

        with caplog.at_level(logging.WARNING):
            graph = GraphService(db_path)
        try:
            assert graph.get_config_values()["schema_version"] == 3
            assert "_NoteLegacy" not in graph._table_names()
            # Orphan note was not attached to any item
            assert graph.get_note("item-real") is None
            assert graph.get_note("item-gone") is None
        finally:
            graph.close()

        assert "orphaned legacy note" in caplog.text


class TestFreshSchema:
    """A brand-new database is stamped at the current version and runs no migration."""

    def test_fresh_database_stamps_current_version(self, tmp_path):
        graph = GraphService(str(tmp_path / "fresh.kuzu"))
        try:
            assert graph.get_config_values()["schema_version"] == _SCHEMA_VERSION
        finally:
            graph.close()

    def test_fresh_database_runs_no_migration_step(self, tmp_path):
        with patch.object(GraphService, "_migrate_to_v2") as spy:
            graph = GraphService(str(tmp_path / "fresh2.kuzu"))
            graph.close()
        spy.assert_not_called()

    def test_reopen_is_idempotent(self, tmp_path):
        db_path = str(tmp_path / "reopen.kuzu")
        GraphService(db_path).close()
        with patch.object(GraphService, "_migrate_to_v2") as spy:
            graph = GraphService(db_path)
            try:
                assert graph.get_config_values()["schema_version"] == _SCHEMA_VERSION
            finally:
                graph.close()
        spy.assert_not_called()


class TestColumnNamesAllowlist:
    def test_known_table_returns_columns(self, tmp_path):
        from reed.graph import GraphService

        g = GraphService(str(tmp_path / "g.kuzu"))
        cols = g._column_names("Item")
        assert "guid" in cols

    def test_unknown_table_raises(self, tmp_path):
        from reed.graph import GraphService

        g = GraphService(str(tmp_path / "g.kuzu"))
        with pytest.raises(ValueError, match="Unknown table"):
            g._column_names("Item') RETURN 1 --")
