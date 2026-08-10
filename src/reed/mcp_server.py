# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from typing import Any

from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import get_settings
from .graph import GraphService
from .poller import FeedPoller


class ApiKeyMiddleware:
    """Pure-ASGI middleware guarding the mounted MCP app with X-API-Key.

    Mirrors api/deps.py's require_api_key (same secrets.compare_digest
    check, same settings.api_key source) but implemented at the ASGI level
    because the MCP app is a mounted Starlette sub-app, not a set of
    FastAPI routes that can take a Depends().
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        settings = get_settings()
        if settings.api_key:
            headers = dict(scope["headers"])
            key = headers.get(b"x-api-key", b"").decode()
            if not secrets.compare_digest(key, settings.api_key):
                response = JSONResponse({"error": "Invalid API key"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_mcp_server(graph: GraphService, poller: FeedPoller) -> FastMCP:
    """Build and return the fully-configured Reed FastMCP server: all tools
    (feed, item, graph traversal, discovery, research, export, config),
    the `reed://graph/overview` resource, and the deep_reading_session /
    weekly_digest / research_thread guided-workflow prompts."""
    mcp: FastMCP = FastMCP("Reed")

    from fastmcp.exceptions import ToolError

    from .api.feeds import FeedAlreadySubscribedError, FeedInvalidError, discover_and_create_feed
    from .api.schemas import decode_cursor, encode_cursor
    from .config import effective_config
    from .opml import build_opml

    # POST /graph/recompute (src/reed/api/graph.py) holds its fire-and-forget
    # recompute task via Starlette's BackgroundTasks so it isn't garbage
    # collected mid-flight (#161). MCP tool calls have no request/response
    # cycle to hang a BackgroundTasks instance off, so the equivalent here is
    # the standard asyncio idiom for the same problem: keep a strong
    # reference in a set for the task's lifetime, discarding it on
    # completion via a done-callback.
    _background_tasks: set[asyncio.Task[Any]] = set()

    def _bounded(name: str, value: int, lo: int = 1, hi: int | None = 200) -> None:
        """Validate a limit/offset-style parameter, matching the REST API's
        Query(..., ge=..., le=...) bounds (api/*.py) so the MCP surface
        raises a clean ToolError instead of leaking a raw Kuzu driver
        exception (negative limit/offset) or a bare IndexError (limit=0,
        via encode_cursor(items[-1]) on an empty page). hi=None means no
        upper bound, matching REST routes (e.g. /topics) whose `offset`
        query param is ge=0 with no le=."""
        if value < lo or (hi is not None and value > hi):
            bound_desc = f"{lo} and {hi}" if hi is not None else f">= {lo}"
            raise ToolError(f"{name} must be {bound_desc}, got: {value}")

    @mcp.tool
    def get_config() -> dict[str, Any]:
        """Return Reed's effective global configuration."""
        return effective_config(graph)

    @mcp.tool
    def list_feeds() -> list[dict[str, Any]]:
        """Return all subscribed feeds with metadata and unread counts."""
        return graph.list_feeds()

    @mcp.tool
    def get_feed(feed_id: str) -> dict[str, Any]:
        """Return a single feed with full metadata."""
        feed = graph.get_feed(feed_id)
        if feed is None:
            raise ToolError(f"Feed not found: {feed_id}")
        return feed

    @mcp.tool
    async def subscribe_feed(
        url: str, display_name: str | None = None, tags: list[str] | None = None
    ) -> dict[str, Any]:
        """Subscribe to a new feed by URL."""
        try:
            return await discover_and_create_feed(graph, url, display_name, tags)
        except (FeedAlreadySubscribedError, FeedInvalidError) as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def refresh_feed(feed_id: str) -> dict[str, Any]:
        """Trigger an immediate poll for a feed."""
        feed = await asyncio.to_thread(graph.get_feed, feed_id)
        if feed is None:
            raise ToolError(f"Feed not found: {feed_id}")
        await poller.refresh_feed(feed)
        refreshed = await asyncio.to_thread(graph.get_feed, feed_id)
        assert refreshed is not None
        return refreshed

    @mcp.tool
    def get_items(
        feed_id: str | None = None,
        unread: bool | None = None,
        starred: bool | None = None,
        tag: str | None = None,
        topic: str | None = None,
        since: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Return items matching filters. The primary reading tool. With no
        filters, returns the most recent items across all feeds."""
        from datetime import datetime

        _bounded("limit", limit)
        topic_id = None
        if topic is not None:
            resolved = graph.get_topic_by_name(topic)
            if resolved is None:
                raise ToolError(f"Topic not found: {topic}")
            topic_id = resolved["id"]
        try:
            cursor_ts, cursor_guid = decode_cursor(cursor) if cursor else (None, None)
        except ValueError as exc:
            raise ToolError("Invalid cursor") from exc
        try:
            since_dt = datetime.fromisoformat(since) if since else None
        except ValueError as exc:
            raise ToolError(f"Invalid since: {since!r}") from exc
        items = graph.list_items_cursor(
            feed_id=feed_id,
            tag=tag,
            unread_only=bool(unread),
            starred=starred,
            since=since_dt,
            limit=limit,
            cursor_ts=cursor_ts,
            cursor_guid=cursor_guid,
            topic_id=topic_id,
        )
        next_cursor = encode_cursor(items[-1]) if len(items) == limit else None
        return {"items": items, "next_cursor": next_cursor}

    @mcp.tool
    def get_item(item_id: str) -> dict[str, Any]:
        """Return a single item with full content. Use this to read an article."""
        item = graph.get_item(item_id)
        if item is None:
            raise ToolError(f"Item not found: {item_id}")
        similar = graph.get_similar_items(item_id, limit=5)
        item["similar_items"] = similar or []
        return item

    @mcp.tool
    def mark_read(
        item_ids: list[str] | None = None,
        feed_id: str | None = None,
        before: str | None = None,
    ) -> dict[str, Any]:
        """Mark one or more items as read. item_ids, feed_id, and before are
        all optional and combinable. Omitting all three marks everything as read."""
        from datetime import datetime

        if feed_id is not None and not graph.feed_exists_by_id(feed_id):
            raise ToolError(f"Feed not found: {feed_id}")
        try:
            before_dt = datetime.fromisoformat(before) if before else None
        except ValueError as exc:
            raise ToolError(f"Invalid before: {before!r}") from exc

        marked = 0
        if item_ids:
            marked += graph.mark_read_by_ids(item_ids)
        if item_ids is None or feed_id is not None or before is not None:
            marked += graph.mark_read_bulk(feed_id=feed_id, before=before_dt)
        return {"marked": marked}

    @mcp.tool
    def mark_starred(item_id: str, starred: bool) -> dict[str, Any]:
        """Stars or unstars an item."""
        item = graph.update_item_state(item_id, starred=starred)
        if item is None:
            raise ToolError(f"Item not found: {item_id}")
        return item

    @mcp.tool
    def tag_item(item_id: str, tag: str, action: str) -> dict[str, Any]:
        """Applies or removes a tag on an item. action is 'add' or 'remove'."""
        if action == "add":
            result = graph.tag_item(item_id, tag)
            if result is None:
                raise ToolError(f"Item not found: {item_id}")
            return result
        if action == "remove":
            item = graph.get_item(item_id)
            if item is None:
                raise ToolError(f"Item not found: {item_id}")
            matching = [t for t in graph.list_tags() if t["name"] == tag]
            if matching:
                graph.untag_item(item_id, matching[0]["id"])
            return {"item_id": item_id, "tag": tag, "action": "removed"}
        raise ToolError(f"action must be 'add' or 'remove', got: {action}")

    @mcp.tool
    def annotate_item(item_id: str, content: str | None) -> dict[str, Any]:
        """Creates or replaces the note on an item. content: null deletes the note."""
        if content is None:
            if graph.get_item(item_id) is None:
                raise ToolError(f"Item not found: {item_id}")
            graph.delete_note(item_id)
            return {"item_id": item_id, "note": None}
        note = graph.put_note(item_id, content)
        if note is None:
            raise ToolError(f"Item not found: {item_id}")
        return note

    @mcp.tool
    def find_similar_items(
        item_id: str, limit: int = 10, unread_only: bool = False
    ) -> list[dict[str, Any]]:
        """Returns items similar to a given item, via SIMILAR_TO edges."""
        _bounded("limit", limit)
        results = graph.get_similar_items(item_id, limit=limit)
        if results is None:
            raise ToolError(f"Item not found: {item_id}")
        if unread_only:
            results = [r for r in results if not r["read"]]
        return results

    @mcp.tool
    def find_adjacent_to_starred(limit: int = 20, min_score: float = 0.0) -> list[dict[str, Any]]:
        """Returns unread items similar to the user's starred items."""
        _bounded("limit", limit)
        results = graph.get_adjacent_to_starred(limit=limit)
        return [r for r in results if r["score"] >= min_score]

    @mcp.tool
    def find_path(
        from_id: str, to_id: str, from_type: str = "item", max_topic_hops: int = 3
    ) -> dict[str, Any]:
        """Find how two items (or an item and a topic) connect through the
        graph — the answer to 'how does this relate to that'. Traversal is
        topic-based only, following ABOUT/RELATED_TO edges — it deliberately
        excludes SIMILAR_TO, so an empty path here doesn't mean the two are
        unrelated by similarity, only that they don't share a topic chain."""
        if from_type not in ("item", "topic"):
            raise ToolError(f"from_type must be 'item' or 'topic', got: {from_type}")
        if max_topic_hops < 1:
            raise ToolError(f"max_topic_hops must be >= 1, got: {max_topic_hops}")
        path = graph.find_connection_path(
            from_id, to_id, from_type=from_type, max_topic_hops=max_topic_hops
        )
        return {"path": path or []}

    @mcp.tool
    def explore_topic(topic_name: str, limit: int = 20) -> dict[str, Any]:
        """Returns items about a topic, plus related topics, ordered by weight."""
        _bounded("limit", limit)
        topic = graph.get_topic_by_name(topic_name)
        if topic is None:
            raise ToolError(f"Topic not found: {topic_name}")
        items = graph.get_topic_items(topic["id"], limit=limit)
        related = graph.get_related_topics(topic["id"])
        return {"topic": topic, "items": items, "related_topics": related}

    @mcp.tool
    def get_author_items(author_name: str, limit: int = 20) -> list[dict[str, Any]]:
        """Returns all items by an author across all subscribed feeds."""
        _bounded("limit", limit)
        return graph.get_author_items(author_name, limit=limit)

    @mcp.tool
    def get_topic_timeline(topic_name: str, bucket: str = "week") -> list[dict[str, Any]]:
        """Returns item volume for a topic over time, bucketed by week or month."""
        topic = graph.get_topic_by_name(topic_name)
        if topic is None:
            raise ToolError(f"Topic not found: {topic_name}")
        try:
            timeline = graph.get_topic_timeline(topic["id"], bucket=bucket)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        assert timeline is not None
        return timeline

    @mcp.tool
    def get_feed_health() -> dict[str, Any]:
        """Returns feeds that are inactive or returning errors."""
        unhealthy = graph.get_feed_health()
        inactive = [f for f in unhealthy if f.get("consecutive_errors", 0) <= 10]
        erroring = [f for f in unhealthy if f.get("consecutive_errors", 0) > 10]
        return {"inactive": inactive, "erroring": erroring}

    @mcp.tool
    def search(query: str, unread: bool | None = None, limit: int = 20) -> dict[str, Any]:
        """Full-text search across items and notes."""
        _bounded("limit", limit)
        items, total = graph.search_items(q=query, unread_only=bool(unread), limit=limit)
        return {"items": items, "total": total}

    @mcp.tool
    def export_opml() -> dict[str, str]:
        """Returns the user's feed list as an OPML string."""
        return {"opml": build_opml(graph.list_feeds())}

    @mcp.tool
    async def trigger_recompute() -> dict[str, str]:
        """Triggers derived edge recomputation asynchronously. The returned
        job_id is not currently associated with any queryable task status —
        there is no tool to poll it against, so treat this as fire-and-forget
        rather than attempting to check on completion."""
        job_id = str(uuid.uuid4())
        task = asyncio.create_task(poller.recompute_derived_edges())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"job_id": job_id, "status": "queued"}

    @mcp.tool
    def list_topics(
        limit: int = 50, offset: int = 0, sort: str = "item_count"
    ) -> list[dict[str, Any]]:
        """List all topics. sort: 'item_count' (default, most-covered first)
        or 'centrality' (PageRank over the topic co-occurrence graph).

        Known limitation (reed#206): centrality is biased by an arbitrary
        edge-direction artifact and can understate low-degree topics'
        real connectivity. Treat it as suggestive, not authoritative."""
        _bounded("limit", limit)
        _bounded("offset", offset, lo=0, hi=None)
        try:
            topics, _total = graph.get_topics(limit=limit, offset=offset, sort=sort)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return topics

    @mcp.tool
    def get_topic_clusters(limit: int = 50) -> list[dict[str, Any]]:
        """Group topics into clusters via Louvain community detection on the
        topic co-occurrence graph — free topic clustering the flat keyword
        extraction otherwise lacks. The client names the clusters semantically."""
        _bounded("limit", limit)
        return graph.get_topic_clusters(limit=limit)

    @mcp.tool
    def list_tags() -> list[dict[str, Any]]:
        """List all tags with item counts."""
        return graph.list_tags()

    @mcp.tool
    def list_authors(limit: int = 50) -> list[dict[str, Any]]:
        """List authors by item count, most-published first."""
        _bounded("limit", limit)
        return graph.list_authors(limit=limit)

    @mcp.tool
    def capture_external_finding(
        item_id: str, url: str, title: str, summary: str, tags: list[str] | None = None
    ) -> dict[str, Any]:
        """Append an external research finding to an item's note — the answer
        to 'go look this up outside Reed', without Reed doing the searching
        itself. Findings become searchable via the search tool afterwards."""
        block = f"External finding: {title}\n{url}\n{summary}"
        note = graph.append_note(item_id, block)
        if note is None:
            raise ToolError(f"Item not found: {item_id}")
        for tag in tags or []:
            graph.tag_item(item_id, tag)
        return note

    @mcp.tool
    def build_research_brief(item_id: str) -> dict[str, Any]:
        """Package an item's full graph context into one call, to prime the
        client's own web research rather than duplicating it in Reed."""
        item = graph.get_item(item_id)
        if item is None:
            raise ToolError(f"Item not found: {item_id}")
        topics = graph.get_item_topics(item_id)
        similar = graph.get_similar_items(item_id, limit=5) or []
        same_author = (
            [i for i in graph.get_author_items(item["author"], limit=5) if i["id"] != item_id]
            if item.get("author")
            else []
        )
        return {
            "item": item,
            "topics": topics,
            "similar_items": similar,
            "same_author_items": same_author,
        }

    @mcp.resource("reed://graph/overview")
    def graph_overview() -> str:
        """One-shot orientation snapshot: counts, top topics, top authors, date range."""
        feeds = graph.list_feeds()
        topics, topic_total = graph.get_topics(limit=20)
        authors = graph.list_authors(limit=20)
        return json.dumps(
            {
                "feed_count": len(feeds),
                "item_count": sum(f.get("item_count", 0) for f in feeds),
                "unread_count": sum(f.get("unread_count", 0) for f in feeds),
                "topic_count": topic_total,
                "top_topics": topics,
                "top_authors": authors,
            },
            default=str,
        )

    @mcp.prompt
    def deep_reading_session() -> str:
        """A guided reading session: unread items, read one, find related, mark read."""
        return (
            "Conduct a deep reading session in Reed:\n"
            "1. get_items(unread=true, limit=20) — see what's waiting to be read\n"
            "2. get_item(item_id) — read an article\n"
            "3. find_similar_items(item_id) — see what else in the library is related\n"
            "4. explore_topic(topic_name) — go deeper on a topic the article raised\n"
            "5. mark_read(item_ids) — tidy up when done"
        )

    @mcp.prompt
    def weekly_digest() -> str:
        """A weekly digest: what's new, what themes are covered, what matches past interests."""
        return (
            "Produce a weekly digest from Reed:\n"
            "1. get_items(unread=true, since=<7 days ago>) — everything new this week\n"
            "2. explore_topic for the most-covered topics — surface themes\n"
            "3. find_adjacent_to_starred — what's new that matches past interests\n"
            "4. Return a structured summary to the user"
        )

    @mcp.prompt
    def research_thread() -> str:
        """A research thread: search a topic, expand via similarity, map
        related topics, annotate."""
        return (
            "Follow a research thread in Reed:\n"
            "1. search(query: topic of interest) — find the seed items\n"
            "2. find_similar_items on the most relevant — expand the thread\n"
            "3. explore_topic on the topics that emerge — map the territory\n"
            "4. annotate_item — capture insights as they surface\n"
            "5. Return a summary with annotated items linked"
        )

    return mcp
