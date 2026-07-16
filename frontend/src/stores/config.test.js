import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useConfigStore } from './config'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), patch: vi.fn() },
}))

describe('config store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('save() patches the given diff and stores the returned values', async () => {
    api.patch.mockResolvedValue({
      data: { accent_color: '#ff0000', font_size_base: 18 },
    })
    const config = useConfigStore()
    await config.save({ accent_color: '#ff0000' })
    expect(api.patch).toHaveBeenCalledWith('/config', { accent_color: '#ff0000' })
    expect(config.values.accent_color).toBe('#ff0000')
    expect(config.values.font_size_base).toBe(18)
  })

  it('save() keeps defaults for keys the server omits', async () => {
    api.patch.mockResolvedValue({ data: { accent_color: '#ff0000' } })
    const config = useConfigStore()
    await config.save({ accent_color: '#ff0000' })
    expect(config.values.default_theme).toBe('system')
  })
})
