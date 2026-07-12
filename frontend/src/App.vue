<template>
  <ApiKeyGate v-if="!auth.hasKey" :message="gateMessage" @connected="bootstrap" />

  <div v-else class="app" :class="`app--${ui.layout}`">
    <template v-if="ui.layout === 'three-pane'">
      <AppSidebar />
      <ItemList />
      <ReadingPane ref="readingPane" />
    </template>
    <RiverView v-else ref="riverView" />

    <KeyboardHelp v-if="ui.showHelp" />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import ItemList from './components/ItemList.vue'
import ReadingPane from './components/ReadingPane.vue'
import RiverView from './components/RiverView.vue'
import KeyboardHelp from './components/KeyboardHelp.vue'
import ApiKeyGate from './components/ApiKeyGate.vue'
import { useAuthStore } from './stores/auth'
import { useConfigStore } from './stores/config'
import { useFeedsStore } from './stores/feeds'
import { useItemsStore } from './stores/items'
import { useUiStore } from './stores/ui'
import { useTheme } from './composables/useTheme'
import { useKeyboard } from './composables/useKeyboard'
import { pageDownScroll } from './lib/scroll'

const auth = useAuthStore()
const config = useConfigStore()
const feeds = useFeedsStore()
const items = useItemsStore()
const ui = useUiStore()

const gateMessage = ref('')
const readingPane = ref(null)
const riverView = ref(null)

useTheme()

function onSpace(event) {
  event.preventDefault()
  if (ui.layout === 'three-pane') {
    if (readingPane.value?.pageDown?.() ?? true) items.selectByOffset(1)
  } else if (pageDownScroll(riverView.value?.scrollEl)) {
    items.selectByOffset(1)
  }
}

useKeyboard({ onSpace })

async function bootstrap() {
  gateMessage.value = ''
  try {
    await config.load()
    await Promise.all([feeds.load(), items.load()])
  } catch (err) {
    if (err.status === 401) {
      auth.clear()
      gateMessage.value = 'That API key was rejected. Try again.'
    }
    // Non-auth failures keep the shell up; the item list surfaces its error.
  }
}

// Reload the item list whenever the active view changes. ui.view is replaced
// wholesale by setView, so a shallow watch is enough.
watch(
  () => ui.view,
  () => {
    if (auth.hasKey) items.load()
  },
)

onMounted(() => {
  if (auth.hasKey) bootstrap()
})
</script>

<style scoped>
.app {
  height: 100%;
}

.app--three-pane {
  display: grid;
  grid-template-columns: var(--sidebar-width) var(--itemlist-width) 1fr;
}

.app--river {
  display: block;
}

@media (max-width: 900px) {
  .app--three-pane {
    grid-template-columns: 1fr;
  }
}
</style>
