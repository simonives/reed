import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useTagsStore } from './tags'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }))

describe('tags store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('load() fetches and byName() resolves ids', async () => {
    api.get.mockResolvedValue({ data: [{ id: 't1', name: 'tech' }, { id: 't2', name: 'news' }] })
    const tags = useTagsStore()
    await tags.load()
    expect(api.get).toHaveBeenCalledWith('/tags')
    expect(tags.byName('news')).toEqual({ id: 't2', name: 'news' })
    expect(tags.byName('missing')).toBeUndefined()
  })
})
