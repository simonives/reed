# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import functools
import ipaddress
import logging
import socket
import ssl
from collections.abc import Iterable
from typing import Any

import httpcore
import httpx
from httpx._utils import get_environment_proxies

logger = logging.getLogger(__name__)

USER_AGENT = "Reed RSS Reader/0.1 (+https://github.com/simonives/reed)"

_MAX_REDIRECTS = 10

# Single source of truth for the http/https scheme allowlist. graph.py's
# _safe_url() imports this rather than keeping an independent copy, so the
# outbound-fetch SSRF guard and the stored/exported URL sanitiser can never
# drift apart (#136).
SAFE_URL_SCHEMES = frozenset({"http", "https"})


class UnsafeURLError(Exception):
    """Raised when a URL resolves to a disallowed scheme or address range."""


class ResponseRejectedError(UnsafeURLError):
    """Raised when a response is too large or of a type the caller refuses.

    Subclasses UnsafeURLError so every existing call site that already turns an
    unsafe fetch into a clean 422 or a logged skip handles it too.
    """


# Default ceiling for a response body from an untrusted URL. Callers pass a
# tighter or looser value from Settings.
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


@functools.lru_cache(maxsize=1)
def _shared_ssl_context() -> ssl.SSLContext:
    """One SSL context for every client. Building one re-parses the CA bundle
    into native memory, so doing it per request and per OPML entry adds up."""
    return httpx.create_ssl_context()


def safe_url(url: str) -> str:
    """Return url only if its scheme is http or https, otherwise empty string.

    Used by graph.py to sanitise stored/exported URLs before they leave the
    graph (rendering, backup export). Parses with httpx.URL — the same parser
    _require_safe_url uses for the SSRF guard — so the two paths agree on
    scheme-extraction edge cases (e.g. a scheme with no `//`).
    """
    try:
        scheme = httpx.URL(url).scheme
    except (httpx.InvalidURL, TypeError):
        return ""
    return url if scheme in SAFE_URL_SCHEMES else ""


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


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _is_public_ip(addr: str) -> bool:
    """True only for globally routable addresses.

    IPv6 forms that embed an IPv4 address (mapped, 6to4, Teredo, NAT64) are
    judged by the embedded address, so they cannot smuggle a private target.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.ipv4_mapped or ip.sixtofour
        if ip.teredo:
            embedded = ip.teredo[1]
        if ip in _NAT64:
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None:
            return _is_public_ip(str(embedded))
    return ip.is_global and not ip.is_multicast


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
    if url.scheme not in SAFE_URL_SCHEMES:
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
            ssl_context=_shared_ssl_context(),
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
    max_bytes: int | None = DEFAULT_MAX_BYTES,
    allowed_content_types: tuple[str, ...] | None = None,
) -> httpx.Response:
    """GET a URL from an untrusted source, blocking SSRF to internal hosts.

    Redirects are followed manually so each hop's resolved address is
    validated before the request is made. The client must not follow
    redirects itself; this passes follow_redirects=False per request.

    The body is streamed and abandoned with ResponseRejectedError once it
    exceeds max_bytes (None disables the cap), or immediately when the
    Content-Type is not in allowed_content_types (prefix match, None allows
    any). The returned Response holds the full, decoded body.
    """
    current = httpx.URL(url)
    for _ in range(_MAX_REDIRECTS):
        await _require_safe_url(current)
        async with client.stream(
            "GET", current, headers=headers, follow_redirects=False
        ) as response:
            location = response.headers.get("Location")
            if response.is_redirect and location:
                # Resolve relative redirects against the current URL, then re-validate
                current = current.join(location)
                continue
            return await _read_capped(response, max_bytes, allowed_content_types)
    raise UnsafeURLError("Too many redirects")


async def _read_capped(
    response: httpx.Response,
    max_bytes: int | None,
    allowed_content_types: tuple[str, ...] | None,
) -> httpx.Response:
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if (
        allowed_content_types is not None
        and response.is_success
        and not content_type.startswith(tuple(t.lower() for t in allowed_content_types))
    ):
        raise ResponseRejectedError(f"Unsupported content type: {content_type or 'unknown'}")
    declared = response.headers.get("Content-Length", "")
    if max_bytes is not None and declared.isdigit() and int(declared) > max_bytes:
        raise ResponseRejectedError(f"Response too large ({declared} bytes, limit {max_bytes})")
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if max_bytes is not None and len(body) > max_bytes:
            raise ResponseRejectedError(f"Response exceeded {max_bytes} bytes")
    # aiter_bytes yields decoded bytes, so drop the encoding and length headers
    # that no longer describe the body we hand back.
    kept = [
        (k, v)
        for k, v in response.headers.multi_items()
        if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
    ]
    return httpx.Response(
        response.status_code,
        headers=kept,
        content=bytes(body),
        request=response.request,
    )


async def safe_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    json: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> httpx.Response:
    """POST to a URL from an untrusted destination, blocking SSRF to internal hosts.

    Unlike safe_get, this makes exactly one request and does not follow
    redirects: automatically re-POSTing a credential-bearing request across a
    redirect hop risks leaking Authorization/signing headers to an unintended
    origin, and 301/302/303 redirects require a method downgrade to GET that a
    blind retry would violate. Neither Raindrop's API nor a well-behaved
    webhook receiver has a legitimate reason to redirect a share POST, so the
    caller is expected to treat a 3xx response the same as any other
    non-success status.
    """
    target = httpx.URL(url)
    await _require_safe_url(target)
    return await client.post(
        target, json=json, headers=headers, follow_redirects=False, timeout=timeout
    )
