# ADR-001: Graph database over relational storage

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

RSS content appears at first to be a list problem: feeds contain items, items have metadata. A relational database handles that trivially. The problem emerges when you ask the interesting questions:

- What else have I read about this topic across all my feeds?
- Which feeds are publishing most about a given subject this month?
- What connects this article to something I starred three months ago?
- What topics cluster around my reading habits?

A relational model answers those questions with multi-table joins that grow in complexity as the relationship graph deepens. More importantly, the MCP server use case — where an AI client traverses the data to surface connections and patterns — maps naturally to graph traversal, not SQL joins. An AI client hopping from an item to its topics, to related topics, to related items across different feeds is a first-class graph operation. Forcing that through a relational layer adds impedance and loses expressiveness.

RSS data has a natural graph shape:

- **Feeds** publish **Items**
- **Items** are written by **Authors**
- **Items** are about **Topics** (extracted from content)
- **Items** carry **Tags** (user-applied)
- **Topics** relate to other **Topics** (by co-occurrence)
- **Items** are similar to other **Items** (via shared topics)

The last two edges — `RELATED_TO` between topics and `SIMILAR_TO` between items — are derived and written back into the graph. These are the edges that make Reed meaningfully different from a list renderer: they create a traversable map of a user's reading history.

## Options considered

**Relational (PostgreSQL or SQLite)**
The default choice. Well-understood, excellent tooling, every developer knows SQL. Rejected because multi-hop traversal queries become unwieldy, full-text search requires a separate extension or service, and the MCP graph traversal use case maps poorly to a relational model.

**Neo4j Community Edition**
The canonical graph database. Mature, excellent tooling, Cypher is the industry-standard graph query language. Rejected because it requires a JVM, is operationally heavy, and the Community Edition has constraints (single machine, limited clustering) that work against the self-hosted zero-ops goal. Not embeddable — requires a running server process.

**ArangoDB**
Multi-model (graph + document + key-value). Self-hostable. Rejected because it requires a server process, adding operational overhead that conflicts with the zero-ops goal.

**DuckDB with pgq extension**
DuckDB is embeddable and analytically powerful. The pgq extension adds property graph queries on top of relational tables. Interesting hybrid, but graph support is an add-on rather than native, and DuckDB's write patterns (optimised for bulk analytical reads) are a less natural fit for the mixed read/write workload of an RSS reader.

**Kuzu**
An embeddable graph database: no server process, single file, Apache 2.0 licence, Cypher query language, Python/Node/Rust/Go bindings, columnar storage. Actively developed and purpose-built for the shape of problem Reed has.

## Decision

Use **Kuzu** as Reed's data store. All persistent data — feeds, items, authors, tags, topics, read state, poll metadata — lives in the Kuzu graph. Full-text search is handled via Kuzu's FTS support. No separate database or search index.

## Consequences

**Positive:**
- Graph traversal queries are natural and expressive in Cypher
- The MCP server tool surface maps directly to graph traversal operations
- Derived edges (`SIMILAR_TO`, `RELATED_TO`) make Reed genuinely different from list-based RSS readers
- Embedded model means zero operational overhead — the database is a file

**Negative / trade-offs:**
- Kuzu is younger than SQLite or PostgreSQL; the ecosystem is smaller and some edge cases are less documented
- Contributors need to know Cypher rather than SQL — a smaller talent pool
- Some operational patterns familiar from relational DBs (migrations, schema inspection) work differently in Kuzu and will need tooling

**Neutral:**
- Full-text search within Kuzu eliminates the need for a separate search index, but the FTS capabilities are less mature than dedicated search engines (Meilisearch, Typesense). Acceptable for v1; revisit if search quality becomes a constraint.
