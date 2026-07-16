<template>
  <nav class="sidebar" aria-label="Feeds and views">
    <header class="sidebar__brand">
      <span class="sidebar__wordmark">Reed</span>
      <button class="icon-btn" title="Settings" aria-label="Settings" @click="ui.toggleSettings()">⚙</button>
      <ViewChrome />
    </header>

    <ul class="sidebar__views">
      <li>
        <button class="view" :class="{ 'view--active': isView('unread') }" @click="setView('unread', 'All unread')">
          <span>All unread</span>
          <span v-if="feeds.totalUnread" class="badge">{{ feeds.totalUnread }}</span>
        </button>
      </li>
      <li>
        <button class="view" :class="{ 'view--active': isView('all') }" @click="setView('all', 'All items')">
          <span>All items</span>
        </button>
      </li>
      <li>
        <button class="view" :class="{ 'view--active': isView('starred') }" @click="setView('starred', 'Starred')">
          <span>Starred</span>
        </button>
      </li>
    </ul>

    <div class="sidebar__feeds-head">
      <h2 class="sidebar__heading">Feeds</h2>
      <button class="icon-btn" title="Add feed" aria-label="Add feed" @click="ui.toggleAddFeed()">+</button>
    </div>
    <p v-if="feeds.loading && !feeds.feeds.length" class="sidebar__hint">Loading…</p>
    <p v-else-if="!feeds.feeds.length" class="sidebar__hint">No feeds yet.</p>
    <ul v-else class="sidebar__feeds">
      <li v-for="feed in feeds.feeds" :key="feed.id">
        <button
          class="view"
          :class="{ 'view--active': isFeed(feed.id) }"
          @click="setView('feed', feed.display_name || feed.title, feed.id)"
        >
          <span class="view__label">
            <span
              v-if="feed.consecutive_errors > 0"
              class="dot dot--error"
              :title="`${feed.consecutive_errors} consecutive errors`"
            ></span>
            {{ feed.display_name || feed.title }}
          </span>
          <span v-if="feed.unread_count" class="badge">{{ feed.unread_count }}</span>
        </button>
        <button class="feed-gear icon-btn" title="Feed settings" aria-label="Feed settings" @click.stop="ui.editFeed(feed.id)">⚙</button>
      </li>
    </ul>
  </nav>
</template>

<script setup>
import ViewChrome from './ViewChrome.vue'
import { useFeedsStore } from '../stores/feeds'
import { useUiStore } from '../stores/ui'

const feeds = useFeedsStore()
const ui = useUiStore()

function isView(type) {
  return ui.view.type === type
}

function isFeed(id) {
  return ui.view.type === 'feed' && ui.view.id === id
}

function setView(type, label, id) {
  ui.setView({ type, label, id })
}
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-3);
  background: var(--bg-subtle);
  border-right: 1px solid var(--border);
  overflow-y: auto;
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2) var(--space-4);
}

.sidebar__wordmark {
  flex: 1;
  font-weight: 600;
  font-size: 1.1rem;
}

.sidebar__views,
.sidebar__feeds {
  list-style: none;
}

.sidebar__heading {
  margin: var(--space-4) var(--space-2) var(--space-1);
  font-size: var(--font-size-xs);
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.sidebar__hint {
  padding: var(--space-2);
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}

.view {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2);
  border-radius: var(--radius);
  color: var(--text);
  font-size: var(--font-size-sm);
  text-align: left;
}

.view:hover {
  background: var(--bg-hover);
}

.view--active {
  background: var(--bg-selected);
  color: var(--accent-color);
}

.view__label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge {
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot--error {
  background: var(--color-danger);
}

.sidebar__feeds-head { display: flex; align-items: center; justify-content: space-between; }

.sidebar__feeds li { position: relative; }
.feed-gear { position: absolute; right: var(--space-1); top: 50%; transform: translateY(-50%); opacity: 0; }
.sidebar__feeds li:hover .feed-gear,
.sidebar__feeds li:focus-within .feed-gear { opacity: 1; }
@media (max-width: 900px) { .feed-gear { opacity: 1; } }
</style>
