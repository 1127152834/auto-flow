import { expect, it } from 'vitest'
import { displayManagementState, canManage } from '../state/management-state'

it('shows an active delete operation before the runtime state', () => {
  expect(displayManagementState({ runtimeState: 'ready', operation: { action: 'delete', state: 'running' }, stale: false })).toBe('正在删除')
})

it('does not make stale or unknown devices actionable', () => {
  expect(canManage({ runtimeState: 'unknown', operation: null, stale: true }, 'start')).toBe(false)
})
