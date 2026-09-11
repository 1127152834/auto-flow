import type { DesktopResult } from '../../shared/settings'
import { SettingsError } from '../settings/store'

export type SettingsIpcEvent = { sender: { id: number; mainFrame: unknown }; senderFrame: unknown }
export function protectSettingsHandler<T>(senderId: number, action: (...args: unknown[]) => Promise<T>) {
  return async (event: SettingsIpcEvent, ...args: unknown[]): Promise<DesktopResult<T>> => {
    if (event.sender.id !== senderId || !event.senderFrame || event.senderFrame !== event.sender.mainFrame) return { ok: false, error: { code: 'UNAUTHORIZED_WINDOW', message: '此窗口不能访问桌面设置' } }
    try { return { ok: true, value: await action(...args) } } catch (error) {
      return { ok: false, error: error instanceof SettingsError ? { code: error.code, message: error.message } : { code: 'LOCAL_OPERATION_FAILED', message: '本地操作未完成，请检查权限并重试' } }
    }
  }
}
