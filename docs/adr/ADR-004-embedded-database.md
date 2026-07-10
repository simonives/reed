# ADR-004: Embedded database (no server process)

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

Having chosen Kuzu as the graph database (ADR-001), a secondary decision remains: run Kuzu embedded within the application process, or run a separate Kuzu server process that the application connects to over a network socket.

The same question arises in relational database choices: SQLite (embedded) vs PostgreSQL (server). The self-hosted, single-user, zero-ops goals are the primary constraints.

## Options considered

**Server-based graph databases (Neo4j, ArangoDB, FalkorDB)**
These run as separate server processes with their own lifecycle, configuration, port, and storage management. Deploying Reed would require managing two processes: the Reed application and the graph database server. Docker Compose handles this with multiple services, but it adds operational surface: the database server needs its own health checks, restart policies, memory limits, and upgrade path.

Neo4j additionally requires a JVM, which is a significant dependency for a lightweight self-hosted application.

**Kuzu in server mode**
Kuzu can run as a server (kùzu_shell or an HTTP server mode). This decouples the database from the application process and would allow, in principle, running the database on separate hardware.

Rejected for v1: the added operational complexity (two processes, network configuration between them) is not justified by any v1 requirement. Single-user workloads do not need database-application separation.

**Kuzu embedded**
Kuzu runs as a library inside the Reed application process. The database is a directory on disk. No separate process, no port, no network configuration. The application opens the Kuzu store on startup and closes it on shutdown.

This is identical to the SQLite model: the database is a file (or directory) that the application owns directly.

## Decision

Run Kuzu **embedded** within the Reed application process. The Kuzu data directory lives at a configurable path (default: `/data/reed.kuzu`) and is mounted as a Docker volume for persistence.

## Consequences

**Positive:**
- Zero operational overhead — no database server to start, stop, monitor, or upgrade separately
- Self-hosting is `docker-compose up` with a single service
- Backup is a file copy — no dump/restore tooling required
- No network configuration between application and database

**Negative / trade-offs:**
- Kuzu's embedded mode uses a single-writer concurrency model. For single-user workloads (ADR-003) this is not a constraint — the feed poller and API will not contend in ways that matter. If multi-user support is added in the future, this may become a bottleneck.
- The application process owns the database file exclusively while running. External tools cannot query the database while Reed is running without going through the API or MCP server.
- Database and application upgrades are coupled — upgrading Reed may require a Kuzu schema migration as part of the same release.

**Neutral:**
- The Kuzu data directory should be excluded from version control and treated as user data. The `.gitignore` excludes `/data/` for this reason.
