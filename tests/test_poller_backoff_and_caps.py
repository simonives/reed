"""Per-feed error backoff (#342) and ingest input caps (#351)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from reed.poller import FeedPoller, _backoff_minutes
from reed.topics import MAX_KEYWORD_INPUT_CHARS, extract_keywords


@pytest.mark.parametrize(
    ("errors", "expected"),
    [(0, 60), (2, 60), (3, 120), (5, 120), (6, 240), (10, 240), (11, 1440), (50, 1440)],
)
def test_backoff_table(errors, expected):
    assert _backoff_minutes(60, errors) == expected


def test_backoff_never_shortens_a_long_interval():
    assert _backoff_minutes(2000, 11) == 2000


def _feed(errors: int, minutes_ago: int) -> dict:
    return {
        "url": "https://f.example/rss",
        "last_fetched_at": datetime.now(UTC) - timedelta(minutes=minutes_ago),
        "consecutive_errors": errors,
    }


def test_failing_feed_is_not_due_until_backoff_elapses():
    poller = FeedPoller(MagicMock())
    now = datetime.now(UTC)
    from reed.config import CONFIG_DEFAULTS

    config = {**CONFIG_DEFAULTS, "default_poll_interval_minutes": 60}
    assert poller._is_due(_feed(0, 61), now, config)
    assert not poller._is_due(_feed(4, 61), now, config)  # needs 120
    assert poller._is_due(_feed(4, 121), now, config)
    assert not poller._is_due(_feed(12, 600), now, config)  # needs a day
    assert poller._is_due(_feed(12, 1441), now, config)


def test_keyword_input_is_capped():
    seen: list[str] = []

    class Spy:
        def extract_keywords(self, text):
            seen.append(text)
            return []

    extract_keywords("word " * 100_000, Spy())
    assert len(seen[0]) == MAX_KEYWORD_INPUT_CHARS


def test_existing_entries_skip_word_count(tmp_path, monkeypatch):
    from reed import poller as poller_mod
    from reed.graph import GraphService

    rss = (
        b'<rss version="2.0"><channel><title>t</title>'
        b"<item><title>a</title><guid>g1</guid><link>https://f.example/1</link>"
        b"<description>hello world</description></item></channel></rss>"
    )
    g = GraphService(str(tmp_path / "t.kuzu"))
    g.create_feed(url="https://f.example/rss", title="t", description="", site_url="")
    p = FeedPoller(g)
    assert len(p._ingest_entries("https://f.example/rss", rss, datetime.now(UTC))) == 1

    calls = {"n": 0}
    real = poller_mod.word_count
    monkeypatch.setattr(
        poller_mod, "word_count", lambda t: calls.__setitem__("n", calls["n"] + 1) or real(t)
    )
    assert p._ingest_entries("https://f.example/rss", rss, datetime.now(UTC)) == []
    assert calls["n"] == 0
    g.close()
