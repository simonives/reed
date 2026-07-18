import { describe, expect, it } from 'vitest'
import { safeHref } from './url'

describe('safeHref', () => {
  it('allows http URLs', () => {
    expect(safeHref('http://example.com/article')).toBe('http://example.com/article')
  })

  it('allows https URLs', () => {
    expect(safeHref('https://example.com/article')).toBe('https://example.com/article')
  })

  it('blocks javascript: URIs', () => {
    expect(safeHref('javascript:alert(document.cookie)')).toBe('#')
  })

  it('blocks data: URIs', () => {
    expect(safeHref('data:text/html,<script>evil()</script>')).toBe('#')
  })

  it('blocks mixed-case javascript: scheme', () => {
    expect(safeHref('JavaScript:void(0)')).toBe('#')
  })

  it('returns # for null', () => {
    expect(safeHref(null)).toBe('#')
  })

  it('returns # for empty string', () => {
    expect(safeHref('')).toBe('#')
  })

  it('returns # for malformed URL', () => {
    expect(safeHref('not a url at all')).toBe('#')
  })
})
