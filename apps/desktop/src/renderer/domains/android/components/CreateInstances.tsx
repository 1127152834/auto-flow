import { ApiClientError } from '../../../shared/api/client'
import { useRef, useState } from 'react'
import { ArrowLeft, CaretDown, CheckCircle, Info, Laptop } from '@phosphor-icons/react'
import type { AndroidDevice, AndroidEnvironment } from '../api'
import type { BatchRequest, Profile } from '../fleet-api'
import { Action, Dot, Quantity, Toggle } from './PrototypeControls'
import configurationPhone from '../assets/reference/configuration-phone.png'
export function CreateInstances({
  profiles,
  environment,
  source,
  onBack,
  onProfiles,
  onSubmit,
}: {
  profiles: Profile[]
  environment?: AndroidEnvironment
  source?: AndroidDevice
  onBack(): void
  onProfiles(): void
  onSubmit(value: BatchRequest): Promise<void>
}) {
  const [name, setName] = useState(source ? `${source.name} 副本` : '测试设备'),
    [quantity, setQuantity] = useState(1)
  const [profileId, setProfileId] = useState(source?.profileId ?? profiles[0]?.id ?? '')
  const profile = profiles.find((p) => p.id === profileId)
  const [resolution, setResolution] = useState(`${source?.width ?? 720}x${source?.height ?? 1280}`)
  const [start, setStart] = useState(true),
    [advanced, setAdvanced] = useState(false)
  const [locale, setLocale] = useState(source?.locale ?? 'zh-CN'),
    [timezone, setTimezone] = useState(source?.timezone ?? 'Asia/Shanghai')
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    pending = useRef<BatchRequest | null>(null)
  const submit = async () => {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    const [width, height] = resolution.split('x').map(Number)
    pending.current ??= {
      batchId: crypto.randomUUID(),
      name,
      quantity,
      profileId: profile.id,
      profileRevision: profile.revision ?? 1,
      width,
      height,
      start,
      instanceType: 'persistent',
      locale,
      timezone,
    }
    try {
      await onSubmit(pending.current!)
    } catch (e) {
      if (e instanceof ApiClientError && e.status >= 400 && e.status < 500) pending.current = null
      setError(e instanceof Error ? e.message : '创建结果尚未确认，请按原编号重试')
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="ad-page ad-create-page">
      <button className="ad-breadcrumb" onClick={onBack}>
        <ArrowLeft size={18} />
        返回资源看板 <span>/</span>创建实例
      </button>
      <header className="ad-page-heading">
        <div>
          <h1>创建安卓实例</h1>
          <p>从环境配置创建，实例之间独立保存数据。</p>
        </div>
      </header>
      <div className="ad-create-grid">
        <div className="ad-create-form">
          <fieldset disabled={busy || Boolean(pending.current)}>
            <section>
              <h2>
                <b>1</b>基本信息
              </h2>
              <div className="ad-form-row">
                <label htmlFor="ad-name">实例名称</label>
                <div>
                  <input id="ad-name" autoFocus value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
                  <p>
                    将创建：{name}{' '}
                    {Array.from({ length: Math.min(quantity, 5) }, (_, i) => String(i + 1).padStart(2, '0')).join('、')}
                    {quantity > 5 ? '…' : ''}
                  </p>
                </div>
                <label>数量</label>
                <Quantity value={quantity} onChange={setQuantity} />
              </div>
            </section>
            <section>
              <h2>
                <b>2</b>环境配置
              </h2>
              <div className="ad-form-row">
                <label htmlFor="ad-profile">选择环境配置</label>
                <select
                  id="ad-profile"
                  value={profileId}
                  onChange={(e) => {
                    setProfileId(e.target.value)
                    const p = profiles.find((p) => p.id === e.target.value)
                    if (p) {
                      setLocale(p.locale ?? 'zh-CN')
                      setTimezone(p.timezone ?? 'Asia/Shanghai')
                      setResolution(`${p.width}x${p.height}`)
                    }
                  }}
                >
                  <option value="" disabled>
                    请选择环境配置
                  </option>
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <button className="ad-link" onClick={onProfiles}>
                  管理配置
                </button>
              </div>
              <div className="ad-profile-note">
                <span>
                  软件渲染 · {resolution.replace('x', ' × ')} ·{' '}
                  {profile?.shellRoot === 'available' ? 'shell root 可用' : 'shell root 待验证'}
                </span>
                <span>
                  <Info size={18} />
                  应用级 root 需单独验证。
                </span>
              </div>
              <div className="ad-form-row ad-resolution">
                <label htmlFor="ad-resolution">分辨率</label>
                <select id="ad-resolution" value={resolution} onChange={(e) => setResolution(e.target.value)}>
                  {['540x960', '720x1280', '1080x1920'].map((v) => (
                    <option key={v} value={v}>
                      {v.replace('x', ' × ')}
                    </option>
                  ))}
                </select>
              </div>
              <button className="ad-advanced" onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}>
                <CaretDown size={18} />
                更多设置 · 语言与时区
              </button>
              {advanced && (
                <div className="ad-advanced-fields">
                  <label>
                    语言
                    <select value={locale} onChange={(e) => setLocale(e.target.value)}>
                      <option value="zh-CN">简体中文</option>
                      <option value="en-US">English</option>
                    </select>
                  </label>
                  <label>
                    时区
                    <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                      <option>Asia/Shanghai</option>
                      <option>UTC</option>
                      <option>America/Los_Angeles</option>
                    </select>
                  </label>
                </div>
              )}
            </section>
            <section>
              <h2>
                <b>3</b>数据与启动
              </h2>
              <div className="ad-form-row">
                <label>实例类型</label>
                <div className="ad-instance-types">
                  <div className="selected"><strong>持久实例</strong><p>保留应用和数据，适合重复调试</p></div>
                </div>
              </div>
              <div className="ad-form-row ad-start-row">
                <label>创建后启动</label>
                <div>
                  <Toggle label="创建后启动" value={start} onChange={setStart} green />
                  <span>启动完成且 Android 就绪后才可操作。</span>
                </div>
              </div>
            </section>
          </fieldset>
          {error && (
            <p role="alert" className="ad-error">
              {error}
            </p>
          )}
        </div>
        <aside className="ad-create-preview">
          <h2>创建预览</h2>
          <div className="ad-create-device">
            <img src={configurationPhone} alt="Android 设备示意" />
            <dl>
              <div>
                <dt>数量</dt>
                <dd>{quantity} 台</dd>
              </div>
              <div>
                <dt>系统</dt>
                <dd>{profile?.name ?? '系统版本待核实'}</dd>
              </div>
              <div>
                <dt>分辨率</dt>
                <dd>{resolution.replace('x', ' × ')}</dd>
              </div>
              <div>
                <dt>数据</dt>
                <dd>独立持久保存</dd>
              </div>
            </dl>
          </div>
          <section>
            <h3>运行环境</h3>
            <p>
              <Laptop size={30} />
              Mac 本机{' '}
              <span>
                <Dot />
                {environment?.available ? '已连接' : '未连接'}
              </span>
            </p>
            <p className={environment?.available ? 'ad-compatible' : ''}>
              <CheckCircle weight="fill" size={23} />
              {environment?.available ? '当前配置兼容' : '请检查运行环境'}
            </p>
            <p className="ad-muted">
              <Info size={18} />
              同时启动数量由本机资源限制。
            </p>
          </section>
        </aside>
      </div>
      <footer className="ad-create-footer">
        <Action onClick={onBack} disabled={busy}>
          取消
        </Action>
        <p>创建进度可在资源看板逐台查看。</p>
        <span>
          将创建 <strong>{quantity}</strong> 台持久实例
        </span>
        <Action
          primary
          onClick={() => void submit()}
          disabled={busy || !name.trim() || !profile || !environment?.available}
        >
          {busy ? '正在提交…' : pending.current ? '按原编号核实创建' : start ? '创建并启动' : '创建实例'}
        </Action>
      </footer>
    </main>
  )
}
