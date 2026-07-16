import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'

// Global tag list. Item responses carry tag names only, but untagging needs a
// tag id; names are unique server-side, so this resolves name→id.
export const useTagsStore = defineStore('tags', () => {
  const tags = ref([])
  const loaded = ref(false)

  async function load() {
    const { data } = await api.get('/tags')
    tags.value = data
    loaded.value = true
  }

  async function ensureLoaded() {
    if (!loaded.value) await load()
  }

  function byName(name) {
    return tags.value.find((t) => t.name === name)
  }

  // Add a tag returned by an item-tagging call if it isn't already known, so
  // byName() can resolve a freshly created tag without a full reload.
  function upsert(tag) {
    if (!tags.value.some((t) => t.id === tag.id)) tags.value.push(tag)
  }

  return { tags, loaded, load, ensureLoaded, byName, upsert }
})
