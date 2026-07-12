<template>
  <div class="help" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" @click.self="close">
    <div class="help__card">
      <header class="help__header">
        <h2>Keyboard shortcuts</h2>
        <button class="btn" aria-label="Close" @click="close">Esc</button>
      </header>
      <dl class="help__list">
        <div v-for="row in shortcuts" :key="row.keys" class="help__row">
          <dt>
            <span v-for="k in row.keys.split(' ')" :key="k" class="kbd">{{ k }}</span>
          </dt>
          <dd>{{ row.label }}</dd>
        </div>
      </dl>
    </div>
  </div>
</template>

<script setup>
import { useUiStore } from '../stores/ui'

const ui = useUiStore()

const shortcuts = [
  { keys: 'j', label: 'Next item' },
  { keys: 'k', label: 'Previous item' },
  { keys: 'Space', label: 'Page down / advance to next item' },
  { keys: 'm', label: 'Toggle read / unread' },
  { keys: 's', label: 'Toggle starred' },
  { keys: 'o', label: 'Open item in new tab' },
  { keys: 'v', label: 'Open original URL in new tab' },
  { keys: 'g h', label: 'Go to all items' },
  { keys: 'g u', label: 'Go to unread' },
  { keys: 'g s', label: 'Go to starred' },
  { keys: '?', label: 'Show this reference' },
]

function close() {
  ui.showHelp = false
}
</script>

<style scoped>
.help {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  z-index: 50;
}

.help__card {
  width: 420px;
  max-width: calc(100vw - var(--space-6));
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.help__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.help__header h2 {
  font-size: 1rem;
}

.help__list {
  padding: var(--space-2) var(--space-4) var(--space-4);
}

.help__row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}

.help__row dt {
  display: flex;
  gap: var(--space-1);
  width: 96px;
  flex-shrink: 0;
}

.help__row dd {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
</style>
