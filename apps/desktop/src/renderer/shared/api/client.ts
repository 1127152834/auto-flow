import type { HealthResponse } from './types'
import type { components } from './generated'

export type ApiClientConfig = {
  baseUrl: string
  token: string
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly error?: components['schemas']['ApiError'],
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

export type ApiClient = {
  request<T>(path: string, init?: RequestInit): Promise<T>
  health(): Promise<HealthResponse>
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
      const payload: unknown = await response.json().catch(() => undefined)
      const detail = typeof payload === 'object' && payload !== null && 'error' in payload
        ? payload.error : undefined
      const error = typeof detail === 'object' && detail !== null
        && 'code' in detail && typeof detail.code === 'string'
        && 'message' in detail && typeof detail.message === 'string'
        ? detail as components['schemas']['ApiError'] : undefined
      throw new ApiClientError(error?.message ?? `API request failed with status ${response.status}`, response.status, error)
    }

    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }

  return {
    request,
    health: () => request<HealthResponse>('/health'),
  }
}
