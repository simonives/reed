# Reed — Claude Context

## Scope

Reed is a self-hosted, open-source RSS reader with a graph-native data model, a public REST API, and a first-class MCP server. Single-user. AGPL-3.0-or-later licence.

**Read the "Current status" subsection in full at the start of every session.** The project is complex and carries significant context across milestones — do not rely on memory of a previous session; verify current state there first.

**Current status**

Current milestone: **M5 — API and integrations complete (complete)**. Starting **M6 — MCP server** next.

| Milestone | Name | Status |
|---|---|---|
| M0 | Foundation | Complete |
| M1 | Walking skeleton | Complete |
| M2 | Usable reader | Complete |
| M3 | Migration-ready | Complete |
| M4 | Graph alive | Complete (derived edges + graph query endpoints deliberately deferred to M5 sub-project 1 — see below) |
| M5 | API and integrations complete | **Complete** — all four sub-projects merged (2026-08-08) |
| M6 | MCP server | **Starting next** — see scope below |
| M7 | v1.0.0 | Not started |

M4 phase breakdown:

| Phase | Scope | Status |
|---|---|---|
| M4-A | Graph enrichment — YAKE topic extraction, Topic/ABOUT schema v5, topics API | Complete |
| M4-B | Bug-fix sprint — enrichment, dedup, cursor pagination, API hardening | Complete |
| M4-C | Bug-fix sprint — XSS, async handler completion, restore isolation, export orphans, config nulls, poller resilience | Complete |

M4-A's design deferred `SIMILAR_TO`/`RELATED_TO` derived-edge computation and the `/graph/*` query endpoints described in `docs/roadmap/milestones.md`'s M4 scope — that work now lives as M5 sub-project 1 (below), not as an M4 gap.

M5 was decomposed into four independently-specced sub-projects (specs and plans on disk at `docs/superpowers/specs/2026-07-24-m5-*-design.md` and `docs/superpowers/plans/2026-07-24-m5-*.md`, gitignored — not in git history, reference locally), all fully specced and adversarially reviewed (Gemini 3.1 Pro). **All four are now complete and merged:**

| Sub-project | Scope | Status |
|---|---|---|
| 1. Graph query endpoints | Derived-edge recompute job (`SIMILAR_TO`/`RELATED_TO`, schema v7), six `/api/v1/graph/*` endpoints | **Complete and merged** (PR #159, 2026-07-26) |
| 2. Share sheet | `ShareTarget` node (schema v8), `/share/*` CRUD + delivery (webhook, Raindrop.io), Settings UI + reading-view Share button | **Complete and merged** (PR #171, 2026-08-04) |
| 3. Export/import reshape | Reconcile `/data/*`, `/opml/*` against `api-design.md`'s `/export/*`, `/import/*` shape; `X-Confirm-Destructive` header on restore | **Complete and merged** (PR #178, 2026-08-07) |
| 4. Topics API completion | `/topics/{id}/items`, `/topics/{id}/related`; fixes issue #99 by deletion | **Complete and merged** (PR #199, 2026-08-08) |

PR #171's `/code-review` (Opus) surfaced four issues fixed before merge (clipboard failures on non-secure origins going unhandled, `_classify_response` crashing on non-dict JSON error bodies, `GET /share/targets` returning secrets in plaintext for no client benefit, and a delete-protection bypass via creating new copy-type targets) plus three deferred as fast-follow issues, subsequently fixed in PR #183 (below): **#172** (Raindrop `collection_id` sent as string, API expects numeric), **#173** (Settings enabled-checkbox can visually desync from store state on a failed toggle), **#174** (share-target config validation discards the Pydantic-coerced model, raw dict persisted instead).

PR #178 preserved and folded in two pre-existing bug fixes the written plan predated (#139's OPML feed-validation, which the plan's draft code would have silently regressed; #155's real feed-metadata population) plus #154 (`safe_url` `TypeError` on non-string input) as an extra task. Its `/code-review` (Opus) headline "critical" finding — a claimed >1MB upload causing an uncaught 500 on backup restore — was independently verified and found NOT to reproduce (Starlette's `Request._get_form()` already converts the internal exception to a clean 400); no fix was needed. Two genuine minor findings were deferred as fast-follow issues: **#179** (duplicated export-route boilerplate in `api/export.py`), **#180** (`import_opml` opens a fresh `http_client()` per feed instead of reusing one across the batch).

**M6 gate — cleared.** PR #159's review surfaced two HIGH/MEDIUM-severity defects in the poller/recompute lifecycle that M6's tools (`trigger_recompute` and friends) would otherwise build directly on top of. All three were fixed and merged in PR #167 (2026-07-30):
- **#160** (HIGH, closed) — a derived-edge recompute failure permanently kills the background poller (regression against M4-C's poller-resilience work)
- **#161** (MEDIUM, closed) — `POST /graph/recompute`'s fire-and-forget task can be garbage-collected mid-flight
- **#162** (MEDIUM, closed) — `GraphService.close()` can block the entire event loop during shutdown if a recompute is mid-flight

PR #167's adversarial review (Gemini 3.1 Pro) surfaced a further, pre-existing defect adjacent to this code path — **#168** (bug, closed): `GraphService.recompute_derived_edges` didn't hold `_conn_lock` across its full multi-statement body, unlike `restore_data`'s established #124 precedent, creating a segfault-risk race if `close()` interleaved mid-recompute. Fixed in PR #183 (2026-08-08) — `recompute_derived_edges` now holds the lock for its full body, matching `restore_data`'s pattern.

**PR #183 (2026-08-08)** closed out #168, #172, and #174 (which turned out to share a root cause with #172 — see above), plus fixes surfaced by two rounds of Opus review and Gemini adversarial passes on this branch: a strengthened, verified-red-fails-without-the-fix regression test for #168's lock; the remaining #172 migration gap (pre-existing Raindrop targets with a stored string `collection_id` now coerce correctly at delivery time too, not just at creation); and event-loop-blocking mitigation (synchronous `graph.*` calls in `poller.py`'s async methods and `share.py`'s `share_item` now route through `asyncio.to_thread`, since #168's fix widened `_conn_lock`'s hold time across the whole recompute). Also directly verified Kuzu's actual concurrency model against the installed version (0.11.3) rather than assuming it — multiple `Connection`s per `Database` are supported, only one write transaction is allowed system-wide at a time, but reads from another connection succeed concurrently with an open write transaction elsewhere — informing **#184**, a follow-up architecture item (connection-pool redesign) not attempted in that PR. Six further findings from that review round filed as individual issues: **#185** (pre-existing `_redact_target` crash on a null config), **#186** (webhook PATCH omitting `secret` silently disables HMAC signing), **#187/#188** (share-target config: unknown keys silently dropped, webhook URL silently normalised), **#189** (422 error detail leaks raw Pydantic validation text), **#190** (audit of sibling `graph.py` methods sharing #168's original unguarded-multi-statement pattern).

**PR #199 (2026-08-08, M5 sub-project 4)** closed out issue #99 by deletion (the fragile `ORDER BY` on an unprojected relationship alias in `get_topic`'s embedded items preview no longer exists — the preview itself was replaced by a `related` field). Two Opus reviews plus a Gemini adversarial pass on that review round found and fixed one MEDIUM in-PR (`decode_cursor` didn't catch `RecursionError` on a deeply-nested crafted cursor, producing an uncaught 500 — both Opus reviews initially called it deferrable/pre-existing, Gemini pushed for a fix now since this PR now owns the fix location; fixed, covers all three cursor-codec consumers). Four further findings filed as follow-ups: **#200** (bug — cursor pagination loops forever when an item's `published_at`/`fetched_at` are both NULL, pre-existing across three call sites, reachable via a backup restore missing `fetched_at`; Gemini escalated this from "defer" to a higher-priority operational risk, but both Opus reviews' read that it's genuinely pre-existing still stands, so it's filed not fixed), **#201** (`/topics/{id}/items` doesn't implement its documented "filterable" contract), **#202** (`/topics/{id}/related` silently truncates at 20 with no client-visible signal — note this revisits a deliberate, already-adversarially-reviewed design call from the original spec, not an oversight), **#203** (batched consistency findings: `topic_exists` duplicates an existing `_exists` helper, inconsistent 404-costing pattern vs. sub-project 1's endpoints, unhandled 500s bypass the error envelope contract).

Also fixed this session: **#182** (untracked high-severity Dependabot alert on `cryptography`, resolved via dependency bump), **#154** (closed — already fixed in PR #178, issue had never been closed), and a full Dependabot backlog sweep (7 open PRs merged or resolved down to 1 genuine conflict requiring a coordinated `vite`+`@vitejs/plugin-vue` bump, fixed directly in PR #197).

**M6 scope** (per `docs/roadmap/milestones.md`): full MCP server via FastMCP, all 21 tools from `docs/architecture/mcp-server.md` (feed tools, item tools, graph traversal, export, config), stdio transport (Claude Desktop, Cursor) and HTTP/SSE transport (networked/remote clients), auth via `REED_API_KEY` on both. Done means a complete reading session conducted entirely through Claude Desktop — browse, read, traverse via graph, annotate, mark read — zero UI. Not yet specced — starts with `/brainstorming` per the mandatory Superpowers workflow below.

Active session plan: M5 is fully complete. M6 (MCP server) is next and unblocked — its gate was cleared back in PR #167/#183. **Before starting new build work, review the open-issue backlog (68 as of 2026-08-08) — Simon flagged it's growing long and wants to make sure tech-debt isn't compounding faster than it's resolved.** Simon's call on ordering. See Expiry for the refresh trigger on this subsection.

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
│   ├── mcp_server.py           ← FastMCP server and tool definitions
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
│   ├── data.py                  ← /api/v1/data (export, backup, restore)
│   ├── opml.py                  ← /api/v1/opml (import/export)
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
│   │   └── specs/                 ← Implementation specs (written by /writing-plans)
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

The live list of unresolved design questions is at `docs/roadmap/open-decisions.md`. Check it before starting work on M5 (share targets, API completion) or M6 (MCP server). The resolved decisions log is in the same file.

## Precedence

This file is authoritative for all work in this repo — no parent CLAUDE.md exists inside it. Global `~/.claude/CLAUDE.md` DOCTRINE and preferences apply where not overridden here; this file overrides the global defaults on repo-specific technical and process matters regardless of recency.

Two specific overrides worth naming: this file pins exact model IDs (e.g. Sonnet 4.6, Opus 4.8) for repo workflows rather than the global tier-only routing, and it makes the Superpowers methodology (brainstorming → plan → TDD → verify → finish) mandatory for this repo even where the global default is lighter-weight.

## Instructions

### Conventions

- **Response envelope.** Success responses are `{"data": ..., "meta": ...}`; errors are `{"error": {"code": ..., "message": ..., "detail": ...}}`. Established in M2.
- **Primary keys.** `Feed` is keyed by `url`, `Item` by `guid` (natural keys). Each also carries a UUID `id` used as the public/API identifier. Kuzu indexes only the primary key, and the natural keys are the ingestion hot path and enforce feed/item dedup, so they stay as PKs; UUID lookups table-scan, which is negligible at single-user scale. This resolves the primary-key portion of issue #31 as a deliberate won't-fix.
- **Graph schema.** The authoritative current schema is in `ARCHITECTURE.md`; the DDL lives in `src/reed/graph.py` `_init_schema`, versioned by `_SCHEMA_VERSION` with registered per-version steps in `_migrate`.
- **Branch naming.** `feat/`, `fix/`, `docs/`, `chore/`.
- **Model routing.** Apply these consistently — the right model for the task is not optional.

  | Task | Model | How |
  |---|---|---|
  | Default — implementation, refactoring, debugging, file edits | Sonnet 4.6 | Default session model — no change needed |
  | `/brainstorming` | Sonnet 4.6, max thinking budget | Simon confirms before brainstorming begins |
  | `/code-review` | Opus 4.8 | Simon runs manually: `claude --model claude-opus-4-8` |
  | `/security-review` | Opus 4.8 | Simon runs manually: `claude --model claude-opus-4-8` |
  | Adversarial review (see Commands) | Gemini 3.1 Pro (High) via `agy` | Run by the assistant after brainstorming and after reviews |

- **Keep "Current status" current.** Update the milestone/phase table and active session plan in Scope whenever a milestone phase completes or the plan changes. Do not let it drift.

### Commands

- **Superpowers methodology — mandatory for all new features or significant changes.** The `superpowers@claude-plugins-official` plugin is installed; do not skip any hard gate without explicit instruction from Simon.
  1. `/brainstorming` — before any implementation. No code until a design is presented and approved. Run the adversarial review workflow (below) on the output before seeking Simon's approval.
  2. `/writing-plans` — immediately after brainstorming approval. Implementation plan written to `docs/superpowers/specs/` before coding begins. Note: `docs/superpowers/` is gitignored — specs live on disk for reference during implementation but are not committed to git.
  3. `/test-driven-development` — mandatory for all implementation. No production code without a failing test first. Delete code written before tests and start over — no exceptions.
  4. `/verification-before-completion` — before marking any task done. All tests pass, output is clean, behaviour matches the spec.
  5. `/finishing-a-development-branch` — before raising a PR.

  **For bug fixes:** write the failing test that reproduces the bug first, then fix. No exception.

  **For exploration or prototyping:** throwaway spikes are exempt from TDD but must be deleted before any production implementation begins. Do not adapt spike code — implement fresh from tests.

- **After implementing any feature or fix:**
  - Run `/simplify` if the new code has obvious duplication, verbosity, or abstraction opportunities.
  - Run `/verify` to confirm the expected behaviour in a live context (not just that tests pass).

- **Before any PR:**
  - Run `/code-review` on the branch diff — mandatory for every PR. Simon runs this manually on Opus 4.8.
  - Run `/security-review` if the change touches any of: auth (`api/deps.py`, `X-API-Key` handling, any new endpoint), external HTTP (poller fetch, feed subscription), Kuzu write paths (`graph.py` mutations), config or environment variable handling, or file I/O / data export/import.
  - After each review, run the adversarial review workflow (below) before presenting findings to Simon.
  - All work happens on a feature branch; PR into `main` — never commit directly to `main`.

- **Adversarial review workflow.** Two outputs require a Gemini pass before Simon approves them: brainstorming proposals (after `/brainstorming`, before approval) and review findings (after `/code-review` or `/security-review`, before Simon acts on them).

  Run:
  ```bash
  agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions --print-timeout 10m -p "<prompt>"
  ```
  Construct the prompt with: brief project context (Reed is a self-hosted RSS reader; the component under review), the full Claude output (proposal or findings), and the instruction "You are an adversarial reviewer. Identify gaps, risks, missed cases, or alternative perspectives. What did Claude miss or get wrong?"

  Then present Simon with: Claude's output, Gemini's adversarial review (verbatim key points, attributed), and a one-paragraph synthesis of where they agree, where they diverge, and what the divergence means. Wait for Simon's explicit approval or amendment before proceeding.

- **After any review (code-review or security-review):**
  - For every finding, create a GitHub issue in `simonives/reed`.
  - Apply labels by finding type: `bug` (correctness), `security`, `performance`, `tech-debt`.
  - Issue title format: `<type>: <short description>` — e.g. `bug: create_item orphans items on resubscription`.
  - Issue body must include: affected file(s) and line numbers, description of the problem, the exploit or failure scenario, and the recommended fix.

## Negatives

- **Do not skip a Superpowers hard gate** (brainstorming, writing-plans, TDD, verification, finishing-a-branch) **without explicit instruction from Simon** in that session. There is no standing exception — only Simon can waive a gate, and only in the moment.
- **Do not write production code before a failing test exists**, except for throwaway exploration spikes — and those must be deleted before production implementation begins; do not adapt spike code into the real implementation.
- **Do not commit directly to `main`.** All work goes through a feature branch and a PR.
- **Do not run `/code-review` or `/security-review` yourself.** Both are run manually by Simon on Opus 4.8 — open the PR and prompt him to run them rather than attempting to run them yourself.
- **Do not merge a Gemini adversarial concern into your own output silently.** Surface it explicitly alongside your synthesis and wait for Simon's call.
- **Do not batch multiple review findings into one GitHub issue** — one finding, one issue. Exception: a finding already fixed within the same PR does not need an issue at all.
- **Do not call Kuzu from anywhere except `graph.py`** (the single seam rule) — API routers, MCP server, and poller must go through it.

## Expiry

- Milestone/phase status table and active session plan (Scope → Current status) — owner: Simon, last-verified: 2026-08-07, refresh interval: on every milestone phase completion or change of active session plan (check every session, per the mandatory read-first instruction).
- Pinned model versions (Sonnet 4.6, Opus 4.8, Gemini 3.1 Pro (High)) — owner: Simon, last-verified: 2026-07-25, refresh interval: whenever a named model is superseded or Simon changes routing.
- Issue #31 reference (primary-key won't-fix) — stable design decision, not perishable; no refresh trigger.
