import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError, createApiClient } from './client'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it('adds the sidecar token to every request', async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    expect(init?.headers).toEqual({ 'x-autoflow-token': 'secret' })
    return new Response(JSON.stringify({
      status: 'ok',
      apiVersion: 'v1',
      instanceId: 'test',
    }), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)

  await expect(createApiClient('http://127.0.0.1:43127', 'secret').health()).resolves.toEqual({
    status: 'ok',
    apiVersion: 'v1',
    instanceId: 'test',
  })

  expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/health', {
    body: undefined,
    headers: { 'x-autoflow-token': 'secret' },
    signal: expect.any(AbortSignal),
  })
})


it('preserves structured error metadata without retaining request content', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ error: {
    code: 'MODEL_EXISTS', message: '模型已存在', details: { fields: { modelKey: '重复' } }, requestId: 'test-request',
  } }, { status: 409 })))
  await expect(createApiClient('http://localhost', 'secret').request('/api/v1/models/sample')).rejects.toMatchObject({
    message: '模型已存在', status: 409, code: 'MODEL_EXISTS', details: { fields: { modelKey: '重复' } }, requestId: 'test-request',
  })
})

it('handles successful empty deletion and forwards cancellation', async () => {
  const signal = new AbortController().signal
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
  vi.stubGlobal('fetch', fetchMock)
  await expect(createApiClient('http://localhost', 'test-token').request<void>('/api/v1/models/sample', { method: 'DELETE', signal })).resolves.toBeUndefined()
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'DELETE', signal: expect.any(AbortSignal), headers: { 'x-autoflow-token': 'test-token' } })
})

it.each(['<h1>private upstream content</h1>', JSON.stringify({ detail: 'private upstream content' }), JSON.stringify({ error: 'private upstream content' })])('uses a safe message for malformed error bodies', async (body) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 502 })))
  await expect(createApiClient('http://localhost', 'test-token').request('/api/v1/models/options')).rejects.toMatchObject({
    message: 'API request failed with status 502', status: 502,
  })
})

it('preserves structured errors for risk confirmation and rate limiting', async () => {
  const error = { code: 'PROXYPANEL_RATE_LIMITED', message: '稍后重试', request_id: 'r1', field_errors: {}, retry_after_seconds: 12, outcome_unknown: false }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error }), { status: 429 })))
  await expect(createApiClient('http://127.0.0.1:43127', 'secret').request('/api/v1/proxies')).rejects.toMatchObject({ status: 429, error })
})

it('supports a no-content delete response', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
  await expect(createApiClient('http://127.0.0.1:43127', 'secret').request('/api/v1/proxy-groups/g1', { method: 'DELETE' })).resolves.toBeUndefined()
})

it('serializes object bodies as JSON without overriding explicit content types', async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers)
    expect(headers.get('content-type')).toBe('application/json')
    expect(init?.body).toBe(JSON.stringify({ name: '工作环境' }))
    return new Response(JSON.stringify({ id: 'profile-1' }), { status: 201 })
  })
  vi.stubGlobal('fetch', fetchMock)

  await createApiClient({ baseUrl: 'http://127.0.0.1:43127', token: 'secret' })
    .request('/api/v1/profiles', { method: 'POST', body: { name: '工作环境' } })
})

it('exposes validation fields, error code, and request id', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    error: {
      code: 'VALIDATION_ERROR',
      message: 'Request validation failed',
      details: { fields: { startUrl: 'invalid URL' } },
      requestId: 'request-1',
    },
  }), { status: 422 })))

  const error = await createApiClient('http://127.0.0.1:43127', 'secret')
    .request('/api/v1/profiles', { method: 'POST' })
    .catch((value: unknown) => value)

  expect(error).toBeInstanceOf(ApiClientError)
  expect(error).toMatchObject({
    status: 422,
    code: 'VALIDATION_ERROR',
    requestId: 'request-1',
    fields: { startUrl: 'invalid URL' },
  })
})

it('maps the legacy authentication detail to fixed copy', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(
    JSON.stringify({ detail: 'Invalid sidecar token' }),
    { status: 401 },
  )))

  await expect(createApiClient('http://127.0.0.1:43127', 'bad-token').health())
    .rejects.toMatchObject({ status: 401, message: '本地服务认证失败' })
})

it('does not expose an arbitrary non-authentication detail', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(
    JSON.stringify({ detail: 'upstream internals' }),
    { status: 502 },
  )))

  await expect(createApiClient('http://127.0.0.1:43127', 'secret').health())
    .rejects.toMatchObject({ status: 502, message: 'API request failed with status 502' })
})

it('aborts a request when its timeout elapses', async () => {
  vi.useFakeTimers()
  let signal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    signal = init?.signal ?? undefined
    return await new Promise<Response>((_resolve, reject) => {
      signal?.addEventListener('abort', () => reject(signal?.reason), { once: true })
    })
  }))

  const request = createApiClient({
    baseUrl: 'http://127.0.0.1:43127',
    token: 'secret',
    timeoutMs: 25,
  }).health()
  const rejection = expect(request).rejects.toMatchObject({ name: 'TimeoutError' })
  await vi.advanceTimersByTimeAsync(25)

  await rejection
  expect(signal?.aborted).toBe(true)
})

it('honors caller cancellation before the timeout', async () => {
  const controller = new AbortController()
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    const signal = init?.signal
    return await new Promise<Response>((_resolve, reject) => {
      signal?.addEventListener('abort', () => reject(signal.reason), { once: true })
    })
  }))

  const request = createApiClient('http://127.0.0.1:43127', 'secret')
    .request('/api/v1/profiles', { signal: controller.signal })
  controller.abort(new DOMException('cancelled', 'AbortError'))

  await expect(request).rejects.toMatchObject({ name: 'AbortError' })
})

it('opens an authenticated event stream with caller-controlled lifetime', async () => {
  const controller = new AbortController()
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    expect(new Headers(init?.headers).get('x-autoflow-token')).toBe('secret')
    expect(init?.signal?.aborted).toBe(false)
    return new Response(new ReadableStream({
      start(streamController) {
        init?.signal?.addEventListener('abort', () => streamController.error(init.signal?.reason), { once: true })
      },
    }))
  })
  vi.stubGlobal('fetch', fetchMock)

  const client = createApiClient('http://127.0.0.1:43127', 'secret')
  const response = await client.stream('/api/v1/kernels/events', { signal: controller.signal })
  const read = response.body?.getReader().read()
  controller.abort(new DOMException('cancelled', 'AbortError'))
  await expect(read).rejects.toMatchObject({ name: 'AbortError' })
})

it('times out only the event stream connection attempt', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => (
    await new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
    })
  )))
  const client = createApiClient({
    baseUrl: 'http://127.0.0.1:43127', token: 'secret', streamConnectTimeoutMs: 25,
  })
  const connection = client.stream('/api/v1/kernels/events')
  const rejection = expect(connection).rejects.toMatchObject({ name: 'TimeoutError' })
  await vi.advanceTimersByTimeAsync(25)
  await rejection
})

it('keeps the request timeout active while the response body is being parsed', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: () => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
    }),
  } as Response)))

  const request = createApiClient({
    baseUrl: 'http://127.0.0.1:43127', token: 'secret', timeoutMs: 25,
  }).health()
  const rejection = expect(request).rejects.toMatchObject({ name: 'TimeoutError' })
  await vi.advanceTimersByTimeAsync(25)
  await rejection
})
