# Future Directions

Capabilities Reed doesn't have yet, that go beyond the v1/v2 scope decisions in `design/user-patterns.md`. These are not committed roadmap items, they are patterns worth building against once a concrete need justifies the design and maintenance cost. Each entry should graduate to `open-decisions.md` (if it blocks a specific component) or a GitHub issue (if it's ready to be scoped for implementation) once someone is actually ready to build it.

---

## Active monitoring, beyond passive feed polling

**The gap.** Reed's entire ingestion model today is passive: subscribe to a feed, poll it on an interval, ingest whatever the publisher chooses to expose. That breaks down for sources that either don't publish a feed at all, or publish one that's stale or incomplete relative to the live page. Many of the most valuable sources for Simon's HR tech / AI governance / employment law watch (regulator decision databases, parliamentary bill trackers, vendor changelogs with no RSS) fall into this gap.

Active monitoring means: given a URL (and a filter, and/or a thing to watch for), periodically fetch the live page and detect meaningful change, emitting a new `Item` when it happens. This is a second ingestion path alongside feed polling, not a replacement for it. Most sources should stay on RSS; this is for the subset that can't be served that way.

Raised 18 Sep 2026, after evaluating [Scrapling](https://github.com/D4Vinci/Scrapling) (BSD-3-Clause, bypasses Cloudflare Turnstile/Interstitial, handles JS-rendered pages via Playwright) for a different purpose and recognising the overlap with this long-standing gap. Full evaluation and a validated example (FWC decision search) in [issue #278](https://github.com/simonives/reed/issues/278). Not scoped for implementation, this document exists to capture the *pattern*, independent of which fetch tool eventually implements it.

There are two genuinely different sub-patterns here, and conflating them is the main design risk.

### Pattern A: new-item detection on a filtered source

The simpler case. A source (a search results page, a filtered listing) returns a set of discrete, permanently-identified items. Monitoring means: fetch the current result set, diff item IDs against the last-seen set, emit new items as they appear. No entity ever changes state, once "AI Kill Switch and Data Centre Control Bill 2026" v. Case #12345 exists in the result set, it exists forever, and a poll either sees it or doesn't.

**Validated example:** the Fair Work Commission's decision search (`fwc.gov.au/document-search`). Server-rendered (Drupal Views + Facets), no bot protection, filters compose as GET query parameters, so a "saved search" is just a URL:

```
https://www.fwc.gov.au/document-search?search-ui=decisions&keyword=<terms>&f[0]=case-type:<facet-id>
```

Tested live: unfair dismissal decisions (`case-type:241359`) mentioning "artificial intelligence" returned 21 real matches, each carrying a clean document-date chip and clickable case-type/bench-type tags. A permanent case ID appearing that wasn't seen last poll is the entire signal. Fetchable with `scrapling.Fetcher` (plain HTTP, no browser needed) since the results are server-rendered.

This pattern is comparatively easy to build: one snapshot per poll, a set-diff against the previous snapshot, done. It maps cleanly onto Reed's existing `Feed` -> `Item` model if a "monitored search" is treated as a feed whose poller does an HTTP GET + HTML parse instead of an RSS parse.

### Pattern B: entity lifecycle tracking

The harder case, and the one that actually motivated this document. Some things worth monitoring aren't a static, permanently-identified item, they're an entity that moves through a sequence of states over time, and "new" isn't the interesting event, *state change* is. The concrete case: a Bill moving through First Reading -> Second Reading -> Third Reading -> Passed Both Houses -> Royal Assent -> in force as an Act.

This is materially different from Pattern A because:

- The entity's identity can be stable (one record, one URL) or can fracture across sources (a Bill and its resulting Act may live in entirely separate databases, under different titles, with no guaranteed cross-reference)
- The interesting signal is a field changing (status: "Before Senate" -> "Passed both houses"), not a new record appearing
- An entity can also terminate without ever reaching the end state (lapsed, withdrawn, negatived at a vote), so "still pending" and "finished, unsuccessfully" both need to be representable
- Detecting a state change requires storing the entity's *previous* state to diff against, not just its existence, so the poller needs a small state snapshot per tracked entity, not just a set of seen IDs

**Source matters enormously here, and the two candidates evaluated for the Bills use case illustrate the point:**

- **AustLII** (`austlii.edu.au`) splits Bills and Acts into two separate databases (`au/legis/cth/bill/` vs. the Consolidated Acts database) with no reliable link field between a Bill and the Act it becomes. Titles often change ("X Bill 2026" -> "X Act 2026"). Tracking a Bill to enactment here means entity resolution across two sources, effectively fuzzy title/date matching, which is a much harder and less reliable build. AustLII's static pages also need `DynamicFetcher` (JS execution) to get past a 403, and its search CGI endpoint (`sinosrch.cgi`) is Cloudflare-hardened hard enough that even `StealthyFetcher`'s Turnstile solver failed after 3 attempts. Workable only via the static alphabetical Bill-title index, not a precise keyword search.
- **The Australian Parliament's own site** (`aph.gov.au/Parliamentary_Business/Bills_Legislation`) tracks a Bill's full progression as fields on a *single record*. Tested live: `Bills_Search_Results?q=artificial+intelligence&bs=1&pbh=1&bhor=1&ra=1&np=1&pmb=1` returned "AI Kill Switch and Data Centre Control Bill 2026" via a plain, unprotected HTTP GET (no bot protection encountered at all), and the bill's detail page (`Bills_Search_Results/Result?bId=<id>`) shows First/Second/Third reading and assent status inline. This is the right source for this pattern: single source of truth, built-in status tracking, trivially fetchable.

**Design implication:** for any future "track entity X through a lifecycle" build, source selection should actively favour a single authoritative source with built-in status fields over reconstructing state from multiple disconnected sources. The latter is a research project in entity resolution; the former is a straightforward polling problem with a small state machine.

**Open questions, once someone is ready to build this:**

- Data model: does a tracked entity need a new node type distinct from `Item` (a `TrackedEntity` or similar, with a `status` property and a `status_history` list), or is a sequence of `Item`s per entity (one per state change) sufficient and more consistent with the existing graph?
- What counts as a terminal state worth stopping polling for (assented; also negatived, withdrawn, lapsed at prorogation), versus states that should keep the entity under active poll
- Poll cadence for lifecycle-tracked entities is almost certainly not the same as `default_poll_interval_minutes`, a Bill's status might not change for weeks, then change twice in one sitting week
- Whether this generalises beyond Bills (job status trackers, application status pages, shipment tracking, anything with a discrete state machine and a status field) or is narrow enough to purpose-build for legislation specifically
