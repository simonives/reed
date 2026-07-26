# Milestones

Reed is developed milestone by milestone, each leaving the project in a genuinely usable state. Milestones have no fixed dates — scope is the commitment, not time.

---

## Dependency map

Not all milestones are sequential. M2 and M3 can run concurrently after M1. M5 and M6 can run concurrently after M4.

```
M0 ──► M1 ──► M2 ──────────────────────────► M4 ──► M5 ──┐
               │                                           ├──► M6 ──► M7
               └──► M3 ──────────────────────────────────► ┘
                    (concurrent with M2)          (M5 + M6 concurrent)
```

**M0 → M1:** Strict. Project must be scaffolded and buildable before any feature work.

**M1 → M2 and M3:** Both depend on M1. Independent of each other — different layers of the stack, separately ownable workstreams.

**M2 + M3 → M4:** Graph features require items flowing through the system and the reading experience to validate against. M3 completion is not strictly required for M4, but completing both first gives a solid base.

**M4 → M5 + M6:** Graph service layer must exist before graph API endpoints and MCP tools can be implemented. M5 and M6 share the same graph service layer — they are parallel workstreams once M4 is complete.

**M5 + M6 → M7:** Nothing is released until all milestones are complete.

---

## Development timeline

Phases are relative effort units — not weeks or sprints. No date commitments.

```
              Ph1    Ph2    Ph3    Ph4    Ph5    Ph6    Ph7    Ph8
                                                                   
M0 Foundation [====]                                               
                                                                   
M1 Skeleton          [====]                                        
                                                                   
M2 UI/Reader                [============]                         
M3 Migration                [============]   <- concurrent with M2 
                                                                   
M4 Graph                                   [============]          
                                                                   
M5 API/Integ                                            [========] 
M6 MCP Server                                           [========] <- concurrent with M5
                                                                   
M7 v1.0.0                                                          [==]
```

---

## M0 — Foundation

**Status:** In progress (this document is the final piece)

Design documentation is complete and the project is buildable. No working features, but every architectural decision is made and recorded.

### Scope

- All design documents complete (ADRs, architecture specs, user patterns, wireframes, milestones)
- `pyproject.toml` with declared dependencies
- `src/reed/` project structure scaffolded
- `Dockerfile` and `docker-compose.yml` in place
- Kuzu schema DDL and migration runner
- GitHub Actions CI pipeline (lint, type check, test runner)
- All open decisions in `docs/roadmap/open-decisions.md` resolved

### Done means

`docker-compose up` starts Reed without errors. No features work, but the project builds, the schema initialises, and CI passes.

---

## M1 — Walking skeleton

The thinnest possible end-to-end slice. Proves that Kuzu, FastAPI, and the async feed poller work together correctly before building on top of them.

### Scope

- Subscribe to a feed via `POST /api/v1/feeds`
- Async poller starts on application launch, polls due feeds on schedule
- Conditional GET (ETag, Last-Modified) implemented
- New items written to Kuzu as `Item` nodes with `HAS_ITEM` edges
- `GET /api/v1/feeds` and `GET /api/v1/items` return correct JSON
- Interactive API docs available at `/docs` (Swagger UI)
- Authentication (`X-API-Key` header) enforced on all endpoints
- No web UI — the `/docs` interface is sufficient for this milestone

### Done means

`docker-compose up`, subscribe to a feed via the API, wait for a poll cycle, and items appear in `GET /api/v1/items`. The full data path from remote feed to Kuzu to API response is verified end-to-end.

---

## M2 — Usable reader

The point where Reed becomes a daily driver. This milestone is the migration-from-Feedly experience for the reading side. Concurrent with M3 after M1.

### Scope

**Web UI**
- Three-pane layout: feed list / item list / reading pane (default)
- River of news single-stream layout (user preference)
- Responsive baseline — readable on mobile

**Reading experience**
- Full article content with reader mode (trafilatura extraction)
- Keyboard shortcuts: j/k navigate, space scroll, m mark read, s star, o open, n note, / search, ? help
- Mark read on open (configurable)
- Catch-up: mark all read for a feed or before a date
- Views: all items, unread, starred, by feed, by tag

**Feed management**
- Add feed — direct URL entry
- Add feed — website URL with automatic feed discovery
- Feed settings drawer: display name, poll interval, reader mode, active/paused, tags
- Remove feed (retains read and starred items)

**Interaction**
- Notes / annotations — create, edit, delete inline below article
- Tags — apply and remove on items
- Dark mode (system, light, dark)
- CSS variable customisation in Settings — Appearance (accent colour, font size, reading width, line height, reading font)

**Settings**
- General: poll interval, reader mode, items per page, mark read on open, layout
- Appearance: theme and CSS variables
- API key display

### Done means

A complete daily reading session — open Reed, scan unread items, read articles, mark read, star items, add a note — conducted entirely within the Reed UI without touching another reader.

---

## M3 — Migration-ready

Makes Reed a viable destination for users coming from Feedly, Inoreader, or any other RSS reader. Concurrent with M2 after M1.

### Scope

**OPML**
- Import: parse OPML, preview feeds with folder → tag mapping, bulk subscribe
- Export: generate OPML from current subscriptions (tags → folders)

**Data portability**
- Full JSON data export: feeds, item metadata, read/starred state, notes, tags
- Instance backup: complete portable archive for migrating to a new server
- Instance restore: import backup to a fresh instance (with destructive-action confirmation)

**Search**
- Full-text search across item titles, content, and notes (Kuzu FTS)
- Filters: unread, starred, feed, date range
- Results with match excerpts

**Settings**
- Export section: OPML download, JSON export, instance backup (async for large libraries)
- Import section: OPML upload, instance restore

### Done means

Export an OPML file from Feedly, import it into Reed, and have all feeds subscribed and items polling within one session. Search across the accumulated library and find relevant items by keyword.

---

## M4 — Graph alive

The differentiating layer. This is what makes Reed something other RSS readers are not.

**Note (2026-07-25):** the "Derived edges" and "Graph API endpoints" scope below was deliberately deferred out of M4 during M4-A's design and now lives as M5 sub-project 1 ("Graph query endpoints" — see `CLAUDE.md`'s Current status section and `docs/superpowers/specs/2026-07-24-m5-graph-query-endpoints-design.md`). M4 as actually shipped covers Topic extraction only; treat the two subsections below as historical scope-at-time-of-writing, not a record of what M4 delivered.

### Scope

**Topic extraction**
- YAKE keyword extraction runs on every new item at poll time
- `ABOUT` edges created between items and topic nodes
- Topic deduplication (normalised name matching)
- `Topic.item_count` maintained

**Derived edges**
- `SIMILAR_TO` edges computed via Jaccard similarity on shared topics
- `RELATED_TO` edges computed via topic co-occurrence
- Scheduled recomputation job (default every 6 hours)
- `POST /api/v1/graph/recompute` triggers on-demand recomputation
- 90-day item comparison window (configurable)

**Graph UI surfaces**
- Topic tags on items (clickable)
- Topic explorer page: items by topic, related topics by weight
- More like this sidebar: opens while reading, shows similar items with shared topics
- Discover view: unread items similar to starred items (starred-adjacent)
- Feed health view: inactive feeds (30+ days) and feeds with consecutive errors

**Graph API endpoints**
- `GET /api/v1/topics` and `GET /api/v1/topics/{id}`
- `GET /api/v1/graph/similar/{item_id}`
- `GET /api/v1/graph/adjacent-to-starred`
- `GET /api/v1/graph/topic/{id}/timeline`
- `GET /api/v1/graph/feed-health`
- `POST /api/v1/graph/recompute`

### Done means

Open an article, expand the More like this sidebar, and see related items that share topics — none of which were manually tagged. Click a topic and navigate to the topic explorer to see coverage across all feeds.

---

## M5 — API and integrations complete

The full public REST API is implemented and the share sheet is live. Concurrent with M6 after M4.

### Scope

**REST API completion**
- All endpoints from `docs/architecture/api-design.md` implemented
- Full request and response validation (Pydantic models throughout)
- Cursor-based pagination on all list endpoints
- Consistent error response format across all endpoints
- OpenAPI docs complete and accurate at `/docs`

**Share sheet**
- Settings → Share targets: configure, add, edit, remove targets
- Reading view: Share button opens share sheet with configured targets
- Built-in v1 targets: Copy link, Copy as Markdown, Raindrop.io, Generic webhook
- Webhook payload delivered per spec in `docs/design/user-patterns.md`

**Notes API**
- `GET /api/v1/items/{id}/note`
- `PUT /api/v1/items/{id}/note` (create or replace)
- `DELETE /api/v1/items/{id}/note`

### Done means

Every endpoint in `docs/architecture/api-design.md` returns correct responses. A third-party tool or script can subscribe to feeds, read items, manage tags, search, export data, and trigger graph recomputation — entirely via the REST API with no UI interaction.

---

## M6 — MCP server

Reed becomes an AI-native reading tool. Concurrent with M5 after M4.

### Scope

**MCP server implementation**
- All 21 tools from `docs/architecture/mcp-server.md` implemented via FastMCP
- Tool input/output schemas matching the spec
- stdio transport for local AI clients (Claude Desktop, Cursor)
- HTTP/SSE transport for networked or remote clients
- Auth via `REED_API_KEY` on both transports

**Tool surface**
- Feed tools: `list_feeds`, `get_feed`, `subscribe_feed`, `refresh_feed`
- Item tools: `get_items`, `get_item`, `mark_read`, `mark_starred`, `tag_item`, `annotate_item`
- Graph traversal: `find_similar_items`, `find_adjacent_to_starred`, `explore_topic`, `get_author_items`, `get_topic_timeline`, `get_feed_health`, `search`
- Export: `export_opml`
- Config: `get_config`, `trigger_recompute`

**Validation**
- All three traversal patterns from `mcp-server.md` tested end-to-end against Claude Desktop:
  - Deep reading session
  - Weekly digest
  - Research thread

### Done means

A complete reading session conducted via Claude Desktop — browsing unread items, reading articles, finding related content via graph traversal, annotating items, and marking read — with no browser interaction. Zero UI, entirely through the MCP interface.

---

## M7 — v1.0.0

Public release. Reed is ready for users who are not Simon.

### Scope

**Distribution**
- Docker image built, tagged, and published to GHCR (`ghcr.io/simonives/reed:1.0.0` and `:latest`)
- `docker-compose.yml` at repository root tested on clean machine
- `pipx install reed` working (pending PyPI name availability — see open items)
- Source tarball included in GitHub Release

**SBOM**
- Application SBOM generated via `cyclonedx-bom` and attached to GitHub Release
- Container SBOM generated via Syft and attached to GitHub Release
- Both in CycloneDX JSON format

**Documentation**
- `README.md` complete with quickstart, configuration reference, and links to docs
- `CONTRIBUTING.md` complete with dev environment setup, branch/PR workflow, code conventions
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1 in full
- `CHANGELOG.md` accurate and complete for v1.0.0
- All `docs/` stubs replaced with complete content

**Website**
- GitHub Pages site (`website/`) live at `simonives.github.io/reed` (or custom domain if configured)
- Landing page complete: hero, feature highlights, quickstart, installation, community links
- VitePress site built and deployed via `pages.yml` workflow

**Repository**
- GitHub Release created with tag `v1.0.0`
- Release notes summarising v1 scope
- Repository made public

### Done means

A stranger finds the repository, follows the README quickstart, and has Reed running and reading their feeds in under 5 minutes on a clean machine.

---

## Post-v1 distribution roadmap

Additional distribution channels to be added after v1.0.0. None are blockers for release.

| Channel | Platform | Notes |
|---|---|---|
| Homebrew tap | macOS + Linux | `brew install simonives/reed/reed`. Maintenance required per release. |
| Winget | Windows | Microsoft native package manager. Submission to Winget manifest repo. |
| Scoop | Windows | Developer-focused. Simpler to publish than Winget. |
| AUR | Arch Linux | Community-maintainable. Arch users often submit their own packages. |
| `.deb` + `.rpm` | Debian/Ubuntu + Fedora/RHEL/Rocky | Built together via `fpm`. Shipped as GitHub Release artifacts. |
| PPA | Debian / Ubuntu | `add-apt-repository ppa:simonives/reed` → `apt install reed`. |
| COPR | Fedora / RHEL | `dnf copr enable simonives/reed` → `dnf install reed`. |

**Not pursuing:** Flatpak, Snap, AppImage — wrong format for a local web server application.

---

## Open items for M7

- **PyPI name:** Resolved — `reed` is taken (job search wrapper, abandoned at v0.0.4). Package name is `reed-rss`; CLI entry point remains `reed`. Update pipx install instructions to `pipx install reed-rss`.
- **GitHub repository visibility:** Repository is currently private. Set to public as part of the M7 release process, not before.
- **GitHub Pages activation:** Requires the repo to be public (free account restriction). Sequence at M7: make repo public → Settings → Pages → Source: GitHub Actions. The `pages.yml` workflow then deploys automatically on the next push touching `website/**`.
- **GitHub Pages domain:** Site will be live at `simonives.github.io/reed` by default. Decide whether to configure a custom domain before v1.0.0.
