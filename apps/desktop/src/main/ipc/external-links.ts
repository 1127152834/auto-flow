import { validatedExternalUrl } from '../../shared/external-links'
import type { DesktopResult } from '../../shared/settings'

type InvokeEvent = { sender: { id: number; mainFrame: object }; senderFrame: object | null }
type Dependencies = { allowedSenderId: number; openExternal(url: string): Promise<void> }

export function createOpenExternalLinkHandler({ allowedSenderId, openExternal }: Dependencies) {
  return async (event: InvokeEvent, raw: unknown): Promise<DesktopResult<{ opened: true }>> => {
    if (event.sender.id !== allowedSenderId || !event.senderFrame || event.senderFrame !== event.sender.mainFrame) {
      return { ok: false, error: { code: 'UNAUTHORIZED_WINDOW', message: '当前窗口不能打开此链接。' } }
    }
    let url: string
    try { url = validatedExternalUrl(raw) } catch {
      return { ok: false, error: { code: 'INVALID_EXTERNAL_LINK', message: '链接无效，仅支持不含登录凭据的 HTTP 或 HTTPS 链接。' } }
    }
    try {
      await openExternal(url)
      return { ok: true, value: { opened: true } }
    } catch {
      return { ok: false, error: { code: 'EXTERNAL_LINK_FAILED', message: '系统未能打开链接，请重试或复制链接。' } }
    }
  }
}
