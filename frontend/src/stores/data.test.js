import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// Mock api/client before importing the store
vi.mock('../api/client', () => ({
  getApiKey: () => 'test-key',
  api: { post: vi.fn() },
}))

import { useDataStore } from './data'

describe('data store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts with null restoreResult and no error', () => {
    const store = useDataStore()
    expect(store.restoreResult).toBeNull()
    expect(store.error).toBe('')
    expect(store.loading).toBe(false)
  })

  it('exportBackup calls fetch with correct URL and API key header', async () => {
    const mockBlob = new Blob(['{}'], { type: 'application/json' })
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(mockBlob),
      headers: { get: () => 'attachment; filename="reed-backup-2026-07-17.json"' },
    })
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:fake')
    global.URL.revokeObjectURL = vi.fn()
    const mockAnchor = { href: '', download: '', click: vi.fn() }
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => {})
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => {})
    vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor)

    const store = useDataStore()
    await store.exportBackup()

    expect(global.fetch).toHaveBeenCalledWith('/api/v1/export/backup', {
      headers: { 'X-API-Key': 'test-key' },
    })
  })

  it('exportJson calls fetch with correct URL and API key header', async () => {
    const mockBlob = new Blob(['{}'], { type: 'application/json' })
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(mockBlob),
      headers: { get: () => 'attachment; filename="reed-export-2026-07-24.json"' },
    })
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:fake')
    global.URL.revokeObjectURL = vi.fn()
    const mockAnchor = { href: '', download: '', click: vi.fn() }
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => {})
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => {})
    vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor)

    const store = useDataStore()
    await store.exportJson()

    expect(global.fetch).toHaveBeenCalledWith('/api/v1/export/json', {
      headers: { 'X-API-Key': 'test-key' },
    })
  })

  it('restoreBackup posts FormData to /import/backup with confirm header and returns summary', async () => {
    const { api } = await import('../api/client')
    api.post.mockResolvedValue({ data: { feeds: 2, items: 10, notes: 1, tags: 3 } })

    const store = useDataStore()
    const file = new File(['{}'], 'backup.json', { type: 'application/json' })
    const result = await store.restoreBackup(file)

    expect(api.post).toHaveBeenCalledWith(
      '/import/backup',
      expect.any(FormData),
      { headers: { 'X-Confirm-Destructive': 'true' } },
    )
    expect(result).toEqual({ feeds: 2, items: 10, notes: 1, tags: 3 })
    expect(store.restoreResult).toEqual({ feeds: 2, items: 10, notes: 1, tags: 3 })
  })

  it('reset clears restoreResult and error', async () => {
    const store = useDataStore()
    store.restoreResult = { feeds: 1, items: 1, notes: 0, tags: 0 }
    store.error = 'oops'
    store.reset()
    expect(store.restoreResult).toBeNull()
    expect(store.error).toBe('')
  })
})
