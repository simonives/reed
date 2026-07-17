import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const LAYOUT_STORAGE = 'reed.layout'

// A view is {type, id?, q?, label?}. type is one of:
//   all | unread | starred | feed | tag | search
const DEFAULT_VIEW = { type: 'unread', label: 'All unread' }

export const useUiStore = defineStore('ui', () => {
  const view = ref({ ...DEFAULT_VIEW })
  const layout = ref(localStorage.getItem(LAYOUT_STORAGE) || 'three-pane')
  const showHelp = ref(false)
  const showSettings = ref(false)
  const showAddFeed = ref(false)
  const editingFeedId = ref(null)

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

  function toggleSettings() {
    showSettings.value = !showSettings.value
  }

  function toggleAddFeed() {
    showAddFeed.value = !showAddFeed.value
  }

  function editFeed(id) {
    editingFeedId.value = id
  }

  function closeFeedEditor() {
    editingFeedId.value = null
  }

  const anyOverlayOpen = computed(
    () => showSettings.value || showAddFeed.value || editingFeedId.value !== null,
  )

  function closeOverlays() {
    showSettings.value = false
    showAddFeed.value = false
    editingFeedId.value = null
  }

  // Query params for GET /items, derived from the active view.
  const queryParams = computed(() => {
    const current = view.value
    if (current.type === 'unread') return { unread: true }
    if (current.type === 'starred') return { starred: true }
    if (current.type === 'feed') return { feed_id: current.id }
    if (current.type === 'tag') return { tag: current.id }
    if (current.type === 'search') return { q: current.q }
    return {} // 'all'
  })

  const title = computed(() => view.value.label || 'All items')

  return {
    view,
    layout,
    showHelp,
    showSettings,
    showAddFeed,
    editingFeedId,
    queryParams,
    title,
    setView,
    setLayout,
    toggleLayout,
    toggleHelp,
    toggleSettings,
    toggleAddFeed,
    editFeed,
    closeFeedEditor,
    anyOverlayOpen,
    closeOverlays,
  }
})
