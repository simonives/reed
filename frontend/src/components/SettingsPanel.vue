<template>
  <div class="modal-backdrop" @click.self="close">
    <section class="panel" role="dialog" aria-label="Settings">
      <header class="panel__head">
        <h2>Settings</h2>
        <button class="icon-btn" aria-label="Close settings" @click="close">×</button>
      </header>

      <nav class="tabs">
        <button :class="{ 'tab--active': tab === 'reading' }" @click="tab = 'reading'">Reading</button>
        <button :class="{ 'tab--active': tab === 'appearance' }" @click="tab = 'appearance'">Appearance</button>
      </nav>

      <form @submit.prevent="onSave">
        <div v-show="tab === 'reading'" class="fields">
          <label>Theme
            <select v-model="draft.default_theme">
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <label>Default poll interval (minutes)
            <input v-model.number="draft.default_poll_interval_minutes" type="number" min="1" />
          </label>
          <label>Items per page
            <input v-model.number="draft.items_per_page" type="number" min="1" max="200" />
          </label>
          <label class="check">
            <input v-model="draft.mark_read_on_open" type="checkbox" /> Mark read on open
          </label>
          <label class="check">
            <input v-model="draft.reader_mode_enabled" type="checkbox" /> Reader mode by default
          </label>
        </div>

        <div v-show="tab === 'appearance'" class="fields">
          <label>Accent colour
            <input v-model="draft.accent_color" type="color" />
          </label>
          <label>Base font size ({{ draft.font_size_base }}px)
            <input v-model.number="draft.font_size_base" type="range" min="12" max="24" />
          </label>
          <label>Reading width ({{ draft.reading_width }}px)
            <input v-model.number="draft.reading_width" type="range" min="480" max="1200" step="20" />
          </label>
          <label>Line height ({{ draft.line_height }})
            <input v-model.number="draft.line_height" type="range" min="1.2" max="2.2" step="0.05" />
          </label>
          <label>Reading font
            <select v-model="draft.font_family_reading">
              <option v-for="font in FONT_OPTIONS" :key="font.value" :value="font.value">{{ font.label }}</option>
            </select>
          </label>
        </div>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <footer class="panel__foot">
          <button type="button" class="btn" @click="close">Cancel</button>
          <button type="submit" class="btn btn--primary" :disabled="saving">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </footer>
      </form>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useConfigStore } from '../stores/config'
import { useUiStore } from '../stores/ui'

// The `value` stacks must match the backend allowlist exactly — the canonical
// source is FONT_FAMILY_STACKS in src/reed/config.py; a mismatch means a 400 on save.
const FONT_OPTIONS = [
  { label: 'System', value: 'system-ui, sans-serif' },
  { label: 'Humanist sans', value: "'Segoe UI', Roboto, system-ui, sans-serif" },
  { label: 'Serif', value: "Georgia, 'Times New Roman', serif" },
  { label: 'Monospace', value: "ui-monospace, 'SF Mono', Menlo, monospace" },
]
const EDITABLE = [
  'default_theme', 'default_poll_interval_minutes', 'items_per_page',
  'mark_read_on_open', 'reader_mode_enabled', 'accent_color',
  'font_size_base', 'reading_width', 'line_height', 'font_family_reading',
]

const config = useConfigStore()
const ui = useUiStore()

const tab = ref('reading')
const saving = ref(false)
const error = ref('')
// Draft seeded from current config; only the diff is saved.
const draft = reactive(Object.fromEntries(EDITABLE.map((k) => [k, config.values[k]])))

function diff() {
  const changed = {}
  for (const key of EDITABLE) {
    const value = draft[key]
    // A cleared numeric input yields '' (or NaN) via v-model.number. Treat that
    // as "unchanged" rather than sending an empty value the backend rejects.
    if (value === '' || (typeof value === 'number' && Number.isNaN(value))) continue
    if (value !== config.values[key]) changed[key] = value
  }
  return changed
}

function close() {
  ui.showSettings = false
}

async function onSave() {
  const patch = diff()
  // Nothing to save — close without a PATCH; an empty body 422s ("No config
  // values provided") and would surface a spurious error.
  if (Object.keys(patch).length === 0) {
    close()
    return
  }
  saving.value = true
  error.value = ''
  try {
    await config.save(patch)
    close()
  } catch (err) {
    error.value = err.message || 'Could not save settings.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.panel {
  width: min(520px, 92vw);
  max-height: 88vh;
  overflow-y: auto;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: var(--space-5);
}
.panel__head { display: flex; justify-content: space-between; align-items: center; }
.tabs { display: flex; gap: var(--space-2); margin: var(--space-4) 0; }
.tabs button { padding: var(--space-1) var(--space-3); border-radius: var(--radius); color: var(--text-secondary); }
.tab--active { background: var(--bg-selected); color: var(--accent-color); }
.fields { display: flex; flex-direction: column; gap: var(--space-4); }
.fields label { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--font-size-sm); }
.fields label.check { flex-direction: row; align-items: center; gap: var(--space-2); }
.panel__foot { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-5); }
.error { color: var(--color-danger); font-size: var(--font-size-sm); margin-top: var(--space-3); }
</style>
