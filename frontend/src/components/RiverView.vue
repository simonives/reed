<template>
  <section class="river" aria-label="River of news">
    <ViewHeader chrome />

    <div ref="scrollEl" class="river__scroll">
      <p v-if="items.loading && !items.items.length" class="list-state">Loading…</p>
      <p v-else-if="items.error" class="list-state list-state--error">
        Could not load items: {{ items.error.message }}
      </p>
      <p v-else-if="!items.items.length" class="list-state">Nothing to read here.</p>

      <template v-else>
        <div v-for="item in items.items" :key="item.id" class="river__entry">
          <ItemRow
            :item="item"
            :selected="item.id === items.selectedId"
            variant="river"
            @select="items.select($event)"
            @toggle-star="items.toggleStar($event)"
          />
          <p
            v-if="item.id === items.selectedId && items.detailError"
            class="list-state list-state--error"
            role="alert"
          >
            Could not load this item. Select it again to retry.
          </p>
          <div v-if="item.id === items.selectedId && items.detail" class="river__article">
            <div class="action-bar river__actions">
              <button class="btn" :class="{ 'btn--active': items.detail.read }" @click="items.toggleRead(items.detail)">
                <span class="kbd">m</span> {{ items.detail.read ? 'Read' : 'Mark read' }}
              </button>
              <a v-if="items.detail.url" class="btn" :href="safeHref(items.detail.url)" target="_blank" rel="noopener noreferrer">
                <span class="kbd">v</span> Source
              </a>
            </div>
            <ArticleBody :html="rawBody" />
          </div>
        </div>
        <button v-if="items.hasMore" class="load-more" :disabled="items.loading" @click="items.loadMore()">
          {{ items.loading ? 'Loading…' : 'Load more' }}
        </button>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import ArticleBody from './ArticleBody.vue'
import ItemRow from './ItemRow.vue'
import ViewHeader from './ViewHeader.vue'
import { useItemsStore } from '../stores/items'
import { safeHref } from '../lib/url'

const items = useItemsStore()
const scrollEl = ref(null)

const rawBody = computed(() => {
  const d = items.detail
  if (!d) return ''
  return d.reader_content || d.content
})

defineExpose({ scrollEl })
</script>

<style scoped>
.river {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.river__scroll {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.river__article {
  margin: 0 0 var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--radius) var(--radius);
  background: var(--bg-raised);
}

.river__actions {
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border);
}
</style>
