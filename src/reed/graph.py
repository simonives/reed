# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import kuzu


class GraphService:
    """Single access point for all Kuzu interactions.

    The REST API and MCP server import this; neither touches Kuzu directly.
    Schema migrations and derived edge recomputation are also handled here.
    """

    def __init__(self, db_path: str) -> None:
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)

    def execute(
        self, query: str, params: dict[str, object] | None = None
    ) -> kuzu.QueryResult | list[kuzu.QueryResult]:
        if params:
            return self._conn.execute(query, params)
        return self._conn.execute(query)

    def close(self) -> None:
        self._conn.close()
        self._db.close()
