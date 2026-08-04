import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '../api/client'
import { useShareStore } from './share'

describe('share store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('load fetches targets and sets loaded', async () => {
    const mockTargets = [{ id: '1', type: 'copy_link', name: 'Copy link', enabled: true, config: {} }]
    api.get.mockResolvedValue({ data: mockTargets })
    const store = useShareStore()
    await store.load()
    expect(store.targets).toEqual(mockTargets)
    expect(store.loaded).toBe(true)
  })

  it('ensureLoaded only loads once', async () => {
    api.get.mockResolvedValue({ data: [] })
    const store = useShareStore()
    await store.ensureLoaded()
    await store.ensureLoaded()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('create posts a new target and appends it', async () => {
    const created = { id: '2', type: 'webhook', name: 'W', enabled: true, config: { url: 'https://x.com' } }
    api.post.mockResolvedValue({ data: created })
    const store = useShareStore()
    store.targets = []
    const result = await store.create('webhook', 'W', { url: 'https://x.com' })
    expect(api.post).toHaveBeenCalledWith('/share/targets', {
      type: 'webhook', name: 'W', config: { url: 'https://x.com' },
    })
    expect(result).toEqual(created)
    expect(store.targets).toContainEqual(created)
  })

  it('update patches a target and replaces it in the list', async () => {
    const original = { id: '1', type: 'webhook', name: 'Old', enabled: true, config: {} }
    const updated = { ...original, name: 'New' }
    const store = useShareStore()
    store.targets = [original]
    api.patch.mockResolvedValue({ data: updated })
    const result = await store.update('1', { name: 'New' })
    expect(api.patch).toHaveBeenCalledWith('/share/targets/1', { name: 'New' })
    expect(result).toEqual(updated)
    expect(store.targets[0]).toEqual(updated)
  })

  it('remove deletes a target and drops it from the list', async () => {
    const store = useShareStore()
    store.targets = [{ id: '1', type: 'webhook', name: 'W', enabled: true, config: {} }]
    api.delete.mockResolvedValue({})
    await store.remove('1')
    expect(api.delete).toHaveBeenCalledWith('/share/targets/1')
    expect(store.targets).toEqual([])
  })

  it('share posts item_id and target_id', async () => {
    api.post.mockResolvedValue({ data: { shared: true } })
    const store = useShareStore()
    const result = await store.share('item-1', 'target-1')
    expect(api.post).toHaveBeenCalledWith('/share', { item_id: 'item-1', target_id: 'target-1' })
    expect(result).toEqual({ shared: true })
  })

  it('create sets error and rethrows on failure', async () => {
    api.post.mockRejectedValue(new Error('409 Conflict'))
    const store = useShareStore()
    await expect(store.create('webhook', 'W', {})).rejects.toThrow('409 Conflict')
    expect(store.error).toBe('409 Conflict')
  })

  it('update sets error and rethrows on failure', async () => {
    api.patch.mockRejectedValue(new Error('409 Conflict'))
    const store = useShareStore()
    store.targets = [{ id: '1', type: 'webhook', name: 'W', enabled: true, config: {} }]
    await expect(store.update('1', { enabled: false })).rejects.toThrow('409 Conflict')
    expect(store.error).toBe('409 Conflict')
  })

  it('remove sets error and rethrows on failure without removing the target', async () => {
    api.delete.mockRejectedValue(new Error('409 Conflict'))
    const store = useShareStore()
    store.targets = [{ id: '1', type: 'copy_link', name: 'Copy link', enabled: true, config: {} }]
    await expect(store.remove('1')).rejects.toThrow('409 Conflict')
    expect(store.error).toBe('409 Conflict')
    expect(store.targets).toHaveLength(1)
  })

  it('remove sets a fallback error message when the rejection has no message', async () => {
    api.delete.mockRejectedValue({})
    const store = useShareStore()
    store.targets = [{ id: '1', type: 'copy_link', name: 'Copy link', enabled: true, config: {} }]
    await expect(store.remove('1')).rejects.toBeTruthy()
    expect(store.error).toBe('Could not delete share target.')
  })

  it('share sets error and rethrows on failure', async () => {
    api.post.mockRejectedValue(new Error('500 Server Error'))
    const store = useShareStore()
    await expect(store.share('item-1', 'target-1')).rejects.toThrow('500 Server Error')
    expect(store.error).toBe('500 Server Error')
  })

  it('a later successful action clears a stale error', async () => {
    api.delete.mockRejectedValue(new Error('409 Conflict'))
    const store = useShareStore()
    store.targets = [{ id: '1', type: 'copy_link', name: 'Copy link', enabled: true, config: {} }]
    await expect(store.remove('1')).rejects.toThrow()
    expect(store.error).toBe('409 Conflict')

    const created = { id: '2', type: 'webhook', name: 'W', enabled: true, config: {} }
    api.post.mockResolvedValue({ data: created })
    await store.create('webhook', 'W', {})
    expect(store.error).toBe('')
  })
})
