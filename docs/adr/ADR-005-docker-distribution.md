# ADR-005: Docker Compose as primary distribution

| | |
|---|---|
| **Date** | 2026-07-10 |
| **Status** | Accepted |

## Context

Reed is a self-hosted application. The distribution model — how a user gets Reed running on their hardware — is a significant part of the user experience and shapes how accessible the project is to different audiences.

The primary goals for distribution are:
- Minimal setup steps to a running instance
- Broad hardware and OS compatibility
- No dependency on a specific hosting provider
- Source always available for contributors and alternative deployments

## Options considered

**PHP on shared hosting**
Initial appeal: shared hosting is the most accessible self-hosting tier. Any user with a cheap shared hosting plan (cPanel, Plesk) could theoretically run Reed.

Rejected for two reasons. First, the language decision (ADR-002) rules out PHP because Kuzu has no PHP bindings. Second, shared hosting cannot run persistent background processes — the feed poller and MCP server both require persistent processes. Shared hosting cron is too coarse and unreliable for a feed reader. PHP shared hosting is not a viable deployment target for Reed independent of the language decision.

**pip install only**
Distribute Reed as a Python package installable via `pip`. Users manage their own Python environment and run Reed directly.

Viable as a secondary distribution path, and will be supported. However, it requires users to manage Python version compatibility and virtual environments — more friction than Docker for non-Python users. Not sufficient as the primary distribution path.

**Platform-specific packages (Homebrew, .deb, snap)**
High accessibility for specific platforms, but significant maintenance overhead for a small open-source project. Each package format requires its own build pipeline and release process. Deferred to post-v1 if there is community demand.

**Docker Compose**
A `docker-compose.yml` that pulls a pre-built image from GitHub Container Registry (GHCR). The user installs Docker (one prerequisite, widely documented), creates a `.env` file with their API key, and runs `docker-compose up`. Reed starts.

Docker Compose is the de facto standard for self-hosted developer tools in 2026. It reaches:
- VPS providers (Hetzner, DigitalOcean, Linode, Vultr) — all support Docker
- Home servers and NAS devices — Synology, TrueNAS, and Unraid all run Docker
- Raspberry Pi — Docker runs on ARM64
- Cloud platforms — Railway, Render, Fly.io all support Docker deployment with minimal configuration
- Any Linux machine — Docker is available on every major distribution

Platform-specific configuration files (`fly.toml`, `render.yaml`) will be provided for one-click cloud deployment targets.

## Decision

**Docker Compose** is the primary distribution method. A pre-built image is published to GitHub Container Registry (`ghcr.io/simonives/reed`) on every release. A `docker-compose.yml` is provided at the repository root.

**From source** (`git clone` + `pip install -e .`) is the secondary path, supported for contributors and users who prefer to build their own image or run without Docker.

## Consequences

**Positive:**
- One command (`docker-compose up`) to a running instance
- Kuzu data directory mounted as a volume — persists across container restarts and upgrades
- The pre-built image pins all Python dependencies — no environment management for end users
- Broad reach across the hardware and platform landscape that matters for Reed's audience
- GHCR is free for public images and co-located with the source repository

**Negative / trade-offs:**
- Docker is a prerequisite — not all potential users have it installed, and some actively dislike it
- Image size will be non-trivial (Python base image + Kuzu + dependencies); mitigated by using a slim base image and multi-stage builds
- GHCR image availability creates a release pipeline responsibility — broken images affect all Docker users

**Neutral:**
- The `docker-compose.yml` at the repository root serves as living documentation of the required environment variables and volume mounts, independent of its role as a deployment tool.
