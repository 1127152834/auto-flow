import type { DesktopResult } from './settings'

export type ExternalLinkBridge = {
  openExternalLink(url: string): Promise<DesktopResult<{ opened: true }>>
}

export function validatedExternalUrl(raw: unknown): string {
  if (typeof raw !== 'string' || /[\u0000-\u0020\u007f]/u.test(raw)) throw new Error('链接无效')
  const url = new URL(raw)
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password) throw new Error('仅支持 HTTP 或 HTTPS 链接')
  return url.href
}
