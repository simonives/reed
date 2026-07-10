# ADR-007: FastMCP for the MCP server

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

The MCP (Model Context Protocol) server is a first-class component of Reed, not a post-v1 addition. It enables AI clients — Claude, Cursor, and any other MCP-compatible tool — to interact with a user's reading graph: browsing feeds, reading items, traversing topics, and finding related content.

The graph model (ADR-001) was chosen partly because of the MCP use case: graph traversal is a natural fit for the kind of multi-hop reasoning an AI client performs. The MCP server is the surface that exposes that capability.

The question is how to implement it.

## Options considered

**Anthropic's official MCP Python SDK**
The reference implementation. Low-level — you define tools, resources, and prompts by hand and manage transport configuration explicitly. Correct and stable, but requires more boilerplate than higher-level abstractions.

**FastMCP**
A Python library that wraps the official MCP SDK with a FastAPI-inspired interface. Tools are defined as decorated Python functions with type annotations; FastMCP handles the schema generation, transport, and protocol boilerplate. The developer experience is close to writing a FastAPI route.

Given that Reed uses FastAPI for its REST layer (ADR-006), the FastMCP pattern is immediately familiar. The same Pydantic-style type annotations that define API request/response schemas define MCP tool input/output schemas.

**TypeScript/Node MCP SDK**
The other first-class MCP implementation. Ruled out: Reed is Python throughout (ADR-002), and splitting the MCP server into a separate Node.js process would introduce a second language and second runtime.

**Building directly on the REST API**
Some MCP servers are thin wrappers around an HTTP API — the tool implementations just call the REST endpoints. For Reed, the MCP server and REST API share the same Python process and graph service layer, so there is no HTTP hop between them. The MCP tools call the graph service directly, which is faster and simpler than round-tripping through the REST layer.

## Decision

Use **FastMCP** for Reed's MCP server. MCP tools are defined as decorated Python functions in the same codebase as the REST API. The MCP server and REST API share the graph service layer directly — no HTTP intermediary.

The MCP server runs in the same process as the FastAPI application, exposed on a separate transport (stdio for local clients, HTTP/SSE for remote clients).

## Consequences

**Positive:**
- Same language, same codebase, same process — MCP tools and REST endpoints share the graph service layer with no network hop
- FastMCP's decorator pattern is immediately readable for anyone familiar with FastAPI
- Tool schemas are generated from Python type annotations — no manual MCP schema authoring
- A single `docker-compose up` starts both the REST API and the MCP server

**Negative / trade-offs:**
- FastMCP is a third-party library, not the official SDK. It adds a dependency on a project that, while well-maintained, is not under Anthropic's control. If FastMCP diverges from the MCP spec or is abandoned, a migration to the official SDK is required — though the migration path would be mechanical since the tool logic would remain unchanged.
- Running the MCP server in the same process as the REST API means a crash in one affects the other. Acceptable for a single-user self-hosted application; would not be acceptable for a multi-tenant service.

**Neutral:**
- The MCP tool surface is the primary interface for AI clients; the REST API is the primary interface for the web UI and third-party integrations. Both expose the same underlying graph service, so changes to the graph model propagate to both surfaces simultaneously.
