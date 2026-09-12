import { useId, type Dispatch, type SetStateAction } from 'react'
import { TagInput } from './TagInput'
export { mergeModelTags } from './TagInput'
import { FormField } from '../../../shared/components/FormField'
import { Disclosure } from '../../../shared/components/ui/disclosure'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Textarea } from '../../../shared/components/ui/textarea'

export type ModelDraft = { modelKey: string; displayName: string; contextWindow: string; tags: string[]; tagDraft: string; description: string }

export function ModelForm({ draft, setDraft, idControl, modelKeyReadonly, copyFeedback, onCopy, onDisplayNameChange, error }: { draft: ModelDraft; setDraft: Dispatch<SetStateAction<ModelDraft>>; idControl?: React.ReactNode; modelKeyReadonly?: boolean; copyFeedback?: string; onCopy?(): void; onDisplayNameChange?(): void; error?: string }) {
  const prefix = useId()
  const set = (patch: Partial<ModelDraft>) => setDraft((current) => ({ ...current, ...patch }))
  return <section className="grid content-start gap-5">
    <h3 className="text-base font-semibold text-ink">模型设置</h3>
    {error ? <p role="alert" className="rounded-control bg-clay-soft p-3 text-sm text-clay">{error}</p> : null}
    <FormField label="显示名称" htmlFor={`${prefix}-name`}>{(a11y) => <><Input {...a11y} autoFocus={modelKeyReadonly} value={draft.displayName} onChange={(event) => { onDisplayNameChange?.(); set({ displayName: event.target.value }) }} /></>}</FormField>
    {idControl ?? <FormField label="模型标识" hint="用于调用远程模型的唯一标识符。" htmlFor={`${prefix}-key`}>{(a11y) => <>
      <div className="grid gap-2"><div className="flex gap-2"><Input {...a11y} aria-label="模型标识" value={draft.modelKey} readOnly /><Button variant="ghost" type="button" aria-label="复制模型标识" onClick={onCopy}>复制</Button></div>{copyFeedback ? <span role="status" className="text-xs text-muted">{copyFeedback}</span> : null}</div>
    </>}</FormField>}
    <FormField label="上下文窗口（最大）" htmlFor={`${prefix}-context`}>{(a11y) => <><Input {...a11y} aria-label="上下文窗口" inputMode="numeric" value={draft.contextWindow} onChange={(event) => set({ contextWindow: event.target.value })} placeholder="可选，留空不设置" /></>}</FormField>
    <div className="grid gap-2"><label className="text-sm font-medium text-ink" htmlFor={`${prefix}-tags`}>自定义标签（可选）</label><TagInput id={`${prefix}-tags`} aria-label="自定义标签" value={draft.tags} draft={draft.tagDraft} onValueChange={tags=>set({tags})} onDraftChange={tagDraft=>set({tagDraft})}/></div>
    <Disclosure summary={<>运行默认值（可选） <span className="text-muted">使用供应商默认参数</span></>}><div className="mt-3 grid gap-3"><p className="text-sm text-muted">本页不覆盖采样参数。使用模型时由调用方传入；未传入的参数沿用供应商默认设置。</p><FormField label="使用说明" htmlFor={`${prefix}-description`}>{(a11y) => <><Textarea {...a11y} value={draft.description} onChange={(event) => set({ description: event.target.value })} /></>}</FormField></div></Disclosure>
  </section>
}
