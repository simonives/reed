// Space-bar paging: scroll a container down by most of a viewport. Returns
// true once the container is already at the bottom, so the caller can decide
// to advance to the next item.
export function pageDownScroll(el) {
  if (!el) return true
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 4
  if (atBottom) return true
  el.scrollBy({ top: el.clientHeight * 0.9, behavior: 'smooth' })
  return false
}
