import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useSearchStore = defineStore('search', () => {
  const query = ref('')
  const filters = ref({})
  const previousView = ref(null)

  function setQuery(q) {
    query.value = q
  }

  function setFilters(f) {
    filters.value = { ...f }
  }

  function setPreviousView(view) {
    previousView.value = view
  }

  function clear() {
    query.value = ''
    filters.value = {}
  }

  return { query, filters, previousView, setQuery, setFilters, setPreviousView, clear }
})
