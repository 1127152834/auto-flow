// @vitest-environment node
import { expect, it, vi } from 'vitest'
import { STUDIO_HOTKEY_ACTIONS, StudioHotkeyController, toStudioAccelerator } from './studio-hotkeys'
import type { StudioHotkeyOwner } from './studio-hotkeys'

function setup() {
  let owner: StudioHotkeyOwner | null = { windowId: 7, instanceId: 'sidecar-1' }
  const callbacks = new Map<string, () => void>()
  const dispatch = vi.fn()
  const register = vi.fn((key: string, callback: () => void) => {
    if (callbacks.has(key)) return false
    callbacks.set(key, callback)
    return true
  })
  const unregister = vi.fn((key: string) => { callbacks.delete(key) })
  const controller = new StudioHotkeyController({ shortcuts: { register, unregister }, getOwner: () => owner, dispatch })
  return { controller, callbacks, dispatch, register, unregister, initial: { ...owner }, setOwner: (next: StudioHotkeyOwner | null) => { owner = next } }
}

it.each([
  ['Ctrl+Alt+R', 'Control+Alt+R'], ['Meta+Shift+S', 'Shift+Command+S'],
  ['Shift+Ctrl+R', 'Control+Shift+R'], ['Meta+ArrowLeft', 'Command+Left'],
  ['F24', 'F24'], ['Alt+Space', 'Alt+Space'],
  ['Ctrl', null], ['Ctrl+Ctrl+A', null], ['Ctrl++A', null],
  ['Ctrl+NotAKey', null], ['Hyper+A', null], ['Meta+Cmd+A', null],
])('normalizes source combination %s to %s', (source, expected) => {
  expect(toStudioAccelerator(source)).toBe(expected)
})

it('registers all nine approved actions and dispatches only from actual native callbacks', () => {
  const fixture = setup()
  expect(STUDIO_HOTKEY_ACTIONS).toEqual(['run_workflow', 'run_workflow_headless', 'stop_workflow', 'save_workflow', 'new_workflow', 'open_local_workflow', 'open_module_search', 'toggle_ai', 'export_workflow'])
  const bindings = Object.fromEntries(STUDIO_HOTKEY_ACTIONS.map((action, index) => [action, `Ctrl+F${index + 1}`]))
  expect(fixture.controller.update(bindings, fixture.initial)).toEqual({ success: true, count: 9 })
  expect(fixture.register).toHaveBeenCalledTimes(9)
  expect(fixture.dispatch).not.toHaveBeenCalled()
  for (let i = 0; i < 9; i++) fixture.callbacks.get(`Control+F${i + 1}`)!()
  expect(fixture.dispatch.mock.calls.map(call => call[0])).toEqual([...STUDIO_HOTKEY_ACTIONS])
})

it('changes bindings and clears only its own native registrations', () => {
  const f = setup()
  const external = vi.fn()
  f.callbacks.set('Control+F12', external)
  expect(f.controller.update({ save_workflow: 'Ctrl+S' }, f.initial).success).toBe(true)
  const stale = f.callbacks.get('Control+S')!
  expect(f.controller.update({ save_workflow: 'Meta+S' }, f.initial)).toEqual({ success: true, count: 1 })
  expect(f.unregister).toHaveBeenCalledWith('Control+S')
  stale()
  expect(f.dispatch).not.toHaveBeenCalled()
  f.callbacks.get('Command+S')!()
  expect(f.dispatch).toHaveBeenCalledWith('save_workflow')
  f.controller.clear()
  expect([...f.callbacks.keys()]).toEqual(['Control+F12'])
  expect(f.unregister).not.toHaveBeenCalledWith('Control+F12')
  expect(f.callbacks.get('Control+F12')).toBe(external)
  f.controller.clear()
  expect(f.unregister).toHaveBeenCalledTimes(2)
})

it.each([false, 'throw'] as const)('rolls back only newly registered keys on native failure %s', failure => {
  const f = setup()
  f.controller.update({ save_workflow: 'Ctrl+S' }, f.initial)
  const old = f.callbacks.get('Control+S')!
  f.callbacks.set('Control+F12', vi.fn()) // A scheduled-task or another app owns this key.
  if (failure === 'throw') f.register.mockImplementation((key, callback) => {
    if (key === 'Control+F12') throw new Error('native failure')
    f.callbacks.set(key, callback)
    return true
  })
  expect(f.controller.update({ new_workflow: 'Ctrl+N', run_workflow: 'Ctrl+F12' }, f.initial)).toMatchObject({ success: false, code: 'STUDIO_HOTKEY_REGISTRATION_FAILED' })
  expect([...f.callbacks.keys()].sort()).toEqual(['Control+F12', 'Control+S'])
  expect(f.unregister.mock.calls).toEqual([['Control+N']])
  old()
  expect(f.dispatch).toHaveBeenCalledExactlyOnceWith('save_workflow')
})

it('allows two owned keys to swap actions atomically without native unregister/re-register', () => {
  const f = setup()
  f.controller.update({ save_workflow: 'Ctrl+S', new_workflow: 'Ctrl+N' }, f.initial)
  f.controller.update({ save_workflow: 'Ctrl+N', new_workflow: 'Ctrl+S' }, f.initial)
  expect(f.register).toHaveBeenCalledTimes(2)
  expect(f.unregister).not.toHaveBeenCalled()
  f.callbacks.get('Control+S')!()
  f.callbacks.get('Control+N')!()
  expect(f.dispatch.mock.calls).toEqual([['new_workflow'], ['save_workflow']])
})

const invalidMappings: unknown[] = [
  null, [], { keyboard_action: 'Ctrl+K' }, { unknown: 'Ctrl+U' }, { toString: 'Ctrl+T' },
  { save_workflow: 4 }, { save_workflow: 'Ctrl' },
  { save_workflow: 'Ctrl+Shift+S', run_workflow: 'Shift+Control+S' },
]
it.each(invalidMappings.map(mapping => ({ mapping })))('rejects invalid or duplicate mapping before touching old registrations: $mapping', ({ mapping }) => {
  const f = setup()
  f.controller.update({ save_workflow: 'Ctrl+S' }, f.initial)
  expect(f.controller.update(mapping, f.initial).success).toBe(false)
  expect(f.register).toHaveBeenCalledTimes(1)
  expect(f.unregister).not.toHaveBeenCalled()
  f.callbacks.get('Control+S')!()
  expect(f.dispatch).toHaveBeenCalledExactlyOnceWith('save_workflow')
})

it('treats source empty-string bindings as unbound and an empty mapping as clear', () => {
  const f = setup()
  f.controller.update({ save_workflow: 'Ctrl+S', run_workflow: 'Ctrl+R' }, f.initial)
  expect(f.controller.update({ save_workflow: '', run_workflow: 'Ctrl+R' }, f.initial)).toEqual({ success: true, count: 1 })
  expect([...f.callbacks.keys()]).toEqual(['Control+R'])
  expect(f.controller.update({}, f.initial)).toEqual({ success: true, count: 0 })
  expect(f.callbacks.size).toBe(0)
})

it.each([null, { windowId: 8, instanceId: 'sidecar-1' }, { windowId: 7, instanceId: 'sidecar-2' }])('fences callbacks and updates after owner becomes %j', next => {
  const f = setup()
  f.controller.update({ run_workflow: 'Ctrl+R' }, f.initial)
  const callback = f.callbacks.get('Control+R')!
  f.setOwner(next)
  callback()
  expect(f.dispatch).not.toHaveBeenCalled()
  expect(f.controller.update({ save_workflow: 'Ctrl+S' }, f.initial)).toMatchObject({ success: false, code: 'STUDIO_HOTKEY_OWNER_UNAVAILABLE' })
  expect(f.register).toHaveBeenCalledTimes(1)
  f.controller.clear()
  f.setOwner(f.initial)
  f.controller.update({ save_workflow: 'Ctrl+R' }, f.initial)
  callback()
  expect(f.dispatch).not.toHaveBeenCalled()
  f.callbacks.get('Control+R')!()
  expect(f.dispatch).toHaveBeenCalledExactlyOnceWith('save_workflow')
})

it('rolls back staged registrations when the owner changes during native registration', () => {
  const f = setup()
  f.controller.update({ save_workflow: 'Ctrl+S' }, f.initial)
  f.register.mockImplementation((key, callback) => {
    f.callbacks.set(key, callback)
    callback() // Staged callbacks are not active before the atomic commit.
    f.setOwner(null)
    return true
  })
  expect(f.controller.update({ new_workflow: 'Ctrl+N' }, f.initial)).toMatchObject({ success: false, code: 'STUDIO_HOTKEY_OWNER_UNAVAILABLE' })
  expect(f.dispatch).not.toHaveBeenCalled()
  expect([...f.callbacks.keys()]).toEqual(['Control+S'])
  f.setOwner(f.initial)
  f.callbacks.get('Control+S')!()
  expect(f.dispatch).toHaveBeenCalledExactlyOnceWith('save_workflow')
})

it('invalidates the original callback when another owner takes over the same accelerator', () => {
  const f = setup()
  expect(f.controller.update({ run_workflow: 'Ctrl+R' }, f.initial).success).toBe(true)
  const oldCallback = f.callbacks.get('Control+R')!
  const nextOwner = { windowId: 8, instanceId: 'sidecar-2' }
  f.setOwner(nextOwner)
  expect(f.controller.update({ save_workflow: 'Ctrl+R' }, nextOwner)).toEqual({ success: true, count: 1 })
  oldCallback()
  expect(f.dispatch).not.toHaveBeenCalled()
  expect(f.unregister).toHaveBeenCalledExactlyOnceWith('Control+R')
  expect(f.register).toHaveBeenCalledTimes(2)
  expect(f.callbacks.get('Control+R')).not.toBe(oldCallback)
  f.callbacks.get('Control+R')!()
  expect(f.dispatch).toHaveBeenCalledExactlyOnceWith('save_workflow')
})
