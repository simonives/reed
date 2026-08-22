# Reed — Agent Context

Reed is a self-hosted, open-source RSS reader with a graph-native data model, a public REST API, and a first-class MCP server. Single-user. AGPL-3.0-or-later licence.

## Scope

**Read the "Current status" subsection in full at the start of every session.** The project is complex and carries significant context across milestones — do not rely on memory of a previous session; verify current state there first.

**Current status**

See [`docs/roadmap/milestones.md`](docs/roadmap/milestones.md) for milestone definitions and current progress, and the repository's GitHub Issues and Milestones for active work items. This file does not track day-to-day project status, check those sources directly rather than relying on this file being current.

**Architecture**

All architecture decisions are documented in `ARCHITECTURE.md`. Read it before making any structural suggestions or changes.

Locked-in decisions:
- **Language:** Python throughout (API, MCP server, poller, graph service)
- **Database:** Kuzu (embedded graph DB — no server process)
- **REST framework:** FastAPI
- **MCP server:** FastMCP
- **Auth:** Single API key via `X-API-Key` header
- **Packaging:** Docker Compose + GitHub source; image on GHCR
- **User model:** Single-user, self-hosted only

**The single seam rule:** `graph.py` is the only module that imports or calls Kuzu. The API routers, MCP server, and poller all import from `graph.py`. Nothing else touches the database directly.

**Project structure**

```
reed/
├── src/reed/                   ← core Python package
│   ├── main.py                 ← FastAPI app factory, lifespan (starts poller + MCP)
│   ├── config.py               ← Settings (pydantic-settings, env vars)
│   ├── graph.py                ← ALL Kuzu interactions — the only file that touches the DB
│   │                             Includes schema DDL, _SCHEMA_VERSION, _migrate()
│   ├── poller.py               ← Async feed poller (background worker)
│   ├── mcp_server.py           ← FastMCP server, 27 tool definitions, prompts, resources
│   ├── mcp.py                  ← ASGI mount for the MCP server (API-key middleware, routing)
│   ├── discovery.py            ← Feed URL auto-discovery (website → feed URL)
│   ├── reader.py                ← Reader mode extraction (trafilatura)
│   ├── text.py                 ← Text utilities (word count, truncation)
│   ├── topics.py                ← YAKE topic extraction and SIMILAR_TO/RELATED_TO computation
│   ├── opml.py                  ← OPML parse and serialise
│   ├── http.py                  ← Shared HTTP client with SSRF guard
│   └── cli.py                   ← `reed serve` CLI entry point
│
├── src/reed/api/                ← FastAPI routers (one file per resource group)
│   ├── feeds.py                 ← /api/v1/feeds
│   ├── items.py                 ← /api/v1/items
│   ├── tags.py                  ← /api/v1/tags
│   ├── topics.py                ← /api/v1/topics
│   ├── search.py                ← /api/v1/search
│   ├── graph.py                 ← /api/v1/graph (similarity, adjacency, feed health, author, timeline, recompute)
│   ├── share.py                 ← /api/v1/share (share targets, delivery)
│   ├── export.py                ← /api/v1/export (JSON, OPML, backup)
│   ├── import_.py                ← /api/v1/import (OPML, backup restore)
│   ├── config.py                ← /api/v1/config (GET/PATCH)
│   ├── deps.py                   ← FastAPI dependencies (API key auth)
│   ├── schemas.py                ← Pydantic request/response models (shared)
│   └── errors.py                 ← Exception handlers and error response builders
│
├── frontend/src/                 ← Vue 3 + Vite single-page application
│   ├── App.vue                   ← Root component, router outlet
│   ├── main.js                   ← App bootstrap
│   ├── components/                ← UI components (FeedList, ItemList, ReadingPane, etc.)
│   ├── stores/                    ← Pinia stores (feeds, items, ui state)
│   ├── composables/                ← Shared Vue composition functions
│   ├── lib/                        ← API client and utilities
│   └── styles/                     ← CSS variables, themes
│
├── docs/
│   ├── roadmap/
│   │   ├── milestones.md          ← Full milestone definitions and dependency map
│   │   └── open-decisions.md      ← Unresolved design questions + resolution log
│   ├── superpowers/
│   │   ├── plans/                 ← Per-session implementation plans (one file per milestone phase)
│   │   └── specs/                 ← Implementation specs (written by the planning workflow)
│   └── adr/                       ← Architecture Decision Records
│
├── tests/                         ← Pytest test suite
├── data/                          ← Mounted volume — reed.kuzu lives here at runtime
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── ARCHITECTURE.md                ← Authoritative architecture reference
```

**Open decisions**

The live list of unresolved design questions is at `docs/roadmap/open-decisions.md`. Check it before starting work on M7 (distribution, documentation, public launch — including the auth-model review gating public cloud hosting). The resolved decisions log is in the same file.

## Precedence

This file is authoritative for all work in this repo — no parent agent-instruction file exists inside it. Global default agent preferences apply where not overridden here; this file overrides those defaults on repo-specific technical and process matters regardless of recency.

Two specific overrides worth naming: this file defines repo-specific model routing conventions (mapping task type to capability tier and risk level, see Instructions below) rather than tier-only routing, and it makes the Superpowers methodology (brainstorming → plan → TDD → verify → finish) mandatory for this repo even where a lighter-weight default might otherwise apply.

## Instructions

### Conventions

- **Response envelope.** Success responses are `{"data": ..., "meta": ...}`; errors are `{"error": {"code": ..., "message": ..., "detail": ...}}`. Established in M2.
- **Primary keys.** `Feed` is keyed by `url`, `Item` by `guid` (natural keys). Each also carries a UUID `id` used as the public/API identifier. Kuzu indexes only the primary key, and the natural keys are the ingestion hot path and enforce feed/item dedup, so they stay as PKs; UUID lookups table-scan, which is negligible at single-user scale. This resolves the primary-key portion of issue #31 as a deliberate won't-fix.
- **Graph schema.** The authoritative current schema is in `ARCHITECTURE.md`; the DDL lives in `src/reed/graph.py` `_init_schema`, versioned by `_SCHEMA_VERSION` with registered per-version steps in `_migrate`.
- **Branch naming.** `feat/`, `fix/`, `docs/`, `chore/`.
- **Model routing.** Match model capability to task risk:
  - Default (implementation, refactoring, debugging, file edits): the project's standard working model.
  - Brainstorming and design workflow: the project's standard working model, maximum available reasoning effort.
  - Code review and security review workflows: the strongest available model tier, run by a maintainer rather than the agent doing the implementation work.
  - Adversarial review (see Commands): a different model family than the one used for the primary work, to catch blind spots the primary model shares with itself.

### Commands

- **Superpowers methodology — mandatory for all new features or significant changes.** The `superpowers@claude-plugins-official` plugin is installed; do not skip any hard gate without explicit instruction from the maintainer.
  1. Brainstorming workflow — before any implementation. No code until a design is presented and approved. Run the adversarial review workflow (below) on the output before seeking the maintainer's approval.
  2. Planning workflow — immediately after brainstorming approval. Implementation plan written to `docs/superpowers/specs/` before coding begins. Note: `docs/superpowers/` is gitignored — specs live on disk for reference during implementation but are not committed to git.
  3. Test-driven development — mandatory for all implementation. No production code without a failing test first. Delete code written before tests and start over — no exceptions.
  4. Verification before completion — before marking any task done. All tests pass, output is clean, behaviour matches the spec.
  5. Finishing-a-branch workflow — before raising a PR.

  **For bug fixes:** write the failing test that reproduces the bug first, then fix. No exception.

  **For exploration or prototyping:** throwaway spikes are exempt from TDD but must be deleted before any production implementation begins. Do not adapt spike code — implement fresh from tests.

- **After implementing any feature or fix:**
  - Run the simplify workflow if the new code has obvious duplication, verbosity, or abstraction opportunities.
  - Run the verify workflow to confirm the expected behaviour in a live context (not just that tests pass).

- **Before any PR:**
  - Run the code-review workflow on the branch diff — mandatory for every PR. Run manually by the maintainer on the strongest available model tier.
  - Run the security-review workflow if the change touches any of: auth (`api/deps.py`, `X-API-Key` handling, any new endpoint), external HTTP (poller fetch, feed subscription), Kuzu write paths (`graph.py` mutations), config or environment variable handling, or file I/O / data export/import.
  - After each review, run the adversarial review workflow (below) before presenting findings to the maintainer.
  - All work happens on a feature branch; PR into `main` — never commit directly to `main`.

- **Adversarial review workflow.** Two outputs require a Gemini pass before the maintainer approves them: brainstorming proposals (after the brainstorming workflow, before approval) and review findings (after code-review or security-review, before the maintainer acts on them).

  Run:
  ```bash
  agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions --print-timeout 10m -p "<prompt>"
  ```
  Construct the prompt with: brief project context (Reed is a self-hosted RSS reader; the component under review), the full agent output (proposal or findings), and the instruction "You are an adversarial reviewer. Identify gaps, risks, missed cases, or alternative perspectives. What did the agent miss or get wrong?"

  Then present the maintainer with: the agent's output, Gemini's adversarial review (verbatim key points, attributed), and a one-paragraph synthesis of where they agree, where they diverge, and what the divergence means. Wait for the maintainer's explicit approval or amendment before proceeding.

- **After any review (code-review or security-review):**
  - For every finding, create a GitHub issue in `simonives/reed`.
  - Apply labels by finding type: `bug` (correctness), `security`, `performance`, `tech-debt`.
  - Issue title format: `<type>: <short description>` — e.g. `bug: create_item orphans items on resubscription`.
  - Issue body must include: affected file(s) and line numbers, description of the problem, the exploit or failure scenario, and the recommended fix.

## Negatives

- **Do not skip a Superpowers hard gate** (brainstorming, planning, TDD, verification, finishing-a-branch) **without explicit instruction from the maintainer** in that session. There is no standing exception — only the maintainer can waive a gate, and only in the moment.
- **Do not write production code before a failing test exists**, except for throwaway exploration spikes — and those must be deleted before production implementation begins; do not adapt spike code into the real implementation.
- **Do not commit directly to `main`.** All work goes through a feature branch and a PR.
- **Do not run the code-review or security-review workflows yourself.** Both are run manually by the maintainer on the strongest available model tier — open the PR and prompt the maintainer to run them rather than attempting to run them yourself.
- **Do not merge a Gemini adversarial concern into your own output silently.** Surface it explicitly alongside your synthesis and wait for the maintainer's call.
- **Do not batch multiple review findings into one GitHub issue** — one finding, one issue. Exception: a finding already fixed within the same PR does not need an issue at all.
- **Do not call Kuzu from anywhere except `graph.py`** (the single seam rule) — API routers, MCP server, and poller must go through it.

## Expiry

- Model routing convention (capability-to-risk mapping, not pinned model IDs) — owner: Simon, last-verified: 2026-07-25, refresh interval: whenever the routing convention itself changes.
- Issue #31 reference (primary-key won't-fix) — stable design decision, not perishable; no refresh trigger.
