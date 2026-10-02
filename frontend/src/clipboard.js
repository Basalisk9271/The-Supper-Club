// The Clipboard API may be unavailable on HTTP LAN addresses or denied by
// browser permissions. Keep a user-initiated fallback for those environments.
export async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Try the selection-based fallback before offering manual copying.
  }

  const previous = document.activeElement
  const field = document.createElement('textarea')
  field.value = text
  field.readOnly = true
  field.style.cssText = 'position:fixed;left:0;top:0;opacity:0;font-size:16px;pointer-events:none'
  document.body.appendChild(field)
  try {
    field.focus({preventScroll: true})
    field.select()
    field.setSelectionRange(0, text.length)
    return document.execCommand('copy') === true
  } catch {
    return false
  } finally {
    field.remove()
    previous?.focus({preventScroll: true})
  }
}
