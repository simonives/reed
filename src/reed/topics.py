# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import yake

from .text import strip_html


def make_extractor() -> yake.KeywordExtractor:
    return yake.KeywordExtractor(lan="en", n=3, dedupLim=0.9, top=10)


def extract_keywords(text: str, extractor: yake.KeywordExtractor) -> list[tuple[str, float]]:
    if not text.strip():
        return []
    return [(kw.lower(), float(score)) for kw, score in extractor.extract_keywords(text)]


def item_text(title: str, summary: str, content: str) -> str:
    parts = [
        strip_html(title or ""),
        strip_html(summary or ""),
        strip_html(content or ""),
    ]
    return " ".join(p for p in parts if p).strip()
