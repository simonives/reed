# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import calendar
import re

import yake

from .text import strip_html

_TIME_ZONES = ["am", "pm", "cst", "cdt", "est", "edt", "pst", "pdt", "mst", "utc", "gmt", "bst"]
_TIME_ZONES += ["cet", "aest", "aedt", "acst", "awst"]
_CALENDAR_NAMES = [
    *calendar.month_name[1:],
    *calendar.month_abbr[1:],
    *calendar.day_name,
    *calendar.day_abbr,
    "Sept",
]
_NOISE_TOKENS = frozenset(_TIME_ZONES + [n.lower() for n in _CALENDAR_NAMES])
_NOISE_PHRASES = frozenset(
    {
        "read more",
        "click here",
        "learn more",
        "sign up",
        "subscribe now",
        "share this",
        "hosted on acast",
        "acast",
        "appeared first on",
    }
)
# Single words too generic to cluster on; multi-word phrases containing them stay valid.
_GENERIC_WORDS = frozenset(
    [
        "work",
        "new",
        "time",
        "people",
        "year",
        "years",
        "day",
        "way",
        "use",
        "make",
        "need",
        "help",
        "like",
        "just",
        "entry",
        "entries",
    ]
)
_CONTRACTION_FRAGMENT = re.compile(r"^['\u2019]|^n['\u2019]t$")
_NUMERIC_TOKEN = re.compile(r"^[\d\W_]+$")  # digits and punctuation only, e.g. 331-363, 1:00
_MIN_LETTERS = 2


def is_valid_topic(keyword: str) -> bool:
    """Reject numeric, time-of-day and boilerplate fragments that YAKE emits as keywords."""
    kw = keyword.strip().lower()
    if kw in _NOISE_PHRASES or sum(c.isalpha() for c in kw) < _MIN_LETTERS:
        return False
    tokens = kw.split()
    if any(_NUMERIC_TOKEN.match(t) or _CONTRACTION_FRAGMENT.match(t) for t in tokens):
        return False
    if len(tokens) == 1 and kw in _GENERIC_WORDS:
        return False
    return not all(t in _NOISE_TOKENS for t in tokens)


def make_extractor() -> yake.KeywordExtractor:
    return yake.KeywordExtractor(lan="en", n=3, dedupLim=0.9, top=10)


def extract_keywords(text: str, extractor: yake.KeywordExtractor) -> list[tuple[str, float]]:
    if not text.strip():
        return []
    return [
        (kw.lower(), float(score))
        for kw, score in extractor.extract_keywords(text)
        if is_valid_topic(kw)
    ]


def item_text(title: str, summary: str, content: str) -> str:
    parts = [
        strip_html(title or ""),
        strip_html(summary or ""),
        strip_html(content or ""),
    ]
    return " ".join(p for p in parts if p).strip()
