import type { DesktopResult } from './settings'

export type StudioPlatformAction =
  | { action: 'clipboard_write_text'; text: string }
  | { action: 'clipboard_write_image'; path: string }
  | { action: 'clipboard_read_text' }
  | { action: 'beep'; count: number; interval: number }
  | { action: 'notification'; title: string; message: string; duration: number; playSound: boolean }

export type StudioPlatformActionResult = { value?: string }

export type StudioPlatformBridge = {
  runStudioPlatformAction(request: StudioPlatformAction): Promise<DesktopResult<StudioPlatformActionResult>>
}
