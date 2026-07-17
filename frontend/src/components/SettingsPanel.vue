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
        <button :class="{ 'tab--active': tab === 'import-export' }" @click="tab = 'import-export'">Import / Export</button>
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

        <div v-show="tab === 'import-export'" class="fields import-export">
          <div class="ie-section">
            <h3>Import subscriptions</h3>
            <p class="ie-hint">Select an OPML file from Feedly, Inoreader, or another RSS reader.</p>

            <div v-if="!opml.previewData && !opml.importResult">
              <label class="file-label">
                Choose OPML file
                <input
                  type="file"
                  accept=".opml,application/xml,text/xml"
                  @change="onFileSelect"
                  :disabled="opml.loading"
                />
              </label>
            </div>

            <div v-if="opml.previewData && !opml.importResult" class="preview-wrap">
              <p class="ie-count">
                {{ opml.previewData.candidates.length }} feed(s) found
                <span v-if="opml.previewData.unparseable > 0">
                  ({{ opml.previewData.unparseable }} skipped — no feed URL)
                </span>
              </p>
              <table class="preview-table">
                <thead>
                  <tr>
                    <th><input type="checkbox" :checked="allSelected" @change="toggleAll" /></th>
                    <th>Title</th>
                    <th>Tags</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in draftCandidates" :key="row.url">
                    <td><input type="checkbox" v-model="row.selected" /></td>
                    <td class="preview-title">{{ row.title }}</td>
                    <td><input v-model="row.tagInput" class="tag-input" /></td>
                    <td>
                      <span v-if="row.already_subscribed" class="badge badge--exists">Subscribed</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="ie-actions">
                <button type="button" class="btn" @click="resetImport">Cancel</button>
                <button
                  type="button"
                  class="btn btn--primary"
                  @click="onImport"
                  :disabled="opml.loading"
                >{{ opml.loading ? 'Importing…' : 'Import selected' }}</button>
              </div>
            </div>

            <div v-if="opml.importResult" class="import-result">
              <p>
                Import complete: {{ opml.importResult.added }} added,
                {{ opml.importResult.skipped }} skipped.
              </p>
              <ul v-if="opml.importResult.failed.length > 0" class="failed-list">
                <li v-for="f in opml.importResult.failed" :key="f.url">{{ f.url }}: {{ f.reason }}</li>
              </ul>
              <button type="button" class="btn" @click="resetImport">Import another file</button>
            </div>

            <p v-if="opml.error" class="error" role="alert">{{ opml.error }}</p>
          </div>

          <div class="ie-section">
            <h3>Export subscriptions</h3>
            <p class="ie-hint">Download all your Reed subscriptions as an OPML file.</p>
            <button
              type="button"
              class="btn btn--primary"
              data-testid="export-btn"
              @click="onExport"
              :disabled="opml.loading"
            >{{ opml.loading ? 'Exporting…' : 'Export subscriptions' }}</button>
          </div>

          <div class="ie-section">
            <h3>Export backup</h3>
            <p class="ie-hint">Download all your feeds, read state, stars, notes, and tags as JSON.</p>
            <button
              type="button"
              class="btn btn--primary"
              data-testid="export-backup-btn"
              @click="onExportBackup"
              :disabled="data.loading"
            >{{ data.loading ? 'Exporting…' : 'Download backup' }}</button>
          </div>

          <div class="ie-section">
            <h3>Restore from backup</h3>
            <p class="ie-hint ie-warn">⚠ This will permanently replace all your feeds, items, notes, and tags. Export a backup first.</p>

            <div v-if="!data.restoreResult">
              <label class="file-label">
                Choose backup file
                <input
                  type="file"
                  accept=".json,application/json"
                  @change="onRestoreFileSelect"
                  :disabled="data.loading"
                />
              </label>
              <p v-if="restoreFile" class="ie-hint">{{ restoreFile.name }}</p>
              <label v-if="restoreFile" class="file-label">
                Type "restore" to confirm
                <input
                  type="text"
                  v-model="restoreConfirm"
                  placeholder="restore"
                  :disabled="data.loading"
                />
              </label>
              <div class="ie-actions">
                <button
                  type="button"
                  class="btn btn--danger"
                  data-testid="restore-btn"
                  :disabled="restoreConfirm !== 'restore' || !restoreFile || data.loading"
                  @click="onRestore"
                >{{ data.loading ? 'Restoring…' : 'Restore' }}</button>
              </div>
              <p v-if="data.error" class="error" role="alert">{{ data.error }}</p>
            </div>

            <div v-if="data.restoreResult" class="restore-result">
              <p>
                Restored {{ data.restoreResult.feeds }} feed(s),
                {{ data.restoreResult.items }} item(s),
                {{ data.restoreResult.notes }} note(s),
                {{ data.restoreResult.tags }} tag(s).
              </p>
              <button type="button" class="btn btn--primary" @click="reloadPage">Reload</button>
            </div>
          </div>
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
import { computed, reactive, ref, watch } from 'vue'
import { useConfigStore } from '../stores/config'
import { useFeedsStore } from '../stores/feeds'
import { useOpmlStore } from '../stores/opml'
import { useUiStore } from '../stores/ui'
import { useDataStore } from '../stores/data'

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
const opml = useOpmlStore()
const feeds = useFeedsStore()
const data = useDataStore()

const tab = ref('reading')
const saving = ref(false)
const error = ref('')
const restoreFile = ref(null)
const restoreConfirm = ref('')
// Draft seeded from current config; only the diff is saved.
const draft = reactive(Object.fromEntries(EDITABLE.map((k) => [k, config.values[k]])))

const draftCandidates = ref([])
const allSelected = computed(
  () => draftCandidates.value.length > 0 && draftCandidates.value.every((r) => r.selected),
)

// Keep draftCandidates in sync with opml.previewData so that setting
// previewData directly (e.g. in tests) also populates the table.
watch(
  () => opml.previewData,
  (data) => {
    if (data) {
      draftCandidates.value = data.candidates.map((c) => ({
        ...c,
        selected: !c.already_subscribed,
        tagInput: c.tags.join(', '),
      }))
    } else {
      draftCandidates.value = []
    }
  },
  { immediate: true },
)

function onFileSelect(event) {
  const file = event.target.files?.[0]
  if (!file) return
  opml.preview(file)
}

function toggleAll(e) {
  draftCandidates.value.forEach((r) => {
    r.selected = e.target.checked
  })
}

function resetImport() {
  opml.reset()
  draftCandidates.value = []
}

async function onImport() {
  const selection = draftCandidates.value
    .filter((r) => r.selected)
    .map((r) => ({
      url: r.url,
      title: r.title,
      tags: r.tagInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    }))
  await opml.importFeeds(selection)
  await feeds.load()
}

async function onExport() {
  await opml.exportFeeds()
}

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

async function onExportBackup() {
  await data.exportBackup()
}

function onRestoreFileSelect(event) {
  restoreFile.value = event.target.files?.[0] ?? null
  restoreConfirm.value = ''
}

async function onRestore() {
  if (!restoreFile.value) return
  try {
    await data.restoreBackup(restoreFile.value)
  } catch {
    restoreFile.value = null
    restoreConfirm.value = ''
  }
}

function reloadPage() {
  window.location.reload()
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
.import-export { gap: var(--space-6); }
.ie-section { display: flex; flex-direction: column; gap: var(--space-3); }
.ie-section h3 { font-size: var(--font-size-sm); font-weight: 600; }
.ie-hint { font-size: var(--font-size-sm); color: var(--text-secondary); }
.file-label { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--font-size-sm); }
.preview-wrap { display: flex; flex-direction: column; gap: var(--space-3); }
.ie-count { font-size: var(--font-size-sm); color: var(--text-secondary); }
.preview-table { width: 100%; font-size: var(--font-size-sm); border-collapse: collapse; }
.preview-table th,
.preview-table td { padding: var(--space-1) var(--space-2); text-align: left; border-bottom: 1px solid var(--border); }
.preview-title { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-input { width: 100%; font: inherit; color: inherit; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: var(--radius); padding: 2px var(--space-1); }
.badge { font-size: var(--font-size-xs); padding: 1px var(--space-1); border-radius: var(--radius); }
.badge--exists { background: var(--bg-hover); color: var(--text-muted); }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
.import-result { font-size: var(--font-size-sm); display: flex; flex-direction: column; gap: var(--space-2); }
.failed-list { padding-left: var(--space-4); color: var(--color-danger); }
.ie-warn { color: var(--color-danger); }
.restore-result { font-size: var(--font-size-sm); display: flex; flex-direction: column; gap: var(--space-2); }
.btn--danger { background: var(--color-danger); color: #fff; border: none; }
.btn--danger:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
