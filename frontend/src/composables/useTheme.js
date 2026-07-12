import { onBeforeUnmount, watch } from 'vue'
import { useConfigStore } from '../stores/config'

// Resolves the configured theme (light/dark/system) against the OS preference
// and reflects it as data-theme on <html>. tokens.css keys the palette off it.
export function useTheme() {
  const config = useConfigStore()
  const media = window.matchMedia('(prefers-color-scheme: dark)')

  function apply() {
    const preference = config.values.default_theme
    const resolved =
      preference === 'system' ? (media.matches ? 'dark' : 'light') : preference
    document.documentElement.setAttribute('data-theme', resolved)
  }

  watch(() => config.values.default_theme, apply, { immediate: true })
  media.addEventListener('change', apply)
  onBeforeUnmount(() => media.removeEventListener('change', apply))
}
