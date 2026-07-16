import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AddFeedModal from './AddFeedModal.vue'
import { useFeedsStore } from '../stores/feeds'
import { useUiStore } from '../stores/ui'

function fill(wrapper, url) {
  return wrapper.find('input[type="url"]').setValue(url)
}

describe('AddFeedModal', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('auto-subscribes when discovery returns exactly one feed', async () => {
    const feeds = useFeedsStore()
    const ui = useUiStore()
    ui.showAddFeed = true
    ui.setView = vi.fn()
    feeds.discover = vi.fn().mockResolvedValue([{ url: 'https://x/feed', title: 'X' }])
    feeds.subscribe = vi.fn().mockResolvedValue({ id: 'f1' })

    const wrapper = mount(AddFeedModal)
    await fill(wrapper, 'https://x')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(feeds.subscribe).toHaveBeenCalledWith('https://x/feed')
    expect(ui.showAddFeed).toBe(false)
    expect(ui.setView).toHaveBeenCalledWith(expect.objectContaining({ type: 'feed', id: 'f1' }))
  })

  it('lists candidates when discovery returns several', async () => {
    const feeds = useFeedsStore()
    useUiStore().showAddFeed = true
    feeds.discover = vi.fn().mockResolvedValue([
      { url: 'https://x/a', title: 'A' },
      { url: 'https://x/b', title: 'B' },
    ])
    feeds.subscribe = vi.fn().mockResolvedValue({ id: 'f1' })

    const wrapper = mount(AddFeedModal)
    await fill(wrapper, 'https://x')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    const candidates = wrapper.findAll('.candidate')
    expect(candidates).toHaveLength(2)
    expect(feeds.subscribe).not.toHaveBeenCalled()
  })

  it('shows a message when discovery finds nothing', async () => {
    const feeds = useFeedsStore()
    useUiStore().showAddFeed = true
    feeds.discover = vi.fn().mockResolvedValue([])

    const wrapper = mount(AddFeedModal)
    await fill(wrapper, 'https://x')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('No feeds found')
  })

  it('surfaces a discovery error', async () => {
    const feeds = useFeedsStore()
    useUiStore().showAddFeed = true
    feeds.discover = vi.fn().mockRejectedValue(new Error('Refusing to fetch: private host'))

    const wrapper = mount(AddFeedModal)
    await fill(wrapper, 'https://x')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Refusing to fetch')
  })
})
