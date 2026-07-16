# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import xml.etree.ElementTree as _ET

import pytest

from reed.opml import build_opml, parse_opml


class TestParseOpml:
    def test_flat_feed_no_folder(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline type="rss" text="Example" xmlUrl="https://example.com/feed.rss"/>
  </body>
</opml>"""
        result = parse_opml(data)
        assert result.unparseable == 0
        assert len(result.candidates) == 1
        assert result.candidates[0].url == "https://example.com/feed.rss"
        assert result.candidates[0].title == "Example"
        assert result.candidates[0].tags == []

    def test_folder_becomes_tag(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline text="Tech">
      <outline type="rss" text="HN" xmlUrl="https://news.ycombinator.com/rss"/>
    </outline>
  </body>
</opml>"""
        result = parse_opml(data)
        assert result.candidates[0].tags == ["Tech"]

    def test_nested_folders_all_become_tags(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline text="Tech">
      <outline text="AI">
        <outline type="rss" text="AI Blog" xmlUrl="https://ai.example.com/feed"/>
      </outline>
    </outline>
  </body>
</opml>"""
        result = parse_opml(data)
        assert set(result.candidates[0].tags) == {"Tech", "AI"}

    def test_category_attribute_parsed_as_tags(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline type="rss" text="Feed" xmlUrl="https://x.com/feed"
             category="/News/Tech,Sports"/>
  </body>
</opml>"""
        result = parse_opml(data)
        tags = set(result.candidates[0].tags)
        assert tags == {"News", "Tech", "Sports"}

    def test_folder_and_category_deduplicated(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline text="Tech">
      <outline type="rss" text="Feed" xmlUrl="https://x.com/feed"
               category="Tech,News"/>
    </outline>
  </body>
</opml>"""
        result = parse_opml(data)
        tags = result.candidates[0].tags
        assert tags.count("Tech") == 1
        assert "News" in tags

    def test_duplicate_outlines_deduped_tags_unioned(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline text="Tech">
      <outline type="rss" text="Feed" xmlUrl="https://x.com/feed"/>
    </outline>
    <outline text="News">
      <outline type="rss" text="Feed" xmlUrl="https://x.com/feed"/>
    </outline>
  </body>
</opml>"""
        result = parse_opml(data)
        assert len(result.candidates) == 1
        assert set(result.candidates[0].tags) == {"Tech", "News"}

    def test_leaf_outline_without_xmlurl_counted_unparseable(self):
        data = b"""<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline text="Not a feed"/>
    <outline type="rss" text="Feed" xmlUrl="https://x.com/feed"/>
  </body>
</opml>"""
        result = parse_opml(data)
        assert result.unparseable == 1
        assert len(result.candidates) == 1

    def test_empty_body_returns_empty_candidates(self):
        data = b"""<?xml version="1.0"?><opml version="2.0"><body></body></opml>"""
        result = parse_opml(data)
        assert result.candidates == []
        assert result.unparseable == 0

    def test_unicode_title_preserved(self):
        data = (
            b"<?xml version='1.0' encoding='utf-8'?><opml version='2.0'><body>"
            b"<outline type='rss' text='Angstrom &amp; Cafe' xmlUrl='https://x.com/feed'/>"
            b"</body></opml>"
        )
        result = parse_opml(data)
        assert result.candidates[0].title == "Angstrom & Cafe"

    def test_malformed_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="Not a valid OPML file"):
            parse_opml(b"this is not xml")

    def test_non_opml_root_raises_value_error(self):
        with pytest.raises(ValueError, match="Not a valid OPML file"):
            parse_opml(b"<rss version='2.0'><channel/></rss>")

    def test_missing_body_raises_value_error(self):
        with pytest.raises(ValueError, match="Not a valid OPML file"):
            parse_opml(b"<opml version='2.0'></opml>")


class TestBuildOpml:
    def test_tagged_feed_nested_under_folder(self):
        feeds = [
            {
                "url": "https://a.com/feed",
                "title": "A",
                "display_name": None,
                "site_url": "https://a.com",
                "tags": ["tech"],
            },
        ]
        xml_str = build_opml(feeds)
        root = _ET.fromstring(xml_str.encode("utf-8"))
        body = root.find("body")
        folder = body.find("outline")
        assert folder is not None and folder.get("text") == "tech"
        feed_el = folder.find("outline")
        assert feed_el is not None
        assert feed_el.get("xmlUrl") == "https://a.com/feed"
        assert feed_el.get("type") == "rss"

    def test_multi_tag_feed_appears_under_each_folder(self):
        feeds = [
            {
                "url": "https://a.com/feed",
                "title": "A",
                "display_name": None,
                "site_url": "",
                "tags": ["news", "tech"],
            },
        ]
        xml_str = build_opml(feeds)
        root = _ET.fromstring(xml_str.encode("utf-8"))
        folders = root.find("body").findall("outline")
        assert len(folders) == 2
        for folder in folders:
            assert folder.find("outline").get("xmlUrl") == "https://a.com/feed"

    def test_untagged_feed_at_top_level(self):
        feeds = [
            {
                "url": "https://b.com/feed",
                "title": "B",
                "display_name": None,
                "site_url": "",
                "tags": [],
            },
        ]
        xml_str = build_opml(feeds)
        root = _ET.fromstring(xml_str.encode("utf-8"))
        outlines = root.find("body").findall("outline")
        assert len(outlines) == 1
        assert outlines[0].get("xmlUrl") == "https://b.com/feed"

    def test_empty_feeds_returns_valid_opml(self):
        xml_str = build_opml([])
        root = _ET.fromstring(xml_str.encode("utf-8"))
        assert root.tag == "opml"
        assert len(root.find("body").findall("outline")) == 0

    def test_display_name_used_over_title(self):
        feeds = [
            {
                "url": "https://a.com/feed",
                "title": "A Title",
                "display_name": "My A Feed",
                "site_url": "",
                "tags": [],
            },
        ]
        xml_str = build_opml(feeds)
        root = _ET.fromstring(xml_str.encode("utf-8"))
        assert root.find("body/outline").get("text") == "My A Feed"

    def test_special_chars_correctly_escaped(self):
        feeds = [
            {
                "url": "https://a.com/feed?a=1&b=2",
                "title": "A & B",
                "display_name": None,
                "site_url": "",
                "tags": [],
            },
        ]
        xml_str = build_opml(feeds)
        root = _ET.fromstring(xml_str.encode("utf-8"))
        outline = root.find("body/outline")
        assert outline.get("text") == "A & B"
        assert outline.get("xmlUrl") == "https://a.com/feed?a=1&b=2"

    def test_xml_declaration_present(self):
        assert build_opml([]).startswith("<?xml")

    def test_head_title_is_reed_subscriptions(self):
        xml_str = build_opml([])
        root = _ET.fromstring(xml_str.encode("utf-8"))
        title = root.find("head/title")
        assert title is not None and title.text == "Reed subscriptions"


class TestRoundTrip:
    def test_round_trip_preserves_urls_and_tag_sets(self):
        feeds = [
            {
                "url": "https://a.com/feed",
                "title": "A",
                "display_name": None,
                "site_url": "https://a.com",
                "tags": ["tech", "news"],
            },
            {
                "url": "https://b.com/feed",
                "title": "B",
                "display_name": None,
                "site_url": "",
                "tags": [],
            },
        ]
        xml_str = build_opml(feeds)
        result = parse_opml(xml_str.encode("utf-8"))
        by_url = {c.url: c for c in result.candidates}
        assert set(by_url["https://a.com/feed"].tags) == {"tech", "news"}
        assert by_url["https://b.com/feed"].tags == []


class TestSecurityParsing:
    def test_xxe_entity_expansion_blocked(self):
        xxe = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<opml version="2.0"><body>
  <outline type="rss" text="&xxe;" xmlUrl="https://x.com/feed"/>
</body></opml>"""
        with pytest.raises(ValueError, match="Not a valid OPML file"):
            parse_opml(xxe)

    def test_billion_laughs_blocked(self):
        bl = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<opml version="2.0"><body>
  <outline type="rss" text="&lol2;" xmlUrl="https://x.com/feed"/>
</body></opml>"""
        with pytest.raises(ValueError, match="Not a valid OPML file"):
            parse_opml(bl)
