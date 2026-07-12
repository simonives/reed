<template>
  <article
    class="row"
    :class="{ 'row--selected': selected, 'row--read': item.read, 'row--river': variant === 'river' }"
    :aria-current="selected ? 'true' : undefined"
    tabindex="0"
    @click="$emit('select', item.id)"
    @keydown.enter.self="$emit('select', item.id)"
  >
    <span class="row__unread" :class="{ 'row__unread--on': !item.read }" aria-hidden="true"></span>

    <div class="row__body">
      <h3 class="row__title">{{ item.title }}</h3>
      <p class="row__meta">
        <span v-if="item.feed" class="row__feed">{{ item.feed.title }}</span>
        <span class="row__dot" aria-hidden="true">·</span>
        <time :datetime="item.published_at || item.fetched_at">{{ time }}</time>
      </p>
      <p v-if="variant === 'river' && item.summary" class="row__summary">{{ item.summary }}</p>
    </div>

    <button
      class="row__star"
      :class="{ 'row__star--on': item.starred }"
      :aria-pressed="item.starred"
      :aria-label="item.starred ? 'Unstar' : 'Star'"
      @click.stop="$emit('toggle-star', item)"
    >
      {{ item.starred ? '★' : '☆' }}
    </button>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { relativeShort } from '../lib/format'

const props = defineProps({
  item: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  variant: { type: String, default: 'list' }, // 'list' | 'river'
})

defineEmits(['select', 'toggle-star'])

const time = computed(() => relativeShort(props.item.published_at || props.item.fetched_at))
</script>

<style scoped>
.row {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}

.row:hover {
  background: var(--bg-hover);
}

.row--selected {
  background: var(--bg-selected);
}

.row--river {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: var(--space-3);
  background: var(--bg-raised);
}

.row__unread {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: transparent;
}

.row__unread--on {
  background: var(--accent-color);
}

.row__body {
  flex: 1;
  min-width: 0;
}

.row__title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  line-height: 1.35;
}

.row--read .row__title {
  font-weight: 400;
  color: var(--text-secondary);
}

.row__meta {
  display: flex;
  gap: var(--space-1);
  align-items: baseline;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}

.row__feed {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__summary {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.row__star {
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: 1rem;
  line-height: 1;
  height: fit-content;
}

.row__star--on {
  color: var(--color-star);
}
</style>
