<template>
  <div class="search-bar">
    <input
      ref="inputEl"
      type="search"
      class="search-bar__input"
      placeholder="Search… (press /)"
      :value="search.query"
      @input="search.setQuery($event.target.value)"
      @keydown.enter.prevent="onSubmit"
      @keydown.escape="onClear"
    />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useSearchStore } from '../stores/search'
import { useUiStore } from '../stores/ui'
import { useItemsStore } from '../stores/items'

const search = useSearchStore()
const ui = useUiStore()
const items = useItemsStore()
const inputEl = ref(null)

function focus() {
  inputEl.value?.focus()
  inputEl.value?.select()
}

function onSubmit() {
  const q = search.query.trim()
  if (!q) return
  search.setPreviousView({ ...ui.view })
  ui.setView({ type: 'search', q, label: `Search: "${q}"` })
  items.load()
}

function onClear() {
  const prev = search.previousView
  search.clear()
  if (ui.view.type === 'search') {
    ui.setView(prev || { type: 'unread', label: 'All unread' })
    items.load()
  }
  inputEl.value?.blur()
}

function onFocusSearch() {
  focus()
}

onMounted(() => window.addEventListener('reed:focus-search', onFocusSearch))
onBeforeUnmount(() => window.removeEventListener('reed:focus-search', onFocusSearch))
</script>

<style scoped>
.search-bar {
  flex: 1;
  min-width: 0;
}

.search-bar__input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font-size: var(--font-size-sm);
}

.search-bar__input:focus {
  outline: none;
  border-color: var(--accent-color);
}
</style>
