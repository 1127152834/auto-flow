import { afterEach, expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
const clients: StudioEventClient[] = []
afterEach(() => { clients.splice(0).forEach(client => client.disconnect()); setStudioTransport(mockRequest) })
it('queries the original command after a lost response without submitting it again', async () => {
  const requests: string[] = []
  let commandId = ''
  setStudioTransport(async (input, init) => {
    const url = String(input); requests.push(url)
    if (url.endsWith('/events/commands')) {
      commandId = JSON.parse(String(init?.body)).commandId
      throw new TypeError('response lost after acceptance')
    }
    if (url.includes('/events/commands/')) return Response.json({ commandId, success: true, httpStatus: 200 })
    return mockRequest(input, init)
  })
  const client = new StudioEventClient('http://autoflow-studio.mock'); clients.push(client)
  const applied = vi.fn(), error = vi.fn()
  client.on('command_result', applied); client.on('command_error', error)
  client.emit('set_verbose_log', { enabled: true })
  await vi.waitFor(() => expect(applied).toHaveBeenCalledWith(expect.objectContaining({ commandId, success: true })))
  expect(requests.filter(url => url.endsWith('/events/commands'))).toHaveLength(1)
  expect(requests.filter(url => url.endsWith(`/events/commands/${commandId}`))).toHaveLength(1)
  expect(error).not.toHaveBeenCalled()
})
it('reports an unconfirmed command when lookup fails, without retrying the operation', async () => {
  const post = vi.fn()
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith('/events/commands')) { post(init); throw new TypeError('network lost') }
    if (String(input).includes('/events/commands/')) return Response.json({ error: 'not found' }, { status: 404 })
    return mockRequest(input, init)
  })
  const client = new StudioEventClient('http://autoflow-studio.mock'); clients.push(client)
  const error = vi.fn(), result = vi.fn()
  client.on('command_error', error); client.on('command_result', result)
  client.emit('execution_stop', { workflowId: 'old' })
  await vi.waitFor(() => expect(error).toHaveBeenCalledWith(expect.objectContaining({ status: 'unconfirmed', commandId: expect.any(String) })))
  expect(result).not.toHaveBeenCalled(); expect(post).toHaveBeenCalledOnce()
})
