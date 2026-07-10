# ADR-002: Python as the primary language

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

The language choice for Reed is constrained by two prior decisions: Kuzu as the database (ADR-001) and the MCP server as a first-class component. Kuzu has official bindings for Python, Node.js, Rust, Java, and C/C++, with a community Go binding. The dominant MCP server implementation is FastMCP, which is Python-native.

Beyond those constraints, Reed needs:
- A REST API framework with automatic OpenAPI documentation (the API is a first-class deliverable)
- An async-capable runtime for the feed poller
- A packaging model that works for self-hosted deployment

The goal is a single language across all components — API, MCP server, graph service, and feed poller — to keep the codebase coherent and reduce contributor friction.

## Options considered

**PHP**
Initial appeal: PHP is available on virtually every shared hosting provider, from cheap shared plans to enterprise environments. The lowest barrier to self-hosting.

Rejected on two grounds. First, Kuzu has no PHP bindings and is not targeting PHP as a supported language. Using PHP as the application layer with Kuzu as the data layer would require a separate Python or Node.js service to handle all graph operations — two languages, two processes, two things to deploy, defeating the simplicity goal. Second, shared hosting cannot run persistent background processes, which Reed's feed poller requires. Cron on shared hosting is coarse (typically 15-minute minimum) and unreliable. The MCP server also requires a persistent process. PHP shared hosting is not a viable deployment target for Reed regardless of language choice.

**Go**
Appeal: compiles to a single binary with no runtime dependencies. Drop the binary on any Linux server and it runs — the most portable self-hosting story possible. Community Kuzu bindings exist for Go.

Rejected because the MCP server ecosystem is Python-first. A Go application layer would require the MCP server to be a separate Python process, splitting the codebase across two languages. The single-binary deployment advantage is largely matched by Docker packaging (ADR-005) without the language split.

**Node.js**
Kuzu has first-class Node.js bindings. The MCP SDK has a TypeScript/Node implementation. A coherent Node.js stack is possible.

Rejected because the Python ecosystem is a better fit for Reed's other concerns: FastMCP is more mature than the Node MCP SDK for this use case, FastAPI's automatic OpenAPI generation is best-in-class, and the data/NLP tooling relevant to topic extraction (spaCy, RAKE, YAKE) is Python-native.

**Python**
Kuzu has first-class Python bindings. FastMCP is Python-native. FastAPI provides automatic OpenAPI documentation. The feed poller runs naturally as an asyncio background task. Topic extraction libraries (RAKE, YAKE, spaCy) are Python-native. One language, one virtual environment, one Docker image.

## Decision

Use **Python** as the primary language across all Reed components: REST API (FastAPI), MCP server (FastMCP), graph service layer (Kuzu Python bindings), and feed poller (asyncio).

## Consequences

**Positive:**
- Single language and virtual environment across the entire codebase
- FastMCP and FastAPI are both Python-native — no impedance between components
- Topic extraction tooling is Python-native
- Contributors need to know one language
- Packaging is a single Docker image or `pip install`

**Negative / trade-offs:**
- Python is not available on shared hosting in a way that supports persistent processes — but this was already ruled out as a deployment target (ADR-005)
- Python startup time and memory footprint are higher than Go or a compiled language — acceptable for a self-hosted single-user application
- Virtual environment management adds minor friction for from-source deployments; mitigated by providing a well-documented setup and a `pyproject.toml`
