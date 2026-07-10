# Feed Poller

The feed poller is an asyncio background worker that runs inside the Reed application process. It is responsible for fetching feeds on schedule, parsing items, extracting content and topics, writing new data to the graph, and triggering derived edge recomputation.

---

## Architecture overview

The poller runs as an `asyncio` task registered with the FastAPI application lifecycle. It starts when the application starts and shuts down cleanly when the application stops.

```
Application startup
       │
       ▼
  PollerService.start()
       │
       ├── load all active Feed nodes from graph
       ├── schedule each feed based on next_poll_at
       └── start the poll loop
              │
              ▼ (runs continuously)
         ┌─────────────────────────────────┐
         │  Find feeds due for polling     │
         │  (next_poll_at <= now)          │
         └────────────┬────────────────────┘
                      │
                      ▼ (for each due feed, concurrently)
              FeedFetchTask
                      │
              ┌───────┴────────┐
              │  HTTP fetch    │  (conditional GET)
              └───────┬────────┘
                      │
              ┌───────┴────────┐
              │  Feed parse    │  (feedparser)
              └───────┬────────┘
                      │
              ┌───────┴────────┐
              │  New item      │  (guid deduplication)
              │  detection     │
              └───────┬────────┘
                      │
              ┌───────┴────────┐
              │  Content       │  (reader mode, if enabled)
              │  extraction    │
              └───────┬────────┘
                      │
              ┌───────┴────────┐
              │  Topic         │  (YAKE keyword extraction)
              │  extraction    │
              └───────┬────────┘
                      │
              ┌───────┴────────┐
              │  Graph write   │  (Item nodes + edges)
              └───────┬────────┘
                      │
                      ▼
              Update Feed.next_poll_at
              Update Feed.last_fetched_at
              Reset / increment consecutive_errors
```

---

## Poll scheduling

The poller uses a simple time-based scheduler. On startup it loads all active feeds and checks `next_poll_at` against the current time.

```python
effective_interval = feed.poll_interval_minutes ?? config.default_poll_interval_minutes

next_poll_at = last_fetched_at + timedelta(minutes=effective_interval)
```

The main loop runs every 60 seconds and dispatches any feeds whose `next_poll_at` is in the past. Each feed poll runs as a separate asyncio task, so slow feeds do not block others.

**Concurrency limit:** A configurable semaphore limits the number of concurrent feed fetches (default: 10). This prevents thundering-herd behaviour on startup when all feeds are immediately due.

---

## HTTP fetching and conditional GET

Feed fetching honours HTTP caching headers to avoid redundant bandwidth and processing.

On each request, if the feed has a stored `etag` or `last_modified` value, the poller sends:

```
If-None-Match: <stored_etag>
If-Modified-Since: <stored_last_modified>
```

A `304 Not Modified` response means no new items. The poller updates `last_fetched_at` and `next_poll_at` and moves on — no parsing, no writes.

On a successful `200` response, the new `ETag` and `Last-Modified` headers (if present) are stored on the Feed node for the next request.

**User-Agent:** All requests identify Reed: `Reed/<version> (+https://github.com/simonives/reed)`. This is respectful practice and helps feed operators understand their traffic.

**Timeouts:** HTTP requests time out after 30 seconds by default (configurable). Feeds that time out increment `consecutive_errors`.

---

## Feed parsing

Feed XML/Atom is parsed with [`feedparser`](https://feedparser.readthedocs.io/), the mature Python feed parsing library. `feedparser` handles:

- RSS 0.9x, RSS 1.0, RSS 2.0
- Atom 0.3 and Atom 1.0
- Malformed feeds (feedparser is deliberately lenient)
- Character encoding detection

After parsing, the poller extracts:

| Feed field | Source |
|---|---|
| `title` | `feed.feed.title` |
| `site_url` | `feed.feed.link` |
| `description` | `feed.feed.subtitle` |
| `language` | `feed.feed.language` |
| `image_url` | `feed.feed.image.url` (if present) |

Per-item fields:

| Item field | Source |
|---|---|
| `guid` | `entry.id` (falls back to `entry.link` if absent) |
| `url` | `entry.link` |
| `title` | `entry.title` |
| `summary` | `entry.summary` |
| `content` | `entry.content[0].value` (if present) |
| `published_at` | `entry.published_parsed` |
| `author` | `entry.author` or `entry.author_detail` |

---

## New item detection

Before writing, the poller checks whether an item already exists by querying the graph for the feed's existing item GUIDs:

```cypher
MATCH (f:Feed {id: $feed_id})-[:HAS_ITEM]->(i:Item)
RETURN i.guid
```

Items whose `guid` is already present are skipped. Only new items proceed to content extraction and writing.

**GUID fallback:** If a feed entry has no `id` field, Reed uses the entry's `link` as the GUID. If that is also absent, the item is skipped with a warning logged.

---

## Content extraction (reader mode)

When reader mode is enabled (globally or per-feed), Reed fetches the full source article and extracts the main content.

**Library:** [`trafilatura`](https://trafilatura.readthedocs.io/) — fast, actively maintained, high extraction quality, pure Python.

```python
import trafilatura

downloaded = trafilatura.fetch_url(item_url)
content = trafilatura.extract(
    downloaded,
    include_comments=False,
    include_tables=True,
    no_fallback=False,
    output_format='txt'
)
```

If extraction fails (returns `None`, times out, or the source URL is unreachable), the poller falls back to the feed-provided summary. `content_source` is set to `'feed'` in this case, even when reader mode is enabled, so the reason for the fallback is auditable.

**Reader mode is applied only to new items.** Existing items already in the graph are not re-fetched.

---

## Topic extraction

Topics are extracted from item content using [YAKE](https://github.com/LIAAD/yake) (Yet Another Keyword Extractor) — a lightweight, unsupervised, language-independent keyword extraction algorithm with no model download required.

```python
import yake

extractor = yake.KeywordExtractor(
    lan='en',
    n=3,          # up to 3-word keyphrases
    dedupLim=0.7,
    top=10        # top 10 topics per item
)

keywords = extractor.extract_keywords(item_content)
# Returns: [('topic name', score), ...]
```

YAKE scores are inverted (lower = more relevant). Reed normalises scores to 0.0–1.0 (higher = more relevant) before storing on the `ABOUT` edge.

The extraction runs on `content` if available, falling back to `summary`. If both are absent, no topics are extracted for the item.

**Topic deduplication:** Topic names are normalised (lowercased, stripped) before lookup. If a Topic node with the same normalised name already exists, the `ABOUT` edge is created to the existing node rather than creating a duplicate. `Topic.item_count` is incremented.

**Future upgrade path:** YAKE can be swapped for spaCy named entity recognition as an opt-in configuration (`topic_extraction_method: 'spacy'`). The extraction interface is abstracted behind a `TopicExtractor` protocol to make this substitution clean.

---

## Graph write path

After detection, extraction, and topic identification, new items are written to the graph in a single transaction per feed poll:

```cypher
-- Create Item node
CREATE (i:Item {
    id: $id, guid: $guid, url: $url,
    title: $title, summary: $summary, content: $content,
    content_source: $content_source, published_at: $published_at,
    fetched_at: $now, word_count: $word_count,
    read: false, starred: false
})

-- Link to Feed
MATCH (f:Feed {id: $feed_id})
CREATE (f)-[:HAS_ITEM {fetched_at: $now}]->(i)

-- Link to Author (create if not exists)
MERGE (a:Author {name: $author_name, email: $author_email})
CREATE (i)-[:WRITTEN_BY]->(a)

-- Link to Topics
MERGE (t:Topic {name: $topic_name})
SET t.item_count = t.item_count + 1
CREATE (i)-[:ABOUT {score: $score, extraction_method: 'yake'}]->(t)
```

Writing is batched per feed poll — all new items from a single feed fetch are written in one transaction. This ensures that a partial write (e.g. application crash mid-poll) does not leave orphaned items.

---

## Error handling and backoff

Each failed poll increments `Feed.consecutive_errors`. The poller applies exponential backoff to the next poll interval based on the error count:

| Consecutive errors | Next poll delay |
|---|---|
| 1–2 | Normal interval |
| 3–5 | 2× normal interval |
| 6–10 | 4× normal interval |
| >10 | 24 hours |

`Feed.last_error` stores the most recent error message for display in the Feed Health view.

Feeds that have exceeded 10 consecutive errors surface in the Feed Health built-in graph query and are flagged in the UI. They are not automatically deactivated — the user decides whether to remove or retry the feed.

---

## Derived edge recomputation

`SIMILAR_TO` (Item → Item) and `RELATED_TO` (Topic → Topic) are derived edges that are not written during feed polling. They are computed by a separate job on a configurable schedule.

**Default schedule:** Every 6 hours.

**Triggerable on demand:** `POST /api/v1/graph/recompute` triggers an immediate recomputation. The endpoint returns `202 Accepted` and runs the job asynchronously.

### RELATED_TO computation

```cypher
-- For each pair of topics, count items where both appear
MATCH (t1:Topic)<-[:ABOUT]-(i:Item)-[:ABOUT]->(t2:Topic)
WHERE t1.id < t2.id  -- avoid duplicate pairs
WITH t1, t2, count(i) AS co_occurrences
WHERE co_occurrences >= 2
WITH t1, t2,
     toFloat(co_occurrences) /
     (t1.item_count + t2.item_count - co_occurrences) AS jaccard
MERGE (t1)-[r:RELATED_TO]->(t2)
SET r.weight = jaccard, r.computed_at = timestamp()
```

### SIMILAR_TO computation

```cypher
-- Items sharing topics within the comparison window
MATCH (i1:Item)-[:ABOUT]->(t:Topic)<-[:ABOUT]-(i2:Item)
WHERE i1.id < i2.id
  AND i1.published_at >= datetime() - duration('P90D')
  AND i2.published_at >= datetime() - duration('P90D')
WITH i1, i2, count(t) AS shared_topics
WHERE shared_topics >= 2
MATCH (i1)-[:ABOUT]->(t1:Topic)
MATCH (i2)-[:ABOUT]->(t2:Topic)
WITH i1, i2, shared_topics,
     count(DISTINCT t1) AS topics_i1,
     count(DISTINCT t2) AS topics_i2
WITH i1, i2,
     toFloat(shared_topics) / (topics_i1 + topics_i2 - shared_topics) AS jaccard
WHERE jaccard > 0.1
MERGE (i1)-[r:SIMILAR_TO]->(i2)
SET r.score = jaccard, r.computed_at = timestamp()
```

The 90-day window and 0.1 score threshold are configurable via global config. Older derived edges outside the window are pruned during each recomputation run.
