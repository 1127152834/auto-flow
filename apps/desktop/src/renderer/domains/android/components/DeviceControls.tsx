import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import type { AndroidDevice } from '../api'

export function DeviceSelect({ devices, value, onChange, disabled }: { devices: AndroidDevice[]; value: string; onChange(value: string): void; disabled: boolean }) {
  return <><label htmlFor="android-device" className="text-xs font-medium">安卓设备</label>
    <Select id="android-device" value={value} onChange={event => onChange(event.target.value)} disabled={disabled} className="h-9 w-52">
      <option value="">{devices.length ? '选择安卓设备' : '请先准备安卓设备'}</option>
      {devices.map(device => <option key={device.deviceId} value={device.deviceId} disabled={device.control !== 'idle' || device.androidStatus === 'unknown'}>{device.name} · {device.control === 'idle' ? device.androidStatus === 'stopped' ? '已停止' : '可用' : '已占用或待恢复'}</option>)}
    </Select></>
}

export function DeviceCard({ device, onOpen, disabled = false }: { device: AndroidDevice; onOpen?(): void; disabled?: boolean }) {
  return <article className="rounded-xl border border-line bg-surface p-5 shadow-sm">
    <h2 className="font-semibold">{device.name}</h2><p className="mt-2 text-sm text-muted">{device.width} × {device.height} · {device.androidStatus === 'ready' ? 'Android 已就绪' : device.androidStatus === 'stopped' ? '已停止' : '状态待核实'}</p>
    <p className="mt-3 text-sm">{device.control === 'idle' ? '设备空闲' : device.control === 'recovery_required' ? '需要恢复，请核实遗留操作' : '设备使用中'}</p>
    {device.ownerRunId && <p className="mt-2 break-all text-xs text-muted">运行：{device.ownerRunId}</p>}
    {device.lastError && <p role="alert" className="mt-2 text-sm text-red-700">{device.lastError}</p>}
    <p className="mt-4 text-xs text-muted">在独立窗口中操作 Android，结束后保留设备和数据。</p>
    {onOpen && <Button className="mt-4" variant="primary" disabled={disabled || device.control !== 'idle' || device.androidStatus === 'unknown'} onClick={onOpen}>打开操作窗口</Button>}
  </article>
}
