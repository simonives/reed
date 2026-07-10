# UI/UX Design Principles

These principles define what Reed's interface should feel like and the constraints every design decision is measured against. Wireframes and component decisions are downstream of this document.

---

## The governing philosophy: get out of the way

Reed's UI exists to help a user read. It is not a product surface to be engaged with; it is a window to be looked through. Every element that draws attention to itself rather than to the content has failed its job.

The reference point is Google Reader (2005–2013): fast, keyboard-driven, unobtrusive, and entirely focused on the reading experience. Reed does not aspire to be more than that. It aspires to be exactly that, running on hardware the user controls, with an API and graph model underneath.

---

## Principles

### 1. Content is the UI

The article is the product. The chrome — navigation, controls, status indicators — is scaffolding. Scaffolding should be invisible until needed.

**In practice:**
- Maximum reading width; generous line height; clean typography
- Navigation collapses or moves out of the way in reading mode
- No persistent banners, badges, or notifications competing for attention
- Unread counts are informative, not anxiety-inducing — they do not flash or animate

---

### 2. Fast is a feature

A slow RSS reader breaks the reading habit. Speed is not a nice-to-have; it is core to the product.

**In practice:**
- Server-rendered or HTMX — no full-page JavaScript bundle to parse before content appears
- Item list is rendered immediately; full article content loads on demand
- Polling and graph computation happen in the background — the UI never blocks on them
- Keyboard navigation moves between items without a network round-trip

---

### 3. Keyboard-first

The target user grew up on Google Reader's keyboard shortcuts. They are not optional.

**Minimum viable shortcut set for v1:**

| Key | Action |
|---|---|
| `j` | Next item |
| `k` | Previous item |
| `Space` | Page down / advance to next item |
| `m` | Toggle read/unread |
| `s` | Toggle starred |
| `o` | Open item in new tab |
| `v` | Open original URL in new tab |
| `g` + `h` | Go to home / all items |
| `g` + `u` | Go to unread |
| `g` + `s` | Go to starred |
| `?` | Show keyboard shortcut reference |

Navigation within a feed or view requires no mouse. A user should be able to process their entire reading queue without touching a pointing device.

---

### 4. One layout, configured — not multiple modes

Reed defaults to a three-pane layout: feed list (left), item list (centre), reading pane (right). This is the established mental model for RSS readers.

A "river of news" single-stream view is available as a user preference — all items chronologically, no sidebar.

Two layouts. No more. Reed does not have a card view, a magazine view, a tile view. Visual complexity in the layout competes with content.

---

### 5. Progressive disclosure

Not everything needs to be visible all the time. Controls and metadata are revealed at the right moment:

- Topic tags, author, share controls appear when an item is open — not on the item list
- Feed health details appear in feed management — not on the main reading view
- Graph query results (More like this, Related topics) appear in a collapsible sidebar while reading — not by default on every item

The user reaches for depth when they want it. Reed does not push it at them.

---

### 6. Dark mode is a first-class citizen

Dark mode is not a cosmetic toggle applied after the fact. It is designed alongside the light theme from the start, using CSS custom properties throughout. System preference (`prefers-color-scheme`) is the default; the user can override in Settings.

Both themes share the same typography, spacing, and layout. The only difference is the colour palette.

---

### 7. Accessible by default

Accessibility is not a post-launch audit item.

**Baseline requirements for v1:**
- Semantic HTML throughout — `<article>`, `<nav>`, `<main>`, `<aside>` used correctly
- All interactive elements reachable by keyboard
- Sufficient colour contrast in both themes (WCAG AA minimum)
- Screen reader-compatible — `aria-label`, `role`, and live regions used correctly
- Focus indicators visible and not suppressed

---

### 8. Mobile: readable, not optimised

v1 is responsive enough to be usable on a phone — the reading pane fills the screen, the sidebar collapses. It is not optimised for mobile. Touch targets, swipe gestures, and a mobile-native reading experience are v2.

The target user accesses Reed from a desktop or laptop. Mobile access is not blocked; it is not the primary design surface.

---

### 9. Settings are minimal and purposeful

Every setting in Reed solves a real problem for a real user. Settings are not added because they are easy to add. The question for every proposed setting is: *who specifically needs this, and what breaks without it?*

**Settings that belong in v1:**
- API key management
- Global poll interval
- Reader mode on/off
- Default theme (light / dark / system)
- Items per page
- Mark read on open (on/off)
- CSS variable overrides (accent colour, font size, reading width, line height) — see below

**Settings that do not belong in v1:**
- Full custom CSS / skin upload
- Per-folder layout overrides

### CSS customisation in v1

Users can tweak Reed's appearance from Settings without editing a file. A small set of CSS custom properties is exposed as named controls — colour pickers, sliders, and dropdowns — stored in the Config node and injected into every page as `:root {}` overrides.

**v1 exposed variables:**

| Variable | Control | Default |
|---|---|---|
| `--accent-color` | Colour picker | Reed default blue |
| `--font-size-base` | Slider (12px–20px) | 16px |
| `--reading-width` | Slider (600px–1200px) | 760px |
| `--line-height` | Slider (1.4–2.0) | 1.65 |
| `--font-family-reading` | Dropdown (system-ui, Georgia, Merriweather) | system-ui |

These variables apply globally across both light and dark themes. A "Reset to defaults" button restores all values.

**v2 skin system:** Full CSS file upload or in-app CSS editor for users who want complete control over Reed's appearance. v1 variables remain as a convenience layer above the v2 system.

---

## What Reed's UI is not

- Not a content discovery engine (algorithmic recommendations do not belong in the feed view)
- Not a social reader (no public profiles, no follower counts, no engagement metrics)
- Not a productivity dashboard (no stats panels on the home screen)
- Not a news aggregator (Reed shows what the user subscribed to, in the order it was published)

The graph queries (More like this, Topic explorer) surface related content — but only when the user reaches for them. Reed does not push related content into the reading flow uninvited.
