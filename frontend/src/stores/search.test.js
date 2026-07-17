import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSearchStore } from './search'

describe('search store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with empty query', () => {
    const search = useSearchStore()
    expect(search.query).toBe('')
  })

  it('starts with empty filters', () => {
    const search = useSearchStore()
    expect(search.filters).toEqual({})
  })

  it('setQuery updates query', () => {
    const search = useSearchStore()
    search.setQuery('governance')
    expect(search.query).toBe('governance')
  })

  it('clear resets query and filters', () => {
    const search = useSearchStore()
    search.setQuery('governance')
    search.clear()
    expect(search.query).toBe('')
    expect(search.filters).toEqual({})
  })

  it('setPreviousView stores the view', () => {
    const search = useSearchStore()
    search.setPreviousView({ type: 'feed', id: 'abc', label: 'My Feed' })
    expect(search.previousView).toEqual({ type: 'feed', id: 'abc', label: 'My Feed' })
  })
})
