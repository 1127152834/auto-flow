import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowsOut,
  ArrowsClockwise,
  Camera,
  CheckCircle,
  Copy,
  Database,
  DotsThree,
  File,
  House,
  Info,
  Keyboard,
  LockKey,
  Monitor,
  Play,
  AndroidLogo,
  Shield,
  SpeakerHigh,
  CopySimple,
  UploadSimple,
} from '@phosphor-icons/react'
import type { AndroidApi, AndroidDevice } from '../api'
import { isCurrentConsoleResponse, isVerifiedAppFailure, type Apps, type ConsoleSession, type DeviceRun, type FleetApi, type InputCommand, type SessionAction } from '../fleet-api'
import { Action, Badge, Dot, Phone, Toggle } from './PrototypeControls'
import { AndroidVideo } from './AndroidVideo'
import { ApplicationsPanel } from './ApplicationsPanel'
export type ConsoleProps = {
  device: AndroidDevice
  session: ConsoleSession | null
  api?: FleetApi
  deviceApi?: AndroidApi
  run?: DeviceRun
  apps?: Apps
  image?: string
  thumbnail?: string
  initialText?: string
  onBack(): void
  onSession(s: ConsoleSession): void
  onTransition?(changing: boolean): Promise<void> | void
  onOpen(): void
  onManage(action: string): void
  onRefresh(): void
}
export function DeviceConsole(p: ConsoleProps) {
  const [tab, setTab] = useState('控制台'),
    [keyboard, setKeyboard] = useState(true),
    [text, setText] = useState(p.initialText ?? ''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [menu, setMenu] = useState(false),
    [fit, setFit] = useState('fit'),
    [packageName, setPackage] = useState(p.apps?.currentPackage ?? '')
  const [videoReady, setVideoReady] = useState(Boolean(p.image)),
    [volumeMenu, setVolumeMenu] = useState(false),
    [unknownInstall, setUnknownInstall] = useState<{ requestId: string; generation: number } | null>(null)
  const switching = useRef(false)
  const sequence = useRef(0),
    queue = useRef(Promise.resolve()),
    file = useRef<HTMLInputElement>(null),
    panel = useRef<HTMLDivElement>(null),
    sessionRef = useRef(p.session),
    failed = useRef(false)
  sessionRef.current = p.session
  useEffect(() => {
    sessionRef.current = p.session
    return () => { sessionRef.current = null }
  }, [p.session])
  const readonly = !p.session || p.session.state !== 'connected' || p.session.access !== 'manual' || p.session.endpoint !== 'embedded',
    workflow = Boolean(p.run && !['succeeded', 'failed', 'stopped', 'interrupted'].includes(p.run.state)),
    temporary = p.device.instanceType === 'temporary'
  const inputError = useCallback((message: string) => {
    if (switching.current) return
    failed.current = true
    setVideoReady(false)
    setError(message)
  }, [])
  const send = useCallback(
    (command: Partial<InputCommand>) => {
      const session = sessionRef.current
      if (!session || session.access !== 'manual' || !p.api || failed.current || switching.current) return
      const payload: InputCommand = {
        action: 0,
        keycode: 0,
        x: 0,
        y: 0,
        width: session.width,
        height: session.height,
        text: '',
        ...command,
        generation: session.generation,
        sequence: ++sequence.current,
        kind: command.kind ?? 'release',
      }
      queue.current = queue.current
        .then(async () => {
          if (failed.current || !isCurrentConsoleResponse(sessionRef.current, session)) return
          const updated = await p.api!.input(session.id, payload)
          if (isCurrentConsoleResponse(sessionRef.current, session)) p.onSession(updated)
        })
        .catch((e) => {
          if (isCurrentConsoleResponse(sessionRef.current, session)) inputError(e instanceof Error ? e.message : '操作结果未知，请核实设备')
        })
    },
    [p.api, p.onSession, inputError],
  )
  const action = async (kind: SessionAction) => {
    if (!p.api || !p.session || busy) return
    const issued = p.session
    const current = () => sessionRef.current?.id === issued.id && sessionRef.current.deviceId === issued.deviceId &&
      sessionRef.current.generation === issued.generation && sessionRef.current.state === issued.state &&
      sessionRef.current.access === issued.access && sessionRef.current.endpoint === issued.endpoint
    setBusy(true)
    switching.current = true
    setError('')
    try {
      await p.onTransition?.(true)
      await queue.current
      if (!current()) return
      const s = await p.api.action(issued, kind)
      if (!current()) return
      p.onSession(s)
      failed.current = false
      p.onRefresh()
    } catch (e) {
      if (current()) setError(e instanceof Error ? e.message : '控制权切换结果未知，请刷新核实')
    } finally {
      setBusy(false)
      switching.current = false
      void p.onTransition?.(false)
    }
  }
  useEffect(() => {
    if (p.apps?.currentPackage) setPackage(p.apps.currentPackage)
  }, [p.apps?.currentPackage])
  useEffect(() => {
    const blur = () => {
      if (!readonly) send({ kind: 'release' })
    }
    window.addEventListener('blur', blur)
    return () => window.removeEventListener('blur', blur)
  }, [readonly, send])
  const key = (keycode: number) => {
    send({ kind: 'key', keycode, action: 0 })
    send({ kind: 'key', keycode, action: 1 })
  }
  const screenshot = async () => {
    try {
      if (!p.deviceApi) return
      const blob = await p.deviceApi.preview(p.device.deviceId, new AbortController().signal)
      const url = URL.createObjectURL(blob),
        link = document.createElement('a')
      link.href = url
      link.download = `${p.device.name}.png`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) {
      setError(e instanceof Error ? e.message : '截图失败')
    }
  }
  const install = async (selected?: File) => {
    if (!selected || !p.api || !p.session) return
    setBusy(true)
    const requestId = crypto.randomUUID()
    try {
      const next = await p.api.install(p.session, selected, requestId)
      if (!isCurrentConsoleResponse(sessionRef.current, p.session)) return
      p.onSession(next)
      setUnknownInstall(null)
      p.onRefresh()
    } catch (e) {
      if (!isCurrentConsoleResponse(sessionRef.current, p.session)) return
      const code = typeof e === 'object' && e !== null && 'code' in e ? String((e as { code?: unknown }).code) : ''
      if (!['ANDROID_APK_INVALID', 'ANDROID_APK_UNSUPPORTED', 'ANDROID_APK_TOO_LARGE', 'ANDROID_INSTALL_FAILED'].includes(code)) setUnknownInstall({ requestId, generation: p.session.generation })
      setError(e instanceof Error ? e.message : '安装结果未知')
    } finally {
      setBusy(false)
      if (file.current) file.current.value = ''
    }
  }
  const verifyInstall = async () => {
    if (!unknownInstall || !p.api?.verifyApp || !p.session) return
    const issued = p.session
    const current = () => isCurrentConsoleResponse(sessionRef.current, issued, unknownInstall.generation)
    try {
      const next = await p.api.verifyApp(p.session, unknownInstall.requestId, unknownInstall.generation)
      if (!current()) return
      p.onSession(next)
      setUnknownInstall(null)
      setError('应用安装已按原请求核实')
      p.onRefresh()
    } catch (cause) {
      if (!current()) return
      if (isVerifiedAppFailure(cause)) {
        setUnknownInstall(null)
        p.onRefresh()
      }
      setError(cause instanceof Error ? cause.message : '安装仍未核实')
    }
  }
  const launch = async () => {
    if (!p.api || !p.session || !packageName) return
    setBusy(true)
    try {
      const next = await p.api.launch(p.session, packageName)
      if (!isCurrentConsoleResponse(sessionRef.current, p.session)) return
      p.onSession(next)
      p.onRefresh()
    } catch (e) {
      if (!isCurrentConsoleResponse(sessionRef.current, p.session)) return
      setError(e instanceof Error ? e.message : '启动失败')
    } finally {
      setBusy(false)
    }
  }
  const tools = (
    <div className="ad-device-tools">
      {[
        [ArrowLeft, '返回', 4],
        [House, '主页', 3],
        [CopySimple, '最近任务', 187],
        [SpeakerHigh, '音量', 24],
        [ArrowsClockwise, '旋转', -1],
        [Camera, '截图', -2],
      ]
        .filter((_, i) => !readonly || i < 3)
        .map(([Icon, label, code]) => {
          const Component = Icon as typeof ArrowLeft
          return (
            <button
              key={String(label)}
              disabled={readonly || busy || Boolean(error)}
              onClick={() =>
                code === -2
                  ? void screenshot()
                  : code === -1
                    ? send({ kind: 'rotate' })
                    : code === 24
                      ? setVolumeMenu(!volumeMenu)
                      : key(code as number)
              }
              aria-label={String(label)}
            >
              <Component size={24} />
              <span>{String(label)}</span>
            </button>
          )
        })}
    </div>
  )
  const application = (
    <section className="ad-app-section">
      <h3>应用</h3>
      <p>当前应用</p>
      <div className="ad-current-app">
        <span className="ad-app-icon">
          <File size={25} />
        </span>
        <div>
          <strong>
            {packageName === 'com.google.android.keep' ? '笔记' : packageName.split('.').pop() || '尚未选择应用'}
          </strong>
          <small>{packageName || '选择或安装应用后启动'}</small>
        </div>
        <Action disabled={readonly || busy || Boolean(unknownInstall)} onClick={() => file.current?.click()}>
          <UploadSimple size={17} />
          上传 APK
        </Action>
        <Action primary disabled={readonly || busy || Boolean(unknownInstall) || !packageName} onClick={() => void launch()}>
          <Play size={16} />
          启动应用
        </Action>
      </div>
    </section>
  )
  const information = (
    <section className="ad-info-section">
      <h3>设备信息</h3>
      <p>
        <AndroidLogo size={21} />
        Android {p.device.androidVersion ?? '版本待核实'}
      </p>
      <p>
        <Monitor size={21} />
        {p.device.width} × {p.device.height}
      </p>
      <p>
        <Database size={21} />
        数据：{temporary ? '按运行策略回收' : '持久保存'}
      </p>
      <p>
        <Shield size={21} />
        Root shell：
        {p.apps?.shellRoot === 'available' ? '可用' : p.apps?.shellRoot === 'unavailable' ? '不可用' : '待验证'}
      </p>
    </section>
  )
  return (
    <main className={`ad-page ad-detail-page ${readonly && workflow ? 'ad-takeover-page' : 'ad-manual-page'}`}>
      <button className="ad-breadcrumb" onClick={p.onBack}>
        <ArrowLeft size={18} />
        返回资源看板
        {!readonly && (
          <>
            <span>/</span>
            {p.device.name}
          </>
        )}
      </button>
      <header className="ad-device-heading">
        <div className="ad-device-heading-image">{p.thumbnail && <img src={p.thumbnail} alt="" />}</div>
        <div>
          <div>
            <h1>{p.device.name}</h1>
            <Badge>
              {!readonly && <AndroidLogo size={18} />}
              {p.device.androidStatus === 'ready' ? '已就绪' : '尚未就绪'}
            </Badge>
            {workflow && <Badge tone="brown">工作流占用</Badge>}
            <Badge tone={workflow ? 'gray' : 'brown'}>{temporary ? '临时实例' : '持久实例'}</Badge>
          </div>
          <p>
            Android {p.device.androidVersion ?? '版本待核实'} · {p.device.width} × {p.device.height}
          </p>
        </div>
        <div className="ad-heading-actions">
          {!readonly && (
            <Action onClick={() => p.onManage('copy')}>
              <Copy size={20} />
              复制配置
            </Action>
          )}
          <div className="ad-more">
            <Action aria-label="更多设备操作" onClick={() => setMenu(!menu)}>
              <DotsThree size={23} />
            </Action>
            {menu && (
              <div className="ad-menu">
                {[
                  ['native', '独立 Mac 窗口'],
                  ['embedded', '返回页面操作'],
                  ['stop', '停止设备'],
                  ['delete', '删除实例'],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => {
                      setMenu(false)
                      if (value === 'native' || value === 'embedded') void action(value)
                      else p.onManage(value)
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {readonly && (
            <Action
              onClick={() =>
                p.session && p.session.state !== 'closed' ? void action(workflow ? 'native' : 'embedded') : p.onOpen()
              }
            >
              打开设备
            </Action>
          )}
        </div>
      </header>
      <div className="ad-detail-surface">
        <nav className="ad-detail-tabs" aria-label="设备详情">
          {['控制台', '应用', '环境配置'].map((label) => (
            <button key={label} aria-current={tab === label ? 'page' : undefined} onClick={() => setTab(label)}>
              {label}
            </button>
          ))}
        </nav>
        {error && (
          <p role="alert" className="ad-error">
            {error}
            {unknownInstall && p.api?.verifyApp && p.session && <Action onClick={() => void verifyInstall()}>按原请求核实</Action>}
            <Action onClick={p.onRefresh}>核实状态</Action>
          </p>
        )}
        {tab === '控制台' ? (
          <>
            {readonly && workflow && (
              <div className="ad-readonly-banner">
                <LockKey size={21} weight="fill" />
                工作流正在操作设备，当前为只读预览。
              </div>
            )}
            <div className="ad-console-grid">
              <div className="ad-screen-panel" ref={panel}>
                <header>
                  <h2>
                    {readonly ? <LockKey size={22} weight="fill" /> : <Dot />}
                    {readonly ? '只读预览' : '手动控制中'}
                  </h2>
                  {!readonly && <span>由你独占操作</span>}
                  <div>
                    <select aria-label="画面显示方式" value={fit} onChange={(e) => setFit(e.target.value)}>
                      <option value="fit">{readonly ? '查看画面' : '适应窗口'}</option>
                      <option value="actual">实际比例</option>
                    </select>
                    <Action
                      aria-label="全屏"
                      onClick={() => {
                        void panel.current?.requestFullscreen().catch(() => setError('全屏暂不可用'))
                      }}
                    >
                      <ArrowsOut size={18} />
                      {!readonly && '全屏'}
                    </Action>
                    {!readonly && (
                      <Action
                        className="ad-end-control"
                        disabled={busy}
                        onClick={() => void action(workflow ? 'resume' : 'end')}
                      >
                        {workflow ? '结束接管并继续' : '结束控制'}
                      </Action>
                    )}
                  </div>
                </header>
                <div className={`ad-screen-stage ${fit === 'actual' ? 'actual' : ''}`}>
                  <Phone>
                    {p.image ? (
                      <img src={p.image} alt="安卓设备画面" />
                    ) : p.session && p.api && p.session.state !== 'closed' && p.session.endpoint === 'embedded' ? (
                      <AndroidVideo
                        api={p.api}
                        session={p.session}
                        keyboard={keyboard}
                        send={send}
                        onError={inputError}
                        onReady={setVideoReady}
                      />
                    ) : (
                      <div className="ad-video-wait">
                        <p>{p.session?.endpoint === 'native' ? '正在独立 Mac 窗口操作' : '尚未连接设备'}</p>
                        <Action
                          onClick={() => (p.session?.endpoint === 'native' ? void action('embedded') : p.onOpen())}
                        >
                          {p.session?.endpoint === 'native' ? '切回页面操作' : '连接设备'}
                        </Action>
                      </div>
                    )}
                  </Phone>
                  {tools}
                  {volumeMenu && (
                    <div className="ad-volume-menu">
                      <Action aria-label="增大音量" onClick={() => key(24)}>
                        音量 +
                      </Action>
                      <Action aria-label="减小音量" onClick={() => key(25)}>
                        音量 −
                      </Action>
                    </div>
                  )}
                </div>
                <footer>
                  {readonly ? (
                    <>
                      <Info size={17} />
                      取得控制权后才能点击、输入或安装应用。
                      <Action onClick={() => void screenshot()}>
                        <Camera size={19} />
                        截图
                      </Action>
                    </>
                  ) : (
                    <>
                      <span>点击即触控 · 按住拖动可滑动 · 长按可呼出菜单</span>
                      <Badge>
                        <Dot tone={videoReady ? 'green' : 'gray'} />
                        {videoReady ? '实时画面' : '等待画面'}
                      </Badge>
                    </>
                  )}
                </footer>
              </div>
              <aside className="ad-console-sidebar">
                {readonly && workflow && p.run ? (
                  <>
                    <section className="ad-current-run">
                      <h2>当前工作流</h2>
                      <dl>
                        <div>
                          <dt>工作流名称</dt>
                          <dd>{p.run.workflowName}</dd>
                        </div>
                        <div>
                          <dt>运行标识</dt>
                          <dd title={p.run.runId}>本次运行</dd>
                        </div>
                        <div>
                          <dt>运行状态</dt>
                          <dd>
                            <Badge tone="brown">
                              {p.run.state === 'pausing'
                                ? '等待暂停'
                                : p.run.state === 'waiting_manual'
                                  ? '已暂停'
                                  : '运行中'}
                            </Badge>
                          </dd>
                        </div>
                      </dl>
                      <div className="ad-run-progress">
                        <span>
                          当前步骤　{p.run.currentStep} / {p.run.totalSteps}
                        </span>
                        <progress value={p.run.currentStep} max={p.run.totalSteps || 1} />
                      </div>
                      <ol>
                        {p.run.steps
                          .slice(Math.max(0, p.run.currentStep - 2), p.run.currentStep + 1)
                          .map((step, index) => (
                            <li key={String(step.id)}>
                              {(step.status ?? (index === 0 ? 'completed' : index === 1 ? 'running' : 'pending')) ===
                              'completed' ? (
                                <CheckCircle size={24} weight="fill" />
                              ) : (step.status ?? (index === 1 ? 'running' : 'pending')) === 'running' ? (
                                <span className="ad-step-active" />
                              ) : (
                                <Dot tone="gray" />
                              )}
                              <strong>{String(step.label)}</strong>
                              <span>
                                ·　
                                {
                                  (
                                    {
                                      completed: '已完成',
                                      running: '执行中',
                                      failed: '失败',
                                      pending: '等待执行',
                                    } as Record<string, string>
                                  )[
                                    String(
                                      step.status ?? (index === 0 ? 'completed' : index === 1 ? 'running' : 'pending'),
                                    )
                                  ]
                                }
                              </span>
                            </li>
                          ))}
                      </ol>
                    </section>
                    <section className="ad-takeover">
                      <h3>手动接管</h3>
                      <p>暂停成功后，设备才交给你操作。</p>
                      <div>
                        <Info size={20} weight="fill" />
                        当前步骤结束后暂停。
                      </div>
                      <Action
                        primary
                        disabled={busy || (p.session?.state === 'waiting_pause' && p.run.state !== 'waiting_manual')}
                        onClick={() => void action(p.run?.state === 'waiting_manual' ? 'embedded' : 'takeover')}
                      >
                        {p.run.state === 'waiting_manual'
                          ? '取得控制权'
                          : p.session?.state === 'waiting_pause'
                            ? '等待动作完成…'
                            : '暂停并接管'}
                      </Action>
                      <button className="ad-link" onClick={() => setError('')}>
                        保持只读
                      </button>
                      <p>
                        <Info size={17} />
                        接管期间保留实例，不执行自动清理。
                      </p>
                    </section>
                    <section className="ad-cleanup">
                      <h3>完成后处理</h3>
                      <Badge tone="gray">{temporary ? '临时实例 · 自动清理' : '持久实例 · 保留数据'}</Badge>
                      <p>手动接管时暂缓回收。</p>
                    </section>
                  </>
                ) : (
                  <>
                    <section className="ad-input-section">
                      <h2>输入与操作</h2>
                      <div className="ad-keyboard">
                        <Keyboard size={22} />
                        <div>
                          <strong>键盘输入</strong>
                          <p>点击画面后接收键盘事件。</p>
                        </div>
                        <Toggle label="键盘输入" value={keyboard} onChange={setKeyboard} />
                      </div>
                      <h3>文本发送</h3>
                      <textarea
                        aria-label="文本发送"
                        placeholder="输入要发送的文本"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        disabled={readonly}
                      />
                      <div className="ad-send">
                        <span>中文通过文本发送。</span>
                        <Action
                          primary
                          disabled={readonly || !text || busy || Boolean(error)}
                          onClick={() => send({ kind: 'text', text })}
                        >
                          发送到设备
                        </Action>
                      </div>
                    </section>
                    {application}
                    {information}
                  </>
                )}
              </aside>
            </div>
          </>
        ) : tab === '应用' ? (
          <section className="ad-secondary">
            {application}
            {p.api && <ApplicationsPanel api={p.api} apps={p.apps} session={p.session} onSession={p.onSession} onRefresh={p.onRefresh} />}
          </section>
        ) : (
          <section className="ad-secondary">
            {information}
            <dl>
              {[
                ['环境', p.device.profileName],
                ['语言', p.device.locale],
                ['时区', p.device.timezone],
                ['CPU', `${p.device.cpu} 核`],
                ['内存', `${p.device.memoryMb} MB`],
                ['应用级 root', '待独立验证'],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <Action onClick={() => p.onManage('copy')}>复制配置创建新实例</Action>
          </section>
        )}
      </div>
      <div className="ad-console-status">
        <Dot tone={videoReady ? 'green' : 'gray'} />
        {p.session?.state === 'unknown' ? (
          <>
            <strong>控制会话状态未知</strong>
            <span>输入已锁定，请重新连接并核实</span>
          </>
        ) : readonly ? (
          videoReady ? (
            '画面连接正常 · 输入已锁定'
          ) : (
            '画面未连接 · 输入已锁定'
          )
        ) : (
          <>
            <strong>
              {p.session?.state === 'closed'
                ? '已结束控制'
                : p.session?.endpoint === 'native'
                  ? '独立窗口'
                  : videoReady
                    ? '已连接'
                    : '正在连接'}
            </strong>
            <span>最新操作：{p.session?.latestOperation ?? '等待操作'}</span>
          </>
        )}
      </div>
      <input hidden ref={file} type="file" accept=".apk" onChange={(e) => void install(e.target.files?.[0])} />
    </main>
  )
}
