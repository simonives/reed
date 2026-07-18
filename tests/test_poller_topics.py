# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reed.graph import GraphService
from reed.poller import FeedPoller


SIMPLE_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
  <title>Tech Feed</title>
  <item>
    <title>Machine learning and neural networks in 2026</title>
    <link>https://tech.example.com/1</link>
    <guid>https://tech.example.com/1</guid>
    <description>Deep learning systems are transforming natural language processing</description>
  </item>
</channel></rss>"""


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    g.create_feed(
        url="https://tech.example.com/feed",
        title="Tech Feed",
        description="",
        site_url="",
    )
    yield g
    g.close()


def test_ingest_entries_returns_triples(graph):
    poller = FeedPoller(graph)
    results = poller._ingest_entries(
        "https://tech.example.com/feed", SIMPLE_RSS, datetime.now(UTC)
    )
    assert len(results) == 1
    item_id, item_url, text = results[0]
    assert isinstance(item_id, str)
    assert isinstance(item_url, str)
    assert isinstance(text, str)


def test_ingest_entries_text_contains_title_and_summary(graph):
    poller = FeedPoller(graph)
    results = poller._ingest_entries(
        "https://tech.example.com/feed", SIMPLE_RSS, datetime.now(UTC)
    )
    _, _, text = results[0]
    assert "Machine learning" in text or "machine learning" in text.lower()


@pytest.mark.asyncio
async def test_backfill_topics_enriches_unenriched_items(graph):
    poller = FeedPoller(graph)
    # Seed item directly (bypassing poller — simulates pre-M4 items)
    item_id = graph.create_item(
        feed_url="https://tech.example.com/feed",
        guid="pre-m4-item",
        url="https://tech.example.com/0",
        title="Natural language processing with transformers",
        summary="BERT and GPT architectures changed everything",
        content="",
        author="",
        word_count=8,
        published_at=None,
        fetched_at=datetime.now(UTC),
    )
    assert item_id in [r["id"] for r in graph.get_unenriched_items()]
    await poller._backfill_topics()
    assert item_id not in [r["id"] for r in graph.get_unenriched_items()]
    topics = graph.get_item_topics(item_id)
    assert len(topics) > 0


@pytest.mark.asyncio
async def test_enrich_new_items_creates_topics(graph):
    poller = FeedPoller(graph)
    item_id = graph.create_item(
        feed_url="https://tech.example.com/feed",
        guid="new-item",
        url="https://tech.example.com/new",
        title="Deep learning in natural language processing",
        summary="",
        content="",
        author="",
        word_count=6,
        published_at=None,
        fetched_at=datetime.now(UTC),
    )
    new_items = [(item_id, "https://tech.example.com/new", "Deep learning in natural language processing")]
    await poller._enrich_new_items(new_items)
    topics = graph.get_item_topics(item_id)
    assert len(topics) > 0
