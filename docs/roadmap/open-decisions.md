# Open Decisions

Unresolved design questions that must be answered before the relevant component is built. Each item should be resolved into an ADR, a design document update, or a documented decision before work begins on the affected area.

Resolved items are removed from this list and captured in the relevant design or architecture document.

---

## Topic extraction approach

**Question:** How are topics extracted from feed item content?

**Affects:** Item write path in the feed poller, graph richness, `ABOUT` edge population, dependency footprint

**Options:**
- Simple keyword extraction (RAKE, YAKE) — no model, fast, zero external dependency, lower quality
- Lightweight NLP (spaCy) — better entity and topic quality; adds a ~50MB model download to the Docker image
- LLM via API — highest quality; requires external API call, key management, adds latency and cost per item; not suitable as a default

**Recommendation pending:** YAKE for v1 (lightweight, no model download, good enough for topic clustering); spaCy as an opt-in upgrade.

---

## Reader mode library

**Question:** Which library handles full-text extraction for reader mode?

**Affects:** Feed poller content extraction step, Docker image size, extraction quality

**Options:**
- `trafilatura` — fast, actively maintained, good quality, pure Python
- `python-readability` — port of Mozilla Readability, well-known, slightly older
- `newspaper4k` — feature-rich but heavier

**Recommendation pending:** `trafilatura` is the current front-runner.

---

## Derived edge computation schedule

**Question:** When are `SIMILAR_TO` and `RELATED_TO` edges recomputed?

**Affects:** Graph freshness, write performance, poller architecture

**Options:**
- On every poll (fresh but potentially expensive as the graph grows)
- On a separate scheduled job (configurable interval — default: every 6 hours)
- On demand (triggered via API)

**Recommendation pending:** Scheduled job, defaulting to every 6 hours, triggerable on demand via API.

---

## OPML folder structure handling

**Question:** How does Reed represent OPML folder/category structure on import?

**Affects:** Tag model, feed organisation, import UX

**Options:**
- Map OPML folders to flat tags (simplest; aligns with Reed's flat tag model)
- Preserve folder hierarchy as nested tags or a separate `Folder` concept (more faithful to OPML but adds complexity)

**Recommendation pending:** Map to flat tags. Note the mapping to the user during import.

---

## Instance backup format

**Question:** What is the precise format of the instance backup / restore archive?

**Affects:** Backup/restore implementation, portability guarantees across Reed versions

**Options:**
- JSON archive (human-readable, portable, version-tagged)
- Kuzu database directory snapshot (fastest; not portable across Kuzu versions)
- Both (JSON as the interchange format; Kuzu snapshot as a fast local backup)

**Recommendation pending:** JSON as the canonical interchange format for portability; document Kuzu directory copy as a fast local backup option.

---

## Author node / co-authorship

**Question:** Should `author` become a proper `Author` graph node instead of a flat string property on `Item`?

**Affects:** Schema (would need a migration), byline parsing/normalisation for co-authored and dirty bylines ("A, B and C", names with titles), any M6+ tool that wants richer author traversal (co-authorship, author-topic affinity graphs)

**Context:** Raised during M6 brainstorming (2026-08-09) when considering richer author-browsing MCP tools. `get_author_profile` (topics/date-range/feeds for an author, via exact-string match on `Item.author`) covers the near-term need without a schema change. A real `Author` node buys co-authorship traversal but requires normalising dirty byline strings first, which is nontrivial and not currently blocking anything.

**Recommendation pending:** Not needed for M6. Revisit only if a concrete use case needs co-authorship traversal specifically (author-profile-by-topic is enough for now).

---

## Saved/named graph traversal views

**Question:** Should Reed let a user save a named query/traversal ("my weekly AI governance digest") for re-running later?

**Affects:** Would need a new node type (or REST-only feature) to store the saved query; MCP-only state would not benefit the web UI

**Context:** Raised during M6 brainstorming (2026-08-09). In an MCP/Claude Code context, this durable-recipe layer already exists client-side (`CLAUDE.md`, slash commands, skills), so building it into Reed risks duplicating something the client already does better, and doing it MCP-only would fragment it away from the web UI.

**Recommendation pending:** Don't build for M6. If it ever lands, it belongs as a REST + web UI feature, not MCP-only.

---

## Manual item capture from an external URL

**Question:** Should Reed support pulling an arbitrary external URL in as a first-class `Item` (not just an annotation), reusing the existing `http.safe_get` SSRF guard and `reader.extract_article`?

**Affects:** Schema (what `Feed` does an orphan item belong to, given most queries reach items via `HAS_ITEM`), polling semantics, export/import handling of orphan items, unread-count accuracy

**Context:** Raised during M6 brainstorming (2026-08-09) as a genuinely graph-native alternative to `capture_external_finding` (which appends to a `Note` instead) — the finding becomes a real node and joins `SIMILAR_TO` computation rather than sitting in a note. M6 ships `capture_external_finding` for the immediate research-loop need; this is a larger design question deliberately deferred rather than rejected.

**Recommendation pending:** Not resolved. Needs its own design pass on the orphan-item questions above before being attempted.

---

## Scheduled AI web-scanning / discovery feature

**Question:** Should Reed support user-configured, scheduled web scanning — themes/topics/sites as parameters, a configurable crawl frequency, results summarised within Reed with links, and the ability to subscribe to discovered sources — and if so, does the scanning execution live inside Reed or get delegated to an external AI client?

**Affects:** Potentially a new node type (watch/scan configuration), a new scheduled trigger separate from the existing feed poller, a summarisation/presentation surface in the web UI, and — depending on which option below — new external API dependencies (search + LLM) or new MCP write-back tools.

**Context:** Raised by Simon (2026-08-09), immediately after M6's design settled the closely related question of whether Reed should ship its own `web_search` MCP tool (rejected — redundant with the client's own search, adds a second secret/API dependency, contradicts the "graph traversal interface, not a research agent" design principle). This request is materially larger: not a single search call, but a standing, scheduled discovery subsystem. It also spans multiple genuinely independent pieces (config storage, scheduling, crawling/summarisation, presentation, subscribe workflow) — per the brainstorming process's own decomposition guidance, this is not a single sub-project-sized unit of work and would need its own `/brainstorming` pass when picked up.

**Options:**
- **Native in Reed** — Reed's own background job (like the feed poller) periodically calls an external search + LLM summarisation API directly. Full control and works with any MCP client, but reintroduces exactly the problem M6 just rejected at a larger scale: new secrets, rate limits, provider lock-in, ongoing operational cost, baked into a project whose entire auth story today is one API key.
- **Delegate to an AI client (Simon's stated preference)** — Reed stores the watch configuration (themes/topics/sites/frequency) via its existing API/MCP surface only. The actual scanning is triggered externally (e.g. a scheduled `claude` CLI invocation via host cron/launchd, outside Reed's container) which reads the config, does its own web research using its own search tool, and writes findings back into Reed through new MCP write tools analogous to M6's `capture_external_finding`. Reed never touches a search API or an LLM API directly — it stores config and receives write-backs, consistent with the position just established in M6.
- **Hybrid** — Reed owns config + schedule + a "candidate discoveries" review surface, but genuinely delegates the crawl/summarise step to an external process either way. Mostly the same as the second option with more Reed-side scaffolding (e.g. a due-for-scan query the external agent polls) — worth considering only if the second option's "purely external cron" trigger proves too manual in practice.

**The application-shell gap (Simon, 2026-08-09, follow-up):** even under the delegated-execution option, "Claude Code does the scanning" only covers the research step. It doesn't cover the parts that make this a *product feature* rather than a one-off script: user-defined settings/scope (what themes/topics/sites, editable over time), firing on a regular schedule, collating results across runs, analysing and categorising what comes back, displaying results somewhere durable, and providing actions against those results (subscribe, dismiss, save, etc). That's application surface — config storage, a results/candidates data model, a UI, and write actions wired back into the graph — that only Reed (or something like it) can own, regardless of who does the actual crawling. So "delegate the search" and "package it as a feature" are different questions; the delegation answer above only resolves the first one. The second is real Reed-side scope (schema + API + UI) whenever this is picked up.

**Recommendation pending:** The delegated-to-AI-client option is the better fit for the *research* step specifically — it extends M6's just-established principle (Reed is a graph store and traversal interface; research/search capability belongs to the client) rather than reversing it, and it avoids a second external-API dependency entirely. But that only answers who does the scanning, not who owns the feature — the application-shell gap above is genuine Reed-side work (config, results model, UI, actions) no matter which scanning option is chosen. Scope is too large and too different in kind (a proactive discovery subsystem, not passive feed aggregation) to fold into M6 or M7 — v1.0.0's scope is already locked and doesn't include this. Treat as a post-v1 feature with its own future milestone and its own `/brainstorming` pass; not a blocker for the current M6→M7 path. Tracked as [issue #205](https://github.com/simonives/reed/issues/205).

---

## User-maintained watch list (external-context alerting)

**Question:** Should Reed support a user-maintained "watch list" — a standing set of topics/entities/descriptions of interest (example use cases, 2026-08-15: "a specific piece of legislation is updated," "content relates to a specific employer's business or assets," "a topic relates to a contract or agreement term," "a topic relates to a feature in a software system I use") that flags new incoming items matching those concerns, regardless of which feed or topic-extraction path they arrived through?

**Affects:** Likely a new node type (a WatchItem or similar: topic/entity/description + match criteria), a new evaluation step in the ingestion pipeline (every newly-ingested item needs to be checked against the watch list, not just topic-extracted), a notification/flagging surface (how does a match actually reach the user — a flag on the item, a digest, a push?), and possibly new MCP tools for managing the list itself.

**Context:** Raised by Simon (2026-08-15) while scoping the M7→v1.0.0 punch list, explicitly as "a must-have in the future," not immediately scoped to a milestone. The framing is important: everything Reed does today is *reactive to its own ingested content* — poll feeds, extract topics from what arrived, traverse relationships within that corpus. A watch list inverts this: the user declares interest *before* content exists, and every new item gets evaluated against standing concerns independent of which feed produced it.

**Likely overlap with [issue #205](https://github.com/simonives/reed/issues/205) (scheduled AI web-scanning/discovery), not yet resolved:** the watch list's scope genuinely depends on whether it's meant to match only against feeds Reed already subscribes to, or against the wider internet. "Flag me if the Fair Work Act is updated" doesn't care whether that update appears in a feed Simon already follows — if the watch list is meant to catch it regardless, it's not a smaller, separate feature next to #205's scheduled discovery subsystem, it *is* that feature (or a specific alerting mode of it). If it's scoped only to existing subscribed feeds, it's a much more contained addition: a saved-query/alert layer over content already being ingested, no new external dependency, fits the current architecture (poller → topic extraction → a new match/flag step). This scope question needs resolving in whatever `/brainstorming` session picks this up — possibly the same session that picks up #205, not necessarily a separate one.

**Recommendation pending:** Not scoped to a milestone. Needs its own `/brainstorming` pass (or a joint one with #205, given the likely overlap) — not a blocker for RC1, M7, or v1.0.0's currently-agreed scope.

---

## Resolved decisions (moved here for reference)

| Decision | Resolved in |
|---|---|
| Graph DB over relational | ADR-001 |
| Python as primary language | ADR-002 |
| Single-user architecture | ADR-003 |
| Embedded database (Kuzu) | ADR-004 |
| Docker Compose distribution | ADR-005 |
| FastAPI for REST layer | ADR-006 |
| FastMCP for MCP server | ADR-007 |
| Web UI rendering model (Vue 3 + Vite) | ADR-008 |
| Topic extraction library (YAKE for v1; spaCy + LLM as v2 opt-ins) | ADR-009 |
| Reader mode library (trafilatura) | ADR-010 |
| ShareTarget storage (graph node, API keys excluded from export) | `docs/architecture/data-model.md` |
| Derived edge schedule (6h default, `POST /api/v1/graph/recompute` on-demand) | `docs/architecture/feed-poller.md` |
| OPML folder handling (map to flat tags, surface mapping in import response) | `docs/design/user-patterns.md` |
| Instance backup format (JSON via API for portability; Kuzu dir copy for fast local backup) | `docs/architecture/api-design.md` |
| PyPI package name (`reed-rss`; CLI entry point remains `reed`) | `pyproject.toml` |
| Repository/registry naming (GitHub `simonives/reed`; PyPI `reed` taken, `reed-rss` used; Docker Hub not applicable — packaging is GHCR, namespaced to the GitHub repo) | `pyproject.toml`, ADR-005 |
| v1 feed ingestion patterns | `docs/design/user-patterns.md` |
| v1 reading patterns | `docs/design/user-patterns.md` |
| Import/export scope (OPML + JSON profile + instance backup) | `docs/design/user-patterns.md` |
| Feed config inheritance model (global default + per-feed override) | `docs/design/user-patterns.md` |
| Built-in graph queries (v1 set) | `docs/design/user-patterns.md` |
| Share sheet scope and webhook payload | `docs/design/user-patterns.md` |
| Notes / annotations as v1 feature | `docs/design/user-patterns.md` |
