# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

from reed.graph import GraphService


def _make_item(graph, guid, title, **kw):
    now = datetime.now(UTC)
    return graph.create_item(
        feed_url="https://example.com/feed",
        guid=guid,
        url=f"https://example.com/{guid}",
        title=title,
        summary="",
        content="",
        author=kw.get("author", ""),
        word_count=10,
        published_at=kw.get("published_at", now),
        fetched_at=now,
    )


class TestGraphSimilar:
    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/graph/similar/some-id")
        assert r.status_code == 401

    def test_returns_404_for_unknown_item(self, authed):
        r = authed.get("/api/v1/graph/similar/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_returns_empty_list_for_item_with_no_similar(self, authed, reed_client):
        graph: GraphService = reed_client.app.state.graph
        graph.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
        i1 = _make_item(graph, "i1", "Solo")
        r = authed.get(f"/api/v1/graph/similar/{i1}")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_returns_similar_items_wrapped_with_score(self, authed, reed_client):
        graph: GraphService = reed_client.app.state.graph
        graph.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
        i1 = _make_item(graph, "i1", "One")
        i2 = _make_item(graph, "i2", "Two")
        graph.enrich_item(i1, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(i2, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        r = authed.get(f"/api/v1/graph/similar/{i1}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["item"]["id"] == i2
        assert data[0]["item"]["title"] == "Two"
        assert "score" in data[0]
        assert set(data[0]["shared_topics"]) == {"topic a", "topic b"}


class TestGraphAdjacentToStarred:
    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/graph/adjacent-to-starred")
        assert r.status_code == 401

    def test_empty_when_no_starred_items(self, authed):
        r = authed.get("/api/v1/graph/adjacent-to-starred")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_returns_wrapped_items_with_score(self, authed, reed_client):
        graph: GraphService = reed_client.app.state.graph
        graph.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
        starred = _make_item(graph, "s1", "Starred")
        graph._execute("MATCH (i:Item {id: $id}) SET i.starred = true", {"id": starred})
        candidate = _make_item(graph, "c1", "Candidate")
        graph.enrich_item(starred, [("topic a", 0.05), ("topic b", 0.05)])
        graph.enrich_item(candidate, [("topic a", 0.05), ("topic b", 0.05)])
        graph.recompute_derived_edges(window_days=90, score_threshold=0.1)

        r = authed.get("/api/v1/graph/adjacent-to-starred")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["item"]["id"] == candidate
        assert "score" in data[0]
        assert "shared_topics" not in data[0]


class TestGraphAuthor:
    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/graph/author/Someone")
        assert r.status_code == 401

    def test_empty_for_unknown_author(self, authed):
        r = authed.get("/api/v1/graph/author/Nobody")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_returns_items_and_pagination_meta(self, authed, reed_client):
        graph: GraphService = reed_client.app.state.graph
        graph.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
        _make_item(graph, "i1", "By Jane", author="Jane Author")
        r = authed.get("/api/v1/graph/author/Jane Author")
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["title"] == "By Jane"
        assert "meta" in body
        assert "next_cursor" in body["meta"]

    def test_author_name_with_slash(self, authed, reed_client):
        graph: GraphService = reed_client.app.state.graph
        graph.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
        _make_item(graph, "i1", "AC/DC anthology", author="AC/DC")
        r = authed.get("/api/v1/graph/author/AC%2FDC")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


class TestGraphTopicTimeline:
    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/graph/topic/some-id/timeline")
        assert r.status_code == 401

    def test_returns_404_for_unknown_topic(self, authed):
        r = authed.get("/api/v1/graph/topic/00000000-0000-0000-0000-000000000000/timeline")
        assert r.status_code == 404

    def test_returns_timeline_buckets(self, authed, reed_client):
        graph: GraphService = reed_client.app.state.graph
        graph.create_feed(url="https://example.com/feed", title="Feed", description="", site_url="")
        i1 = _make_item(graph, "i1", "One")
        graph.enrich_item(i1, [("weekly topic", 0.05)])
        topics, _ = graph.get_topics()
        topic_id = next(t["id"] for t in topics if t["name"] == "weekly topic")

        r = authed.get(f"/api/v1/graph/topic/{topic_id}/timeline")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


class TestGraphFeedHealth:
    def test_requires_auth(self, reed_client):
        r = reed_client.get("/api/v1/graph/feed-health")
        assert r.status_code == 401

    def test_empty_buckets_for_healthy_instance(self, authed):
        r = authed.get("/api/v1/graph/feed-health")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data == {"inactive": [], "erroring": []}

    def test_erroring_feed_appears_in_erroring_bucket(self, authed, reed_client):
        from unittest.mock import AsyncMock, patch

        # The real app.state.poller is running in the background against this
        # same graph (via the reed_client/authed fixtures); a freshly created
        # feed has last_fetched_at unset, so the poller's own due-check
        # considers it due and can race a real poll attempt against the feed
        # fields this test asserts on. Suppress _poll_feed for determinism —
        # same isolation pattern as test_reader_and_migration.py.
        with patch("reed.poller.FeedPoller._poll_feed", new_callable=AsyncMock):
            graph: GraphService = reed_client.app.state.graph
            graph.create_feed(
                url="https://example.com/feed", title="Feed", description="", site_url=""
            )
            graph._execute(
                "MATCH (f:Feed {url: $url}) SET f.consecutive_errors = 11",
                {"url": "https://example.com/feed"},
            )
            r = authed.get("/api/v1/graph/feed-health")
        data = r.json()["data"]
        assert len(data["erroring"]) == 1
        assert data["inactive"] == []

    def test_inactive_feed_has_days_since_last_item(self, authed, reed_client):
        from datetime import timedelta
        from unittest.mock import AsyncMock, patch

        # See test_erroring_feed_appears_in_erroring_bucket: suppress the real
        # background poller so it cannot overwrite the last_fetched_at we set
        # below before the assertion runs.
        with patch("reed.poller.FeedPoller._poll_feed", new_callable=AsyncMock):
            graph: GraphService = reed_client.app.state.graph
            graph.create_feed(
                url="https://example.com/feed", title="Feed", description="", site_url=""
            )
            old = datetime.now(UTC) - timedelta(days=70)
            graph._execute(
                "MATCH (f:Feed {url: $url}) SET f.subscribed_at = $old, f.last_fetched_at = $old",
                {"url": "https://example.com/feed", "old": old},
            )
            r = authed.get("/api/v1/graph/feed-health")
        data = r.json()["data"]
        assert len(data["inactive"]) == 1
        assert data["inactive"][0]["days_since_last_item"] >= 69


class TestGraphRecompute:
    def test_requires_auth(self, reed_client):
        r = reed_client.post("/api/v1/graph/recompute")
        assert r.status_code == 401

    def test_returns_202_immediately(self, authed, reed_client):
        from unittest.mock import AsyncMock, patch

        poller = reed_client.app.state.poller
        with patch.object(poller, "recompute_derived_edges", new=AsyncMock()):
            r = authed.post("/api/v1/graph/recompute")
        assert r.status_code == 202

    def test_recompute_task_is_not_orphaned(self, authed, reed_client):
        """#161 — the triggered recompute must be tracked (e.g. via FastAPI's
        BackgroundTasks), not a bare fire-and-forget asyncio.create_task whose
        return value is discarded, leaving no strong reference and letting the
        event loop garbage-collect the task mid-flight. Guards both that the
        untracked-task mechanism isn't used AND that the recompute is actually
        invoked — a broken implementation that dropped the call entirely would
        still pass a create_task-absence check alone."""
        import asyncio
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock, patch

        poller = reed_client.app.state.poller
        # Prevent the poller's own interval-based recompute from firing during
        # this test's window, so only the request-triggered call is observed.
        poller._last_recompute = datetime.now(UTC)
        with (
            patch.object(asyncio, "create_task", wraps=asyncio.create_task) as mock_create_task,
            patch.object(poller, "recompute_derived_edges", new=AsyncMock()) as mock_recompute,
        ):
            r = authed.post("/api/v1/graph/recompute")
        assert r.status_code == 202
        mock_create_task.assert_not_called()
        mock_recompute.assert_called_once()
