// Vue 3 custom directive: v-ripple. Spawns a .ripple span (base.css) inside
// the host element on pointerdown, sized and positioned to expand from the
// click point. Never spawns anything when the user prefers reduced motion:
// state-layer colour feedback (base.css .state-layer / .btn / .icon-btn)
// still applies instantly in that case, since it is a separate mechanism.
export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function spawnRipple(el, event) {
  if (prefersReducedMotion()) return

  const rect = el.getBoundingClientRect()
  const size = Math.max(rect.width, rect.height)
  const span = document.createElement('span')
  span.className = 'ripple'
  span.style.width = `${size}px`
  span.style.height = `${size}px`
  span.style.left = `${event.clientX - rect.left - size / 2}px`
  span.style.top = `${event.clientY - rect.top - size / 2}px`
  span.addEventListener('animationend', () => span.remove())
  setTimeout(() => span.remove(), 600)
  el.appendChild(span)
}

export const ripple = {
  mounted(el) {
    el.__rippleHandler = (event) => spawnRipple(el, event)
    el.addEventListener('pointerdown', el.__rippleHandler)
  },
  unmounted(el) {
    el.removeEventListener('pointerdown', el.__rippleHandler)
    delete el.__rippleHandler
  },
}
