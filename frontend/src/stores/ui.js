import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const LAYOUT_STORAGE = 'reed.layout'

// A view is {type, id?, label?}. type is one of:
//   all | unread | starred | feed | tag
const DEFAULT_VIEW = { type: 'unread', label: 'All unread' }

export const useUiStore = defineStore('ui', () => {
  const view = ref({ ...DEFAULT_VIEW })
  const layout = ref(localStorage.getItem(LAYOUT_STORAGE) || 'three-pane')
  const showHelp = ref(false)

  function setView(next) {
    view.value = next
  }

  function setLayout(next) {
    layout.value = next
    localStorage.setItem(LAYOUT_STORAGE, next)
  }

  function toggleLayout() {
    setLayout(layout.value === 'three-pane' ? 'river' : 'three-pane')
  }

  function toggleHelp() {
    showHelp.value = !showHelp.value
  }

  // Query params for GET /items, derived from the active view.
  const queryParams = computed(() => {
    const current = view.value
    if (current.type === 'unread') return { unread: true }
    if (current.type === 'starred') return { starred: true }
    if (current.type === 'feed') return { feed_id: current.id }
    if (current.type === 'tag') return { tag: current.id }
    return {} // 'all'
  })

  const title = computed(() => view.value.label || 'All items')

  return {
    view,
    layout,
    showHelp,
    queryParams,
    title,
    setView,
    setLayout,
    toggleLayout,
    toggleHelp,
  }
})
