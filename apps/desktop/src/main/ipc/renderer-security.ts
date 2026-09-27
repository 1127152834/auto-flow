import type { WebContents } from 'electron'
import type { DesktopIpcEvent } from './automation-studio'

/** Compare the entry document, allowing its router hash and Studio context query. */
export function isTrustedRenderer(event: DesktopIpcEvent, entryUrl: string): boolean {
  const frame = event.senderFrame
  if (!frame || frame !== event.sender.mainFrame || typeof frame !== 'object' || !('url' in frame) || typeof frame.url !== 'string') return false
  try {
    const actual = new URL(frame.url)
    const expected = new URL(entryUrl)
    if (!['file:', 'http:', 'https:'].includes(actual.protocol) || actual.username || actual.password) return false
    actual.hash = expected.hash = ''
    actual.search = expected.search = ''
    return actual.href === expected.href
  } catch { return false }
}

export function protectRendererNavigation(contents: WebContents): void {
  contents.setWindowOpenHandler(() => ({ action: 'deny' }))
  contents.on('will-navigate', event => event.preventDefault())
  contents.on('will-redirect', event => event.preventDefault())
  contents.on('will-attach-webview', event => event.preventDefault())
}
