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

  it('anyOverlayOpen is false when all overlays closed', () => {
    const ui = useUiStore()
    expect(ui.anyOverlayOpen).toBe(false)
  })

  it('anyOverlayOpen is true when settings is open', () => {
    const ui = useUiStore()
    ui.toggleSettings()
    expect(ui.anyOverlayOpen).toBe(true)
  })

  it('anyOverlayOpen is true when addFeed is open', () => {
    const ui = useUiStore()
    ui.toggleAddFeed()
    expect(ui.anyOverlayOpen).toBe(true)
  })

  it('anyOverlayOpen is true when feed editor is open', () => {
    const ui = useUiStore()
    ui.editFeed('some-id')
    expect(ui.anyOverlayOpen).toBe(true)
  })

  it('closeOverlays sets all overlay flags to false', () => {
    const ui = useUiStore()
    ui.toggleSettings()
    ui.toggleAddFeed()
    ui.editFeed('some-id')
    ui.closeOverlays()
    expect(ui.showSettings).toBe(false)
    expect(ui.showAddFeed).toBe(false)
    expect(ui.editingFeedId).toBeNull()
    expect(ui.anyOverlayOpen).toBe(false)
  })
})
