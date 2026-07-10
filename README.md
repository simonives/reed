# Reed

A self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server.

## What is Reed?

Reed is a single-user, self-hosted RSS reader built for simplicity and developer access. It uses a graph database ([Kuzu](https://kuzudb.com)) to model relationships between feeds, articles, authors, topics, and tags — making it traversable by AI tools via a built-in MCP server.

## Status

Active development — M0 scaffold complete. The Python package, Vue 3 frontend skeleton, Dockerfile, and CI pipeline are in place. Working towards M1: feed polling, graph schema, and the first real API endpoints.

## Design goals

- Simple, fast RSS reading UI
- Fully public REST API (first-class, not an afterthought)
- MCP server for AI client integration and graph traversal
- Single-user, self-hosted — no SaaS, no cloud service
- Zero operational overhead — one `docker-compose up` to run

## Technology

- **Python** — application language across all components
- **Kuzu** — embedded graph database
- **FastAPI** — REST API and OpenAPI documentation
- **FastMCP** — MCP server
- **Vue 3 + Vite** — web UI (three-pane reader, keyboard-first)
- **Docker Compose** — primary distribution and deployment

## Self-hosting

```bash
# Docker (coming soon)
docker-compose up

# From source (coming soon)
git clone https://github.com/simonives/reed
cd reed
pip install -e .
reed serve
```

## Licence

AGPL v3
