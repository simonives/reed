<template>
  <header class="view-header">
    <h1 class="view-header__title">
      {{ ui.title }}
      <span v-if="items.total" class="view-header__count">({{ items.total }})</span>
    </h1>

    <SearchBar class="view-header__search" />

    <div class="view-header__actions">
      <span v-if="catchUpError" class="view-header__error" role="alert">{{ catchUpError }}</span>
      <button v-if="items.canCatchUp" class="btn" title="Mark all as read" @click="catchUp">
        Catch up
      </button>
      <ViewChrome v-if="chrome" />
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import SearchBar from './SearchBar.vue'
import ViewChrome from './ViewChrome.vue'
import { useItemsStore } from '../stores/items'
import { useUiStore } from '../stores/ui'

defineProps({
  chrome: { type: Boolean, default: false },
})

const ui = useUiStore()
const items = useItemsStore()

const catchUpError = ref('')

async function catchUp() {
  catchUpError.value = ''
  try {
    await items.markViewRead()
  } catch {
    catchUpError.value = 'Could not mark all read.'
  }
}
</script>

<style scoped>
.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.view-header__title {
  font-size: 0.95rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.view-header__count {
  color: var(--text-muted);
  font-weight: 400;
}

.view-header__search {
  flex: 1;
  min-width: 0;
}

.view-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.view-header__error {
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}
</style>
