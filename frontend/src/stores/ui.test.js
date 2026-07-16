import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useUiStore } from './ui'

describe('ui store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('toggles the help overlay', () => {
    const ui = useUiStore()
    expect(ui.showHelp).toBe(false)
    ui.toggleHelp()
    expect(ui.showHelp).toBe(true)
  })

  it('toggles the settings overlay', () => {
    const ui = useUiStore()
    expect(ui.showSettings).toBe(false)
    ui.toggleSettings()
    expect(ui.showSettings).toBe(true)
  })
})
