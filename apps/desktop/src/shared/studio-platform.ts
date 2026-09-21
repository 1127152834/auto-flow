import type { DesktopResult } from './settings'

export type StudioPlatformAction =
  | { action: 'clipboard_write_text'; text: string }
  | { action: 'clipboard_write_image'; path: string }
  | { action: 'clipboard_read_text' }
  | { action: 'beep'; count: number; interval: number }
  | { action: 'notification'; title: string; message: string; duration: number; playSound: boolean }
  | { action: 'open_path'; path: string }
  | { action: 'system_control'; operation: 'shutdown' | 'restart' | 'logout' | 'hibernate' | 'sleep'; delay: number; force: boolean }
  | { action: 'lock_screen' }

export type StudioPlatformActionResult = { value?: string }

export type StudioPlatformBridge = {
  runStudioPlatformAction(request: StudioPlatformAction): Promise<DesktopResult<StudioPlatformActionResult>>
}
