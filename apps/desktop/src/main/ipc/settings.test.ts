import { expect, it, vi } from 'vitest'
import { protectSettingsHandler } from './settings'
import { SettingsError } from '../settings/store'

it('rejects other windows and subframes before performing any action', async () => {
  const frame = {}
  const action = vi.fn(async () => true)
  const handler = protectSettingsHandler(5, action)
  expect(await handler({ sender: { id: 6, mainFrame: frame }, senderFrame: frame })).toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
  expect(await handler({ sender: { id: 5, mainFrame: frame }, senderFrame: {} })).toMatchObject({ ok: false })
  expect(action).not.toHaveBeenCalled()
  expect(await handler({ sender: { id: 5, mainFrame: frame }, senderFrame: frame })).toEqual({ ok: true, value: true })
})

it('returns actionable known errors without serializing raw filesystem or secret-bearing errors', async () => {
  const frame = {}; const event = { sender: { id: 5, mainFrame: frame }, senderFrame: frame }
  expect(await protectSettingsHandler(5, async () => { throw new SettingsError('WORKSPACE_BUSY', '任务进行中') })(event)).toEqual({ ok: false, error: { code: 'WORKSPACE_BUSY', message: '任务进行中' } })
  const result = await protectSettingsHandler(5, async () => { throw new Error('token=never-export /Users/private') })(event)
  expect(result).toMatchObject({ ok: false, error: { code: 'LOCAL_OPERATION_FAILED' } })
  expect(JSON.stringify(result)).not.toContain('never-export')
})
