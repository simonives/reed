import { describe, expect, it } from 'vitest'
import { applyAppearance, cssValue } from './useAppearance'

describe('appearance', () => {
  it('appends px only to pixel-valued keys', () => {
    expect(cssValue('font_size_base', 18)).toBe('18px')
    expect(cssValue('reading_width', 800)).toBe('800px')
    expect(cssValue('line_height', 1.8)).toBe('1.8')
    expect(cssValue('accent_color', '#ff0000')).toBe('#ff0000')
  })

  it('applies each appearance var to the element', () => {
    const el = document.createElement('div')
    applyAppearance(
      {
        accent_color: '#ff0000',
        font_size_base: 18,
        reading_width: 800,
        line_height: 1.8,
        font_family_reading: 'Georgia, serif',
      },
      el,
    )
    expect(el.style.getPropertyValue('--accent-color')).toBe('#ff0000')
    expect(el.style.getPropertyValue('--font-size-base')).toBe('18px')
    expect(el.style.getPropertyValue('--reading-width')).toBe('800px')
    expect(el.style.getPropertyValue('--line-height')).toBe('1.8')
    expect(el.style.getPropertyValue('--font-family-reading')).toBe('Georgia, serif')
  })

  it('ignores keys with null values', () => {
    const el = document.createElement('div')
    applyAppearance({ accent_color: null }, el)
    expect(el.style.getPropertyValue('--accent-color')).toBe('')
  })
})
