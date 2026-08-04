import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ReadingPane from './ReadingPane.vue'
import { useItemsStore } from '../stores/items'
import { useShareStore } from '../stores/share'

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

describe('ReadingPane share button', () => {
  beforeEach(() => setActivePinia(createPinia()))

  function withShareTargets(targets) {
    const share = useShareStore()
    share.targets = targets
    share.loaded = true
    share.ensureLoaded = vi.fn().mockResolvedValue()
    share.share = vi.fn().mockResolvedValue({})
    return share
  }

  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue() } })
  })

  it('copy_link target copies the item URL and does not call the share API', async () => {
    const detail = { id: 'i1', title: 'T', url: 'https://example.com/a', tags: [], note: null, content: '', read: true, starred: false }
    withDetail(detail)
    const share = withShareTargets([{ id: 't1', name: 'Copy link', type: 'copy_link', enabled: true }])
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="share-toggle"]').trigger('click')
    await wrapper.find('[data-test="share-target"]').trigger('click')
    await flushPromises()
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://example.com/a')
    expect(share.share).not.toHaveBeenCalled()
  })

  it('surfaces an error message when clipboard.writeText rejects (non-secure context)', async () => {
    // Reed is self-hosted and commonly reached over plain HTTP on a LAN
    // address; navigator.clipboard is undefined/rejects in that context, so
    // the two default copy targets must not fail silently.
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new TypeError('clipboard unavailable')) },
    })
    const detail = { id: 'i1', title: 'T', url: 'https://example.com/a', tags: [], note: null, content: '', read: true, starred: false }
    withDetail(detail)
    withShareTargets([{ id: 't1', name: 'Copy link', type: 'copy_link', enabled: true }])
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="share-toggle"]').trigger('click')
    await wrapper.find('[data-test="share-target"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Could not copy to clipboard')
  })

  it('copy_markdown target copies a markdown link', async () => {
    const detail = { id: 'i1', title: 'My Title', url: 'https://example.com/a', tags: [], note: null, content: '', read: true, starred: false }
    withDetail(detail)
    withShareTargets([{ id: 't2', name: 'Copy as markdown', type: 'copy_markdown', enabled: true }])
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="share-toggle"]').trigger('click')
    await wrapper.find('[data-test="share-target"]').trigger('click')
    await flushPromises()
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('[My Title](https://example.com/a)')
  })

  it('webhook target calls shareStore.share with item and target ids', async () => {
    const detail = { id: 'i1', title: 'T', url: 'https://example.com/a', tags: [], note: null, content: '', read: true, starred: false }
    withDetail(detail)
    const share = withShareTargets([{ id: 't3', name: 'My webhook', type: 'webhook', enabled: true }])
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="share-toggle"]').trigger('click')
    await wrapper.find('[data-test="share-target"]').trigger('click')
    await flushPromises()
    expect(share.share).toHaveBeenCalledWith('i1', 't3')
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled()
  })

  it('only lists enabled share targets', async () => {
    const detail = { id: 'i1', title: 'T', url: 'https://example.com/a', tags: [], note: null, content: '', read: true, starred: false }
    withDetail(detail)
    withShareTargets([
      { id: 't1', name: 'Enabled target', type: 'copy_link', enabled: true },
      { id: 't2', name: 'Disabled target', type: 'copy_link', enabled: false },
    ])
    const wrapper = mount(ReadingPane)
    await wrapper.find('[data-test="share-toggle"]').trigger('click')
    const items = wrapper.findAll('[data-test="share-target"]')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toBe('Enabled target')
  })
})
