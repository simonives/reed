# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import defusedxml
import defusedxml.ElementTree as DefET


@dataclass
class FeedCandidate:
    url: str
    title: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    candidates: list[FeedCandidate]
    unparseable: int


def _clean_tags(tags: list[str]) -> list[str]:
    """Strip whitespace, drop empty strings, deduplicate preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in tags:
        t = raw.strip()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _parse_category(category: str) -> list[str]:
    """Split 'cat1/sub,cat2' into flat tag segments ['cat1', 'sub', 'cat2']."""
    parts: list[str] = []
    for segment in category.split(","):
        for part in segment.split("/"):
            parts.append(part)
    return parts


def parse_opml(data: bytes) -> ParseResult:
    """Parse an OPML document from raw bytes into a ParseResult.

    Raises ValueError for malformed XML, non-OPML roots, or missing <body>.
    Uses defusedxml to block XXE and entity-expansion attacks on untrusted input.
    """
    try:
        root = DefET.fromstring(data)
    except (ET.ParseError, defusedxml.DefusedXmlException) as exc:
        raise ValueError(f"Not a valid OPML file: {exc}") from exc

    if root.tag.lower() != "opml":
        raise ValueError(f"Not a valid OPML file: root element is <{root.tag}>, expected <opml>")

    body = root.find("body")
    if body is None:
        raise ValueError("Not a valid OPML file: missing <body> element")

    candidates: dict[str, FeedCandidate] = {}
    unparseable = 0

    def _collect(node: ET.Element, ancestor_tags: list[str]) -> None:
        nonlocal unparseable
        for child in node:
            if child.tag != "outline":
                continue
            xml_url = child.get("xmlUrl") or child.get("xmlurl") or ""
            if xml_url:
                title = child.get("text") or child.get("title") or xml_url
                cat_tags = _parse_category(child.get("category", ""))
                all_tags = _clean_tags(ancestor_tags + cat_tags)
                if xml_url in candidates:
                    existing = candidates[xml_url]
                    extra = [t for t in all_tags if t not in existing.tags]
                    merged = _clean_tags(existing.tags + extra)
                    candidates[xml_url] = FeedCandidate(
                        url=xml_url, title=existing.title, tags=merged
                    )
                else:
                    candidates[xml_url] = FeedCandidate(url=xml_url, title=title, tags=all_tags)
            else:
                folder_name = child.get("text") or child.get("title") or ""
                sub_outlines = [c for c in child if c.tag == "outline"]
                if sub_outlines:
                    next_ancestors = ancestor_tags + (
                        [folder_name.strip()] if folder_name.strip() else []
                    )
                    _collect(child, next_ancestors)
                else:
                    unparseable += 1

    _collect(body, [])
    return ParseResult(candidates=list(candidates.values()), unparseable=unparseable)


def build_opml(feeds: list[dict[str, Any]]) -> str:
    """Build an OPML 2.0 document from a list of feed dicts (as returned by graph.list_feeds()).

    Feeds with N tags are nested under N tag-named folder outlines.
    Untagged feeds are emitted as top-level outlines.
    Uses stdlib ET (not defusedxml) — output is trusted, not parsed from untrusted input.
    """
    root = ET.Element("opml", version="2.0")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = "Reed subscriptions"
    ET.SubElement(head, "dateCreated").text = datetime.now(UTC).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )
    body = ET.SubElement(root, "body")

    tag_to_feeds: dict[str, list[dict[str, Any]]] = {}
    untagged: list[dict[str, Any]] = []
    for feed in feeds:
        tags = feed.get("tags") or []
        if tags:
            for tag in tags:
                tag_to_feeds.setdefault(tag, []).append(feed)
        else:
            untagged.append(feed)

    def _feed_outline(parent: ET.Element, feed: dict[str, Any]) -> None:
        label = feed.get("display_name") or feed.get("title") or feed["url"]
        ET.SubElement(
            parent,
            "outline",
            type="rss",
            text=label,
            title=label,
            xmlUrl=feed["url"],
            htmlUrl=feed.get("site_url") or "",
        )

    for tag_name in sorted(tag_to_feeds):
        folder = ET.SubElement(body, "outline", text=tag_name, title=tag_name)
        for feed in tag_to_feeds[tag_name]:
            _feed_outline(folder, feed)

    for feed in untagged:
        _feed_outline(body, feed)

    ET.indent(root, space="  ")
    buf = BytesIO()
    ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")
