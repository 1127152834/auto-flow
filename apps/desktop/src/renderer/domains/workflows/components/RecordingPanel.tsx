import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import type { WorkflowRecording } from '../hooks/useWorkflowRecording'
import type { RecordingGeneration, RecordingStep } from '../recording-api'
import type { WorkflowContent } from '../types'

type Props = { recording: WorkflowRecording; disabled: boolean; otherActive: boolean; profileId: string; content: WorkflowContent; semanticKey: string; commit(): void; apply(value: RecordingGeneration, key: string): void }
export function RecordingPanel({ recording: r, disabled, otherActive, profileId, content, semanticKey, commit, apply }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [url, setUrl] = useState('')
  const [selected, setSelected] = useState<RecordingStep | null>(null)
  const [text, setText] = useState('')
  const [label, setLabel] = useState('')
  const [useVariables, setUseVariables] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [preview, setPreview] = useState<{ value: RecordingGeneration; key: string; recordingId: string } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const loading = useRef(0)
  const latest = useRef({ semanticKey, id: r.record?.recordingId }); latest.current = { semanticKey, id: r.record?.recordingId }
  const record = r.record
  const canEdit = record && ['stopped', 'interrupted'].includes(record.captureState)
  const saveEdit = async () => {
    if (!dirty || !selected || !record) return true
    let config: Record<string, never>
    try { config = JSON.parse(text); if (!config || Array.isArray(config) || typeof config !== 'object') throw Error() }
    catch { r.setMessage('步骤参数必须是有效 JSON 对象，修改已保留'); return false }
    const result = await r.perform(async () => { await r.api.edit(record.recordingId, { expectedRevision: record.revision, changes: [{ stepId: selected.stepId, config, label, useVariables }] }) })
    if (result) setDirty(false)
    return result
  }
  r.flushReview.current = saveEdit
  useEffect(() => () => { r.flushReview.current = async () => true; loading.current++ }, [r.flushReview])
  const select = async (step: RecordingStep) => {
    if (!record || !await saveEdit()) return
    const token = ++loading.current, id = record.recordingId
    try {
      const config = step.valueRef ? await r.api.value(id, step.stepId) : step.config
      if (token !== loading.current || latest.current.id !== id) return
      setSelected(step); setText(JSON.stringify(config, null, 2)); setLabel(step.label); setUseVariables(step.useVariables); setDirty(false)
    } catch (error) { r.setMessage(error instanceof Error ? error.message : '无法读取步骤完整参数') }
  }
  const generate = async () => {
    commit()
    if (!record || !await saveEdit()) return
    const id = record.recordingId, key = semanticKey, snapshot = structuredClone(content)
    await r.perform(async () => {
      const fresh = await r.api.get(id)
      const value = await r.api.generate(id, { generationId: crypto.randomUUID(), expectedRevision: fresh.revision, target: snapshot })
      if (latest.current.semanticKey !== key || latest.current.id !== id) throw new Error('流程或录制已切换，请重新生成预览')
      setPreview({ value, key, recordingId: id })
    })
  }
  const blocked = disabled || r.busy
  return <section className="shrink-0 border-b border-line bg-surface px-5 py-2" aria-label="网页录制">
    <div className="flex items-center gap-2"><Button variant="ghost" onClick={() => setExpanded(!expanded)}>{expanded ? '收起录制' : '网页录制'}</Button><span role="status" className="text-xs text-muted">{record ? `${record.captureState} · ${record.lastSeq} 步 · 浏览器 ${record.browserState}` : '将真实操作生成可编辑流程'}</span></div>
    {expanded ? <div className="mt-2 space-y-3">
      <p className="text-xs text-muted">使用工具栏所选浏览器配置，强制可见模式。普通录制值保存在当前工作区；录制前登录状态不会传给独立运行。</p>
      <div className="flex flex-wrap gap-2"><Button disabled={blocked || otherActive || r.active || !profileId} onClick={() => void r.start(profileId, content.document.id)}>打开录制浏览器</Button>
        <Select aria-label="最近录制" value={record?.recordingId ?? ''} disabled={blocked} onChange={e => { void r.select(e.target.value); setSelected(null); setPreview(null) }}><option value="">选择录制</option>{r.history.map(item => <option key={item.recordingId} value={item.recordingId}>{item.profileName} · {new Date(item.createdAt).toLocaleString()}</option>)}</Select>
        <Button disabled={blocked || record?.browserState !== 'ready' || record.captureState !== 'idle'} onClick={() => void r.command('start')}>开始录制</Button>
        <Button disabled={blocked || record?.captureState !== 'recording'} onClick={() => void r.command('pause')}>暂停录制</Button>
        <Button disabled={blocked || record?.captureState !== 'paused'} onClick={() => void r.command('resume')}>继续录制</Button>
        <Button disabled={blocked || !record || !['recording', 'paused'].includes(record.captureState)} onClick={() => void r.command('stop')}>停止并审查</Button>
        <Button disabled={blocked || !r.active} onClick={() => void r.close()}>关闭录制浏览器</Button>
        <Button disabled={blocked || !record || r.active} onClick={() => setConfirmDelete(true)}>删除录制草稿</Button>
      </div>
      {record?.browserState === 'ready' ? <div className="flex flex-wrap gap-2"><Select aria-label="录制目标页" value={record.targetPageId ?? ''} disabled={blocked} onChange={e => void r.page(e.target.value)}><option value="">选择目标页</option>{record.pages.map(page => <option key={page.pageId} value={page.pageId}>{page.title || page.url}</option>)}</Select><Input className="max-w-sm" aria-label="录制导航地址" placeholder="http:// 或 https://" value={url} onChange={e => setUrl(e.target.value)} /><Button disabled={blocked || !record.targetPageId} onClick={() => void r.page(record.targetPageId!, url || undefined)}>导航／聚焦</Button></div> : null}
      {record?.issues.map((issue, i) => <p key={i} className="text-xs text-amber-800">{String(issue.message)}</p>)}
      {r.message ? <p role="alert" className="text-sm text-red-700">{r.message}</p> : null}
      <div className="grid max-h-72 grid-cols-2 gap-3 overflow-hidden">
        <div className="overflow-y-auto" aria-label="录制步骤列表">{r.steps.map(step => <div key={step.stepId} className="flex items-center border-b border-line py-1"><button className="min-w-0 flex-1 truncate px-2 text-left text-sm disabled:opacity-50" disabled={blocked || !canEdit} onClick={() => void select(step)}>{step.seq}. {step.label || step.action}{step.excluded ? '（已排除）' : ''}{step.issues.length ? ' · 待核验' : ''}</button>{canEdit ? <Button variant="ghost" disabled={blocked || dirty} onClick={() => void r.perform(async () => { await r.api.edit(record!.recordingId, { expectedRevision: record!.revision, changes: [{ stepId: step.stepId, excluded: !step.excluded }] }) })}>{step.excluded ? '恢复' : '排除'}</Button> : null}</div>)}</div>
        {selected && canEdit ? <div className="space-y-2 overflow-y-auto" aria-label="录制步骤审查"><Input aria-label="录制步骤名称" value={label} onChange={e => { setLabel(e.target.value); setDirty(true) }} /><Textarea aria-label="录制步骤参数" rows={7} value={text} onChange={e => { setText(e.target.value); setDirty(true) }} /><label className="text-xs"><input type="checkbox" checked={useVariables} onChange={e => { setUseVariables(e.target.checked); setDirty(true) }} /> 将文本作为变量引用（默认保留原文）</label><p className="text-xs text-muted">导航的 navigation：direct 表示主动访问，result 表示前一步结果；新页面需指定 causeStepId。修改后需重新测试定位。</p><div className="flex gap-2"><Button disabled={blocked || !dirty} onClick={() => void saveEdit()}>保存步骤修改</Button><Button disabled={blocked || record?.browserState !== 'ready'} onClick={() => void r.perform(async () => { const c = JSON.parse(text); const result = await r.api.test(record!.recordingId, { pageId: record!.targetPageId ?? selected.pageId, selector: c.selector ?? '', framePath: c.framePath ?? [], variables: content.document.variables, literalPaths: useVariables ? [] : ['config.selector', ...(c.framePath ?? []).map((_: string, i: number) => `config.framePath.${i}`)] }); r.setMessage(`匹配 ${result.count} 个，首个${result.first?.visible ? '可见' : '不可见或不存在'}`) })}>测试定位</Button></div></div> : <p className="p-3 text-sm text-muted">停止录制后选择步骤审查。定位失效和不支持的操作需要补充或明确排除。</p>}
      </div>
      <div className="flex gap-2"><Button disabled={blocked || dirty || r.after === 0} onClick={r.firstPage}>第一页</Button><Button disabled={blocked || dirty || r.next === null} onClick={r.nextPage}>下一页</Button><Button variant="primary" disabled={blocked || !canEdit} onClick={() => void generate()}>生成流程预览</Button></div>
    </div> : null}
    <Dialog open={Boolean(preview)} onOpenChange={open => { if (!open) setPreview(null) }}><DialogContent><DialogTitle>加入录制步骤</DialogTitle><DialogDescription>追加到空流程或唯一顶层尾部，一次撤销。加入后需要手动保存。</DialogDescription><p>{preview?.value.nodes.length} 个节点</p>{preview?.value.issues.map((issue, i) => <p key={i} className="text-xs text-amber-800">{String(issue.message)}</p>)}<div className="flex justify-end gap-2"><Button onClick={() => setPreview(null)}>取消</Button><Button disabled={blocked || !preview || preview.key !== semanticKey || preview.value.issues.some(i => ['NAVIGATION_UNCONFIRMED', 'PAGE_SOURCE_REQUIRED', 'RECORDING_UNSUPPORTED'].includes(String(i.code)))} onClick={() => { if (preview) { apply(preview.value, preview.key); setPreview(null) } }}>加入画布</Button></div></DialogContent></Dialog>
    <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}><DialogContent><DialogTitle>删除录制草稿？</DialogTitle><DialogDescription>删除此录制及其原文文件，已加入工作流的节点保留。</DialogDescription><Button onClick={() => setConfirmDelete(false)}>取消</Button><Button variant="danger" disabled={blocked} onClick={() => void r.perform(async () => { if (record) await r.api.remove(record.recordingId); setConfirmDelete(false); setSelected(null) })}>删除</Button></DialogContent></Dialog>
  </section>
}
