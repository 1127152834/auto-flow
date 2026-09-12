import type {ConnectionView,ProxyView,ProxyPage,GroupPage} from '../../src/renderer/domains/proxies/api'
export const connection: ConnectionView = {
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
    exit_ip: '192.0.2.10',
    http_endpoint: { host: '192.0.2.10', port: 8080 },
    socks5_endpoint: { host: '192.0.2.10', port: 1080 },
    credential_available: true,
    health: {
      state,
      latency_ms: state === 'healthy' ? 68 : null,
      exit_ip: state === 'healthy' ? '192.0.2.10' : null,
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

export const proxies: ProxyPage = { items: [proxy('proxy-1', 'Dallas Verizon')], offset: 0, limit: 50, matched_count: 1 }
export const groups: GroupPage = { items: [], offset: 0, limit: 100, matched_count: 0 }

