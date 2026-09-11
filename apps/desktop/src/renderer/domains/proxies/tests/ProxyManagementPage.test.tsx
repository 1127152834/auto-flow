import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { ApiClientError, type ApiClient } from '../../../shared/api/client'
import type { ApiError, ConnectionView, GroupPage, GroupView, ProxyPage, ProxyView } from '../api'
import { ProxyManagementPage } from '../pages/ProxyManagementPage'
import { LocalProxyGroupEditor } from '../components/LocalProxyGroups'

afterEach(cleanup)

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
