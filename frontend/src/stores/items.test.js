import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useItemsStore } from './items'
import { useTagsStore } from './tags'
import { useUiStore } from './ui'
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

describe('items store — cursor pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('load() stores next_cursor and sets hasMore=true for non-search view', async () => {
    const ui = useUiStore()
    ui.view = { type: 'unread' }
    api.get.mockResolvedValue({ data: [{ id: 'i1' }], meta: { next_cursor: 'abc123' } })
    const items = useItemsStore()
    await items.load()
    expect(items.nextCursor).toBe('abc123')
    expect(items.hasMore).toBe(true)
  })

  it('load() sets hasMore=false and nextCursor=null when next_cursor is null', async () => {
    const ui = useUiStore()
    ui.view = { type: 'all' }
    api.get.mockResolvedValue({ data: [{ id: 'i1' }], meta: { next_cursor: null } })
    const items = useItemsStore()
    await items.load()
    expect(items.nextCursor).toBeNull()
    expect(items.hasMore).toBe(false)
  })

  it('loadMore() passes cursor param for non-search view', async () => {
    const ui = useUiStore()
    ui.view = { type: 'unread' }
    api.get.mockResolvedValue({ data: [{ id: 'i1' }], meta: { next_cursor: 'page2' } })
    const items = useItemsStore()
    await items.load()

    api.get.mockResolvedValue({ data: [{ id: 'i2' }], meta: { next_cursor: null } })
    await items.loadMore()

    const [, params] = api.get.mock.calls[1]
    expect(params.params).toMatchObject({ cursor: 'page2' })
    expect(params.params).not.toHaveProperty('offset')
  })

  it('loadMore() updates nextCursor and hasMore from response', async () => {
    const ui = useUiStore()
    ui.view = { type: 'feed', id: 'f1' }
    api.get.mockResolvedValue({ data: [{ id: 'i1' }], meta: { next_cursor: 'tok1' } })
    const items = useItemsStore()
    await items.load()

    api.get.mockResolvedValue({ data: [{ id: 'i2' }], meta: { next_cursor: null } })
    await items.loadMore()

    expect(items.nextCursor).toBeNull()
    expect(items.hasMore).toBe(false)
    expect(items.items).toHaveLength(2)
  })

  it('load() for search view sets hasMore from has_more meta field', async () => {
    const ui = useUiStore()
    ui.view = { type: 'search', q: 'hello' }
    api.get.mockResolvedValue({
      data: [{ id: 'i1' }],
      meta: { total: 50, offset: 0, has_more: true },
    })
    const items = useItemsStore()
    await items.load()
    expect(items.hasMore).toBe(true)
    expect(items.nextCursor).toBeNull()
    expect(items.total).toBe(50)
  })

  it('loadMore() for search view passes offset param', async () => {
    const ui = useUiStore()
    ui.view = { type: 'search', q: 'hello' }
    api.get.mockResolvedValue({
      data: [{ id: 'i1' }, { id: 'i2' }],
      meta: { total: 10, offset: 0, has_more: true },
    })
    const items = useItemsStore()
    await items.load()

    api.get.mockResolvedValue({
      data: [{ id: 'i3' }],
      meta: { total: 10, offset: 2, has_more: false },
    })
    await items.loadMore()

    const [, params] = api.get.mock.calls[1]
    expect(params.params).toMatchObject({ offset: 2 })
    expect(params.params).not.toHaveProperty('cursor')
  })
})
