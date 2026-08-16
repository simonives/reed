# Changelog

All notable changes to Reed will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Reed uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Reed has not yet had a tagged release — everything below is unreleased,
grouped by the milestone it landed in.

---

## [Unreleased]

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
- `SIMILAR_TO` derived-edge recompute had unbounded combinatorial blowup when a single generic or boilerplate topic dominated a large corpus (e.g. a podcast-hosting-platform phrase repeated on every episode of one feed), causing multi-minute, multi-gigabyte recompute passes. Fixed with a configurable topic-dominance cap (percentage-of-corpus plus an absolute floor) excluding dominant topics from the similarity join
- A recompute failure could permanently kill the background poller; the derived-edge recompute's database lock is now held across its full multi-statement body to prevent a race with concurrent shutdown

### Security
- Dependency vulnerabilities are tracked via Dependabot and `pip-audit`; alerts are triaged and resolved as they arrive
