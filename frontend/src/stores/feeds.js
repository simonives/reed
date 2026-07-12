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

  return { feeds, loading, totalUnread, load, adjustUnread }
})
