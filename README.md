# Reed

[![Licence](https://img.shields.io/badge/Licence-AGPL_3.0-blue.svg)](https://github.com/simonives/reed/blob/main/LICENSE)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
[![CI Status](https://github.com/simonives/reed/actions/workflows/ci.yml/badge.svg)](https://github.com/simonives/reed/actions/workflows/ci.yml) ![Status](https://img.shields.io/badge/status-pre--release-orange.svg)

A self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server.

## What is Reed?

Reed is a single-user, self-hosted RSS reader built for simplicity and developer access. It uses a graph database ([Kuzu](https://kuzudb.com)) to model relationships between feeds, articles, authors, topics, and tags — making it traversable by AI tools via a built-in MCP server.

## Why I built Reed

My daily reading routine runs through an AI-assisted second brain, and RSS never fit into it cleanly. The reader I was using kept decent API access behind a paid tier, and even then, its data model — and every competitor's, FOSS or commercial — was a flat list of articles. None of them were built with AI clients as a first-class consumer, so there was no way to hand an agent something richer than "here are some unread items."

Reed exists to fix that. Feeds, articles, authors, topics, and tags are nodes and edges in a graph, not rows in a table, so an AI client can traverse relationships — hop from an item to its topics, to related topics, to related items across other feeds — instead of just paging through a list. It started as a weekend prototype and has grown into a daily driver.

## Status

Active development, pre-1.0.0. Milestones M0 through M6 are complete: foundation, walking skeleton, usable reader, migration-ready, graph alive (topic extraction, similarity graph), full API and integrations (share sheet, export/import, topics API), and a 27-tool MCP server exposing the whole graph to AI clients over stdio and HTTP. M7 (distribution, documentation, public launch) is in progress — see [`docs/roadmap/milestones.md`](docs/roadmap/milestones.md) for the live status.

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

Reed is not yet published as a versioned release — the Docker image on GHCR and the PyPI package land with v1.0.0. Until then, run it from source:

```bash
git clone https://github.com/simonives/reed
cd reed
pip install -e .
reed serve
```

Or build the Docker image locally (matching the tag `docker-compose.yml` expects, so `docker compose up` picks it up without edits):

```bash
git clone https://github.com/simonives/reed
cd reed
docker build -t ghcr.io/simonives/reed:latest .
cp .env.example .env   # add your REED_API_KEY
docker compose up
```

Either way, set a real `REED_API_KEY` before starting — see [`.env.example`](.env.example) and [`CONTRIBUTING.md`](CONTRIBUTING.md) for local development setup.

## Licence

AGPL v3
