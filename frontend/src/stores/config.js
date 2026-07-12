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
}

export const useConfigStore = defineStore('config', () => {
  const values = ref({ ...DEFAULTS })
  const loaded = ref(false)

  async function load() {
    const { data } = await api.get('/config')
    values.value = { ...DEFAULTS, ...data }
    loaded.value = true
  }

  return { values, loaded, load }
})
