# Contributing to Reed

Reed is an open-source project and contributions are welcome. This document covers everything you need to get started.

## Before you contribute

Read the [Code of Conduct](CODE_OF_CONDUCT.md). All contributors are expected to follow it.

Reed is in active early development. Before starting work on anything significant, open an issue or discussion first — it avoids duplicated effort and ensures the contribution aligns with the project direction.

## Ways to contribute

- **Bug reports** — open an issue using the bug report template
- **Feature requests** — open an issue using the feature request template
- **Documentation** — fix typos, improve clarity, add examples
- **Code** — fix bugs, implement features from the roadmap

## Development setup

**Prerequisites:**
- Python 3.11+
- Docker and Docker Compose (for integration testing)
- Git

**Setup:**

```bash
git clone https://github.com/simonives/reed
cd reed
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Run the test suite:**

```bash
pytest
```

**Lint and format:**

```bash
ruff check .
ruff format .
```

**Type check:**

```bash
mypy src/reed
```

**Run locally with Docker:**

```bash
cp .env.example .env   # add your REED_API_KEY
docker-compose up
```

## Branching model

Reed uses GitHub Flow. All work happens on feature branches; `main` is always releasable.

```
main  ────────────────────────────────── (protected)
         ↑           ↑         ↑
    feat/thing    fix/bug   docs/update
```

**Branch naming:**

| Prefix | Use for |
|---|---|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `chore/` | Build, CI, dependencies, tooling |
| `release/` | Release preparation |

**Rules:**
- No direct commits to `main`
- All changes go through a pull request
- CI must pass before merge
- One approval required (from the maintainer)

## Opening a pull request

1. Fork the repository
2. Create a branch from `main` with the appropriate prefix
3. Make your changes
4. Run the full test suite and linting locally before pushing
5. Open a PR against `main` — fill in the PR template fully
6. A maintainer will review and either merge or request changes

**Keep PRs focused.** One logical change per PR. A PR that fixes a bug and adds a feature will be asked to split.

## Commit messages

Use the imperative mood in the subject line. Keep it under 72 characters.

```
Add feed discovery for website URLs
Fix poll interval not respecting per-feed override
Update CONTRIBUTING with Docker setup instructions
```

No need for a body on simple changes. Add one when the why is non-obvious.

## Code conventions

- **Formatting:** `ruff format` — enforced by CI
- **Linting:** `ruff check` — enforced by CI
- **Type annotations:** all public functions and methods must have type annotations; `mypy` runs in CI
- **Comments:** only when the why is non-obvious. No docstrings on trivial methods.
- **Tests:** new features require tests; bug fixes require a regression test

## Licence

By contributing to Reed you agree that your contributions will be licenced under the GNU Affero General Public Licence v3.0.

Add the following header to new source files:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors
```

## Response time

Reed is a maintained side project. Issues and pull requests are reviewed weekly. If you haven't heard back within two weeks, a polite follow-up comment on the issue is welcome.
