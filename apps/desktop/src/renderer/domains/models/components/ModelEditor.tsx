import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AiModel, ModelDiscoveryRead, ModelInput, ModelProvider, ModelTestResult } from '../model'
import { modelKeys } from '../model'
import type { ModelApi } from '../api'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { FormField } from '../../../shared/components/FormField'
import { ModelDeleteDialog } from './ModelDeleteDialog'
import { ModelForm, mergeModelTags, type ModelDraft } from './ModelForm'
import { ModelIdInput } from './ModelIdInput'
import { ModelTestPanel } from './ModelTestPanel'
import { refreshAfterModelConflict } from '../cache'

const initialDraft = (model?: AiModel | null): ModelDraft => ({ modelKey: model?.modelKey ?? '', displayName: model?.displayName ?? '', contextWindow: model?.contextWindow?.toString() ?? '', tags: model?.tagsJson ?? [], tagDraft: '', description: model?.description ?? '' })

export function ModelEditor({ open, onOpenChange, provider, model, api, onSaved, onRemoved, instanceId }: { open: boolean; onOpenChange(open: boolean): void; provider: ModelProvider; model?: AiModel | null; api: ModelApi; onSaved(model: AiModel): void; onRemoved(): void; instanceId: string }) {
  const cache = useQueryClient()
  const [draft, setDraft] = useState(() => initialDraft(model))
  const [validation, setValidation] = useState('')
  const [copyFeedback, setCopyFeedback] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [testState, setTestState] = useState<{ pending: boolean; key?: string; result?: ModelTestResult; error?: string; checkedAt?: string }>({ pending: false })
  const session = useRef(0)
  const testGeneration = useRef(0)
  const displayNameAutomatic = useRef(!model)
  const wasOpen = useRef(open)
  const currentKey = useRef(draft.modelKey.trim())
  currentKey.current = draft.modelKey.trim()
  useEffect(() => {
    if (open && !wasOpen.current) { session.current += 1; testGeneration.current += 1; displayNameAutomatic.current = !model; setDraft(initialDraft(model)); setValidation(''); setCopyFeedback(''); setTestState({ pending: false }) }
    if (!open && wasOpen.current) session.current += 1
    wasOpen.current = open
    return () => { session.current += 1 }
  }, [open, model])

  const discovery = useQuery({ queryKey: modelKeys.discovery(instanceId, provider.id), queryFn: ({ signal }) => api.discoverModels(provider.id, signal), enabled: open && !model, staleTime: 30_000, retry: false, refetchOnWindowFocus: false })
  const save = useMutation({ mutationFn: (input: ModelInput) => model ? api.updateModel(model.id, input) : api.createModel(provider.id, input), retry: false, onSuccess: (saved) => { onSaved(saved); onOpenChange(false) }, onError: (error) => refreshAfterModelConflict(cache, instanceId, error) })
  const test = async () => {
    const key = draft.modelKey.trim(); const requestSession = session.current; const requestGeneration = ++testGeneration.current
    setTestState({ pending: true, key })
    try { const result = await api.testModel(provider.id, { modelKey: key }); if (session.current === requestSession && testGeneration.current === requestGeneration && currentKey.current === key) setTestState({ pending: false, key, result, checkedAt: new Date().toLocaleTimeString('zh-CN', { hour12: false }) }) }
    catch (error) { refreshAfterModelConflict(cache, instanceId, error); if (session.current === requestSession && testGeneration.current === requestGeneration && currentKey.current === key) setTestState({ pending: false, key, error: error instanceof Error ? error.message : '测试失败' }) }
  }
  const submit = () => {
    const raw = draft.contextWindow.trim(); const contextWindow = raw ? Number(raw) : null
    if (contextWindow !== null && (!Number.isSafeInteger(contextWindow) || contextWindow < 1)) { setValidation('上下文窗口必须是正安全整数，或留空。'); return }
    const modelKey = draft.modelKey.trim(); const displayName = draft.displayName.trim()
    if (!modelKey || !displayName) { setValidation('请填写模型标识和显示名称。'); return }
    setValidation(''); save.mutate({ modelKey, displayName, tagsJson: mergeModelTags(draft.tags, draft.tagDraft), contextWindow, enabled: model?.enabled ?? true, description: draft.description })
  }
  const changeId = (modelKey: string, option?: ModelDiscoveryRead['items'][number]) => {
    testGeneration.current += 1
    setDraft((current) => ({ ...current, modelKey, displayName: option && displayNameAutomatic.current ? option.displayName : current.displayName, contextWindow: option?.contextWindow && Number.isSafeInteger(option.contextWindow) && option.contextWindow > 0 ? String(option.contextWindow) : current.contextWindow }))
    setValidation(''); setTestState({ pending: false })
  }
  const testPending = testState.pending && testState.key === draft.modelKey.trim()
  return <>
    <Modal open={open} onOpenChange={onOpenChange} title={model ? '编辑模型' : '添加模型'} size="large" variant="split" bodyClassName="md:grid-cols-[285px_minmax(0,1fr)]" closeDisabled={save.isPending} footer={<><Button type="button" disabled={save.isPending} onClick={() => onOpenChange(false)}>取消</Button><Button type="button" variant="primary" disabled={save.isPending || !draft.modelKey.trim() || !draft.displayName.trim()} onClick={submit}>{save.isPending ? '正在保存…' : model ? '保存修改' : '保存模型'}</Button></>}>
      <ModelTestPanel provider={provider} modelKey={draft.modelKey} enabled={model?.enabled ?? true} pending={testPending} actionDisabled={save.isPending} result={testState.key === draft.modelKey.trim() ? testState.result : undefined} error={testState.key === draft.modelKey.trim() ? testState.error : undefined} checkedAt={testState.checkedAt} onTest={() => void test()} />
      <div className="grid content-start gap-4"><ModelForm draft={draft} setDraft={setDraft} modelKeyReadonly={Boolean(model)} copyFeedback={copyFeedback} onDisplayNameChange={() => { displayNameAutomatic.current = false }} onCopy={() => void navigator.clipboard.writeText(draft.modelKey).then(() => setCopyFeedback('模型标识已复制'), () => setCopyFeedback('复制未完成，请选中标识手动复制'))} error={validation || save.error?.message} idControl={!model ? <div className="grid gap-2"><FormField label="模型标识" hint="也可手动输入模型标识，按 Enter 确认。" htmlFor="model-id">{(a11y) => <><ModelIdInput {...a11y} id="model-id" value={draft.modelKey} options={discovery.data?.items ?? []} onChange={changeId} /></>}</FormField><div className="flex items-center justify-between gap-3 text-xs text-muted"><span>{discovery.isFetching ? '正在读取供应商目录…' : discovery.error ? `目录读取失败，仍可手动输入模型标识：${discovery.error.message}` : `已发现 ${discovery.data?.total ?? 0} 个模型`}</span><Button type="button" variant="ghost" aria-label="刷新模型目录" disabled={discovery.isFetching} onClick={() => void discovery.refetch()}>刷新</Button></div></div> : undefined} />
      {model ? <Button type="button" variant="ghost" disabled={save.isPending} onClick={() => setDeleteOpen(true)}>从目录移除</Button> : null}</div>
    </Modal>
    {model ? <ModelDeleteDialog open={deleteOpen} onOpenChange={setDeleteOpen} model={model} api={api} instanceId={instanceId} onRemoved={() => { onOpenChange(false); onRemoved() }} /> : null}
  </>
}
