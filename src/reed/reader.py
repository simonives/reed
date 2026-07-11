# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import asyncio
import logging

import httpx
import trafilatura

from .http import UnsafeURLError, http_client, safe_get

logger = logging.getLogger(__name__)


async def extract_article(url: str, http: httpx.AsyncClient | None = None) -> str | None:
    """Fetch an article URL and extract the main content as HTML.

    The URL comes from feed entry links (feed-author controlled), so the fetch
    goes through safe_get, which blocks SSRF to private address ranges and
    re-validates each redirect hop. Returns None when the page cannot be
    fetched or trafilatura finds no usable content (e.g. JavaScript-rendered
    pages — see ADR-010).
    """
    try:
        if http is not None:
            response = await safe_get(http, url)
        else:
            async with http_client() as client:
                response = await safe_get(client, url)
        response.raise_for_status()
    except (httpx.HTTPError, UnsafeURLError) as exc:
        logger.warning("Reader fetch failed for %s: %s", url, exc)
        return None

    # trafilatura is CPU-bound and synchronous; keep it off the event loop
    extracted: str | None = await asyncio.to_thread(
        trafilatura.extract,
        response.text,
        url=url,
        output_format="html",
        include_links=True,
        include_images=True,
    )
    if not extracted:
        logger.info("Reader extraction produced no content for %s", url)
        return None
    return extracted
