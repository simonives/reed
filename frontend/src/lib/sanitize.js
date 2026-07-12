// Article HTML (content and reader_content) is third-party, feed-author
// controlled. It must never reach v-html unsanitised — see the deferred
// stored-XSS finding from the M2 security review. Every render path for
// untrusted markup goes through sanitizeArticle().

import DOMPurify from 'dompurify'

// Open external links in a new tab without leaking the opener reference.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.getAttribute('href')) {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer nofollow')
  }
})

export function sanitizeArticle(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    // Forbid anything that can execute or exfiltrate, even though DOMPurify
    // strips scripts by default — being explicit documents intent.
    FORBID_TAGS: ['style', 'form', 'input', 'button'],
    FORBID_ATTR: ['style'],
    ADD_ATTR: ['target'],
  })
}
