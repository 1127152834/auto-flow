import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import { FormField } from '../../../shared/components/FormField'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { EmptyState } from '../../../shared/components/ui/empty-state'
import { Input } from '../../../shared/components/ui/input'
import { Progress } from '../../../shared/components/ui/progress'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import type { AiTestApi, AiTestRun, AiTestRunCreate, AiTestTarget } from '../ai-test-api'

type Props = { api: AiTestApi; target: AiTestTarget; onTakeOver?: () => void }
type Draft = Pick<AiTestRunCreate, 'instruction' | 'mode' | 'modelId' | 'maxSteps' | 'timeoutSeconds'>

const STATE_TEXT: Record<AiTestRun['state'], string> = {
  queued: '等待中', running: '运行中', succeeded: '通过', failed: '失败', cancelled: '已停止',
  needs_verification: '结果待核实：程序中断，无法确定测试是否完成',
}
const modes = [
  { value: 'flash', label: '快速（约 3–5 秒/步）' },
  { value: 'pro', label: '深度（约 15–40 秒/步）' },
]
const isActive = (state?: AiTestRun['state']) => state === 'queued' || state === 'running'
const inRange = (value: string, min: number, max: number) => /^\d+$/.test(value) && Number(value) >= min && Number(value) <= max
const message = (cause: unknown, fallback: string) => cause instanceof Error && cause.message ? cause.message : fallback

function duration(run: AiTestRun) {
  if (!run.startedAt || !run.finishedAt) return null
  const seconds = Math.max(0, Math.round((Date.parse(run.finishedAt) - Date.parse(run.startedAt)) / 1000))
  return seconds >= 60 ? `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒` : `${seconds} 秒`
}

function useVisible() {
  const [hidden, setHidden] = useState(() => document.visibilityState === 'hidden')
  useEffect(() => {
    const onChange = () => setHidden(document.visibilityState === 'hidden')
    document.addEventListener('visibilitychange', onChange)
    return () => document.removeEventListener('visibilitychange', onChange)
  }, [])
  return !hidden
}

function useBlobUrl(load: () => Promise<Blob>, key: string) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let created: string | null = null, live = true
    load().then((blob) => { if (live) setUrl(created = URL.createObjectURL(blob)) }).catch(() => undefined)
    return () => { live = false; if (created) URL.revokeObjectURL(created) }
  }, [key])
  return url
}

function Thumb({ api, runId, name }: { api: AiTestApi; runId: string; name: string }) {
  const url = useBlobUrl(() => api.artifactBlob(runId, name), `${runId}/${name}`)
  return url ? <img src={url} alt="步骤截图" className="h-16 w-9 rounded-control border border-line object-cover" /> : null
}

function Steps({ api, run }: { api: AiTestApi; run: AiTestRun }) {
  const steps = run.steps ?? []
  if (!steps.length) return <p className="m-0 text-sm text-muted">{isActive(run.state) ? '正在等待第一步…' : '没有记录到步骤'}</p>
  return <ol aria-label="测试步骤" className="m-0 grid list-none gap-2 p-0">
    {steps.map((step, i) => <li key={step.index ?? i} className="flex items-center gap-3 text-sm text-ink">
      <span className="w-6 shrink-0 text-muted">{step.index ?? i + 1}</span>
      <span className="min-w-0 flex-1">{step.summary}</span>
      {step.screenshot ? <Thumb api={api} runId={run.id} name={step.screenshot} /> : null}
    </li>)}
  </ol>
}

function LiveScreen({ api, runId, visible }: { api: AiTestApi; runId: string; visible: boolean }) {
  const shot = useQuery({ queryKey: ['android-ai-screen', runId], queryFn: () => api.screenBlob(runId), refetchInterval: visible ? 2000 : false, gcTime: 0 })
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!shot.data) return
    const created = URL.createObjectURL(shot.data)
    setUrl(created)
    return () => URL.revokeObjectURL(created)
  }, [shot.data])
  return <figure className="m-0 grid gap-1">
    <figcaption className="text-xs text-muted">实时画面（只读）</figcaption>
    {url ? <img src={url} alt="实时画面（只读）" className="max-h-96 w-fit rounded-control border border-line object-contain" />
      : <p className="m-0 text-sm text-muted">{shot.isError ? message(shot.error, '暂时无法读取设备画面') : '正在读取设备画面…'}</p>}
  </figure>
}

function Artifacts({ api, run }: { api: AiTestApi; run: AiTestRun }) {
  const save = async (name: string) => {
    const url = URL.createObjectURL(await api.artifactBlob(run.id, name))
    const link = document.createElement('a')
    link.href = url; link.download = name; link.click()
    URL.revokeObjectURL(url)
  }
  if (!run.artifacts?.length) return null
  return <div className="flex flex-wrap gap-2" aria-label="测试产物">
    {run.artifacts.map((name) => <Button key={name} size="sm" onClick={() => void save(name)}>{name}</Button>)}
  </div>
}

export function AiTestPanel({ api, target, onTakeOver }: Props) {
  const queryClient = useQueryClient(), visible = useVisible()
  const targetKey = `${target.deviceKind}:${target.deviceId ?? target.serial ?? ''}`
  const tool = useQuery({ queryKey: ['android-ai-tool'], queryFn: api.tool, refetchInterval: (q) => q.state.data?.state === 'installing' && visible ? 2000 : false })
  const models = useQuery({ queryKey: ['android-ai-models'], queryFn: api.modelOptions })
  const history = useQuery({ queryKey: ['android-ai-runs', targetKey], queryFn: () => api.runs(target) })
  const [activeId, setActiveId] = useState<string | null>(null)
  const active = useQuery({
    queryKey: ['android-ai-run', activeId], queryFn: () => api.run(activeId!), enabled: Boolean(activeId),
    refetchInterval: (q) => isActive(q.state.data?.state) && visible ? 2000 : false,
  })
  const [draft, setDraft] = useState({ instruction: '', mode: 'flash', modelId: '', maxSteps: '30', timeoutSeconds: '600' })
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [helperFor, setHelperFor] = useState<Draft | null>(null)
  const [removing, setRemoving] = useState<AiTestRun | null>(null)
  const [takingOver, setTakingOver] = useState(false)
  const taken = useRef(false)

  const options = (models.data?.items ?? []).map((item) => ({ value: item.id, label: item.displayName }))
  const modelId = draft.modelId || options[0]?.value || ''
  const run = active.data
  const running = isActive(run?.state)
  const refreshHistory = () => queryClient.invalidateQueries({ queryKey: ['android-ai-runs', targetKey] })

  // Pick up a run that is still going when the panel opens.
  useEffect(() => {
    const going = history.data?.items.find((item) => isActive(item.state))
    if (going && !activeId) setActiveId(going.id)
  }, [history.data, activeId])

  useEffect(() => {
    if (run && !isActive(run.state)) { void refreshHistory() }
    if (takingOver && run && !isActive(run.state) && !taken.current) { taken.current = true; setTakingOver(false); onTakeOver?.() }
  }, [run?.state, takingOver])

  const begin = async (input: Draft, retried = false) => {
    setBusy(true); setError('')
    try {
      const started = await api.start({ ...input, requestId: crypto.randomUUID(), deviceKind: target.deviceKind, deviceId: target.deviceId, serial: target.serial })
      queryClient.setQueryData(['android-ai-run', started.id], started)
      setActiveId(started.id)
      void refreshHistory()
    } catch (cause) {
      if (!retried && cause instanceof ApiClientError && cause.code === 'AI_TEST_HELPER_REQUIRED') setHelperFor(input)
      else setError(message(cause, '无法开始测试'))
    } finally { setBusy(false) }
  }
  const installHelper = async () => {
    const input = helperFor
    if (!input) return
    setBusy(true); setError('')
    try {
      await api.installHelper({ deviceKind: target.deviceKind, deviceId: target.deviceId, serial: target.serial })
      setHelperFor(null)
    } catch (cause) { setHelperFor(null); setError(message(cause, '测试辅助组件安装失败')); setBusy(false); return }
    setBusy(false)
    await begin(input, true)
  }
  const installTool = async () => {
    setError('')
    try { queryClient.setQueryData(['android-ai-tool'], await api.installTool({ requestId: crypto.randomUUID() })) }
    catch (cause) { setError(message(cause, '测试工具安装失败')) }
  }
  const stop = async (andTakeOver: boolean) => {
    if (!run) return
    setError(''); taken.current = false
    if (andTakeOver) setTakingOver(true)
    try { queryClient.setQueryData(['android-ai-run', run.id], await api.cancel(run.id)) }
    catch (cause) { setTakingOver(false); setError(message(cause, '无法停止测试')) }
  }
  const remove = async () => {
    const item = removing
    if (!item) return
    try {
      await api.remove(item.id)
      if (activeId === item.id) setActiveId(null)
      await refreshHistory()
    } catch (cause) { setError(message(cause, '无法删除测试记录')) }
    setRemoving(null)
  }

  const instruction = draft.instruction.trim()
  const valid = instruction.length >= 1 && instruction.length <= 4000 && Boolean(modelId)
    && inRange(draft.maxSteps, 1, 200) && inRange(draft.timeoutSeconds, 30, 3600)
  const state = tool.data?.state
  const items = history.data?.items ?? []

  return <section aria-label="AI 测试" className="grid gap-4 p-4">
    {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
    {tool.isError ? <p role="alert" className="m-0 text-sm text-danger">{message(tool.error, '无法读取测试工具状态')}</p> : null}

    {state && state !== 'ready' ? <div className="grid gap-2 rounded-control border border-line bg-surface p-3">
      {state === 'installing' ? <><p className="m-0 text-sm text-ink">正在安装测试工具…</p><Progress value={null} aria-label="安装进度" /></> : <>
        <p className="m-0 text-sm text-muted">{tool.data?.message ?? (state === 'failed' ? '测试工具安装失败' : '尚未安装测试工具')}</p>
        <div><Button variant="primary" disabled={state === 'missing_prerequisite'} onClick={() => void installTool()}>安装测试工具</Button></div>
      </>}
    </div> : null}

    {state === 'ready' ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (valid && !running) void begin({ instruction, mode: draft.mode, modelId, maxSteps: Number(draft.maxSteps), timeoutSeconds: Number(draft.timeoutSeconds) }) }}>
      <FormField label="测试指令" htmlFor="ai-test-instruction" hint="用一句话描述要在设备上完成的操作">
        <Textarea value={draft.instruction} maxLength={4000} onChange={(e) => setDraft({ ...draft, instruction: e.target.value })} />
      </FormField>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label="模式" htmlFor="ai-test-mode"><Select value={draft.mode} options={modes} clearable={false} onValueChange={(v) => setDraft({ ...draft, mode: v ?? 'flash' })} /></FormField>
        <FormField label="模型" htmlFor="ai-test-model" error={models.isError ? message(models.error, '无法读取模型列表') : options.length || models.isPending ? undefined : '请先在模型管理中添加模型'}>
          <Select value={modelId || null} options={options} clearable={false} loading={models.isPending} onValueChange={(v) => setDraft({ ...draft, modelId: v ?? '' })} />
        </FormField>
        <FormField label="步数上限" htmlFor="ai-test-steps" hint="1–200" error={inRange(draft.maxSteps, 1, 200) ? undefined : '步数需在 1 到 200 之间'}>
          <Input inputMode="numeric" value={draft.maxSteps} onChange={(e) => setDraft({ ...draft, maxSteps: e.target.value })} />
        </FormField>
        <FormField label="超时秒数" htmlFor="ai-test-timeout" hint="30–3600" error={inRange(draft.timeoutSeconds, 30, 3600) ? undefined : '超时需在 30 到 3600 秒之间'}>
          <Input inputMode="numeric" value={draft.timeoutSeconds} onChange={(e) => setDraft({ ...draft, timeoutSeconds: e.target.value })} />
        </FormField>
      </div>
      <div><Button type="submit" variant="primary" disabled={!valid || running} loading={busy}>开始测试</Button></div>
    </form> : null}

    {run ? <div className="grid gap-3 rounded-control border border-line bg-surface p-3" aria-label="当前测试">
      <div className="flex flex-wrap items-center gap-2"><Badge>{STATE_TEXT[run.state]}</Badge><span className="text-sm text-ink">{run.instruction}</span></div>
      {run.state === 'running' && target.deviceKind === 'managed' ? <LiveScreen api={api} runId={run.id} visible={visible} /> : null}
      <Steps api={api} run={run} />
      {running ? <div className="flex gap-2">
        <Button onClick={() => void stop(false)}>停止</Button>
        {onTakeOver ? <Button onClick={() => void stop(true)} loading={takingOver}>停止并接管</Button> : null}
      </div> : run.errorMessage ? <p className="m-0 text-sm text-danger">{run.errorMessage}</p> : null}
    </div> : null}

    <div className="grid gap-2">
      <h3 className="m-0 text-sm font-semibold text-ink">测试记录</h3>
      {history.isError ? <p role="alert" className="m-0 text-sm text-danger">{message(history.error, '无法读取测试记录')}</p> : null}
      {!history.isPending && !items.length && !history.isError ? <EmptyState className="min-h-32" title="还没有测试记录" description="填写指令并开始测试后，结果会保存在这里。" /> : null}
      <ul className="m-0 grid list-none gap-2 p-0">
        {items.map((item) => <li key={item.id} className="grid gap-2 rounded-control border border-line p-3">
          <div className="flex flex-wrap items-center gap-2"><Badge>{STATE_TEXT[item.state]}</Badge><span className="min-w-0 flex-1 text-sm text-ink">{item.instruction}</span></div>
          <p className="m-0 text-xs text-muted">
            {[duration(item) && `耗时 ${duration(item)}`, `${item.steps?.length ?? 0} 步`, item.modelKey ?? item.modelId].filter(Boolean).join(' · ')}
          </p>
          {item.errorMessage ? <p className="m-0 text-sm text-danger">{item.errorMessage}</p> : null}
          <Artifacts api={api} run={item} />
          <div className="flex gap-2">
            <Button size="sm" onClick={() => setActiveId(item.id)}>查看</Button>
            {!isActive(item.state) ? <>
              <Button size="sm" disabled={running || busy} onClick={() => void begin({ instruction: item.instruction, mode: item.mode, modelId: item.modelId, maxSteps: item.maxSteps, timeoutSeconds: item.timeoutSeconds })}>用相同指令重跑</Button>
              <Button size="sm" variant="ghost" onClick={() => setRemoving(item)}>删除</Button>
            </> : null}
          </div>
        </li>)}
      </ul>
    </div>

    <AlertDialog open={Boolean(helperFor)} onOpenChange={(open) => { if (!open && !busy) setHelperFor(null) }}>
      <AlertDialogContent>
        <AlertDialogTitle>需要在该设备安装测试辅助组件</AlertDialogTitle>
        <AlertDialogDescription>安装后会自动继续刚才的测试。</AlertDialogDescription>
        <div className="flex justify-end gap-2">
          <AlertDialogCancel asChild><Button disabled={busy}>取消</Button></AlertDialogCancel>
          <AlertDialogAction asChild><Button variant="primary" disabled={busy} onClick={(e) => { e.preventDefault(); void installHelper() }}>安装并继续</Button></AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
    <AlertDialog open={Boolean(removing)} onOpenChange={(open) => { if (!open) setRemoving(null) }}>
      <AlertDialogContent>
        <AlertDialogTitle>删除测试记录</AlertDialogTitle>
        <AlertDialogDescription>记录和截图将被删除，无法恢复。</AlertDialogDescription>
        <div className="flex justify-end gap-2">
          <AlertDialogCancel asChild><Button>取消</Button></AlertDialogCancel>
          <AlertDialogAction asChild><Button variant="danger" onClick={(e) => { e.preventDefault(); void remove() }}>确认删除</Button></AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  </section>
}
