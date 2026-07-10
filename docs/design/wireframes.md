# Wireframes

ASCII wireframes for all v1 screens. All diagrams render in GitHub's code blocks (monospace, left-aligned). Verify rendering at `github.com/simonives/reed`.

These are layout wireframes, not visual designs. Colours, typography, and spacing are defined in `principles.md` and resolved during implementation.

---

## Legend

```
+-------+     Box border
|       |     Vertical border
[Label]       Button or action
[___________] Text input field
[Option    v] Dropdown
[ ] / [x]     Checkbox (unchecked / checked)
( ) / (o)     Radio button (unselected / selected)
[ON ] / [OFF] Toggle
>             Active / selected item
*             Starred item
#             Unread count badge
...           Truncated text
~             Placeholder / empty content area
```

---

## 1. Setup — Welcome screen

Shown on first run when no feeds exist and no config has been applied.

```
+------------------------------------------------------------------+
|  Reed                                                            |
+------------------------------------------------------------------+
|                                                                  |
|                                                                  |
|    Welcome to Reed                                               |
|    Your self-hosted RSS reader.                                  |
|                                                                  |
|    How would you like to get started?                            |
|                                                                  |
|    +---------------------------+  +---------------------------+  |
|    |                           |  |                           |  |
|    |  [+] Import OPML file     |  |  [+] Add my first feed   |  |
|    |                           |  |                           |  |
|    |  Migrate from Feedly,     |  |  Paste a feed URL or     |  |
|    |  Inoreader, or any        |  |  website address and     |  |
|    |  other RSS reader.        |  |  Reed finds the feed.    |  |
|    |                           |  |                           |  |
|    +---------------------------+  +---------------------------+  |
|                                                                  |
|    Or  [Skip for now — start with an empty library]             |
|                                                                  |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 2. Setup — Instance restore

Shown on first run when the user chooses to restore from a backup.

```
+------------------------------------------------------------------+
|  Reed — Restore from backup                                      |
+------------------------------------------------------------------+
|                                                                  |
|    Restore instance                                              |
|    Upload a Reed backup file to restore a previous instance.     |
|                                                                  |
|    Backup file                                                   |
|    [____________________________________________________] Browse |
|                                                                  |
|    ! This will replace all current data on this instance.        |
|      Feeds, items, notes, tags, and settings will be            |
|      overwritten. This action cannot be undone.                  |
|                                                                  |
|    [ ] I understand this will replace all current data           |
|                                                                  |
|    [Cancel]                          [Restore instance]          |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 3. Main reading view — Three-pane (default)

The primary UI. Left: feed list. Centre: item list. Right: reading pane.

```
+----------------------+------------------------+---------------------------+
| Reed              [?]| All unread (47)    [/] | How AI is changing the    |
+----------------------+                        | nature of knowledge work  |
| [+] Add feed         | [ ] How AI is chang... |                           |
|                      |     The Batch  · 2h    | The Batch · Andrew Ng     |
| > All unread    (47) |                        | 10 Jul 2026 · 8 min read  |
|   Starred        (3) | [ ] The quiet death... |                           |
|   Discover           |     Ben Evans  · 3h    | AI Governance             |
|                      |                        | Knowledge Work            |
| FEEDS                | [*] Why open source... | Future of Work            |
|   The Batch      (4) |     Simon W.   · 5h    |                           |
|   Ben Evans      (2) |                        | Full article content      |
|   Simon Willison (6) | [ ] Stratechery Dai... | renders here with the     |
|   Stratechery    (3) |     Stratechery · 1d   | configured font, size,    |
|   MIT Tech Rev.  (1) |                        | and reading width.        |
|   WIRED          (0) | [ ] The economics o... |                           |
|   Hacker News   (24) |     MIT Tech R. · 1d   | Paragraphs, images, and   |
|   The Economist  (7) |                        | embedded content display  |
|                      | [ ] Notes from the ... | as the author intended.   |
|                      |     The Economis · 2d  |                           |
|                      |                        | [m Read][s Star][n Note]  |
|                      |                        | [v Source]   [Share    v] |
+----------------------+------------------------+---------------------------+
  j/k navigate   m mark read   s star   n note   o open   / search   ? help
```

---

## 4. Main reading view — River of news

Alternate layout. Single chronological stream, no sidebar.

```
+------------------------------------------------------------------+
| Reed                                 [/] Search     [?] Help     |
+------------------------------------------------------------------+
| All unread (47)  [Feeds v]  [Unread v]  [Newest v]               |
+------------------------------------------------------------------+
|                                                                  |
| [ ] How AI is changing the nature of knowledge work              |
|     The Batch · Andrew Ng · 2 hours ago                         |
|     AI is not merely a productivity tool. The more important ... |
|                                                     [m][s][n][>] |
+------------------------------------------------------------------+
| [ ] The quiet death of the long-form technology essay            |
|     Ben Evans · 3 hours ago                                      |
|     Something has shifted in how technology gets written about.  |
|                                                     [m][s][n][>] |
+------------------------------------------------------------------+
| [*] Why open source matters more now than ever                   |
|     Simon Willison · 5 hours ago                    * Starred    |
|     The centralisation of AI infrastructure has created a new .. |
|                                                     [m][s][n][>] |
+------------------------------------------------------------------+
```

---

## 5. Add feed — URL entry

```
+------------------------------------------------------------------+
|  Add feed                                               [x] Close |
+------------------------------------------------------------------+
|                                                                  |
|  Feed or website URL                                             |
|  [____________________________________________] [Add feed]       |
|                                                                  |
|  Paste a feed URL (RSS or Atom) or a website address.           |
|  Reed will find the feed automatically.                          |
|                                                                  |
|  Examples:                                                       |
|    https://simonwillison.net/atom/everything/                    |
|    https://simonwillison.net                                     |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 5b. Add feed — Feed discovered, preview

```
+------------------------------------------------------------------+
|  Add feed                                               [x] Close |
+------------------------------------------------------------------+
|                                                                  |
|  [____________________________________________] [Add feed]       |
|  https://simonwillison.net                                       |
|                                                                  |
|  + Feed found                                                    |
|  +--------------------------------------------------------------+|
|  |  Simon Willison's Weblog                                     ||
|  |  simonwillison.net · Updates roughly daily                   ||
|  |                                                              ||
|  |  Recent items:                                               ||
|  |    Why open source matters more now than ever  · 5h          ||
|  |    Weeknotes: things I learned this week        · 2d          ||
|  |    Notes on using LLMs for code review          · 5d          ||
|  +--------------------------------------------------------------+|
|                                                                  |
|  Display name  [Simon Willison's Weblog        ]  (optional)    |
|  Tags          [ai, blogs                      ]  (optional)    |
|  Poll interval [(o) Default (60 min)  ( ) Custom [____] min ]   |
|                                                                  |
|  [Cancel]                                    [Subscribe to feed] |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 6. OPML import — Preview

```
+------------------------------------------------------------------+
|  Import OPML                                            [x] Close |
+------------------------------------------------------------------+
|                                                                  |
|  [____________________________________] Browse   [Import OPML]  |
|  feedly-export.opml                                              |
|                                                                  |
|  47 feeds found across 5 folders.                                |
|  3 feeds are already subscribed and will be skipped.            |
|                                                                  |
|  [x] Select all                         [Deselect already added] |
|                                                                  |
|  FOLDER: AI & Technology  (tag: ai-technology)                  |
|  [x] The Batch                 thebatch.andrewng.org/rss         |
|  [x] Simon Willison's Weblog   simonwillison.net/atom/...        |
|  [x] MIT Technology Review     feeds.technologyreview.com/...    |
|  [ ] TechCrunch  (already subscribed)                            |
|                                                                  |
|  FOLDER: Strategy  (tag: strategy)                              |
|  [x] Stratechery               stratechery.com/feed              |
|  [x] Ben Evans                 ben-evans.com/benedictevans...    |
|                                                                  |
|  ... 39 more feeds                          [Show all]           |
|                                                                  |
|  [Cancel]               [Import 44 feeds (skip 3 existing)]      |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 7. Feed settings drawer

Slides in from the right when a feed is selected for editing.

```
+------------------------------------------------------------------+
|  Feed settings                                          [x] Close |
+------------------------------------------------------------------+
|                                                                  |
|  The Batch                                                       |
|  thebatch.andrewng.org/rss                                       |
|  Subscribed 15 Jun 2026 · 142 items · Last updated 2h ago       |
|                                                                  |
|  Display name                                                    |
|  [The Batch                                ]  (blank = use feed) |
|                                                                  |
|  Tags                                                            |
|  [ai, newsletters                          ]                     |
|                                                                  |
|  Poll interval                                                   |
|  (o) Use default (60 min)    ( ) Custom  [____] minutes          |
|                                                                  |
|  Reader mode                                                     |
|  (o) Use default (On)        ( ) On      ( ) Off                 |
|                                                                  |
|  Feed status                                                     |
|  [ON ] Active                                                    |
|                                                                  |
|  [Save changes]                          [Remove this feed...]   |
|                                                                  |
|  ! Remove feed: read and starred items are kept. Unread items    |
|    are removed.                                                  |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 8. Search overlay

Opens over the current view when `/` is pressed or the search icon is clicked.

```
+------------------------------------------------------------------+
| [/ Search Reed_______________________________________] [x] Close  |
+------------------------------------------------------------------+
| Searching: All items    [Unread only] [Starred only]             |
| Date: [Any time     v]  Feed: [All feeds          v]             |
+------------------------------------------------------------------+
|                                                                  |
|  Showing 12 results for "AI governance"                          |
|                                                                  |
|  Why AI governance frameworks keep failing                       |
|  The Economist · 3 days ago                           [x] Read   |
|  ...the core problem with **AI governance** is that the          |
|  frameworks emerge after the systems are already deployed...     |
|                                                                  |
|  The missing accountability layer in AI governance               |
|  MIT Technology Review · 1 week ago                             |
|  ...proposals for **AI governance** tend to focus on            |
|  technical standards while ignoring institutional design...      |
|                                                                  |
|  AI governance as competitive advantage                          |
|  Simon Willison's Weblog · 2 weeks ago             [*] Starred   |
|  Note: "Key framing for the quarterly governance write-up"                |
|  ...organisations that treat **AI governance** seriously now...  |
|                                                                  |
|  [Load more results]                                             |
|                                                                  |
+------------------------------------------------------------------+
```

---

## 9. Topic explorer page

```
+------------------------------------------------------------------+
| < Back    Topic: AI Governance                   (47 items)      |
+------------------------------------------------------------------+
|                                                                  |
| Related topics                                                   |
| [Responsible AI (0.72)] [Algorithmic Accountability (0.61)]      |
| [AI Policy (0.58)] [Machine Learning (0.44)] [Ethics (0.39)]     |
|                                                                  |
+------------------+-----------------------------------------------+
| Filter           | Items about AI Governance                     |
| [Unread only  v] |                                               |
| [All feeds    v] | [ ] Why AI governance frameworks keep fail... |
| [All time     v] |     The Economist · 3d                        |
|                  |                                               |
|                  | [ ] The missing accountability layer in AI... |
|                  |     MIT Technology Review · 1w                |
|                  |                                               |
|                  | [*] AI governance as competitive advantage    |
|                  |     Simon Willison · 2w                       |
|                  |                                               |
|                  | [ ] Why regulation always lags the technol... |
|                  |     Stratechery · 3w                          |
|                  |                                               |
|                  | [Load more]                                   |
+------------------+-----------------------------------------------+
```

---

## 10. Reading pane — More like this sidebar open

The "More like this" panel expands within the reading view.

```
+----------------------+------------------------+-------------------+
| Reed              [?]| All unread (47)    [/] | How AI is chan... |
+----------------------+                        +-------------------+
| [+] Add feed         | [ ] How AI is chang... | < Back to list    |
|                      |     The Batch  · 2h    +-------------------+
| > All unread    (47) |                        | How AI is         |
|   Starred        (3) | [ ] The quiet death... | changing the      |
|   Discover           |     Ben Evans  · 3h    | nature of         |
|                      |                        | knowledge work    |
| FEEDS                | [*] Why open source... |                   |
|   The Batch      (4) |     Simon W.   · 5h    | The Batch · 2h    |
|   Ben Evans      (2) |                        | AI Governance     |
|   Simon Willison (6) | [ ] Stratechery Dai... | Knowledge Work    |
|   Stratechery    (3) |     Stratechery · 1d   +-------------------+
|   MIT Tech Rev.  (1) |                        | More like this v  |
|   WIRED          (0) | [ ] The economics o... +-------------------+
|   Hacker News   (24) |     MIT Tech R. · 1d   | The missing ac... |
|                      |                        | MIT TR · 0.78     |
|                      |                        | AI Governance     |
|                      |                        |                   |
|                      |                        | Why regulation... |
|                      |                        | Stratechery · 0.71|
|                      |                        | AI Policy         |
|                      |                        |                   |
|                      |                        | AI governance ... |
|                      |                        | Simon W. · 0.65   |
|                      |                        | Responsible AI    |
+----------------------+------------------------+-------------------+
```

---

## 11. Discover view — Starred-adjacent

```
+------------------------------------------------------------------+
| Reed                                                          [?] |
+------------------------------------------------------------------+
| Discover                                         [Refresh]        |
| Unread items similar to your starred items                       |
+------------------------------------------------------------------+
|                                                                  |
| Based on 12 starred items · Last updated 1 hour ago              |
|                                                                  |
+------------------------------------------------------------------+
| [ ] The missing accountability layer in AI governance            |
|     MIT Technology Review · 1 week ago                           |
|     Similar to: "AI governance as competitive advantage" (0.78)  |
|     Shared topics: AI Governance · Responsible AI                |
|                                          [m Read] [s Star] [>]   |
+------------------------------------------------------------------+
| [ ] Why open source matters more now than ever                   |
|     Simon Willison's Weblog · 5 hours ago                        |
|     Similar to: "Why open source wins in the long run" (0.71)   |
|     Shared topics: Open Source · Developer Tools                 |
|                                          [m Read] [s Star] [>]   |
+------------------------------------------------------------------+
| [ ] The economics of attention in the age of AI assistants       |
|     MIT Technology Review · 2 days ago                           |
|     Similar to: "How AI is changing knowledge work" (0.65)       |
|     Shared topics: AI · Knowledge Work · Future of Work          |
|                                          [m Read] [s Star] [>]   |
+------------------------------------------------------------------+
```

---

## 12. Note editor — Inline

The note editor appears inline below the article content when `n` is pressed.

```
+------------------------------------------------------------------+
|  ...end of article content.                                      |
|                                                                  |
|  [m Mark read] [s Star] [n Note] [v Source]  [Share v]          |
+------------------------------------------------------------------+
|  Your note                                          [x] Dismiss  |
|                                                                  |
|  [________________________________________________]             |
|  [________________________________________________]             |
|  [________________________________________________]             |
|  [________________________________________________]             |
|                                                                  |
|  Auto-saved                        [Delete note]                 |
+------------------------------------------------------------------+
```

**With existing note:**

```
+------------------------------------------------------------------+
|  Your note                                [Edit]  [x] Dismiss   |
|                                                                  |
|  Key framing for the quarterly governance write-up. The               |
|  accountability gap argument is worth pulling into the          |
|  committee terms of reference discussion.                           |
|                                                                  |
|  Saved 10 Jul 2026, 3:42pm                                      |
+------------------------------------------------------------------+
```

---

## 13. Share sheet

Opens as a popover when the Share button is clicked.

```
                                    +--------------------------+
                                    | Share                    |
                                    +--------------------------+
                                    | How AI is changing the   |
                                    | nature of knowledge work |
                                    | The Batch · 10 Jul 2026  |
                                    +--------------------------+
                                    | [=] Copy link            |
                                    | [M] Copy as Markdown     |
                                    +--------------------------+
                                    | [R] Save to Raindrop.io  |
                                    | [W] Send to webhook      |
                                    +--------------------------+
                                    | Configure targets in     |
                                    | Settings -> Share        |
                                    +--------------------------+
```

**Post-share confirmation (toast, top-right):**

```
+------------------------------+
| + Saved to Raindrop.io       |
+------------------------------+
```

---

## 14. Settings — General

```
+------------------+-------------------------------------------+
| Settings         |  General                                  |
+------------------+-------------------------------------------+
| > General        |                                           |
|   Appearance     |  Polling                                  |
|   Share targets  |  Default poll interval  [60    ] minutes  |
|   Export         |  (Applied to all feeds without an         |
|   Import         |   individual override.)                   |
|   API            |                                           |
+------------------+  Reading                                  |
                   |  Reader mode            [ON ]             |
                   |  Mark read on open      [ON ]             |
                   |  Items per page         [50          v]   |
                   |                                           |
                   |  Display                                  |
                   |  Default layout   (o) Three-pane          |
                   |                   ( ) River of news       |
                   |  Theme            [System (auto)      v]  |
                   |                                           |
                   |  [Save changes]                           |
                   |                                           |
                   +-------------------------------------------+
```

---

## 15. Settings — Appearance

```
+------------------+-------------------------------------------+
| Settings         |  Appearance                               |
+------------------+-------------------------------------------+
| General          |                                           |
| > Appearance     |  Theme                                    |
|   Share targets  |  ( ) Light  ( ) Dark  (o) System (auto)  |
|   Export         |                                           |
|   Import         |  Accent colour                            |
|   API            |  [#3B82F6    ] [PREVIEW SWATCH    ]       |
+------------------+                                           |
                   |  Reading font                             |
                   |  [System UI (default)              v]     |
                   |    System UI / Georgia / Merriweather     |
                   |                                           |
                   |  Font size                                |
                   |  Aa  [----o-----------]  Aa               |
                   |  12px       16px (default)       20px     |
                   |                                           |
                   |  Reading width                            |
                   |  [-----|----------]                       |
                   |  600px  760px (default)          1200px   |
                   |                                           |
                   |  Line height                              |
                   |  [------o---------]                       |
                   |  1.4     1.65 (default)              2.0  |
                   |                                           |
                   |  Preview applies to this page live.       |
                   |                                           |
                   |  [Reset to defaults]       [Save changes] |
                   |                                           |
                   +-------------------------------------------+
```

---

## 16. Settings — Share targets

```
+------------------+-------------------------------------------+
| Settings         |  Share targets                            |
+------------------+-------------------------------------------+
| General          |                                           |
| Appearance       |  Configure where articles can be shared   |
| > Share targets  |  from the reading view.                   |
|   Export         |                                           |
|   Import         |  Active targets                           |
|   API            |  +---------------------------------------+|
+------------------+  | [=] Copy link           Built-in  [ON]||
                   |  | [M] Copy as Markdown     Built-in  [ON]||
                   |  | [R] Raindrop.io          [Edit]    [ON]||
                   |  | [W] Webhook: n8n         [Edit]   [ON] ||
                   |  +---------------------------------------+ |
                   |                                           |
                   |  [+ Add share target]                     |
                   |     Raindrop.io / Webhook                 |
                   |                                           |
                   +-------------------------------------------+
```

**Add Raindrop target (expanded):**

```
                   |  [+ Add share target]  v                  |
                   |  +---------------------------------------+ |
                   |  | Type   (o) Raindrop.io  ( ) Webhook  | |
                   |  |                                       | |
                   |  | Name   [Raindrop.io              ]   | |
                   |  | API key [______________________________]| |
                   |  | Default collection  [00.INBOX      v] | |
                   |  |                          [Test] [Save]| |
                   |  +---------------------------------------+ |
```

---

## 17. Settings — Export

```
+------------------+-------------------------------------------+
| Settings         |  Export                                   |
+------------------+-------------------------------------------+
| General          |                                           |
| Appearance       |  Feed list (OPML)                         |
| Share targets    |  Export your subscriptions for use in     |
| > Export         |  any RSS reader.                          |
|   Import         |  [Download OPML]                          |
|   API            |                                           |
+------------------+  Full data export (JSON)                  |
                   |  Feeds, items, notes, tags, and read      |
                   |  history. Use for archiving or analysis.  |
                   |  [Generate JSON export]                   |
                   |                                           |
                   |  Instance backup                          |
                   |  Complete backup for migrating to a new   |
                   |  Reed instance. Import via Settings ->    |
                   |  Import -> Restore from backup.           |
                   |  [Generate instance backup]               |
                   |                                           |
                   +-------------------------------------------+
```

---

## 18. Feed health view

Accessible from the Feeds section or via the `/graph/feed-health` API.

```
+------------------------------------------------------------------+
| Feed health                                                      |
+------------------------------------------------------------------+
|                                                                  |
| Inactive feeds  (no new items in 30+ days)                       |
+------------------------------------------------------------------+
| The Economist (Free)                                             |
| Last item: 15 Apr 2026 · 86 days ago                            |
| The feed is reachable but has published no new items.            |
|                               [Refresh now]  [Remove feed]       |
+------------------------------------------------------------------+
|                                                                  |
| Feeds with errors  (3+ consecutive failures)                     |
+------------------------------------------------------------------+
| WIRED (RSS)                                                      |
| 12 consecutive errors · Last error: Connection timeout           |
| Last successful fetch: 8 Jul 2026                                |
|                               [Retry now]    [Remove feed]       |
+------------------------------------------------------------------+
|                                                                  |
| All other feeds are healthy.                                     |
|                                                                  |
+------------------------------------------------------------------+
```
