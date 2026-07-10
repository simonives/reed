# ADR-008: Vue 3 + Vite for the web UI

## Status

Accepted

## Context

Reed's v1 web UI requires:

- A three-pane layout (feed list, article list, reading pane) with independently-scrollable, keyboard-navigable panes
- Keyboard shortcuts (`j`/`k` to navigate items, `n`/`p` to move between feeds, `r` to toggle reader mode, `s` to star) that update multiple panes simultaneously without a page reload
- Mark-as-read tracking as the user navigates — scroll position and read state are client-side concerns
- Virtual list rendering for feeds with hundreds of items
- Smooth pane transitions and responsive interaction across the reading loop

The UI also consumes a fully-designed REST API (`/api/v1/`), which is shared with the MCP server. Any rendering model needs to sit cleanly on top of that API.

Three options were evaluated:

**Jinja2 server-side templates** — Zero JavaScript dependencies. Every interaction triggers a full page reload. The three-pane layout cannot be implemented without significant vanilla JavaScript, which means building a SPA anyway, without the structure. Keyboard shortcuts require manual DOM event listeners with no reactive binding. Ruled out.

**HTMX** — Server returns HTML fragments; HTMX swaps them into the DOM. Eliminates full page reloads. Excellent for form-heavy CRUD and settings flows. Breaks down for the reading loop: shared client-side state (active feed, selected item, read status) cannot be managed by HTML-over-the-wire. Complex keyboard interactions across panes require dropping into Alpine.js or vanilla JS, producing a multi-library accumulation of workarounds. Ruled out.

**Vue 3 + Vite** — A reactive component framework running in the browser, consuming the REST API. The three-pane layout is the native use case for this model. Client-side state management (Pinia) handles active selection and read state cleanly. Keyboard shortcuts are first-class `keydown` event bindings on reactive state. Vite provides a minimal, fast build pipeline.

## Decision

Vue 3 + Vite is the web UI rendering model.

- `frontend/` at the repository root contains the Vue 3 application
- Pinia manages shared UI state (active feed, selected item, read/starred tracking)
- Vite builds the static bundle; the Dockerfile uses a multi-stage build to produce `dist/` and serve it from the FastAPI container as a static mount
- The Vue app calls `/api/v1/` exclusively — no server-rendered HTML for the UI

**Vue 3 over React or Svelte:**
- Vue 3 Composition API maps more naturally to Python developer intuitions than React hooks
- The FastAPI ecosystem has the most examples and tooling around the FastAPI + Vue 3 pairing
- Vue 3 tree-shaking produces competitive bundle sizes without Svelte's smaller component ecosystem

## Consequences

**Positive:**
- The wireframed three-pane layout can be built directly, without workarounds
- Keyboard navigation, virtual lists, and scroll-based read tracking are idiomatic in this model
- The REST API is the single source of truth — Vue UI and MCP server are both consumers; no coupling between them
- Vite's HMR makes frontend development fast during M2

**Negative:**
- Build step: `npm install && vite build` is added to the Dockerfile multi-stage build
- Two languages in the repository: Python (backend) and TypeScript/JavaScript (frontend)
- Contributors need both Python and frontend tooling installed for full-stack development; backend-only contributors can work without Node

## Frontend structure

```
frontend/
  index.html
  vite.config.js
  package.json
  src/
    main.js
    App.vue
    views/
      FeedListView.vue
      ArticleListView.vue
      ArticleReaderView.vue
      SettingsView.vue
    components/
      FeedItem.vue
      ArticleRow.vue
      ReaderPane.vue
      SearchBar.vue
    stores/
      feeds.js      ← Pinia: subscribed feeds, active feed
      articles.js   ← Pinia: item list, selected item, read state
      ui.js         ← Pinia: pane layout, keyboard mode, reader mode
    composables/
      useKeyboard.js     ← j/k/n/p/r/s shortcuts
      useReadTracking.js ← mark read on navigate/scroll
      useReaderMode.js   ← fetch full-text content
    api/
      client.js     ← Axios instance with X-API-Key header
      feeds.js
      articles.js
      search.js
```
