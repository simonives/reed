"""Response size caps, content-type gate, shared SSL context and payload trimming
(#341, #345, #346)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastmcp import Client

from reed.graph import GraphService
from reed.http import ResponseRejectedError, UnsafeURLError, _shared_ssl_context, safe_get

from .conftest import create_test_item, fake_stream


def _resp(content, headers=None):
    return httpx.Response(
        200, content=content, headers=headers, request=httpx.Request("GET", "https://e.example/")
    )


async def _chunks(n_chunks, size):
    for _ in range(n_chunks):
        yield b"x" * size


async def _get(response, **kw):
    client = AsyncMock()
    client.stream = fake_stream(response)
    with patch("reed.http._resolve_safe_ips", AsyncMock(return_value=["93.184.216.34"])):
        return await safe_get(client, "https://e.example/", **kw)


class TestSafeGetLimits:
    async def test_small_body_is_returned_whole(self):
        r = await _get(_resp(b"hello"), max_bytes=100)
        assert r.content == b"hello"
        assert r.status_code == 200

    async def test_declared_oversize_is_rejected_before_reading(self):
        with pytest.raises(ResponseRejectedError):
            await _get(_resp(b"x" * 2000), max_bytes=1000)

    async def test_undeclared_oversize_is_cut_off_while_streaming(self):
        # An async generator body has no Content-Length, so the cap must bite mid-stream.
        with pytest.raises(ResponseRejectedError):
            await _get(_resp(_chunks(10, 500)), max_bytes=1000)

    async def test_cap_can_be_disabled(self):
        r = await _get(_resp(b"x" * 5000), max_bytes=None)
        assert len(r.content) == 5000

    async def test_disallowed_content_type_is_rejected(self):
        with pytest.raises(ResponseRejectedError, match="content type"):
            await _get(
                _resp(b"%PDF", {"Content-Type": "application/pdf"}),
                allowed_content_types=("text/html",),
            )

    async def test_allowed_content_type_passes_with_charset(self):
        r = await _get(
            _resp(b"<p>x</p>", {"Content-Type": "text/html; charset=utf-8"}),
            allowed_content_types=("text/html",),
        )
        assert r.text == "<p>x</p>"

    async def test_rejection_is_an_unsafe_url_error(self):
        # Existing call sites catch UnsafeURLError; the new error must be covered.
        assert issubclass(ResponseRejectedError, UnsafeURLError)


def test_ssl_context_is_shared():
    assert _shared_ssl_context() is _shared_ssl_context()


class TestSummaryCap:
    def test_long_summary_becomes_body_plus_snippet(self, tmp_path):
        g = GraphService(str(tmp_path / "t.kuzu"))
        g.create_feed(url="https://f.example/rss", title="F", description="", site_url="")
        long_html = "<p>" + ("word " * 800) + "</p>"
        g.create_item(
            feed_url="https://f.example/rss",
            guid="g1",
            url="https://f.example/1",
            title="T",
            summary=long_html,
            content="",
            author="",
            word_count=800,
            published_at=None,
            fetched_at=datetime.now(UTC),
        )
        items, _ = g.list_items(limit=5)
        assert len(items[0]["summary"]) <= 305
        full = g.get_item(items[0]["id"])
        assert "word word word" in full["content"]
        g.close()


class TestMcpSearchPayload:
    async def test_search_omits_full_text_fields(self, mcp_server):
        server, graph, poller = mcp_server
        graph.create_feed(url="https://f.example.com/rss", title="F", description="", site_url="")
        create_test_item(
            graph,
            feed_url="https://f.example.com/rss",
            guid="g1",
            url="https://f.example.com/1",
            title="Quokka habitat",
            content="quokka " * 200,
        )
        async with Client(server) as client:
            result = await client.call_tool("search", {"query": "quokka"})
        items = result.data["items"]
        assert items
        for item in items:
            assert "content" not in item
            assert "note_body" not in item
