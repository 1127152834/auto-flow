import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowCounterClockwise, ArrowClockwise, Check, FloppyDisk, FolderOpen, List, Plus, Trash, WarningCircle, X } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { useApi } from '../../../app/ApiProvider'
import { createWorkflowApi } from '../api'
import { addNode, connectNodes, deleteSelection, documentSignature, patchNode, pasteNodes, referencedVariables, renameVariable, signature } from '../editor-model'
import { collectIssues } from '../diagnostics'
import { useWorkflowEditor } from '../hooks/useWorkflowEditor'
import { NodeCatalog } from '../components/NodeCatalog'
import { NodeInspector } from '../components/NodeInspector'
import { VariablePanel } from '../components/VariablePanel'
import { WorkflowCanvas } from '../components/WorkflowCanvas'
import { RunToolbar } from '../components/RunToolbar'
import { RunPanel } from '../components/RunPanel'
import { createWorkflowRunApi } from '../run-api'
import { useWorkflowRun } from '../hooks/useWorkflowRun'
import type { Point, WorkflowContent } from '../types'

type LeaveReason = 'close' | 'quit' | 'workspace' | 'new' | 'open'
type Props = { connected: boolean; locked: boolean; registerLeave(handler: ((reason: LeaveReason) => Promise<boolean>) | null): void }

function isTextTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest('input,textarea,select,[contenteditable="true"],[role="textbox"],[role="dialog"]'))
}

export function StudioPage({ connected, locked: externalLocked, registerLeave }: Props) {
  const [opening, setOpening] = useState(false)
  const openingRef = useRef(false)
  const alive = useRef(true)
  const locked = externalLocked || opening
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const { client, profiles } = useApi()
  const api = useMemo(() => createWorkflowApi(client), [client])
  const runApi = useMemo(() => createWorkflowRunApi(client), [client])
  const run = useWorkflowRun(runApi, connected)
  const runRef = useRef(run)
  runRef.current = run
  const profilesQuery = useQuery({ queryKey: ['workflows', 'run-profiles'], queryFn: profiles.list, enabled: connected })
  const [profileId, setProfileId] = useState('')
  const queryClient = useQueryClient()
  const catalogQuery = useQuery({ queryKey: ['workflows', 'catalog'], queryFn: api.catalog, enabled: connected, staleTime: Infinity })
  const catalog = catalogQuery.data?.items ?? []
  const editor = useWorkflowEditor(api, connected && !locked)
  const editorRef = useRef(editor)
  editorRef.current = editor
  const [selection, setSelection] = useState({ nodes: [] as string[], edges: [] as string[] })
  const [tab, setTab] = useState('properties')
  const [catalogVisible, setCatalogVisible] = useState(true)
  const [openDialog, setOpenDialog] = useState(false)
  const [search, setSearch] = useState('')
  const [deletingVariable, setDeletingVariable] = useState<string | null>(null)
  const [leave, setLeave] = useState<{ reason: LeaveReason; dirty: boolean; active: boolean; resolve(result: boolean): void } | null>(null)
  const leaveRef = useRef<typeof leave>(null)
  const checkingLeave = useRef(false)
  const [leaving, setLeaving] = useState(false)
  const [locate, setLocate] = useState<{ nodeId: string; request: number; document: string } | null>(null)
  const clipboard = useRef<{ content: WorkflowContent; nodes: string[]; copies: number } | null>(null)
  const pointer = useRef<Point>({ x: 100, y: 100 })
  const listQuery = useQuery({ queryKey: ['workflows', 'list'], queryFn: api.list, enabled: openDialog && connected })
  const validationMatches = Boolean(run.validation && documentSignature(editor.content.document, catalog) === documentSignature(run.validation.document, catalog))
  const issues = useMemo(() => [...collectIssues(editor.content, catalog), ...validationMatches ? run.validation?.issues ?? [] : []], [editor.content, catalog, run.validation, validationMatches])
  const selectedNode = editor.content.document.nodes.find(node => selection.nodes.includes(node.id)) ?? null
  const sameDocument = Boolean(run.run && documentSignature(editor.content.document, catalog) === documentSignature(run.run.document, catalog))
  const runMarkers = useMemo(() => {
    if (!sameDocument || !run.run) return undefined
    const terminal = ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(run.run.state)
    const markers: Record<string, string> = Object.fromEntries(run.run.nodeOrder.map(id => [id, terminal ? '未执行' : '待执行']))
    for (const id of run.run.completedNodeIds) markers[id] = '已完成'
    if (run.run.currentNodeId && !run.run.completedNodeIds.includes(run.run.currentNodeId)) markers[run.run.currentNodeId] = run.run.state === 'failed' ? '失败' : run.run.state === 'cancelled' ? '已停止' : run.run.state === 'interrupted' ? '已中断' : run.run.state === 'stopping' ? '停止中' : '执行中'
    for (const event of run.events) if (event.type === 'node_failed' && event.nodeId) markers[event.nodeId] = '失败'
    if (run.run.error?.nodeId) markers[run.run.error.nodeId] = '失败'
    return markers
  }, [run.run, run.events, sameDocument])

  const select = useCallback((nodes: string[] | null, edges: string[] | null) => {
    setSelection(previous => {
      const next = { nodes: nodes ?? previous.nodes, edges: edges ?? previous.edges }
      return JSON.stringify(previous) === JSON.stringify(next) ? previous : next
    })
  }, [])
  const clearSelection = () => setSelection({ nodes: [], edges: [] })
  const commitFocusedField = () => {
    if (document.activeElement instanceof HTMLElement && document.activeElement.matches('input,textarea')) document.activeElement.blur()
    editorRef.current.endEdit()
  }
  const save = async () => {
    commitFocusedField()
    const successful = await editorRef.current.save()
    if (successful) await queryClient.invalidateQueries({ queryKey: ['workflows', 'list'] })
    return successful
  }
  const prepareLeave = useCallback(async (reason: LeaveReason): Promise<boolean> => {
    if (openingRef.current || leaveRef.current || checkingLeave.current) return false
    checkingLeave.current = true
    commitFocusedField()
    await editorRef.current.waitForSave()
    const active = await runRef.current.verifyActive()
    checkingLeave.current = false
    if (!alive.current || leaveRef.current || active === null) return false
    const dirty = editorRef.current.isDirty()
    if (!dirty && !active) return true
    return new Promise(resolve => {
      const request = { reason, dirty, active, resolve }
      leaveRef.current = request
      setLeave(request)
    })
  }, [])
  const finishLeave = (result: boolean) => { leaveRef.current?.resolve(result); leaveRef.current = null; setLeave(null) }
  const continueLeave = async (saveFirst: boolean) => {
    if (leaving || !leaveRef.current) return
    setLeaving(true)
    try {
      if (saveFirst && !await save()) return
      if (await runRef.current.stop()) finishLeave(true)
    } finally { if (alive.current) setLeaving(false) }
  }
  const startRun = () => {
    if (locked || checkingLeave.current || leaveRef.current) return
    commitFocusedField()
    if (document.querySelector('[data-pending-variable-rename="true"]')) { editorRef.current.setMessage('变量名称尚未成功修改，请修正后再运行'); setTab('variables'); return }
    void runRef.current.start(structuredClone(editorRef.current.current()), profileId)
  }
  useEffect(() => {
    registerLeave(prepareLeave)
    return () => { registerLeave(null); leaveRef.current?.resolve(false); leaveRef.current = null }
  }, [prepareLeave, registerLeave])

  const add = (type: string, position?: Point) => {
    if (locked) return
    const definition = catalog.find(item => item.type === type)
    if (!definition) return
    let id = ''
    editor.mutate(content => { const next = addNode(content, definition, position ?? { x: 80 + (content.document.nodes.length % 3) * 270, y: 100 + Math.floor(content.document.nodes.length / 3) * 160 }); id = next.document.nodes.at(-1)!.id; return next })
    select([id], [])
    setTab('properties')
  }
  const removeSelected = () => { if (!locked) { editor.mutate(content => deleteSelection(content, selection.nodes, selection.edges)); clearSelection() } }
  const copy = (cut: boolean) => {
    if (!selection.nodes.length || locked) return
    clipboard.current = { content: structuredClone(editor.current()), nodes: [...selection.nodes], copies: 0 }
    if (cut) removeSelected()
  }
  const paste = () => {
    const copied = clipboard.current
    if (!copied || locked) return
    copied.copies += 1
    let ids: string[] = []
    editor.mutate(content => { const result = pasteNodes(content, copied.content, copied.nodes, { x: pointer.current.x + copied.copies * 24, y: pointer.current.y + copied.copies * 24 }); ids = result.ids; return result.content })
    select(ids, [])
  }
  const newFlow = async () => { if (!locked && await prepareLeave('new')) { editor.replace(); clearSelection() } }
  const showOpen = async () => { if (!locked && connected && await prepareLeave('open')) { setSearch(''); setOpenDialog(true) } }
  const openFlow = async (id: string) => {
    if (openingRef.current || locked || !connected || editor.saving) return
    const before = signature(editor.current())
    openingRef.current = true
    setOpening(true)
    try {
      const record = await api.get(id)
      if (!alive.current) return
      if (signature(editorRef.current.current()) !== before) { editor.setMessage('打开期间流程发生变化，当前草稿已保留，请重新打开'); return }
      editor.replace(record); clearSelection(); setOpenDialog(false)
    }
    catch (error) { editor.setMessage(error instanceof Error ? error.message : '无法打开流程，当前内容已保留') }
    finally { openingRef.current = false; if (alive.current) setOpening(false) }
  }

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      const command = event.ctrlKey || event.metaKey
      if (command && event.key.toLowerCase() === 's') { event.preventDefault(); if (!locked && !leave && !openDialog && !deletingVariable) void save(); return }
      if (locked || isTextTarget(event.target)) return
      const key = event.key.toLowerCase()
      if (command && key === 'z') { event.preventDefault(); if (event.shiftKey) editor.redo(); else editor.undo() }
      else if (command && key === 'y') { event.preventDefault(); editor.redo() }
      else if (command && key === 'c') { event.preventDefault(); copy(false) }
      else if (command && key === 'x') { event.preventDefault(); copy(true) }
      else if (command && key === 'v') { event.preventDefault(); paste() }
      else if (command && key === 'a') { event.preventDefault(); select(editor.content.document.nodes.map(node => node.id), []) }
      else if (key === 'delete' || key === 'backspace') { event.preventDefault(); removeSelected() }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  })

  const changeVariableName = (oldName: string, name: string) => {
    const trimmed = name.trim()
    if (!trimmed || editor.content.document.variables.some(variable => variable.name === trimmed && variable.name !== oldName)) { editor.setMessage('变量名称不能为空或重复'); return }
    editor.endEdit()
    editor.mutate(content => renameVariable(content, oldName, trimmed))
  }
  const deleteVariable = (name: string) => {
    const content = editor.current()
    const references = referencedVariables({ nodes: content.document.nodes.map(node => node.config), variables: content.document.variables.filter(variable => variable.name !== name).map(variable => variable.value) })
    if (references.includes(name)) setDeletingVariable(name)
    else editor.mutate(c => ({ ...c, document: { ...c.document, variables: c.document.variables.filter(v => v.name !== name) } }))
  }
  const renameInputId = 'workflow-name'

  return <div className="flex h-dvh min-h-0 flex-col bg-canvas text-ink" aria-label="工作流工作台">
    <header className="flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        <Button variant="ghost" aria-label={catalogVisible ? '收起动作库' : '展开动作库'} onClick={() => setCatalogVisible(v => !v)}><List size={19} /></Button>
        <span className="mr-2 hidden text-sm font-semibold xl:inline">工作流工作台</span>
        <Button variant="ghost" disabled={locked || editor.saving} onClick={() => void newFlow()}><Plus size={16} />新建</Button>
        <Button variant="ghost" disabled={!connected || locked || editor.saving} onClick={() => void showOpen()}><FolderOpen size={17} />打开</Button>
        <label className="sr-only" htmlFor={renameInputId}>流程名称</label>
        <Input id={renameInputId} value={editor.content.document.name} disabled={locked} onFocus={editor.beginEdit} onBlur={editor.endEdit} onChange={event => editor.mutate(c => ({ ...c, document: { ...c.document, name: event.target.value } }))} className="w-44 border-transparent bg-transparent font-semibold hover:border-line focus:border-line lg:w-56" />
      </div>
      <div className="flex items-center gap-1.5">
        <span role="status" className="mr-2 flex items-center gap-1 text-xs text-muted">{editor.saving ? '正在保存…' : editor.dirty ? '有未保存修改' : editor.saved ? <><Check size={14} />已保存</> : '尚未保存'}</span>
        <Button variant="ghost" aria-label="撤销" title="撤销 Ctrl/Cmd+Z" disabled={locked || !editor.history.past.length} onClick={editor.undo}><ArrowCounterClockwise size={18} /></Button>
        <Button variant="ghost" aria-label="重做" title="重做 Ctrl/Cmd+Shift+Z" disabled={locked || !editor.history.future.length} onClick={editor.redo}><ArrowClockwise size={18} /></Button>
        <Button variant="ghost" aria-label="删除选中项" disabled={locked || !(selection.nodes.length || selection.edges.length)} onClick={removeSelected}><Trash size={17} /></Button>
        <Button variant="primary" disabled={!connected || locked || editor.saving} onClick={() => void save()}><FloppyDisk size={17} />保存</Button>
      </div>
    </header>
    <RunToolbar profiles={profilesQuery.data?.items ?? []} profileId={profileId} onProfileChange={setProfileId} active={run.active} busy={run.busy} uncertain={run.uncertain} disabled={!connected || locked || Boolean(leave)} profilesLoading={profilesQuery.isPending} profilesError={profilesQuery.isError} onStart={startRun} onStop={() => void run.stop()} onRefresh={() => { void run.refresh(); void profilesQuery.refetch() }} canRetryStart={run.canRetryStart} onRetryStart={() => void run.retryStart()} />
    {run.validation?.issues.length ? <div className="max-h-28 shrink-0 overflow-y-auto border-b border-red-200 bg-red-50 px-5 py-2 text-xs text-red-800" aria-label="运行校验问题">{run.validation.issues.map((issue, index) => <p key={index} className="flex items-center gap-2"><span>{issue.message} · {issue.path.join(' / ')}</span>{issue.nodeId ? <Button variant="ghost" className="h-7 text-xs" disabled={!validationMatches || locked} onClick={() => { select([issue.nodeId!], []); setTab('properties'); setLocate(previous => ({ nodeId: issue.nodeId!, request: (previous?.request ?? 0) + 1, document: documentSignature(editor.content.document, catalog) })) }}>定位 {run.validation!.document.nodes.find(node => node.id === issue.nodeId)?.label || issue.nodeId}</Button> : null}</p>)}</div> : null}
    {editor.message ? <div role="alert" className="flex shrink-0 items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-950"><span>{editor.message}</span><div className="flex shrink-0 gap-2">{editor.conflict ? <><Button disabled={!connected || locked || editor.saving} onClick={() => void editor.saveAsNew()}>另存为新流程</Button><Button disabled={!connected || locked || opening} onClick={() => void prepareLeave('open').then(ready => { if (ready) void openFlow(editor.content.document.id) })}>重新加载并放弃修改</Button></> : null}<Button variant="ghost" aria-label="关闭提示" onClick={() => editor.setMessage(null)}><X size={15} /></Button></div></div> : null}
    {catalogQuery.isError ? <div role="alert" className="flex items-center justify-between border-b border-line bg-surface px-5 py-2 text-sm">动作库加载失败，现有编辑内容已保留。<Button variant="ghost" disabled={!connected} onClick={() => void catalogQuery.refetch()}>重新加载动作库</Button></div> : null}
    <div className="flex min-h-0 flex-1">
      {catalogVisible ? <aside className="w-[230px] shrink-0 overflow-y-auto border-r border-line bg-surface max-[1050px]:w-[190px]" aria-label="动作库"><NodeCatalog items={catalog} onAdd={add} disabled={locked || !catalog.length} />{catalogQuery.isPending ? <p role="status" className="px-4 text-sm text-muted">正在加载动作库…</p> : null}</aside> : null}
      <WorkflowCanvas key={`${editor.content.document.id}:${editor.documentSession}`} content={editor.content} catalog={catalog} issues={issues} selectedNodes={selection.nodes} selectedEdges={selection.edges} disabled={locked} runMarkers={runMarkers} locate={locate?.document === documentSignature(editor.content.document, catalog) ? locate : null}
        onSelect={select} onEditStart={editor.beginEdit} onEditEnd={editor.endEdit} onPointer={point => { pointer.current = point }} onAdd={add}
        onMove={positions => editor.mutate(c => ({ ...c, layout: { ...c.layout, nodes: { ...c.layout.nodes, ...positions } } }))}
        onViewport={viewport => { if (!locked) editor.mutate(c => ({ ...c, layout: { ...c.layout, viewport } })) }}
        onConnect={(source, target) => { const result = connectNodes(editor.current(), source, target); if (result.error) editor.setMessage(result.error); else editor.mutate(() => result.content) }} />
      <aside className="flex w-[310px] shrink-0 flex-col overflow-hidden border-l border-line bg-surface max-[1050px]:w-[280px]" aria-label="配置面板">
        <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
          <TabsList className="m-3 shrink-0"><TabsTrigger value="properties">节点属性</TabsTrigger><TabsTrigger value="variables">流程变量 <span className="ml-1 text-xs">{editor.content.document.variables.length}</span></TabsTrigger></TabsList>
          <TabsContent value="properties" className="min-h-0 flex-1 overflow-y-auto"><NodeInspector node={selectedNode} definition={catalog.find(d => d.type === selectedNode?.type)} variables={editor.content.document.variables} issues={issues.filter(i => i.nodeId === selectedNode?.id)} disabled={locked} onEditStart={editor.beginEdit} onEditEnd={editor.endEdit} onChange={config => { if (selectedNode) editor.mutate(c => patchNode(c, selectedNode.id, { config })) }} onLabelChange={label => { if (selectedNode) editor.mutate(c => patchNode(c, selectedNode.id, { label })) }} /></TabsContent>
          <TabsContent value="variables" forceMount className="min-h-0 flex-1 overflow-y-auto data-[state=inactive]:hidden"><VariablePanel variables={editor.content.document.variables} disabled={locked} onEditStart={editor.beginEdit} onEditEnd={editor.endEdit} onChange={variables => editor.mutate(c => ({ ...c, document: { ...c.document, variables } }))} onRename={changeVariableName} onDelete={deleteVariable} />{issues.filter(i => i.nodeId === null).map((issue, index) => <p key={index} className="px-4 pb-2 text-xs text-amber-800">{issue.message}</p>)}</TabsContent>
        </Tabs>
        <div className="border-t border-line px-4 py-3 text-xs text-muted">{editor.content.document.nodes.length} 个节点 · {editor.content.document.edges.length} 条连线{issues.length ? <span className="mt-2 flex items-center gap-1 text-amber-800"><WarningCircle size={13} />{issues.length} 项待完成 · 可以保存进度</span> : null}</div>
      </aside>
    </div>
    <RunPanel run={run.run} events={run.events} history={run.history} nextOffset={run.nextOffset} sameDocument={sameDocument} connected={connected} message={run.message} api={runApi} onSelect={run.select} onMore={() => void run.more()} onLocate={id => { if (sameDocument) { select([id], []); setTab('properties'); setLocate(previous => ({ nodeId: id, request: (previous?.request ?? 0) + 1, document: documentSignature(editor.content.document, catalog) })) } }} />
    <Dialog open={Boolean(leave)} onOpenChange={open => { if (!open && !editor.saving && !leaving) finishLeave(false) }} busy={editor.saving || leaving}>
      <DialogContent><DialogTitle>{leave?.active ? '停止运行后离开？' : '保存当前流程的修改？'}</DialogTitle><DialogDescription>{leave?.dirty ? `“${editor.content.document.name || '未命名流程'}”有未保存内容。` : ''}{leave?.active ? '当前工作区仍有运行，浏览器清理完成后才会继续。' : '保存成功后才会继续离开。'}</DialogDescription>{editor.message || run.message ? <p role="alert" className="text-sm text-red-700">{editor.message || run.message}</p> : null}<div className="flex justify-end gap-2"><Button disabled={editor.saving || leaving} onClick={() => finishLeave(false)}>取消</Button>{leave?.dirty ? <><Button disabled={(!connected && leave.active) || editor.saving || leaving} onClick={() => void continueLeave(false)}>{leave.active ? '放弃并停止' : '放弃修改'}</Button><Button variant="primary" disabled={!connected || locked || editor.saving || leaving} onClick={() => void continueLeave(true)}>{editor.saving ? '保存中…' : leave.active ? '保存并停止' : '保存并继续'}</Button></> : <Button variant="primary" disabled={!connected || leaving} onClick={() => void continueLeave(false)}>停止并继续</Button>}</div>{leaving && !editor.saving ? <p role="status" className="text-xs text-muted">正在确认运行停止与浏览器清理…</p> : null}</DialogContent>
    </Dialog>
    <Dialog open={openDialog} onOpenChange={setOpenDialog} busy={opening}><DialogContent><DialogTitle>打开工作流</DialogTitle><DialogDescription>当前工作区中已保存的流程，按最近修改排序。</DialogDescription><Input aria-label="搜索工作流" placeholder="搜索流程名称" value={search} onChange={event => setSearch(event.target.value)} />{editor.message ? <p role="alert" className="text-sm text-red-700">{editor.message}</p> : null}<div className="max-h-80 space-y-1 overflow-y-auto">{listQuery.isPending ? <p role="status">正在加载…</p> : listQuery.isError ? <p role="alert">无法读取流程列表，请恢复连接后重试。</p> : listQuery.data?.items.filter(item => item.name.toLowerCase().includes(search.toLowerCase())).map(item => <button type="button" key={item.id} disabled={opening || !connected || locked} onClick={() => void openFlow(item.id)} className="flex w-full items-center justify-between gap-4 rounded-control px-3 py-3 text-left hover:bg-surface-hover disabled:opacity-50"><span className="truncate text-sm font-medium">{item.name}</span><time className="shrink-0 text-xs text-muted">{new Date(item.updatedAt).toLocaleString()}</time></button>)}{listQuery.data?.items.length === 0 ? <p className="py-6 text-center text-sm text-muted">还没有保存的流程</p> : null}</div>{opening ? <p role="status">正在打开…</p> : null}<Button onClick={() => setOpenDialog(false)} disabled={opening}>关闭</Button></DialogContent></Dialog>
    <Dialog open={deletingVariable !== null} onOpenChange={open => { if (!open) setDeletingVariable(null) }}><DialogContent><DialogTitle>删除被引用的变量？</DialogTitle><DialogDescription>“{deletingVariable}”仍被流程引用。删除后引用文本会保留，并标记缺失变量；可以撤销此次删除。</DialogDescription><div className="flex justify-end gap-2"><Button onClick={() => setDeletingVariable(null)}>取消</Button><Button variant="danger" disabled={locked} onClick={() => { editor.mutate(c => ({ ...c, document: { ...c.document, variables: c.document.variables.filter(v => v.name !== deletingVariable) } })); setDeletingVariable(null) }}>删除变量</Button></div></DialogContent></Dialog>
  </div>
}
