import { Plus } from '@phosphor-icons/react'
import { useState } from 'react'
import type { ModelApi } from '../api'
import type { AiModel, ModelProvider } from '../model'
import { useModelManagement } from '../hooks/use-model-management'
import { Button } from '../../../shared/components/ui/button'
import { ProviderSidebar } from '../components/ProviderSidebar'
import { ProviderDetail } from '../components/ProviderDetail'
import { ModelDirectory } from '../components/ModelDirectory'
import { FeedbackCard } from '../components/FeedbackCard'
import { ProviderWizard } from '../components/ProviderWizard'
import { ModelEditor } from '../components/ModelEditor'
import { ProviderDeleteDialog } from '../components/ProviderDeleteDialog'
import { ModelDeleteDialog } from '../components/ModelDeleteDialog'

export function ModelManagementPage({ api, instanceId }: { api: ModelApi; instanceId: string }) {
  const state = useModelManagement(api, instanceId)
  const [providerSearch, setProviderSearch] = useState('')
  const [modelSearch, setModelSearch] = useState('')
  const [modelStatus, setModelStatus] = useState('all')
  const [wizard, setWizard] = useState<{ provider?: ModelProvider } | null>(null)
  const [editor, setEditor] = useState<{ provider: ModelProvider; model?: AiModel } | null>(null)
  const [deleteProvider, setDeleteProvider] = useState<ModelProvider | null>(null)
  const [deleteModel, setDeleteModel] = useState<AiModel | null>(null)
  const { selected, providers } = state
  const add = () => setWizard({})
  const openModel = (model?: AiModel) => { if (selected) { state.clearModelFeedback(); setEditor({ provider: selected, model }) } }
  const addModel = async (sync: boolean) => {
    if (!selected) return
    if (sync) await state.resetDiscovery(selected.id)
    state.clearModelFeedback()
    setEditor({ provider: selected })
  }
  const feedback = selected && state.providerFeedback[selected.id]

  return <main className="mx-auto w-full max-w-[1600px] px-8 pb-10 pt-8 max-[640px]:px-4">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><h1 className="m-0 text-3xl font-semibold tracking-tight">模型管理</h1><p className="mb-0 mt-2 text-sm text-muted">接入模型供应商，维护可用于自动化任务的模型目录。</p></div><Button variant="primary" onClick={add} aria-label="添加模型供应商"><Plus size={17} />添加供应商</Button></header>
    {providers.isError && providers.data && <div role="alert" className="mb-4 flex items-center justify-between gap-3 rounded-card border border-red-200 bg-red-50 p-4 text-sm text-red-800"><span>刷新失败：{providers.error.message}</span><Button onClick={() => void providers.refetch()}>重试刷新</Button></div>}
    {providers.isPending ? <div role="status" className="rounded-card border border-line bg-surface p-8"><div className="mb-4 h-5 w-40 animate-pulse rounded bg-surface-subtle" />正在加载模型供应商…</div> : !providers.data ? <div role="alert" className="rounded-card border border-line bg-surface p-8"><p>{providers.error?.message}</p><Button onClick={() => void providers.refetch()}>重试</Button></div> : providers.data.items.length === 0 ? <section className="grid min-h-96 place-content-center gap-4 rounded-card border border-line bg-surface text-center"><h2 className="m-0 text-xl">还没有模型供应商</h2><p className="m-0 text-sm text-muted">添加供应商，建立你的第一个模型目录。</p><Button onClick={add}>添加第一个供应商</Button></section> : <div className="grid min-h-[660px] grid-cols-[278px_minmax(0,1fr)] overflow-hidden rounded-card border border-line bg-surface max-[920px]:grid-cols-1">
      <ProviderSidebar providers={providers.data.items} selectedId={selected?.id ?? ''} search={providerSearch} onSearch={setProviderSearch} onSelect={state.select} onAdd={add} />
      {selected && <div className="min-w-0 p-6 max-[640px]:p-4"><ProviderDetail provider={selected} feedback={feedback} busy={Boolean(state.activity)} crudBusy={state.activity?.kind === 'crud'} testing={state.activity?.kind === 'provider' && state.activity.providerId === selected.id} onTest={() => void state.testProvider(selected)} onEdit={() => setWizard({ provider: selected })} onToggle={() => void state.toggleProvider(selected)} onDelete={() => setDeleteProvider(selected)} />
        <div className="mt-8 grid gap-4">{state.modelFeedback && <FeedbackCard feedback={state.modelFeedback} />}<ModelDirectory models={selected.models} search={modelSearch} status={modelStatus} busy={state.activity?.kind === 'crud'} testingKey={state.activity?.kind === 'model' ? state.activity.modelKey ?? null : null} onSearch={setModelSearch} onStatus={setModelStatus} onAdd={sync => void addModel(sync)} onTest={model => void state.testModel(selected, model)} onEdit={openModel} onToggle={model => void state.toggleModel(selected, model)} onDelete={setDeleteModel} /></div>
      </div>}
    </div>}
    {wizard && <ProviderWizard open instanceId={instanceId} api={api} provider={wizard.provider} onOpenChange={open => { if (!open) setWizard(null) }} onSaved={state.providerSaved} />}
    {editor && <ModelEditor open api={api} instanceId={instanceId} provider={editor.provider} model={editor.model} onOpenChange={open => { if (!open) setEditor(null) }} onSaved={() => void state.refresh()} onRemoved={() => { setEditor(null); void state.refresh() }} />}
    {deleteProvider && <ProviderDeleteDialog instanceId={instanceId} provider={deleteProvider} api={api} blocked={Boolean(state.activity)} onClose={() => setDeleteProvider(null)} onRemoved={() => void state.removed(deleteProvider.id)} />}
    {deleteModel && <ModelDeleteDialog open instanceId={instanceId} blocked={Boolean(state.activity)} model={deleteModel} api={api} onOpenChange={open => { if (!open) setDeleteModel(null) }} onRemoved={() => void state.refresh()} />}
  </main>
}
