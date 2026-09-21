import { expect, it, vi } from 'vitest'
import { createConsoleController } from '../state/console-controller'
import { DEVICE_ID, makeSession } from './management-fixtures'

it('does not replay old input after leaving', async () => {
  const api = {
    session: vi.fn(async () => makeSession()),
    input: vi.fn(async (_id: string, body: { text?: string }) => { calls.push(body.text ?? ''); return makeSession() }),
    action: vi.fn(async () => makeSession()),
    heartbeat: vi.fn(async () => makeSession()),
  }
  const calls: string[] = []
  const controller = createConsoleController(api, { workspaceIdentity: 'w', backendInstanceId: 'b' })
  await controller.open(DEVICE_ID)
  controller.send({ kind: 'text', text: 'sample' })
  await controller.leave()
  await controller.open(DEVICE_ID)
  await controller.flush()
  expect(calls).toHaveLength(1)
})
