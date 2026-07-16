import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useItemsStore } from './items'
import { useTagsStore } from './tags'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn() },
}))

describe('items store — notes & tags', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('saveNote() puts the body and updates detail', async () => {
    api.put.mockResolvedValue({ data: { body: 'hello' } })
    const items = useItemsStore()
    items.detail = { id: 'i1', note: null, tags: [] }
    await items.saveNote('i1', 'hello')
    expect(api.put).toHaveBeenCalledWith('/items/i1/note', { body: 'hello' })
    expect(items.detail.note).toEqual({ body: 'hello' })
  })

  it('deleteNote() clears detail.note', async () => {
    api.delete.mockResolvedValue({})
    const items = useItemsStore()
    items.detail = { id: 'i1', note: { body: 'x' }, tags: [] }
    await items.deleteNote('i1')
    expect(api.delete).toHaveBeenCalledWith('/items/i1/note')
    expect(items.detail.note).toBeNull()
  })

  it('addTag() posts and appends the name', async () => {
    api.post.mockResolvedValue({ data: { id: 't1', name: 'tech' } })
    const items = useItemsStore()
    items.detail = { id: 'i1', note: null, tags: [] }
    await items.addTag('i1', 'tech')
    expect(api.post).toHaveBeenCalledWith('/items/i1/tags', { name: 'tech' })
    expect(items.detail.tags).toContain('tech')
  })

  it('removeTag() resolves name→id and deletes', async () => {
    const tags = useTagsStore()
    tags.tags = [{ id: 't1', name: 'tech' }]
    tags.loaded = true
    api.delete.mockResolvedValue({})
    const items = useItemsStore()
    items.detail = { id: 'i1', note: null, tags: ['tech'] }
    await items.removeTag('i1', 'tech')
    expect(api.delete).toHaveBeenCalledWith('/items/i1/tags/t1')
    expect(items.detail.tags).not.toContain('tech')
  })
})
