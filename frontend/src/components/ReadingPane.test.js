import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ReadingPane from './ReadingPane.vue'
import { useItemsStore } from '../stores/items'

function withDetail(detail) {
  const items = useItemsStore()
  items.selectedId = detail.id
  items.detail = detail
  return items
}

describe('ReadingPane note & tag editing', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('saves a note', async () => {
    const items = withDetail({ id: 'i1', title: 'T', tags: [], note: null, content: '', read: true, starred: false })
    items.saveNote = vi.fn().mockResolvedValue({ body: 'my note' })
    const wrapper = mount(ReadingPane)
    await wrapper.find('textarea[aria-label="Note"]').setValue('my note')
    await wrapper.find('[data-test="save-note"]').trigger('click')
    await flushPromises()
    expect(items.saveNote).toHaveBeenCalledWith('i1', 'my note')
  })

  it('adds a tag on Enter', async () => {
    const items = withDetail({ id: 'i1', title: 'T', tags: [], note: null, content: '', read: true, starred: false })
    items.addTag = vi.fn().mockResolvedValue()
    const wrapper = mount(ReadingPane)
    const input = wrapper.find('input[aria-label="Add tag"]')
    await input.setValue('tech')
    await input.trigger('keydown.enter')
    await flushPromises()
    expect(items.addTag).toHaveBeenCalledWith('i1', 'tech')
  })

  it('removes a tag', async () => {
    const items = withDetail({ id: 'i1', title: 'T', tags: ['tech'], note: null, content: '', read: true, starred: false })
    items.removeTag = vi.fn().mockResolvedValue()
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="remove-tag"]').trigger('click')
    await flushPromises()
    expect(items.removeTag).toHaveBeenCalledWith('i1', 'tech')
  })

  it('does not delete a non-existent note on empty save', async () => {
    const items = withDetail({ id: 'i1', title: 'T', tags: [], note: null, content: '', read: true, starred: false })
    items.saveNote = vi.fn()
    items.deleteNote = vi.fn()
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="save-note"]').trigger('click')
    await flushPromises()
    expect(items.saveNote).not.toHaveBeenCalled()
    expect(items.deleteNote).not.toHaveBeenCalled()
  })
})
