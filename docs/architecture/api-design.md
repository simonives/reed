# API Design

Reed's REST API is a first-class deliverable. The web UI consumes it; so does the MCP server's write path; so does any automation or third-party integration a user builds. It is designed to be complete, consistent, and self-documenting.

---

## Fundamentals

**Base URL:** `/api/v1/`

**Authentication:** All endpoints require the `X-API-Key` header. The API key is set via the `REED_API_KEY` environment variable at deployment time. A missing or invalid key returns `401 Unauthorized`.

**Format:** All request and response bodies are JSON. `Content-Type: application/json` is required on write requests.

**Auto-generated docs:** FastAPI generates an interactive OpenAPI (Swagger UI) at `/docs` and a ReDoc view at `/redoc`. These are always in sync with the implementation.

---

## Response conventions

### Success

```json
{
  "data": { ... },
  "meta": { ... }
}
```

`meta` is present on paginated responses. It is omitted on single-resource responses.

### Error

```json
{
  "error": {
    "code": "FEED_NOT_FOUND",
    "message": "No feed with id 'abc123' exists.",
    "detail": { }
  }
}
```

| HTTP status | Meaning |
|---|---|
| `200 OK` | Success |
| `201 Created` | Resource created |
| `202 Accepted` | Async operation started |
| `204 No Content` | Success with no body (DELETE) |
| `400 Bad Request` | Malformed request or validation failure |
| `401 Unauthorized` | Missing or invalid API key |
| `404 Not Found` | Resource does not exist |
| `409 Conflict` | Resource already exists (e.g. duplicate feed URL) |
| `422 Unprocessable Entity` | Request is valid JSON but fails business rules |
| `500 Internal Server Error` | Unexpected server error |

---

## Pagination

List endpoints that may return large result sets are paginated with cursor-based pagination.

**Request:**
```
GET /api/v1/items?cursor=<opaque_cursor>&limit=50
```

**Response meta:**
```json
{
  "meta": {
    "cursor": "next_page_cursor_value",
    "has_more": true,
    "total": 1842
  }
}
```

`limit` defaults to 50, maximum 200. `total` reflects the count matching the current filters, not the page size.

---

## Resource groups

### `/feeds` — Feed management

| Method | Path | Description |
|---|---|---|
| `GET` | `/feeds` | List all subscribed feeds |
| `POST` | `/feeds` | Subscribe to a new feed |
| `GET` | `/feeds/{id}` | Get a single feed |
| `PATCH` | `/feeds/{id}` | Update feed settings (display name, poll interval, reader mode, active state) |
| `DELETE` | `/feeds/{id}` | Unsubscribe (does not delete items) |
| `POST` | `/feeds/{id}/refresh` | Trigger an immediate poll for this feed |
| `GET` | `/feeds/{id}/items` | List items for a specific feed |
| `POST` | `/feeds/discover` | Given a website URL, return discovered feed URL(s) |

**Subscribe request body:**
```json
{
  "url": "https://example.com/feed.xml",
  "display_name": "Optional custom name",
  "tags": ["tag1", "tag2"],
  "poll_interval_minutes": null
}
```

`poll_interval_minutes: null` means inherit the global default. An integer value sets a per-feed override.

**Feed object:**
```json
{
  "id": "uuid",
  "url": "https://example.com/feed.xml",
  "title": "Feed Title",
  "display_name": null,
  "site_url": "https://example.com",
  "description": "...",
  "subscribed_at": "2026-07-10T09:00:00Z",
  "last_fetched_at": "2026-07-10T17:00:00Z",
  "next_poll_at": "2026-07-10T18:00:00Z",
  "consecutive_errors": 0,
  "last_error": null,
  "is_active": true,
  "effective_poll_interval_minutes": 60,
  "poll_interval_minutes": null,
  "reader_mode_enabled": null,
  "effective_reader_mode_enabled": true,
  "item_count": 142,
  "unread_count": 7
}
```

`effective_*` fields reflect the resolved value after applying config inheritance.

---

### `/items` — Item reading and state

| Method | Path | Description |
|---|---|---|
| `GET` | `/items` | List items (with filters) |
| `GET` | `/items/{id}` | Get a single item with full content |
| `PATCH` | `/items/{id}` | Update read state, starred state |
| `POST` | `/items/mark-read` | Bulk mark items as read |

**List filters (query parameters):**

| Parameter | Type | Description |
|---|---|---|
| `unread` | boolean | Filter to unread items only |
| `starred` | boolean | Filter to starred items only |
| `feed_id` | string | Filter to a specific feed |
| `tag` | string | Filter to items with this tag |
| `topic` | string | Filter to items about this topic |
| `since` | ISO 8601 | Items published after this date |
| `until` | ISO 8601 | Items published before this date |
| `cursor` | string | Pagination cursor |
| `limit` | integer | Page size (default 50, max 200) |

**Bulk mark-read request:**
```json
{
  "feed_id": "uuid",
  "before": "2026-07-10T00:00:00Z"
}
```

Both `feed_id` and `before` are optional. Omitting both marks everything as read (catch-up all).

**Item object (list view):**
```json
{
  "id": "uuid",
  "url": "https://example.com/article",
  "title": "Article Title",
  "summary": "First 300 characters...",
  "published_at": "2026-07-09T12:00:00Z",
  "read": false,
  "starred": false,
  "word_count": 1240,
  "feed": { "id": "uuid", "title": "Feed Name" },
  "author": { "name": "Author Name" },
  "tags": ["tag1"],
  "topics": [
    { "name": "Topic A", "score": 0.85 }
  ]
}
```

**Item object (detail view):** Adds `content` (full article text) and `note` (user annotation if present).

---

### `/tags` — Tag management

| Method | Path | Description |
|---|---|---|
| `GET` | `/tags` | List all tags with item counts |
| `POST` | `/tags` | Create a tag |
| `DELETE` | `/tags/{id}` | Delete a tag (removes from all items) |
| `POST` | `/items/{id}/tags` | Apply a tag to an item |
| `DELETE` | `/items/{id}/tags/{tag_id}` | Remove a tag from an item |

---

### `/notes` — Item annotations

| Method | Path | Description |
|---|---|---|
| `GET` | `/items/{id}/note` | Get the note for an item (404 if none) |
| `PUT` | `/items/{id}/note` | Create or replace the note for an item |
| `DELETE` | `/items/{id}/note` | Delete the note for an item |

Notes are scoped to items — one note per item. `PUT` is idempotent: it creates the note if it does not exist or replaces it if it does.

---

### `/topics` — Topic graph

| Method | Path | Description |
|---|---|---|
| `GET` | `/topics` | List all topics ordered by item count |
| `GET` | `/topics/{id}` | Get a topic with related topics |
| `GET` | `/topics/{id}/items` | Items about this topic (paginated, filterable) |
| `GET` | `/topics/{id}/related` | Related topics ordered by weight |

**Topic detail object:**
```json
{
  "id": "uuid",
  "name": "AI Governance",
  "item_count": 47,
  "related": [
    { "id": "uuid", "name": "Responsible AI", "weight": 0.72 },
    { "id": "uuid", "name": "Algorithmic Accountability", "weight": 0.61 }
  ]
}
```

---

### `/search` — Full-text and graph-aware search

| Method | Path | Description |
|---|---|---|
| `GET` | `/search` | Search across items and notes |

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `q` | string | Full-text search query (required) |
| `scope` | string | `'items'`, `'notes'`, or `'all'` (default: `'all'`) |
| `unread` | boolean | Restrict to unread items |
| `feed_id` | string | Restrict to a feed |
| `since` | ISO 8601 | Date range start |
| `until` | ISO 8601 | Date range end |
| `limit` | integer | Page size |

Search uses Kuzu's FTS index. Results include a `relevance_score` field.

---

### `/graph` — Built-in graph queries

These endpoints expose the six built-in graph queries as REST endpoints. They are also available as MCP tools.

| Method | Path | Description |
|---|---|---|
| `GET` | `/graph/similar/{item_id}` | Items similar to a given item (via SIMILAR_TO edges) |
| `GET` | `/graph/adjacent-to-starred` | Unread items similar to starred items |
| `GET` | `/graph/author/{author_id}/items` | All items by an author across all feeds |
| `GET` | `/graph/topic/{topic_id}/timeline` | Item volume for a topic over time |
| `GET` | `/graph/feed-health` | Feeds that are inactive or erroring |
| `POST` | `/graph/recompute` | Trigger derived edge recomputation (async, returns 202) |

**Similar items response:**
```json
{
  "data": [
    {
      "item": { ... },
      "score": 0.78,
      "shared_topics": ["AI Governance", "Responsible AI"]
    }
  ]
}
```

**Feed health response:**
```json
{
  "data": {
    "inactive": [
      { "feed": { ... }, "last_fetched_at": "2026-05-01T00:00:00Z", "days_since_last_item": 70 }
    ],
    "erroring": [
      { "feed": { ... }, "consecutive_errors": 12, "last_error": "Connection timeout" }
    ]
  }
}
```

---

### `/share` — Share sheet actions

| Method | Path | Description |
|---|---|---|
| `GET` | `/share/targets` | List configured share targets |
| `POST` | `/share/targets` | Add a share target |
| `PATCH` | `/share/targets/{id}` | Update a share target |
| `DELETE` | `/share/targets/{id}` | Remove a share target |
| `POST` | `/share` | Share an item to a target |

**Share request:**
```json
{
  "item_id": "uuid",
  "target_id": "uuid"
}
```

Built-in share target types: `copy_link`, `copy_markdown`, `webhook`, `raindrop`.

**Webhook execution** sends the [webhook payload](../design/user-patterns.md#webhook-payload-v1-spec) to the configured URL as an HTTP POST.

---

### `/config` — Global configuration

| Method | Path | Description |
|---|---|---|
| `GET` | `/config` | Get global config |
| `PATCH` | `/config` | Update one or more global config values |

**Config object:**
```json
{
  "default_poll_interval_minutes": 60,
  "reader_mode_enabled": true,
  "default_theme": "system",
  "items_per_page": 50,
  "mark_read_on_open": true
}
```

---

### `/import` and `/export` — Data portability

| Method | Path | Description |
|---|---|---|
| `GET` | `/export/opml` | Export feed list as OPML |
| `GET` | `/export/json` | Export full user data as JSON profile |
| `GET` | `/export/backup` | Export full instance backup archive |
| `POST` | `/import/opml` | Import feed subscriptions from an OPML file |
| `POST` | `/import/backup` | Import and restore a full instance backup |

**Export types:**

| Endpoint | Contents | Purpose |
|---|---|---|
| `/export/opml` | Feed list only (URLs, titles, tags as folders) | Migrate subscriptions to another RSS reader |
| `/export/json` | Feeds + items metadata + read/starred state + notes + tags | Personal data portability, archival |
| `/export/backup` | Complete instance state in portable JSON format | Instance migration (export from old server, import to new) |

Large exports (`/export/json`, `/export/backup`) are generated asynchronously. The endpoint returns `202 Accepted` with a job ID. The client polls `GET /export/jobs/{id}` for completion and a download URL.

**Backup import** (`POST /import/backup`) is destructive — it replaces the current instance state. The endpoint requires a confirmation header (`X-Confirm-Destructive: true`) to prevent accidental data loss.

---

## Design notes

**The UI consumes this API.** Every action available in the web UI is available via the API. There are no UI-only features and no API-only features.

**The MCP server shares this API's business logic** but does not call it over HTTP. Both the REST API and the MCP server import the same graph service layer directly. The REST API is the external contract; the MCP server is a parallel consumer of the same internal code.

**API versioning:** The `/api/v1/` prefix allows breaking changes to be introduced in `/api/v2/` without breaking existing integrations. There are no plans for v2 at this time, but the prefix is included from the start to avoid a future migration burden.
