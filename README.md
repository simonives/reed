# Reed

[![Licence](https://img.shields.io/badge/Licence-AGPL_3.0-blue.svg)](https://github.com/simonives/reed/blob/main/LICENSE)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
[![CI Status](https://github.com/simonives/reed/actions/workflows/ci.yml/badge.svg)](https://github.com/simonives/reed/actions/workflows/ci.yml) ![Status](https://img.shields.io/badge/status-pre--release-orange.svg)

> **BETA.** Reed is public and usable today, but pre-1.0.0. Expect breaking changes before the v1.0.0 tag. See [Roadmap to v1.0.0](#roadmap-to-v100) below for what's left.

A self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server.

## What is Reed?

Reed is a single-user, self-hosted RSS reader built for simplicity and developer access. It uses a graph database ([Kuzu](https://kuzudb.com)) to model relationships between feeds, articles, authors, topics, and tags — making it traversable by AI tools via a built-in MCP server.

## Why I built Reed

My daily reading routine runs through an AI-assisted second brain, and RSS never fit into it cleanly. The reader I was using kept decent API access behind a paid tier, and even then, its data model — and every competitor's, FOSS or commercial — was a flat list of articles. None of them were built with AI clients as a first-class consumer, so there was no way to hand an agent something richer than "here are some unread items."

Reed exists to fix that. Feeds, articles, authors, topics, and tags are nodes and edges in a graph, not rows in a table, so an AI client can traverse relationships — hop from an item to its topics, to related topics, to related items across other feeds — instead of just paging through a list. It started as a weekend prototype and has grown into a daily driver.

## Status

Public beta, pre-1.0.0. Milestones M0 through M6 are complete: foundation, walking skeleton, usable reader, migration-ready, graph alive (topic extraction, similarity graph), full API and integrations (share sheet, export/import, topics API), and a 27-tool MCP server exposing the whole graph to AI clients over stdio and HTTP. See [`docs/roadmap/milestones.md`](docs/roadmap/milestones.md) for the live status, and the roadmap sections below for what's left before v1.0.0.

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

## Roadmap to v1.0.0

What's left before the beta label comes off:

- **Website:** a live project site with quickstart and installation instructions, served via GitHub Pages.
- **Distribution polish:** the release pipeline is built and dry-run verified, but no real `v1.0.0` tag has been pushed yet.
- **Public-hosting auth review:** the current single-static-API-key auth model was designed for a LAN-bound, self-hosted deployment. Before v1.0.0 formally endorses public cloud hosting (Railway, Render, Fly.io), that model needs a dedicated review, tracked as its own GitHub issue.

Track live progress in [`docs/roadmap/milestones.md`](docs/roadmap/milestones.md) and the repository's Issues and Milestones.

## Roadmap after v1.0.0

Ideas already scoped for consideration after the initial release. None are commitments yet.

- **User-maintained watch lists:** a standing set of topics or descriptions of interest that flags new incoming items matching those concerns, independent of which feed or topic-extraction path they arrived through.
- **Saved graph traversal views:** named, reusable graph queries beyond the current ad hoc traversal tools.
- **Author and co-authorship modelling:** treating authors as first-class graph entities with their own relationships, not just item metadata.
- **Scheduled discovery:** an opt-in feature to periodically scan for new content beyond the feeds a user already subscribes to, rather than being limited to what has already been ingested.

See `docs/roadmap/open-decisions.md` in the repository for the full design-question backlog these are drawn from.

## Licence

AGPL v3
