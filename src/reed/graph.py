# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import kuzu

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 2

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
    i.reader_content AS reader_content
"""

# Columns added after M1; applied via ALTER TABLE for databases created before
# schema version 2.
_V2_MIGRATIONS = [
    "ALTER TABLE Feed ADD id STRING",
    "ALTER TABLE Feed ADD display_name STRING",
    "ALTER TABLE Feed ADD subscribed_at TIMESTAMP",
    "ALTER TABLE Feed ADD is_active BOOLEAN DEFAULT true",
    "ALTER TABLE Feed ADD reader_mode_enabled BOOLEAN",
    "ALTER TABLE Feed ADD consecutive_errors INT64 DEFAULT 0",
    "ALTER TABLE Feed ADD last_error STRING",
    "ALTER TABLE Item ADD id STRING",
    "ALTER TABLE Item ADD author STRING",
    "ALTER TABLE Item ADD word_count INT64 DEFAULT 0",
    "ALTER TABLE Item ADD reader_content STRING",
    "ALTER TABLE Item ADD reader_fetched_at TIMESTAMP",
]


def _rows(result: kuzu.QueryResult | list[kuzu.QueryResult]) -> list[dict[str, Any]]:
    if isinstance(result, list):
        result = result[0]
    cols = result.get_column_names()
    rows: list[dict[str, Any]] = []
    while result.has_next():
        rows.append(dict(zip(cols, result.get_next(), strict=True)))
    return rows


class GraphService:
    """Single access point for all Kuzu interactions.

    The REST API and MCP server import this; neither touches Kuzu directly.
    """

    def __init__(self, db_path: str) -> None:
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute("""
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
        self._conn.execute("""
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
                PRIMARY KEY (guid)
            )
        """)
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Tag(
                name STRING,
                id STRING,
                PRIMARY KEY (name)
            )
        """)
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Note(
                item_id STRING,
                body STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                PRIMARY KEY (item_id)
            )
        """)
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Config(
                key STRING,
                value STRING,
                PRIMARY KEY (key)
            )
        """)
        self._conn.execute("CREATE REL TABLE IF NOT EXISTS HAS_ITEM(FROM Feed TO Item)")
        self._conn.execute("CREATE REL TABLE IF NOT EXISTS TAGGED(FROM Item TO Tag)")
        self._conn.execute("CREATE REL TABLE IF NOT EXISTS FEED_TAGGED(FROM Feed TO Tag)")
        self._migrate()
        logger.debug("Schema ready")

    def _migrate(self) -> None:
        version = self.get_config_values().get("schema_version", 1)
        if version >= _SCHEMA_VERSION:
            return
        for ddl in _V2_MIGRATIONS:
            try:
                self._conn.execute(ddl)
            except RuntimeError as exc:
                # Fresh databases already have these columns from CREATE TABLE
                message = str(exc).lower()
                if "already has property" in message or "already exists" in message:
                    continue
                raise
        self._backfill_v2()
        self.set_config_value("schema_version", _SCHEMA_VERSION)
        logger.info("Schema migrated to version %d", _SCHEMA_VERSION)

    def _backfill_v2(self) -> None:
        for table, key in (("Feed", "url"), ("Item", "guid")):
            rows = _rows(
                self._conn.execute(
                    f"MATCH (n:{table}) WHERE n.id IS NULL RETURN n.{key} AS key"
                )
            )
            for row in rows:
                self._conn.execute(
                    f"MATCH (n:{table}) WHERE n.{key} = $key SET n.id = $id",
                    {"key": row["key"], "id": str(uuid.uuid4())},
                )
        self._conn.execute(
            "MATCH (f:Feed) WHERE f.is_active IS NULL SET f.is_active = true"
        )
        self._conn.execute(
            "MATCH (f:Feed) WHERE f.consecutive_errors IS NULL SET f.consecutive_errors = 0"
        )
        self._conn.execute(
            "MATCH (f:Feed) WHERE f.subscribed_at IS NULL SET f.subscribed_at = $now",
            {"now": datetime.now(UTC)},
        )

    def _exists(self, query: str, params: dict[str, Any]) -> bool:
        rows = _rows(self._conn.execute(query, params))
        return bool(rows and rows[0].get("cnt", 0) > 0)

    # --- Config ---

    def get_config_values(self) -> dict[str, Any]:
        rows = _rows(self._conn.execute("MATCH (c:Config) RETURN c.key AS key, c.value AS value"))
        return {row["key"]: json.loads(row["value"]) for row in rows}

    def set_config_value(self, key: str, value: Any) -> None:
        self._conn.execute(
            "MERGE (c:Config {key: $key}) ON CREATE SET c.value = $value "
            "ON MATCH SET c.value = $value",
            {"key": key, "value": json.dumps(value)},
        )

    # --- Feeds ---

    def feed_exists(self, url: str) -> bool:
        return self._exists(
            "MATCH (f:Feed {url: $url}) RETURN count(f) AS cnt", {"url": url}
        )

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
        self._conn.execute(
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
                "site_url": site_url,
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
        result = self._conn.execute(
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
            self._conn.execute(
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
            self._conn.execute(
                f"MATCH (f:Feed) WHERE f.id = $id SET {set_clause}",
                {"id": feed_id, **updates},
            )
        if "tags" in fields and fields["tags"] is not None:
            self.set_feed_tags(feed_id, fields["tags"])
        return self.get_feed(feed_id)

    def set_feed_tags(self, feed_id: str, tags: list[str]) -> None:
        self._conn.execute(
            "MATCH (f:Feed)-[r:FEED_TAGGED]->(:Tag) WHERE f.id = $id DELETE r",
            {"id": feed_id},
        )
        for name in tags:
            tag = self.ensure_tag(name)
            self._conn.execute(
                """
                MATCH (f:Feed), (t:Tag {name: $name})
                WHERE f.id = $id
                MERGE (f)-[:FEED_TAGGED]->(t)
                """,
                {"id": feed_id, "name": tag["name"]},
            )

    def list_feeds_for_polling(self) -> list[dict[str, Any]]:
        result = self._conn.execute(
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
        self._conn.execute(
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
        self._conn.execute(
            "MATCH (f:Feed) WHERE f.id = $id DETACH DELETE f", {"id": feed_id}
        )
        return True

    # --- Items ---

    def item_exists(self, guid: str) -> bool:
        return self._exists(
            "MATCH (i:Item {guid: $guid}) RETURN count(i) AS cnt", {"guid": guid}
        )

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
            item_id = str(uuid.uuid4())
            self._conn.execute(
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
                    "url": url,
                    "title": title,
                    "summary": summary,
                    "content": content,
                    "author": author,
                    "word_count": word_count,
                    "published_at": published_at,
                    "fetched_at": fetched_at,
                },
            )
        self._conn.execute(
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
        prefix, params = self._item_filters(
            feed_id, tag, unread_only, starred_only, since, until
        )
        count_rows = _rows(
            self._conn.execute(f"{prefix} RETURN count(i) AS total", params)
        )
        total = int(count_rows[0]["total"]) if count_rows else 0
        result = self._conn.execute(
            f"""
            {prefix}
            RETURN {_ITEM_COLS}, f.id AS feed_id,
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

    def _tags_for_items(self, guids: list[str]) -> dict[str, list[str]]:
        if not guids:
            return {}
        rows = _rows(
            self._conn.execute(
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
        result = self._conn.execute(
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
            self._conn.execute(
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
        count_rows = _rows(
            self._conn.execute(f"{match} {where} RETURN count(i) AS total", params)
        )
        total = int(count_rows[0]["total"]) if count_rows else 0
        self._conn.execute(f"{match} {where} SET i.read = true", params)
        return total

    def save_reader_content(self, item_id: str, content: str, fetched_at: datetime) -> None:
        self._conn.execute(
            """
            MATCH (i:Item) WHERE i.id = $id
            SET i.reader_content = $content, i.reader_fetched_at = $fetched_at
            """,
            {"id": item_id, "content": content, "fetched_at": fetched_at},
        )

    def _item_guid(self, item_id: str) -> str | None:
        rows = _rows(
            self._conn.execute(
                "MATCH (i:Item) WHERE i.id = $id RETURN i.guid AS guid", {"id": item_id}
            )
        )
        return rows[0]["guid"] if rows else None

    # --- Tags ---

    def ensure_tag(self, name: str) -> dict[str, Any]:
        rows = _rows(
            self._conn.execute(
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
            self._conn.execute(
                "MATCH (t:Tag) WHERE t.id = $id RETURN t.id AS id, t.name AS name",
                {"id": tag_id},
            )
        )
        return rows[0] if rows else None

    def list_tags(self) -> list[dict[str, Any]]:
        result = self._conn.execute(
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
        self._conn.execute("MATCH (t:Tag) WHERE t.id = $id DETACH DELETE t", {"id": tag_id})
        return True

    def tag_item(self, item_id: str, name: str) -> dict[str, Any] | None:
        guid = self._item_guid(item_id)
        if guid is None:
            return None
        tag = self.ensure_tag(name)
        self._conn.execute(
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
        self._conn.execute(f"{pattern} DELETE r", params)
        return True

    # --- Notes ---

    def get_note(self, item_id: str) -> dict[str, Any] | None:
        rows = _rows(
            self._conn.execute(
                """
                MATCH (n:Note {item_id: $item_id})
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
        rows = _rows(
            self._conn.execute(
                """
                MERGE (n:Note {item_id: $item_id})
                ON CREATE SET n.body = $body, n.created_at = $now, n.updated_at = $now
                ON MATCH SET n.body = $body, n.updated_at = $now
                RETURN n.body AS body, n.created_at AS created_at, n.updated_at AS updated_at
                """,
                {"item_id": item_id, "body": body, "now": now},
            )
        )
        return rows[0]

    def delete_note(self, item_id: str) -> bool:
        if self.get_note(item_id) is None:
            return False
        self._conn.execute("MATCH (n:Note {item_id: $item_id}) DELETE n", {"item_id": item_id})
        return True

    def close(self) -> None:
        self._conn.close()
        self._db.close()
