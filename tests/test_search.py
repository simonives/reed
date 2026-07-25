# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from datetime import UTC, datetime

from reed.graph import GraphService, _rows


def _make_gs(tmp_path):
    return GraphService(str(tmp_path / "test.kuzu"))


def _create_feed(gs, url="https://example.com/feed", feed_id="feed-uuid-1"):
    gs._conn.execute(
        """
        CREATE (:Feed {url: $url, id: $id, title: 'Test Feed', is_active: true,
                       consecutive_errors: 0, poll_interval_minutes: 60,
                       subscribed_at: timestamp('2026-01-01T00:00:00Z')})
        """,
        {"url": url, "id": feed_id},
    )


def _base_item(**overrides):
    defaults = dict(
        feed_url="https://example.com/feed",
        guid="https://example.com/1",
        url="https://example.com/1",
        title="Test Item",
        summary="",
        content="<p>Hello world content.</p>",
        author="Jane",
        word_count=3,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return defaults


class TestIssue59:
    def test_derives_summary_from_content_when_empty(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            gs.create_item(
                **_base_item(
                    summary="",
                    content="<p>AI governance and accountability in enterprise HR systems.</p>",
                )
            )
            items, _ = gs.list_items()
            assert items[0]["summary"] != ""
            assert "AI governance" in items[0]["summary"]
        finally:
            gs.close()

    def test_preserves_existing_summary(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            gs.create_item(
                **_base_item(
                    summary="Explicit summary here.",
                    content="<p>Different content text.</p>",
                )
            )
            items, _ = gs.list_items()
            assert items[0]["summary"] == "Explicit summary here."
        finally:
            gs.close()

    def test_no_summary_no_content_stays_empty(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            gs.create_item(**_base_item(summary="", content=""))
            items, _ = gs.list_items()
            assert items[0]["summary"] == ""
        finally:
            gs.close()


class TestNoteBodySync:
    def test_put_note_sets_note_body_on_item(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            item_id = gs.create_item(**_base_item())
            gs.put_note(item_id, "This is my note about governance.")
            result = _rows(
                gs._conn.execute(
                    "MATCH (i:Item) WHERE i.id = $id RETURN i.note_body AS note_body",
                    {"id": item_id},
                )
            )
            assert result[0]["note_body"] == "This is my note about governance."
        finally:
            gs.close()

    def test_put_note_update_syncs_note_body(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            item_id = gs.create_item(**_base_item())
            gs.put_note(item_id, "First note.")
            gs.put_note(item_id, "Updated note.")
            result = _rows(
                gs._conn.execute(
                    "MATCH (i:Item) WHERE i.id = $id RETURN i.note_body AS note_body",
                    {"id": item_id},
                )
            )
            assert result[0]["note_body"] == "Updated note."
        finally:
            gs.close()

    def test_delete_note_clears_note_body(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            item_id = gs.create_item(**_base_item())
            gs.put_note(item_id, "A note.")
            gs.delete_note(item_id)
            result = _rows(
                gs._conn.execute(
                    "MATCH (i:Item) WHERE i.id = $id RETURN i.note_body AS note_body",
                    {"id": item_id},
                )
            )
            assert result[0]["note_body"] is None
        finally:
            gs.close()


class TestMakeExcerpt:
    def test_wraps_matched_term_in_em(self):
        from reed.graph import _make_excerpt

        result = _make_excerpt("The quick brown fox jumps over the lazy dog", "fox")
        assert result is not None
        assert "<em>" in result
        assert "fox" in result

    def test_returns_none_for_no_match(self):
        from reed.graph import _make_excerpt

        assert _make_excerpt("Hello world", "zzz") is None

    def test_returns_none_for_empty_text(self):
        from reed.graph import _make_excerpt

        assert _make_excerpt("", "foo") is None

    def test_strips_html_tags(self):
        from reed.graph import _make_excerpt

        result = _make_excerpt("<p>AI governance framework</p>", "governance")
        assert result is not None
        assert "<p>" not in result
        assert "<em>governance</em>" in result

    def test_ellipsis_for_context_outside_window(self):
        from reed.graph import _make_excerpt

        long_text = "word " * 30 + "target " + "word " * 30
        result = _make_excerpt(long_text.strip(), "target")
        assert result is not None
        assert "…" in result


class TestMatchSource:
    def test_content_match(self):
        from reed.graph import _match_source

        item = {"title": "AI governance", "summary": "", "content": "", "note_body": None}
        result = _match_source(item, "governance")
        assert "content" in result

    def test_note_only_match(self):
        from reed.graph import _match_source

        item = {
            "title": "Unrelated",
            "summary": "Unrelated",
            "content": "Unrelated",
            "note_body": "governance notes",
        }
        result = _match_source(item, "governance")
        assert "note" in result
        assert "content" not in result

    def test_both_match(self):
        from reed.graph import _match_source

        item = {
            "title": "governance",
            "summary": "",
            "content": "",
            "note_body": "governance notes",
        }
        result = _match_source(item, "governance")
        assert "content" in result
        assert "note" in result

    def test_fallback_when_no_text_match(self):
        from reed.graph import _match_source

        item = {"title": "Unrelated", "summary": "", "content": "", "note_body": None}
        result = _match_source(item, "zzz")
        assert result == ["content"]


class TestSearchItems:
    def _setup(self, tmp_path):
        gs = _make_gs(tmp_path)
        _create_feed(gs)
        gs.create_item(
            **_base_item(
                guid="https://example.com/1",
                title="AI governance in enterprise HR",
                summary="",
                content=(
                    "<p>Accountability frameworks for artificial intelligence in HR systems.</p>"
                ),
                author="Jane Smith",
            )
        )
        gs.create_item(
            **_base_item(
                guid="https://example.com/2",
                title="Supply chain optimisation",
                summary="Logistics and procurement automation.",
                content="<p>Reducing costs through smarter procurement.</p>",
                author="Bob Jones",
            )
        )
        return gs

    def test_returns_matching_items_ranked(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            results, total = gs.search_items("governance")
            assert total >= 1
            assert any(
                "governance" in r["title"].lower()
                or "governance" in (r.get("content") or "").lower()
                for r in results
            )
        finally:
            gs.close()

    def test_no_match_returns_empty(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            results, total = gs.search_items("zzznomatch")
            assert results == []
            assert total == 0
        finally:
            gs.close()

    def test_score_is_float(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            results, _ = gs.search_items("governance")
            assert len(results) > 0
            assert isinstance(results[0]["score"], float)
        finally:
            gs.close()

    def test_excerpt_contains_em_tag(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            results, _ = gs.search_items("governance")
            assert len(results) > 0
            assert results[0]["excerpt"] is not None
            assert "<em>" in results[0]["excerpt"]
        finally:
            gs.close()

    def test_match_source_in_result(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            results, _ = gs.search_items("governance")
            assert len(results) > 0
            assert isinstance(results[0]["match_source"], list)
        finally:
            gs.close()

    def test_note_body_match_surfaces_note_source(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            item_id = gs.create_item(
                **_base_item(
                    title="Unrelated title",
                    summary="Unrelated summary",
                    content="<p>Unrelated content.</p>",
                )
            )
            gs.put_note(item_id, "This item is about accountability governance.")
            results, _ = gs.search_items("accountability")
            assert len(results) >= 1
            note_results = [r for r in results if "note" in r["match_source"]]
            assert len(note_results) >= 1
            assert note_results[0]["note_excerpt"] is not None
        finally:
            gs.close()

    def test_author_filter(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            results, total = gs.search_items("governance", author="Jane Smith")
            assert total >= 1
            assert all(r["author"] == "Jane Smith" for r in results)
        finally:
            gs.close()

    def test_unread_only_filter(self, tmp_path):
        gs = self._setup(tmp_path)
        try:
            items, _ = gs.list_items()
            gs.update_item_state(items[0]["id"], read=True)
            results_all, total_all = gs.search_items("governance")
            results_unread, total_unread = gs.search_items("governance", unread_only=True)
            assert total_unread <= total_all
        finally:
            gs.close()

    def test_feed_id_filter(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs, url="https://feed1.com/feed", feed_id="feed-1")
            _create_feed(gs, url="https://feed2.com/feed", feed_id="feed-2")
            gs.create_item(
                **_base_item(
                    feed_url="https://feed1.com/feed",
                    guid="https://feed1.com/1",
                    title="AI governance report",
                    content="<p>Governance matters.</p>",
                )
            )
            gs.create_item(
                **_base_item(
                    feed_url="https://feed2.com/feed",
                    guid="https://feed2.com/1",
                    title="AI governance analysis",
                    content="<p>Governance here too.</p>",
                )
            )
            results, total = gs.search_items("governance", feed_id="feed-1")
            assert total == 1
            assert results[0]["feed_id"] == "feed-1"
        finally:
            gs.close()

    def test_limit_and_offset(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            for i in range(5):
                gs.create_item(
                    **_base_item(
                        guid=f"https://example.com/{i}",
                        title=f"AI governance item {i}",
                        content="<p>Governance content.</p>",
                    )
                )
            results1, total = gs.search_items("governance", limit=2, offset=0)
            results2, _ = gs.search_items("governance", limit=2, offset=2)
            assert total >= 5
            assert len(results1) == 2
            assert len(results2) == 2
            assert results1[0]["id"] != results2[0]["id"]
        finally:
            gs.close()


class TestSearchDeterministicOrder:
    """#131 — score-tied results must have a stable secondary sort."""

    def test_tied_score_results_are_stable_across_repeated_queries(self, tmp_path):
        gs = _make_gs(tmp_path)
        try:
            _create_feed(gs)
            for i in range(4):
                gs.create_item(
                    **_base_item(
                        guid=f"https://example.com/{i}",
                        url=f"https://example.com/{i}",
                        title="python tutorial guide",
                        summary="python tutorial guide content",
                        content="<p>python tutorial guide content</p>",
                        published_at=datetime(2026, 1, i + 1, tzinfo=UTC),
                        fetched_at=datetime(2026, 1, i + 1, tzinfo=UTC),
                    )
                )
            first, _ = gs.search_items("python", limit=4)
            second, _ = gs.search_items("python", limit=4)
            assert len(first) == 4
            assert [r["guid"] for r in first] == [r["guid"] for r in second]
        finally:
            gs.close()
