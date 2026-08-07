import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useOpmlStore } from './opml'

vi.mock('../api/client', () => ({
  api: { post: vi.fn() },
  getApiKey: vi.fn(() => 'test-key'),
}))

import { api } from '../api/client'

describe('useOpmlStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('preview sets previewData on success', async () => {
    const mockData = {
      candidates: [{ url: 'https://x.com/feed', title: 'X', tags: [], already_subscribed: false }],
      unparseable: 0,
    }
    api.post.mockResolvedValue({ data: mockData })
    const store = useOpmlStore()
    const file = new File(['<opml/>'], 'test.opml', { type: 'application/xml' })
    await store.preview(file)
    expect(store.previewData).toEqual(mockData)
    expect(store.error).toBe('')
    expect(store.loading).toBe(false)
  })

  it('preview sets error and re-throws on failure', async () => {
    api.post.mockRejectedValue(new Error('Parse error'))
    const store = useOpmlStore()
    const file = new File(['bad'], 'test.opml')
    await expect(store.preview(file)).rejects.toThrow('Parse error')
    expect(store.error).toBe('Parse error')
    expect(store.loading).toBe(false)
  })

  it('importFeeds posts selection and stores result', async () => {
    const mockResult = { added: 2, skipped: 0, failed: [] }
    api.post.mockResolvedValue({ data: mockResult })
    const store = useOpmlStore()
    const selection = [{ url: 'https://x.com/feed', title: 'X', tags: [] }]
    const result = await store.importFeeds(selection)
    expect(api.post).toHaveBeenCalledWith('/import/opml', { feeds: selection })
    expect(result).toEqual(mockResult)
    expect(store.importResult).toEqual(mockResult)
  })

  it('reset clears all state', () => {
    const store = useOpmlStore()
    store.previewData = { candidates: [], unparseable: 0 }
    store.importResult = { added: 1, skipped: 0, failed: [] }
    store.error = 'oops'
    store.reset()
    expect(store.previewData).toBeNull()
    expect(store.importResult).toBeNull()
    expect(store.error).toBe('')
  })
})
