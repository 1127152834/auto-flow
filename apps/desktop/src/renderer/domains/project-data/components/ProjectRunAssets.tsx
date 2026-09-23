import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Select } from '../../../shared/components/ui/select'
import { safeProjectError } from '../../projects/presentation-error'
import { createProjectRunAssetsApi, type AssetQuery, type RunAsset } from '../run-assets-api'

type Props = { workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean }
const kinds = [{ value: '', label: '全部运行数据' }, { value: 'result', label: '节点结果' }, { value: 'file', label: '结果文件' }, { value: 'diagnostic', label: '变量诊断' }]
const label = (asset: RunAsset) => `${asset.workflowName} · ${asset.nodeId} · ${asset.executionId ?? '历史执行'}`
export function ProjectRunAssets(props: Props) {
  return <Assets key={JSON.stringify([props.workspaceKey, props.instanceId, props.projectId])} {...props} />
}
function Assets({ workspaceKey, instanceId, projectId, client, disabled }: Props) {
  const api = useMemo(() => createProjectRunAssetsApi(client, projectId), [client, projectId])
  const [query, setQuery] = useState<AssetQuery>({ kind: '', nodeId: '', runId: '', cursor: 0 })
  const [selected, setSelected] = useState<RunAsset | null>(null)
  const [preview, setPreview] = useState<{ url?: string; text?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showLogs, setShowLogs] = useState(false)
  const [logCursor, setLogCursor] = useState(0)
  const request = useRef<AbortController | null>(null)
  const objectUrl = useRef<string | null>(null)
  const prefix = [workspaceKey, instanceId, 'project-data', projectId, 'run-assets']
  const page = useQuery({ queryKey: [...prefix, query], queryFn: ({ signal }) => api.list(query, signal), enabled: !disabled })
  const logs = useQuery({ queryKey: [...prefix, 'logs', selected?.assetId, logCursor], queryFn: ({ signal }) => api.logs(selected!, logCursor, signal), enabled: !disabled && showLogs && Boolean(selected) })
  useEffect(() => () => { request.current?.abort(); if (objectUrl.current) URL.revokeObjectURL(objectUrl.current) }, [client, disabled])
  const close = () => {
    request.current?.abort()
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
    objectUrl.current = null; setPreview(null); setSelected(null); setError(null); setLoading(false); setShowLogs(false); setLogCursor(0)
  }
  const load = async (asset: RunAsset, download = false) => {
    close(); setSelected(asset); setLoading(true)
    const controller = new AbortController(); request.current = controller
    try {
      if (!download && asset.size !== null && asset.size > 10 * 1024 * 1024) {
        setPreview({ text: '文件大于 10 MiB，请下载查看完整内容。' }); return
      }
      const blob = await api.content(asset, controller.signal)
      if (controller.signal.aborted) return
      const image = /^image\/(png|jpeg|webp|gif)$/.test(asset.mimeType)
      if (download || image) {
        const url = URL.createObjectURL(blob); objectUrl.current = url
        if (download) {
          const a = document.createElement('a'); a.href = url
          const extension = asset.mimeType === 'image/png' ? 'png' : asset.mimeType === 'application/json' ? 'json' : 'bin'
          a.download = `${asset.runId}-${asset.artifactId ?? asset.sequence}.${extension}`; a.click()
        } else setPreview({ url })
      } else if (/^(application\/(json|x-ndjson)|text\/)/.test(asset.mimeType)) {
        const text = await blob.text()
        if (!controller.signal.aborted) setPreview({ text: text.length > 100000 ? `${text.slice(0, 100000)}\n…预览仅显示前 100,000 字符，下载可获取完整内容。` : text })
      } else setPreview({ text: '此文件类型请下载查看。' })
    } catch (caught) { if (!controller.signal.aborted) setError(safeProjectError(caught)) }
    finally { if (!controller.signal.aborted) setLoading(false) }
  }
  return <section aria-label="自动化运行数据" className="grid gap-3 rounded-card border border-line bg-surface p-4">
    <div className="flex flex-wrap items-center gap-3">
      <Select aria-label="运行数据类型" value={query.kind} clearable={false} options={kinds} onValueChange={kind => { close(); setQuery({ ...query, kind: kind as AssetQuery['kind'], cursor: 0 }) }} />
      <Input aria-label="筛选运行 ID" placeholder="运行 ID" value={query.runId} onChange={event => { close(); setQuery({ ...query, runId: event.target.value, cursor: 0 }) }} />
      <Input aria-label="筛选节点 ID" placeholder="节点 ID" value={query.nodeId} onChange={event => { close(); setQuery({ ...query, nodeId: event.target.value, cursor: 0 }) }} />
      <Button disabled={disabled || page.isFetching} onClick={() => void page.refetch()}>刷新运行数据</Button>
    </div>
    {page.isPending ? <p role="status">正在读取运行数据…</p> : null}
    {page.error ? <p role="alert">{safeProjectError(page.error)}</p> : null}
    {page.data?.items.length === 0 ? <p>没有匹配的运行数据</p> : null}
    <ul className="grid gap-2">{page.data?.items.map(asset => <li key={asset.assetId} className="flex flex-wrap items-center justify-between gap-3 border-b border-line py-3">
      <div className="min-w-0"><p className="break-all">{label(asset)}</p><p className="break-all text-sm text-muted">{kinds.find(item => item.value === asset.kind)?.label} · {asset.mimeType} · {asset.size === null ? '按需读取' : `${asset.size} 字节`} · <time>{asset.createdAt ?? '历史记录未保存时间'}</time></p><p className="break-all text-xs text-muted">运行：{asset.runId}</p></div>
      <div className="flex gap-2"><Button aria-label={`预览 ${asset.assetId}`} disabled={disabled} onClick={() => void load(asset)}>预览</Button><Button aria-label={`下载 ${asset.assetId}`} disabled={disabled} onClick={() => void load(asset, true)}>下载</Button><Button aria-label={`日志 ${asset.assetId}`} disabled={disabled} onClick={() => { close(); setSelected(asset); setShowLogs(true) }}>查看节点日志</Button></div>
    </li>)}</ul>
    {page.data ? <Pagination offset={query.cursor} limit={50} total={page.data.total} count={page.data.items.length} disabled={disabled || page.isFetching} onOffsetChange={cursor => { close(); setQuery({ ...query, cursor }) }} /> : null}
    {selected ? <section aria-label="运行数据详情" className="grid gap-2 border-t border-line pt-3"><div className="flex justify-between gap-3"><p className="break-all">{label(selected)} · 运行 {selected.runId} · 事件 {selected.sequence}</p><Button onClick={close}>关闭详情</Button></div>
      {loading ? <p role="status">正在读取内容…</p> : null}{error ? <p role="alert">{error}</p> : null}
      {preview?.url ? <img className="max-h-[560px] max-w-full object-contain" src={preview.url} alt={`运行截图 ${selected.nodeId}`} /> : null}
      {preview?.text ? <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all">{preview.text}</pre> : null}
      {showLogs && logs.isPending ? <p role="status">正在读取节点日志…</p> : null}
      {showLogs && logs.error ? <p role="alert">{safeProjectError(logs.error)}</p> : null}
      {showLogs && logs.data ? <><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all">{logs.data.items.map(item => JSON.stringify(item)).join('\n') || '暂无节点日志'}</pre><Pagination offset={logCursor} limit={100} total={logs.data.total} count={logs.data.items.length} disabled={disabled || logs.isFetching} onOffsetChange={setLogCursor} /></> : null}
    </section> : null}
  </section>
}
