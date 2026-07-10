# User Flows

This document maps the primary user journeys through Reed. Each flow defines the steps, decision points, and system behaviour. Wireframes are downstream of these flows.

Flows marked **v1** ship before 1.0.0. Flows marked **v2** are explicitly deferred.

---

## 1. First run and onboarding

**Trigger:** User accesses Reed for the first time (fresh Docker deployment or from-source install).

```
User opens Reed in browser
        │
        ▼
Setup screen (no feeds, no config)
        │
        ├── Set API key?  ─── Already set via REED_API_KEY env var
        │                     Skip to next step
        │
        ▼
Choose: How would you like to add feeds?
        │
        ├── Import OPML file  ──► Flow 3a: OPML import
        │
        ├── Add feeds manually ──► Flow 2: Add a feed
        │
        └── Skip for now ──► Empty reading view with prompt
```

**System behaviour on first run:**
- Config node is created with all defaults
- Schema migrations are run (or initial schema is created)
- The setup screen does not re-appear once at least one feed exists

---

## 2. Add a feed (v1)

**Trigger:** User clicks "Add feed" from the feed list or navigation.

```
User enters a URL
        │
        ▼
Is the URL a valid feed? (Reed attempts to parse it directly)
        │
        ├── Yes ──► Show feed preview (title, description, recent items)
        │                   │
        │                   ▼
        │           User confirms
        │                   │
        │                   ▼
        │           Optional: set display name, tags, poll interval
        │                   │
        │                   ▼
        │           Feed subscribed ──► Immediate poll triggered
        │                              Feed appears in list
        │
        └── No ──► Is the URL a website? (Reed checks for feed links)
                        │
                        ├── Feed(s) found ──► Show discovered feed(s)
                        │                    User selects one ──► preview flow above
                        │
                        └── No feed found ──► Error: no feed discovered
                                             Suggest: check the URL or try /feed, /rss
```

**Feed preview shows:**
- Feed title and description
- Site URL
- Last 3 item titles and dates
- Estimated update frequency (derived from recent item timestamps)

---

## 3a. OPML import (v1)

**Trigger:** User selects "Import OPML" from the Add feed menu or Settings.

```
User uploads OPML file
        │
        ▼
Reed parses OPML
        │
        ▼
Preview: list of feeds found
  - Feed title + URL
  - Folder/category name (to be mapped to a tag)
  - Already subscribed? (flagged, will be skipped)
        │
        ▼
User reviews and confirms (or deselects individual feeds)
        │
        ▼
Import runs
  - Feeds subscribed in batch
  - OPML folder names mapped to tags
  - Immediate polls queued (rate-limited — not all at once)
        │
        ▼
Import summary: N feeds added, M skipped (already subscribed), K failed
```

**Error handling:** Feeds that fail validation (unreachable URL, not a valid feed) are listed in the summary. The import is not aborted by individual failures.

---

## 3b. OPML export (v1)

**Trigger:** User selects "Export" → "Feed list (OPML)" from Settings.

```
User initiates export
        │
        ▼
Reed generates OPML (tags → folders, all active feeds)
        │
        ▼
Browser downloads opml file: reed-feeds-YYYY-MM-DD.opml
```

Instant — no async step needed.

---

## 3c. JSON profile export (v1)

**Trigger:** User selects "Export" → "Full data export (JSON)" from Settings.

```
User initiates export
        │
        ▼
Reed queues async export job
(feeds + item metadata + read/starred state + notes + tags)
        │
        ▼
Settings shows: "Export in progress..."
        │
        ▼ (job completes — seconds to minutes depending on library size)
"Export ready" — download link appears
        │
        ▼
Browser downloads: reed-export-YYYY-MM-DD.json
```

---

## 3d. Instance backup and restore (v1)

**Trigger:** User is migrating Reed to a new server.

**Export:**
```
User selects "Export" → "Instance backup" from Settings
        │
        ▼
Reed queues async backup job (complete instance state)
        │
        ▼
Download: reed-backup-YYYY-MM-DD.json
```

**Restore (new instance):**
```
User installs Reed on new server (fresh instance)
        │
        ▼
Setup screen appears
        │
        ▼
User selects "Restore from backup"
        │
        ▼
Upload backup file
        │
        ▼
Warning: "This will replace all current data. Continue?"
User confirms (or cancels)
        │
        ▼
Restore runs
        │
        ▼
Reed restarts / reloads — fully restored state
```

---

## 4. Daily reading loop (v1)

**Trigger:** User opens Reed to read.

```
User opens Reed
        │
        ▼
Feed list (left) shows unread counts per feed
        │
        ▼
User selects a feed or "All unread"
        │
        ▼
Item list (centre) shows unread items, newest first
        │
        ▼
User selects an item (click or j/k keys)
        │
        ▼
Reading pane (right) shows:
  - Title, author, feed name, published date
  - Full content (reader mode if enabled)
  - Topics (clickable)
  - Tags (editable)
  - "More like this" sidebar (collapsed by default)
        │
        ▼
Item is marked read automatically (if mark-read-on-open is on)
OR user presses m to toggle
        │
        ▼
User reads, then:
  ├── j → next item (m auto-marks previous as read)
  ├── s → star the item
  ├── o → open original in new tab
  ├── Share button → share sheet (Flow 8)
  ├── Annotate button → note editor (Flow 7)
  └── Click topic tag → Topic explorer (Flow 6b)
```

---

## 5. Feed management (v1)

### Edit a feed

```
User opens Feed Settings (from feed list context menu or feed detail)
        │
        ▼
Edit form shows current values:
  - Display name override
  - Poll interval (shows effective value; null = global default)
  - Reader mode (shows effective value; null = global default)
  - Active / paused toggle
  - Tags assigned to this feed
        │
        ▼
User saves changes
        │
        ▼
Changes applied immediately
Poll interval change takes effect on next scheduled poll
```

### Remove a feed

```
User selects "Remove feed" from feed settings
        │
        ▼
Confirmation: "Remove [Feed Name]?
  Items already read will be retained in your library.
  Unread items will be removed."
        │
        ├── Confirm ──► Feed node set to inactive; unread items removed;
        │               read/starred items retained with feed reference
        │
        └── Cancel ──► No change
```

**Rationale for retaining read items:** Read and starred items may have notes, tags, and graph edges the user values. Removing a feed does not erase the user's reading history.

---

## 6a. Search (v1)

**Trigger:** User activates search (keyboard shortcut `/` or search button).

```
User types search query
        │
        ▼
Results appear as user types (debounced — 300ms)
  - Items matching title/content (FTS)
  - Notes matching content
  - Each result shows: title, feed, date, excerpt with match highlighted
        │
        ▼
User can filter results:
  - Unread only
  - Starred only
  - Date range
  - Specific feed
        │
        ▼
User selects a result ──► Item opens in reading pane
```

---

## 6b. Topic explorer (v1)

**Trigger:** User clicks a topic tag on an item, or opens the Topic explorer from navigation.

```
Topic page opens:
  - Topic name and item count
  - Related topics (by weight — ordered list)
  - Item list: all items about this topic, newest first
        │
        ▼
User can:
  ├── Click a related topic ──► Navigate to that topic page
  ├── Select an item ──► Opens in reading pane
  └── Filter by: date range, feed, unread only
```

---

## 6c. More like this (v1)

**Trigger:** User expands the "More like this" sidebar while reading an item.

```
Sidebar expands (right side of reading pane)
        │
        ▼
Shows: up to 10 items similar to the current item
  Each result shows:
  - Title, feed, date
  - Shared topics (the reason for similarity)
  - Read/starred state
        │
        ▼
User clicks a result ──► Item opens in reading pane
                          "More like this" updates for the new item
```

---

## 6d. Starred-adjacent discovery (v1)

**Trigger:** User opens the "Discover" view from navigation.

```
Discover view shows:
  - Heading: "Based on your starred items"
  - List of unread items with similarity scores
  - Each result shows: title, feed, date, shared topics with starred items
        │
        ▼
User reads and acts on items as in the daily reading loop
```

**Refresh:** The Discover view is recomputed whenever derived edges are recomputed (every 6 hours, or on demand).

---

## 7. Notes and annotations (v1)

**Trigger:** User clicks "Add note" or presses `n` while reading an item.

```
Note editor opens (inline below article or in a drawer)
        │
        ▼
User types freeform text
        │
        ▼
Auto-saves on blur / after 2 seconds of inactivity
        │
        ▼
Note indicator appears on item in list view (small icon)
```

**Editing an existing note:**
```
User clicks note or presses n
        │
        ▼
Note editor opens with existing content
User edits and saves (auto-save) or deletes
```

---

## 8. Share sheet (v1)

**Trigger:** User clicks the share button on an item or presses `Shift+S`.

```
Share sheet opens (modal or popover)
  Shows: configured share targets as buttons
        │
        ▼
User selects a target:
  │
  ├── Copy link ──► URL copied to clipboard. Toast: "Link copied."
  │
  ├── Copy as Markdown ──► [Title](URL) copied. Toast: "Copied as Markdown."
  │
  ├── Raindrop.io ──► Article saved to configured collection.
  │                   Toast: "Saved to Raindrop."
  │                   (Error state if API key invalid or request fails)
  │
  └── Webhook ──► HTTP POST sent to configured URL.
                  Toast: "Sent." or error if request fails.
```

**No share targets configured:**
```
Share sheet opens with message:
  "No share targets configured. Add them in Settings."
  [Go to Settings] button
```

---

## 9. CSS customisation (v1)

**Trigger:** User opens Settings → Appearance.

```
Appearance settings shows:
  - Theme: Light / Dark / System (radio)
  - Accent colour: colour picker (hex input + visual swatch)
  - Font size: slider with live preview (12–20px)
  - Reading width: slider with live preview (600–1200px)
  - Line height: slider with live preview (1.4–2.0)
  - Reading font: dropdown (System UI / Georgia / Merriweather)
  - [Reset to defaults] button
        │
        ▼
Changes apply live (injected as :root CSS variables)
        │
        ▼
User navigates away — changes are persisted to Config node
```

**Live preview:** Changes apply to the Settings page itself in real time — no save-and-reload cycle.

---

## 10. Global settings (v1)

**Trigger:** User opens Settings → General.

```
General settings:
  - Default poll interval: number input (minutes)
  - Reader mode: toggle (on/off)
  - Items per page: dropdown (25 / 50 / 100)
  - Mark read on open: toggle
  - API key: display (masked) + regenerate button
        │
        ▼
Save button (or auto-save on change)
        │
        ▼
Changes apply immediately
Poll interval change takes effect on next poll cycle
```

---

## 11. MCP usage (v1)

MCP flows are initiated by the AI client, not the user directly. These are the expected interaction patterns from an AI client's perspective.

**Reading session:**
```
AI client calls list_feeds
        │
        ▼
AI client calls get_items(unread: true, limit: 20)
        │
        ▼
AI client calls get_item(item_id) for items of interest
        │
        ▼
AI client calls find_similar_items(item_id) to expand thread
        │
        ▼
AI client calls mark_read(item_ids) to tidy up
        │
        ▼
AI client returns summary to user
```

**Research query:**
```
User asks AI: "What's in my library about AI governance?"
        │
        ▼
AI client calls search(query: "AI governance")
        │
        ▼
AI client calls explore_topic(topic_name: "AI Governance")
        │
        ▼
AI client calls find_similar_items for top results
        │
        ▼
AI client calls annotate_item for relevant items
        │
        ▼
AI client returns structured summary with linked items
```

---

## Flow → screen mapping

| Flow | Screens required |
|---|---|
| First run | Setup / welcome screen |
| Add feed | Add feed modal / drawer |
| OPML import | Import modal with preview |
| Export | Settings → Export section |
| Backup restore | Setup screen (restore path) |
| Daily reading | Three-pane reading view |
| Feed management | Feed settings drawer |
| Search | Search overlay / panel |
| Topic explorer | Topic page |
| More like this | Reading pane sidebar |
| Discover | Discover view |
| Notes | Inline note editor |
| Share sheet | Share modal / popover |
| CSS customisation | Settings → Appearance |
| Global settings | Settings → General |
