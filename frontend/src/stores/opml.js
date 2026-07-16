import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api, getApiKey } from '../api/client'

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
      const { data } = await api.post('/opml/preview', formData)
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
      const { data } = await api.post('/opml/import', { feeds: selection })
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
      const resp = await fetch('/api/v1/opml/export', {
        headers: { 'X-API-Key': getApiKey() },
      })
      if (!resp.ok) throw new Error(`Export failed: ${resp.status}`)
      const blob = await resp.blob()
      const disposition = resp.headers.get('content-disposition') || ''
      const match = disposition.match(/filename="([^"]+)"/)
      const filename = match ? match[1] : 'reed-feeds.opml'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
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
