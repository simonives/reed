# ADR-010: trafilatura for reader mode content extraction

## Status

Accepted

## Context

Reed's reader mode fetches the full article URL and extracts the main content — stripping navigation, ads, footers, and boilerplate — to produce a clean reading experience. This runs in the feed poller when `reader_mode_enabled` is true for a feed or item, and on demand via the API.

Three Python libraries were evaluated:

**trafilatura** — Actively maintained (2024 releases), purpose-built for web content extraction, handles a wide range of modern web layouts. Pure Python, no external binary dependencies. Returns clean text or HTML. Has built-in metadata extraction (title, author, date). Fast.

**python-readability** — A Python port of Mozilla's Readability algorithm (the same algorithm Firefox Reader View uses). Solid and well-understood, but less actively maintained than trafilatura. Returns an HTML fragment rather than clean text, so post-processing is needed.

**newspaper4k** — Feature-rich: extracts authors, publish dates, images, keywords, and summaries in addition to body text. Heavier dependency footprint. More than Reed needs for reader mode.

## Decision

trafilatura is the reader mode extraction library.

## Rationale

trafilatura has the best maintenance trajectory of the three options and handles the widest range of modern web content — including paywalled sites that return article previews, dynamic content patterns, and non-English pages. Its output is clean text or structured HTML with a single function call. The metadata it extracts (title, author, date) can supplement feed-provided metadata when the feed itself is sparse.

python-readability is a reasonable fallback but its maintenance velocity is lower and it requires more post-processing. newspaper4k is overbuilt for the task.

## Consequences

- Reader mode extraction is a single `trafilatura.fetch_url()` + `trafilatura.extract()` call in the poller
- trafilatura's extraction is not perfect on all sites — JavaScript-heavy single-page apps may return little or no content, since trafilatura does not execute JavaScript. This is a known limitation of all Python-based extractors and is documented as expected behaviour
- If a user finds trafilatura failing on specific sites, the mitigation in v1 is to disable reader mode for that feed; a pluggable extractor backend is a v2 consideration
