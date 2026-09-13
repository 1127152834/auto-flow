import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { ApiWireError } from '../../../shared/api/client'
import { apiRequest } from '../api'
import { configureStudioConnection } from '../api/config'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'])('AutoFlow errors through Studio %s transport', mode => {
  let server: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let restore: () => void
  let body: unknown
  let status: number
  beforeEach(async () => {
    const handler = async () => Response.json(body, { status })
    if (mode === 'http') server = await startHttpStudioFixture(handler)
    restore = configureStudioConnection(server?.origin || 'http://autoflow-studio.mock', mode === 'http' ? fetch : handler)
  })
  afterEach(async () => { restore(); await server?.close(); server = undefined })
  it.each([401, 409, 422, 503])('preserves a standard error envelope at HTTP %i', async code => {
    const error = { code: 'FIXTURE_REJECTED', message: '服务拒绝本次操作', details: { fields: { selector: '字段无效' } }, requestId: 'fixture-request' } satisfies ApiWireError
    body = { error }; status = code
    const result = await apiRequest('/contract')
    expect(result.success).toBe(false)
    expect(result.error).toContain('服务拒绝本次操作')
    expect(result.error).toContain(`HTTP ${code}`)
    expect(result.errorDetails).toEqual(error)
    expect(result.error).not.toContain('字段无效')
  })
  it('preserves the proxy error contract including unknown command outcome', async () => {
    const error = { code: 'PROXY_OUTCOME_UNKNOWN', message: '操作结果尚未确认', request_id: 'proxy-request', field_errors: {}, retry_after_seconds: 3, outcome_unknown: true } satisfies ApiWireError
    body = { error }; status = 503
    const result = await apiRequest('/contract')
    expect(result.errorDetails).toEqual(error)
    expect(result.error).toContain('操作结果尚未确认')
  })
  it('does not invent typed metadata for malformed envelopes', async () => {
    body = { error: { code: { invalid: true }, message: 123 } }; status = 500
    const result = await apiRequest('/contract')
    expect(result.success).toBe(false)
    expect(result.error).toContain('HTTP 500')
    expect(result.errorDetails).toBeUndefined()
  })
})
