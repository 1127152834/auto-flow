import { afterEach, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { ApiClientError, type ApiClient } from '../../../shared/api/client'
import type { ApiError, ConnectionView, GroupPage, GroupView, ProxyPage, ProxyView } from '../api'
import { ProxyManagementPage } from '../pages/ProxyManagementPage'
import { LocalProxyGroupEditor } from '../components/LocalProxyGroups'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const connection: ConnectionView = {
  id: 'connection-1',
  name: 'ProxyPanel 主连接',
  has_secret: true,
  status: 'connected',
  revision: 1,
  last_verified_at: '2026-09-12T01:00:00Z',
  last_synced_at: '2026-09-12T01:01:00Z',
  last_error: null,
  capabilities: [],
}

function proxy(id: string, name: string, state: ProxyView['health']['state'] = 'healthy'): ProxyView {
  return {
    id,
    connection_id: connection.id,
    name,
    name_override: null,
    enabled: true,
    remote_status: null,
    remote_missing: false,
    carrier: 'Verizon',
    city: 'Dallas',
    region: 'Texas, US',
    exit_ip: '174.56.12.34',
    http_endpoint: { host: '174.56.12.34', port: 8080 },
    socks5_endpoint: { host: '174.56.12.34', port: 1080 },
    credential_available: true,
    health: {
      state,
      latency_ms: state === 'healthy' ? 68 : null,
      exit_ip: state === 'healthy' ? '174.56.12.34' : null,
      checked_at: '2026-09-12T01:02:00Z',
      source: 'local_probe',
      error: null,
    },
    subscription_expires_at: null,
    last_synced_at: '2026-09-12T01:01:00Z',
    stale: false,
    revision: 1,
    reference_count: 2,
    capabilities: [
      { key: 'change_ip', available: false, evidence: 'unknown', reason: '真实响应尚未核验', constraints: {} },
      { key: 'relocate', available: false, evidence: 'unknown', reason: '真实响应尚未核验', constraints: {} },
    ],
  }
}

const proxies: ProxyPage = { items: [proxy('proxy-1', 'Dallas Verizon')], offset: 0, limit: 50, matched_count: 1 }
const groups: GroupPage = { items: [], offset: 0, limit: 100, matched_count: 0 }

function client(handler: (path: string, init?: RequestInit) => unknown): ApiClient {
  return {
    request: async <T,>(path: string, init?: RequestInit) => handler(path, init) as T,
    health: async () => ({ status: 'ok', apiVersion: 'v1', instanceId: 'test' }),
  }
}

function connectedClient(): ApiClient {
  return client((path) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [connection] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    if (path.startsWith('/api/v1/proxies?')) return proxies
    if (path === '/api/v1/proxies/proxy-1') return proxies.items[0]
    if (path === '/api/v1/proxies/proxy-1/references') return { profiles: [{ id: 'profile-1', name: '采集任务' }], groups: [] }
    throw new Error(`Unexpected request: ${path}`)
  })
}

it('shows a connection empty state without fabricated proxy metrics', async () => {
  render(<ProxyManagementPage api={client((path) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    throw new Error(`Unexpected request: ${path}`)
  })} />)

  expect(await screen.findByRole('button', { name: '连接 ProxyPanel' })).toBeInTheDocument()
  expect(screen.queryByLabelText('代理摘要')).not.toBeInTheDocument()
  expect(screen.queryByText('即将到期')).not.toBeInTheDocument()
})

it('loads proxies, opens the detail drawer, and keeps unverified writes disabled', async () => {
  const user = userEvent.setup()
  render(<ProxyManagementPage api={connectedClient()} />)

  expect(await screen.findByText('Dallas Verizon')).toBeInTheDocument()
  expect(screen.getByText('当前页健康')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '详情' }))
  const drawer = await screen.findByRole('dialog', { name: 'Dallas Verizon' })
  expect(within(drawer).getByText('AutoFlow 本地 HTTPS 探测')).toBeInTheDocument()
  await user.click(within(drawer).getByRole('tab', { name: '位置与轮换' }))
  expect(within(drawer).getByRole('button', { name: '更换 IP' })).toBeDisabled()
  expect(within(drawer).getByRole('button', { name: '改变地点' })).toBeDisabled()
  expect(within(drawer).getByText('真实响应尚未核验')).toBeInTheDocument()
  expect(within(drawer).queryByText('丢包')).not.toBeInTheDocument()
})

it('clears a submitted API key and shows the structured API error', async () => {
  const user = userEvent.setup()
  const error: ApiError = {
    code: 'PROXYPANEL_AUTH_FAILED',
    message: 'API Key 无效',
    request_id: 'request-1',
    field_errors: {},
    retry_after_seconds: null,
    outcome_unknown: false,
  }
  render(<ProxyManagementPage api={client((path, init) => {
    if (path === '/api/v1/proxy-panel/connections' && init?.method === 'POST') throw new ApiClientError(error.message, 502, error)
    if (path === '/api/v1/proxy-panel/connections') return { items: [] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    throw new Error(`Unexpected request: ${path}`)
  })} />)

  await user.click(await screen.findByRole('button', { name: '连接 ProxyPanel' }))
  const key = screen.getByLabelText('API Key')
  await user.type(key, 'secret-that-must-be-cleared')
  await user.click(screen.getByRole('button', { name: '验证并连接' }))
  expect(await screen.findByText('API Key 无效')).toBeInTheDocument()
  await waitFor(() => expect(key).toHaveValue(''))
})

it('preserves ordered members and requires an explicit risk acknowledgement', async () => {
  const user = userEvent.setup()
  const first = proxy('proxy-1', 'Dallas Verizon')
  const second = proxy('proxy-2', 'Miami AT&T', 'untested')
  const group: GroupView = {
    id: 'group-1',
    name: '美国移动组',
    description: '',
    member_ids: [first.id, second.id],
    revision: 2,
    reference_count: 0,
    created_at: '2026-09-12T01:00:00Z',
    updated_at: '2026-09-12T01:00:00Z',
  }
  const onSubmit = vi.fn(async () => undefined)
  render(<LocalProxyGroupEditor open group={group} proxies={[first, second]} busy={false} error="包含未检测成员" riskRequired onOpenChange={() => undefined} onSubmit={onSubmit} />)

  await user.click(screen.getByRole('button', { name: '下移 Dallas Verizon' }))
  await user.click(screen.getByRole('button', { name: '了解风险并保存' }))
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ member_ids: [second.id, first.id] }), true)
})

it('keeps a missing group member visible so it can be removed before saving', async () => {
  const user = userEvent.setup()
  const group: GroupView = {
    id: 'group-missing',
    name: '待清理代理组',
    description: '',
    member_ids: ['missing-proxy'],
    revision: 1,
    reference_count: 0,
    created_at: '2026-09-12T01:00:00Z',
    updated_at: '2026-09-12T01:00:00Z',
  }
  const onSubmit = vi.fn(async () => undefined)
  render(<LocalProxyGroupEditor open group={group} proxies={[]} busy={false} riskRequired={false} onOpenChange={() => undefined} onSubmit={onSubmit} />)

  expect(screen.getByText('已失效代理')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '移除 已失效代理' }))
  await user.click(screen.getByRole('button', { name: '保存代理组' }))
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ member_ids: [] }), false)
})

it('keeps the group draft and resubmits the same version after a server risk response', async () => {
  const user = userEvent.setup()
  const risky = proxy('proxy-2', 'Miami AT&T', 'untested')
  const group: GroupView = {
    id: 'group-1',
    name: '美国移动组',
    description: '',
    member_ids: [risky.id],
    revision: 2,
    reference_count: 0,
    created_at: '2026-09-12T01:00:00Z',
    updated_at: '2026-09-12T01:00:00Z',
  }
  const acknowledgements: boolean[] = []
  const riskError: ApiError = {
    code: 'PROXY_MEMBER_RISK_CONFIRMATION_REQUIRED',
    message: '组内包含未检测成员',
    request_id: 'request-risk',
    field_errors: { member_ids: risky.id },
    retry_after_seconds: null,
    outcome_unknown: false,
  }
  render(<ProxyManagementPage api={client((path, init) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [connection] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return { ...groups, items: [group], matched_count: 1 }
    if (path.startsWith('/api/v1/proxies?')) return { ...proxies, items: [risky] }
    if (path === `/api/v1/proxy-groups/${group.id}` && init?.method === 'PUT') {
      const body = JSON.parse(String(init.body)) as { acknowledge_risk: boolean; expected_revision: number }
      acknowledgements.push(body.acknowledge_risk)
      expect(body.expected_revision).toBe(group.revision)
      if (!body.acknowledge_risk) throw new ApiClientError(riskError.message, 409, riskError)
      return group
    }
    throw new Error(`Unexpected request: ${path}`)
  })} />)

  await user.click(await screen.findByRole('button', { name: '编辑' }))
  await user.click(screen.getByRole('button', { name: '保存代理组' }))
  expect(await screen.findByText('组内包含未检测成员')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '了解风险并保存' }))
  await waitFor(() => expect(acknowledgements).toEqual([false, true]))
})

it('keeps a saved connection when its first sync is unavailable', async () => {
  const user = userEvent.setup()
  let saved = false
  const syncError: ApiError = {
    code: 'PROXYPANEL_SCHEMA_UNSUPPORTED',
    message: '响应结构尚未核验',
    request_id: 'request-sync',
    field_errors: {},
    retry_after_seconds: null,
    outcome_unknown: false,
  }
  render(<ProxyManagementPage api={client((path, init) => {
    if (path === '/api/v1/proxy-panel/connections' && init?.method === 'POST') {
      saved = true
      return { ...connection, name: 'ProxyPanel' }
    }
    if (path === `/api/v1/proxy-panel/connections/${connection.id}/sync`) throw new ApiClientError(syncError.message, 502, syncError)
    if (path === '/api/v1/proxy-panel/connections') return { items: saved ? [connection] : [] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    if (path.startsWith('/api/v1/proxies?')) return proxies
    throw new Error(`Unexpected request: ${path}`)
  })} />)

  await user.click(await screen.findByRole('button', { name: '连接 ProxyPanel' }))
  await user.type(screen.getByLabelText('API Key'), 'stored-before-sync')
  await user.click(screen.getByRole('button', { name: '验证并连接' }))
  expect(await screen.findByText(/连接已保存，代理同步暂不可用：响应结构尚未核验/)).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '连接 ProxyPanel' })).not.toBeInTheDocument()
  expect(screen.getByText('ProxyPanel 主连接')).toBeInTheDocument()
})

it('ignores a late detail response, then updates metadata and copies through the bridge', async () => {
  const user = userEvent.setup()
  let resolveFirst: ((value: ProxyView) => void) | undefined
  let detailCalls = 0
  let updateBody: { expected_revision: number; name_override: string | null; enabled: boolean | null } | undefined
  const copy = vi.fn(async () => ({ copied: true as const }))
  vi.stubGlobal('autoflow', {
    getSidecarStatus: vi.fn(),
    restartSidecar: vi.fn(),
    copyProxyCredentials: copy,
  })
  render(<ProxyManagementPage api={client((path, init) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [connection] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    if (path.startsWith('/api/v1/proxies?')) return proxies
    if (path === '/api/v1/proxies/proxy-1' && init?.method === 'PATCH') {
      updateBody = JSON.parse(String(init.body)) as typeof updateBody
      return { ...proxies.items[0], name_override: '工作代理', enabled: false, revision: 2 }
    }
    if (path === '/api/v1/proxies/proxy-1') {
      detailCalls += 1
      if (detailCalls === 1) return new Promise<ProxyView>((resolve) => { resolveFirst = resolve })
      return proxies.items[0]
    }
    if (path === '/api/v1/proxies/proxy-1/references') return { profiles: [], groups: [] }
    throw new Error(`Unexpected request: ${path}`)
  })} />)

  await user.click((await screen.findAllByRole('button', { name: '详情' }))[0])
  await user.click(await screen.findByRole('button', { name: '关闭代理详情' }))
  await act(async () => { resolveFirst?.(proxies.items[0]) })
  expect(screen.queryByRole('dialog', { name: 'Dallas Verizon' })).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '详情' }))
  const drawer = await screen.findByRole('dialog', { name: 'Dallas Verizon' })
  await user.clear(within(drawer).getByLabelText('显示名称'))
  await user.type(within(drawer).getByLabelText('显示名称'), '工作代理')
  await user.click(within(drawer).getByRole('switch', { name: '启用此代理' }))
  await user.click(within(drawer).getByRole('button', { name: '保存本地设置' }))
  await waitFor(() => expect(updateBody).toEqual({ expected_revision: 1, name_override: '工作代理', enabled: false }))
  await user.click(within(drawer).getByRole('tab', { name: '凭据与白名单' }))
  await user.click(within(drawer).getByRole('button', { name: '复制用户名' }))
  expect(copy).toHaveBeenCalledWith({ proxyId: 'proxy-1', protocol: 'socks5', format: 'username' })
})

it('probes SOCKS5 when it is the only available endpoint', async () => {
  const user = userEvent.setup()
  const socksOnly = { ...proxies.items[0], http_endpoint: null }
  let requestedProtocol: string | undefined
  render(<ProxyManagementPage api={client((path, init) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [connection] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    if (path.startsWith('/api/v1/proxies?')) return { ...proxies, items: [socksOnly] }
    if (path === '/api/v1/proxies/proxy-1/probe') {
      requestedProtocol = (JSON.parse(String(init?.body)) as { protocol: string }).protocol
      return { status: 'completed', operation_id: null, resource: socksOnly.health, error: null }
    }
    if (path === '/api/v1/proxies/proxy-1') return socksOnly
    throw new Error(`Unexpected request: ${path}`)
  })} />)

  await user.click(await screen.findByRole('button', { name: '检测' }))
  await waitFor(() => expect(requestedProtocol).toBe('socks5'))
})

it('marks stale projections and attempts one background sync for an expired connection', async () => {
  const expiredConnection = {
    ...connection,
    last_synced_at: new Date(Date.now() - 6 * 60_000).toISOString(),
  }
  const staleProxy = { ...proxies.items[0], stale: true }
  const syncError: ApiError = {
    code: 'PROXYPANEL_UNAVAILABLE',
    message: 'ProxyPanel 暂不可用',
    request_id: 'request-auto-sync',
    field_errors: {},
    retry_after_seconds: null,
    outcome_unknown: false,
  }
  let syncCalls = 0

  render(
    <StrictMode>
      <ProxyManagementPage api={client((path) => {
        if (path === '/api/v1/proxy-panel/connections') return { items: [expiredConnection] }
        if (path === `/api/v1/proxy-panel/connections/${connection.id}/sync`) {
          syncCalls += 1
          throw new ApiClientError(syncError.message, 503, syncError)
        }
        if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
        if (path.startsWith('/api/v1/proxies?')) return { ...proxies, items: [staleProxy] }
        throw new Error(`Unexpected request: ${path}`)
      })} />
    </StrictMode>,
  )

  expect(await screen.findByText('待同步')).toBeInTheDocument()
  await waitFor(() => expect(syncCalls).toBe(1))
  expect(screen.getByText('Dallas Verizon')).toBeInTheDocument()
  expect(await screen.findByText(/ProxyPanel 暂不可用。已加载的数据会继续保留/)).toBeInTheDocument()
  expect(syncCalls).toBe(1)
})

it('can retry a saved failed connection and clears its old sync error after recovery', async () => {
  const user = userEvent.setup()
  let recovered = false
  let attempts = 0
  const failure: ApiError = { code: 'PROXYPANEL_SCHEMA_UNSUPPORTED', message: '旧同步错误', request_id: 'old', field_errors: {}, retry_after_seconds: null, outcome_unknown: false }
  render(<ProxyManagementPage api={client((path) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [{ ...connection, status: recovered ? 'connected' : 'failed', last_synced_at: recovered ? new Date().toISOString() : null, last_error: recovered ? null : failure }] }
    if (path === `/api/v1/proxy-panel/connections/${connection.id}/sync`) {
      attempts += 1
      if (attempts === 1) throw new ApiClientError(failure.message, 502, failure)
      recovered = true
      return { status: 'completed', resource: {} }
    }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    if (path.startsWith('/api/v1/proxies?')) return recovered ? proxies : { ...proxies, items: [], matched_count: 0 }
    throw new Error(`Unexpected request: ${path}`)
  })} />)
  const retry = await screen.findByRole('button', { name: '刷新代理' })
  expect(retry).toBeEnabled()
  await user.click(retry)
  await waitFor(() => expect(attempts).toBe(1))
  await waitFor(() => expect(retry).toBeEnabled())
  await user.click(retry)
  expect(await screen.findByText('Dallas Verizon')).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByText(/已加载的数据会继续保留/)).not.toBeInTheDocument())
  expect(attempts).toBe(2)
})

it('uses the explicitly selected probe protocol without falling back silently', async () => {
  const user = userEvent.setup()
  const protocols: string[] = []
  render(<ProxyManagementPage api={client((path, init) => {
    if (path === '/api/v1/proxy-panel/connections') return { items: [{ ...connection, last_synced_at: new Date().toISOString() }] }
    if (path === '/api/v1/proxy-groups?offset=0&limit=100') return groups
    if (path.startsWith('/api/v1/proxies?')) return proxies
    if (path === '/api/v1/proxies/proxy-1') return proxies.items[0]
    if (path === '/api/v1/proxies/proxy-1/references') return { profiles: [], groups: [] }
    if (path === '/api/v1/proxies/proxy-1/probe') {
      protocols.push(JSON.parse(String(init?.body)).protocol)
      return { status: 'completed', resource: {} }
    }
    throw new Error(`Unexpected request: ${path}`)
  })} />)
  await user.click(await screen.findByRole('button', { name: '详情' }))
  const drawer = await screen.findByRole('dialog', { name: 'Dallas Verizon' })
  const select = within(drawer).getByRole('combobox', { name: '检测协议' })
  expect(select).toHaveValue('socks5')
  await user.selectOptions(select, 'http')
  await user.click(within(drawer).getByRole('button', { name: '测试连接' }))
  await waitFor(() => expect(protocols).toEqual(['http']))
  expect(select).toHaveValue('http')
})
