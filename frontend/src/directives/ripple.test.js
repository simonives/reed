import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { ripple, spawnRipple } from './ripple'

function mockMatchMedia(reducedMotion) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? reducedMotion : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}

describe('spawnRipple', () => {
  let el

  beforeEach(() => {
    el = document.createElement('button')
    el.getBoundingClientRect = () => ({ width: 40, height: 40, left: 0, top: 0 })
    document.body.appendChild(el)
  })

  afterEach(() => {
    el.remove()
  })

  it('appends a .ripple span on pointerdown when motion is allowed', () => {
    mockMatchMedia(false)
    spawnRipple(el, { clientX: 20, clientY: 20 })
    expect(el.querySelectorAll('.ripple')).toHaveLength(1)
  })

  it('does not append a .ripple span when the user prefers reduced motion', () => {
    mockMatchMedia(true)
    spawnRipple(el, { clientX: 20, clientY: 20 })
    expect(el.querySelectorAll('.ripple')).toHaveLength(0)
  })

  it('removes the .ripple span once its animation ends', () => {
    mockMatchMedia(false)
    spawnRipple(el, { clientX: 20, clientY: 20 })
    const span = el.querySelector('.ripple')
    expect(span).not.toBeNull()
    span.dispatchEvent(new Event('animationend'))
    expect(el.querySelectorAll('.ripple')).toHaveLength(0)
  })
})

describe('ripple directive', () => {
  let el

  beforeEach(() => {
    el = document.createElement('button')
    el.getBoundingClientRect = () => ({ width: 40, height: 40, left: 0, top: 0 })
    document.body.appendChild(el)
    mockMatchMedia(false)
  })

  afterEach(() => {
    el.remove()
  })

  it('spawns a ripple on pointerdown once mounted', () => {
    ripple.mounted(el)
    el.dispatchEvent(new PointerEvent('pointerdown', { clientX: 10, clientY: 10 }))
    expect(el.querySelectorAll('.ripple')).toHaveLength(1)
  })

  it('stops spawning ripples after unmounted', () => {
    ripple.mounted(el)
    ripple.unmounted(el)
    el.dispatchEvent(new PointerEvent('pointerdown', { clientX: 10, clientY: 10 }))
    expect(el.querySelectorAll('.ripple')).toHaveLength(0)
  })
})
