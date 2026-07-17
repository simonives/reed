import { onBeforeUnmount, onMounted } from 'vue'
import { useItemsStore } from '../stores/items'
import { useUiStore } from '../stores/ui'

// Google Reader-style keyboard layer (principles.md §3). Global listener,
// disabled while typing in a field. `g` starts a short-lived prefix for the
// go-to-view sequences (g h / g u / g s).
export function useKeyboard(options = {}) {
  const items = useItemsStore()
  const ui = useUiStore()

  let gPending = false
  let gTimer = null

  function clearPrefix() {
    gPending = false
    if (gTimer) clearTimeout(gTimer)
    gTimer = null
  }

  function openInNewTab(url) {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  function handleGoTo(key) {
    if (key === 'h') return ui.setView({ type: 'all', label: 'All items' })
    if (key === 'u') return ui.setView({ type: 'unread', label: 'All unread' })
    if (key === 's') return ui.setView({ type: 'starred', label: 'Starred' })
    return null
  }

  function onKeydown(event) {
    const el = event.target
    const typing =
      el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
    if (typing) {
      if (event.key === 'Escape') el.blur()
      return
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return

    // Close overlays on Escape (#61); block all other shortcuts behind overlays (#62).
    if (ui.anyOverlayOpen) {
      if (event.key === 'Escape') ui.closeOverlays()
      return
    }

    if (gPending) {
      clearPrefix()
      if (handleGoTo(event.key) !== null) {
        event.preventDefault()
        return
      }
      // Not a go-to target — fall through and treat as a normal key.
    }

    const item = items.activeItem

    switch (event.key) {
      case 'j':
        items.selectByOffset(1)
        break
      case 'k':
        items.selectByOffset(-1)
        break
      case 'm':
        if (item) items.toggleRead(item)
        break
      case 's':
        if (item) items.toggleStar(item)
        break
      // o opens the item, v its original source. With no per-item permalink
      // route in core, both resolve to the article URL.
      case 'o':
      case 'v':
        openInNewTab(item?.url)
        break
      case '?':
        ui.toggleHelp()
        break
      case 'Escape':
        if (ui.showHelp) ui.showHelp = false
        return // don't preventDefault on Escape
      case ' ':
        if (options.onSpace) options.onSpace(event)
        else items.selectByOffset(1)
        break
      case 'g':
        gPending = true
        gTimer = setTimeout(clearPrefix, 1500)
        break
      case '/':
        window.dispatchEvent(new CustomEvent('reed:focus-search'))
        break
      default:
        return // unhandled key: let the browser have it
    }
    event.preventDefault()
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeydown)
    clearPrefix()
  })
}
