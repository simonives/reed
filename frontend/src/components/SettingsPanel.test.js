import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsPanel from './SettingsPanel.vue'
import { useConfigStore } from '../stores/config'
import { useUiStore } from '../stores/ui'
import { useOpmlStore } from '../stores/opml'
import { useFeedsStore } from '../stores/feeds'
import { useShareStore } from '../stores/share'

describe('SettingsPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('saves the changed draft and closes', async () => {
    const config = useConfigStore()
    const ui = useUiStore()
    ui.showSettings = true
    config.save = vi.fn().mockResolvedValue()

    const wrapper = mount(SettingsPanel)
    await wrapper.find('input[type="color"]').setValue('#00ff00')
    await wrapper.find('form').trigger('submit.prevent')

    expect(config.save).toHaveBeenCalledWith(
      expect.objectContaining({ accent_color: '#00ff00' }),
    )
    expect(ui.showSettings).toBe(false)
  })

  it('closes without saving when nothing changed', async () => {
    const config = useConfigStore()
    const ui = useUiStore()
    ui.showSettings = true
    config.save = vi.fn().mockResolvedValue()

    const wrapper = mount(SettingsPanel)
    await wrapper.find('form').trigger('submit.prevent')

    // An empty diff must not PATCH — the backend rejects an empty body with 422.
    expect(config.save).not.toHaveBeenCalled()
    expect(ui.showSettings).toBe(false)
  })

  it('drops a cleared numeric field from the patch', async () => {
    const config = useConfigStore()
    const ui = useUiStore()
    ui.showSettings = true
    config.save = vi.fn().mockResolvedValue()

    const wrapper = mount(SettingsPanel)
    await wrapper.find('input[type="color"]').setValue('#00ff00')
    // Clearing items-per-page yields '' via v-model.number; it must not be sent.
    await wrapper.find('input[type="number"][max="200"]').setValue('')
    await wrapper.find('form').trigger('submit.prevent')

    const patch = config.save.mock.calls[0][0]
    expect(patch).toHaveProperty('accent_color', '#00ff00')
    expect(patch).not.toHaveProperty('items_per_page')
  })
})

describe('SettingsPanel — Import/Export tab', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders an Import / Export tab button', () => {
    const wrapper = mount(SettingsPanel)
    const tabLabels = wrapper.findAll('.tabs button').map((t) => t.text())
    expect(tabLabels).toContain('Import / Export')
  })

  it('file change calls opml.preview with the selected file', async () => {
    const opml = useOpmlStore()
    opml.preview = vi.fn().mockResolvedValue()
    const wrapper = mount(SettingsPanel)
    const tabs = wrapper.findAll('.tabs button')
    await tabs.find((t) => t.text() === 'Import / Export').trigger('click')

    const fileInput = wrapper.find('input[type="file"]')
    const file = new File(['<opml/>'], 'test.opml', { type: 'application/xml' })
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')

    expect(opml.preview).toHaveBeenCalledWith(file)
  })

  it('shows preview table rows when previewData is set', async () => {
    const opml = useOpmlStore()
    opml.previewData = {
      candidates: [
        { url: 'https://x.com/feed', title: 'X Feed', tags: ['tech'], already_subscribed: false },
        { url: 'https://y.com/feed', title: 'Y Feed', tags: [], already_subscribed: true },
      ],
      unparseable: 0,
    }
    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Import / Export').trigger('click')

    const rows = wrapper.findAll('.preview-table tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[1].find('.badge--exists').exists()).toBe(true)
  })

  it('Import selected button calls importFeeds and reloads feeds', async () => {
    const opml = useOpmlStore()
    const feeds = useFeedsStore()
    opml.previewData = {
      candidates: [
        { url: 'https://x.com/feed', title: 'X', tags: ['tech'], already_subscribed: false },
      ],
      unparseable: 0,
    }
    opml.importFeeds = vi.fn().mockResolvedValue({ added: 1, skipped: 0, failed: [] })
    feeds.load = vi.fn().mockResolvedValue()

    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Import / Export').trigger('click')
    await wrapper.find('.ie-actions .btn--primary').trigger('click')
    await wrapper.vm.$nextTick()

    expect(opml.importFeeds).toHaveBeenCalled()
    const call = opml.importFeeds.mock.calls[0][0]
    expect(call[0].url).toBe('https://x.com/feed')
    expect(feeds.load).toHaveBeenCalled()
  })

  it('Export button calls opml.exportFeeds', async () => {
    const opml = useOpmlStore()
    opml.exportFeeds = vi.fn().mockResolvedValue()
    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Import / Export').trigger('click')
    await wrapper.find('[data-testid="export-btn"]').trigger('click')
    expect(opml.exportFeeds).toHaveBeenCalled()
  })
})

describe('SettingsPanel — Share tab', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders the Share tab with configured targets', async () => {
    const share = useShareStore()
    share.loaded = true
    share.targets = [
      { id: 't1', type: 'webhook', name: 'My webhook', enabled: true, config: { url: 'https://x.com/hook' } },
    ]
    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Share').trigger('click')

    const text = wrapper.text()
    expect(text).toContain('My webhook')
    expect(wrapper.find('.badge--type').text()).toBe('webhook')
  })

  it('submitting the add-target form calls shareStore.create with the right args', async () => {
    const share = useShareStore()
    share.loaded = true
    share.targets = []
    share.create = vi.fn().mockResolvedValue({ id: 't2', type: 'webhook', name: 'W', enabled: true, config: {} })

    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Share').trigger('click')

    await wrapper.find('[data-testid="new-target-type"]').setValue('webhook')
    await wrapper.find('[data-testid="new-target-name"]').setValue('W')
    await wrapper.find('[data-testid="new-target-url"]').setValue('https://x.com/hook')
    await wrapper.find('[data-testid="add-target-btn"]').trigger('click')
    await flushPromises()

    expect(share.create).toHaveBeenCalledWith('webhook', 'W', { url: 'https://x.com/hook' })
  })

  it('clicking delete on a target calls shareStore.remove', async () => {
    const share = useShareStore()
    share.loaded = true
    share.targets = [
      { id: 't1', type: 'webhook', name: 'My webhook', enabled: true, config: { url: 'https://x.com/hook' } },
    ]
    share.remove = vi.fn().mockResolvedValue()

    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Share').trigger('click')
    await wrapper.find('[data-testid="delete-target-btn"]').trigger('click')
    await flushPromises()

    expect(share.remove).toHaveBeenCalledWith('t1')
  })

  it('shows share.error in the DOM when deleting a seeded target is rejected', async () => {
    const share = useShareStore()
    share.loaded = true
    share.targets = [
      { id: 't1', type: 'copy_link', name: 'Copy link', enabled: true, config: {} },
    ]
    // Mirrors the real store behaviour for a 409 on a seeded, non-deletable target.
    share.remove = vi.fn().mockImplementation(async () => {
      share.error = 'Could not delete share target.'
      throw new Error('Could not delete share target.')
    })

    const wrapper = mount(SettingsPanel)
    await wrapper.findAll('.tabs button').find((t) => t.text() === 'Share').trigger('click')
    await wrapper.find('[data-testid="delete-target-btn"]').trigger('click')
    await flushPromises()

    expect(share.remove).toHaveBeenCalledWith('t1')
    expect(wrapper.text()).toContain('Could not delete share target.')
    // The target must remain — the store's own catch is responsible for not
    // mutating `targets` on failure; this asserts the UI still reflects that.
    expect(wrapper.findAll('.target-row')).toHaveLength(1)
  })
})
