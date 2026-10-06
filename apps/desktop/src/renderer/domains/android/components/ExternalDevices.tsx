import { useQuery } from '@tanstack/react-query'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { EmptyState } from '../../../shared/components/ui/empty-state'
import type { AiTestApi } from '../ai-test-api'

const stateText = (state: string) => state === 'device' ? '可用' : state === 'offline' ? '离线' : state === 'unauthorized' ? '未授权' : `不可用（${state}）`

export function ExternalDevices({ api, onSelect }: { api: AiTestApi; onSelect: (serial: string) => void }) {
  const query = useQuery({ queryKey: ['android', 'external-devices'], queryFn: () => api.externalDevices(), gcTime: 0 })
  const devices = query.data ?? []
  return (
    <section className="space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="m-0 text-xl font-semibold text-ink">外接设备</h1>
          <p className="m-0 text-sm text-muted">外接设备可能同时被其他程序操作</p>
        </div>
        <Button onClick={() => void query.refetch()} loading={query.isFetching} loadingText="刷新中">刷新</Button>
      </header>
      {query.isError ? <p role="alert" className="m-0 text-sm text-danger">{query.error instanceof Error && query.error.message ? query.error.message : '无法读取外接设备'}</p>
        : query.isPending ? <p role="status" className="m-0 text-sm text-muted">正在读取外接设备…</p>
        : devices.length === 0 ? <EmptyState title="没有外接设备" description="启动模拟器或连接设备后点击刷新；由 AutoFlow 创建的设备不在此列出" />
        : <ul className="m-0 grid list-none gap-2 p-0">
          {devices.map((device) => (
            <li key={device.serial} className="flex items-center justify-between gap-4 rounded-control border border-line p-3">
              <div className="grid gap-1">
                <strong className="text-sm text-ink">{device.model || device.product || '未知型号'}</strong>
                <span className="text-xs text-muted">{device.serial}</span>
                {device.state === 'unauthorized' && <span className="text-xs text-muted">请在设备上允许 USB 调试</span>}
              </div>
              <div className="flex items-center gap-3">
                <Badge>{stateText(device.state)}</Badge>
                <Button size="sm" disabled={device.state !== 'device'} onClick={() => onSelect(device.serial)} aria-label={`选择 ${device.serial}`}>选择</Button>
              </div>
            </li>
          ))}
        </ul>}
    </section>
  )
}
