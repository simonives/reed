# ADR-006: FastAPI for the REST layer

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

Reed's REST API is a first-class deliverable. The web UI consumes it; so does the MCP server's write path; so does any third-party integration a user builds. The API framework choice affects documentation quality, request validation, async support, and long-term maintainability.

Given Python as the application language (ADR-002), the choice is between Python REST frameworks.

## Options considered

**Flask**
The lightweight Python web framework. Minimal, well-understood, huge community. Requires separate libraries for request validation (marshmallow, pydantic-as-a-plugin) and OpenAPI documentation (flasgger, flask-smorest). Works, but the API-first requirement means adding several libraries to get feature parity with FastAPI out of the box.

**Django REST Framework (DRF)**
Full-featured, battle-tested. The right choice for a complex web application with many models, admin interfaces, and a large contributor base. Overkill for Reed — DRF's ORM-centric model fits relational databases, not a Kuzu graph. The impedance between DRF's patterns and a graph data layer would require working against the framework rather than with it.

**FastAPI**
Async-native Python REST framework built on Starlette and Pydantic. Key properties:
- Automatic OpenAPI/Swagger documentation generated from type annotations — no manual spec maintenance
- Pydantic models for request and response validation
- Async-native — the feed poller runs as an asyncio background task in the same process
- Active development and large community
- Designed for building APIs, not full web applications — matches Reed's API-first positioning

## Decision

Use **FastAPI** for Reed's REST API. All routes are defined with Pydantic request/response models. OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc`. The feed poller runs as an asyncio background task registered with the FastAPI application lifecycle.

## Consequences

**Positive:**
- OpenAPI documentation is generated automatically and always in sync with the implementation — critical for an API-first project
- Pydantic validation means malformed requests are rejected at the framework layer, not in business logic
- Async-native design means the feed poller, API handlers, and Kuzu queries can share the same event loop without threading complexity
- `/docs` gives any user or contributor a live, interactive API explorer with no extra tooling

**Negative / trade-offs:**
- FastAPI's async model requires care around blocking operations — Kuzu queries must be run in a thread pool executor if they block the event loop. This is a known pattern but adds boilerplate.
- FastAPI does not include a built-in templating or static file server suitable for a rich UI — Jinja2 and `StaticFiles` are added separately. Minor friction for the web UI component.

**Neutral:**
- FastAPI's automatic OpenAPI spec can be exported as a JSON file and used to generate client SDKs in other languages. Useful if Reed's API is ever consumed from a non-Python context.
