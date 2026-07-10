# ADR-009: YAKE for topic extraction (v1)

## Status

Accepted

## Context

The feed poller writes `Topic` nodes and `ABOUT` edges during item ingestion. Every incoming item needs topic extraction: a lightweight operation that runs inline per item on every poll cycle. The extracted topics drive the graph's `ABOUT` edges, which in turn feed the derived `RELATED_TO` (topic co-occurrence) and `SIMILAR_TO` (item similarity) edges — the core of Reed's graph traversal value.

Three approaches were considered:

**Simple keyword extraction (YAKE, RAKE)** — Pure Python libraries with no model download. YAKE (Yet Another Keyword Extractor) runs on raw text, requires no training data, and produces keywords weighted by position, frequency, and co-occurrence. Runs in milliseconds per item. No added Docker image size.

**Lightweight NLP (spaCy)** — Named entity recognition and dependency parsing produce higher-quality entity-level topics. Requires downloading a language model (~50 MB for `en_core_web_sm`, ~500 MB for `en_core_web_trf`). Adds meaningful Docker image size and startup time. Significantly better for recognising people, organisations, and proper nouns as topics.

**LLM via API** — Highest quality. Requires an external API key, adds per-item latency and cost, and introduces an external dependency unsuitable as a default for a self-hosted tool.

## Decision

YAKE is the topic extraction library for v1.

spaCy is deferred to v2 as a configurable opt-in (`REED_TOPIC_BACKEND=spacy`). Users who want higher-quality entity extraction and are willing to accept the larger image can enable it.

LLM-via-API extraction is deferred to v2+ as a second opt-in (`REED_TOPIC_BACKEND=llm`), for users with an API key who prioritise quality over operational simplicity.

## Rationale

YAKE is sufficient for v1's goal: populate `Topic` nodes with enough signal for graph traversal to be useful. The use case is clustering and discovery — "what topics appear across my feeds, and which items share them" — not precision entity extraction. YAKE produces adequate signal for this without adding weight to the Docker image or complexity to the installation story.

The v1 self-hosting pitch is `docker-compose up`. A 50–500 MB model download on first run contradicts that. spaCy belongs behind an opt-in.

## Consequences

- Topic quality in v1 is keyword-level, not entity-level. Proper nouns (company names, people) may be extracted inconsistently
- The graph's topic nodes in v1 are lower quality than they will be in v2 with spaCy — this is acceptable for the walking skeleton and early adopters
- The `REED_TOPIC_BACKEND` config key is reserved from v1 and defaults to `yake`; switching backends in v2 is a config change, not a code change for users
