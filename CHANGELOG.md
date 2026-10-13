# Changelog

All notable changes to Reed will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Reed uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

0.6.1 is the first tagged release. Entries before it are grouped by the milestone they landed in.

---

## [Unreleased]

### Fixed
- Kuzu's page cache defaulted to about 80% of system RAM, so Reed's memory grew to roughly 3 GB (including swap) on a 3.8 GB host. The cache is now capped by `REED_KUZU_BUFFER_POOL_MB` (default 512, `0` restores Kuzu's default). A recompute over a 463 MB library completes in 2.2 s at that cap

## [0.6.2] - 2026-10-13

### Fixed
- The derived-edge recompute failed on every poll cycle when Kuzu's `SIMILAR_TO` table hit an internal CSR assertion (`csr_node_group.cpp`, `KU_UNREACHABLE`), logging over 1,000 failures a day. The recompute now drops and recreates `SIMILAR_TO` (derived data) and retries once when it sees that assertion
- A failed recompute is no longer retried every 60 seconds. It backs off from 5 minutes, doubling per consecutive failure, up to the recompute interval, and a success clears the backoff

### Changed
- The release workflow no longer publishes `v0.*` tags to PyPI. They still build and push the container image and create a GitHub Release. PyPI publishing starts at v1.0.0

## [0.6.1] - 2026-10-04

### Added

**Core reader (M1–M3)**
- Feed subscription, polling (async background worker, conditional GET via ETag/Last-Modified), and item ingestion
- Three-pane reading UI (Vue 3 + Vite): feed list, item list, reading pane, keyboard-first navigation
- Read/starred state, tags, per-item notes, reader mode (Trafilatura-based content extraction)
- OPML import/export and full JSON backup/restore
- Kuzu-backed graph data model with a public REST API (`/api/v1/`) from the start

**Graph and topics (M4)**
- YAKE-based topic extraction per item, with a `Topic` node and `ABOUT` edges
- `/api/v1/topics` endpoints for listing and traversing topics
- XSS hardening, async handler completion, restore isolation, and poller resilience fixes from a dedicated bug-fix sprint

**API and integrations (M5)**
- Derived-edge recompute job producing `SIMILAR_TO` (item-to-item) and `RELATED_TO` (topic-to-topic) edges, plus `/api/v1/graph/*` traversal endpoints (similarity, adjacency, feed health, author, topic timeline)
- Share sheet: `ShareTarget` nodes, `/api/v1/share/*` CRUD and delivery (webhook, Raindrop.io), Settings UI and reading-view Share button
- Export/import reshaped to a consistent `/export/*` / `/import/*` shape, with a `X-Confirm-Destructive` header guarding restore
- `/api/v1/topics/{id}/items` and `/api/v1/topics/{id}/related` completing the topics API

**MCP server (M6)**
- Full MCP server via FastMCP: 27 tools spanning feeds, items, graph traversal (including cross-node path-finding between items and topics), topic/tag/author discovery, export, research capture, and config
- `reed://graph/overview` resource and three guided-workflow prompts (`deep_reading_session`, `weekly_digest`, `research_thread`)
- Both stdio (Claude Desktop, Cursor) and HTTP transports, authenticated via `X-API-Key` on both
- Topic centrality (PageRank) and clustering (Louvain) over the topic-co-occurrence graph

### Fixed
- `get_topic_clusters` applied `limit` to topic rows ordered by cluster id, so the unclustered bucket (`-1`, every topic without `RELATED_TO` edges) came back first as one alphabetical cluster of fragments. `limit` now counts clusters, the unclustered bucket and singletons are excluded, clusters are ordered by size, each lists at most 25 topics by item count, and each carries a `size` field
- Topic extraction emitted numeric, time-of-day, calendar, contraction (`n’t`) and boilerplate fragments (`1:00 am cst`, `331-363`, `hosted on acast`) that dominated clustering. `is_valid_topic()` now filters them at extraction, and existing invalid topics are purged when the poller starts
- Feed-level tags were invisible at item level, so tag filters returned nothing and every tag count was 0. Items now inherit their feed's tags at read time across item lists, tag counts, search and `item.tags`
- Poll errors with an empty `str(exc)` (for example httpx timeouts) were stored as an empty `last_error`. The exception type is now recorded
- The `mark_starred` MCP tool returned the full article body (about 92 KB) for a single toggle. It no longer returns `content` or `reader_content`
- `SIMILAR_TO` derived-edge recompute had unbounded combinatorial blowup when a single generic or boilerplate topic dominated a large corpus (e.g. a podcast-hosting-platform phrase repeated on every episode of one feed), causing multi-minute, multi-gigabyte recompute passes. Fixed with a configurable topic-dominance cap (percentage-of-corpus plus an absolute floor) excluding dominant topics from the similarity join
- A recompute failure could permanently kill the background poller; the derived-edge recompute's database lock is now held across its full multi-statement body to prevent a race with concurrent shutdown

### Security
- Dependency vulnerabilities are tracked via Dependabot and `pip-audit`; alerts are triaged and resolved as they arrive
