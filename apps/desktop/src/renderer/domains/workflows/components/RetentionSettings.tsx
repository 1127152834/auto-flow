import { useEffect, useRef, useState } from 'react'
import { retentionApi, type RetentionConfig, type RetentionUsage } from '../api'
import { getStudioTransportRevision } from '../api/transport'
import { isRetentionConfig } from '../lib/retentionContract'
import { useSettingsDraftProtection, type RegisterSettingsLeaveGuard } from '../hooks/useSettingsDraftProtection'
import { Button } from './controls/button'
import { Input } from './controls/input'

type NumericKey = Exclude<keyof RetentionConfig, 'enabled'>
const fields: [NumericKey, string][] = [
  ['recordings_max_days', '录像保留天数'], ['recordings_max_total_mb', '录像总大小上限(MB)'],
  ['data_max_days', '数据保留天数'], ['data_max_total_mb', '数据总大小上限(MB)'], ['cleanup_interval_hours', '清理间隔(小时)'],
]
type Draft = { enabled: boolean } & Record<NumericKey, string>
const toDraft = (config: RetentionConfig): Draft => ({ enabled: config.enabled, ...Object.fromEntries(fields.map(([key]) => [key, String(config[key])])) }) as Draft

export function RetentionSettings({ registerLeaveGuard }: { registerLeaveGuard?: RegisterSettingsLeaveGuard }) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [baseline, setBaseline] = useState('')
  const [usage, setUsage] = useState<RetentionUsage | null>(null)
  const [mock, setMock] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [connected, setConnected] = useState(true)
  const lock = useRef(false)
  const mounted = useRef(true)
  const loadedRevision = useRef<number | null>(null)
  const current = (revision: number) => mounted.current && revision === getStudioTransportRevision()

  const refresh = async () => {
    if (lock.current) return
    lock.current = true; setBusy(true); setError(''); setMessage('')
    const revision = getStudioTransportRevision()
    try {
      const res = await retentionApi.getConfig()
      if (!current(revision)) return
      if (!res.success || !res.data) { setError(res.error || '无法读取留存策略'); return }
      const next = toDraft(res.data.config)
      setDraft(next); setBaseline(JSON.stringify(next)); setUsage(res.data.usage); setMock(res.data.mock === true)
      loadedRevision.current = revision; setConnected(true)
    } catch (e) { if (current(revision)) setError(e instanceof Error ? e.message : '无法读取留存策略') }
    finally { lock.current = false; if (mounted.current) setBusy(false) }
  }
  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => { mounted.current = false }
    // A new connection invalidates the form instead of silently replacing its draft.
  }, [])
  useEffect(() => {
    const invalidate = () => {
      if (loadedRevision.current !== getStudioTransportRevision()) { setConnected(false); setError('服务连接已变更，请重新打开留存设置后核对；当前输入已保留') }
    }
    window.addEventListener('studio:transport-changed', invalidate)
    return () => window.removeEventListener('studio:transport-changed', invalidate)
  }, [])
  const save = async (): Promise<boolean> => {
    if (!draft || lock.current) return false
    if (loadedRevision.current !== getStudioTransportRevision()) { setError('服务连接已变更，不能向新连接提交旧策略'); return false }
    const config = { enabled: draft.enabled, ...Object.fromEntries(fields.map(([key]) => [key, Number(draft[key])])) }
    if (fields.some(([key]) => draft[key].trim() === '') || !isRetentionConfig(config)) {
      setError('请填写非负安全整数；清理间隔必须至少为 1 小时'); return false
    }
    lock.current = true; setBusy(true); setError(''); setMessage('')
    const revision = getStudioTransportRevision()
    try {
      const res = await retentionApi.setConfig(config)
      if (!current(revision)) return false
      if (!res.success || !res.data) { setError(res.error || '保存策略失败'); return false }
      const next = toDraft(res.data.config)
      setDraft(next); setBaseline(JSON.stringify(next)); setMock(res.data.mock === true)
      setMessage(res.data.mock ? 'Mock 策略已保存；未启动真实定时清理' : '清理策略已保存')
      return true
    } catch (e) { if (current(revision)) setError(e instanceof Error ? e.message : '保存策略失败'); return false }
    finally { lock.current = false; if (mounted.current) setBusy(false) }
  }
  const dirty = !!draft && JSON.stringify(draft) !== baseline
  const leave = useSettingsDraftProtection(registerLeaveGuard, '保存留存策略？', dirty, busy, save)
  const cleanup = async () => {
    if (lock.current || dirty || loadedRevision.current !== getStudioTransportRevision()) return
    lock.current = true; setBusy(true); setError(''); setMessage('')
    const revision = getStudioTransportRevision()
    try {
      const result = await retentionApi.cleanup()
      if (!current(revision)) return
      if (!result.success || !result.data) { setError(result.error || '清理失败'); return }
      const data = result.data
      setMessage(data.mock ? 'Mock 清理确认：未删除任何真实文件' : `清理完成：录像 ${data.recordings.removed} 个（${data.recordings.freedMB} MB），数据 ${data.data.removed} 个（${data.data.freedMB} MB）`)
      const updated = await retentionApi.usage()
      if (!current(revision)) return
      if (updated.success && updated.data) setUsage(updated.data.usage)
      else setError(`清理已确认，但用量刷新失败：${updated.error || '无有效响应'}`)
    } catch (e) { if (current(revision)) setError(e instanceof Error ? e.message : '清理请求失败，请核对后再操作') }
    finally { lock.current = false; if (mounted.current) setBusy(false) }
  }
  return <div className="space-y-4">
    <p className="text-xs text-gray-500">运行录像与采集数据的留存策略。天数和大小为 0 表示不限；清理间隔至少为 1 小时。手动清理使用已保存的策略。</p>
    {mock && <p className="text-xs text-amber-700">当前为 Mock 服务：策略与交互可验证，不执行真实文件清理。</p>}
    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    {message && <p role="status" className="text-sm text-gray-600">{message}</p>}
    {!draft ? <Button disabled={busy} onClick={() => void refresh()}>{busy ? '读取中…' : '重试读取'}</Button> : <>
      {usage && <div className="grid grid-cols-2 gap-2 text-sm"><span>运行录像：{usage.recordings.count} 个 · {usage.recordings.sizeMB} MB</span><span>采集数据：{usage.data.count} 个 · {usage.data.sizeMB} MB</span></div>}
      <fieldset disabled={busy || leave.pending || !connected} className="space-y-3">
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={draft.enabled} onChange={e => setDraft({ ...draft, enabled: e.target.checked })} />启用自动清理</label>
        <div className="grid grid-cols-2 gap-3">{fields.map(([key, label]) => <label key={key} className="text-xs text-gray-700">{label}<Input aria-label={label} type="number" min={key === 'cleanup_interval_hours' ? 1 : 0} step={1} value={draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></label>)}</div>
        {dirty && <p className="text-xs text-gray-500">策略尚未保存，请先保存后执行手动清理。</p>}
        <div className="flex justify-end gap-2"><Button variant="outline" disabled={dirty} onClick={() => void cleanup()}>立即清理一次</Button><Button onClick={() => void save()}>保存策略</Button></div>
      </fieldset>
    </>}
    {leave.dialog}
  </div>
}
