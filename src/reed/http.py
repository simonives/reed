# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Iterable
from typing import Any

import httpcore
import httpx
from httpx._utils import get_environment_proxies

logger = logging.getLogger(__name__)

USER_AGENT = "Reed RSS Reader/0.1 (+https://github.com/simonives/reed)"

_MAX_REDIRECTS = 10


class UnsafeURLError(Exception):
    """Raised when a URL resolves to a disallowed scheme or address range."""


def http_client() -> httpx.AsyncClient:
    """Shared outbound HTTP client policy: timeout, redirects, user agent.

    Direct connections use a transport that pins each connection to a
    pre-validated public IP (see _PinnedResolverBackend), so every direct
    request is SSRF-safe at the connection layer, redirects included. Callers
    still go through safe_get for the fail-fast pre-check and scheme check.

    HTTP_PROXY/HTTPS_PROXY/NO_PROXY are honoured: a request routed through a
    proxy is the proxy's egress decision, so the proxy connection is not pinned
    (proxies commonly live on private addresses). NO_PROXY hosts fall back to
    the pinned direct transport.
    """
    return httpx.AsyncClient(
        timeout=30,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
        transport=_PinnedTransport(),
        mounts=_env_proxy_mounts(),
    )


def _env_proxy_mounts() -> dict[str, httpx.AsyncBaseTransport | None]:
    """Rebuild httpx's env-proxy mounts.

    httpx builds these from HTTP_PROXY/HTTPS_PROXY/NO_PROXY itself, but only when
    no explicit transport is passed; passing the pinned transport disables that,
    so we reconstruct them (reusing httpx's own env parser for NO_PROXY / *
    handling). A None value routes to the default (pinned) transport, so
    NO_PROXY hosts stay pinned; a proxy pattern gets an unpinned proxy transport.
    """
    mounts: dict[str, httpx.AsyncBaseTransport | None] = {}
    for pattern, url in get_environment_proxies().items():
        mounts[pattern] = None if url is None else httpx.AsyncHTTPTransport(proxy=url)
    return mounts


def _is_public_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def _resolve_safe_ips(host: str) -> list[str]:
    """Resolve host and return every validated public IP to try connecting to.

    Every resolved address must be public; a split-horizon or rebinding record
    that returns even one private/reserved answer is refused wholesale.
    Returning the addresses lets the caller connect to those exact IPs with no
    second resolution — that is what closes the resolve-then-connect race — and
    trying each in turn preserves dual-stack fallback (an unreachable AAAA on an
    IPv4-only network no longer strands the feed). Runs on the loop's async
    resolver so a slow DNS server cannot block it.
    """
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Cannot resolve host: {host}") from exc
    addrs = [str(info[4][0]) for info in infos]
    if not addrs:
        raise UnsafeURLError(f"Host did not resolve: {host}")
    for addr in addrs:
        if not _is_public_ip(addr):
            raise UnsafeURLError(f"Host resolves to a private or reserved address: {host}")
    # De-duplicate, preserving getaddrinfo's (RFC 6724) ordering.
    return list(dict.fromkeys(addrs))


async def _require_safe_url(url: httpx.URL) -> None:
    """Fail-fast pre-check for safe_get. The connection-level guarantee against
    DNS rebinding is _PinnedResolverBackend; this avoids a connection attempt
    (and surfaces _resolve_safe_ips's specific message) for an obviously-internal
    or unresolvable host.
    """
    if url.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Disallowed scheme: {url.scheme!r}")
    if not url.host:
        raise UnsafeURLError("URL has no host")
    await _resolve_safe_ips(url.host)


class _PinnedResolverBackend(httpcore.AnyIOBackend):
    """Resolve the host to validated public IPs and connect to one of those
    exact addresses, instead of letting the OS re-resolve the hostname at
    connect time.

    This closes the resolve-then-connect DNS-rebinding window: safe_get's
    pre-check and the real connection would otherwise perform independent
    resolutions, and an attacker controlling a low-TTL record could return a
    public answer to the check and an internal one to the connection. httpcore
    still passes the original hostname to start_tls, so TLS SNI, certificate
    verification, and response.url all keep using the hostname.
    """

    async def connect_tcp(  # type: ignore[override]
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        # Resolution must respect the connect timeout: a resolver that accepts
        # queries but never answers must not hang the poll loop past `timeout`.
        try:
            async with asyncio.timeout(timeout):
                ips = await _resolve_safe_ips(host)
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout(f"DNS resolution timed out for {host}") from exc

        # Try each validated address until one connects. Every candidate has
        # been validated, so the pin holds; this restores the multi-address
        # fallback the hostname path had (dual-stack on IPv4-only networks).
        # ConnectTimeout is a *sibling* of ConnectError (both subclass nothing
        # in common but Exception), so it must be caught explicitly — a dropped
        # SYN to a dead AAAA is the very case the fallback exists for.
        last_exc: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for ip in ips:
            try:
                return await super().connect_tcp(
                    ip,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_exc = exc
        # _resolve_safe_ips never returns an empty list (it raises instead), so
        # the loop ran and last_exc is set; guard explicitly rather than assert
        # (which -O would strip).
        if last_exc is None:  # pragma: no cover - unreachable
            raise httpcore.ConnectError(f"No address to connect to for {host}")
        raise last_exc


class _PinnedTransport(httpx.AsyncHTTPTransport):
    """httpx's async transport with a connection pool that pins DNS resolution
    to a validated IP (see _PinnedResolverBackend).

    httpx exposes no public hook to inject a network backend, so the pool is
    built here — mirroring httpx's own default limits — rather than letting the
    base __init__ build a pool we would discard.

    The guarantee that this keeps pinning across httpx versions is the pyproject
    version cap, not this construction. The only drift this construction catches
    by itself is a rename of the `_pool` attribute (handle_async_request would
    then raise AttributeError rather than silently serve unpinned connections);
    a semantic change to how httpx drives the pool would still need the cap.
    """

    def __init__(self) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(),
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=5.0,
            http1=True,
            http2=False,
            retries=0,
            network_backend=_PinnedResolverBackend(),
        )


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
