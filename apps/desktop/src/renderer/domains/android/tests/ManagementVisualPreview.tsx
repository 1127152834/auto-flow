// Development-only visual harness: actual AndroidPage with explicit fixture transport.
// No production entry imports this module; screenshots are not runtime acceptance.
import { createRoot } from 'react-dom/client'
import { ApiProvider } from '../../../app/ApiProvider'
import { ApplicationHeader } from '../../../app/ApplicationHeader'
import { AndroidPage } from '../pages/AndroidPage'
import { PrototypePreview } from './PrototypePreview'
import { devices, environment, profile, images } from './prototype-fixtures'
import type { StreamingApiClient, ApiRequestInit } from '../../../shared/api/client'
import type { ManagementDevicePage } from '../management-api'
import '../../../styles/index.css'
import '../android.css'

const empty = new URLSearchParams(location.search).has('empty')
const records: ManagementDevicePage['items'] = devices.map((device, index) => ({
  deviceId: device.deviceId, revision: 1, name: index === 4 ? '启动设备 05' : device.name,
  runtimeState: device.androidStatus as 'ready' | 'starting' | 'stopped',
  owner: { kind: index === 2 || index === 3 ? 'manualSession' : 'none', id: index === 2 || index === 3 ? `session-${index}` : null },
  observedAt: new Date().toISOString(), stale: false,
  specSnapshot: { ...device, instanceType: 'persistent', ownerRunId: null, control: index === 2 || index === 3 ? 'manual' : 'idle' },
  latestOperation: null,
  allowedActions: index === 2 || index === 3 ? ['return_to_console', 'end_control'] : index === 4 ? [] : index === 5 ? ['start', 'delete'] : ['open', 'stop', 'restart', 'delete'],
  blockedReasons: {}, restoreState: null,
}))
const client: StreamingApiClient = {
  async request<T>(path: string, init?: ApiRequestInit) {
    if (init?.method && init.method !== 'GET') throw new Error('视觉样例不执行设备写入操作')
    let result: unknown
    if (path.includes('/management/devices')) result = { items: empty ? [] : records, total: empty ? 0 : records.length, nextCursor: null }
    else if (path.endsWith('/capabilities')) result = { management: true, control: true, images: true, bulk: true, backups: true, workflow: false, reasons: {} }
    else if (path.endsWith('/environment')) result = { ...environment, checkedAt: '2026-09-30T05:00:00Z', checks: { adb: { status: 'pass', message: 'ADB 可用' }, lima: { status: 'pass', message: '虚拟机运行正常' }, images: { status: 'pass', message: '兼容镜像可用' } }, hostWorkspaceFreeBytes: 180 * 1024 ** 3, vmDockerFreeBytes: 31 * 1024 ** 3 }
    else if (path.endsWith('/profiles')) result = [profile]
    else if (path.endsWith('/cleanup/resources')) result = { items: [] }
    else if (path.includes('/operations?') || path.endsWith('/management/images')) result = { items: [], total: 0, nextCursor: null }
    else if (path.endsWith('/backups')) result = []
    else throw new Error(`Unsupported visual fixture GET: ${path}`)
    return result as T
  },
  async stream(path) {
    const deviceId = devices.find(device => path.includes(device.deviceId))?.deviceId
    if (!deviceId) throw new Error(`Unsupported fixture stream: ${path}`)
    return fetch(images[deviceId])
  },
  async health() { return { status: 'ok', apiVersion: 'v1', instanceId: 'visual-fixture' } },
}
createRoot(document.getElementById('root')!).render(<ApiProvider baseUrl="" token="" instanceId="visual-fixture" client={client}>
  {new URLSearchParams(location.search).get('androidFixture') === 'manual' ? <PrototypePreview /> : <>
    <ApplicationHeader route="android" status="connected" onNavigate={() => {}} />
    <AndroidPage />
  </>}
  <aside style={{ position: 'fixed', right: 8, bottom: 4, fontSize: 10, pointerEvents: 'none', color: '#555' }}>视觉验收样例 · 非真实设备</aside>
</ApiProvider>)
