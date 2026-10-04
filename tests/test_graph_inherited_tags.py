# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest

from reed.graph import GraphService
from tests.conftest import create_test_item

FEED = "https://example.com/feed"


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    g.create_feed(url=FEED, title="F", description="", site_url="", tags=["Tech"])
    yield g
    g.close()


def _item(graph, guid="a", title="Workday release notes"):
    return create_test_item(graph, FEED, guid, f"https://example.com/{guid}", title)


def test_list_items_by_tag_includes_items_inheriting_feed_tag(graph):
    item_id = _item(graph)
    items, total = graph.list_items(tag="Tech")
    assert total == 1
    assert items[0]["id"] == item_id


def test_inherited_and_explicit_tag_does_not_duplicate(graph):
    item_id = _item(graph)
    graph.tag_item(item_id, "Tech")
    items, total = graph.list_items(tag="Tech")
    assert total == 1 and len(items) == 1


def test_untagging_feed_removes_inherited_items(graph):
    feed = graph.list_feeds_for_polling()[0]
    _item(graph)
    graph.set_feed_tags(feed["id"], [])
    _, total = graph.list_items(tag="Tech")
    assert total == 0


def test_explicit_item_tag_survives_feed_untag(graph):
    feed = graph.list_feeds_for_polling()[0]
    item_id = _item(graph)
    graph.tag_item(item_id, "Tech")
    graph.set_feed_tags(feed["id"], [])
    _, total = graph.list_items(tag="Tech")
    assert total == 1


def test_list_tags_counts_inherited_items_once(graph):
    first = _item(graph, "a")
    _item(graph, "b")
    graph.tag_item(first, "Tech")
    counts = {t["name"]: t["item_count"] for t in graph.list_tags()}
    assert counts["Tech"] == 2


def test_search_by_tag_includes_inherited(graph):
    _item(graph, "a", "Workday payroll update")
    items, total = graph.search_items("Workday", tag="Tech")
    assert total == 1


def test_item_tags_field_includes_inherited_tag_names(graph):
    _item(graph)
    items, _ = graph.list_items()
    assert items[0]["tags"] == ["Tech"]
