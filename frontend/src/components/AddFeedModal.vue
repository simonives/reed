<template>
  <div class="modal-backdrop overlay" @click.self="close">
    <section class="modal" role="dialog" aria-label="Add feed">
      <header class="modal__head">
        <h2>Add feed</h2>
        <button class="icon-btn" aria-label="Close" @click="close">×</button>
      </header>

      <form @submit.prevent="onSubmit">
        <input
          v-model.trim="url"
          type="url"
          required
          placeholder="Feed or site URL"
          aria-label="Feed or site URL"
        />
        <button type="submit" class="btn btn--primary" :disabled="busy || !url">
          {{ busy ? 'Checking…' : 'Add' }}
        </button>
      </form>

      <p v-if="message" class="message" role="alert">{{ message }}</p>

      <ul v-if="candidates.length > 1" class="candidates">
        <li v-for="feed in candidates" :key="feed.url">
          <button class="candidate" :disabled="busy" @click="subscribe(feed.url)">
            <span class="candidate__title">{{ feed.title || feed.url }}</span>
            <span class="candidate__url">{{ feed.url }}</span>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useFeedsStore } from '../stores/feeds'
import { useItemsStore } from '../stores/items'
import { useUiStore } from '../stores/ui'

const feeds = useFeedsStore()
const items = useItemsStore()
const ui = useUiStore()

const url = ref('')
const busy = ref(false)
const message = ref('')
const candidates = ref([])

function close() {
  ui.showAddFeed = false
}

async function onSubmit() {
  busy.value = true
  message.value = ''
  candidates.value = []
  try {
    const found = await feeds.discover(url.value)
    if (found.length === 0) {
      message.value = 'No feeds found at that URL.'
    } else if (found.length === 1) {
      await subscribe(found[0].url)
    } else {
      candidates.value = found
    }
  } catch (err) {
    message.value = err.message || 'Could not check that URL.'
  } finally {
    busy.value = false
  }
}

async function subscribe(feedUrl) {
  busy.value = true
  message.value = ''
  try {
    const created = await feeds.subscribe(feedUrl)
    close()
    ui.setView({ type: 'feed', label: created.display_name || created.title, id: created.id })
    items.load().catch((err) => console.error('Failed to refresh items after subscribe', err))
  } catch (err) {
    message.value = err.code === 'CONFLICT' ? 'Already subscribed to that feed.' : (err.message || 'Could not subscribe.')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
/* Top-align the add-feed modal rather than vertically centring it. */
.overlay {
  align-items: flex-start;
  padding-top: 12vh;
}
.modal {
  width: min(480px, 92vw);
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: var(--space-5);
}
.modal__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-4); }
form { display: flex; gap: var(--space-2); }
form input { flex: 1; padding: var(--space-2); border: 1px solid var(--border-strong); border-radius: var(--radius); }
.message { margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); }
.candidates { list-style: none; margin-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.candidate { display: flex; flex-direction: column; width: 100%; text-align: left; padding: var(--space-2); border: 1px solid var(--border); border-radius: var(--radius); }
.candidate:hover { background: var(--bg-hover); }
.candidate__title { font-size: var(--font-size-sm); }
.candidate__url { font-size: var(--font-size-xs); color: var(--text-muted); }
</style>
