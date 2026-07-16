import { watch } from 'vue'
import { useConfigStore } from '../stores/config'

// Config key → CSS custom property. default_theme is handled by useTheme; these
// are the five user-exposed reading appearance vars (tokens.css).
export const APPEARANCE_VARS = {
  accent_color: '--accent-color',
  font_size_base: '--font-size-base',
  reading_width: '--reading-width',
  line_height: '--line-height',
  font_family_reading: '--font-family-reading',
}

// These keys are stored as unitless numbers but the CSS var wants px.
const PX_KEYS = new Set(['font_size_base', 'reading_width'])

export function cssValue(key, value) {
  return PX_KEYS.has(key) ? `${value}px` : String(value)
}

// Reflect appearance config onto an element's inline style (defaults to :root).
export function applyAppearance(values, el = document.documentElement) {
  for (const [key, cssVar] of Object.entries(APPEARANCE_VARS)) {
    if (values[key] != null) el.style.setProperty(cssVar, cssValue(key, values[key]))
  }
}

// Keeps :root appearance vars in step with config. Reactive, so a Settings save
// updates the page live.
export function useAppearance() {
  const config = useConfigStore()
  watch(() => config.values, (v) => applyAppearance(v), { immediate: true, deep: true })
}
