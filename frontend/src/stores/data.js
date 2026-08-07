import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api, getApiKey } from '../api/client'

export async function _downloadBlob(url, fallbackName) {
  const resp = await fetch(url, { headers: { 'X-API-Key': getApiKey() } })
  if (!resp.ok) throw new Error(`Download failed: ${resp.status}`)
  const blob = await resp.blob()
  const disposition = resp.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : fallbackName
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(objectUrl)
}

export const useDataStore = defineStore('data', () => {
  const loading = ref(false)
  const error = ref('')
  const restoreResult = ref(null)

  async function exportBackup() {
    loading.value = true
    error.value = ''
    try {
      await _downloadBlob('/api/v1/export/backup', 'reed-backup.json')
    } catch (err) {
      error.value = err.message || 'Export failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function exportJson() {
    loading.value = true
    error.value = ''
    try {
      await _downloadBlob('/api/v1/export/json', 'reed-export.json')
    } catch (err) {
      error.value = err.message || 'Export failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function restoreBackup(file) {
    loading.value = true
    error.value = ''
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.post('/import/backup', formData, {
        headers: { 'X-Confirm-Destructive': 'true' },
      })
      restoreResult.value = data
      return data
    } catch (err) {
      error.value = err.message || 'Restore failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  function reset() {
    restoreResult.value = null
    error.value = ''
  }

  return { loading, error, restoreResult, exportBackup, exportJson, restoreBackup, reset }
})
