import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'
import { useConfigStore } from './config'
import { useFeedsStore } from './feeds'
import { useUiStore } from './ui'

// Bulk mark-read is only supported server-side for these views.
const CATCH_UP_VIEWS = ['all', 'unread', 'feed']

export const useItemsStore = defineStore('items', () => {
  const ui = useUiStore()
  const config = useConfigStore()
  const feeds = useFeedsStore()

  const items = ref([])
  const total = ref(0)
  const hasMore = ref(false)
  const loading = ref(false)
  const error = ref(null)

  const selectedId = ref(null)
  const detail = ref(null)
  const detailLoading = ref(false)
  const detailError = ref(null)

  // Monotonic tokens so out-of-order responses from rapid view switches or
  // held j/k are discarded (the last *requested* wins, not the last to arrive).
  let loadToken = 0
  let selectToken = 0

  const selectedIndex = computed(() =>
    items.value.findIndex((i) => i.id === selectedId.value),
  )

  // The item keyboard/actions operate on: the open detail only when it matches
  // the current selection, otherwise the selected list row. Prevents acting on
  // the previous item while a detail fetch is still in flight.
  const activeItem = computed(() => {
    if (detail.value && detail.value.id === selectedId.value) return detail.value
    return items.value.find((i) => i.id === selectedId.value) || null
  })

  const canCatchUp = computed(
    () => CATCH_UP_VIEWS.includes(ui.view.type) && items.value.some((i) => !i.read),
  )

  function currentParams(offset) {
    return { ...ui.queryParams, limit: config.values.items_per_page, offset }
  }

  async function load() {
    const token = ++loadToken
    loading.value = true
    error.value = null
    selectedId.value = null
    detail.value = null
    detailError.value = null
    try {
      const body = await api.get('/items', { params: currentParams(0) })
      if (token !== loadToken) return
      items.value = body.data
      total.value = body.meta.total
      hasMore.value = body.meta.has_more
    } catch (err) {
      if (token !== loadToken) return
      error.value = err
      items.value = []
      total.value = 0
      hasMore.value = false
    } finally {
      if (token === loadToken) loading.value = false
    }
  }

  async function loadMore() {
    if (!hasMore.value || loading.value) return
    const token = loadToken
    loading.value = true
    try {
      const body = await api.get('/items', { params: currentParams(items.value.length) })
      if (token !== loadToken) return // a fresh load() superseded this page
      items.value.push(...body.data)
      total.value = body.meta.total
      hasMore.value = body.meta.has_more
    } finally {
      if (token === loadToken) loading.value = false
    }
  }

  async function select(id) {
    if (id == null) return
    const token = ++selectToken
    selectedId.value = id
    detailLoading.value = true
    detailError.value = null
    try {
      const { data } = await api.get(`/items/${id}`)
      if (token !== selectToken) return // superseded by a newer selection
      detail.value = data
      // Mark-read-on-open is best-effort and self-rolling-back; a failure here
      // must not clear the article that loaded fine.
      if (config.values.mark_read_on_open && !data.read) {
        setState(id, { read: true }).catch(() => {})
      }
    } catch (err) {
      if (token !== selectToken) return
      detail.value = null
      detailError.value = err
    } finally {
      if (token === selectToken) detailLoading.value = false
    }
  }

  function selectByOffset(delta) {
    if (items.value.length === 0) return
    const index = selectedIndex.value
    let next = index === -1 ? 0 : index + delta
    next = Math.max(0, Math.min(items.value.length - 1, next))
    const target = items.value[next]
    if (target) {
      select(target.id) // select() handles its own errors; safe to not await
      if (next >= items.value.length - 3) loadMore()
    }
  }

  // Apply a read/starred change to both the list row and the open detail, keep
  // the sidebar unread badge in step, and return the prior field values so a
  // failed request can restore them exactly.
  function applyLocal(id, patch) {
    const row = items.value.find((i) => i.id === id)
    const target = row || (detail.value?.id === id ? detail.value : null)
    if (!target) return null

    const prior = {}
    for (const key of Object.keys(patch)) prior[key] = target[key]
    const wasRead = target.read
    const feed = target.feed

    if (row) Object.assign(row, patch)
    if (detail.value?.id === id) Object.assign(detail.value, patch)

    if ('read' in patch && wasRead !== patch.read && feed) {
      feeds.adjustUnread(feed.id, patch.read ? -1 : 1)
    }
    return prior
  }

  async function setState(id, patch) {
    const prior = applyLocal(id, patch)
    try {
      await api.patch(`/items/${id}`, patch)
    } catch (err) {
      if (prior) applyLocal(id, prior) // restore captured values, not !patch
      throw err
    }
  }

  function toggleRead(item) {
    return setState(item.id, { read: !item.read })
  }

  function toggleStar(item) {
    return setState(item.id, { starred: !item.starred })
  }

  // Catch-up. Marks the loaded rows read in place and refreshes feed badges
  // from the server, avoiding a full list refetch (which would reset scroll
  // and selection). Throws on failure so the caller can surface it.
  async function markViewRead() {
    const payload = ui.view.type === 'feed' ? { feed_id: ui.view.id } : {}
    await api.post('/items/mark-read', payload)
    for (const item of items.value) item.read = true
    if (detail.value) detail.value.read = true
    await feeds.load()
  }

  async function extractReader(id) {
    const { data } = await api.post(`/items/${id}/extract`)
    if (detail.value?.id === id) detail.value = data
    return data
  }

  return {
    items,
    total,
    hasMore,
    loading,
    error,
    selectedId,
    detail,
    detailLoading,
    detailError,
    activeItem,
    canCatchUp,
    load,
    loadMore,
    select,
    selectByOffset,
    toggleRead,
    toggleStar,
    markViewRead,
    extractReader,
  }
})
