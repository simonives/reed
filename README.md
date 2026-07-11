# Reed

[![Licence](https://img.shields.io/badge/Licence-AGPL_3.0-blue.svg)](https://github.com/simonives/reed/blob/main/LICENSE) ![Python Version](https://img.shields.
  io/badge/python-3.11+-blue.svg) [![CI Status](https://github.com/simonives/reed/actions/workflows/ci.yml/badge.svg)](https://github.com/simonives/reed/actions/workflows/ci.
  yml) ![Version](https://img.shields.io/badge/version-M1-blue.svg)

A self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server.

## What is Reed?

Reed is a single-user, self-hosted RSS reader built for simplicity and developer access. It uses a graph database ([Kuzu](https://kuzudb.com)) to model relationships between feeds, articles, authors, topics, and tags — making it traversable by AI tools via a built-in MCP server.

## Why I built Reed

I originally built Reed because my daily routines around my second brain did not have a neat and frictionless mechanism for incorproating a review and engagement task within my agentic workflow. I had my RSS feeds in a web-based application, however decent API access required a paid subscription. Further, the structures and interfaces of this application, and the competitors I was aware of (both FOSS and commercial) weren't built for an AI first, or AI at all, workflow. So I decided to build reed. I built a working prototype over a weekend with a vew to building something that [iterate with Claude here to build a compelling story].

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
