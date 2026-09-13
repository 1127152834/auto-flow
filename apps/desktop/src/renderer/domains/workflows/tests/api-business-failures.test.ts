import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest } from '../api'
import { configureStudioConnection } from '../api/config'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'])('API response contract over %s', mode => {
  let server: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let restore: () => void
  let respond: () => Response
  const disconnected = vi.fn()
  beforeEach(async () => {
    disconnected.mockClear()
    window.addEventListener('studio:connection-error', disconnected)
    const handler = async () => respond()
    if (mode === 'http') server = await startHttpStudioFixture(handler)
    restore = configureStudioConnection(server?.origin || 'http://autoflow-studio.mock', mode === 'http' ? fetch : handler)
  })
  afterEach(async () => { restore(); window.removeEventListener('studio:connection-error', disconnected); await server?.close(); server = undefined })

  it.each([
    [{ success: false, error: '凭据不存在' }, '凭据不存在'],
    [{ success: false, message: '连接测试失败' }, '连接测试失败'],
    [{ success: false, detail: '权限不足' }, '权限不足'],
    [{ success: false }, '操作失败，服务未提供具体原因'],
  ])('rejects explicit business failure %j without a network outage', async (body, message) => {
    respond = () => Response.json(body)
    const response = await apiRequest('/contract')
    expect(response).toEqual({ success: false, error: message })
    expect(disconnected).not.toHaveBeenCalled()
  })
  it.each([
    { success: true, matched: false, count: 0 },
    { data: { success: false, error: '用户数据里的字段' } },
    { name: '模块元数据' },
    [{ success: false }],
    null,
  ])('retains successful payload %j without unwrapping it', async body => {
    respond = () => Response.json(body)
    expect(await apiRequest('/contract')).toEqual({ success: true, data: body })
  })
  it('keeps HTTP validation paths and status in the error', async () => {
    respond = () => Response.json({ detail: [{ loc: ['body', 'nodeId', 'config', 'selector'], msg: '必填' }] }, { status: 422 })
    const response = await apiRequest('/contract')
    expect(response.success).toBe(false)
    expect(response.error).toContain('HTTP 422')
    expect(response.error).toContain('body.nodeId.config.selector: 必填')
    expect(disconnected).not.toHaveBeenCalled()
  })
  it('does not report a malformed JSON success response as success', async () => {
    respond = () => new Response('{broken', { headers: { 'Content-Type': 'application/json' } })
    const response = await apiRequest('/contract')
    expect(response.success).toBe(false)
    expect(response.error).toBeTruthy()
    expect(disconnected).not.toHaveBeenCalled()
  })
})
