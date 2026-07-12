<template>
  <div class="gate">
    <form class="gate__card" @submit.prevent="submit">
      <h1 class="gate__title">Reed</h1>
      <p class="gate__lede">Enter your API key to connect to this instance.</p>
      <input
        ref="input"
        v-model="key"
        class="gate__input"
        type="password"
        autocomplete="off"
        aria-label="API key"
        placeholder="X-API-Key"
      />
      <p v-if="message" class="gate__error" role="alert">{{ message }}</p>
      <button class="btn btn--primary gate__submit" type="submit">Connect</button>
    </form>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  message: { type: String, default: '' },
})
const emit = defineEmits(['connected'])

const auth = useAuthStore()
const key = ref('')
const input = ref(null)

onMounted(() => input.value?.focus())

function submit() {
  if (!key.value.trim()) return
  auth.save(key.value)
  emit('connected')
}
</script>

<style scoped>
.gate {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--bg-subtle);
}

.gate__card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  width: 320px;
  padding: var(--space-6);
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

.gate__title {
  font-size: 1.5rem;
  font-weight: 600;
}

.gate__lede {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.gate__input {
  padding: var(--space-2) var(--space-3);
  background: var(--bg);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
}

.gate__error {
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}

.gate__submit {
  justify-content: center;
}
</style>
