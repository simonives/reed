# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from ..graph import GraphService
from ..http import UnsafeURLError, http_client, safe_post
from ..text import snippet
from .deps import get_graph, require_api_key
from .schemas import envelope

router = APIRouter(
    prefix="/api/v1/share",
    tags=["share"],
    dependencies=[Depends(require_api_key)],
)


class WebhookConfig(BaseModel):
    url: HttpUrl
    # Optional per adversarial review (judgement call 2, option B): when set,
    # Task 6's _deliver_webhook computes an HMAC-SHA256 signature of the
    # outgoing payload with this as the key and sends it as X-Reed-Signature,
    # so a receiver — especially one exposed on the public internet, e.g. a
    # personal n8n/Make instance — can verify the request actually came from
    # this Reed instance. Omitting it preserves today's unsigned behaviour.
    secret: str | None = None


class RaindropConfig(BaseModel):
    token: str
    # Raindrop's REST v1 $id field is numeric (#172) — typing this as int lets
    # Pydantic coerce a numeric string (e.g. from a form input) at
    # target-creation time and reject a non-numeric value with a clear 422,
    # rather than failing later, opaquely, against Raindrop's own API.
    collection_id: int


class ShareTargetCreate(BaseModel):
    type: Literal["copy_link", "copy_markdown", "webhook", "raindrop"]
    name: str
    config: dict[str, Any] = {}


class ShareTargetUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


def _validate_config(type_: str, config: dict[str, Any]) -> dict[str, Any]:
    """Validate config and return the Pydantic-coerced dict to persist.

    #174 — callers must persist this return value, not the raw request dict:
    RaindropConfig coerces a numeric string collection_id to int (#172), and
    that coercion is lost if the caller re-persists the original dict.
    """
    if type_ == "webhook":
        try:
            # mode="json" so HttpUrl serialises back to a plain string —
            # graph.create_share_target persists this dict as JSON, and a
            # raw HttpUrl object isn't JSON-serialisable.
            return WebhookConfig(**config).model_dump(mode="json", exclude_none=True)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid webhook config: {exc}",
            ) from exc
    elif type_ == "raindrop":
        try:
            return RaindropConfig(**config).model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid raindrop config: {exc}",
            ) from exc
    elif config:  # copy_link, copy_markdown
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{type_} targets do not accept a config",
        )
    return config


_UNCREATABLE_TYPES = ("copy_link", "copy_markdown")
_SENSITIVE_CONFIG_KEYS = ("secret", "token")


def _redact_target(target: dict[str, Any]) -> dict[str, Any]:
    # GET /targets is polled repeatedly (Settings tab loads, popover loads)
    # and the frontend never reads a target's secret/token — there is no
    # client-side benefit to serving them, so scrub them from list responses
    # rather than leaving webhook signing secrets and Raindrop tokens sitting
    # in devtools/network history/proxy logs for no reason.
    redacted = dict(target)
    redacted["config"] = {
        k: v for k, v in target["config"].items() if k not in _SENSITIVE_CONFIG_KEYS
    }
    return redacted


@router.get("/targets")
def list_share_targets(graph: GraphService = Depends(get_graph)) -> dict[str, Any]:
    return envelope([_redact_target(t) for t in graph.list_share_targets()])


@router.post("/targets", status_code=status.HTTP_201_CREATED)
def create_share_target(
    body: ShareTargetCreate, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    if body.type in _UNCREATABLE_TYPES:
        # copy_link/copy_markdown are seeded once at install and aren't
        # user-creatable (spec: "there's only ever one useful 'copy link'
        # and one useful 'copy as markdown'"). Enforcing this at creation
        # closes a bypass of the delete-protection guard below: without it,
        # a client could create a new copy-type target that then becomes
        # permanently undeletable, since that guard keys off type alone.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{body.type} targets cannot be created; only the seeded pair exists",
        )
    config = _validate_config(body.type, body.config)
    return envelope(graph.create_share_target(body.type, body.name, config))


@router.patch("/targets/{target_id}")
def update_share_target(
    target_id: str, body: ShareTargetUpdate, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    if "config" in fields:
        existing = graph.get_share_target(target_id)
        if existing is not None:
            fields["config"] = _validate_config(existing["type"], fields["config"])
    updated = graph.update_share_target(target_id, **fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share target not found")
    return envelope(updated)


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_share_target(target_id: str, graph: GraphService = Depends(get_graph)) -> None:
    existing = graph.get_share_target(target_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share target not found")
    if existing["type"] in ("copy_link", "copy_markdown"):
        # Adversarial review finding: the frontend only lets a user create
        # webhook/raindrop targets (copy_link/copy_markdown aren't
        # user-creatable beyond the seeded pair — see the spec's Frontend
        # section), so deleting one of the two seeded copy targets via this
        # generic endpoint would be permanent with no recreate path in the
        # UI. Reject it outright rather than let a default silently vanish.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{existing['type']} targets cannot be deleted",
        )
    graph.delete_share_target(target_id)


class ShareRequest(BaseModel):
    item_id: str
    target_id: str


class _DeliveryError(Exception):
    """Internal only — carries the HTTP status share_item should return."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _build_excerpt(item: dict[str, Any]) -> str:
    return snippet(item.get("content") or item.get("summary") or "")


def _sign_payload(secret: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _classify_response(response: httpx.Response) -> None:
    if response.is_redirect:
        raise _DeliveryError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Delivery target returned a redirect ({response.status_code}), "
            "which Reed does not follow",
        )
    if response.is_success:
        return
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        # A delivery target can return valid-but-non-object JSON on an
        # error status (e.g. a bare list or string) — response.json()
        # succeeds, so the except ValueError above never fires.
        body = {}
    message = body.get("errorMessage") or f"Delivery target returned HTTP {response.status_code}"
    if 400 <= response.status_code < 500:
        raise _DeliveryError(status.HTTP_422_UNPROCESSABLE_ENTITY, message)
    raise _DeliveryError(status.HTTP_502_BAD_GATEWAY, message)


async def _deliver_webhook(
    target: dict[str, Any], item: dict[str, Any], topics: list[dict[str, Any]]
) -> None:
    excerpt = _build_excerpt(item)
    published_at = item.get("published_at")
    payload = {
        "event": "share",
        "item": {
            "title": item.get("title"),
            "url": item.get("url"),
            "excerpt": excerpt,
            "author": item.get("author"),
            "published_at": published_at.isoformat() if published_at else None,
            # Deviation from brief (approved): the brief's example used
            # feed_id (the feed's opaque UUID primary key) as the feed
            # "url", which is wrong. graph.get_item now also returns
            # feed_url (added alongside feed_id/feed_title), so use that.
            "feed": (
                {"title": item.get("feed_title"), "url": item.get("feed_url")}
                if item.get("feed_id")
                else None
            ),
            "tags": item.get("tags", []),
            "topics": topics,
        },
        "shared_at": datetime.now(UTC).isoformat(),
    }
    config = target["config"]
    headers: dict[str, str] = {}
    secret = config.get("secret")
    if secret:
        headers["X-Reed-Signature"] = _sign_payload(secret, payload)
    async with http_client() as client:
        response = await safe_post(client, config["url"], json=payload, headers=headers or None)
    _classify_response(response)


async def _deliver_raindrop(target: dict[str, Any], item: dict[str, Any]) -> None:
    excerpt = _build_excerpt(item)
    config = target["config"]
    # #172 — collection_id is coerced to int by RaindropConfig at validation
    # time (create/PATCH), but targets persisted before that fix (or seeded
    # directly at the graph layer) can still have a string stored — and, since
    # RaindropConfig.collection_id was str-typed before #172, that string can
    # be genuinely non-numeric. Coerce defensively here so every existing
    # target delivers correctly without a manual delete-and-recreate, but
    # don't let a malformed legacy value escape as an uncaught 500 (code
    # review, PR #183) — surface it as the same clean 422 an invalid new
    # target would get at creation time.
    try:
        collection_id = int(config["collection_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _DeliveryError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Share target has an invalid collection_id; edit the target to set "
            "a numeric Raindrop collection ID",
        ) from exc
    async with http_client() as client:
        response = await safe_post(
            client,
            "https://api.raindrop.io/rest/v1/raindrop",
            json={
                "link": item.get("url"),
                "title": item.get("title"),
                "excerpt": excerpt,
                "collection": {"$id": collection_id},
            },
            headers={"Authorization": f"Bearer {config['token']}"},
        )
    _classify_response(response)


@router.post("")
async def share_item(
    body: ShareRequest, graph: GraphService = Depends(get_graph)
) -> dict[str, Any]:
    # Security review on PR #183 — recompute_derived_edges (#168) now holds
    # _conn_lock across its full body, so a synchronous graph.* call made
    # directly here (this is the one genuinely async def endpoint in
    # share.py — the CRUD routes are plain def and already run in FastAPI's
    # threadpool) would block the whole ASGI event loop behind an in-flight
    # recompute, not just this request.
    target = await asyncio.to_thread(graph.get_share_target, body.target_id)
    if target is None or not target["enabled"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share target not found")
    if target["type"] not in ("webhook", "raindrop"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Target type is not deliverable via the API",
        )
    item = await asyncio.to_thread(graph.get_item, body.item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    try:
        if target["type"] == "webhook":
            topics = await asyncio.to_thread(graph.get_item_topics, item["id"])
            await _deliver_webhook(target, item, topics)
        else:
            await _deliver_raindrop(target, item)
    except _DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except UnsafeURLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return envelope({"shared": True})
