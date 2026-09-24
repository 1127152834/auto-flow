import { toElectronAccelerator } from './scheduled-hotkeys'

// Source: WebRPA@5ccb900e customShortcuts / GlobalHotkeyService.
// AutoFlow adaptation: Electron owns native registration; callbacks target only
// the current Studio host, never the durable workflow event journal.
export const STUDIO_HOTKEY_ACTIONS = [
  'run_workflow', 'run_workflow_headless', 'stop_workflow', 'save_workflow',
  'new_workflow', 'open_local_workflow', 'open_module_search', 'toggle_ai', 'export_workflow',
] as const
export type StudioHotkeyAction = typeof STUDIO_HOTKEY_ACTIONS[number]
export type StudioHotkeyOwner = { windowId: number; instanceId: string }
export type StudioHotkeyUpdateResult =
  | { success: true; count: number }
  | { success: false; code: string; error: string }

type ShortcutRegistry = {
  register(accelerator: string, callback: () => void): boolean
  unregister(accelerator: string): void
}
type Registration = { actionId: StudioHotkeyAction }
const actions = new Set<string>(STUDIO_HOTKEY_ACTIONS)
const sameOwner = (left: StudioHotkeyOwner | null, right: StudioHotkeyOwner): boolean =>
  left?.windowId === right.windowId && left.instanceId === right.instanceId
const failure = (code: string, error: string): StudioHotkeyUpdateResult => ({ success: false, code, error })

export function toStudioAccelerator(value: string): string | null {
  const parts = value.split('+').map(part => part.trim().toLowerCase())
  if (parts.some(part => !part)) return null
  const key = parts.pop()!
  const aliases: Record<string, string> = { ctrl: 'ctrl', control: 'ctrl', alt: 'alt', shift: 'shift', meta: 'cmd', cmd: 'cmd', command: 'cmd' }
  if (Object.hasOwn(aliases, key)) return null
  const modifiers = parts.map(part => Object.hasOwn(aliases, part) ? aliases[part]! : null)
  if (modifiers.includes(null) || new Set(modifiers).size !== modifiers.length) return null
  const keyAliases: Record<string, string> = { arrowup: 'up', arrowdown: 'down', arrowleft: 'left', arrowright: 'right', escape: 'esc', return: 'enter', ' ': 'space' }
  const normalizedKey = Object.hasOwn(keyAliases, key) ? keyAliases[key]! : key
  if (!/^[a-z0-9`\-=[\]\\;',./]$/.test(normalizedKey)
    && !/^f(?:[1-9]|1\d|2[0-4])$/.test(normalizedKey)
    && !['esc', 'enter', 'space', 'up', 'down', 'left', 'right', 'tab', 'backspace', 'delete', 'insert', 'home', 'end', 'pageup', 'pagedown', 'capslock', 'numlock', 'scrolllock', 'printscreen', 'pause'].includes(normalizedKey)) return null
  return toElectronAccelerator([...['ctrl', 'alt', 'shift', 'cmd'].filter(part => modifiers.includes(part)), normalizedKey].join('+'))
}

export class StudioHotkeyController {
  private registered = new Map<string, Registration>()
  private owner: StudioHotkeyOwner | null = null

  constructor(private readonly dependencies: {
    shortcuts: ShortcutRegistry
    /** Return null unless both the Studio window and its ready sidecar are current. */
    getOwner(): StudioHotkeyOwner | null
    dispatch(actionId: StudioHotkeyAction): void
  }) {}

  update(mapping: unknown, owner: StudioHotkeyOwner): StudioHotkeyUpdateResult {
    if (!Number.isSafeInteger(owner.windowId) || owner.windowId < 1 || !owner.instanceId?.trim()
      || !sameOwner(this.dependencies.getOwner(), owner)) return failure('STUDIO_HOTKEY_OWNER_UNAVAILABLE', '工作台或服务连接已变化，请重试')
    if (!mapping || typeof mapping !== 'object' || Array.isArray(mapping)) return failure('STUDIO_HOTKEY_INVALID', '快捷键配置必须是动作与组合键的映射')
    const desired = new Map<string, StudioHotkeyAction>()
    for (const [actionId, value] of Object.entries(mapping)) {
      if (!actions.has(actionId) || typeof value !== 'string') return failure('STUDIO_HOTKEY_INVALID', '快捷键动作或组合键无效')
      // The source settings clear a binding by storing an empty string.
      if (!value.trim()) continue
      const accelerator = toStudioAccelerator(value)
      if (!accelerator) return failure('STUDIO_HOTKEY_INVALID', `组合键无效：${value}`)
      if (desired.has(accelerator)) return failure('STUDIO_HOTKEY_DUPLICATE', `组合键重复：${value}`)
      desired.set(accelerator, actionId as StudioHotkeyAction)
    }
    // Native callbacks belong to the window/service that registered them.
    // A new owner must acquire fresh callback identities even for unchanged keys.
    // Same-owner edits retain the staged, atomic update below.
    if (this.owner && !sameOwner(this.owner, owner)) this.clear()
    const added = new Map<string, Registration>()
    const rollback = () => {
      for (const accelerator of added.keys()) this.dependencies.shortcuts.unregister(accelerator)
    }
    for (const [accelerator, actionId] of desired) {
      if (this.registered.has(accelerator)) continue
      const registration = { actionId }
      let accepted = false
      try {
        accepted = this.dependencies.shortcuts.register(accelerator, () => {
          if (this.registered.get(accelerator) !== registration || !this.owner
            || !sameOwner(this.dependencies.getOwner(), this.owner)) return
          this.dependencies.dispatch(registration.actionId)
        })
      } catch {
        // A native exception is not a successful registration.
      }
      if (!accepted) {
        rollback()
        return failure('STUDIO_HOTKEY_REGISTRATION_FAILED', `无法注册组合键 ${accelerator}，可能已被系统或其他功能占用`)
      }
      added.set(accelerator, registration)
    }
    if (!sameOwner(this.dependencies.getOwner(), owner)) {
      rollback()
      return failure('STUDIO_HOTKEY_OWNER_UNAVAILABLE', '工作台或服务连接已变化，请重试')
    }
    // Existing accelerators may swap actions without unregistering each other.
    for (const [accelerator, registration] of this.registered) {
      const actionId = desired.get(accelerator)
      if (actionId) registration.actionId = actionId
      else {
        this.registered.delete(accelerator)
        this.dependencies.shortcuts.unregister(accelerator)
      }
    }
    for (const [accelerator, registration] of added) this.registered.set(accelerator, registration)
    this.owner = { ...owner }
    return { success: true, count: desired.size }
  }

  clear(): void {
    const accelerators = [...this.registered.keys()]
    this.registered.clear()
    this.owner = null
    for (const accelerator of accelerators) this.dependencies.shortcuts.unregister(accelerator)
  }
}
