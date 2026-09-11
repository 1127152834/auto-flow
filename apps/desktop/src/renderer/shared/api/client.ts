import type { HealthResponse } from './types'
import type { components } from './generated'

type ProxyApiError = components['schemas']['ApiError']

export type ApiClientConfig = {
  baseUrl: string
  token: string
}

export class ApiClientError extends Error {
  readonly code: string | null
  readonly details: Record<string, unknown>
  readonly requestId: string | null
  readonly error?: ProxyApiError

  constructor(
    message: string,
    readonly status: number,
    codeOrError: string | ProxyApiError | null = null,
    details: Record<string, unknown> = {},
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.error = typeof codeOrError === 'object' && codeOrError !== null ? codeOrError : undefined
    this.code = this.error?.code ?? (typeof codeOrError === 'string' ? codeOrError : null)
    this.details = details
    this.requestId = this.error?.request_id ?? requestId
  }
}

export type ApiClient = {
  request<T>(path: string, init?: RequestInit): Promise<T>
  health(): Promise<HealthResponse>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requestHeaders(headers: HeadersInit | undefined, token: string): Record<string, string> {
  const values = headers ? Object.fromEntries(new Headers(headers).entries()) : {}
  return { ...values, 'x-autoflow-token': token }
}

function requestUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

export function createApiClient(config: ApiClientConfig): ApiClient
export function createApiClient(baseUrl: string, token: string): ApiClient
export function createApiClient(configOrBaseUrl: ApiClientConfig | string, token?: string): ApiClient {
  const config = typeof configOrBaseUrl === 'string'
    ? { baseUrl: configOrBaseUrl, token: token ?? '' }
    : configOrBaseUrl

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(requestUrl(config.baseUrl, path), {
      ...init,
      headers: requestHeaders(init.headers, config.token),
    })

    if (!response.ok) {
      const fallback = `API request failed with status ${response.status}`
      const body: unknown = await response.json().catch(() => undefined)
      if (isRecord(body) && isRecord(body.error)) {
        const error = body.error
        if (typeof error.code === 'string' && typeof error.message === 'string') {
          if (typeof error.request_id === 'string') {
            throw new ApiClientError(error.message, response.status, {
              code: error.code, message: error.message, request_id: error.request_id,
              field_errors: isRecord(error.field_errors) ? error.field_errors : {},
              retry_after_seconds: typeof error.retry_after_seconds === 'number' && Number.isFinite(error.retry_after_seconds) ? error.retry_after_seconds : null,
              outcome_unknown: error.outcome_unknown === true,
            })
          }
          throw new ApiClientError(
            error.message, response.status, error.code,
            isRecord(error.details) ? error.details : {},
            typeof error.requestId === 'string' ? error.requestId : null,
          )
        }
      }
      throw new ApiClientError(fallback, response.status)
    }

    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }

  return {
    request,
    health: () => request<HealthResponse>('/health'),
  }
}
