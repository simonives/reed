import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsPanel from './SettingsPanel.vue'
import { useConfigStore } from '../stores/config'
import { useUiStore } from '../stores/ui'
import { useOpmlStore } from '../stores/opml'
import { useFeedsStore } from '../stores/feeds'

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
