# Open Decisions

Unresolved design questions that must be answered before the relevant component is built. Each item should be resolved into an ADR or documented design decision before work begins on the affected area.

---

## UI rendering model

**Question:** Jinja2 server-rendered templates, HTMX, or minimal React/Preact?

**Affects:** Frontend build setup, developer experience, interactivity ceiling

**Options:**
- Jinja2 — zero JS dependencies, simplest, but limited interactivity without page reloads
- HTMX — interactive without a JS build step, stays server-centric
- Minimal SPA (React/Preact) — most interactive, but introduces a build pipeline

---

## Topic extraction approach

**Question:** How are topics extracted from feed item content?

**Affects:** Item write path, graph richness, dependency footprint

**Options:**
- Simple keyword extraction (RAKE, YAKE) — no model, fast, lightweight
- Lightweight NLP (spaCy) — better quality, adds a large dependency
- LLM via API — highest quality, requires external API call and key, adds latency and cost

---

## OPML import/export

**Question:** Scope and format of OPML support?

**Affects:** First-run experience, migration from other readers (Feedly, Inoreader)

**Notes:** High priority for M1 — without it, onboarding from an existing reader is manual.

---

## Derived edge computation schedule

**Question:** When are `SIMILAR_TO` and `RELATED_TO` edges recomputed?

**Affects:** Graph freshness, write performance, poller architecture

**Options:**
- On every poll (fresh but potentially expensive)
- On a separate scheduled job (configurable interval)
- On demand (triggered via API)

---

## Webhook support

**Question:** Should Reed notify an external endpoint when new items matching a filter arrive?

**Affects:** API scope, complexity, use cases (automation, Zapier-style workflows)

---

## Feed discovery

**Question:** Given a website URL (not a feed URL), should Reed find the feed automatically?

**Affects:** UX of adding feeds — parsing `<link rel="alternate">` from the page

**Notes:** Common and expected behaviour in RSS readers. Low complexity, high UX value.

---

## Repository name confirmation

**Question:** Is `reed` available and clean on GitHub, PyPI, and Docker Hub?

**Status:** GitHub repo created at `simonives/reed` (private). PyPI and Docker Hub not yet checked.
