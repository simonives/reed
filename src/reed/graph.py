# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import html as _html
import json
import logging
import pathlib
import re
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import kuzu

from .config import CONFIG_DEFAULTS
from .http import safe_url as _safe_url

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 6

# Config keys writable via PATCH /config and safe to restore from backup.
# schema_version is managed separately and excluded intentionally.
_ALLOWED_CONFIG_KEYS = frozenset(CONFIG_DEFAULTS.keys()) | {"default_poll_interval_minutes"}


_FEED_COLS = """
    f.id AS id, f.url AS url, f.title AS title, f.display_name AS display_name,
    f.description AS description, f.site_url AS site_url,
    f.poll_interval_minutes AS poll_interval_minutes,
    f.reader_mode_enabled AS reader_mode_enabled, f.is_active AS is_active,
    f.subscribed_at AS subscribed_at, f.last_fetched_at AS last_fetched_at,
    f.consecutive_errors AS consecutive_errors, f.last_error AS last_error,
    f.etag AS etag, f.last_modified AS last_modified
"""

_ITEM_COLS = """
    i.id AS id, i.guid AS guid, i.url AS url, i.title AS title,
    i.summary AS summary, i.content AS content, i.author AS author,
    i.word_count AS word_count, i.published_at AS published_at,
    i.fetched_at AS fetched_at, i.read AS read, i.starred AS starred,
    i.reader_content AS reader_content, i.enriched_at AS enriched_at
"""

_ITEM_LIST_COLS = """
    i.id AS id, i.guid AS guid, i.url AS url, i.title AS title,
    i.summary AS summary, i.author AS author,
    i.word_count AS word_count, i.published_at AS published_at,
    i.fetched_at AS fetched_at, i.read AS read, i.starred AS starred
"""


def _rows(result: kuzu.QueryResult | list[kuzu.QueryResult]) -> list[dict[str, Any]]:
    if isinstance(result, list):
        result = result[0]
    cols = result.get_column_names()
    rows: list[dict[str, Any]] = []
    while result.has_next():
        rows.append(dict(zip(cols, result.get_next(), strict=True)))
    return rows


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]*(?:>|$)", "", text)


def _make_excerpt(text: str, q: str, window: int = 20) -> str | None:
    """Return a ~window-word excerpt around the first query term match, with <em> tags."""
    if not text:
        return None
    clean = _strip_html(text)
    words = clean.split()
    if not words:
        return None
    terms = [t for t in q.lower().split() if t]
    for i, word in enumerate(words):
        if any(t in word.lower() for t in terms):
            start = max(0, i - 8)
            end = min(len(words), start + window)
            parts = []
            for w in words[start:end]:
                esc = _html.escape(w)
                parts.append(f"<em>{esc}</em>" if any(t in w.lower() for t in terms) else esc)
            result = " ".join(parts)
            if start > 0:
                result = "…" + result
            if end < len(words):
                result = result + "…"
            return result
    return None


def _match_source(item: dict[str, Any], q: str) -> list[str]:
    """Return which fields matched the query: 'content', 'note', or both."""
    terms = [t for t in q.lower().split() if t]
    sources: list[str] = []
    content_text = " ".join(
        filter(None, [item.get("title"), item.get("summary"), item.get("content")])
    ).lower()
    if any(t in content_text for t in terms):
        sources.append("content")
    note_body = (item.get("note_body") or "").lower()
    if note_body and any(t in note_body for t in terms):
        sources.append("note")
    return sources or ["content"]  # FTS matched — assume content if we can't tell


class GraphService:
    """Single access point for all Kuzu interactions.

    The REST API and MCP server import this; neither touches Kuzu directly.
    """

    def __init__(self, db_path: str) -> None:
        pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        self._conn_lock = threading.RLock()
        self._ensure_schema()

    def _execute(
        self, query: str, params: dict[str, Any] | None = None
    ) -> kuzu.QueryResult | list[kuzu.QueryResult]:
        with self._conn_lock:
            if params is not None:
                return self._conn.execute(query, params)
            return self._conn.execute(query)

    def _ensure_schema(self) -> None:
        tables = self._table_names()
        fresh = "Feed" not in tables
        if "Note" in tables and "item_id" in self._column_names("Note"):
            self._execute("ALTER TABLE Note RENAME TO _NoteLegacy")
        self._init_schema()
        if fresh:
            self.set_config_value("schema_version", _SCHEMA_VERSION)
            logger.debug("Fresh schema initialised at version %d", _SCHEMA_VERSION)
            return
        self._migrate()
        logger.debug("Schema ready")

    def _init_schema(self) -> None:
        self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Feed(
                url STRING,
                id STRING,
                title STRING,
                display_name STRING,
                description STRING,
                site_url STRING,
                poll_interval_minutes INT64,
                reader_mode_enabled BOOLEAN,
                is_active BOOLEAN DEFAULT true,
                subscribed_at TIMESTAMP,
                last_fetched_at TIMESTAMP,
                consecutive_errors INT64 DEFAULT 0,
                last_error STRING,
                etag STRING,
                last_modified STRING,
                PRIMARY KEY (url)
            )
        """)
        self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Item(
                guid STRING,
                id STRING,
                url STRING,
                title STRING,
                summary STRING,
                content STRING,
                author STRING,
                word_count INT64 DEFAULT 0,
                published_at TIMESTAMP,
                fetched_at TIMESTAMP,
                read BOOLEAN,
                starred BOOLEAN,
                reader_content STRING,
                reader_fetched_at TIMESTAMP,
                note_body STRING,
                enriched_at TIMESTAMP,
                PRIMARY KEY (guid)
            )
        """)
        self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Tag(
                name STRING,
                id STRING,
                PRIMARY KEY (name)
            )
        """)
        self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Note(
                id STRING,
                body STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                PRIMARY KEY (id)
            )
        """)
        self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Config(
                key STRING,
                value STRING,
                PRIMARY KEY (key)
            )
        """)
        self._execute("CREATE REL TABLE IF NOT EXISTS HAS_ITEM(FROM Feed TO Item)")
        self._execute("CREATE REL TABLE IF NOT EXISTS TAGGED(FROM Item TO Tag)")
        self._execute("CREATE REL TABLE IF NOT EXISTS FEED_TAGGED(FROM Feed TO Tag)")
        self._execute("CREATE REL TABLE IF NOT EXISTS HAS_NOTE(FROM Item TO Note)")
        self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Topic(
                id STRING,
                name STRING,
                item_count INT64,
                PRIMARY KEY (name)
            )
        """)
        self._execute("CREATE REL TABLE IF NOT EXISTS ABOUT(FROM Item TO Topic, score DOUBLE)")
        # FTS index — CREATE_FTS_INDEX has no IF NOT EXISTS so we suppress errors.
        # On existing v3 DBs the column doesn't exist yet; _migrate_to_v4 creates it.
        _fts_cypher = (
            "CALL CREATE_FTS_INDEX('Item', 'item_fts',"
            " ['title', 'summary', 'content', 'note_body'])"
        )
        try:
            self._execute(_fts_cypher)
        except RuntimeError as e:
            logger.warning("FTS index creation skipped in _init_schema: %s", e)

    def _table_names(self) -> set[str]:
        rows = _rows(self._execute("CALL show_tables() RETURN name"))
        return {row["name"] for row in rows}

    def _column_names(self, table: str) -> set[str]:
        # table must be a real table name: every caller passes an internal
        # constant, but interpolating it into the catalog call means a future
        # non-constant caller would inject. Fail loudly instead (#56).
        if table not in self._table_names():
            raise ValueError(f"Unknown table: {table!r}")
        rows = _rows(self._execute(f"CALL table_info('{table}') RETURN name"))
        return {row["name"] for row in rows}

    def _migrate(self) -> None:
        stored = self.get_config_values().get("schema_version", 1)
        if stored >= _SCHEMA_VERSION:
            return
        migrations = [
            (2, self._migrate_to_v2),
            (3, self._migrate_to_v3),
            (4, self._migrate_to_v4),
            (5, self._migrate_to_v5),
            (6, self._migrate_to_v6),
        ]
        for target, run in migrations:
            if target > stored:
                run()
                self.set_config_value("schema_version", target)
                logger.info("Schema migrated to version %d", target)

    def _migrate_to_v2(self) -> None:
        feed_cols = self._column_names("Feed")
        item_cols = self._column_names("Item")
        additions = [
            ("Feed", "id", "STRING", feed_cols),
            ("Feed", "display_name", "STRING", feed_cols),
            ("Feed", "subscribed_at", "TIMESTAMP", feed_cols),
            ("Feed", "is_active", "BOOLEAN DEFAULT true", feed_cols),
            ("Feed", "reader_mode_enabled", "BOOLEAN", feed_cols),
            ("Feed", "consecutive_errors", "INT64 DEFAULT 0", feed_cols),
            ("Feed", "last_error", "STRING", feed_cols),
            ("Item", "id", "STRING", item_cols),
            ("Item", "author", "STRING", item_cols),
            ("Item", "word_count", "INT64 DEFAULT 0", item_cols),
            ("Item", "reader_content", "STRING", item_cols),
            ("Item", "reader_fetched_at", "TIMESTAMP", item_cols),
        ]
        for table, column, decl, existing in additions:
            if column not in existing:
                self._execute(f"ALTER TABLE {table} ADD {column} {decl}")
        self._backfill_v2()

    def _backfill_v2(self) -> None:
        for table, key in (("Feed", "url"), ("Item", "guid")):
            rows = _rows(
                self._execute(f"MATCH (n:{table}) WHERE n.id IS NULL RETURN n.{key} AS key")
            )
            for row in rows:
                self._execute(
                    f"MATCH (n:{table}) WHERE n.{key} = $key SET n.id = $id",
                    {"key": row["key"], "id": str(uuid.uuid4())},
                )
        self._execute("MATCH (f:Feed) WHERE f.is_active IS NULL SET f.is_active = true")
        self._execute(
            "MATCH (f:Feed) WHERE f.consecutive_errors IS NULL SET f.consecutive_errors = 0"
        )
        self._execute(
            "MATCH (f:Feed) WHERE f.subscribed_at IS NULL SET f.subscribed_at = $now",
            {"now": datetime.now(UTC)},
        )

    def _migrate_to_v3(self) -> None:
        """Copy legacy Note rows (item_id FK) onto HAS_NOTE edges, then drop the legacy table."""
        if "_NoteLegacy" not in self._table_names():
            return
        legacy = _rows(
            self._execute(
                "MATCH (o:_NoteLegacy) RETURN o.item_id AS item_id, o.body AS body, "
                "o.created_at AS created_at, o.updated_at AS updated_at"
            )
        )
        migrated = 0
        for row in legacy:
            item_rows = _rows(
                self._execute(
                    "MATCH (i:Item) WHERE i.id = $item_id RETURN count(i) AS c",
                    {"item_id": row["item_id"]},
                )
            )
            if item_rows and item_rows[0].get("c", 0) > 0:
                self._execute(
                    """
                    MATCH (i:Item) WHERE i.id = $item_id
                    CREATE (i)-[:HAS_NOTE]->(:Note {
                        id: $id, body: $body,
                        created_at: $created_at, updated_at: $updated_at
                    })
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "item_id": row["item_id"],
                        "body": row["body"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    },
                )
                migrated += 1
        discarded = len(legacy) - migrated
        if discarded > 0:
            logger.warning(
                "Dropped %d orphaned legacy note(s) with no matching item during v3 migration",
                discarded,
            )
        self._execute("DROP TABLE _NoteLegacy")

    def _migrate_to_v4(self) -> None:
        if "note_body" not in self._column_names("Item"):
            self._execute("ALTER TABLE Item ADD note_body STRING")
        # CREATE_FTS_INDEX has no IF NOT EXISTS; suppress errors.
        # May fail on stripped legacy DBs missing v1 columns — _init_schema
        # will retry on the next open once all columns are present.
        try:
            self._execute(
                "CALL CREATE_FTS_INDEX('Item', 'item_fts',"
                " ['title', 'summary', 'content', 'note_body'])"
            )
        except RuntimeError as e:
            logger.warning("FTS index creation skipped in _migrate_to_v4: %s", e)
        # Backfill note_body from existing HAS_NOTE edges.
        self._execute("""
            MATCH (i:Item)-[:HAS_NOTE]->(n:Note)
            SET i.note_body = n.body
        """)

    def _migrate_to_v5(self) -> None:
        # Topic node table and ABOUT rel table are created by _init_schema (IF NOT EXISTS).
        # Items are enriched by FeedPoller._backfill_topics() on startup.
        pass

    def _migrate_to_v6(self) -> None:
        self._execute("ALTER TABLE Item ADD enriched_at TIMESTAMP DEFAULT NULL")

    def _exists(self, query: str, params: dict[str, Any]) -> bool:
        rows = _rows(self._execute(query, params))
        return bool(rows and rows[0].get("cnt", 0) > 0)

    # --- Config ---

    def get_config_values(self) -> dict[str, Any]:
        rows = _rows(self._execute("MATCH (c:Config) RETURN c.key AS key, c.value AS value"))
        return {row["key"]: json.loads(row["value"]) for row in rows}

    def set_config_value(self, key: str, value: Any) -> None:
        self._execute(
            "MERGE (c:Config {key: $key}) ON CREATE SET c.value = $value "
            "ON MATCH SET c.value = $value",
            {"key": key, "value": json.dumps(value)},
        )

    # --- Feeds ---

    def feed_exists(self, url: str) -> bool:
        return self._exists("MATCH (f:Feed {url: $url}) RETURN count(f) AS cnt", {"url": url})

    def feed_exists_by_id(self, feed_id: str) -> bool:
        return self._exists(
            "MATCH (f:Feed) WHERE f.id = $id RETURN count(f) AS cnt", {"id": feed_id}
        )

    def create_feed(
        self,
        url: str,
        title: str,
        description: str,
        site_url: str,
        display_name: str | None = None,
        poll_interval_minutes: int | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        feed_id = str(uuid.uuid4())
        self._execute(
            """
            CREATE (:Feed {
                url: $url,
                id: $id,
                title: $title,
                display_name: $display_name,
                description: $description,
                site_url: $site_url,
                poll_interval_minutes: $poll_interval_minutes,
                is_active: true,
                consecutive_errors: 0,
                subscribed_at: $subscribed_at
            })
            """,
            {
                "url": url,
                "id": feed_id,
                "title": title,
                "display_name": display_name,
                "description": description,
                "site_url": _safe_url(site_url),
                "poll_interval_minutes": poll_interval_minutes,
                "subscribed_at": datetime.now(UTC),
            },
        )
        if tags:
            self.set_feed_tags(feed_id, tags)
        feed = self.get_feed(feed_id)
        assert feed is not None
        return feed

    def _feed_query(self, where: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        result = self._execute(
            f"""
            MATCH (f:Feed)
            {where}
            OPTIONAL MATCH (f)-[:HAS_ITEM]->(i:Item)
            RETURN {_FEED_COLS},
                   count(i) AS item_count,
                   sum(CASE WHEN i.read = false THEN 1 ELSE 0 END) AS unread_count
            ORDER BY coalesce(display_name, title) ASC
            """,
            params,
        )
        feeds = _rows(result)
        tag_rows = _rows(
            self._execute(
                f"""
                MATCH (f:Feed)
                {where}
                MATCH (f)-[:FEED_TAGGED]->(t:Tag)
                RETURN f.id AS feed_id, t.name AS name
                ORDER BY name
                """,
                params,
            )
        )
        tags_by_feed: dict[str, list[str]] = {}
        for row in tag_rows:
            tags_by_feed.setdefault(row["feed_id"], []).append(row["name"])
        for feed in feeds:
            feed["unread_count"] = int(feed["unread_count"] or 0)
            feed["tags"] = tags_by_feed.get(feed["id"], [])
        return feeds

    def get_feed(self, feed_id: str) -> dict[str, Any] | None:
        feeds = self._feed_query("WHERE f.id = $id", {"id": feed_id})
        return feeds[0] if feeds else None

    def get_feed_by_url(self, url: str) -> dict[str, Any] | None:
        feeds = self._feed_query("WHERE f.url = $url", {"url": url})
        return feeds[0] if feeds else None

    def list_feeds(self) -> list[dict[str, Any]]:
        return self._feed_query("", {})

    def update_feed(self, feed_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not self.feed_exists_by_id(feed_id):
            return None
        allowed = {"display_name", "poll_interval_minutes", "reader_mode_enabled", "is_active"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if updates:
            set_clause = ", ".join(f"f.{k} = ${k}" for k in updates)
            self._execute(
                f"MATCH (f:Feed) WHERE f.id = $id SET {set_clause}",
                {"id": feed_id, **updates},
            )
        if "tags" in fields and fields["tags"] is not None:
            self.set_feed_tags(feed_id, fields["tags"])
        return self.get_feed(feed_id)

    def set_feed_tags(self, feed_id: str, tags: list[str]) -> None:
        self._execute(
            "MATCH (f:Feed)-[r:FEED_TAGGED]->(:Tag) WHERE f.id = $id DELETE r",
            {"id": feed_id},
        )
        for name in tags:
            tag = self.ensure_tag(name)
            self._execute(
                """
                MATCH (f:Feed), (t:Tag {name: $name})
                WHERE f.id = $id
                MERGE (f)-[:FEED_TAGGED]->(t)
                """,
                {"id": feed_id, "name": tag["name"]},
            )

    def list_feeds_for_polling(self) -> list[dict[str, Any]]:
        result = self._execute(
            f"""
            MATCH (f:Feed)
            WHERE f.is_active = true
            RETURN {_FEED_COLS}
            """
        )
        return _rows(result)

    def update_feed_poll_metadata(
        self,
        url: str,
        last_fetched_at: datetime,
        etag: str | None,
        last_modified: str | None,
        error: str | None,
    ) -> None:
        self._execute(
            """
            MATCH (f:Feed {url: $url})
            SET f.last_fetched_at = $last_fetched_at,
                f.etag = $etag,
                f.last_modified = $last_modified,
                f.last_error = $error,
                f.consecutive_errors =
                    CASE WHEN $error IS NULL THEN 0 ELSE f.consecutive_errors + 1 END
            """,
            {
                "url": url,
                "last_fetched_at": last_fetched_at,
                "etag": etag,
                "last_modified": last_modified,
                "error": error,
            },
        )

    def delete_feed(self, feed_id: str) -> bool:
        if not self.feed_exists_by_id(feed_id):
            return False
        # Items are kept (read/starred state preserved); only the feed and its edges go
        self._execute("MATCH (f:Feed) WHERE f.id = $id DETACH DELETE f", {"id": feed_id})
        return True

    # --- Items ---

    def item_exists(self, guid: str) -> bool:
        return self._exists("MATCH (i:Item {guid: $guid}) RETURN count(i) AS cnt", {"guid": guid})

    def create_item(
        self,
        feed_url: str,
        guid: str,
        url: str,
        title: str,
        summary: str,
        content: str,
        author: str,
        word_count: int,
        published_at: datetime | None,
        fetched_at: datetime,
    ) -> str | None:
        """Create an Item node and HAS_ITEM edge if they don't exist.

        Item node creation is skipped if the guid already exists (e.g. shared across
        feeds, or resubscription after delete). The HAS_ITEM edge is always created
        if absent. Returns the new item's id, or None if the item already existed.
        """
        item_id: str | None = None
        if not self.item_exists(guid):
            if not summary and content:
                clean = _strip_html(content)
                summary = clean[:300].rsplit(" ", 1)[0] + "…" if len(clean) > 300 else clean
            item_id = str(uuid.uuid4())
            self._execute(
                """
                CREATE (:Item {
                    guid: $guid,
                    id: $id,
                    url: $url,
                    title: $title,
                    summary: $summary,
                    content: $content,
                    author: $author,
                    word_count: $word_count,
                    published_at: $published_at,
                    fetched_at: $fetched_at,
                    read: false,
                    starred: false
                })
                """,
                {
                    "guid": guid,
                    "id": item_id,
                    "url": _safe_url(url),
                    "title": title,
                    "summary": summary,
                    "content": content,
                    "author": author,
                    "word_count": word_count,
                    "published_at": published_at,
                    "fetched_at": fetched_at,
                },
            )
        self._execute(
            """
            MATCH (f:Feed {url: $feed_url}), (i:Item {guid: $guid})
            MERGE (f)-[:HAS_ITEM]->(i)
            """,
            {"feed_url": feed_url, "guid": guid},
        )
        return item_id

    def _item_filters(
        self,
        feed_id: str | None,
        tag: str | None,
        unread_only: bool,
        starred_only: bool,
        since: datetime | None,
        until: datetime | None,
    ) -> tuple[str, dict[str, Any]]:
        """Build the MATCH...WHERE prefix (feed bound as f, item as i) for item queries."""
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if tag is not None:
            params["tag"] = tag
        if unread_only:
            clauses.append("i.read = false")
        if starred_only:
            clauses.append("i.starred = true")
        if since is not None:
            clauses.append("i.published_at >= $since")
            params["since"] = since
        if until is not None:
            clauses.append("i.published_at <= $until")
            params["until"] = until

        # Starred and tagged views are user-curated: items stay visible after
        # their feed is removed. Feed-derived views require a live feed edge.
        if feed_id is not None:
            match = "MATCH (f:Feed)-[:HAS_ITEM]->(i:Item)"
            if tag is not None:
                match += " MATCH (i)-[:TAGGED]->(t:Tag {name: $tag})"
            clauses.append("f.id = $feed_id")
            params["feed_id"] = feed_id
            optional = ""
        elif starred_only or tag is not None:
            match = (
                "MATCH (i:Item)-[:TAGGED]->(t:Tag {name: $tag})"
                if tag is not None
                else "MATCH (i:Item)"
            )
            # WHERE must precede OPTIONAL MATCH or it would filter only the
            # optional pattern
            optional = " OPTIONAL MATCH (f:Feed)-[:HAS_ITEM]->(i)"
        else:
            match = "MATCH (f:Feed)-[:HAS_ITEM]->(i:Item)"
            optional = ""

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return match + where + optional, params

    def list_items(
        self,
        feed_id: str | None = None,
        tag: str | None = None,
        unread_only: bool = False,
        starred_only: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        prefix, params = self._item_filters(feed_id, tag, unread_only, starred_only, since, until)
        count_rows = _rows(self._execute(f"{prefix} RETURN count(DISTINCT i) AS total", params))
        total = int(count_rows[0]["total"]) if count_rows else 0
        result = self._execute(
            f"""
            {prefix}
            WITH i, collect(f)[1] AS f
            RETURN {_ITEM_LIST_COLS}, f.id AS feed_id,
                   coalesce(f.display_name, f.title) AS feed_title
            ORDER BY coalesce(i.published_at, i.fetched_at) DESC
            SKIP $offset LIMIT $limit
            """,
            {**params, "offset": offset, "limit": limit},
        )
        items = _rows(result)
        tags_by_guid = self._tags_for_items([i["guid"] for i in items])
        for item in items:
            item["tags"] = tags_by_guid.get(item["guid"], [])
        return items, total

    def list_items_cursor(
        self,
        feed_id: str | None = None,
        tag: str | None = None,
        unread_only: bool = False,
        starred_only: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        cursor_ts: datetime | None = None,
        cursor_guid: str | None = None,
    ) -> list[dict[str, Any]]:
        """Keyset-paginated item list. cursor_ts+cursor_guid encode the last-seen position."""
        prefix, params = self._item_filters(feed_id, tag, unread_only, starred_only, since, until)
        cursor_clause = ""
        if cursor_ts is not None and cursor_guid is not None:
            # Insert a WITH bridge so the cursor predicate is always a fresh WHERE,
            # regardless of whether the prefix ends with WHERE or OPTIONAL MATCH.
            cursor_clause = (
                "\nWITH i, f"
                "\nWHERE (coalesce(i.published_at, i.fetched_at) < $cursor_ts"
                " OR (coalesce(i.published_at, i.fetched_at) = $cursor_ts"
                " AND i.guid > $cursor_guid))"
            )
            params["cursor_ts"] = cursor_ts
            params["cursor_guid"] = cursor_guid
        result = self._execute(
            f"""
            {prefix}{cursor_clause}
            WITH i, collect(f)[1] AS f
            RETURN {_ITEM_LIST_COLS}, f.id AS feed_id,
                   coalesce(f.display_name, f.title) AS feed_title
            ORDER BY coalesce(i.published_at, i.fetched_at) DESC, i.guid ASC
            LIMIT $limit
            """,
            {**params, "limit": limit},
        )
        items = _rows(result)
        tags_by_guid = self._tags_for_items([i["guid"] for i in items])
        for item in items:
            item["tags"] = tags_by_guid.get(item["guid"], [])
        return items

    def search_items(
        self,
        q: str,
        feed_id: str | None = None,
        tag: str | None = None,
        author: str | None = None,
        unread_only: bool = False,
        starred_only: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: dict[str, Any] = {"q": q, "offset": offset, "limit": limit}

        if feed_id is not None:
            feed_clause = " MATCH (f:Feed)-[:HAS_ITEM]->(i)"
            clauses.append("f.id = $feed_id")
            params["feed_id"] = feed_id
        else:
            feed_clause = " OPTIONAL MATCH (f:Feed)-[:HAS_ITEM]->(i)"

        tag_clause = ""
        if tag is not None:
            tag_clause = " MATCH (i)-[:TAGGED]->(t:Tag {name: $tag})"
            params["tag"] = tag

        if author is not None:
            clauses.append("i.author = $author")
            params["author"] = author
        if unread_only:
            clauses.append("i.read = false")
        if starred_only:
            clauses.append("i.starred = true")
        if since is not None:
            clauses.append("i.published_at >= $since")
            params["since"] = since
        if until is not None:
            clauses.append("i.published_at <= $until")
            params["until"] = until

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        prefix = (
            f"CALL QUERY_FTS_INDEX('Item', 'item_fts', $q) "
            f"WITH node AS i, score{feed_clause}{tag_clause}{where}"
        )

        # count query must not include $offset/$limit — Kuzu rejects unused params
        count_params = {k: v for k, v in params.items() if k not in ("offset", "limit")}
        count_rows = _rows(
            self._execute(f"{prefix} RETURN count(DISTINCT i) AS total", count_params)
        )
        total = int(count_rows[0]["total"]) if count_rows else 0

        rows = _rows(
            self._execute(
                f"""
                {prefix}
                WITH i, score, collect(f)[1] AS f
                RETURN i.id AS id, i.guid AS guid, i.url AS url, i.title AS title,
                       i.summary AS summary, i.content AS content,
                       i.note_body AS note_body, i.author AS author,
                       i.published_at AS published_at, i.fetched_at AS fetched_at,
                       i.read AS read, i.starred AS starred, i.word_count AS word_count,
                       score,
                       f.id AS feed_id, coalesce(f.display_name, f.title) AS feed_title
                ORDER BY score DESC, i.fetched_at DESC, i.guid ASC
                SKIP $offset LIMIT $limit
                """,
                params,
            )
        )

        for item in rows:
            # Try each field in priority order; use first field that yields a match
            excerpt = None
            for field in ("summary", "content", "title"):
                excerpt = _make_excerpt(item.get(field) or "", q)
                if excerpt is not None:
                    break
            item["excerpt"] = excerpt
            item["note_excerpt"] = _make_excerpt(item.get("note_body") or "", q)
            item["match_source"] = _match_source(item, q)

        return rows, total

    def _tags_for_items(self, guids: list[str]) -> dict[str, list[str]]:
        if not guids:
            return {}
        rows = _rows(
            self._execute(
                """
                UNWIND $guids AS g
                MATCH (i:Item {guid: g})-[:TAGGED]->(t:Tag)
                RETURN i.guid AS guid, t.name AS name
                ORDER BY name
                """,
                {"guids": guids},
            )
        )
        tags: dict[str, list[str]] = {}
        for row in rows:
            tags.setdefault(row["guid"], []).append(row["name"])
        return tags

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        result = self._execute(
            f"""
            MATCH (i:Item)
            WHERE i.id = $id
            OPTIONAL MATCH (f:Feed)-[:HAS_ITEM]->(i)
            RETURN {_ITEM_COLS}, f.id AS feed_id,
                   coalesce(f.display_name, f.title) AS feed_title
            LIMIT 1
            """,
            {"id": item_id},
        )
        rows = _rows(result)
        if not rows:
            return None
        item = rows[0]
        item["tags"] = self._tags_for_items([item["guid"]]).get(item["guid"], [])
        item["note"] = self.get_note(item_id)
        return item

    def update_item_state(
        self, item_id: str, read: bool | None = None, starred: bool | None = None
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        if read is not None:
            updates["read"] = read
        if starred is not None:
            updates["starred"] = starred
        if updates:
            set_clause = ", ".join(f"i.{k} = ${k}" for k in updates)
            self._execute(
                f"MATCH (i:Item) WHERE i.id = $id SET {set_clause}",
                {"id": item_id, **updates},
            )
        return self.get_item(item_id)

    def mark_read_bulk(self, feed_id: str | None = None, before: datetime | None = None) -> int:
        match = "MATCH (i:Item)"
        clauses = ["i.read = false"]
        params: dict[str, Any] = {}
        if feed_id is not None:
            match = "MATCH (f:Feed)-[:HAS_ITEM]->(i:Item)"
            clauses.append("f.id = $feed_id")
            params["feed_id"] = feed_id
        if before is not None:
            clauses.append("coalesce(i.published_at, i.fetched_at) < $before")
            params["before"] = before
        where = "WHERE " + " AND ".join(clauses)
        count_rows = _rows(self._execute(f"{match} {where} RETURN count(i) AS total", params))
        total = int(count_rows[0]["total"]) if count_rows else 0
        self._execute(f"{match} {where} SET i.read = true", params)
        return total

    def save_reader_content(self, item_id: str, content: str, fetched_at: datetime) -> None:
        self._execute(
            """
            MATCH (i:Item) WHERE i.id = $id
            SET i.reader_content = $content, i.reader_fetched_at = $fetched_at
            """,
            {"id": item_id, "content": content, "fetched_at": fetched_at},
        )

    def _item_guid(self, item_id: str) -> str | None:
        rows = _rows(
            self._execute("MATCH (i:Item) WHERE i.id = $id RETURN i.guid AS guid", {"id": item_id})
        )
        return rows[0]["guid"] if rows else None

    # --- Tags ---

    def ensure_tag(self, name: str) -> dict[str, Any]:
        rows = _rows(
            self._execute(
                """
                MERGE (t:Tag {name: $name})
                ON CREATE SET t.id = $id
                RETURN t.id AS id, t.name AS name
                """,
                {"name": name.strip(), "id": str(uuid.uuid4())},
            )
        )
        return rows[0]

    def get_tag(self, tag_id: str) -> dict[str, Any] | None:
        rows = _rows(
            self._execute(
                "MATCH (t:Tag) WHERE t.id = $id RETURN t.id AS id, t.name AS name",
                {"id": tag_id},
            )
        )
        return rows[0] if rows else None

    def list_tags(self) -> list[dict[str, Any]]:
        result = self._execute(
            """
            MATCH (t:Tag)
            OPTIONAL MATCH (i:Item)-[:TAGGED]->(t)
            RETURN t.id AS id, t.name AS name, count(i) AS item_count
            ORDER BY name ASC
            """
        )
        return _rows(result)

    def delete_tag(self, tag_id: str) -> bool:
        if self.get_tag(tag_id) is None:
            return False
        self._execute("MATCH (t:Tag) WHERE t.id = $id DETACH DELETE t", {"id": tag_id})
        return True

    def tag_item(self, item_id: str, name: str) -> dict[str, Any] | None:
        guid = self._item_guid(item_id)
        if guid is None:
            return None
        tag = self.ensure_tag(name)
        self._execute(
            """
            MATCH (i:Item {guid: $guid}), (t:Tag {name: $name})
            MERGE (i)-[:TAGGED]->(t)
            """,
            {"guid": guid, "name": tag["name"]},
        )
        return tag

    def untag_item(self, item_id: str, tag_id: str) -> bool:
        pattern = "MATCH (i:Item)-[r:TAGGED]->(t:Tag) WHERE i.id = $item_id AND t.id = $tag_id"
        params = {"item_id": item_id, "tag_id": tag_id}
        if not self._exists(f"{pattern} RETURN count(r) AS cnt", params):
            return False
        self._execute(f"{pattern} DELETE r", params)
        return True

    # --- Notes ---

    def get_note(self, item_id: str) -> dict[str, Any] | None:
        rows = _rows(
            self._execute(
                """
                MATCH (i:Item)-[:HAS_NOTE]->(n:Note) WHERE i.id = $item_id
                RETURN n.body AS body, n.created_at AS created_at, n.updated_at AS updated_at
                """,
                {"item_id": item_id},
            )
        )
        return rows[0] if rows else None

    def put_note(self, item_id: str, body: str) -> dict[str, Any] | None:
        if self._item_guid(item_id) is None:
            return None
        now = datetime.now(UTC)
        if self.get_note(item_id) is not None:
            self._execute(
                """
                MATCH (i:Item)-[:HAS_NOTE]->(n:Note) WHERE i.id = $item_id
                SET n.body = $body, n.updated_at = $now
                """,
                {"item_id": item_id, "body": body, "now": now},
            )
        else:
            self._execute(
                """
                MATCH (i:Item) WHERE i.id = $item_id
                CREATE (i)-[:HAS_NOTE]->(:Note {
                    id: $id, body: $body, created_at: $now, updated_at: $now
                })
                """,
                {"item_id": item_id, "id": str(uuid.uuid4()), "body": body, "now": now},
            )
        self._execute(
            "MATCH (i:Item) WHERE i.id = $id SET i.note_body = $body",
            {"id": item_id, "body": body},
        )
        return self.get_note(item_id)

    def delete_note(self, item_id: str) -> bool:
        if self.get_note(item_id) is None:
            return False
        self._execute(
            "MATCH (i:Item)-[:HAS_NOTE]->(n:Note) WHERE i.id = $item_id DETACH DELETE n",
            {"item_id": item_id},
        )
        self._execute(
            "MATCH (i:Item) WHERE i.id = $id SET i.note_body = NULL",
            {"id": item_id},
        )
        return True

    # --- Data portability ---

    def export_data(self) -> dict[str, Any]:
        """Return a full backup dict (version 1 format). Excludes schema_version from config."""
        feeds_raw = self.list_feeds()
        feeds = [
            {
                "id": f["id"],
                "url": f["url"],
                "title": f["title"],
                "display_name": f["display_name"],
                "description": f["description"],
                "site_url": f["site_url"],
                "poll_interval_minutes": f["poll_interval_minutes"],
                "reader_mode_enabled": f["reader_mode_enabled"],
                "subscribed_at": f["subscribed_at"].isoformat() if f["subscribed_at"] else None,
                "tags": f["tags"],
            }
            for f in feeds_raw
        ]

        item_rows = _rows(
            self._execute("""
                MATCH (i:Item)
                OPTIONAL MATCH (f:Feed)-[:HAS_ITEM]->(i)
                RETURN i.id AS id, i.guid AS guid, i.url AS url, i.title AS title,
                       i.author AS author, i.word_count AS word_count,
                       i.published_at AS published_at, i.fetched_at AS fetched_at,
                       i.read AS read, i.starred AS starred, f.url AS feed_url
                ORDER BY i.fetched_at ASC
            """)
        )
        item_tag_rows = _rows(
            self._execute(
                "MATCH (i:Item)-[:TAGGED]->(t:Tag) RETURN i.id AS item_id, t.name AS tag_name"
            )
        )
        tags_by_item: dict[str, list[str]] = {}
        for row in item_tag_rows:
            tags_by_item.setdefault(row["item_id"], []).append(row["tag_name"])
        items = [
            {
                "id": r["id"],
                "guid": r["guid"],
                "url": r["url"],
                "title": r["title"],
                "author": r["author"],
                "word_count": r["word_count"] or 0,
                "published_at": r["published_at"].isoformat() if r["published_at"] else None,
                "fetched_at": r["fetched_at"].isoformat() if r["fetched_at"] else None,
                "read": r["read"] or False,
                "starred": r["starred"] or False,
                "feed_url": r["feed_url"],
                "tags": tags_by_item.get(r["id"], []),
            }
            for r in item_rows
        ]

        note_rows = _rows(
            self._execute("""
                MATCH (i:Item)-[:HAS_NOTE]->(n:Note)
                RETURN i.id AS item_id, n.body AS body,
                       n.created_at AS created_at, n.updated_at AS updated_at
            """)
        )
        notes = [
            {
                "item_id": n["item_id"],
                "body": n["body"],
                "created_at": n["created_at"].isoformat() if n["created_at"] else None,
                "updated_at": n["updated_at"].isoformat() if n["updated_at"] else None,
            }
            for n in note_rows
        ]

        tag_nodes = _rows(
            self._execute("MATCH (t:Tag) RETURN t.id AS id, t.name AS name ORDER BY name")
        )
        tags = [{"id": t["id"], "name": t["name"]} for t in tag_nodes]

        config = {k: v for k, v in self.get_config_values().items() if k != "schema_version"}

        topic_rows = _rows(
            self._execute("MATCH (t:Topic) RETURN t.id AS id, t.name AS name ORDER BY name")
        )
        topics_export = [{"id": str(t["id"]), "name": str(t["name"])} for t in topic_rows]

        about_rows = _rows(
            self._execute(
                "MATCH (i:Item)-[a:ABOUT]->(t:Topic) "
                "RETURN i.guid AS item_guid, t.name AS topic_name, a.score AS score"
            )
        )
        about_export = [
            {"item_guid": r["item_guid"], "topic_name": r["topic_name"], "score": float(r["score"])}
            for r in about_rows
        ]

        return {
            "version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "feeds": feeds,
            "items": items,
            "notes": notes,
            "tags": tags,
            "topics": topics_export,
            "about_edges": about_export,
            "config": config,
        }

    def restore_data(self, backup: dict[str, Any]) -> dict[str, Any]:
        """Clear all data and re-insert from backup. Schema is never touched.

        Kuzu transactions are connection-scoped, and every thread shares this
        one `kuzu.Connection`, so a statement issued by another thread while
        this transaction is open would execute inside it — silently
        entangling an unrelated write, or exposing a half-cleared graph to a
        concurrent read (#124). This method therefore holds `_conn_lock` for
        the *entire* transaction, not just around BEGIN/COMMIT/ROLLBACK: the
        `with` block here stays entered across every nested `_execute` call
        `_restore_data_inner` makes, so no other thread's `_execute` (which
        acquires the same lock) can run until this transaction has committed
        or rolled back. This relies on `_conn_lock` being a `threading.RLock`
        — the reentrant acquire from nested `_execute` calls on this same
        thread must succeed immediately without releasing the lock to other
        threads. Do not change `_conn_lock` to a plain `threading.Lock`; that
        would deadlock here (and reintroduce this issue's failure mode if
        someone "fixed" the deadlock by moving the lock back inside
        `_execute`).
        """
        with self._conn_lock:
            self._execute("BEGIN TRANSACTION")
            try:
                result = self._restore_data_inner(backup)
                self._execute("COMMIT")
                return result
            except Exception:
                self._execute("ROLLBACK")
                raise

    def _restore_data_inner(self, backup: dict[str, Any]) -> dict[str, Any]:
        # Delete Topic edges and nodes before clearing the rest (order matters
        # for referential integrity)
        self._execute("MATCH ()-[r:ABOUT]->() DELETE r")
        self._execute("MATCH (t:Topic) DELETE t")
        # Delete edges before nodes (order is mandatory).
        for rel in ("TAGGED", "FEED_TAGGED", "HAS_NOTE", "HAS_ITEM"):
            self._execute(f"MATCH ()-[r:{rel}]->() DELETE r")
        for node in ("Note", "Item", "Tag", "Feed", "Config"):
            self._execute(f"MATCH (n:{node}) DETACH DELETE n")

        # Config — restore allowlisted keys then stamp current schema_version.
        for key, value in backup.get("config", {}).items():
            if key in _ALLOWED_CONFIG_KEYS:
                self.set_config_value(key, value)
            else:
                logger.warning("restore_data: skipping unknown config key %r", key)
        self.set_config_value("schema_version", _SCHEMA_VERSION)

        # Tags (with original UUIDs so tag-name lookups stay consistent).
        for tag in backup.get("tags", []):
            self._execute(
                "CREATE (:Tag {id: $id, name: $name})",
                {"id": tag["id"], "name": tag["name"]},
            )

        # Feeds (no tag edges yet).
        for feed in backup.get("feeds", []):
            self._execute(
                """
                CREATE (:Feed {
                    url: $url, id: $id, title: $title, display_name: $display_name,
                    description: $description, site_url: $site_url,
                    poll_interval_minutes: $poll_interval_minutes,
                    reader_mode_enabled: $reader_mode_enabled,
                    is_active: true, consecutive_errors: 0,
                    subscribed_at: $subscribed_at
                })
                """,
                {
                    "url": feed["url"],
                    "id": feed["id"],
                    "title": feed.get("title") or "",
                    "display_name": feed.get("display_name"),
                    "description": feed.get("description") or "",
                    "site_url": _safe_url(feed.get("site_url") or ""),
                    "poll_interval_minutes": feed.get("poll_interval_minutes"),
                    "reader_mode_enabled": feed.get("reader_mode_enabled"),
                    "subscribed_at": (
                        datetime.fromisoformat(feed["subscribed_at"])
                        if feed.get("subscribed_at")
                        else datetime.now(UTC)
                    ),
                },
            )

        # Items with HAS_ITEM edges.
        for item in backup.get("items", []):
            self._execute(
                """
                CREATE (:Item {
                    guid: $guid, id: $id, url: $url, title: $title,
                    summary: $summary, content: $content, author: $author,
                    word_count: $word_count, published_at: $published_at,
                    fetched_at: $fetched_at, read: $read, starred: $starred
                })
                """,
                {
                    "guid": item["guid"],
                    "id": item["id"],
                    "url": _safe_url(item.get("url") or ""),
                    "title": item.get("title") or "",
                    "summary": "",
                    "content": "",
                    "author": item.get("author") or "",
                    "word_count": item.get("word_count") or 0,
                    "published_at": (
                        datetime.fromisoformat(item["published_at"])
                        if item.get("published_at")
                        else None
                    ),
                    "fetched_at": (
                        datetime.fromisoformat(item["fetched_at"])
                        if item.get("fetched_at")
                        else datetime.now(UTC)
                    ),
                    "read": item.get("read", False),
                    "starred": item.get("starred", False),
                },
            )
            if item.get("feed_url"):
                self._execute(
                    "MATCH (f:Feed {url: $feed_url}), (i:Item {id: $id}) "
                    "CREATE (f)-[:HAS_ITEM]->(i)",
                    {"feed_url": item["feed_url"], "id": item["id"]},
                )

        # Notes with HAS_NOTE edges; also sync note_body for FTS.
        for note in backup.get("notes", []):
            self._execute(
                """
                MATCH (i:Item {id: $item_id})
                CREATE (i)-[:HAS_NOTE]->(:Note {
                    id: $note_id, body: $body,
                    created_at: $created_at, updated_at: $updated_at
                })
                """,
                {
                    "item_id": note["item_id"],
                    "note_id": str(uuid.uuid4()),
                    "body": note["body"],
                    "created_at": (
                        datetime.fromisoformat(note["created_at"])
                        if note.get("created_at")
                        else datetime.now(UTC)
                    ),
                    "updated_at": (
                        datetime.fromisoformat(note["updated_at"])
                        if note.get("updated_at")
                        else datetime.now(UTC)
                    ),
                },
            )
            self._execute(
                "MATCH (i:Item) WHERE i.id = $id SET i.note_body = $body",
                {"id": note["item_id"], "body": note["body"]},
            )

        # Tag edges.
        for feed in backup.get("feeds", []):
            for tag_name in feed.get("tags", []):
                self._execute(
                    "MATCH (f:Feed {id: $id}), (t:Tag {name: $name}) MERGE (f)-[:FEED_TAGGED]->(t)",
                    {"id": feed["id"], "name": tag_name},
                )
        for item in backup.get("items", []):
            for tag_name in item.get("tags", []):
                self._execute(
                    "MATCH (i:Item {id: $id}), (t:Tag {name: $name}) MERGE (i)-[:TAGGED]->(t)",
                    {"id": item["id"], "name": tag_name},
                )

        # Topics (insert with item_count = 0; recomputed below from ABOUT edges).
        for topic in backup.get("topics", []):
            self._execute(
                "MERGE (t:Topic {name: $name}) ON CREATE SET t.id = $id, t.item_count = 0",
                {"name": topic["name"], "id": topic["id"]},
            )

        # ABOUT edges — insert after all Items and Topics exist.
        for edge in backup.get("about_edges", []):
            self._execute(
                "MATCH (i:Item {guid: $item_guid}), (t:Topic {name: $topic_name}) "
                "CREATE (i)-[:ABOUT {score: $score}]->(t)",
                {
                    "item_guid": edge["item_guid"],
                    "topic_name": edge["topic_name"],
                    "score": float(edge["score"]),
                },
            )

        # Recompute item_count for each Topic from actual ABOUT edge counts.
        topic_counts = _rows(
            self._execute(
                "MATCH (i:Item)-[:ABOUT]->(t:Topic) RETURN t.name AS name, count(i) AS cnt"
            )
        )
        for row in topic_counts:
            self._execute(
                "MATCH (t:Topic {name: $name}) SET t.item_count = $cnt",
                {"name": row["name"], "cnt": int(row["cnt"])},
            )

        feed_count = int(_rows(self._execute("MATCH (f:Feed) RETURN count(f) AS n"))[0]["n"])
        item_count = int(_rows(self._execute("MATCH (i:Item) RETURN count(i) AS n"))[0]["n"])
        return {
            "feeds": feed_count,
            "items": item_count,
            "notes": len(backup.get("notes", [])),
            "tags": len(backup.get("tags", [])),
        }

    # --- Topics ---

    def _upsert_topic(self, name: str) -> str:
        """Create Topic if it doesn't exist; increment item_count if it does. Returns UUID id."""
        topic_id = str(uuid.uuid4())
        self._execute(
            "MERGE (t:Topic {name: $name}) "
            "ON CREATE SET t.id = $id, t.item_count = 1 "
            "ON MATCH SET t.item_count = t.item_count + 1",
            {"name": name, "id": topic_id},
        )
        rows = _rows(
            self._execute(
                "MATCH (t:Topic {name: $name}) RETURN t.id AS id",
                {"name": name},
            )
        )
        return str(rows[0]["id"])

    def link_item_topic(self, item_id: str, topic_name: str, score: float) -> None:
        """Upsert topic and create ABOUT edge from Item to Topic; no-op if edge already exists."""
        already = self._exists(
            "MATCH (i:Item {id: $item_id})-[:ABOUT]->(t:Topic {name: $topic_name}) "
            "RETURN count(*) AS cnt",
            {"item_id": item_id, "topic_name": topic_name},
        )
        if not already:
            self._upsert_topic(topic_name)
            self._execute(
                "MATCH (i:Item {id: $item_id}), (t:Topic {name: $topic_name}) "
                "CREATE (i)-[:ABOUT {score: $score}]->(t)",
                {"item_id": item_id, "topic_name": topic_name, "score": score},
            )

    def enrich_item(self, item_id: str, keywords: list[tuple[str, float]]) -> None:
        """Link keywords to item as topics, then mark item as enriched."""
        for name, score in keywords:
            self.link_item_topic(item_id, name, score)
        self._execute(
            "MATCH (i:Item {id: $id}) SET i.enriched_at = $ts",
            {"id": item_id, "ts": datetime.now(UTC)},
        )

    def get_unenriched_items(self) -> list[dict[str, Any]]:
        """Return all items not yet enriched (enriched_at IS NULL)."""
        return _rows(
            self._execute(
                "MATCH (i:Item) WHERE i.enriched_at IS NULL "
                "RETURN i.id AS id, i.title AS title, "
                "i.summary AS summary, i.content AS content"
            )
        )

    def get_topics(self, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        count_rows = _rows(self._execute("MATCH (t:Topic) RETURN count(t) AS total"))
        total = int(count_rows[0]["total"]) if count_rows else 0
        rows = _rows(
            self._execute(
                "MATCH (t:Topic) "
                "RETURN t.id AS id, t.name AS name, t.item_count AS item_count "
                "ORDER BY t.item_count DESC "
                "SKIP $offset LIMIT $limit",
                {"offset": offset, "limit": limit},
            )
        )
        return rows, total

    def get_topic(self, topic_id: str) -> dict[str, Any] | None:
        rows = _rows(
            self._execute(
                "MATCH (t:Topic) WHERE t.id = $id "
                "RETURN t.id AS id, t.name AS name, t.item_count AS item_count",
                {"id": topic_id},
            )
        )
        if not rows:
            return None
        topic = rows[0]
        item_rows = _rows(
            self._execute(
                "MATCH (i:Item)-[a:ABOUT]->(t:Topic) WHERE t.id = $id "
                "OPTIONAL MATCH (f:Feed)-[:HAS_ITEM]->(i) "
                "RETURN i.id AS id, i.title AS title, i.url AS url, "
                "f.id AS feed_id, coalesce(f.display_name, f.title) AS feed_title "
                "ORDER BY a.score ASC LIMIT 20",
                {"id": topic_id},
            )
        )
        topic["items"] = [
            {
                "id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "feed": (
                    {"id": r["feed_id"], "title": r["feed_title"]} if r.get("feed_id") else None
                ),
            }
            for r in item_rows
        ]
        return topic

    def get_item_topics(self, item_id: str) -> list[dict[str, Any]]:
        return [
            {"id": str(r["id"]), "name": str(r["name"]), "score": float(r["score"])}
            for r in _rows(
                self._execute(
                    "MATCH (i:Item {id: $item_id})-[a:ABOUT]->(t:Topic) "
                    "RETURN t.id AS id, t.name AS name, a.score AS score "
                    "ORDER BY a.score ASC",
                    {"item_id": item_id},
                )
            )
        ]

    def close(self) -> None:
        self._conn.close()
        self._db.close()
