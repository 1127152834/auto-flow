import type { HealthResponse } from './types'

export type ApiClientConfig = {
  baseUrl: string
  token: string
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null = null,
    readonly details: Record<string, unknown> = {},
    readonly requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiClientError'
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
