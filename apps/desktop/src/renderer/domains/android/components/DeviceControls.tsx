import { DotsThree, Play, ArrowSquareOut, LockSimple } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import { canOpen, deviceGroup, deviceStatus } from '../model'
import { DevicePreview } from './DevicePreview'
import type { AndroidApi, AndroidDevice, DeviceCommand } from '../api'

export function DeviceSelect({ devices, value, onChange, disabled }: { devices: AndroidDevice[]; value: string; onChange(value: string): void; disabled: boolean }) {
  return <><label htmlFor="android-device" className="text-xs font-medium">安卓设备</label><Select id="android-device" value={value || null} onValueChange={next => onChange(next ?? '')} disabled={disabled} className="w-52" options={devices.map(device => ({ value: device.deviceId, label: `${device.name} · ${deviceStatus(device)}`, disabled: !canOpen(device) }))} placeholder={devices.length ? '选择安卓设备' : '请先创建安卓设备'} /></>
}
export type DeviceAction = DeviceCommand['action'] | 'rename' | 'copy'
type Props = { device: AndroidDevice; onOpen?(): void; onDetail?(): void; onAction?(action: DeviceAction): void; disabled?: boolean; api?: AndroidApi; previewEnabled?: boolean }
export function DeviceCard({ device, onOpen, onDetail, onAction, disabled = false, api, previewEnabled = true }: Props) {
  const idle = device.control === 'idle'
  const tone = deviceGroup(device) === '可分配' ? 'bg-sage-soft text-sage-strong' : deviceGroup(device) === '使用中' ? 'bg-clay-soft text-clay' : 'bg-surface-subtle text-muted'
  return <article className="rounded-control border border-line bg-surface p-4" aria-label={device.name}>
    <div className="flex items-start gap-4">
      {api && <DevicePreview device={device} api={api} enabled={previewEnabled} />}
      <div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-2"><h3 className="break-words text-base font-semibold">{device.name}</h3>{onAction && <DropdownMenu><DropdownMenuTrigger asChild><Button className="-mt-2 -mr-2 h-8 w-8 shrink-0 p-0" variant="ghost" aria-label={`${device.name}的更多操作`}><DotsThree size={22} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem disabled={disabled || !idle} onSelect={() => onAction('rename')}>重命名</DropdownMenuItem>
<DropdownMenuItem onSelect={() => onAction('copy')}>复制配置</DropdownMenuItem>
<DropdownMenuItem disabled={disabled || !idle || !['ready', 'starting'].includes(device.androidStatus)} onSelect={() => onAction('stop')}>停止设备</DropdownMenuItem>
<DropdownMenuItem disabled={disabled || !idle || device.dataRetained} onSelect={() => onAction('restart')}>重启设备</DropdownMenuItem>
<DropdownMenuItem disabled={disabled || device.control !== 'recovery_required'} onSelect={() => onAction('recover')}>核实状态</DropdownMenuItem>
<DropdownMenuItem onSelect={onDetail}>查看详情</DropdownMenuItem>
<DropdownMenuItem disabled={disabled || !idle || device.androidStatus === 'ready'} onSelect={() => onAction('start')}>{device.dataRetained ? '恢复实例' : '启动设备'}</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled={disabled || !idle} className="text-red-700" onSelect={() => onAction('delete')}>删除实例…</DropdownMenuItem></DropdownMenuContent></DropdownMenu>}</div>
        <p className="mt-2 text-sm text-muted">Android {device.androidVersion ?? '13'} · {device.width} × {device.height}</p>
        <div className="mt-3 flex flex-wrap gap-2"><span className={`rounded-full px-2.5 py-1 text-xs ${tone}`}>{deviceStatus(device)}</span><span className="rounded-full bg-clay-soft px-2.5 py-1 text-xs text-clay">持久实例</span></div>
        <p className="mt-3 text-xs text-muted">{device.ownerRunId ? <><LockSimple size={12} className="mr-1 inline" />独占使用 · 查看详情处理运行</> : device.dataRetained ? '应用和数据已保留，可恢复运行环境。' : `${device.cpu ?? 1} CPU · ${device.memoryMb ?? 1536} MiB · ARM64`}</p>
      </div>
    </div>
    {device.lastError && <p role="alert" className="mt-3 text-xs text-red-700">{device.lastError}</p>}
    <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-3">
      {device.control === 'recovery_required' && onAction ? <Button className="h-9 text-sm" disabled={disabled} onClick={() => onAction('recover')}>核实状态</Button> : idle && ['stopped', 'retained', 'missing'].includes(device.androidStatus) && onAction ? <Button className="h-9 text-sm" variant="primary" disabled={disabled} onClick={() => onAction('start')}><Play size={14} />{device.dataRetained ? '恢复实例' : '启动设备'}</Button> : onOpen && <Button className="h-9 text-sm" variant="primary" disabled={disabled || !canOpen(device)} onClick={onOpen}><ArrowSquareOut size={14} />打开操作窗口</Button>}
      {onDetail && <Button className="h-9 text-sm" onClick={onDetail}>查看详情</Button>}
    </div>
  </article>
}
