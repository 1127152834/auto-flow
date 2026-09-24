import type { ReactNode } from 'react'
import { ArrowLeft, ArrowSquareOut, FlowArrow } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { DevicePreview } from './DevicePreview'
import { canOpen, deviceStatus } from '../model'
import type { AndroidApi, AndroidDevice } from '../api'

export function DeviceDetails({ device, api, disabled, connected, onBack, onOpen, onStudio, children, history }: { device: AndroidDevice; api: AndroidApi; disabled: boolean; connected: boolean; onBack(): void; onOpen(): void; onStudio(): void; children: ReactNode; history: ReactNode }) {
  const system = device.androidVersion ? `Android ${device.androidVersion}` : 'Android 版本待核实'
  const architecture = device.architecture ?? '架构待核实'
  return <div className="space-y-5"><Button variant="ghost" className="-ml-3 px-3" onClick={onBack}><ArrowLeft size={16} />返回资源看板</Button><header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">{device.name}</h1><p className="mt-2 text-sm text-muted">{system} · {device.width} × {device.height} · {deviceStatus(device)}</p></div><div className="flex gap-3"><Button disabled={!connected} onClick={onStudio}><FlowArrow size={18} />打开工作流工作台</Button><Button variant="primary" disabled={disabled || !canOpen(device)} onClick={onOpen}><ArrowSquareOut size={18} />打开操作窗口</Button></div></header>
    <Tabs defaultValue="overview"><TabsList><TabsTrigger value="overview">控制台</TabsTrigger><TabsTrigger value="environment">环境配置</TabsTrigger><TabsTrigger value="history">运行记录</TabsTrigger></TabsList>
      <TabsContent value="overview"><div className="grid gap-5 lg:grid-cols-[minmax(320px,1.25fr)_1fr]"><section className="rounded-card border border-line bg-surface px-6"><DevicePreview device={device} api={api} enabled={connected} large /></section><section className="space-y-5 rounded-card border border-line bg-surface p-6"><h2 className="font-semibold">设备与控制权</h2><p className="text-sm">{deviceStatus(device)}</p><p className="text-sm text-muted">手动操作会打开独立 Mac 窗口。关掉窗口后，会话仍然保留；点击“结束操作”才会释放占用。</p>{device.lastError && <p role="alert" className="text-sm text-red-700">{device.lastError}</p>}{device.operation && <div className="rounded-control bg-surface-subtle p-4 text-sm"><p>最近设备操作 · {device.operation.stage}</p><p className="mt-2 text-xs text-muted">{new Date(device.operation.startedAt).toLocaleString()}</p></div>}<p className="text-xs text-muted">在工作流工作台中选择此设备即可运行。设备被占用时，其他操作暂不可用，需先结束当前会话。</p>{children}</section></div></TabsContent>
      <TabsContent value="environment"><section className="rounded-card border border-line bg-surface p-6"><h2 className="font-semibold">实例实际配置</h2><p className="my-3 text-sm text-muted">此实例保留创建时的配置。需要其他规格时，请返回看板选择“复制配置”。</p><dl className="grid gap-5 md:grid-cols-2">{[['系统', `${system} · ${architecture}`], ['运行环境', device.runtimeId], ['CPU 配额', String(device.cpu ?? 1)], ['内存', `${device.memoryMb ?? 1536} MiB`], ['显示', `${device.width} × ${device.height} · ${device.dpi ?? 320} DPI`], ['渲染', '软件渲染'], ['数据', device.dataRetained ? '独立数据已保留，运行环境已移除' : '独立持久数据'], ['Root', 'Shell 与应用级能力均未在此实例验证'], ['镜像 ID', device.imageId], ['设备编号', device.deviceId]].map(([label, value]) => <div key={label} className="border-b border-line pb-4"><dt className="text-xs text-muted">{label}</dt><dd className="mt-2 break-all text-sm">{value}</dd></div>)}</dl></section></TabsContent>
      <TabsContent value="history">{history}</TabsContent>
    </Tabs>
  </div>
}
