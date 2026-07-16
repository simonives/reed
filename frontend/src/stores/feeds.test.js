import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useFeedsStore } from './feeds'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))


describe('feeds store — subscribe/discover', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('discover() returns the candidate list', async () => {
    api.post.mockResolvedValue({ data: [{ url: 'https://x/feed', title: 'X', type: 'feed' }] })
    const feeds = useFeedsStore()
    const found = await feeds.discover('https://x')
    expect(api.post).toHaveBeenCalledWith('/feeds/discover', { url: 'https://x' })
    expect(found).toHaveLength(1)
  })

  it('subscribe() posts the url and reloads the list', async () => {
    api.post.mockResolvedValue({ data: { id: 'f1', url: 'https://x/feed' } })
    api.get.mockResolvedValue({ data: [{ id: 'f1' }] })
    const feeds = useFeedsStore()
    const created = await feeds.subscribe('https://x/feed')
    expect(api.post).toHaveBeenCalledWith('/feeds', { url: 'https://x/feed' })
    expect(created.id).toBe('f1')
    expect(feeds.feeds).toHaveLength(1)
  })
})

describe('feeds store — manage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('update() patches and replaces the row in place', async () => {
    const feeds = useFeedsStore()
    feeds.feeds = [{ id: 'f1', display_name: 'Old' }]
    api.patch.mockResolvedValue({ data: { id: 'f1', display_name: 'New' } })
    const updated = await feeds.update('f1', { display_name: 'New' })
    expect(api.patch).toHaveBeenCalledWith('/feeds/f1', { display_name: 'New' })
    expect(updated.display_name).toBe('New')
    expect(feeds.feeds[0].display_name).toBe('New')
  })

  it('remove() deletes and drops the row', async () => {
    const feeds = useFeedsStore()
    feeds.feeds = [{ id: 'f1' }, { id: 'f2' }]
    api.delete.mockResolvedValue({})
    const ok = await feeds.remove('f1')
    expect(api.delete).toHaveBeenCalledWith('/feeds/f1')
    expect(ok).toBe(true)
    expect(feeds.feeds.map((f) => f.id)).toEqual(['f2'])
  })

  it('refresh() posts and replaces the row', async () => {
    const feeds = useFeedsStore()
    feeds.feeds = [{ id: 'f1', consecutive_errors: 2 }]
    api.post.mockResolvedValue({ data: { id: 'f1', consecutive_errors: 0 } })
    await feeds.refresh('f1')
    expect(api.post).toHaveBeenCalledWith('/feeds/f1/refresh')
    expect(feeds.feeds[0].consecutive_errors).toBe(0)
  })
})
