# Reed — Architecture

> A self-hosted, open-source RSS reader with a graph-native data model, a public REST API, and a first-class MCP server.

---

## Design principles

1. **Single-user, self-hosted.** Reed runs for one person on hardware they control. There is no multi-tenancy, no cloud service, no SaaS model. This constraint simplifies almost every decision.
2. **API-first.** The web UI consumes the same public REST API available to any client. The API is a first-class deliverable, not an afterthought.
3. **Graph-native.** Relationships between feeds, items, topics, authors, and tags are first-class data, not derived from joins at query time.
4. **MCP as a primary interface.** The MCP server is built alongside the API, not bolted on. AI clients traversing the graph are an expected and supported use case.
5. **Zero operational overhead.** No database server to run, no message broker, no external services. The data layer is an embedded file. `docker-compose up` is the entire deployment.
6. **Open source, copyleft licensed.** AGPL v3. Anyone can download, run, fork, and contribute. Commercial SaaS use of Reed's code requires contributing back.

---

## Technology decisions

| Concern | Decision | Rationale |
|---|---|---|
| Language | Python | First-class Kuzu bindings; FastMCP is Python-native; FastAPI for REST; one language across all components |
| Data store | Kuzu | Embedded graph DB (no server process); Cypher query language; Apache 2.0; the SQLite of graph databases |
| REST framework | FastAPI | Automatic OpenAPI/Swagger docs; async-native; Pydantic validation |
| MCP server | FastMCP | Python-native; minimal boilerplate; matches the application language |
| Web UI | Vue 3 + Vite | Three-pane layout and keyboard shortcuts require client-side reactive state; Vue 3 Composition API is natural for Python developers; best-documented FastAPI pairing |
| Packaging | Docker Compose + GitHub source | Docker is the self-hosting standard for this audience; source available for contributors and alternative deployments |
| Container registry | GitHub Container Registry (GHCR) | Co-located with source; free for public images |
| Auth | API key (single-user) | Single-user context makes OAuth unnecessary; a static key in environment config is sufficient |

---

## Graph data model

### Nodes

| Node | Properties |
|---|---|
| `Feed` | `url` (PK), `id`, `title`, `display_name`, `description`, `site_url`, `poll_interval_minutes`, `reader_mode_enabled`, `is_active`, `subscribed_at`, `last_fetched_at`, `consecutive_errors`, `last_error`, `etag`, `last_modified` |
| `Item` | `guid` (PK), `id`, `url`, `title`, `summary`, `content`, `author`, `word_count`, `published_at`, `fetched_at`, `read`, `starred`, `reader_content`, `reader_fetched_at` |
| `Tag` | `name` (PK, user-defined), `id` (UUID) |
| `Note` | `id` (PK), `body`, `created_at`, `updated_at` |
| `Config` | `key` (PK), `value` |

`author` is stored as a flat `Item.author` string; there is no `Author` node. `Topic` and its derived edges are future work (see below).

### Edges

| Edge | Direction | Description |
|---|---|---|
| `HAS_ITEM` | Feed → Item | An item belongs to a feed |
| `HAS_NOTE` | Item → Note | An item's user note (1:1) |
| `TAGGED` | Item → Tag | User-applied tag on an item |
| `FEED_TAGGED` | Feed → Tag | User-applied tag on a feed |

#### Future (derived graph)

The following edges are not yet implemented. They represent planned AI-assisted enrichment once the core graph is stable:

| Edge | Direction | Description |
|---|---|---|
| `ABOUT` | Item → Topic | Topic extracted from item content |
| `RELATED_TO` | Topic → Topic | Topics co-occurring across items (inferred) |
| `SIMILAR_TO` | Item → Item | Items sharing topic nodes (inferred) |

When implemented, these derived edges will make traversal from an MCP client genuinely useful: hop from an item to its topics, to related topics, to related items across different feeds.

### Schema conventions

**Response envelope.** REST responses use a `{ "data": ..., "meta": ... }` envelope on success and `{ "error": { "code": ..., "message": ..., "detail": ... } }` on error. Established in M2.

**Primary keys.** `Feed` is keyed by `url` and `Item` by `guid` (natural keys); each also carries a UUID `id` that is the public/API identifier. Kuzu builds a hash index only on the primary key, and the natural keys are the ingestion hot path (the poller matches feeds by `url` and items by `guid` on every poll) and the enforcement point for feed/item deduplication. UUID `id` lookups table-scan, which is negligible at single-user scale. Switching to UUID primary keys (issue #31) is a deliberate won't-fix, recorded here to close the question.

---

## Component architecture

```
┌─────────────────────────────────────────────────────┐
│                     Reed Container                  │
│                                                     │
│  ┌─────────────┐   ┌─────────────┐                 │
│  │   Web UI    │   │  MCP Server │                 │
│  │  (Vue 3 +   │   │  (FastMCP)  │                 │
│  │   Vite,     │   │             │                 │
│  │   static)   │   └──────┬──────┘                 │
│  └──────┬──────┘          │                        │
│         │                 │                        │
│  ┌──────▼─────────────────▼──────┐                 │
│  │          REST API             │                 │
│  │          (FastAPI)            │                 │
│  └──────────────┬────────────────┘                 │
│                 │                                  │
│  ┌──────────────▼────────────────┐                 │
│  │        Graph Service          │                 │
│  │   (Kuzu query + write layer)  │                 │
│  └──────────────┬────────────────┘                 │
│                 │                                  │
│  ┌──────────────▼────────────────┐                 │
│  │       Kuzu Graph DB           │                 │
│  │       (embedded file)         │                 │
│  └───────────────────────────────┘                 │
│                                                     │
│  ┌───────────────────────────────┐                 │
│  │       Feed Poller             │                 │
│  │  (background worker, async)   │                 │
│  │  Reads: Feed nodes (due)      │                 │
│  │  Writes: Item nodes + edges   │                 │
│  └───────────────────────────────┘                 │
│                                                     │
└─────────────────────────────────────────────────────┘
         │
         ▼
  /data/reed.kuzu   ← mounted volume (persists outside container)
```

### Components

**REST API (FastAPI)**
The primary interface. Serves the web UI, handles all CRUD for feeds and items, exposes read state and search. OpenAPI docs available at `/docs`. All endpoints require the configured API key (passed as a header).

**MCP Server (FastMCP)**
Runs alongside the API in the same process. Exposes graph traversal tools to any MCP-compatible AI client. Tool surface includes: read feeds, read items, traverse topics, find related items, search by keyword, mark read/starred.

**Graph Service**
A Python module wrapping all Kuzu interactions. The API and MCP server both import this — neither touches Kuzu directly. This is the single seam between the application logic and the data layer.

**Feed Poller**
An async background worker (asyncio) that runs inside the same container. On startup, it schedules polls for all registered feeds based on `poll_interval_minutes`. On each poll: fetches the feed URL (honouring ETag and Last-Modified for conditional GET), parses items, writes new `Item` nodes and edges to the graph, updates `Feed` poll metadata.

**Web UI (Vue 3 + Vite)**
A Vue 3 single-page application built with Vite, served as static files from the FastAPI container. Pinia manages shared state (active feed, selected item, read/starred tracking). The app consumes `/api/v1/` exclusively — no server-rendered HTML. Vite's multi-stage Docker build produces a `dist/` bundle mounted at the container root. The three-pane layout, keyboard shortcuts, and scroll-based read tracking require client-side reactive state; this is the model they are native to. See `ADR-008`.

---

## Self-hosting model

### Docker Compose (primary)

```yaml
services:
  reed:
    image: ghcr.io/simonives/reed:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      REED_API_KEY: "your-key-here"
      REED_DATA_PATH: "/data/reed.kuzu"
      REED_POLL_DEFAULT_INTERVAL: "60"
```

`docker-compose up` is the complete deployment. The Kuzu database file lives in the mounted `./data` volume and persists across container restarts and upgrades.

### From source

```bash
git clone https://github.com/simonives/reed
cd reed
pip install -e .
reed serve
```

No external services required. Kuzu is an embedded dependency — it installs with the Python package.

### One-click cloud targets

The Docker image deploys without modification to Railway, Render, Fly.io, and any platform supporting Docker. A `fly.toml` and `render.yaml` will be provided in the repository.

---

## API design

- Base path: `/api/v1/`
- Authentication: `X-API-Key` header
- Format: JSON
- Docs: `/docs` (Swagger UI, auto-generated from FastAPI)

Core resource groups:
- `/feeds` — subscribe, list, refresh, delete
- `/items` — list (with filters), read state, starred state
- `/tags` — list, apply, remove
- `/topics` — list, traverse
- `/search` — full-text and graph-aware search
- `/graph` — raw graph traversal endpoints (for power users and MCP)

---

## MCP server design

The MCP server exposes the graph as a set of tools an AI client can call in sequence to traverse and reason over reading history.

Initial tool surface:
- `list_feeds` — all subscribed feeds with metadata
- `get_feed_items` — items from a feed, with filters (unread, starred, date range)
- `get_item` — full content of a single item
- `get_topics` — all topics in the graph
- `traverse_topic` — items and related topics connected to a given topic node
- `find_related_items` — items similar to a given item (via shared topic edges)
- `search` — keyword search across item titles and content
- `mark_read` / `mark_starred` — write operations from the AI client

The traversal tools are the differentiator. An AI client can hop: item → topics → related topics → related items across different feeds. This is the use case that justifies the graph model.

---

## Open decisions

See `docs/roadmap/open-decisions.md` for the live list of unresolved decisions and `docs/roadmap/open-decisions.md#resolved-decisions` for the full resolution log.
