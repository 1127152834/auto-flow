import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import type { components } from '../../../shared/api/generated'
import { createProjectRunsApi } from '../api'
import { createTaskArtifactApi } from '../artifact-api'
import { FailedRunFollowup } from '../components/FailedRunFollowup'
import { TaskDetail, type TaskDetailTab } from '../components/TaskDetail'
import { createTaskEvidenceApi } from '../evidence-api'
import { useRunEvents } from '../events'
import type { RunPageContext } from './RunDirectoryPage'
import { presentRunFailure } from '../presentation'
import { TaskEndPanel } from '../../environments/components/TaskEndPanel'

export type TaskDetailPageProps = RunPageContext & { taskId: string; tab: TaskDetailTab }
export function TaskDetailPage({ workspaceKey, instanceId, projectId, taskId, tab, client, disabled, onNavigate }: TaskDetailPageProps) {
  const queryClient = useQueryClient()
  const api = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId]), evidence = useMemo(() => createTaskEvidenceApi(client, projectId, taskId), [client, projectId, taskId])
  const [nodeId, setNodeId] = useState<string | null>(null), [level, setLevel] = useState<string | null>(null), [query, setQuery] = useState('')
  const [eventError, setEventError] = useState<string>()
  const [artifactPreview, setArtifactPreview] = useState<{ url: string; label: string }>()
  const [inlineScreenshot, setInlineScreenshot] = useState<{ url: string; label: string }>()
  const [artifactError, setArtifactError] = useState<string>()
  const artifactRequest = useRef<AbortController | null>(null)
  const artifactPreviewUrl = useRef<string | null>(null)
  const inlineScreenshotUrl = useRef<string | null>(null)
  const prefix = [workspaceKey, instanceId, 'project-runs', projectId, 'task', taskId]
  const detail = useQuery({ queryKey: [...prefix, 'detail'], queryFn: ({ signal }) => api.getTask(taskId, signal), enabled: !disabled })
  const attempts = useInfiniteQuery({ queryKey: [...prefix, 'attempts'], initialPageParam: 1, queryFn: ({ pageParam, signal }) => evidence.attempts(pageParam, signal), getNextPageParam: page => page.page * page.pageSize < page.total ? page.page + 1 : undefined, enabled: !disabled })
  const logs = useInfiniteQuery({ queryKey: [...prefix, 'logs', nodeId, level, query], initialPageParam: 0, queryFn: ({ pageParam, signal }) => evidence.logs(pageParam, { ...(nodeId ? { nodeId } : {}), ...(level ? { level: level as 'debug' | 'info' | 'warning' | 'error' } : {}), ...(query ? { query } : {}) }, signal), getNextPageParam: page => page.hasMore ? page.afterSequence : undefined, enabled: !disabled && tab === 'logs' })
  const outputs = useInfiniteQuery({ queryKey: [...prefix, 'outputs'], initialPageParam: 1, queryFn: ({ pageParam, signal }) => evidence.outputs(pageParam, signal), getNextPageParam: page => page.page * page.pageSize < page.total ? page.page + 1 : undefined, enabled: !disabled && tab !== 'logs' })
  const artifactApi = useMemo(() => createTaskArtifactApi(client, projectId, taskId), [client, projectId, taskId])
  const artifacts = useInfiniteQuery({ queryKey: [...prefix, 'artifacts'], initialPageParam: 1, queryFn: ({ pageParam, signal }) => artifactApi.list(pageParam, signal), getNextPageParam: page => page.page * page.pageSize < page.total ? page.page + 1 : undefined, enabled: !disabled && tab !== 'logs' })
  const terminal = Boolean(detail.data?.run.terminal)
  useRunEvents({
    client, workspaceKey, instanceId, projectId, taskId,
    runId: detail.data?.run.runId,
    disabled: disabled || terminal,
    onChange() {
      void queryClient.invalidateQueries({ queryKey: prefix })
    },
    onError: setEventError,
  })
  const inlineArtifact = artifacts.data?.pages.flatMap(page => page.items).find(item => item.kind === 'screenshot' && item.availability === 'available')
  useEffect(() => {
    if (tab !== 'evidence' || !inlineArtifact) return
    const controller = new AbortController()
    void artifactApi.content(inlineArtifact.artifactId, controller.signal).then(blob => {
      if (controller.signal.aborted) return
      if (inlineScreenshotUrl.current) URL.revokeObjectURL(inlineScreenshotUrl.current)
      const url = URL.createObjectURL(blob)
      inlineScreenshotUrl.current = url
      setInlineScreenshot({ url, label: `${inlineArtifact.purpose === 'result' ? '节点截图' : '失败截图'}：${inlineArtifact.nodeName}` })
    }).catch(caught => { if (!controller.signal.aborted) setArtifactError(presentRunFailure(caught, '截图读取失败，请重试')) })
    return () => controller.abort()
  }, [artifactApi, inlineArtifact?.artifactId, inlineArtifact?.nodeName, inlineArtifact?.purpose, tab])
  useEffect(() => () => { artifactRequest.current?.abort(); if (artifactPreviewUrl.current) URL.revokeObjectURL(artifactPreviewUrl.current); if (inlineScreenshotUrl.current) URL.revokeObjectURL(inlineScreenshotUrl.current) }, [])
  const backToTasks = () => onNavigate({ projectId, tab: 'runs', runView: 'tasks' })
  if (!detail.data) return <section className="grid gap-3 rounded-control border border-line bg-surface p-5" role={detail.error || disabled ? 'alert' : 'status'}>
    <p className="m-0">{detail.error ? `无法读取任务：${presentRunFailure(detail.error)}` : disabled ? '本地服务暂不可用，请等待连接恢复。' : '正在读取任务…'}</p>
    <div className="flex gap-2">{detail.error ? <Button onClick={() => void detail.refetch()}>重试读取</Button> : null}<Button variant="secondary" onClick={backToTasks}>返回任务目录</Button></div>
  </section>
  const attemptsPage = attempts.data?.pages.at(-1), attemptItems = attempts.data?.pages.flatMap(page => page.items) ?? []
  const logPage = logs.data?.pages.at(-1), logItems = logs.data?.pages.flatMap(page => page.items) ?? []
  const outputPage = outputs.data?.pages.at(-1), outputItems = outputs.data?.pages.flatMap(page => page.items) ?? []
  const artifactPage = artifacts.data?.pages.at(-1), artifactItems = artifacts.data?.pages.flatMap(page => page.items) ?? []
  const error = detail.error ?? attempts.error ?? (tab === 'logs' ? logs.error : tab === 'evidence' ? artifacts.error ?? outputs.error : outputs.error)
  const errorMessage = error
    ? detail.error
      ? `刷新失败，保留上次读取的任务：${presentRunFailure(error)}`
      : presentRunFailure(error)
    : undefined
  const closePreview = () => { if (artifactPreviewUrl.current) URL.revokeObjectURL(artifactPreviewUrl.current); artifactPreviewUrl.current = null; setArtifactPreview(undefined) }
  const openArtifact = async (artifact: components['schemas']['RunArtifactView']) => {
    setArtifactError(undefined)
    artifactRequest.current?.abort()
    const controller = new AbortController()
    artifactRequest.current = controller
    try {
      const blob = await artifactApi.content(artifact.artifactId, controller.signal, artifact.mediaType ?? 'image/png')
      if (controller.signal.aborted) return
      if (artifact.kind === 'file') {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = artifact.fileName || artifact.artifactId
        document.body.append(link)
        link.click()
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
        return
      }
      if (artifactPreviewUrl.current) URL.revokeObjectURL(artifactPreviewUrl.current)
      const url = URL.createObjectURL(blob)
      artifactPreviewUrl.current = url
      setArtifactPreview({ url, label: `${artifact.kind === 'image' ? '保存图片' : artifact.purpose === 'result' ? '节点截图' : '失败截图'}：${artifact.nodeName}` })
    } catch (caught) { if (!controller.signal.aborted) setArtifactError(presentRunFailure(caught, '产物读取失败，请重试')) }
  }
  const followUp = detail.data.run.status === 'failed' && detail.data.inputSnapshot.inputs.length > 0
    ? <FailedRunFollowup key={taskId} client={client} workspaceKey={workspaceKey} instanceId={instanceId} projectId={projectId} taskId={taskId} statusRevision={detail.data.task.statusRevision} disabled={disabled} onOpenBatch={batchId => onNavigate({ projectId, tab: 'runs', runView: 'batches', batchId })}/>
    : undefined
  return <>
    {eventError ? <div role="alert" className="mb-3 flex items-center justify-between gap-3 rounded-control border border-warning/30 bg-surface p-3 text-sm"><span>实时更新暂时中断：{eventError}。页面会从持久记录继续补读。</span><Button size="sm" onClick={() => { setEventError(undefined); void queryClient.invalidateQueries({ queryKey: prefix }) }}>立即补读</Button></div> : null}
    {artifactError ? <div role="alert" className="mb-3 rounded-control border border-danger/30 bg-danger/10 p-3 text-sm">产物读取失败：{artifactError}</div> : null}
    <TaskEndPanel workspaceKey={workspaceKey} instanceId={instanceId} projectId={projectId} taskId={taskId} runId={detail.data.run.runId} executionGeneration={detail.data.run.executionGeneration} inputs={detail.data.inputSnapshot.inputs} client={client} disabled={disabled} />
    <TaskDetail followUp={followUp} detail={detail.data} attempts={attemptsPage ? { ...attemptsPage, items: attemptItems } : undefined} logs={logPage ? { ...logPage, items: logItems } : undefined} outputs={outputPage ? { ...outputPage, items: outputItems } : undefined} artifacts={artifactPage ? { ...artifactPage, items: artifactItems } : undefined} inlineScreenshotUrl={inlineScreenshot?.url} inlineScreenshotLabel={inlineScreenshot?.label} selectedTab={tab} selectedNode={nodeId} level={level} query={query} loading={attempts.isLoading || (tab === 'logs' ? logs.isLoading : outputs.isLoading || artifacts.isLoading)} error={errorMessage} onTabChange={next => onNavigate({ projectId, tab: 'runs', taskId, taskTab: next })} onNodeChange={setNodeId} onLevelChange={setLevel} onQueryChange={setQuery} onOpenArtifact={artifact => void openArtifact(artifact)} onOpenRecord={target => onNavigate({ projectId, tab: 'data', tableId: target.tableId, dataTab: 'records', record: { mode: 'detail', datasetGeneration: target.datasetGeneration, recordKey: { type: target.keyType as 'text' | 'integer' | 'uuid', value: target.keyValue } } })} onLocateLog={nextNodeId => { setNodeId(nextNodeId); onNavigate({ projectId, tab: 'runs', taskId, taskTab: 'logs' }) }} onLoadMoreArtifacts={() => void artifacts.fetchNextPage()} onLoadMoreLogs={() => void logs.fetchNextPage()} onLoadMoreAttempts={() => void attempts.fetchNextPage()} onLoadMoreOutputs={() => void outputs.fetchNextPage()} onRetry={() => { void detail.refetch(); void attempts.refetch(); if (tab === 'logs') void logs.refetch(); else { void outputs.refetch(); void artifacts.refetch() } }} onBack={() => onNavigate({ projectId, tab: 'runs', runView: 'batches', batchId: detail.data.task.batchId })}/>
    <Dialog open={Boolean(artifactPreview)} onOpenChange={open => { if (!open) closePreview() }}><DialogContent className="max-w-5xl"><DialogTitle>{artifactPreview?.label ?? '运行图片'}</DialogTitle><DialogDescription>图片来自本次运行保存的本地产物。</DialogDescription>{artifactPreview ? <img className="max-h-[70vh] w-full rounded-control border border-line object-contain" src={artifactPreview.url} alt={artifactPreview.label}/> : null}</DialogContent></Dialog>
  </>
}
