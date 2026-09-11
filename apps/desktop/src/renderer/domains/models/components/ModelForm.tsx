import { useId, type Dispatch, type KeyboardEvent, type SetStateAction } from 'react'
import { X } from '@phosphor-icons/react/X'
import { FormField } from '../../../shared/components/FormField'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Textarea } from '../../../shared/components/ui/textarea'

export function mergeModelTags(current: string[], input: string): string[] {
  return [...new Set([...current, ...input.split(/[,，]/)].map((value) => value.trim()).filter(Boolean))]
}

export type ModelDraft = { modelKey: string; displayName: string; contextWindow: string; tags: string[]; tagDraft: string; description: string }

export function ModelForm({ draft, setDraft, idControl, modelKeyReadonly, copyFeedback, onCopy, onDisplayNameChange, error }: { draft: ModelDraft; setDraft: Dispatch<SetStateAction<ModelDraft>>; idControl?: React.ReactNode; modelKeyReadonly?: boolean; copyFeedback?: string; onCopy?(): void; onDisplayNameChange?(): void; error?: string }) {
  const prefix = useId()
  const set = (patch: Partial<ModelDraft>) => setDraft((current) => ({ ...current, ...patch }))
  const commitTags = () => setDraft((current) => ({ ...current, tags: mergeModelTags(current.tags, current.tagDraft), tagDraft: '' }))
  const tagKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) { event.preventDefault(); commitTags() }
  }
  return <section className="grid content-start gap-5">
    <h3 className="text-base font-semibold text-ink">模型设置</h3>
    {error ? <p role="alert" className="rounded-control bg-clay-soft p-3 text-sm text-clay">{error}</p> : null}
    <FormField label="显示名称" htmlFor={`${prefix}-name`}><Input autoFocus={modelKeyReadonly} value={draft.displayName} onChange={(event) => { onDisplayNameChange?.(); set({ displayName: event.target.value }) }} /></FormField>
    {idControl ?? <FormField label="模型标识" hint="用于调用远程模型的唯一标识符。" htmlFor={`${prefix}-key`}>
      <div className="grid gap-2"><div className="flex gap-2"><Input aria-label="模型标识" value={draft.modelKey} readOnly /><Button variant="ghost" type="button" aria-label="复制模型标识" onClick={onCopy}>复制</Button></div>{copyFeedback ? <span role="status" className="text-xs text-muted">{copyFeedback}</span> : null}</div>
    </FormField>}
    <FormField label="上下文窗口（最大）" htmlFor={`${prefix}-context`}><Input aria-label="上下文窗口" inputMode="numeric" value={draft.contextWindow} onChange={(event) => set({ contextWindow: event.target.value })} placeholder="可选，留空不设置" /></FormField>
    <div className="grid gap-2"><label className="text-sm font-medium text-ink" htmlFor={`${prefix}-tags`}>自定义标签（可选）</label><div className="flex flex-wrap gap-2 rounded-control border border-line bg-surface p-2">
      {draft.tags.map((tag) => <Badge key={tag}>{tag}<button type="button" aria-label={`移除标签 ${tag}`} onClick={() => set({ tags: draft.tags.filter((item) => item !== tag) })}><X size={12} /></button></Badge>)}
      <input id={`${prefix}-tags`} aria-label="自定义标签" className="min-w-32 flex-1 bg-transparent text-sm outline-none" value={draft.tagDraft} onChange={(event) => set({ tagDraft: event.target.value })} onKeyDown={tagKeyDown} onBlur={commitTags} placeholder="输入后按回车添加" />
    </div></div>
    <details><summary className="cursor-pointer text-sm font-medium">运行默认值（可选） <span className="text-muted">使用供应商默认参数</span></summary><div className="mt-3 grid gap-3"><p className="text-sm text-muted">本页不覆盖采样参数。使用模型时由调用方传入；未传入的参数沿用供应商默认设置。</p><FormField label="使用说明" htmlFor={`${prefix}-description`}><Textarea value={draft.description} onChange={(event) => set({ description: event.target.value })} /></FormField></div></details>
  </section>
}
