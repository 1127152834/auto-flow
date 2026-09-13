import { expect, it, vi } from 'vitest'
vi.mock('../hooks/stores/aiPermissionStore', () => ({ actionNeedsApproval: () => false, requestApproval: async () => true }))
import { executeClientAction, onAssistantUiEvent } from '../api/aiAssistantSkills'

it('does not claim an unmounted panel was opened and delivers exactly once when it is connected', async () => {
  expect((await executeClientAction('open_global_config')).success).toBe(false)
  const handler = vi.fn()
  const unsubscribe = onAssistantUiEvent('open_global_config', handler)
  try {
    expect((await executeClientAction('open_global_config', { tab: 'models' })).success).toBe(true)
    expect(handler).toHaveBeenCalledExactlyOnceWith({ tab: 'models' })
  } finally { unsubscribe() }
  expect((await executeClientAction('open_global_config')).success).toBe(false)
  expect(handler).toHaveBeenCalledOnce()
})

it('reports a failed consumer instead of confirming success', async () => {
  const log = vi.spyOn(console, 'error').mockImplementation(() => {})
  const unsubscribe = onAssistantUiEvent('open_global_config', () => { throw new Error('failed to open') })
  try {
    expect((await executeClientAction('open_global_config')).success).toBe(false)
    expect(log).toHaveBeenCalledOnce()
  } finally { unsubscribe(); log.mockRestore() }
})
