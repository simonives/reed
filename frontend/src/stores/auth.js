import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getApiKey, setApiKey } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const apiKey = ref(getApiKey())
  const hasKey = computed(() => apiKey.value.length > 0)

  function save(key) {
    setApiKey(key.trim())
    apiKey.value = getApiKey()
  }

  function clear() {
    setApiKey('')
    apiKey.value = ''
  }

  return { apiKey, hasKey, save, clear }
})
