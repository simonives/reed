# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "Reed RSS Reader/0.1 (+https://github.com/simonives/reed)"

_MAX_REDIRECTS = 10


class UnsafeURLError(Exception):
    """Raised when a URL resolves to a disallowed scheme or address range."""


def http_client() -> httpx.AsyncClient:
    """Shared outbound HTTP client policy: timeout, redirects, user agent.

    This client must only be used together with safe_get, which performs the
    SSRF checks and follows redirects manually. Every outbound fetch in Reed
    (feeds, discovery, reader extraction) targets a URL that is ultimately
    third-party controlled — directly (feed authors' article links) or via a
    redirect from a user-supplied URL — so all of them go through safe_get.
    """
    return httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


async def _resolve_is_safe(host: str) -> bool:
    """Return True only if every address the host resolves to is public.

    Rejecting on any private/loopback/link-local/reserved result prevents a
    DNS-rebinding-style bypass where one A record is public and another is
    internal. Resolution runs through the loop's async resolver so a slow DNS
    server cannot block the event loop.
    """
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


async def _require_safe_url(url: httpx.URL) -> None:
    if url.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Disallowed scheme: {url.scheme!r}")
    if not url.host:
        raise UnsafeURLError("URL has no host")
    if not await _resolve_is_safe(url.host):
        raise UnsafeURLError(f"Host resolves to a private or reserved address: {url.host}")


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """GET a URL from an untrusted source, blocking SSRF to internal hosts.

    Redirects are followed manually so each hop's resolved address is
    validated before the request is made. The client must not follow
    redirects itself; this passes follow_redirects=False per request.
    """
    current = httpx.URL(url)
    for _ in range(_MAX_REDIRECTS):
        await _require_safe_url(current)
        response = await client.get(current, headers=headers, follow_redirects=False)
        location = response.headers.get("Location")
        if not response.is_redirect or not location:
            return response
        # Resolve relative redirects against the current URL, then re-validate
        current = current.join(location)
    raise UnsafeURLError("Too many redirects")
