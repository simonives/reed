<template>
  <!-- Untrusted feed HTML, sanitised via DOMPurify before rendering. This is
       the single render path for article markup; every layout uses it. -->
  <div class="article-body" v-html="clean"></div>
</template>

<script setup>
import { computed } from 'vue'
import { sanitizeArticle } from '../lib/sanitize'

const props = defineProps({
  html: { type: String, default: '' },
})

// Keyed only on the raw html string, so read/star mutations on the open item
// don't re-run DOMPurify.
const clean = computed(() => sanitizeArticle(props.html))
</script>

<style scoped>
.article-body {
  font-family: var(--font-family-reading);
  font-size: var(--font-size-base);
  line-height: var(--line-height);
  color: var(--text);
}

.article-body :deep(p),
.article-body :deep(ul),
.article-body :deep(ol),
.article-body :deep(blockquote),
.article-body :deep(pre),
.article-body :deep(figure) {
  margin: var(--space-4) 0;
}

.article-body :deep(h2),
.article-body :deep(h3) {
  margin: var(--space-5) 0 var(--space-2);
  line-height: 1.3;
}

.article-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius);
}

.article-body :deep(ul),
.article-body :deep(ol) {
  padding-left: var(--space-5);
}

.article-body :deep(blockquote) {
  padding-left: var(--space-4);
  border-left: 3px solid var(--border-strong);
  color: var(--text-secondary);
}

.article-body :deep(pre) {
  padding: var(--space-3);
  background: var(--bg-subtle);
  border-radius: var(--radius);
  overflow-x: auto;
}
</style>
