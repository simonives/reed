<template>
  <div class="modal-backdrop scrim" @click.self="close">
    <aside class="drawer" role="dialog" :aria-label="`${feedName} settings`">
      <header class="drawer__head">
        <h2>{{ feedName }}</h2>
        <button class="icon-btn" aria-label="Close" @click="close">×</button>
      </header>

      <form @submit.prevent="onSave">
        <label>Display name
          <input v-model.trim="draft.display_name" aria-label="Display name" :placeholder="feed.title" />
        </label>
        <label>Poll interval (minutes, blank = default)
          <input v-model.number="draft.poll_interval_minutes" type="number" min="1" />
        </label>
        <label>Reader mode
          <select v-model="readerMode" aria-label="Reader mode">
            <option value="inherit">Use global default</option>
            <option value="on">On</option>
            <option value="off">Off</option>
          </select>
        </label>
        <label class="check"><input v-model="draft.is_active" type="checkbox" /> Active</label>

        <label>Tags
          <span class="tags">
            <span v-for="tag in draft.tags" :key="tag" class="tag">
              {{ tag }}<button type="button" aria-label="Remove tag" @click="removeTag(tag)">×</button>
            </span>
          </span>
          <input
            v-model.trim="tagInput"
            placeholder="Add tag, Enter"
            @keydown.enter.prevent="addTag"
          />
        </label>

        <p v-if="error" class="error" role="alert">{{ error }}</p>

        <footer class="drawer__foot">
          <button type="button" class="btn" data-test="refresh" :disabled="busy" @click="onRefresh">
            {{ refreshing ? 'Refreshing…' : 'Refresh now' }}
          </button>
          <button type="submit" class="btn btn--primary" :disabled="busy">Save</button>
          <button type="button" class="btn btn--danger" data-test="delete" :disabled="busy" @click="onDelete">Delete</button>
        </footer>
      </form>

      <dl class="status">
        <div><dt>Last fetched</dt><dd>{{ formatDateTime(feed.last_fetched_at) || '—' }}</dd></div>
        <div><dt>Next poll</dt><dd>{{ formatDateTime(feed.next_poll_at) || '—' }}</dd></div>
        <div v-if="feed.consecutive_errors"><dt>Errors</dt><dd class="danger">{{ feed.consecutive_errors }} — {{ feed.last_error }}</dd></div>
      </dl>
    </aside>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useFeedsStore } from '../stores/feeds'
import { useUiStore } from '../stores/ui'
import { formatDateTime } from '../lib/format'

const feeds = useFeedsStore()
const ui = useUiStore()

const feed = computed(() => feeds.feeds.find((f) => f.id === ui.editingFeedId) || {})
const feedName = computed(() => feed.value.display_name || feed.value.title || 'Feed')

const draft = reactive({
  display_name: feed.value.display_name || '',
  poll_interval_minutes: feed.value.poll_interval_minutes ?? null,
  is_active: feed.value.is_active ?? true,
  tags: [...(feed.value.tags || [])],
})
// reader_mode_enabled is a nullable tri-state (null = inherit global default).
// Use string sentinels to avoid binding <select> directly to null/boolean.
function toSentinel(v) {
  if (v === true) return 'on'
  if (v === false) return 'off'
  return 'inherit'
}
function fromSentinel(s) {
  if (s === 'on') return true
  if (s === 'off') return false
  return null
}
const readerMode = ref(toSentinel(feed.value.reader_mode_enabled))
const tagInput = ref('')
const busy = ref(false)
const refreshing = ref(false)
const error = ref('')

function addTag() {
  const t = tagInput.value.trim()
  if (t && !draft.tags.includes(t)) draft.tags.push(t)
  tagInput.value = ''
}
function removeTag(tag) {
  draft.tags = draft.tags.filter((t) => t !== tag)
}
function close() {
  ui.closeFeedEditor()
}

async function onSave() {
  busy.value = true
  error.value = ''
  try {
    await feeds.update(ui.editingFeedId, {
      display_name: draft.display_name || null,
      poll_interval_minutes: draft.poll_interval_minutes || null,
      reader_mode_enabled: fromSentinel(readerMode.value),
      is_active: draft.is_active,
      tags: draft.tags,
    })
    close()
  } catch (err) {
    error.value = err.message || 'Could not save feed.'
  } finally {
    busy.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  error.value = ''
  try {
    await feeds.refresh(ui.editingFeedId)
  } catch (err) {
    error.value = err.message || 'Could not refresh feed.'
  } finally {
    refreshing.value = false
  }
}

async function onDelete() {
  if (!window.confirm(`Delete ${feedName.value}? This removes the feed and its items.`)) return
  busy.value = true
  try {
    await feeds.remove(ui.editingFeedId)
    close()
  } catch (err) {
    error.value = err.message || 'Could not delete feed.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
/* Slide the drawer in from the right edge. */
.scrim { justify-content: flex-end; }
.drawer { width: min(380px, 92vw); height: 100%; overflow-y: auto; background: var(--bg-raised); border-left: 1px solid var(--border); padding: var(--space-5); }
.drawer__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-4); }
form { display: flex; flex-direction: column; gap: var(--space-4); }
form label { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--font-size-sm); }
form label.check { flex-direction: row; align-items: center; gap: var(--space-2); }
.tags { display: flex; flex-wrap: wrap; gap: var(--space-1); margin-bottom: var(--space-1); }
.tag { display: inline-flex; gap: 4px; padding: 2px var(--space-2); background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 999px; font-size: var(--font-size-xs); }
.drawer__foot { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
.btn--danger { color: var(--color-danger); border-color: var(--color-danger); }
.status { margin-top: var(--space-5); font-size: var(--font-size-xs); color: var(--text-muted); display: flex; flex-direction: column; gap: var(--space-2); }
.status dt { font-weight: 600; }
.danger { color: var(--color-danger); }
.error { color: var(--color-danger); font-size: var(--font-size-sm); }
</style>
