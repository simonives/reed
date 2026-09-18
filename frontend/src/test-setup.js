// jsdom (as of v25) does not implement PointerEvent — see
// https://github.com/jsdom/jsdom/issues/2527. Polyfill it as a thin
// MouseEvent subclass so tests can dispatch real pointerdown events.
if (typeof window !== 'undefined' && typeof window.PointerEvent === 'undefined') {
  class PointerEvent extends MouseEvent {
    constructor(type, params = {}) {
      super(type, params)
      this.pointerId = params.pointerId ?? 0
      this.pointerType = params.pointerType ?? 'mouse'
    }
  }
  window.PointerEvent = PointerEvent
  globalThis.PointerEvent = PointerEvent
}
