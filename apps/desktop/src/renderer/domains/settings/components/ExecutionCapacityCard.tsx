import { Cpu } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import type { ExecutionSettings, ExecutionSettingsApi } from '../executionApi'
import { SettingsCard } from './SettingsCard'

const message = (cause: unknown, fallback: string) => cause instanceof Error ? cause.message : fallback

export function ExecutionCapacityCard({ api }: { api: ExecutionSettingsApi }) {
  const [settings, setSettings] = useState<ExecutionSettings | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api.read().then(value => { if (active) { setSettings(value); setDraft(String(value.effectiveMaxRunningBrowsers)) } })
      .catch(cause => { if (active) setError(message(cause, '读取失败')) })
    return () => { active = false }
  }, [api])

  async function save(value: number | null) {
    if (!settings) return
    setSaving(true); setError('')
    try {
      const saved = await api.save(value, settings.revision)
      setSettings(saved); setDraft(String(saved.effectiveMaxRunningBrowsers))
    } catch (cause) { setError(message(cause, '保存失败，请刷新后重试')) } finally { setSaving(false) }
  }

  const parsed = Number(draft)
  const draftError = draft.trim() && Number.isInteger(parsed) && parsed >= 1 && parsed <= 64 ? '' : '请输入 1–64 的整数'
  const description = settings
    ? `推荐 ${settings.recommendedMaxRunningBrowsers} 个（依据：${settings.hardware.logicalCpus} 个逻辑 CPU、${settings.hardware.totalMemoryGb} GB 内存）。等待人工处理的任务不占这里的名额。`
    : '正在读取本机配置…'
  return <SettingsCard icon={Cpu} title="同时运行的浏览器" description={description}>
    <div className="grid gap-3">
      <label className="grid items-center gap-2 sm:grid-cols-[1fr_13rem]">
        <span><strong className="block">最多同时运行</strong><small className="text-muted">{settings?.maxRunningBrowsers === null ? '当前使用推荐值' : '当前使用自定义值'}</small></span>
        <Input inputMode="numeric" aria-label="最多同时运行的浏览器" value={draft} disabled={!settings || saving} aria-invalid={Boolean(draftError)} onChange={event => setDraft(event.target.value)} />
      </label>
      {draftError ? <p role="alert" className="m-0 text-sm text-danger">{draftError}</p> : null}
      {settings?.memoryPressure ? <p role="status" className="m-0 text-sm text-muted">本机内存占用较高，新任务会暂缓启动。</p> : null}
      {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={!settings || saving || Boolean(draftError)} onClick={() => void save(parsed)}>保存</Button>
        <Button disabled={!settings || saving || settings.maxRunningBrowsers === null} onClick={() => void save(null)}>恢复推荐值</Button>
      </div>
    </div>
  </SettingsCard>
}
