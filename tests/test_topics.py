# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from reed.topics import extract_keywords, item_text, make_extractor


def test_extract_keywords_returns_list_of_pairs():
    extractor = make_extractor()
    results = extract_keywords(
        "Machine learning and neural networks are transforming artificial intelligence research",
        extractor,
    )
    assert isinstance(results, list)
    assert len(results) > 0
    for kw, score in results:
        assert isinstance(kw, str)
        assert isinstance(score, float)


def test_extract_keywords_are_lowercase():
    extractor = make_extractor()
    results = extract_keywords("Apple Inc. released new iPhone Pro features", extractor)
    for kw, _ in results:
        assert kw == kw.lower(), f"keyword not lowercase: {kw!r}"


def test_extract_keywords_empty_string_returns_empty():
    extractor = make_extractor()
    assert extract_keywords("", extractor) == []


def test_extract_keywords_whitespace_only_returns_empty():
    extractor = make_extractor()
    assert extract_keywords("   \t\n  ", extractor) == []


def test_item_text_strips_html():
    result = item_text("<b>Big Title</b>", "<p>Summary paragraph</p>", "<div>Content body</div>")
    assert "<" not in result
    assert "Big Title" in result
    assert "Summary paragraph" in result
    assert "Content body" in result


def test_item_text_handles_all_empty():
    result = item_text("", "", "")
    assert result == ""


def test_item_text_handles_partial_fields():
    result = item_text("Title only", "", "")
    assert result.strip() == "Title only"


def test_item_text_concatenates_all_three_fields():
    result = item_text("Alpha", "Beta", "Gamma")
    assert "Alpha" in result
    assert "Beta" in result
    assert "Gamma" in result
