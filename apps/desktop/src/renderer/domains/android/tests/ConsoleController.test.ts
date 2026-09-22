import { expect, it, vi } from 'vitest'
import { createConsoleController } from '../state/console-controller'
import { DEVICE_ID, makeSession } from './management-fixtures'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(next => { resolve = next })
  return { promise, resolve }
}

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

it('ends and discards an open response that arrives after leave', async () => {
  const opening = deferred<ReturnType<typeof makeSession>>()
  const api = {
    session: vi.fn(() => opening.promise),
    input: vi.fn(async () => makeSession()),
    action: vi.fn(async (target: ReturnType<typeof makeSession>) => makeSession({ ...target, state: 'closed' })),
    heartbeat: vi.fn(async () => makeSession()),
  }
  const controller = createConsoleController(api, { workspaceIdentity: 'w', backendInstanceId: 'b' })
  const pending = controller.open(DEVICE_ID)

  await controller.leave()
  const late = makeSession()
  opening.resolve(late)
  await pending

  expect(controller.session).toBeNull()
  expect(api.action).toHaveBeenCalledWith(late, 'end')
})

it('discards a stale open when switching devices before it resolves', async () => {
  const first = deferred<ReturnType<typeof makeSession>>()
  const second = deferred<ReturnType<typeof makeSession>>()
  const api = {
    session: vi.fn((deviceId: string) => deviceId === DEVICE_ID ? first.promise : second.promise),
    input: vi.fn(async () => makeSession()),
    action: vi.fn(async (target: ReturnType<typeof makeSession>) => makeSession({ ...target, state: 'closed' })),
    heartbeat: vi.fn(async () => makeSession()),
  }
  const controller = createConsoleController(api, { workspaceIdentity: 'w', backendInstanceId: 'b' })
  const firstOpen = controller.open(DEVICE_ID)
  const otherDevice = '44444444-4444-4444-8444-444444444444'
  const secondOpen = controller.open(otherDevice)
  const stale = makeSession({ deviceId: DEVICE_ID })
  first.resolve(stale)
  await firstOpen

  expect(controller.session).toBeNull()
  expect(api.action).toHaveBeenCalledWith(stale, 'end')

  const current = makeSession({ id: '55555555-5555-4555-8555-555555555555', deviceId: otherDevice })
  second.resolve(current)
  await secondOpen
  expect(controller.session).toEqual(current)
})

it('does not resurrect a session from a heartbeat that resolves after leave', async () => {
  const heartbeat = deferred<ReturnType<typeof makeSession>>()
  const api = {
    session: vi.fn(async () => makeSession()),
    input: vi.fn(async () => makeSession()),
    action: vi.fn(async (target: ReturnType<typeof makeSession>) => makeSession({ ...target, state: 'closed' })),
    heartbeat: vi.fn(() => heartbeat.promise),
  }
  const controller = createConsoleController(api, { workspaceIdentity: 'w', backendInstanceId: 'b' })
  await controller.open(DEVICE_ID)
  const pending = controller.heartbeat()

  await controller.leave()
  heartbeat.resolve(makeSession())
  await pending

  expect(controller.session).toBeNull()
})
