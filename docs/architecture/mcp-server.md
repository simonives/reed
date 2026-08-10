# MCP Server

Reed includes a first-class MCP (Model Context Protocol) server built with [FastMCP](https://github.com/jlowin/fastmcp). It runs in the same process as the REST API and shares the graph service layer directly — no HTTP intermediary between the MCP tools and the data.

The MCP server is the interface through which AI clients — Claude, Cursor, or any MCP-compatible tool — interact with a user's reading graph. It is not a thin API wrapper; it is a graph traversal interface designed for the way AI clients reason and explore.

---

## Design principles

**Graph-native, not REST-over-MCP.** Tools are designed around graph traversal patterns — hop from item to topics to related items — not CRUD operations. An AI client can follow a thread of interest across feeds, authors, and time without the user directing each step.

**Read-heavy, write-capable.** Most tools are read operations. Write tools (mark read, star, tag, annotate) are included because an AI client that cannot act on what it finds is only half useful.

**Shared service layer.** MCP tools and REST API handlers both call the same `GraphService` Python module. A change to how Reed queries or writes the graph affects both surfaces simultaneously.

**Same process, separate transport.** The MCP server and REST API run in the same FastAPI application. The MCP server is exposed via stdio (for local AI clients like Claude Desktop) and optionally via HTTP/SSE (for remote or networked clients).

---

## Transport configuration

**stdio** (default for local clients):
```json
{
  "mcpServers": {
    "reed": {
      "command": "docker",
      "args": ["exec", "-i", "reed", "python", "-m", "reed.mcp"],
      "env": { "REED_API_KEY": "your-key-here" }
    }
  }
}
```

**HTTP/SSE** (for networked or remote clients):
```
http://localhost:8000/mcp
```

Auth on both transports uses the same `REED_API_KEY` as the REST API.

---

## Tool inventory

### Feed tools

#### `list_feeds`
Returns all subscribed feeds with metadata and unread counts.

**Input:** None

**Output:**
```json
[
  {
    "id": "uuid",
    "title": "Feed Title",
    "site_url": "https://example.com",
    "unread_count": 7,
    "last_fetched_at": "2026-07-10T17:00:00Z",
    "is_active": true
  }
]
```

---

#### `get_feed`
Returns a single feed with full metadata.

**Input:**
```json
{ "feed_id": "uuid" }
```

---

#### `subscribe_feed`
Subscribes to a new feed by URL.

**Input:**
```json
{
  "url": "https://example.com/feed.xml",
  "display_name": "Optional name",
  "tags": ["optional", "tags"]
}
```

**Output:** The created feed object.

---

#### `refresh_feed`
Triggers an immediate poll for a feed.

**Input:**
```json
{ "feed_id": "uuid" }
```

---

### Item tools

#### `get_items`
Returns items matching filters. The primary reading tool.

**Input:**
```json
{
  "feed_id": "uuid",
  "unread": true,
  "starred": false,
  "tag": "string",
  "topic": "string",
  "since": "2026-07-01T00:00:00Z",
  "limit": 20,
  "cursor": "opaque_cursor"
}
```

All fields are optional. With no filters, returns the most recent items across all feeds.

**Output:** Paginated list of item objects (summary view — no full content).

---

#### `get_item`
Returns a single item with full content. Use this to read an article.

**Input:**
```json
{ "item_id": "uuid" }
```

**Output:** Full item object including `content`, `topics`, `tags`, `note`, and `similar_items` (top 5 by score).

---

#### `mark_read`
Marks one or more items as read.

**Input:**
```json
{
  "item_ids": ["uuid1", "uuid2"],
  "feed_id": "uuid",
  "before": "2026-07-10T00:00:00Z"
}
```

`item_ids`, `feed_id`, and `before` are all optional and combinable. Omitting all three marks everything as read.

---

#### `mark_starred`
Stars or unstars an item.

**Input:**
```json
{ "item_id": "uuid", "starred": true }
```

---

#### `tag_item`
Applies or removes a tag on an item.

**Input:**
```json
{ "item_id": "uuid", "tag": "tag-name", "action": "add" }
```

`action` is either `"add"` or `"remove"`. Creates the tag if it does not already exist.

---

#### `annotate_item`
Creates or replaces the note on an item.

**Input:**
```json
{ "item_id": "uuid", "content": "My annotation text." }
```

Passing `content: null` deletes the note.

---

### Graph traversal tools

These are the tools that make the graph model tangible. They power the six built-in queries and enable open-ended AI-driven exploration.

#### `find_similar_items`
Returns items similar to a given item, via `SIMILAR_TO` edges.

**Input:**
```json
{
  "item_id": "uuid",
  "limit": 10,
  "unread_only": false
}
```

**Output:**
```json
[
  {
    "item": { ... },
    "score": 0.78,
    "shared_topics": ["AI Governance", "Responsible AI"]
  }
]
```

**Typical AI use:** After reading an item, surface what else in the library is related before moving on.

---

#### `find_adjacent_to_starred`
Returns unread items similar to the user's starred items. The "Discover" view in graph form.

**Input:**
```json
{ "limit": 20, "min_score": 0.2 }
```

**Output:** Items ranked by similarity score to the user's starred set.

**Typical AI use:** "What in my unread items is most relevant to what I've found important enough to star?"

---

#### `find_path`
Finds how two items (or an item and a topic) connect through the graph — the answer to "how does this relate to that."

**Input:**
```json
{
  "from_id": "uuid",
  "to_id": "uuid",
  "from_type": "item",
  "max_topic_hops": 3
}
```

`from_type` is `"item"` or `"topic"`. `max_topic_hops` must be `>= 1`.

**Output:** `{ "path": [ ... ] }` — an ordered list of nodes/edges connecting the two, or an empty list if no connection is found within `max_topic_hops`.

Traversal follows `ABOUT`/`RELATED_TO` edges only — it is topic-based, not similarity-based, and deliberately excludes `SIMILAR_TO`. An empty path does not mean the two are unrelated by similarity, only that they don't share a topic chain within the hop budget.

**Typical AI use:** "How does this article connect to that one?"

---

#### `explore_topic`
Returns items about a topic, plus related topics, ordered by weight.

**Input:**
```json
{
  "topic_name": "AI Governance",
  "limit": 20,
  "since": "2026-06-01T00:00:00Z"
}
```

**Output:**
```json
{
  "topic": { "id": "uuid", "name": "AI Governance", "item_count": 47 },
  "items": [ ... ],
  "related_topics": [
    { "name": "Responsible AI", "weight": 0.72 },
    { "name": "Algorithmic Accountability", "weight": 0.61 }
  ]
}
```

**Typical AI use:** "What's in my library about AI Governance? What related topics are covered?"

---

#### `get_author_items`
Returns all items by an author across all subscribed feeds.

**Input:**
```json
{
  "author_name": "Simon Willison",
  "limit": 20,
  "since": "2026-01-01T00:00:00Z"
}
```

**Typical AI use:** "What has this author published that I haven't read?"

---

#### `get_topic_timeline`
Returns item volume for a topic over time, bucketed by week or month.

**Input:**
```json
{
  "topic_name": "AI Governance",
  "bucket": "week",
  "since": "2026-01-01T00:00:00Z"
}
```

**Output:**
```json
[
  { "period": "2026-W01", "count": 3 },
  { "period": "2026-W02", "count": 7 },
  ...
]
```

**Typical AI use:** "Is coverage of this topic increasing or decreasing in my feeds?"

---

#### `get_feed_health`
Returns feeds that are inactive or returning errors.

**Input:** None

**Output:**
```json
{
  "inactive": [
    { "feed": { ... }, "days_since_last_item": 70 }
  ],
  "erroring": [
    { "feed": { ... }, "consecutive_errors": 12, "last_error": "..." }
  ]
}
```

---

#### `search`
Full-text search across items and notes.

**Input:**
```json
{
  "query": "search terms",
  "scope": "all",
  "unread": false,
  "since": "2026-06-01T00:00:00Z",
  "limit": 20
}
```

**Typical AI use:** "Find everything in my library about [specific concept] — not just topic matches, but keyword matches in content."

---

### Discovery tools

Cheap enumeration tools for orienting an AI client before it starts traversing — "what topics/tags/authors exist in this library at all."

#### `list_topics`
Lists all topics.

**Input:**
```json
{ "limit": 50, "offset": 0, "sort": "item_count" }
```

`sort` is `"item_count"` (default, most-covered first) or `"centrality"` (PageRank over the topic co-occurrence graph). Known limitation (reed#206): centrality is biased by an arbitrary edge-direction artifact and can understate low-degree topics' real connectivity — treat it as suggestive, not authoritative.

---

#### `list_tags`
Lists all tags with item counts.

**Input:** None

---

#### `list_authors`
Lists authors by item count, most-published first.

**Input:**
```json
{ "limit": 50 }
```

---

#### `get_topic_clusters`
Groups topics into clusters via Louvain community detection on the topic co-occurrence graph — free topic clustering the flat keyword extraction otherwise lacks. The client names the clusters semantically.

**Input:**
```json
{ "limit": 50 }
```

---

### Export tools

#### `export_opml`
Returns the user's feed list as an OPML string.

**Input:** None

**Output:** `{ "opml": "<opml>...</opml>" }`

---

### Research tools

Tools that package graph context for an AI client's own research, rather than duplicating web search or fact-finding inside Reed.

#### `capture_external_finding`
Appends an external research finding to an item's note — the answer to "go look this up outside Reed," without Reed doing the searching itself. Unlike `annotate_item`, this *appends* a timestamped block rather than replacing the note, so a client accumulating findings across a research session never silently clobbers what's already there. Findings become searchable via the `search` tool afterwards.

**Input:**
```json
{
  "item_id": "uuid",
  "url": "https://example.gov/reg-123",
  "title": "New regulation text",
  "summary": "Full text of the regulation referenced in this article.",
  "tags": ["optional", "tags"]
}
```

---

#### `build_research_brief`
Packages an item's full graph context into one call — the item itself, its topics, similar items, and other items by the same author — to prime the client's own web research rather than duplicating it in Reed.

**Input:**
```json
{ "item_id": "uuid" }
```

**Output:**
```json
{
  "item": { ... },
  "topics": [ ... ],
  "similar_items": [ ... ],
  "same_author_items": [ ... ]
}
```

---

### Config tools

#### `get_config`
Returns global configuration.

#### `trigger_recompute`
Triggers derived edge recomputation asynchronously.

**Input:** None

**Output:** `{ "job_id": "uuid", "status": "queued" }`

The returned `job_id` is not currently associated with any queryable task status — there is no tool to poll it against; treat this as fire-and-forget.

---

## Resources and prompts

#### Resource: `reed://graph/overview`
A one-shot orientation snapshot: feed/item/unread/topic counts, top topics, and top authors. Useful as the first call in a session to ground an AI client in the shape of the library before it starts traversing.

#### Prompts

Three guided-workflow prompts package the traversal patterns below into ready-made instructions a client can invoke directly:

- **`deep_reading_session`** — unread items, read one, find related, mark read.
- **`weekly_digest`** — what's new, what themes are covered, what matches past interests.
- **`research_thread`** — search a topic, expand via similarity, map related topics, annotate.

---

## Traversal patterns

The most powerful use of the Reed MCP server is chaining tools in sequence. An AI client can traverse the graph without the user directing each hop.

**Pattern: Deep reading session**
1. `get_items(unread: true, limit: 20)` — what's waiting to be read
2. `get_item(item_id)` — read an article
3. `find_similar_items(item_id)` — what else in the library is related
4. `explore_topic(topic_name)` — go deeper on a topic the article raised
5. `mark_read(item_ids)` — tidy up

**Pattern: Weekly digest**
1. `get_items(unread: true, since: 7 days ago)` — everything new this week
2. `explore_topic` for the most covered topics — surface themes
3. `find_adjacent_to_starred` — what's new that matches past interests
4. Return a structured summary to the user

**Pattern: Research thread**
1. `search(query: "topic of interest")` — find the seed items
2. `find_similar_items` on the most relevant — expand the thread
3. `explore_topic` on the topics that emerge — map the territory
4. `annotate_item` — capture insights as they surface
5. Return a summary with annotated items linked

---

## Tool count summary

| Category | Tools | Read/Write |
|---|---|---|
| Feeds | `list_feeds`, `get_feed`, `subscribe_feed`, `refresh_feed` | 3 read, 1 write |
| Items | `get_items`, `get_item`, `mark_read`, `mark_starred`, `tag_item`, `annotate_item` | 2 read, 4 write |
| Graph traversal | `find_similar_items`, `find_adjacent_to_starred`, `find_path`, `explore_topic`, `get_author_items`, `get_topic_timeline`, `get_feed_health`, `search` | 8 read |
| Discovery | `list_topics`, `list_tags`, `list_authors`, `get_topic_clusters` | 4 read |
| Export | `export_opml` | 1 read |
| Research | `capture_external_finding`, `build_research_brief` | 1 read, 1 write |
| Config | `get_config`, `trigger_recompute` | 1 read, 1 write |
| **Total** | **27 tools** | **20 read, 7 write** |

Plus one resource (`reed://graph/overview`) and three prompts (`deep_reading_session`, `weekly_digest`, `research_thread`) — see "Resources and prompts" above.
