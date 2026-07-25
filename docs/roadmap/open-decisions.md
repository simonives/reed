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
