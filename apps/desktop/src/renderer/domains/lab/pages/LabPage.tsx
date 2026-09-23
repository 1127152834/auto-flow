import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import { createLayaApi } from '../api'
import { AutomationPreview } from '../components/AutomationPreview'
import { ExperimentHistory } from '../components/ExperimentHistory'
import { QuestionEditor } from '../components/QuestionEditor'
import { ResultPanel } from '../components/ResultPanel'
import { buildRequest, draftsFromQuestions } from '../draft'
import { presets } from '../presets'
import { readRecords, removeRecord, saveRecord } from '../storage'
import type { ExperimentRecord, InputMode, LayaRequest, LayaResult, LayaStatus, ModelChoice, QuestionDraft } from '../types'

const modelOptions = [
  { value: 'auto', label: 'Router · 自动路由', description: '英文选 English，中文等输入选 Multilingual' },
  { value: 'english', label: 'English', description: '英语通用模型 · 512 tokens' },
  { value: 'multilingual', label: 'Multilingual', description: '多语言模型 · 1024 tokens' },
  { value: 'typed-decisions', label: 'Typed Decisions', description: '英语专项模型 · 1024 tokens' },
]
const stateNames: Record<string, string> = { not_downloaded: '未下载', cached: '已缓存', downloading: '下载中', loading: '加载中', ready: '就绪', failed: '失败', available: '可路由' }

export function LabPage({ client, workspaceKey }: { client: ApiClient; workspaceKey: string }) {
  const api = useMemo(() => createLayaApi(client), [client])
  const initial = presets[0].request
  const [model, setModel] = useState<ModelChoice>(initial.model)
  const [mode, setMode] = useState<InputMode>('text')
  const [input, setInput] = useState(initial.state as string)
  const [drafts, setDrafts] = useState<QuestionDraft[]>(() => draftsFromQuestions(initial.questions))
  const [status, setStatus] = useState<LayaStatus | null>(null)
  const [statusError, setStatusError] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<LayaResult | null>(null)
  const [request, setRequest] = useState<LayaRequest | null>(null)
  const [records, setRecords] = useState(() => readRecords(workspaceKey))
  const [savedId, setSavedId] = useState<string | null>(null)

  useEffect(() => { setRecords(readRecords(workspaceKey)); setResult(null); setRequest(null); setSavedId(null) }, [workspaceKey])
  useEffect(() => {
    let active = true
    const refresh = () => { void api.status().then(value => { if (active) { setStatus(value); setStatusError('') } }).catch(() => { if (active) setStatusError('无法读取模型状态') }) }
    refresh()
    if (pending) { const timer = window.setInterval(refresh, 1000); return () => { active = false; window.clearInterval(timer) } }
    return () => { active = false }
  }, [api, pending])

  const invalidate = () => { setResult(null); setRequest(null); setSavedId(null); setError('') }
  const apply = (preset: typeof presets[number]) => {
    setModel(preset.request.model)
    setMode(typeof preset.request.state === 'string' ? 'text' : 'json')
    setInput(typeof preset.request.state === 'string' ? preset.request.state : JSON.stringify(preset.request.state, null, 2))
    setDrafts(draftsFromQuestions(preset.request.questions))
    invalidate()
  }
  const run = async () => {
    let body: LayaRequest
    try { body = buildRequest(model, mode, input, drafts) } catch (cause) { setError(cause instanceof Error ? cause.message : '输入无效'); return }
    setPending(true); setError(''); setResult(null); setSavedId(null)
    try {
      const answer = await api.predict(body)
      setRequest(body); setResult(answer)
    } catch (cause) {
      setError(cause instanceof DOMException && cause.name === 'TimeoutError' ? '等待模型响应超时，请检查服务状态后重试' : cause instanceof TypeError ? '无法连接本地模型服务，请检查服务状态后重试' : cause instanceof Error ? cause.message : '推理失败，请重试')
    } finally { setPending(false) }
  }
  const save = () => {
    if (!request || !result) return
    const record: ExperimentRecord = { id: crypto.randomUUID(), createdAt: new Date().toISOString(), request, result }
    try { setRecords(saveRecord(workspaceKey, record)); setSavedId(record.id); setError('') } catch { setError('本地存储空间不足，实验结果未保存') }
  }
  const restore = (record: ExperimentRecord) => {
    setModel(record.request.model); setMode(typeof record.request.state === 'string' ? 'text' : 'json')
    setInput(typeof record.request.state === 'string' ? record.request.state : JSON.stringify(record.request.state, null, 2))
    setDrafts(draftsFromQuestions(record.request.questions)); setRequest(record.request); setResult(record.result); setSavedId(record.id); setError('')
  }
  const remove = (id: string) => { try { setRecords(removeRecord(workspaceKey, id)); if (savedId === id) setSavedId(null) } catch { setError('删除记录失败，请检查本地存储') } }

  return <main className="min-h-dvh bg-canvas px-4 py-8 text-ink sm:px-6 lg:px-8"><div className="mx-auto grid w-full max-w-[1320px] gap-7">
    <header><p className="m-0 text-xs font-semibold uppercase tracking-[0.16em] text-clay">AUTOFlow / LAB</p><h1 className="mb-0 mt-2 text-3xl font-semibold">实验室</h1><p className="mb-0 mt-2 max-w-3xl text-sm text-muted">用本地模型把消息转成可观察的决策，再预览它将如何参与自动化。这里的动作只做模拟。</p></header>
    <section className="grid gap-4 rounded-card border border-line bg-surface p-5" aria-labelledby="lab-presets-heading"><div><h2 id="lab-presets-heading" className="m-0 text-lg font-semibold">Laya 决策实验</h2><p className="mb-0 mt-1 text-sm text-muted">从示例开始，或直接修改输入和问题。首次运行某个模型时需下载权重。</p></div><div className="flex flex-wrap gap-2">{presets.map(preset => <Button key={preset.id} size="sm" variant="secondary" onClick={() => apply(preset)} disabled={pending}>{preset.label}</Button>)}</div></section>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
      <section className="grid gap-6 rounded-card border border-line bg-surface p-5" aria-label="实验配置">
        <fieldset disabled={pending} className="contents">
          <div className="grid gap-2"><label className="text-sm font-semibold" htmlFor="lab-model">选择模型</label><Select id="lab-model" value={model} clearable={false} options={modelOptions} onValueChange={value => { if (value === 'auto' || value === 'english' || value === 'multilingual' || value === 'typed-decisions') { setModel(value); invalidate() } }} /><p className="m-0 text-xs text-muted">Typed Decisions 仅适合其训练过的英语工作流；中文建议使用 Router 或 Multilingual。</p></div>
          <div className="grid gap-3"><div className="flex gap-2" role="group" aria-label="输入格式"><Button size="sm" variant={mode === 'text' ? 'primary' : 'secondary'} aria-pressed={mode === 'text'} onClick={() => { setMode('text'); invalidate() }}>文本 / 邮件 / 工单</Button><Button size="sm" variant={mode === 'json' ? 'primary' : 'secondary'} aria-pressed={mode === 'json'} onClick={() => { setMode('json'); invalidate() }}>JSON 数据</Button></div><label className="grid gap-2 text-sm font-semibold" htmlFor="lab-input">待判断内容<Textarea id="lab-input" className="min-h-44 font-normal" value={input} onChange={event => { setInput(event.target.value); invalidate() }} placeholder={mode === 'json' ? '{"subject":"...","body":"..."}' : '粘贴消息、邮件或工单内容'} /></label><p className="m-0 text-xs text-muted">最多 16 KiB；具体 token 限额取决于所选模型和候选项长度。</p></div>
          <QuestionEditor drafts={drafts} onChange={value => { setDrafts(value); invalidate() }} />
        </fieldset>
        <div className="grid gap-3 border-t border-line pt-5"><Button variant="primary" loading={pending} loadingText="正在判断…" disabled={status?.busy && !pending} onClick={() => void run()}>运行 Laya 推理</Button>{status ? <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" role="status">{status.models.map(item => <span key={item.key}>{item.key}：{stateNames[item.state] ?? item.state}{item.device ? ` · ${item.device.toUpperCase()}` : ''}</span>)}</div> : null}{statusError ? <p role="alert" className="m-0 text-xs text-danger">{statusError}</p> : null}{error ? <p role="alert" className="m-0 rounded-control bg-red-50 p-3 text-sm text-red-800">{error}</p> : null}</div>
      </section>
      <div className="grid gap-6"><ResultPanel result={result} request={request} />{result ? <div className="flex flex-wrap items-center gap-3"><Button variant="secondary" onClick={save} disabled={Boolean(savedId)}>{savedId ? '已保存到本机' : '保存实验记录'}</Button><span className="text-xs text-muted">保存后，原始输入会留在此设备的当前工作区。</span></div> : null}<AutomationPreview result={result} /></div>
    </div>
    <ExperimentHistory records={records} pending={pending} onRestore={restore} onRemove={remove} />
  </div></main>
}
