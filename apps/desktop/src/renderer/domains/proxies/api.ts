import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type ApiError = components['schemas']['ApiError']
export type Capability = components['schemas']['Capability']
export type ConnectionView = components['schemas']['ConnectionView']
export type CredentialView = components['schemas']['CredentialView']
export type GroupCreate = components['schemas']['GroupCreate']
export type GroupPage = components['schemas']['GroupPage']
export type GroupReferences = components['schemas']['GroupReferences']
export type GroupUpdate = components['schemas']['GroupUpdate']
export type GroupView = components['schemas']['GroupView']
export type HealthSnapshot = components['schemas']['HealthSnapshot']
export type IpAllowlist = components['schemas']['IpAllowlist']
export type LocationList = components['schemas']['LocationList']
export type ProxyPage = components['schemas']['ProxyPage']
export type ProxyReferences = components['schemas']['ProxyReferences']
export type ProxyUpdate = components['schemas']['ProxyUpdate']
export type ProxyView = components['schemas']['ProxyView']
export type RotationSchedule = components['schemas']['RotationSchedule']
export type ActionResult = components['schemas']['ActionResult']

export type ProxyFilters = {
  q?: string
  carrier?: string
  city?: string
  health?: HealthSnapshot['state'] | ''
  offset?: number
  limit?: number
}

export type GroupDraft = Pick<GroupCreate, 'name' | 'description' | 'member_ids'>
export type ProxyMetadataDraft = Pick<ProxyUpdate, 'name_override' | 'enabled'>

function queryString(values: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  const serialized = query.toString()
  return serialized ? `?${serialized}` : ''
}

function json(body: unknown, idempotent = false): RequestInit {
  return {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(idempotent ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
    },
    body: JSON.stringify(body),
  }
}

export function errorDetail(error: unknown): ApiError | null {
  if (!error || typeof error !== 'object') return null
  const value = error as Record<string, unknown>
  const detail = value.error ?? value.detail
  if (!detail || typeof detail !== 'object') return null
  const candidate = detail as Record<string, unknown>
  if (typeof candidate.code !== 'string' || typeof candidate.message !== 'string') return null
  return detail as ApiError
}

export function errorMessage(error: unknown): string {
  const detail = errorDetail(error)
  if (detail?.retry_after_seconds != null) return `${detail.message}（${detail.retry_after_seconds} 秒后可重试）`
  return detail?.message ?? (error instanceof Error && error.message ? error.message : '请求失败，请稍后重试')
}

export function capability(
  capabilities: Capability[],
  key: string,
): Capability | undefined {
  return capabilities.find((item) => item.key === key)
}

export function createProxyApi(client: ApiClient) {
  const get = <T>(path: string) => client.request<T>(`/api/v1${path}`)
  const send = <T>(path: string, init: RequestInit) => client.request<T>(`/api/v1${path}`, init)

  return {
    async getConnection(): Promise<ConnectionView | null> {
      const result = await get<{ items: ConnectionView[] }>('/proxy-panel/connections')
      return result.items[0] ?? null
    },
    createConnection(name: string, apiKey: string) {
      return send<ConnectionView>('/proxy-panel/connections', json({ name, api_key: apiKey }))
    },
    updateConnection(connection: ConnectionView, name: string) {
      return send<ConnectionView>(`/proxy-panel/connections/${connection.id}`, {
        ...json({ expected_revision: connection.revision, name }),
        method: 'PATCH',
      })
    },
    replaceApiKey(connection: ConnectionView, apiKey: string) {
      return send<ConnectionView>(`/proxy-panel/connections/${connection.id}/api-key`, {
        ...json({ expected_revision: connection.revision, api_key: apiKey }),
        method: 'PUT',
      })
    },
    disconnect(connectionId: string) {
      return send<void>(`/proxy-panel/connections/${connectionId}`, { method: 'DELETE' })
    },
    sync(connectionId: string) {
      return send<ActionResult>(`/proxy-panel/connections/${connectionId}/sync`, json({}, true))
    },
    listProxies(filters: ProxyFilters = {}) {
      return get<ProxyPage>(`/proxies${queryString({
        q: filters.q?.trim(),
        carrier: filters.carrier,
        city: filters.city,
        health: filters.health,
        offset: filters.offset ?? 0,
        limit: filters.limit ?? 50,
      })}`)
    },
    async listAllProxies() {
      const items: ProxyView[] = []
      let offset = 0
      do {
        const page = await get<ProxyPage>(`/proxies${queryString({ offset, limit: 100 })}`)
        items.push(...page.items)
        offset += page.items.length
        if (!page.items.length || items.length >= page.matched_count) break
      } while (true)
      return items
    },
    getProxy(proxyId: string) {
      return get<ProxyView>(`/proxies/${proxyId}`)
    },
    getProxyReferences(proxyId: string) {
      return get<ProxyReferences>(`/proxies/${proxyId}/references`)
    },
    updateProxy(proxy: ProxyView, draft: ProxyMetadataDraft) {
      const body: ProxyUpdate = { expected_revision: proxy.revision, ...draft }
      return send<ProxyView>(`/proxies/${proxy.id}`, { ...json(body), method: 'PATCH' })
    },
    probeProxy(proxyId: string, protocol: 'http' | 'socks5' = 'http') {
      return send<ActionResult>(`/proxies/${proxyId}/probe`, json({ protocol }, true))
    },
    getLocations(connectionId: string, q = '', carrier = '') {
      return get<LocationList>(`/proxy-panel/connections/${connectionId}/locations${queryString({ q, carrier })}`)
    },
    changeIp(proxy: ProxyView) {
      return send<ActionResult>(`/proxies/${proxy.id}/change-ip`, json({ expected_revision: proxy.revision }, true))
    },
    relocate(proxy: ProxyView, locationId: string) {
      return send<ActionResult>(`/proxies/${proxy.id}/relocate`, json({ expected_revision: proxy.revision, location_id: locationId }, true))
    },
    getRotation(proxyId: string) {
      return get<RotationSchedule>(`/proxies/${proxyId}/rotation-schedule`)
    },
    saveRotation(proxy: ProxyView, schedule: RotationSchedule) {
      return send<ActionResult>(`/proxies/${proxy.id}/rotation-schedule`, {
        ...json({ expected_revision: proxy.revision, mode: schedule.mode, interval_seconds: schedule.interval_seconds }, true),
        method: 'PUT',
      })
    },
    getAllowlist(proxyId: string) {
      return get<IpAllowlist>(`/proxies/${proxyId}/ip-auth`)
    },
    saveAllowlist(proxy: ProxyView, allowlist: IpAllowlist) {
      return send<ActionResult>(`/proxies/${proxy.id}/ip-auth`, {
        ...json({ expected_revision: proxy.revision, ...allowlist }, true),
        method: 'PUT',
      })
    },
    getCredentials(proxyId: string) {
      return get<CredentialView>(`/proxies/${proxyId}/credentials`)
    },
    rotateCredentials(proxy: ProxyView) {
      return send<ActionResult>(`/proxies/${proxy.id}/credentials/rotate`, json({ expected_revision: proxy.revision }, true))
    },
    listGroups(q = '') {
      return get<GroupPage>(`/proxy-groups${queryString({ q: q.trim(), offset: 0, limit: 100 })}`)
    },
    createGroup(draft: GroupDraft, acknowledgeRisk = false) {
      return send<GroupView>('/proxy-groups', json({ ...draft, acknowledge_risk: acknowledgeRisk }))
    },
    updateGroup(group: GroupView, draft: GroupDraft, acknowledgeRisk = false) {
      const body: GroupUpdate = {
        ...draft,
        expected_revision: group.revision,
        acknowledge_risk: acknowledgeRisk,
      }
      return send<GroupView>(`/proxy-groups/${group.id}`, { ...json(body), method: 'PUT' })
    },
    deleteGroup(groupId: string) {
      return send<void>(`/proxy-groups/${groupId}`, { method: 'DELETE' })
    },
    getGroupReferences(groupId: string) {
      return get<GroupReferences>(`/proxy-groups/${groupId}/references`)
    },
  }
}

export type ProxyApi = ReturnType<typeof createProxyApi>
