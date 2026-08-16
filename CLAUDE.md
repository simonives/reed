# Reed — Claude Context

## Scope

Reed is a self-hosted, open-source RSS reader with a graph-native data model, a public REST API, and a first-class MCP server. Single-user. AGPL-3.0-or-later licence.

**Read the "Current status" subsection in full at the start of every session.** The project is complex and carries significant context across milestones — do not rely on memory of a previous session; verify current state there first.

**Current status**

Current milestone: **M6 — MCP server (complete)**. Starting **M7 — v1.0.0** next.

| Milestone | Name | Status |
|---|---|---|
| M0 | Foundation | Complete |
| M1 | Walking skeleton | Complete |
| M2 | Usable reader | Complete |
| M3 | Migration-ready | Complete |
| M4 | Graph alive | Complete (derived edges + graph query endpoints deliberately deferred to M5 sub-project 1 — see below) |
| M5 | API and integrations complete | Complete — all four sub-projects merged (2026-08-08) |
| M6 | MCP server | **Complete** — merged (PR #229, 2026-08-10) |
| M7 | v1.0.0 | **In progress** — see below |

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

**M6 — complete (PR #229, merged 2026-08-10).** Full MCP server via FastMCP: 27 tools (grew from the originally-scoped 21 as the design settled — feed, item, graph traversal, discovery, research, export, config tools), a `reed://graph/overview` resource, and three guided-workflow prompts (`deep_reading_session`, `weekly_digest`, `research_thread`). Both stdio (Claude Desktop, Cursor, via `reed.mcp:main`) and HTTP transports, auth via `REED_API_KEY`/`X-API-Key` on both. Built via Subagent-Driven Development across 13 tasks specced in `docs/superpowers/specs/2026-08-09-m6-mcp-server-design.md` and `docs/superpowers/plans/2026-08-09-m6-mcp-server.md` (gitignored — reference locally), each with a task-scoped review, followed by a whole-branch review and one consolidated fix wave. New backend capability added along the way: `find_connection_path` (graph traversal between items/topics via ABOUT/RELATED_TO), topic centrality (PageRank) and clustering (Louvain) over Kuzu's `algo` extension, `append_note`, `get_topic_by_name`. 19 follow-up issues filed from the whole-branch review (#207–#226) plus 2 from the final re-review (#227, #228) — none block merge, all deferred tech-debt/doc-gap/nit-level. A genuine ~2.6x PageRank directional bias from `RELATED_TO`'s arbitrary canonical edge direction was investigated, found to have no clean fix in the installed Kuzu version without a schema-level rewrite, and documented-and-deferred rather than silently shipped or withheld (issue #206). Four new design questions were also raised and deliberately deferred during M6 brainstorming, logged in `docs/roadmap/open-decisions.md`: author node/co-authorship, saved/named graph traversal views, manual item capture from an external URL, and a scheduled AI web-scanning/discovery feature (issue #205, explicitly scoped as post-v1.0.0, needs its own future milestone and brainstorming pass).

**Not yet done:** a live Claude Desktop reading session through the stdio bridge — the milestone's own "done means a complete reading session conducted entirely through Claude Desktop, zero UI" criterion — requires an actual Claude Desktop client and could not be performed in the agent environment that built M6. Simon should verify this manually before treating M6 as fully proven end-to-end, though the branch itself is merged and CI-green.

**M7 — in progress.** Decomposed into four sub-projects (same pattern as M5):

| Sub-project | Scope | Status |
|---|---|---|
| 1. Distribution & SBOM | Fix and verify the never-fired `release.yml` release pipeline (GHCR, PyPI, both SBOMs), safely via a `workflow_dispatch` dry-run mechanism | **Complete and merged** (PR #255, 2026-08-16) — 9 SDD tasks (found and fixed 4 real bugs via live dry-run testing: Python version mismatch, invalid `cyclonedx-py` flag, missing CI-time dependency, unsanitized `github.ref_name` in filenames), then a fresh whole-branch review (Opus, adversarially checked by Gemini 3.1 Pro — the earlier informal review's findings were never persisted to disk, so this one started clean) found and fixed 5 more: a publish gate that could push to PyPI from an arbitrary branch on `workflow_dispatch`, a shell-injection-prone `github.ref_name` interpolation, two workflow tests that passed with their guarded logic inverted, and a `docker compose` test that false-reds for anyone following the README's own quickstart. All 5 fixes mutation-tested (revert → red → restore → green). A 6th finding (`lxml[html-clean]`'s version floor) was investigated, found to be based on an inverted premise, and discarded after direct verification (downloaded lxml 5.1.0, confirmed `lxml/html/clean.py` ships natively below 5.2.0). 5 more findings deferred as follow-ups: **#250** (tag/version consistency check), **#251** (SBOM overstates dependency surface by ~1/3 — describes the CI dev environment, not the shipped artifact), **#252** (application SBOM never uploaded as an artifact, so a dry run can't verify it), **#253** (third-party actions pinned by mutable tag, not SHA), **#254** (job holds write/id-token permissions during untrusted dependency install — needs Simon's explicit call, conflicts with the original no-restructure constraint). None of these five block a real release; land before v1.0.0 goes public. **Still no real `v*.*.*` tag has ever been pushed** — the pipeline is fixed and dry-run-verified, not yet exercised for real. |
| 2. Documentation completeness | README real quickstart, CHANGELOG backfill, ARCHITECTURE.md/AGENTS.md/GEMINI.md accuracy pass, employer-reference removal | **Complete and merged** (PR #249, 2026-08-16) — a full read-through found and fixed a stale README placeholder, a pre-M4 ARCHITECTURE.md graph model, AGENTS.md/GEMINI.md frozen at M4, an empty CHANGELOG, a hardcoded `docker-compose.yml` API key default, and two places naming a real employer/committee in mockup content. `CONTRIBUTING.md`/`CODE_OF_CONDUCT.md` reviewed and found already accurate, no changes needed. Follow-up filed: **#248** (verify `SIMILAR_TO` populates once the recompute gate opens post-#241 fix) |
| 3. Website | VitePress site content (hero/features copy exists; body explicitly marked "coming in v1.0.0"), GitHub Pages live via `pages.yml` | Not started |
| 4. Repository | Make repo public, real `v1.0.0` tag, GitHub Release | Not started — gated on sub-projects 1-3, plus Simon's Claude Desktop verification (above) and the go-live gate below |

**RC1 — a personal-use checkpoint Simon introduced 2026-08-15, separate from and prerequisite to the public v1.0.0 release.** Built and run locally (`docker build`, not the unfinished release pipeline — RC1 never depended on sub-project 1). Confirmed working end-to-end against a real 52-feed/4,751-item personal OPML import (feeds, items, search, topics, MCP tools all live-tested), running at `~/reed-local/` outside any git worktree so it survives branch cleanup. **RC1's only known blocker, issue #241, is now fixed and merged (below) — RC1 is stable for daily personal use.** Next step is Simon rebuilding the local image off current `main` and validating the fix against his real database (see #241's own note on this).

**Issue #241 — CLOSED, merged 2026-08-16 (PR #247).** `SIMILAR_TO` derived-edge recompute had unbounded combinatorial blowup from corpus-dominant topics — found live during RC1 dogfooding (15+ minutes, 6.6GB+ memory, 87% of a 7.66GB container limit, on the real 4,751-item personal library, ending in an ungraceful SIGKILL). Root cause confirmed by direct read-only query of the live database: one topic, `"hosted on acast"` (podcast hosting-platform boilerplate repeated on every episode of one feed), `item_count=1444`, alone accounted for 88.7% of the join's combinatorial cost. Fix: exclude any topic exceeding both a percentage-of-corpus threshold (`similarity_max_topic_share`, default 5%) and an absolute floor (`similarity_topic_share_floor`, default 50) from `SIMILAR_TO`'s computation, applied consistently across all 6 points either the MERGE or sweep statement touches a Topic node — `RELATED_TO` untouched (unaffected by the defect; its join is bounded by YAKE's fixed keyword cap). Full `/brainstorming` → spec → plan → Subagent-Driven Development cycle: 3 tasks, one fix round (a task reviewer caught a real test-design flaw — the original sweep-consistency test used symmetric data that couldn't distinguish "filter applied" from "filter ignored," fixed and independently re-verified by two reviewers), final whole-branch review (Opus) did further independent mutation testing and returned "ready to merge: yes." Full suite: 602 passed, 2 skipped. 4 non-blocking follow-ups filed: **#243** (sweep filter points lack individual mutation coverage — code correct, test-coverage gap), **#244** (`Topic.item_count` never decremented on deletion, pre-existing bug now more consequential since the cap depends on it), **#245** (cap scales quadratically with corpus size, no absolute ceiling — irrelevant at current scale), **#246** (cap's percentage denominator is the whole corpus, not the join's own time window — residual edge case). **Not yet done:** Simon validating the fix's actual wall-clock/memory improvement against his real RC1 database — the spec's predicted 89% cost reduction is unvalidated end-to-end, since the test suite can only prove correctness, not the real-world performance win.

**Issue #242 (priority, blocks public v1.0.0, does NOT block RC1) — single-key auth model needs review for public cloud hosting.** Raised by Simon while planning v1.0.0: `ARCHITECTURE.md` already commits to one-click Railway/Render/Fly.io deployment as a target, but the current auth model (single static `X-API-Key`, empty key = silent open-access "dev mode") was reasoned about for a LAN-bound self-hosted threat model, not a public-internet-reachable one. Concrete gaps identified (not yet solutioned, needs its own dedicated `/brainstorming` session per the same pattern as #241): silent open access on a misconfigured public deploy, no rate-limiting/brute-force protection, TLS/HTTPS requirement undocumented, M6 security review's DNS-rebinding reasoning needs revisiting for the internet-exposed case, and `fly.toml`/`render.yaml` are promised in `ARCHITECTURE.md` but don't exist.

Active session plan: two-tier punch list, agreed with Simon 2026-08-15 — **RC1 bar: cleared and validated** (#241 fixed and merged; Simon rebuilt the local RC1 image off current `main` and confirmed live against his real ~4,750-item library — CPU/memory settled to idle well within minutes, no repeat of the old 15-minute/6.6GB crisis). **v1.0.0 public bar:** M7 sub-projects 1 (distribution/SBOM) and 2 (documentation) now complete; sub-projects 3 (website) and 4 (public repository launch) remain, plus resolving #242 (auth model for public cloud hosting). Next up per Simon's direction (2026-08-16): a full open-issue backlog review, to catch anything high-priority or blocking before more net-new build work — backlog was 103 as of 2026-08-15, now +10 net (+4 from #241's follow-ups, +1 from #248, +5 from sub-project 1's final review — #250-254). See Expiry for the refresh trigger on this subsection.

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

- Milestone/phase status table and active session plan (Scope → Current status) — owner: Simon, last-verified: 2026-08-16, refresh interval: on every milestone phase completion or change of active session plan (check every session, per the mandatory read-first instruction).
- Pinned model versions (Sonnet 4.6, Opus 4.8, Gemini 3.1 Pro (High)) — owner: Simon, last-verified: 2026-07-25, refresh interval: whenever a named model is superseded or Simon changes routing.
- Issue #31 reference (primary-key won't-fix) — stable design decision, not perishable; no refresh trigger.
