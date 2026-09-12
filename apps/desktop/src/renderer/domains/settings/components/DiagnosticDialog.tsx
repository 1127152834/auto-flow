import { Spinner } from '../../../shared/components/ui/spinner'
import { Check } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import type { DiagnosticPreview, SettingsBridge } from '../../../../shared/settings'
import { Modal } from '../../../shared/components/Modal'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'

function unwrap<T>(result: Awaited<ReturnType<SettingsBridge['getSettings']>> | { ok: true; value: T } | { ok: false; error: { message: string } }): T {
  if (!result.ok) throw new Error(result.error.message)
  return result.value as T
}

export function DiagnosticDialog({ open, bridge, onOpenChange }: { open: boolean; bridge: SettingsBridge; onOpenChange(open: boolean): void }) {
  const [includeLogs, setIncludeLogs] = useState(false)
  const [preview, setPreview] = useState<DiagnosticPreview | null>(null)
  const [busy, setBusy] = useState<'preview' | 'save' | null>(null)
  const [previewError, setPreviewError] = useState('')
  const [saveError, setSaveError] = useState('')
  const generation = useRef(0)
  const mounted = useRef(true)

  async function loadPreview(logs = includeLogs) {
    const request = ++generation.current
    setBusy('preview'); setPreviewError(''); setSaveError(''); setPreview(null)
    try { const next = unwrap<DiagnosticPreview>(await bridge.previewDiagnostics(logs)); if (mounted.current && request === generation.current) setPreview(next) }
    catch (cause) { if (mounted.current && request === generation.current) setPreviewError(cause instanceof Error ? cause.message : '诊断预览生成失败') }
    finally { if (mounted.current && request === generation.current) setBusy(null) }
  }

  useEffect(() => { mounted.current = true; if (open) void loadPreview(false); else { generation.current += 1; setIncludeLogs(false); setPreview(null); setPreviewError(''); setSaveError(''); setBusy(null) } return () => { mounted.current = false; generation.current += 1 } }, [open])

  async function save() {
    if (!preview) return
    setBusy('save'); setSaveError('')
    try {
      const result = unwrap<{ saved: boolean; path?: string }>(await bridge.saveDiagnostics(preview.id))
      if (result.saved) { notify({ title: `诊断信息已保存${result.path ? `：${result.path.split(/[\\/]/).pop()}` : ''}`, tone: 'success' }); onOpenChange(false) }
    } catch (cause) { if (mounted.current) setSaveError(cause instanceof Error ? cause.message : '无法写入所选位置') }
    finally { if (mounted.current) setBusy(null) }
  }

  return <Modal open={open} onOpenChange={onOpenChange} closeDisabled={busy !== null} title="导出诊断信息" description="预览完整内容后，选择本地保存位置。" size="large" footer={<><Button disabled={busy !== null} onClick={() => onOpenChange(false)}>取消</Button><Button variant="primary" disabled={!preview || busy !== null} onClick={() => void save()}>{busy === 'save' ? <><Spinner  />正在保存…</> : saveError ? '重新选择保存位置' : '选择保存位置'}</Button></>}>
    <div className="grid gap-5 md:grid-cols-[15rem_minmax(0,1fr)]">
      <div className="grid content-start gap-3 text-sm"><strong>将包含</strong>{['基础版本与平台信息', '本地服务状态', '最近错误码'].map(item => <span className="flex items-center gap-2" key={item}><Check className="text-clay" weight="bold" />{item}</span>)}<label className="mt-2 flex cursor-pointer items-start gap-3 border-t border-line pt-4"><Checkbox disabled={busy !== null} checked={includeLogs} onCheckedChange={(checked) => { const next = checked === true; setIncludeLogs(next); void loadPreview(next) }} aria-label="添加最近日志" /><span><strong className="block">添加最近日志（可选）</strong><small className="text-muted">仅包含当前应用记录的结构化生命周期事件，不扫描用户原始日志。</small></span></label><p className="text-xs leading-5 text-muted">不包含数据库、凭据或浏览器配置，不会自动上传。</p></div>
      <div><strong className="text-sm">内容预览</strong>{busy === 'preview' ? <p role="status" className="mt-3 flex items-center gap-2 text-sm text-muted"><Spinner  />正在生成完整预览…</p> : previewError ? <div role="alert" className="mt-3 rounded-control border border-danger/30 bg-danger-soft p-3 text-sm text-danger">{previewError}<div className="mt-3"><Button onClick={() => void loadPreview()}>重试生成</Button></div></div> : <>{saveError ? <div role="alert" className="mt-3 rounded-control border border-danger/30 bg-danger-soft p-3 text-sm text-danger">{saveError}。预览内容已保留，请重新选择保存位置。</div> : null}<pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-control bg-surface-subtle p-4 text-xs leading-5">{preview?.content}</pre></>}</div>
    </div>
  </Modal>
}
