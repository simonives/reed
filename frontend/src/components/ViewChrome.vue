<template>
  <button class="icon-btn" :title="layoutTitle" aria-label="Toggle layout" @click="ui.toggleLayout()">
    {{ ui.layout === 'three-pane' ? '▣' : '☰' }}
  </button>
  <button class="icon-btn" title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts" @click="ui.toggleHelp()">
    ?
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useUiStore } from '../stores/ui'

// The layout toggle + keyboard-help pair, shared by the sidebar (three-pane)
// and the view header (river, which has no sidebar).
const ui = useUiStore()

const layoutTitle = computed(() =>
  ui.layout === 'three-pane' ? 'Switch to river of news' : 'Switch to three-pane',
)
</script>
