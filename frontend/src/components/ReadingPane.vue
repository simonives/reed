<template>
  <section ref="scrollEl" class="reading" aria-label="Article">
    <p v-if="!items.selectedId" class="reading__empty">Select an item to read.</p>
    <p v-else-if="items.detailLoading && !detail" class="reading__empty">Loading…</p>
    <p v-else-if="items.detailError" class="reading__empty" role="alert">
      Could not load this item. Select it again to retry.
    </p>

    <article v-else-if="detail" class="article">
      <header class="article__head">
        <h1 class="article__title">{{ detail.title }}</h1>
        <p class="article__meta">
          <span v-if="detail.feed">{{ detail.feed.title }}</span>
          <span v-if="detail.author"> · {{ detail.author.name }}</span>
        </p>
        <p class="article__meta article__meta--muted">
          <time v-if="published" :datetime="published">{{ formatDateTime(published) }}</time>
          <span v-if="readingTime"> · {{ readingTime }}</span>
        </p>
        <ul v-if="detail.tags.length" class="article__tags">
          <li v-for="tag in detail.tags" :key="tag" class="article__tag">{{ tag }}</li>
        </ul>
      </header>

      <div class="action-bar article__actions">
        <button class="btn" :class="{ 'btn--active': detail.read }" @click="items.toggleRead(detail)">
          <span class="kbd">m</span> {{ detail.read ? 'Read' : 'Mark read' }}
        </button>
        <button class="btn" :class="{ 'btn--active': detail.starred }" @click="items.toggleStar(detail)">
          <span class="kbd">s</span> {{ detail.starred ? 'Starred' : 'Star' }}
        </button>
        <a v-if="detail.url" class="btn" :href="detail.url" target="_blank" rel="noopener noreferrer">
          <span class="kbd">v</span> Source
        </a>
        <button v-if="canToggleReader" class="btn" @click="showReader = !showReader">
          {{ showReader ? 'Show original' : 'Show reader view' }}
        </button>
        <button
          v-else-if="canExtract"
          class="btn"
          :disabled="extracting"
          @click="extract"
        >
          {{ extracting ? 'Extracting…' : 'Reader view' }}
        </button>
      </div>

      <p v-if="extractError" class="article__error" role="alert">{{ extractError }}</p>

      <div v-if="detail.note" class="article__note">
        <strong>Note</strong>
        <p>{{ detail.note.body }}</p>
      </div>

      <ArticleBody :html="rawBody" />
    </article>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ArticleBody from './ArticleBody.vue'
import { useConfigStore } from '../stores/config'
import { useItemsStore } from '../stores/items'
import { formatDateTime } from '../lib/format'
import { pageDownScroll } from '../lib/scroll'

const items = useItemsStore()
const config = useConfigStore()

const scrollEl = ref(null)
const showReader = ref(true)
const extracting = ref(false)
const extractError = ref('')

const detail = computed(() => items.detail)
const published = computed(() => detail.value?.published_at || detail.value?.fetched_at)

const readingTime = computed(() => {
  const words = detail.value?.word_count || 0
  if (!words) return ''
  return `${Math.max(1, Math.round(words / 200))} min read`
})

const canToggleReader = computed(() => !!detail.value?.reader_content)
const canExtract = computed(
  () => !detail.value?.reader_content && !!detail.value?.url && config.values.reader_mode_enabled,
)

const rawBody = computed(() => {
  const d = detail.value
  if (!d) return ''
  return showReader.value && d.reader_content ? d.reader_content : d.content
})

// Reset per-article view state and scroll to top when the item changes.
watch(
  () => detail.value?.id,
  () => {
    showReader.value = true
    extractError.value = ''
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  },
)

async function extract() {
  if (!detail.value) return
  extracting.value = true
  extractError.value = ''
  try {
    await items.extractReader(detail.value.id)
    showReader.value = true
  } catch (err) {
    extractError.value = err.message || 'Could not extract article content.'
  } finally {
    extracting.value = false
  }
}

// Space paging: scroll the article; true once at the bottom so App advances.
function pageDown() {
  return pageDownScroll(scrollEl.value)
}

defineExpose({ pageDown })
</script>

<style scoped>
.reading {
  height: 100%;
  overflow-y: auto;
  background: var(--bg);
}

.reading__empty {
  padding: var(--space-6) var(--space-4);
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}

.article {
  max-width: var(--reading-width);
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}

.article__title {
  font-size: 1.6rem;
  line-height: 1.25;
  font-family: var(--font-family-reading);
}

.article__meta {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.article__meta--muted {
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.article__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
  list-style: none;
}

.article__tag {
  padding: 2px var(--space-2);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.article__actions {
  margin: var(--space-4) 0;
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.article__error {
  margin-bottom: var(--space-3);
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}

.article__note {
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--bg-subtle);
  border-left: 3px solid var(--accent-color);
  border-radius: var(--radius);
  font-size: var(--font-size-sm);
}

.article__note p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  white-space: pre-wrap;
}
</style>
