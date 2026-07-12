<template>
  <section class="itemlist" aria-label="Items">
    <ViewHeader />

    <div class="itemlist__scroll">
      <p v-if="items.loading && !items.items.length" class="list-state">Loading…</p>
      <p v-else-if="items.error" class="list-state list-state--error">
        Could not load items: {{ items.error.message }}
      </p>
      <p v-else-if="!items.items.length" class="list-state">Nothing to read here.</p>

      <template v-else>
        <ItemRow
          v-for="item in items.items"
          :key="item.id"
          :item="item"
          :selected="item.id === items.selectedId"
          @select="items.select($event)"
          @toggle-star="items.toggleStar($event)"
        />
        <button v-if="items.hasMore" class="load-more" :disabled="items.loading" @click="items.loadMore()">
          {{ items.loading ? 'Loading…' : 'Load more' }}
        </button>
      </template>
    </div>
  </section>
</template>

<script setup>
import ItemRow from './ItemRow.vue'
import ViewHeader from './ViewHeader.vue'
import { useItemsStore } from '../stores/items'

const items = useItemsStore()
</script>

<style scoped>
.itemlist {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.itemlist__scroll {
  flex: 1;
  overflow-y: auto;
}
</style>
