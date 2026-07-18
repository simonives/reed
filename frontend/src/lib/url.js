const SAFE_SCHEMES = new Set(['http:', 'https:'])

export function safeHref(url) {
  if (!url) return '#'
  try {
    return SAFE_SCHEMES.has(new URL(url).protocol) ? url : '#'
  } catch {
    return '#'
  }
}
