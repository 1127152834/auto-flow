import type { HealthResponse } from './types'
import type { components } from './generated'

export type ApiClientConfig = {
  baseUrl: string
  token: string
  timeoutMs?: number
  streamConnectTimeoutMs?: number
}

export type ApiRequestInit = Omit<RequestInit, 'body'> & {
  body?: BodyInit | object | null
  timeoutMs?: number
}

export type ApiWireError =
  | components['schemas']['ApiError']
  | components['schemas']['BrowserApiError']

export class ApiClientError extends Error {
  readonly code: string | null
  readonly details: Record<string, unknown>
  readonly requestId: string | null
  readonly fields?: Record<string, string>
  readonly error?: ApiWireError

  constructor(
    message: string,
    readonly status: number,
    codeOrError: string | ApiWireError | null = null,
    details: Record<string, unknown> = {},
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.error = typeof codeOrError === 'object' && codeOrError !== null ? codeOrError : undefined
    const value = record(this.error)
    this.code = this.error?.code ?? (typeof codeOrError === 'string' ? codeOrError : null)
    this.details = record(value?.details) ?? details
    this.requestId = typeof value?.requestId === 'string'
      ? value.requestId
      : typeof value?.request_id === 'string' ? value.request_id : requestId
    this.fields = stringRecord(this.details.fields) ?? stringRecord(value?.field_errors)
  }
}

export type ApiClient = {
  request<T>(path: string, init?: ApiRequestInit): Promise<T>
  health(): Promise<HealthResponse>
}

export type StreamingApiClient = ApiClient & {
  stream(path: string, init?: RequestInit): Promise<Response>
}

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : undefined
}

function stringRecord(value: unknown): Record<string, string> | undefined {
  const entries = Object.entries(record(value) ?? {})
    .filter((entry): entry is [string, string] => typeof entry[1] === 'string')
  return entries.length ? Object.fromEntries(entries) : undefined
}

export function parseApiWireError(payload: unknown): ApiWireError | undefined {
  const envelope = record(payload)
  const detail = record(envelope?.error)
  let error: ApiWireError | undefined
  if (typeof detail?.code === 'string' && typeof detail.message === 'string') {
    error = typeof detail.request_id === 'string'
      ? {
          code: detail.code, message: detail.message, request_id: detail.request_id,
          field_errors: record(detail.field_errors) ?? {},
          retry_after_seconds: typeof detail.retry_after_seconds === 'number' && Number.isFinite(detail.retry_after_seconds) ? detail.retry_after_seconds : null,
          outcome_unknown: detail.outcome_unknown === true,
        }
      : {
          code: detail.code, message: detail.message,
          details: record(detail.details) ?? {},
          requestId: typeof detail.requestId === 'string' ? detail.requestId : '',
        }
  }
  return error
}

function isJsonBody(body: ApiRequestInit['body']): body is Record<string, unknown> | unknown[] {
  if (Array.isArray(body)) return true
  if (!body || typeof body !== 'object') return false
  return Object.getPrototypeOf(body) === Object.prototype
}

function requestHeaders(
  headers: HeadersInit | undefined,
  token: string,
  jsonBody = false,
): Record<string, string> {
  const values = new Headers(headers)
  if (jsonBody && !values.has('content-type')) values.set('content-type', 'application/json')
  values.set('x-autoflow-token', token)
  return Object.fromEntries(values.entries())
}

function requestUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

export function createApiClient(config: ApiClientConfig): StreamingApiClient
export function createApiClient(baseUrl: string, token: string): StreamingApiClient
export function createApiClient(configOrBaseUrl: ApiClientConfig | string, token?: string): StreamingApiClient {
  const config = typeof configOrBaseUrl === 'string'
    ? { baseUrl: configOrBaseUrl, token: token ?? '' }
    : configOrBaseUrl
  const defaultTimeoutMs = config.timeoutMs ?? 10_000
  const streamConnectTimeoutMs = config.streamConnectTimeoutMs ?? 10_000

  async function ensureOk(response: Response): Promise<Response> {
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => undefined)
      const error = parseApiWireError(payload)
      const legacyDetail = response.status === 401 ? '本地服务认证失败' : undefined
      throw new ApiClientError(
        error?.message ?? legacyDetail ?? `API request failed with status ${response.status}`,
        response.status,
        error ?? null,
      )
    }
    return response
  }

  async function authenticatedFetch(
    path: string,
    init: ApiRequestInit = {},
    signal = init.signal,
  ): Promise<Response> {
    const { timeoutMs, body, ...requestInit } = init
    void timeoutMs
    const jsonBody = isJsonBody(body)
    return ensureOk(await fetch(requestUrl(config.baseUrl, path), {
      ...requestInit,
      body: jsonBody ? JSON.stringify(body) : body as BodyInit | null | undefined,
      headers: requestHeaders(init.headers, config.token, jsonBody),
      signal,
    }))
  }

  async function request<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
    const controller = new AbortController()
    const abort = () => controller.abort(init.signal?.reason)
    if (init.signal?.aborted) abort()
    else init.signal?.addEventListener('abort', abort, { once: true })
    const timeoutMs = init.timeoutMs ?? defaultTimeoutMs
    const timer = timeoutMs > 0
      ? window.setTimeout(() => controller.abort(new DOMException('API request timed out', 'TimeoutError')), timeoutMs)
      : undefined

    try {
      const response = await authenticatedFetch(path, init, controller.signal)
      if (response.status === 204) return undefined as T
      return await response.json() as T
    } finally {
      if (timer !== undefined) window.clearTimeout(timer)
      init.signal?.removeEventListener('abort', abort)
    }
  }

  async function stream(path: string, init: RequestInit = {}): Promise<Response> {
    const timeout = new AbortController()
    const timer = window.setTimeout(
      () => timeout.abort(new DOMException('API stream connection timed out', 'TimeoutError')),
      streamConnectTimeoutMs,
    )
    const signal = init.signal
      ? AbortSignal.any([init.signal, timeout.signal])
      : timeout.signal
    try {
      return await authenticatedFetch(path, init, signal)
    } finally {
      window.clearTimeout(timer)
    }
  }

  return {
    request,
    stream,
    health: () => request<HealthResponse>('/health'),
  }
}
