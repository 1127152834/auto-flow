import { afterEach, expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
const clients: StudioEventClient[] = []
afterEach(() => { clients.splice(0).forEach(client => client.disconnect()); setStudioTransport(mockRequest) })

it.each([
  ['wrong identity', { commandId: 'another', success: true }],
  ['missing identity', { success: true }],
  ['missing success', { commandId: 'original' }],
  ['nonboolean success', { commandId: 'original', success: 'yes' }],
  ['array', []],
  ['null', null],
])('queries the original command after a malformed successful response: %s', async (_label, body) => {
  const calls: string[] = []
  setStudioTransport(async (input, init) => {
    const url = String(input)
    if (!url.includes('/events/commands')) return mockRequest(input, init)
    calls.push(url)
    return Response.json(url.endsWith('/events/commands') ? body : { commandId: 'original', success: true, httpStatus: 200 })
  })
  const client = new StudioEventClient('http://autoflow-studio.mock'); clients.push(client)
  const result = vi.fn(), error = vi.fn()
  client.on('command_result', result); client.on('command_error', error)
  client.emit('set_verbose_log', { enabled: true }, 'original')
  await vi.waitFor(() => expect(result).toHaveBeenCalledWith({ commandId: 'original', success: true, httpStatus: 200 }))
  expect(result).toHaveBeenCalledOnce(); expect(error).not.toHaveBeenCalled()
  expect(calls).toEqual(['http://autoflow-studio.mock/api/events/commands', 'http://autoflow-studio.mock/api/events/commands/original'])
})

it.each([
  { commandId: 'other', success: true, httpStatus: 200 },
  { commandId: 'original', success: true, httpStatus: 0 },
  { commandId: 'original', success: true, httpStatus: 200.5 },
  { commandId: 'original', success: true, httpStatus: 700 },
  { commandId: 'original', httpStatus: 200 },
  { commandId: 'original', success: 'true', httpStatus: 200 },
])('keeps an invalid lookup unconfirmed: %j', async body => {
  const post = vi.fn()
  setStudioTransport(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/events/commands')) { post(); throw new Error('response lost') }
    if (url.includes('/events/commands/')) return Response.json(body)
    return mockRequest(input, init)
  })
  const client = new StudioEventClient('http://autoflow-studio.mock'); clients.push(client)
  const result = vi.fn(), error = vi.fn()
  client.on('command_result', result); client.on('command_error', error)
  client.emit('set_verbose_log', { enabled: true }, 'original')
  await vi.waitFor(() => expect(error).toHaveBeenCalledWith(expect.objectContaining({ commandId: 'original', status: 'unconfirmed' })))
  expect(result).not.toHaveBeenCalled(); expect(post).toHaveBeenCalledOnce()
})

it('reports an explicit HTTP rejection without querying or resubmitting', async () => {
  const calls: string[] = []
  setStudioTransport(async (input, init) => {
    const url = String(input)
    if (!url.includes('/events/commands')) return mockRequest(input, init)
    calls.push(url)
    return Response.json({ success: false, error: '命令 ID 冲突' }, { status: 409 })
  })
  const client = new StudioEventClient('http://autoflow-studio.mock'); clients.push(client)
  const error = vi.fn(); client.on('command_error', error)
  client.emit('set_verbose_log', { enabled: true }, 'original')
  await vi.waitFor(() => expect(error).toHaveBeenCalledWith({ commandId: 'original', success: false, error: '命令 ID 冲突' }))
  expect(calls).toHaveLength(1)
})
