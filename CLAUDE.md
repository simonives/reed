# Reed — Claude Context

Reed is a self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server. Single-user. AGPL-3.0-or-later licence.

---

## MANDATORY: Read this section first — every session

**Before doing anything else in a Reed session, read this section in full.** The project is complex and carries significant context across milestones. Do not rely on memory of a previous session; verify current state here first.

### Where we are now

**Current milestone: M4 — Graph alive (complete)**

| Milestone | Name | Status |
|---|---|---|
| M0 | Foundation | ✅ Complete |
| M1 | Walking skeleton | ✅ Complete |
| M2 | Usable reader | ✅ Complete |
| M3 | Migration-ready | ✅ Complete |
| M4 | Graph alive | ✅ Complete |
| M5 | API and integrations complete | Not started |
| M6 | MCP server | Not started |
| M7 | v1.0.0 | Not started |

**M4 phase breakdown:**

| Phase | Scope | Status |
|---|---|---|
| M4-A | Graph enrichment — YAKE topic extraction, Topic/ABOUT schema v5, topics API | ✅ Complete |
| M4-B | Bug-fix sprint — enrichment, dedup, cursor pagination, API hardening | ✅ Complete |
| M4-C | Bug-fix sprint — XSS, async handler completion, restore isolation, export orphans, config nulls, poller resilience | ✅ Complete |

**Active session plan:** none — M4 complete. Next: review open issues, then scope M5.

**Update this section** when a milestone phase completes or the active session plan changes. Do not let it drift.

---

## Architecture

All architecture decisions are documented in `ARCHITECTURE.md`. Read it before making any structural suggestions or changes.

Key decisions already locked in:
- **Language:** Python throughout (API, MCP server, poller, graph service)
- **Database:** Kuzu (embedded graph DB — no server process)
- **REST framework:** FastAPI
- **MCP server:** FastMCP
- **Auth:** Single API key via `X-API-Key` header
- **Packaging:** Docker Compose + GitHub source; image on GHCR
- **User model:** Single-user, self-hosted only

---

## Project structure

```
reed/
├── src/reed/                   ← core Python package
│   ├── main.py                 ← FastAPI app factory, lifespan (starts poller + MCP)
│   ├── config.py               ← Settings (pydantic-settings, env vars)
│   ├── graph.py                ← ALL Kuzu interactions — the only file that touches the DB
│   │                             Includes schema DDL, _SCHEMA_VERSION, _migrate()
│   ├── poller.py               ← Async feed poller (background worker)
│   ├── mcp_server.py           ← FastMCP server and tool definitions
│   ├── discovery.py            ← Feed URL auto-discovery (website → feed URL)
│   ├── reader.py               ← Reader mode extraction (trafilatura)
│   ├── text.py                 ← Text utilities (word count, truncation)
│   ├── topics.py               ← YAKE topic extraction and SIMILAR_TO/RELATED_TO computation
│   ├── opml.py                 ← OPML parse and serialise
│   ├── http.py                 ← Shared HTTP client with SSRF guard
│   └── cli.py                  ← `reed serve` CLI entry point
│
├── src/reed/api/               ← FastAPI routers (one file per resource group)
│   ├── feeds.py                ← /api/v1/feeds
│   ├── items.py                ← /api/v1/items
│   ├── tags.py                 ← /api/v1/tags
│   ├── topics.py               ← /api/v1/topics
│   ├── search.py               ← /api/v1/search
│   ├── data.py                 ← /api/v1/data (export, backup, restore)
│   ├── opml.py                 ← /api/v1/opml (import/export)
│   ├── config.py               ← /api/v1/config (GET/PATCH)
│   ├── deps.py                 ← FastAPI dependencies (API key auth)
│   ├── schemas.py              ← Pydantic request/response models (shared)
│   └── errors.py               ← Exception handlers and error response builders
│
├── frontend/src/               ← Vue 3 + Vite single-page application
│   ├── App.vue                 ← Root component, router outlet
│   ├── main.js                 ← App bootstrap
│   ├── components/             ← UI components (FeedList, ItemList, ReadingPane, etc.)
│   ├── stores/                 ← Pinia stores (feeds, items, ui state)
│   ├── composables/            ← Shared Vue composition functions
│   ├── lib/                    ← API client and utilities
│   └── styles/                 ← CSS variables, themes
│
├── docs/
│   ├── roadmap/
│   │   ├── milestones.md       ← Full milestone definitions and dependency map
│   │   └── open-decisions.md  ← Unresolved design questions + resolution log
│   ├── superpowers/
│   │   ├── plans/              ← Per-session implementation plans (one file per milestone phase)
│   │   └── specs/              ← Implementation specs (written by /writing-plans)
│   └── adr/                    ← Architecture Decision Records
│
├── tests/                      ← Pytest test suite
├── data/                       ← Mounted volume — reed.kuzu lives here at runtime
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── ARCHITECTURE.md             ← Authoritative architecture reference
```

**The single seam rule:** `graph.py` is the only module that imports or calls Kuzu. The API routers, MCP server, and poller all import from `graph.py`. Nothing else touches the database directly.

---

## Model routing

Apply these model choices consistently. The right model for the task is not optional.

| Task | Model | How |
|---|---|---|
| Default — implementation, refactoring, debugging, file edits | Sonnet 4.6 | Default session model — no change needed |
| `/brainstorming` | Sonnet 4.6, max thinking budget | Simon will confirm before brainstorming begins |
| `/code-review` | Opus 4.8 | Simon runs manually: `claude --model claude-opus-4-8` |
| `/security-review` | Opus 4.8 | Simon runs manually: `claude --model claude-opus-4-8` |
| Adversarial review (see below) | Gemini 3.1 Pro (High) via `agy` | Run by the assistant after brainstorming and after reviews |

### Adversarial review workflow

Two outputs require an adversarial pass through Gemini before Simon approves them:

1. **Brainstorming proposals** — after `/brainstorming` produces a design, before Simon approves it.
2. **Review findings** — after `/code-review` or `/security-review` produces findings, before Simon acts on them.

**Process:**

After producing the output, run:

```bash
agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions --print-timeout 10m -p "<prompt>"
```

Construct the prompt to include:
- Brief project context (Reed is a self-hosted RSS reader; relevant component being reviewed)
- The full Claude output (proposal or findings)
- Instruction: "You are an adversarial reviewer. Identify gaps, risks, missed cases, or alternative perspectives. What did Claude miss or get wrong?"

Then present Simon with:
- **Claude's output** (the proposal or findings)
- **Gemini's adversarial review** (verbatim key points, attributed)
- **Your synthesis** (one paragraph: where they agree, where they diverge, what the divergence means)

Wait for Simon's explicit approval or amendment before proceeding. Do not merge a Gemini concern into your own output silently — surface it.

---

## Branch and PR workflow

- All work on a feature branch
- PR into `main` — never commit directly to `main`
- Branch naming: `feat/`, `fix/`, `docs/`, `chore/`

---

## Superpowers — mandatory development methodology

The `superpowers@claude-plugins-official` plugin is installed and its methodology is **mandatory** for all work on this project. Do not skip any hard gate without explicit instruction from Simon.

**Required workflow for any new feature or significant change:**
1. `/brainstorming` — before any implementation. No code until a design is presented and approved. Run adversarial review on the output before seeking Simon's approval (see Model routing above).
2. `/writing-plans` — immediately after brainstorming approval. Implementation plan written to `docs/superpowers/specs/` and committed before coding begins.
3. `/test-driven-development` — mandatory for all implementation. No production code without a failing test first. Delete code written before tests and start over — no exceptions.
4. `/verification-before-completion` — before marking any task done. All tests pass, output is clean, behaviour matches the spec.
5. `/finishing-a-development-branch` — before raising a PR.

**For bug fixes:** write the failing test that reproduces the bug first, then fix. No exception.

**For exploration or prototyping:** throwaway spikes are exempt from TDD but must be deleted before any production implementation begins. Do not adapt spike code — implement fresh from tests.

---

## Development workflow

Apply these gates consistently — do not skip them or wait to be asked.

**After implementing any feature or fix:**
- Run `/simplify` if the new code has obvious duplication, verbosity, or abstraction opportunities.
- Run `/verify` to confirm the expected behaviour in a live context (not just that tests pass).

**Before any PR:**
- Run `/code-review` on the branch diff. Mandatory for every PR. Simon runs this manually on Opus 4.8.
- Run `/security-review` if the change touches any of the following:
  - Auth (`api/deps.py`, `X-API-Key` handling, any new endpoint)
  - External HTTP (poller fetch, feed subscription)
  - Kuzu write paths (`graph.py` mutations)
  - Config or environment variable handling
  - File I/O or data export/import
- After each review, run the adversarial review workflow (see Model routing) before presenting findings to Simon.

Both `/code-review` and `/security-review` are run manually by Simon. Open the PR and prompt Simon to run them; do not attempt to run them yourself.

**After any review (code-review or security-review):**
- For every finding in the output, create a GitHub issue in `simonives/reed`.
- Apply labels based on finding type: `bug` for correctness issues, `security` for security findings, `performance` for perf issues, `tech-debt` for cleanup items.
- Issue title format: `<type>: <short description>` — e.g. `bug: create_item orphans items on resubscription`.
- Issue body must include: affected file(s) and line numbers, description of the problem, the exploit or failure scenario, and the recommended fix.
- Do not batch multiple findings into one issue. One finding = one issue.
- Findings already fixed in the same PR do not need an issue — only open findings that are being deferred.

---

## Code conventions

- **Response envelope.** Success responses are `{"data": ..., "meta": ...}`; errors are
  `{"error": {"code": ..., "message": ..., "detail": ...}}`. Established in M2.
- **Primary keys.** `Feed` is keyed by `url`, `Item` by `guid` (natural keys). Each also
  carries a UUID `id` used as the public/API identifier. Kuzu indexes only the primary
  key, and the natural keys are the ingestion hot path and enforce feed/item dedup, so
  they stay as PKs; UUID lookups table-scan, which is negligible at single-user scale.
  This resolves the primary-key portion of issue #31 as a deliberate won't-fix.
- **Graph schema.** The authoritative current schema is in `ARCHITECTURE.md`; the DDL
  lives in `src/reed/graph.py` `_init_schema`, versioned by `_SCHEMA_VERSION` with
  registered per-version steps in `_migrate`.

---

## Open decisions

The live list of unresolved design questions is at `docs/roadmap/open-decisions.md`. Check it before starting work on M5 (share targets, API completion) or M6 (MCP server). The resolved decisions log is in the same file.
