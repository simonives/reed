# Changelog

All notable changes to Reed will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Reed uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

0.6.1 is the first tagged release. Entries before it are grouped by the milestone they landed in.

---

## [Unreleased]

## [0.6.5] - 2026-11-18

Follow-up to 0.6.4 (which was deployed but never tagged). Live memory on the reference instance, which was reaching the 2 GB cap and being killed about every 8 hours, held at about 290 MB over the first 2 hours after this build, with no restarts. Findings and measurements are in #335, #326 and #355.

### Fixed
- Kuzu holds un-checkpointed write data in memory and by default checkpoints only at 16 MB of log. Measured on a production-sized copy, a `CHECKPOINT` every 50 writes cut native growth per write from about 32 KB to about 3 to 5 KB. The poller now checkpoints after each poll cycle's writes, each backfill batch and each recompute (#355, #364)
- `CALL drop_projected_graph` cleared the prepared-statement cache on every topic-cluster or centrality call, bringing back the per-prepare leak. The cache now clears only on schema changes and FTS index calls (#337)
- Restoring a backup failed and rolled back whenever derived `RELATED_TO` edges existed, and the rollback error hid the real one (#339)
- The outbound address check allowed ranges that are not globally routable and misjudged IPv6 forms that embed an IPv4 address. It now requires a global address and judges embedded IPv4 forms by the embedded address (#357)
- MCP `mark_read` with `item_ids` and `feed_id` also marked the whole feed read. The combination is now rejected (#343)
- `PATCH /api/v1/config` could not set the four `similarity_*` keys (#344)
- Atom entries with only `<updated>` had no publication date, so they dropped out of similarity and timelines (#352)
- Two concurrent subscribes to one feed returned 500 for the loser, and a feed or item deleted mid-request raised an assertion. They now return 409 and 404 (#353)
- Dead feeds were polled at the full rate forever. The backoff in the architecture doc is now applied: double after 3 errors, quadruple after 6, daily after 10 (#342)
- The derived-edge recompute ran in full on every restart, and the topic-dominance cap counted all history rather than the similarity window. The last recompute time now comes from the stored edges and the cap counts in-window items (#347, #246)
- Shutdown could close the database under a running worker thread. It now waits for poller thread work, closes the database after the MCP lifespan exits, checkpoints first so the next start has no log to replay, and any later call fails with a clear error (#348)
- The Docker image installed dependencies without the lockfile. It now installs the exact versions in `uv.lock` (#350)

### Changed
- A poll cycle writes all feed metadata in one statement, and item enrichment is one write instead of about 21 (#338). On a scratch copy this took enrichment from 1,747 ms to 205 ms for ten keywords
- Responses from feed and article URLs are streamed and capped (`REED_MAX_FEED_BYTES`, default 10 MB; `REED_MAX_ARTICLE_BYTES`, default 5 MB), and articles must be HTML. One shared SSL context serves all clients (#341, #345, #346)
- MCP `search` no longer returns each hit's full text. A feed that puts a whole article in its description now stores it as the item body with a short summary (#341)
- Keyword extraction reads at most 15,000 characters per item, and entries that are already stored skip HTML parsing (#351)
- Kuzu is limited to two worker threads (`REED_KUZU_MAX_THREADS`), and the image sets `MALLOC_ARENA_MAX=2` and `MALLOC_TRIM_THRESHOLD_=131072` (#349)

### Tests
- The concurrency test asserts overlap instead of elapsed time, which failed CI intermittently (#354)

## [0.6.4] - 2026-11-18

### Fixed
- Memory grew without bound until the kernel OOM killer ended the process (#335, #326). Kuzu's `Connection.execute(query, params)` builds a new prepared statement on every call and leaks about 40 KB of native memory each time (1,600 calls leaked 68 MB; preparing once and re-executing leaked nothing). Reed now prepares each query text once and reuses it, in a bounded cache cleared on schema changes
- Polling re-ran `MERGE (f)-[:HAS_ITEM]->(i)` for every entry of every feed on every cycle, even when the item was already stored, which cost 260 ms per entry. `create_item` now checks the edge with a read first and returns without writing, which takes 8 ms
- Memory spikes of 1 GB or more within a minute of a restart, then hourly (#334). The poller polled every due feed at once and each feed ran its own article extraction, so the lxml and trafilatura work of all feeds overlapped. Feed polls are now limited to four at a time and article extractions to two at a time across all feeds
- The startup topic backfill loaded the full text of every unenriched item in one query (#133). It now loads ids first and reads text in batches of 100

## [0.6.3] - 2026-10-14

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
