import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { AndroidManagementApi, Image, Operation } from '../management-api'

type Props = {
  instanceId: string
  api: Pick<AndroidManagementApi, 'operations' | 'images' | 'registerImage' | 'pullImage' | 'operationByRequest' | 'verify' | 'deleteImage' | 'verifyImage' | 'verifyImageDelete'>
}
type DeleteDraft = { id: string; content: boolean; requestId: string; revision: number }
type VerifyDraft = { id: string; check: string; evidence: string }

const verificationLabels: Record<string, string> = { passed: '通过', failed: '失败', blocked: '阻塞', not_tested: '未测试', unknown: '未知' }

function display(value: unknown): string {
  if (Array.isArray(value)) return value.join('、')
  if (value == null || value === '') return '无'
  return String(value)
}

export function ImageManager({ api, instanceId }: Props) {
  const images = useQuery({ queryKey: ['android-management', instanceId, 'images'], queryFn: api.images })
  const [cursor, setCursor] = useState('')
  const [previous, setPrevious] = useState<string[]>([])
  const pulls = useQuery({
    queryKey: ['android-management', instanceId, 'unknown-pulls', cursor],
    queryFn: () => api.operations(`?action=pull&state=needs_verification&limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
  })
  const [name, setName] = useState('')
  const [imageId, setImageId] = useState('')
  const [reference, setReference] = useState('')
  const [pullReference, setPullReference] = useState('')
  const [operation, setOperation] = useState<Operation | null>(null)
  const [deleteDraft, setDeleteDraft] = useState<DeleteDraft | null>(null)
  const [verifyDraft, setVerifyDraft] = useState<VerifyDraft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [errorAction, setErrorAction] = useState<'register' | 'pull' | 'verifyOperation' | 'delete' | 'verifyDelete' | 'verify' | null>(null)
  const [message, setMessage] = useState('')
  const registerBody = useRef<{ id: string; name: string; reference: string } | null>(null)
  const verifyRequest = useRef<string | null>(null)
  const pullRequest = useRef<{ requestId: string; reference: string } | null>(null)

  const run = async (action: typeof errorAction, fn: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError(''); setMessage(''); setErrorAction(action)
    try { await fn(); setErrorAction(null) }
    catch (cause) {
      const conflict = cause instanceof ApiClientError && cause.status === 409
      if (action === 'delete' && cause instanceof ApiClientError && cause.code === 'ANDROID_IMAGE_DELETE_RESULT_UNKNOWN') setErrorAction('verifyDelete')
      setError(conflict ? '镜像引用或版本发生冲突，请重新读取后重试' : cause instanceof Error ? cause.message : '镜像操作结果尚未确认，请按原请求重试')
    }
    finally { setBusy(false) }
  }

  const register = () => {
    registerBody.current ??= { id: imageId.trim(), name: name.trim(), reference: reference.trim() }
    const body = registerBody.current
    return run('register', async () => { await api.registerImage(body); registerBody.current = null; setName(''); setImageId(''); setReference(''); setMessage('镜像已登记'); await images.refetch() })
  }

  const pull = () => {
    if (!pullRequest.current && (!pulls.data || pulls.isError || pulls.isFetching || pulls.data.total > 0)) return
    pullRequest.current ??= { requestId: crypto.randomUUID(), reference: pullReference.trim() }
    const request = pullRequest.current
    return run('pull', async () => {
      try {
        const next = await api.pullImage(request)
        setOperation(next)
        if (['succeeded', 'failed', 'cancelled'].includes(next.state)) pullRequest.current = null
        setMessage(`拉取操作已接受：${request.requestId}`)
      } catch (cause) {
        if (cause instanceof ApiClientError && cause.status === 422 && cause.code === 'VALIDATION_ERROR' && pullRequest.current?.requestId === request.requestId) pullRequest.current = null
        throw cause
      }
    })
  }

  const verifyOperation = (selectedRequest?: string) => {
    const requestId = selectedRequest ?? pullRequest.current?.requestId ?? operation?.requestId
    if (!requestId) return
    verifyRequest.current = requestId
    return run('verifyOperation', async () => {
      let next = await api.operationByRequest(requestId)
      setOperation(next)
      if (next.state === 'needs_verification') {
        next = await api.verify(next.operationId, { requestId })
        setOperation(next)
      }
      if (['succeeded', 'failed', 'cancelled'].includes(next.state)) {
        if (pullRequest.current?.requestId === requestId) pullRequest.current = null
        await images.refetch()
        await pulls.refetch()
        setCursor(''); setPrevious([])
      }
      setMessage('已按原请求核实拉取状态')
    })
  }

  const remove = (draft: DeleteDraft) => run('delete', async () => { await api.deleteImage(draft.id, { requestId: draft.requestId, expectedRevision: draft.revision, deleteContent: draft.content }); setDeleteDraft(null); setMessage(draft.content ? '镜像内容已删除' : '镜像登记已取消'); await images.refetch() })

  const verifyDelete = (draft: DeleteDraft) => run('verifyDelete', async () => { await api.verifyImageDelete(draft.id, { requestId: draft.requestId }); setDeleteDraft(null); setMessage('已按原请求核实镜像删除结果'); await images.refetch() })

  const verify = () => {
    if (!verifyDraft) return
    const draft = verifyDraft
    return run('verify', async () => { await api.verifyImage(draft.id, { check: draft.check.trim(), evidence: draft.evidence.trim() ? { message: draft.evidence.trim() } : {} }); setVerifyDraft(null); setMessage('已由服务端核实镜像并保存验证记录'); await images.refetch() })
  }

  const retry = () => {
    if (errorAction === 'register') return void register()
    if (errorAction === 'pull') return void pull()
    if (errorAction === 'verifyOperation') return void verifyOperation(verifyRequest.current ?? undefined)
    if (errorAction === 'delete' && deleteDraft) return void remove(deleteDraft)
    if (errorAction === 'verifyDelete' && deleteDraft) return void verifyDelete(deleteDraft)
    if (errorAction === 'verify') return void verify()
  }

  if (images.isPending) return <section role="status">正在读取镜像目录…</section>
  if (images.isError || !images.data) return <section role="alert">镜像目录暂不可用。<button type="button" onClick={() => void images.refetch()}>重新读取</button></section>
  const page = Array.isArray(images.data) ? { items: [] as Image[], total: 0 } : images.data
  return <section aria-label="镜像管理" aria-busy={busy} className="rounded-card border border-line bg-surface p-5">
    <header><h2 className="font-semibold">镜像管理</h2><p className="mt-1 text-sm text-muted">登记固定摘要；拉取仅支持 redroid/redroid（含 docker.io 前缀）的 tag 或仓库摘要。</p></header>
    <div className="mt-4 grid gap-4 lg:grid-cols-3">
      <form aria-label="登记镜像" className="grid gap-2 rounded-control border border-line p-3" onSubmit={(event) => { event.preventDefault(); void register() }}>
        <h3 className="font-medium">登记已有镜像</h3>
        <label>镜像名称<input aria-label="镜像名称" value={name} disabled={busy} onChange={(event) => { registerBody.current = null; setName(event.target.value) }} /></label>
        <label>镜像摘要<input aria-label="镜像摘要" value={imageId} disabled={busy} onChange={(event) => { registerBody.current = null; setImageId(event.target.value) }} placeholder="sha256:…" /></label>
        <label>镜像引用<input aria-label="镜像引用" value={reference} disabled={busy} onChange={(event) => { registerBody.current = null; setReference(event.target.value) }} placeholder="registry/repository:tag" /></label>
        <button type="submit" disabled={busy || !name.trim() || !imageId.trim() || !reference.trim()}>登记镜像</button>
      </form>
      <form aria-label="拉取镜像" className="grid gap-2 rounded-control border border-line p-3" onSubmit={(event) => { event.preventDefault(); void pull() }}>
        <h3 className="font-medium">受限拉取</h3>
        <label>镜像引用<input aria-label="拉取镜像引用" value={pullReference} disabled={busy || !!pullRequest.current} onChange={(event) => { pullRequest.current = null; setPullReference(event.target.value); setOperation(null) }} placeholder="redroid/redroid:13 或 redroid/redroid@sha256:…" /></label>
        <button type="submit" disabled={busy || !!pullRequest.current || !pullReference.trim() || !pulls.data || pulls.isError || pulls.isFetching || pulls.data.total > 0}>开始拉取</button>
        {operation && <div role="status" className="text-xs">拉取操作：{operation.stageLabel} · {operation.state} · {operation.requestId}<button type="button" disabled={busy} onClick={() => void verifyOperation()}>按原编号核实拉取</button></div>}
      </form>
      <div className="rounded-control border border-line p-3 text-sm"><h3 className="font-medium">目录状态</h3><p className="mt-2">已登记 {page.total} 个镜像</p><p className="mt-1 text-xs text-muted">删除登记与删除本机内容分开确认。</p></div>
    </div>
    <section aria-label="待核实的镜像拉取" className="mt-4 rounded-control border border-line p-3 text-sm">
      <h3 className="font-medium">待核实的镜像拉取</h3>
      <p className="text-xs text-muted">存在未知结果时先按原编号核实，再提交新拉取。</p>
      {pulls.isPending && <p role="status">正在读取拉取记录…</p>}
      {pulls.isError && <p role="alert">拉取记录暂不可用，请重新读取后再拉取。</p>}
      <button type="button" disabled={busy || pulls.isFetching} onClick={() => { if (cursor) { setCursor(''); setPrevious([]) } else void pulls.refetch() }}>重新读取拉取记录</button>
      {pulls.data && <>
        <ul>{pulls.data.items.map(item => <li key={item.operationId} className="mt-2 break-all">{item.requestId} · {item.stageLabel}
          <button type="button" aria-label={`核实拉取 ${item.requestId}`} disabled={busy || pulls.isError || pulls.isFetching} onClick={() => void verifyOperation(item.requestId)}>按原编号核实</button>
        </li>)}</ul>
        {!pulls.data.total && <p>没有待核实的拉取。</p>}
        <div className="mt-2 flex flex-wrap gap-3"><button type="button" aria-label="上一页拉取记录" disabled={busy || pulls.isError || pulls.isFetching || !previous.length} onClick={() => { setCursor(previous[previous.length - 1]); setPrevious(previous.slice(0, -1)) }}>上一页</button><span>第 {previous.length + 1} 页 · 共 {pulls.data.total} 项待核实</span><button type="button" aria-label="下一页拉取记录" disabled={busy || pulls.isError || pulls.isFetching || !pulls.data.nextCursor} onClick={() => { setPrevious([...previous, cursor]); setCursor(pulls.data?.nextCursor ?? '') }}>下一页</button></div>
      </>}
    </section>
    {error && <p role="alert" className="mt-3 text-sm text-danger">{error}{errorAction && <button type="button" disabled={busy} onClick={retry}>{errorAction === 'verifyDelete' ? '核实删除结果' : errorAction === 'pull' || errorAction === 'verifyOperation' ? '按原编号重试' : '按原请求重试'}</button>}</p>}
    {message && <p role="status" className="mt-3 text-sm">{message}</p>}
    <div className="mt-4 grid gap-2">{page.items.map((image) => {
      const verification = String(image.verification?.state ?? 'not_tested')
      const records = Array.isArray(image.verification?.records) ? image.verification.records : []
      const references = (image.references ?? []).map((item) => `${display(item.kind)}:${display(item.id ?? item.name)}`)
      return <article key={image.id} className="rounded-control border border-line p-3">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><strong>{image.name}</strong><p className="mt-1 break-all text-xs text-muted">{image.imageId} · {image.reference} · {image.state} · 镜像元数据核验 {verificationLabels[verification] ?? verification}</p><p className="mt-1 text-xs text-muted">组件声明 {display(image.googleComponents ?? 'unknown')} · 谷歌组件验收 {verificationLabels[image.validation ?? 'not_tested'] ?? display(image.validation)}</p></div><span className="text-xs text-muted">修订 {image.revision}</span></div>
        <p className="mt-2 text-xs text-muted">引用：{references.length ? references.join('、') : '无'}</p>
        {!!records.length && <ul className="mt-2 grid gap-1 text-xs">{records.map((record, index) => <li key={index}>验证记录：{display(record.check)} · {verificationLabels[String(record.result)] ?? display(record.result)}{typeof record.evidence === 'object' && record.evidence !== null && 'message' in record.evidence ? ` · ${display(record.evidence.message)}` : ''}</li>)}</ul>}
        <div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => setVerifyDraft({ id: image.id, check: '', evidence: '' })}>验证 {image.name}</button><button type="button" disabled={busy} onClick={() => setDeleteDraft({ id: image.id, content: false, requestId: crypto.randomUUID(), revision: image.revision })}>取消登记 {image.name}</button><button type="button" disabled={busy} onClick={() => setDeleteDraft({ id: image.id, content: true, requestId: crypto.randomUUID(), revision: image.revision })}>删除镜像内容 {image.name}</button></div>
        {verifyDraft?.id === image.id && <div role="dialog" aria-label="镜像验证" className="mt-3 grid gap-2 rounded-control bg-surface-subtle p-3"><label>检查项<input aria-label="验证检查项" value={verifyDraft.check} onChange={(event) => setVerifyDraft({ ...verifyDraft, check: event.target.value })} /></label><label>证据说明<input aria-label="验证证据" value={verifyDraft.evidence} onChange={(event) => setVerifyDraft({ ...verifyDraft, evidence: event.target.value })} /></label><div><button type="button" disabled={busy || !verifyDraft.check.trim()} onClick={() => void verify()}>服务端核实</button><button type="button" onClick={() => setVerifyDraft(null)}>取消</button></div></div>}
        {deleteDraft?.id === image.id && <div role="dialog" aria-label="镜像删除确认" className="mt-3 rounded-control bg-surface-subtle p-3 text-sm"><p>{deleteDraft.content ? '删除内容会影响本机镜像缓存' : '取消登记只移除管理目录记录，不删除本机内容'}</p><div className="mt-2"><button type="button" disabled={busy} onClick={() => void remove(deleteDraft)}>{deleteDraft.content ? '确认删除镜像内容' : '确认取消登记'}</button><button type="button" onClick={() => setDeleteDraft(null)}>取消</button></div></div>}
      </article>
    })}</div>
    {!page.items.length && <p className="mt-3 text-sm text-muted">尚未登记镜像。</p>}
  </section>
}
