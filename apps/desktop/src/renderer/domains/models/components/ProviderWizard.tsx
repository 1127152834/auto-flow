import { ArrowLeft, CaretRight, CircleNotch, ShieldCheck } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import type { ModelApi } from '../api'
import { refreshAfterModelConflict } from '../cache'
import type { ModelDiscoveryRead, ModelProviderCreateInput, ModelProviderRead, ProviderDraft } from '../model'
import { modelKeys } from '../model'
import { findProviderPreset, providerPresets, type ProviderPreset } from '../provider-catalog'
import { ProviderCatalogStep } from './ProviderCatalogStep'
import { ProviderConnectionStep } from './ProviderConnectionStep'
import { ProviderModelsStep } from './ProviderModelsStep'

type Step = 'catalog' | 'connection' | 'models'

const fromPreset = (preset: ProviderPreset): ProviderDraft => ({ name: preset.displayName, presetId: preset.id, providerKind: preset.providerKind, baseUrl: preset.defaultBaseUrl || null, apiKey: '', apiKeyTouched: false, enabled: true, description: '' })
const fromProvider = (provider: ModelProviderRead): ProviderDraft => ({ name: provider.name, presetId: provider.presetId, providerKind: provider.providerKind, baseUrl: provider.baseUrl, apiKey: '', apiKeyTouched: false, enabled: provider.enabled, description: provider.description })
const createInput = ({ apiKeyTouched: _ignored, ...draft }: ProviderDraft): ModelProviderCreateInput => draft
const message = (error: unknown) => error instanceof Error ? error.message : '操作未完成，请稍后重试'

export function ProviderWizard(props: { open: boolean; instanceId: string; onOpenChange(open: boolean): void; provider?: ModelProviderRead | null; api: ModelApi; onSaved(provider: ModelProviderRead): void }) {
  return <ProviderWizardSession key={`${props.provider?.id ?? 'new'}-${props.open ? 'open' : 'closed'}`} {...props} />
}

function ProviderWizardSession({ open, instanceId, onOpenChange, provider, api, onSaved }: { open: boolean; instanceId: string; onOpenChange(open: boolean): void; provider?: ModelProviderRead | null; api: ModelApi; onSaved(provider: ModelProviderRead): void }) {
  const editing = Boolean(provider)
  const initialPreset = findProviderPreset(provider?.presetId) ?? providerPresets[0]!
  const [step, setStep] = useState<Step>(editing ? 'connection' : 'catalog')
  const [draft, setDraft] = useState(() => provider ? fromProvider(provider) : fromPreset(initialPreset))
  const [discovery, setDiscovery] = useState<ModelDiscoveryRead | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const queryClient = useQueryClient()
  const preset = findProviderPreset(draft.presetId) ?? providerPresets.at(-1)!
  const original = provider ? fromProvider(provider) : null
  const connectionChanged = Boolean(original && (draft.presetId !== original.presetId || draft.providerKind !== original.providerKind || (draft.baseUrl ?? '').trim() !== (original.baseUrl ?? '').trim() || draft.apiKeyTouched))
  const required = preset.apiKeyPolicy === 'required' || draft.providerKind === 'anthropic' || draft.providerKind === 'gemini'
  const keyValid = !required || draft.apiKey.trim() !== '' || Boolean(provider?.apiKeyConfigured && !draft.apiKeyTouched)
  const valid = Boolean(draft.name.trim() && (draft.baseUrl ?? '').trim() && keyValid)

  const preview = useMutation({ mutationFn: () => api.previewConnection(createInput(draft)), gcTime: 0, onSuccess: (result) => { setDiscovery(result); setSelected(new Set()); setStep('models') }, onError: (error) => refreshAfterModelConflict(queryClient, instanceId, error) })
  const save = useMutation({
    mutationFn: async () => {
      if (provider) {
        if (!connectionChanged) return api.updateProvider(provider.id, { name: draft.name, enabled: draft.enabled, description: draft.description })
        await queryClient.cancelQueries({ queryKey: modelKeys.discovery(instanceId, provider.id), exact: true })
        const body = { name: draft.name, presetId: draft.presetId ?? null, providerKind: draft.providerKind, baseUrl: draft.baseUrl ?? null, enabled: draft.enabled, description: draft.description, ...(draft.apiKeyTouched ? { apiKey: draft.apiKey } : {}) }
        return api.updateConnection(provider.id, body)
      }
      const byKey = new Map((discovery?.items ?? []).map((item) => [item.modelKey, item]))
      return api.connect({ provider: createInput(draft), selectedModels: [...selected].map((modelKey) => { const remote = byKey.get(modelKey)!; return { modelKey, displayName: remote.displayName, tagsJson: [], contextWindow: remote.contextWindow ?? null, enabled: true, description: '' } }) })
    },
    gcTime: 0,
    onSuccess: async (saved) => { if (provider && connectionChanged) await queryClient.invalidateQueries({ queryKey: modelKeys.discovery(instanceId, provider.id), exact: true }); setDraft((current) => ({ ...current, apiKey: '', apiKeyTouched: false })); onSaved(saved); onOpenChange(false) },
    onError: (error) => refreshAfterModelConflict(queryClient, instanceId, error),
  })
  const busy = preview.isPending || save.isPending
  const update = (patch: Partial<ProviderDraft>) => { if (busy) return; setDraft((current) => ({ ...current, ...patch })); setDiscovery(null); setSelected(new Set()); preview.reset(); save.reset() }
  const choose = (next: ProviderPreset) => { setDraft(fromPreset(next)); setDiscovery(null); setSelected(new Set()) }
  const close = (next: boolean) => { if (!busy) onOpenChange(next) }

  const footer = step === 'catalog' ? <><Button onClick={() => close(false)}>取消</Button><Button variant="primary" onClick={() => setStep('connection')}>下一步<CaretRight size={15} /></Button></> : step === 'connection' ? <>{!editing && <Button variant="ghost" onClick={() => setStep('catalog')}><ArrowLeft size={15} />上一步</Button>}<span className="grow" /><Button onClick={() => close(false)}>取消</Button>{editing ? <Button variant="primary" disabled={!valid || busy} onClick={() => save.mutate()}>{save.isPending && <CircleNotch className="animate-spin" />}{connectionChanged ? '测试并保存' : '保存修改'}</Button> : <Button variant="primary" disabled={!valid || busy} onClick={() => preview.mutate()}>{preview.isPending ? <CircleNotch className="animate-spin" /> : <ShieldCheck />}测试连接</Button>}</> : <><Button variant="ghost" onClick={() => { setStep('connection'); setDiscovery(null); setSelected(new Set()) }}><ArrowLeft />修改连接</Button><span className="grow" /><Button onClick={() => close(false)}>取消</Button><Button variant="primary" disabled={busy || !discovery} onClick={() => save.mutate()}>{save.isPending && <CircleNotch className="animate-spin" />}保存供应商{selected.size ? `和 ${selected.size} 个模型` : ''}</Button></>

  return <Modal open={open} onOpenChange={close} closeDisabled={busy} size="large" title={editing ? '编辑模型供应商' : '添加供应商'} description={editing ? '修改基础信息可直接保存；连接发生变化时先验证。' : '选择供应商、验证连接，然后按需添加模型。'} footer={footer}>
    <div className="grid gap-6">
      <div aria-label="新增供应商步骤" className="grid grid-cols-3 gap-2">{(['catalog', 'connection', 'models'] as Step[]).map((value, index) => <span key={value} aria-current={step === value ? 'step' : undefined} className={`rounded-lg px-3 py-2 text-center text-sm ${step === value ? 'bg-clay text-white' : 'bg-surface-subtle text-muted'}`}>{index + 1}. {['选择供应商', '连接信息', '选择模型'][index]}</span>)}</div>
      {step === 'catalog' && <ProviderCatalogStep selectedId={draft.presetId ?? ''} onSelect={choose} />}
      {step === 'connection' && <ProviderConnectionStep draft={draft} preset={preset} hasStoredKey={Boolean(provider?.apiKeyConfigured)} error={preview.error || save.error ? message(preview.error || save.error) : undefined} disabled={busy} onChange={update} />}
      {step === 'models' && save.error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><strong className="block">保存失败，可以重试</strong>{message(save.error)}</div>}
      {step === 'models' && discovery && <ProviderModelsStep discovery={discovery} selected={selected} onSelected={setSelected} />}
    </div>
  </Modal>
}
