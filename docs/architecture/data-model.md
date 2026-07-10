# Data Model

Reed's data layer is a [Kuzu](https://kuzudb.com) embedded graph database. All persistent data — feeds, items, authors, topics, tags, notes, read state, poll metadata — lives in a single Kuzu store at a configurable path (default: `/data/reed.kuzu`).

This document specifies the full graph schema: node tables, relationship tables, indexes, and the config inheritance model.

---

## Node tables

### Feed

A subscribed RSS or Atom feed.

```cypher
CREATE NODE TABLE Feed (
    id        STRING,
    url       STRING,
    title     STRING,
    site_url  STRING,
    description     STRING,
    language        STRING,
    image_url       STRING,
    display_name    STRING,
    subscribed_at   TIMESTAMP,
    last_fetched_at TIMESTAMP,
    next_poll_at    TIMESTAMP,
    etag            STRING,
    last_modified   STRING,
    consecutive_errors INT64,
    last_error      STRING,
    is_active       BOOLEAN,
    poll_interval_minutes INT64,
    reader_mode_enabled   BOOLEAN,
    PRIMARY KEY (id)
)
```

**Config inheritance:** `poll_interval_minutes` and `reader_mode_enabled` are nullable. A `NULL` value means "inherit from global config". An explicit value overrides the global default for that feed only. See [Config inheritance model](#config-inheritance-model).

**`display_name`:** User-set override for the feed title. `NULL` means use `title` as reported by the feed.

**`is_active`:** When `false`, the poller skips this feed. Users can pause a feed without unsubscribing.

---

### Item

A single article or entry from a feed.

```cypher
CREATE NODE TABLE Item (
    id               STRING,
    guid             STRING,
    url              STRING,
    title            STRING,
    summary          STRING,
    content          STRING,
    content_source   STRING,
    published_at     TIMESTAMP,
    fetched_at       TIMESTAMP,
    word_count       INT64,
    language         STRING,
    read             BOOLEAN,
    read_at          TIMESTAMP,
    starred          BOOLEAN,
    starred_at       TIMESTAMP,
    PRIMARY KEY (id)
)
```

**`guid`:** The feed-provided unique identifier for the item. Used for deduplication — if an item with the same `guid` already exists for a feed, it is not inserted again.

**`content` and `content_source`:** `content` holds the full article text. `content_source` is either `'feed'` (content came directly from the feed) or `'reader_mode'` (content was extracted from the source URL by the reader mode pipeline). A `NULL` content with `content_source = 'feed'` means the feed provided no content beyond the summary.

---

### Author

A content author. Authors are deduplicated by name + email combination at write time.

```cypher
CREATE NODE TABLE Author (
    id    STRING,
    name  STRING,
    email STRING,
    url   STRING,
    PRIMARY KEY (id)
)
```

**Notes:** Feed-level authors (where the feed itself has an author rather than individual items) are represented as an Author node linked to the Feed node via `HAS_AUTHOR`. Item-level authors are linked to Item nodes via `WRITTEN_BY`.

---

### Tag

A user-defined label. Flat — no nesting or hierarchy.

```cypher
CREATE NODE TABLE Tag (
    id         STRING,
    name       STRING,
    created_at TIMESTAMP,
    PRIMARY KEY (id)
)
```

**OPML import:** OPML folder/category names are mapped to Tag nodes on import. The mapping is surfaced to the user during the import process.

---

### Topic

A subject extracted from item content. Topics are the primary mechanism for cross-feed relationship discovery.

```cypher
CREATE NODE TABLE Topic (
    id         STRING,
    name       STRING,
    source     STRING,
    item_count INT64,
    PRIMARY KEY (id)
)
```

**`source`:** Either `'extracted'` (identified by the topic extraction pipeline from item content) or `'inferred'` (derived from co-occurrence patterns across items).

**`item_count`:** Denormalised count of items linked to this topic. Updated on each write. Used for Topic explorer sorting without a full graph aggregation.

---

### Note

A user-authored freeform annotation attached to an item.

```cypher
CREATE NODE TABLE Note (
    id         STRING,
    content    STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (id)
)
```

Notes are queryable via the MCP server — "show me everything I've annotated about AI governance" traverses `HAS_NOTE` edges and filters by content. Notes are included in the JSON profile export and instance backup.

---

### Config

A singleton node holding global application configuration. There is exactly one Config node in the graph, with `id = 'global'`.

```cypher
CREATE NODE TABLE Config (
    id                            STRING,
    default_poll_interval_minutes INT64,
    reader_mode_enabled           BOOLEAN,
    default_theme                 STRING,
    items_per_page                INT64,
    mark_read_on_open             BOOLEAN,
    css_accent_color              STRING,
    css_font_size_base            INT64,
    css_reading_width             INT64,
    css_line_height               DOUBLE,
    css_font_family_reading       STRING,
    created_at                    TIMESTAMP,
    updated_at                    TIMESTAMP,
    PRIMARY KEY (id)
)
```

The Config node is created on first run with sensible defaults. It is updated via the Settings UI or `PATCH /api/v1/config`. See [Config inheritance model](#config-inheritance-model).

---

### SchemaVersion

Tracks applied schema migrations. Append-only — one node per migration.

```cypher
CREATE NODE TABLE SchemaVersion (
    version     INT64,
    description STRING,
    applied_at  TIMESTAMP,
    PRIMARY KEY (version)
)
```

---

## Relationship tables

### HAS_ITEM

A feed contains items.

```cypher
CREATE REL TABLE HAS_ITEM (
    FROM Feed TO Item,
    fetched_at TIMESTAMP
)
```

**Cardinality:** Many-to-one (each Item belongs to exactly one Feed). Enforced at write time — an Item is created only via a Feed's poll.

---

### WRITTEN_BY

An item is written by an author.

```cypher
CREATE REL TABLE WRITTEN_BY (
    FROM Item TO Author
)
```

**Cardinality:** Many-to-many. A single item may have multiple authors; an author appears across many items.

---

### HAS_AUTHOR

A feed has a default author (for feeds that attribute authorship at the feed level rather than per-item).

```cypher
CREATE REL TABLE HAS_AUTHOR (
    FROM Feed TO Author
)
```

---

### TAGGED_WITH

A user has applied a tag to an item.

```cypher
CREATE REL TABLE TAGGED_WITH (
    FROM Item TO Tag,
    tagged_at TIMESTAMP
)
```

---

### ABOUT

An item is about a topic. Populated by the topic extraction pipeline.

```cypher
CREATE REL TABLE ABOUT (
    FROM Item TO Topic,
    score             DOUBLE,
    extraction_method STRING
)
```

**`score`:** Relevance score from the extraction pipeline (0.0–1.0). Used to rank topics by salience.

**`extraction_method`:** The extraction library used (`'yake'`, `'spacy'`, etc.). Preserved for auditability if the extraction pipeline changes.

---

### HAS_NOTE

An item has a user annotation.

```cypher
CREATE REL TABLE HAS_NOTE (
    FROM Item TO Note
)
```

**Cardinality:** One item may have multiple notes. One note belongs to exactly one item.

---

### RELATED_TO

Two topics are related. A derived edge, computed from topic co-occurrence across items.

```cypher
CREATE REL TABLE RELATED_TO (
    FROM Topic TO Topic,
    weight      DOUBLE,
    computed_at TIMESTAMP
)
```

**`weight`:** Co-occurrence strength (0.0–1.0). Higher weight = topics appear together in more items.

**Computation:** Recomputed by the derived edge job on a configured schedule (default: every 6 hours). Triggerable on demand via `POST /api/v1/graph/recompute`.

---

### SIMILAR_TO

Two items are similar. A derived edge, computed from shared topic nodes.

```cypher
CREATE REL TABLE SIMILAR_TO (
    FROM Item TO Item,
    score       DOUBLE,
    computed_at TIMESTAMP
)
```

**`score`:** Similarity score based on Jaccard similarity of the items' Topic sets (0.0–1.0).

**Computation:** Recomputed on the same schedule as `RELATED_TO`. Only items within the same time window (configurable, default: 90 days) are compared to prevent the graph from growing unbounded.

---

## Full-text search index

Kuzu's FTS extension is used for keyword search across item content. The index covers `Item.title`, `Item.summary`, and `Item.content`.

```cypher
INSTALL fts;
LOAD EXTENSION fts;

CALL create_fts_index(
    'item_search',
    'Item',
    ['title', 'summary', 'content']
);
```

Note content (`Note.content`) is searchable via a separate index:

```cypher
CALL create_fts_index(
    'note_search',
    'Note',
    ['content']
);
```

FTS indexes are created on first run and updated incrementally as new items are written.

---

## Config inheritance model

Reed uses a two-level config system. The `Config` singleton provides global defaults. Individual `Feed` nodes carry sparse overrides — only the settings the user has explicitly changed for that feed.

At runtime, the effective config for a feed is resolved as:

```
effective_value = feed.setting ?? global_config.setting
```

A `NULL` property on a Feed node means "use the global default". An explicit value — even `false` or `0` — overrides the global for that feed.

**Behaviour when the global default changes:**
- Feeds with `NULL` for that setting automatically receive the new default.
- Feeds with an explicit per-feed value are not affected.

This is intentional — per-feed overrides are sticky until the user explicitly resets them. A user who has configured a specific feed to poll every 5 minutes will not have that overridden if the global default changes to 30 minutes.

**Reset to default:** Setting a per-feed value to `NULL` via the API or UI resets it to the global default.

---

## Entity relationship summary

```
Config (singleton)

Feed ──HAS_ITEM──► Item ──WRITTEN_BY──► Author
 │                  │
 └──HAS_AUTHOR──►   ├──TAGGED_WITH──► Tag
                    │
                    ├──ABOUT──────► Topic ──RELATED_TO──► Topic
                    │
                    ├──HAS_NOTE──► Note
                    │
                    └──SIMILAR_TO──► Item (derived)
```

---

## Schema versioning and migrations

Schema changes are applied via migration scripts that run on startup if `SchemaVersion.version` is behind the application's expected version. Migrations are append-only — they add nodes, relationships, or properties; they do not drop or rename existing structures without a documented migration path.

Migration scripts live in `src/reed/migrations/` and are numbered sequentially (`001_initial_schema.cypher`, `002_add_note_table.cypher`, etc.).
