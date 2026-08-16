# Reed — Gemini / Antigravity Context

Reed is a self-hosted, open-source RSS reader with a graph-native data model, a public REST API, and a first-class MCP server. Single-user. AGPL-3.0-or-later licence.

## Scope

**Read the "Current status" subsection in full at the start of every session.** The project is complex and carries significant context across milestones — do not rely on memory of a previous session; verify current state there first.

**Current status**

Current milestone: **M6 — MCP server (complete)**. **M7 — v1.0.0 in progress.**

| Milestone | Name | Status |
|---|---|---|
| M0 | Foundation | Complete |
| M1 | Walking skeleton | Complete |
| M2 | Usable reader | Complete |
| M3 | Migration-ready | Complete |
| M4 | Graph alive | Complete |
| M5 | API and integrations complete | Complete — four sub-projects (graph query endpoints, share sheet, export/import reshape, topics API completion), all merged |
| M6 | MCP server | Complete — FastMCP, 27 tools, stdio + HTTP transports |
| M7 | v1.0.0 | In progress — four sub-projects: distribution/SBOM release pipeline, documentation, website, public repository launch |

M7 is gated on: the release pipeline (`.github/workflows/release.yml`) actually firing a real release, and a public-facing security review of the single-static-API-key auth model before recommending public cloud hosting (see `docs/roadmap/open-decisions.md`).

A personal-use checkpoint ("RC1") was introduced ahead of the public v1.0.0 release — the same codebase, run locally, validated against a real feed library. RC1's blocking issue (unbounded `SIMILAR_TO` derived-edge recompute cost from a corpus-dominant topic) is fixed.

Active session plan: see `docs/roadmap/milestones.md` and open GitHub issues for current priorities. See Expiry for the refresh trigger on this subsection.

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

This file is authoritative for all work in this repo when operating as Gemini via Antigravity (`agy`) — no parent instruction file exists inside it. Global default preferences apply where not overridden here; this file overrides those defaults on repo-specific technical and process matters regardless of recency.

Two specific overrides worth naming: this file pins exact model IDs (e.g. Sonnet 4.6, Opus 4.8) for the primary Claude-driven workflow in this repo rather than tier-only routing, and it makes the Superpowers methodology (brainstorming → plan → TDD → verify → finish) mandatory for this repo. When acting as Gemini here, you are most often the **adversarial reviewer** called out from a Claude Code session (see Commands), not the primary driver — treat the Claude-side process below as the standing workflow you are reviewing into, not one you initiate independently unless Simon asks you to directly.

## Instructions

### Conventions

- **Response envelope.** Success responses are `{"data": ..., "meta": ...}`; errors are `{"error": {"code": ..., "message": ..., "detail": ...}}`. Established in M2.
- **Primary keys.** `Feed` is keyed by `url`, `Item` by `guid` (natural keys). Each also carries a UUID `id` used as the public/API identifier. Kuzu indexes only the primary key, and the natural keys are the ingestion hot path and enforce feed/item dedup, so they stay as PKs; UUID lookups table-scan, which is negligible at single-user scale. This resolves the primary-key portion of issue #31 as a deliberate won't-fix.
- **Graph schema.** The authoritative current schema is in `ARCHITECTURE.md`; the DDL lives in `src/reed/graph.py` `_init_schema`, versioned by `_SCHEMA_VERSION` with registered per-version steps in `_migrate`.
- **Branch naming.** `feat/`, `fix/`, `docs/`, `chore/`.
- **Model routing.** Apply these consistently — the right model for the task is not optional.

  | Task | Model | How |
  |---|---|---|
  | Default — implementation, refactoring, debugging, file edits | Sonnet 4.6 | Default session model in the Claude Code driver session |
  | Brainstorming/design workflow | Sonnet 4.6, max thinking budget | Simon confirms before it begins |
  | Code review workflow | Opus 4.8 | Simon runs manually: `claude --model claude-opus-4-8` |
  | Security review workflow | Opus 4.8 | Simon runs manually: `claude --model claude-opus-4-8` |
  | Adversarial review — **this is you** | Gemini 3.1 Pro (High) via `agy` | Called by the Claude-side assistant after brainstorming and after reviews |

- **Keep "Current status" current.** Whoever is driving should update the milestone/phase table and active session plan in Scope whenever a milestone phase completes or the plan changes. Do not let it drift.

### Commands

- **Superpowers methodology — mandatory for all new features or significant changes** in the primary (Claude Code) workflow. The `superpowers@claude-plugins-official` plugin is installed there; no hard gate is skipped without explicit instruction from Simon.
  1. Brainstorming workflow — before any implementation. No code until a design is presented and approved. You are called in here to adversarially review the proposal before Simon approves it.
  2. Planning workflow — immediately after brainstorming approval. Implementation plan written to `docs/superpowers/specs/` before coding begins. Note: `docs/superpowers/` is gitignored — specs live on disk for reference during implementation but are not committed to git.
  3. Test-driven development — mandatory for all implementation. No production code without a failing test first. Code written before tests gets deleted and restarted — no exceptions.
  4. Verification before completion — before marking any task done. All tests pass, output is clean, behaviour matches the spec.
  5. Finishing-a-branch workflow — before raising a PR.

  **For bug fixes:** the failing test that reproduces the bug is written first, then the fix. No exception.

  **For exploration or prototyping:** throwaway spikes are exempt from TDD but must be deleted before any production implementation begins. Spike code is never adapted into production — production is implemented fresh from tests.

- **After implementing any feature or fix** (Claude-side): the simplify workflow runs if the new code has obvious duplication, verbosity, or abstraction opportunities; the verify workflow runs to confirm expected behaviour in a live context.

- **Before any PR** (Claude-side):
  - The code-review workflow runs on the branch diff — mandatory for every PR, run manually by Simon on Opus 4.8.
  - The security-review workflow runs if the change touches any of: auth (`api/deps.py`, `X-API-Key` handling, any new endpoint), external HTTP (poller fetch, feed subscription), Kuzu write paths (`graph.py` mutations), config or environment variable handling, or file I/O / data export/import.
  - After each review, the adversarial review workflow below runs before findings are presented to Simon.
  - All work happens on a feature branch; PR into `main` — never a direct commit to `main`.

- **Adversarial review workflow — your primary role in this repo.** Two outputs require your pass before Simon approves them: brainstorming proposals (after the brainstorming workflow, before approval) and review findings (after code-review or security-review, before Simon acts on them).

  You are invoked as:
  ```bash
  agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions --print-timeout 10m -p "<prompt>"
  ```
  The prompt you receive carries: brief project context (Reed is a self-hosted RSS reader; the component under review), the full Claude output (proposal or findings), and the instruction to identify gaps, risks, missed cases, or alternative perspectives — what Claude missed or got wrong.

  Your review is then presented to Simon alongside Claude's original output and a synthesis of where you agree, where you diverge, and what the divergence means. Nothing you raise gets silently folded into the other side's output — it is surfaced explicitly, and Simon gives explicit approval or amendment before anyone proceeds.

- **After any review (code-review or security-review):**
  - For every finding, a GitHub issue is created in `simonives/reed`.
  - Labels applied by finding type: `bug` (correctness), `security`, `performance`, `tech-debt`.
  - Issue title format: `<type>: <short description>` — e.g. `bug: create_item orphans items on resubscription`.
  - Issue body includes: affected file(s) and line numbers, description of the problem, the exploit or failure scenario, and the recommended fix.

## Negatives

- **No Superpowers hard gate** (brainstorming, planning, TDD, verification, finishing-a-branch) **is skipped without explicit instruction from Simon** in that session. There is no standing exception — only Simon can waive a gate, and only in the moment.
- **No production code is written before a failing test exists**, except for throwaway exploration spikes — and those are deleted before production implementation begins; spike code is never adapted into the real implementation.
- **No direct commits to `main`.** All work goes through a feature branch and a PR.
- **The code-review and security-review workflows are not run by an agent, Claude-side or Gemini-side.** Both are run manually by Simon on Opus 4.8.
- **A Gemini adversarial concern is never merged into Claude's output silently.** It is surfaced explicitly alongside the synthesis, and Simon's call is awaited before proceeding.
- **Multiple review findings are never batched into one GitHub issue** — one finding, one issue. Exception: a finding already fixed within the same PR does not need an issue at all.
- **Kuzu is never called from anywhere except `graph.py`** (the single seam rule) — API routers, MCP server, and poller must go through it.

## Expiry

- Milestone/phase status table and active session plan (Scope → Current status) — owner: Simon, last-verified: 2026-08-16, refresh interval: on every milestone phase completion or change of active session plan (check every session, per the mandatory read-first instruction).
- Pinned model versions (Sonnet 4.6, Opus 4.8, Gemini 3.1 Pro (High)) — owner: Simon, last-verified: 2026-07-25, refresh interval: whenever a named model is superseded or Simon changes routing.
- Issue #31 reference (primary-key won't-fix) — stable design decision, not perishable; no refresh trigger.
