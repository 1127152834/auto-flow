import { ArrowRight, DotsThree, GearSix, Info, LockKey, Plus, SpinnerGap } from '@phosphor-icons/react'
import { useState } from 'react'
import type { AndroidDevice } from '../api'
import type { Allocation, Batch, DeviceRun, Profile } from '../fleet-api'
import { Action, Badge, Dot } from './PrototypeControls'
import { DevicePreview } from './DevicePreview'
import type { AndroidApi } from '../api'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
export type BoardProps = {
  devices: AndroidDevice[]
  profiles: Profile[]
  allocations: Allocation[]
  batches: Batch[]
  runs: Record<string, DeviceRun | undefined>
  api?: AndroidApi
  images?: Record<string, string>
  onCreate(): void
  onProfiles(): void
  onOpen(d: AndroidDevice): void
  onAllocate(d?: AndroidDevice): void
  onManage(d: AndroidDevice, action: string): void
  onRuns(): void
  onBatch(id: string, action: 'retry' | 'cancel'): void
  onCancelAllocation?(id: string): void
  managementMode?: boolean
}
const group = (d: AndroidDevice) =>
  d.control === 'managing' || d.control === 'recovery_required'
    ? 2
    : d.control !== 'idle' || d.ownerRunId
      ? 1
      : d.androidStatus === 'ready'
        ? 0
        : 2
export function ResourceBoard(p: BoardProps) {
  const [view, setView] = useState('board'),
    [environment, setEnvironment] = useState('')
  const [menu, setMenu] = useState<string | null>(null)
  const visible = p.devices.filter((d) => !environment || d.profileId === environment)
  const waiting = p.allocations.filter(
    (a) => !['running', 'cleaning', 'succeeded', 'failed', 'cancelled'].includes(a.state),
  )
  const card = (d: AndroidDevice) => {
    const g = group(d),
      run = p.runs[d.deviceId],
      temporary = d.instanceType === 'temporary'
    const starting = d.androidStatus === 'starting' || d.control === 'managing'
    return (
      <article className={`ad-device-card ad-card-${g}`} key={d.deviceId}>
        <div className="ad-card-phone">
          {p.images?.[d.deviceId] ? (
            <img src={p.images[d.deviceId]} alt={`${d.name}画面`} />
          ) : p.api ? (
            <DevicePreview api={p.api} device={d} enabled={d.androidStatus === 'ready'} />
          ) : null}
        </div>
        <div className="ad-card-content">
          <div className="ad-card-title">
            <button onClick={() => p.onOpen(d)}>{d.name}</button>
            <Badge tone={g === 0 ? 'green' : starting ? 'blue' : 'gray'}>
              {g === 0
                ? '已就绪'
                : g === 1
                  ? temporary
                    ? '临时实例'
                    : '持久实例'
                  : starting
                    ? '启动中'
                    : d.control === 'recovery_required'
                      ? '需要核实'
                      : '已停止'}
            </Badge>
          </div>
          <p className="ad-spec">
            {d.androidVersion ? `Android ${d.androidVersion}` : 'Android 版本待核实'} · {d.width} × {d.height} · {d.architecture ?? '架构待核实'}
          </p>
          {g !== 1 && !starting && <Badge tone="brown">{temporary ? '临时实例' : '持久实例'}</Badge>}
          {g === 1 ? (
            <>
              <p className="ad-workflow">{p.managementMode ? '手动控制中' : run ? `工作流：${run.workflowName}` : '手动控制中'}</p>
              <p className="ad-step">
                {run
                  ? `当前步骤：${run.steps[Math.max(0, run.currentStep - 1)]?.label ?? '等待执行'} · ${run.currentStep}/${run.totalSteps}`
                  : '设备由你独占操作'}
              </p>
              <progress value={run?.currentStep ?? 0} max={run?.totalSteps || 1} />
              <p className="ad-lock">
                <LockKey size={17} weight="fill" />
                独占使用 · 只读预览
              </p>
            </>
          ) : g === 2 ? (
            <div className="ad-device-state">
              {starting ? (
                <>
                  <strong>
                    <SpinnerGap className="ad-spin" size={21} />
                    等待 Android 就绪…
                  </strong>
                  <p>就绪后可分配任务。</p>
                </>
              ) : (
                <p>{d.lastError ?? '数据已保留'}</p>
              )}
            </div>
          ) : null}
        </div>
        <div className="ad-more">
          <button aria-label={`${d.name}更多操作`} onClick={() => setMenu(menu === d.deviceId ? null : d.deviceId)}>
            <DotsThree size={23} />
          </button>
          {menu === d.deviceId && (
            <div className="ad-menu">
              {[
                ['copy', '复制配置'],
                ['rename', '重命名'],
                ['restart', '重启设备'],
                ['stop', '停止设备'],
                ['recover', '核实状态'],
                ['delete', '删除实例'],
              ].map(([a, label]) => (
                <button
                  key={a}
                  onClick={() => {
                    setMenu(null)
                    p.onManage(d, a)
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="ad-card-actions">
          {g === 0 ? (
            <>
              {!p.managementMode && <Action primary onClick={() => p.onAllocate(d)}>分配给工作流</Action>}
              <Action onClick={() => p.onOpen(d)}>打开设备</Action>
            </>
          ) : g === 1 ? (
            <>
              <Action primary onClick={() => p.onOpen(d)}>
                查看运行
              </Action>
              <Action onClick={() => p.onOpen(d)}>预览</Action>
              <span>{temporary ? '完成后自动清理' : '完成后保留数据'}</span>
            </>
          ) : (
            <Action
              onClick={() => (starting || d.control === 'recovery_required' ? p.onOpen(d) : p.onManage(d, 'start'))}
            >
              {starting || d.control === 'recovery_required' ? '查看详情' : '启动设备'}
            </Action>
          )}
        </div>
      </article>
    )
  }
  return (
    <main className="ad-page ad-board-page">
      <header className="ad-page-heading">
        <div>
          <h1>{p.managementMode ? '安卓设备' : '安卓模拟器'}</h1>
          <p>{p.managementMode ? '管理本机安卓实例、应用与数据。' : '按工作流分配设备，跟踪运行与回收。'}</p>
        </div>
        <div>
          <Action onClick={p.onProfiles}>
            <GearSix size={19} />
            环境配置
          </Action>
          <Action primary onClick={p.onCreate}>
            <Plus size={19} />
            创建实例
          </Action>
        </div>
      </header>
      <section className="ad-board">
        <div className="ad-board-toolbar">
          <div className="ad-segments">
            <Action primary={view === 'list'} onClick={() => setView('list')}>
              实例列表
            </Action>
            <Action primary={view === 'board'} onClick={() => setView('board')}>
              资源看板
            </Action>
          </div>
          <span>
            {p.devices.length} 台设备 · {p.devices.filter((d) => group(d) === 0).length} 台可分配
          </span>
          <select aria-label="全部环境" value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            <option value="">全部环境</option>
            {p.profiles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </div>
        {view === 'board' ? (
          <div className="ad-columns">
            {(p.managementMode ? ['可操作', '手动控制', '启动与停止'] : ['可分配', '工作流占用', '启动与停止']).map((title, i) => (
              <section className="ad-column" key={title}>
                <h2>
                  <Dot tone={['green', 'brown', 'gray'][i]} />
                  {title}
                  <span>{visible.filter((d) => group(d) === i).length}</span>
                </h2>
                <div className="ad-column-cards">
                  {visible.filter((d) => group(d) === i).map(card)}
                  {!visible.some((d) => group(d) === i) && <p className="ad-empty">暂无{title}设备</p>}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <TableScroll label="安卓实例列表" className="ad-instance-list">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>实例名称</TableHead>
                  <TableHead>环境</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>数据策略</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((d) => (
                  <TableRow key={d.deviceId}>
                    <TableCell>
                      <button className="ad-link" onClick={() => p.onOpen(d)}>
                        {d.name}
                      </button>
                    </TableCell>
                    <TableCell>
                      {d.profileName} · {d.width} × {d.height}
                    </TableCell>
                    <TableCell>{['可分配', '使用中', d.lastError ? '需要核实' : '启动与停止'][group(d)]}</TableCell>
                    <TableCell>{d.instanceType === 'temporary' ? '临时实例' : '持久实例'}</TableCell>
                    <TableCell>
                      <Action onClick={() => p.onOpen(d)}>打开设备</Action>
                      {!p.managementMode && <Action disabled={group(d) !== 0} onClick={() => p.onAllocate(d)}>分配工作流</Action>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableScroll>
        )}
      </section>
      {!p.managementMode && <section className="ad-waiting">
        <header>
          <h2>
            等待设备的任务 <span>{waiting.length}</span>
          </h2>
          <button onClick={p.onRuns}>
            查看全部运行 <ArrowRight size={18} />
          </button>
        </header>
        <TableScroll label="等待设备的任务">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>工作流</TableHead>
              <TableHead>所需环境</TableHead>
              <TableHead>分配方式</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {waiting.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.workflowName}</TableCell>
                <TableCell>{item.profileName}</TableCell>
                <TableCell>
                  {item.request.mode === 'temporary'
                    ? '新建临时实例'
                    : item.request.mode === 'automatic'
                      ? '自动分配'
                      : `指定${item.deviceName ?? '设备'}`}
                </TableCell>
                <TableCell>
                  <Dot tone="amber" />
                  {item.state === 'waiting_start' || item.state === 'starting'
                    ? '等待启动'
                    : item.state === 'waiting_capacity'
                      ? '等待容量'
                      : item.state === 'waiting_device'
                        ? '等待设备'
                        : '等待创建'}
                  {p.onCancelAllocation && (
                    <button
                      className="ad-cancel-allocation"
                      aria-label={`取消${item.workflowName}等待`}
                      onClick={() => p.onCancelAllocation?.(item.id)}
                    >
                      取消
                    </button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!waiting.length && (
              <TableRow>
                <TableCell colSpan={4} className="ad-empty">
                  暂无等待任务 <button onClick={() => p.onAllocate()}>分配工作流</button>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        </TableScroll>
        <p>
          <Info size={16} />
          工作流运行期间独占设备；释放持久实例时保留数据。
        </p>
      </section>}
      {!p.managementMode && p.batches
        .filter((b) => b.state !== 'succeeded' && b.state !== 'cancelled')
        .map((b) => (
          <section className="ad-batch" key={b.id}>
            <h2>{b.request.name} · 创建进度</h2>
            {b.items.map((i) => (
              <p key={i.deviceId}>
                {i.name} ·{' '}
                {(
                  {
                    waiting_capacity: '容量不足，等待资源',
                    creating: '创建中',
                    starting: '启动中',
                    waiting_create: '等待创建',
                    succeeded: '已完成',
                    failed: '失败',
                  } as Record<string, string>
                )[i.state] ?? i.state}
                {i.error && `：${i.error}`}
              </p>
            ))}
            <Action onClick={() => p.onBatch(b.id, 'retry')}>重试失败项</Action>
            <Action onClick={() => p.onBatch(b.id, 'cancel')}>取消等待项</Action>
          </section>
        ))}
    </main>
  )
}
