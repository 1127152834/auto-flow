import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useApi } from '../../../app/ApiProvider'
import { androidApi } from '../api'
import { DeviceCard } from '../components/DeviceControls'

export function AndroidPage() {
  const { client, instanceId } = useApi()
  const api = useMemo(() => androidApi(client), [client])
  const environment = useQuery({ queryKey: ['android', instanceId, 'environment'], queryFn: api.environment, refetchInterval: 10000 })
  const devices = useQuery({ queryKey: ['android', instanceId, 'devices'], queryFn: api.devices, refetchInterval: 3000 })
  return <main className="mx-auto max-w-6xl px-8 py-8"><p className="text-xs tracking-widest text-muted">AUTOFLOW / ANDROID</p><h1 className="mt-2 text-2xl font-semibold">安卓设备</h1>
    <p className="mt-2 text-sm text-muted">工作流自动执行，人工处理时打开独立的 Mac 操作窗口。</p>
    <p role="status" className="my-5 text-sm">{environment.data?.message ?? '正在检查运行环境…'}</p>
    {(environment.error || devices.error) && <p role="alert">无法读取安卓运行环境，请检查本机服务。</p>}
    {devices.isPending && <p>正在读取设备…</p>}
    {devices.data?.length === 0 && <p className="rounded-xl border border-dashed border-line p-8 text-sm text-muted">尚未登记设备。请先按部署说明准备独立测试设备，再在工作流中选择它。</p>}
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{devices.data?.map(device => <DeviceCard key={device.deviceId} device={devices.isError ? { ...device, androidStatus: 'unknown', lastError: '无法核实当前设备状态' } : device} />)}</div>
  </main>
}
