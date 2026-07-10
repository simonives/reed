# User Patterns

Decided user patterns for Reed v1 and v2. This document is the source of truth for feature scope decisions. Each item is marked **v1** (ships before 1.0.0) or **v2** (explicitly deferred).

---

## Feed ingestion

| Pattern | Scope | Notes |
|---|---|---|
| Direct feed URL entry | v1 | Paste a feed URL; Reed validates and subscribes |
| Website URL with feed discovery | v1 | Reed checks `<link rel="alternate">` then common paths (`/feed`, `/rss`, `/feed.xml`, `/atom.xml`, `/index.xml`) |
| OPML import | v1 | Bulk subscribe from any RSS reader export; critical for migration |
| OPML export | v1 | User can migrate out of Reed; non-negotiable for a project committed to data ownership |
| Full JSON profile export | v1 | Exports all user data: feeds, items, read state, starred items, notes, tags — complete picture of the user's reading history |
| Full backup / restore | v1 | Export a portable archive from one Reed instance and import it to a new instance to be fully productive immediately. Covers instance migration without data loss. |
| API-based subscription | v1 | `POST /api/v1/feeds` — falls out of the REST API; enables automation |
| Feed search / directory | v2 | Requires third-party feed directory dependency; deferred |
| Browser bookmarklet | v2 | One-click subscribe from browser; deferred until core is stable |

### Import / export design notes

Three distinct export types, each serving a different purpose:

- **OPML export** — feed list only; for migrating subscriptions to another RSS reader
- **JSON profile export** — complete user data snapshot (feeds + all item metadata + read/starred state + notes + tags); for backup or personal data portability
- **Instance backup / restore** — a portable archive (JSON or structured format) that a new Reed instance can fully import to restore an identical state; designed for instance migration (e.g. moving to a new server)

---

## Reading and interaction patterns

| Pattern | Scope | Notes |
|---|---|---|
| Three-pane layout (default) | v1 | Feed list / item list / reading pane; configurable to river-of-news single stream |
| Keyboard shortcuts | v1 | j/k navigate, space scroll, m mark read, s star, g+h home — Google Reader muscle memory; non-optional for this audience |
| Reader mode / full-text extraction | v1 | Fetches and extracts full article content for summary-only feeds; library TBD (`trafilatura` or `python-readability`) |
| Offline content | v1 | Full article content stored in Item node at poll time; readable without internet access |
| MCP reading and writing | v1 | AI clients traverse the graph; read and write operations both supported |
| Catch-up / mark all read | v1 | Mark all items in a feed, folder, or before a date as read |
| Views and filters | v1 | Unread, starred, by feed, by tag, by topic, today, this week |
| Dark mode | v1 | CSS custom properties; expected baseline |
| Responsive / mobile web | v1 | Readable on mobile as baseline; optimised layout in v2 |
| RSS-to-email delivery | v2 | Deferred |
| Push notifications | v2 | Browser notifications for new items matching a filter; deferred |

---

## Feed configuration

| Feature | Scope | Notes |
|---|---|---|
| Global default config | v1 | System-wide defaults for all settings (poll interval, reader mode, etc.); applied to all feeds unless overridden |
| Per-feed config override | v1 | Any global setting can be overridden at the feed level; only explicitly set values override the global default |
| Global config updates | v1 | Changing a global default applies to all feeds that have not been individually configured; feeds with a per-feed override retain their override |
| Feed display name override | v1 | Custom name for any feed regardless of what the feed reports |
| Per-feed poll interval | v1 | Default inherited from global; overridable per feed |
| Per-feed reader mode toggle | v1 | Default inherited from global; overridable per feed |
| Per-feed tagging at subscription | v1 | Assign tags when subscribing, not just after |

### Config inheritance model

Global config is the default for every setting. Per-feed config is a sparse override — only the values a user has explicitly changed are stored. When the global default changes, all feeds without a per-feed override for that setting receive the new default automatically.

This mirrors CSS inheritance: global = cascade, per-feed = inline style.

---

## Interaction features

| Feature | Scope | Notes |
|---|---|---|
| Notes / annotations | v1 | Freeform text attached to any item; queryable via MCP ("show everything I've noted about X") |
| Tags (user-defined, flat) | v1 | Manual; auto-suggested from extracted topics; OPML folder structure maps to tags on import |
| Built-in graph queries | v1 | See table below |
| Full user data export (JSON) | v1 | See import/export above |
| Highlights (text selection) | v2 | Storing text ranges adds complexity; deferred |

### Built-in graph queries (v1)

These are surfaced in the UI and available as MCP tools. They are the primary way the graph model becomes visible to users.

| Query | Trigger | Description |
|---|---|---|
| **More like this** | Sidebar while reading an item | Items in the library sharing topics with the current article |
| **Topic explorer** | Click any topic tag | All items about a given topic across all feeds, newest first |
| **Starred-adjacent** | "Discover" view | Unread items similar to starred items — surfaces overlooked relevant content |
| **Author profile** | Click any author name | All items from an author across all subscribed feeds |
| **Topic timeline** | Topic explorer header | Volume of items about a topic over time |
| **Feed health** | Feed management view | Feeds inactive for >30 days or returning consistent errors |

---

## Share sheet

A configurable set of share targets in Settings. The reading view renders enabled targets as share buttons. Each target has a name, type (built-in or webhook), and configuration.

### v1 share targets

| Target | Type | Notes |
|---|---|---|
| Copy link | Built-in | Copies article URL to clipboard |
| Copy as Markdown | Built-in | `[Title](URL)` — essential for Obsidian, Notion, Bear, etc. |
| Generic webhook | Built-in | POSTs article metadata (title, URL, excerpt, author, tags) to a configured URL; covers Make, Zapier, n8n, and any custom integration |
| Raindrop.io | Built-in | Saves to a configured collection via Raindrop API; first-class integration |

### v2 share targets

| Target | Notes |
|---|---|
| Readwise | Syncs highlights and notes via Readwise API; ubiquitous among knowledge workers |
| Omnivore | Open-source read-it-later; philosophical alignment with Reed |
| Obsidian (local REST API) | Saves article as a note to a local Obsidian vault via the Obsidian Local REST API plugin |
| Notion | Popular developer and knowledge worker tool; save article as a Notion page via Notion API |
| Mastodon / Fediverse | Share to a configured Mastodon account; more relevant than Twitter for the open-source self-hosted audience |
| Bluesky | Share via AT Protocol |
| Email (mailto) | Opens a `mailto:` link; no SMTP config required |

### Webhook payload (v1 spec)

```json
{
  "event": "share",
  "item": {
    "title": "Article title",
    "url": "https://example.com/article",
    "excerpt": "First 300 characters of content...",
    "author": "Author Name",
    "published_at": "2026-07-10T09:00:00Z",
    "feed": {
      "title": "Feed Name",
      "url": "https://example.com/feed.xml"
    },
    "tags": ["tag1", "tag2"],
    "topics": ["Topic A", "Topic B"]
  },
  "shared_at": "2026-07-10T17:30:00Z"
}
```

---

## Graph schema additions (from this session)

The following additions to the graph model were identified during user pattern design and must be reflected in `docs/architecture/data-model.md`:

- **`Note` node** — `content` (text), `created_at`, `updated_at`; linked to Item via `HAS_NOTE` edge
- **`ShareTarget` node** (or config file entry) — configurable share destinations; TBD whether this lives in the graph or a separate config structure
- **`author` property on Item** — needed for the author profile query if Author node is not yet extracted; fallback before full Author node extraction is implemented
