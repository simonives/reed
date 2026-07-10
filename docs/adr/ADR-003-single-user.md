# ADR-003: Single-user architecture

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

RSS readers can be architected for a single user per instance or for multiple users sharing an instance (multi-tenancy). The distinction has significant downstream effects on auth, data modelling, operational complexity, and the self-hosting experience.

Reed's positioning is explicitly a self-hosted alternative to services like Feedly — something a person runs for themselves, not something they operate for others. The target user deploys Reed on a VPS, home server, or NAS and uses it personally.

## Options considered

**Multi-user**
Supports multiple accounts per instance. Requires user authentication (registration, login, session management), per-user data isolation in the graph (every node and edge scoped to a user ID), and access control on every API endpoint and MCP tool.

The operational and code complexity multiplies significantly: password management or OAuth integration, per-user feed subscriptions, per-user read state, per-user tags and topics, and the graph schema becomes more complex to partition correctly. The self-hosting story also changes — running Reed for multiple people means taking on responsibility for other people's data and uptime.

**Single-user**
One user per instance. Auth reduces to a single API key configured at setup time. The graph has no user scoping — everything in the database belongs to the instance owner. No registration flow, no session management, no per-user isolation.

Anyone who wants to share Reed with another person runs a second instance. This is consistent with how most self-hosted developer tools work (Miniflux, FreshRSS in single-user mode, Wallabag).

## Decision

Reed is **single-user**. One instance serves one person. Authentication is a single API key set via environment variable at deployment time.

This decision is scoped to v1. Multi-user support is not ruled out permanently, but it is explicitly out of scope until the single-user experience is complete and stable.

## Consequences

**Positive:**
- Auth is trivial — one API key, no session management, no registration flow
- The graph schema has no user scoping — simpler node and edge definitions
- Every API endpoint and MCP tool operates in a single namespace — no access control logic
- The self-hosting story is clean: one person, one instance, one file

**Negative / trade-offs:**
- Shared household or team use requires running multiple instances — more operational overhead for that use case
- If multi-user support is added in the future, the graph schema will need migration to add user scoping — a non-trivial change. This is an accepted cost.

**Neutral:**
- The single-user constraint makes the Kuzu embedded model (ADR-004) more viable — no concurrent write contention across users. Kuzu's concurrency model (single writer) is a natural fit for single-user workloads.
