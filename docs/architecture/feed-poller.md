# Feed Poller

> This document is a stub. Will specify the polling architecture, scheduling model, HTTP caching behaviour, and error handling.

## Placeholder

Content will cover:

- Async worker model (asyncio)
- Per-feed poll interval configuration
- Conditional GET (ETag and Last-Modified)
- Feed parsing (library choice — feedparser or equivalent)
- Error handling and back-off strategy
- New item detection and deduplication (guid)
- Write path into the Kuzu graph
- Derived edge recomputation trigger
