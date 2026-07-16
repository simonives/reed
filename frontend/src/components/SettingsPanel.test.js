import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsPanel from './SettingsPanel.vue'
import { useConfigStore } from '../stores/config'
import { useUiStore } from '../stores/ui'

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
