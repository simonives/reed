import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FeedSettingsDrawer from './FeedSettingsDrawer.vue'
import { useFeedsStore } from '../stores/feeds'
import { useUiStore } from '../stores/ui'

function setup() {
  const feeds = useFeedsStore()
  const ui = useUiStore()
  feeds.feeds = [{
    id: 'f1', display_name: 'HN', title: 'Hacker News',
    poll_interval_minutes: null, reader_mode_enabled: null, is_active: true,
    tags: ['tech'], consecutive_errors: 0, last_error: null,
    last_fetched_at: null, next_poll_at: null,
  }]
  ui.editFeed('f1')
  return { feeds, ui }
}

describe('FeedSettingsDrawer', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('saves edited fields', async () => {
    const { feeds } = setup()
    feeds.update = vi.fn().mockResolvedValue({ id: 'f1', display_name: 'Hacker' })
    const wrapper = mount(FeedSettingsDrawer)
    await wrapper.find('input[aria-label="Display name"]').setValue('Hacker')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(feeds.update).toHaveBeenCalledWith('f1', expect.objectContaining({ display_name: 'Hacker' }))
  })

  it('deletes after confirmation and closes', async () => {
    const { feeds, ui } = setup()
    feeds.remove = vi.fn().mockResolvedValue(true)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mount(FeedSettingsDrawer)
    await wrapper.find('[data-test="delete"]').trigger('click')
    await flushPromises()
    expect(feeds.remove).toHaveBeenCalledWith('f1')
    expect(ui.editingFeedId).toBe(null)
  })

  it('refreshes on demand', async () => {
    const { feeds } = setup()
    feeds.refresh = vi.fn().mockResolvedValue({ id: 'f1' })
    const wrapper = mount(FeedSettingsDrawer)
    await wrapper.find('[data-test="refresh"]').trigger('click')
    await flushPromises()
    expect(feeds.refresh).toHaveBeenCalledWith('f1')
  })

  it('saves inherit (null) when reader mode is untouched on an inheriting feed', async () => {
    const { feeds } = setup()
    feeds.update = vi.fn().mockResolvedValue({ id: 'f1' })
    const wrapper = mount(FeedSettingsDrawer)
    // Do not touch the reader mode select — feed has reader_mode_enabled: null
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(feeds.update).toHaveBeenCalledWith('f1', expect.objectContaining({ reader_mode_enabled: null }))
  })

  it('sends true when reader mode select is set to On', async () => {
    const { feeds } = setup()
    feeds.update = vi.fn().mockResolvedValue({ id: 'f1' })
    const wrapper = mount(FeedSettingsDrawer)
    await wrapper.find('select[aria-label="Reader mode"]').setValue('on')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(feeds.update).toHaveBeenCalledWith('f1', expect.objectContaining({ reader_mode_enabled: true }))
  })

  it('sends false when reader mode select is set to Off', async () => {
    const { feeds } = setup()
    feeds.update = vi.fn().mockResolvedValue({ id: 'f1' })
    const wrapper = mount(FeedSettingsDrawer)
    await wrapper.find('select[aria-label="Reader mode"]').setValue('off')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(feeds.update).toHaveBeenCalledWith('f1', expect.objectContaining({ reader_mode_enabled: false }))
  })
})
