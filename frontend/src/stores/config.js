import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'

// Runtime config from the backend Config node. Defaults mirror the server's
// CONFIG_DEFAULTS so the UI behaves sensibly before the first load resolves.
const DEFAULTS = {
  default_theme: 'system',
  items_per_page: 50,
  mark_read_on_open: true,
  reader_mode_enabled: true,
  default_poll_interval_minutes: 60,
  accent_color: '#3b82f6',
  font_size_base: 16,
  reading_width: 760,
  line_height: 1.65,
  font_family_reading: 'system-ui, sans-serif',
}

export const useConfigStore = defineStore('config', () => {
  const values = ref({ ...DEFAULTS })
  const loaded = ref(false)

  async function load() {
    const { data } = await api.get('/config')
    values.value = { ...DEFAULTS, ...data }
    loaded.value = true
  }

  // PATCH only the changed keys; the response echoes the full effective config.
  async function save(patch) {
    const { data } = await api.patch('/config', patch)
    values.value = { ...DEFAULTS, ...data }
  }

  return { values, loaded, load, save }
})
