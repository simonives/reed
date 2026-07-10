# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import kuzu

logger = logging.getLogger(__name__)


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
                title STRING,
                description STRING,
                site_url STRING,
                poll_interval_minutes INT64,
                last_fetched_at TIMESTAMP,
                error_state STRING,
                etag STRING,
                last_modified STRING,
                PRIMARY KEY (url)
            )
        """)
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Item(
                guid STRING,
                url STRING,
                title STRING,
                summary STRING,
                content STRING,
                published_at TIMESTAMP,
                fetched_at TIMESTAMP,
                read BOOLEAN,
                starred BOOLEAN,
                PRIMARY KEY (guid)
            )
        """)
        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_ITEM(FROM Feed TO Item)
        """)
        logger.debug("Schema ready")

    # --- Feeds ---

    def feed_exists(self, url: str) -> bool:
        result = self._conn.execute(
            "MATCH (f:Feed {url: $url}) RETURN count(f) AS cnt",
            {"url": url},
        )
        rows = _rows(result)
        return bool(rows and rows[0].get("cnt", 0) > 0)

    def create_feed(
        self,
        url: str,
        title: str,
        description: str,
        site_url: str,
        poll_interval_minutes: int,
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            CREATE (:Feed {
                url: $url,
                title: $title,
                description: $description,
                site_url: $site_url,
                poll_interval_minutes: $poll_interval_minutes
            })
            """,
            {
                "url": url,
                "title": title,
                "description": description,
                "site_url": site_url,
                "poll_interval_minutes": poll_interval_minutes,
            },
        )
        feed = self.get_feed(url)
        assert feed is not None
        return feed

    def get_feed(self, url: str) -> dict[str, Any] | None:
        result = self._conn.execute(
            """
            MATCH (f:Feed {url: $url})
            RETURN f.url AS url, f.title AS title, f.description AS description,
                   f.site_url AS site_url, f.poll_interval_minutes AS poll_interval_minutes,
                   f.last_fetched_at AS last_fetched_at, f.error_state AS error_state,
                   f.etag AS etag, f.last_modified AS last_modified
            """,
            {"url": url},
        )
        rows = _rows(result)
        return rows[0] if rows else None

    def list_feeds(self) -> list[dict[str, Any]]:
        result = self._conn.execute(
            """
            MATCH (f:Feed)
            RETURN f.url AS url, f.title AS title, f.description AS description,
                   f.site_url AS site_url, f.poll_interval_minutes AS poll_interval_minutes,
                   f.last_fetched_at AS last_fetched_at, f.error_state AS error_state,
                   f.etag AS etag, f.last_modified AS last_modified
            ORDER BY f.title ASC
            """
        )
        return _rows(result)

    def list_feeds_for_polling(self) -> list[dict[str, Any]]:
        result = self._conn.execute(
            """
            MATCH (f:Feed)
            RETURN f.url AS url, f.etag AS etag, f.last_modified AS last_modified,
                   f.poll_interval_minutes AS poll_interval_minutes,
                   f.last_fetched_at AS last_fetched_at
            """
        )
        return _rows(result)

    def update_feed_poll_metadata(
        self,
        url: str,
        last_fetched_at: datetime,
        etag: str | None,
        last_modified: str | None,
        error_state: str | None,
    ) -> None:
        self._conn.execute(
            """
            MATCH (f:Feed {url: $url})
            SET f.last_fetched_at = $last_fetched_at,
                f.etag = $etag,
                f.last_modified = $last_modified,
                f.error_state = $error_state
            """,
            {
                "url": url,
                "last_fetched_at": last_fetched_at,
                "etag": etag,
                "last_modified": last_modified,
                "error_state": error_state,
            },
        )

    def delete_feed(self, url: str) -> bool:
        if not self.feed_exists(url):
            return False
        # Delete HAS_ITEM edges and the Feed node; Items are kept (read/starred state preserved)
        self._conn.execute(
            "MATCH (f:Feed {url: $url})-[r:HAS_ITEM]->() DELETE r",
            {"url": url},
        )
        self._conn.execute(
            "MATCH (f:Feed {url: $url}) DELETE f",
            {"url": url},
        )
        return True

    # --- Items ---

    def item_exists(self, guid: str) -> bool:
        result = self._conn.execute(
            "MATCH (i:Item {guid: $guid}) RETURN count(i) AS cnt",
            {"guid": guid},
        )
        rows = _rows(result)
        return bool(rows and rows[0].get("cnt", 0) > 0)

    def _has_item_edge_exists(self, feed_url: str, guid: str) -> bool:
        result = self._conn.execute(
            """
            MATCH (f:Feed {url: $feed_url})-[:HAS_ITEM]->(i:Item {guid: $guid})
            RETURN count(*) AS cnt
            """,
            {"feed_url": feed_url, "guid": guid},
        )
        rows = _rows(result)
        return bool(rows and rows[0].get("cnt", 0) > 0)

    def create_item(
        self,
        feed_url: str,
        guid: str,
        url: str,
        title: str,
        summary: str,
        content: str,
        published_at: datetime | None,
        fetched_at: datetime,
    ) -> bool:
        """Create an Item node and HAS_ITEM edge if they don't exist.

        Item node creation is skipped if the guid already exists (e.g. shared across
        feeds, or resubscription after delete). The HAS_ITEM edge is always created
        if absent. Returns True only when a new Item node was created.
        """
        is_new_item = not self.item_exists(guid)
        if is_new_item:
            self._conn.execute(
                """
                CREATE (:Item {
                    guid: $guid,
                    url: $url,
                    title: $title,
                    summary: $summary,
                    content: $content,
                    published_at: $published_at,
                    fetched_at: $fetched_at,
                    read: false,
                    starred: false
                })
                """,
                {
                    "guid": guid,
                    "url": url,
                    "title": title,
                    "summary": summary,
                    "content": content,
                    "published_at": published_at,
                    "fetched_at": fetched_at,
                },
            )
        if not self._has_item_edge_exists(feed_url, guid):
            self._conn.execute(
                """
                MATCH (f:Feed {url: $feed_url}), (i:Item {guid: $guid})
                CREATE (f)-[:HAS_ITEM]->(i)
                """,
                {"feed_url": feed_url, "guid": guid},
            )
        return is_new_item

    def list_items(
        self,
        feed_url: str | None = None,
        unread_only: bool = False,
        starred_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        item_cols = """
            i.guid AS guid, i.url AS url, i.title AS title,
            i.summary AS summary, i.content AS content,
            i.published_at AS published_at, i.fetched_at AS fetched_at,
            i.read AS read, i.starred AS starred
        """
        if feed_url is not None:
            result = self._conn.execute(
                f"""
                MATCH (f:Feed {{url: $feed_url}})-[:HAS_ITEM]->(i:Item)
                WHERE ($unread_only = false OR i.read = false)
                  AND ($starred_only = false OR i.starred = true)
                RETURN {item_cols}
                ORDER BY i.fetched_at DESC
                SKIP $offset LIMIT $limit
                """,
                {
                    "feed_url": feed_url,
                    "unread_only": unread_only,
                    "starred_only": starred_only,
                    "offset": offset,
                    "limit": limit,
                },
            )
        else:
            result = self._conn.execute(
                f"""
                MATCH (f:Feed)-[:HAS_ITEM]->(i:Item)
                WHERE ($unread_only = false OR i.read = false)
                  AND ($starred_only = false OR i.starred = true)
                RETURN {item_cols}
                ORDER BY i.fetched_at DESC
                SKIP $offset LIMIT $limit
                """,
                {
                    "unread_only": unread_only,
                    "starred_only": starred_only,
                    "offset": offset,
                    "limit": limit,
                },
            )
        return _rows(result)

    def close(self) -> None:
        self._conn.close()
        self._db.close()
