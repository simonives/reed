import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'
import { _downloadBlob } from './data'

export const useOpmlStore = defineStore('opml', () => {
  const previewData = ref(null)
  const importResult = ref(null)
  const loading = ref(false)
  const error = ref('')

  async function preview(file) {
    loading.value = true
    error.value = ''
    previewData.value = null
    importResult.value = null
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.post('/import/opml/preview', formData)
      previewData.value = data
    } catch (err) {
      error.value = err.message || 'Could not parse OPML file.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function importFeeds(selection) {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.post('/import/opml', { feeds: selection })
      importResult.value = data
      return data
    } catch (err) {
      error.value = err.message || 'Import failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function exportFeeds() {
    loading.value = true
    error.value = ''
    try {
      await _downloadBlob('/api/v1/export/opml', 'reed-feeds.opml')
    } catch (err) {
      error.value = err.message || 'Export failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  function reset() {
    previewData.value = null
    importResult.value = null
    error.value = ''
  }

  return { previewData, importResult, loading, error, preview, importFeeds, exportFeeds, reset }
})
