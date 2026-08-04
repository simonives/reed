import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useShareStore = defineStore('share', () => {
  const targets = ref([])
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.get('/share/targets')
      targets.value = data
      loaded.value = true
    } catch (err) {
      error.value = err.message || 'Could not load share targets.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function ensureLoaded() {
    if (!loaded.value) await load()
  }

  async function create(type, name, config) {
    error.value = ''
    try {
      const { data } = await api.post('/share/targets', { type, name, config })
      targets.value.push(data)
      return data
    } catch (err) {
      error.value = err.message || 'Could not create share target.'
      throw err
    }
  }

  async function update(id, fields) {
    error.value = ''
    try {
      const { data } = await api.patch(`/share/targets/${id}`, fields)
      const idx = targets.value.findIndex((t) => t.id === id)
      if (idx !== -1) targets.value[idx] = data
      return data
    } catch (err) {
      error.value = err.message || 'Could not update share target.'
      throw err
    }
  }

  async function remove(id) {
    error.value = ''
    try {
      await api.delete(`/share/targets/${id}`)
      targets.value = targets.value.filter((t) => t.id !== id)
    } catch (err) {
      error.value = err.message || 'Could not delete share target.'
      throw err
    }
  }

  async function share(itemId, targetId) {
    error.value = ''
    try {
      const { data } = await api.post('/share', { item_id: itemId, target_id: targetId })
      return data
    } catch (err) {
      error.value = err.message || 'Could not share item.'
      throw err
    }
  }

  return { targets, loaded, loading, error, load, ensureLoaded, create, update, remove, share }
})
