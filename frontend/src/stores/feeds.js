import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useFeedsStore = defineStore('feeds', () => {
  const feeds = ref([])
  const loading = ref(false)

  const totalUnread = computed(() =>
    feeds.value.reduce((sum, feed) => sum + (feed.unread_count || 0), 0),
  )

  async function load() {
    loading.value = true
    try {
      const { data } = await api.get('/feeds')
      feeds.value = data
    } finally {
      loading.value = false
    }
  }

  // Keep sidebar unread badges in sync with read/unread toggles without a
  // full reload. Clamped at zero so a stale count can't go negative.
  function adjustUnread(feedId, delta) {
    const feed = feeds.value.find((f) => f.id === feedId)
    if (feed) feed.unread_count = Math.max(0, (feed.unread_count || 0) + delta)
  }

  async function discover(url) {
    const { data } = await api.post('/feeds/discover', { url })
    return data
  }

  async function subscribe(url) {
    const { data } = await api.post('/feeds', { url })
    await load()
    return data
  }

  function replaceRow(feed) {
    const i = feeds.value.findIndex((f) => f.id === feed.id)
    if (i !== -1) feeds.value[i] = feed
  }

  async function update(id, patch) {
    const { data } = await api.patch(`/feeds/${id}`, patch)
    replaceRow(data)
    return data
  }

  async function refresh(id) {
    const { data } = await api.post(`/feeds/${id}/refresh`)
    replaceRow(data)
    return data
  }

  async function remove(id) {
    await api.delete(`/feeds/${id}`)
    feeds.value = feeds.value.filter((f) => f.id !== id)
    return true
  }

  return { feeds, loading, totalUnread, load, adjustUnread, discover, subscribe, update, refresh, remove }
})
