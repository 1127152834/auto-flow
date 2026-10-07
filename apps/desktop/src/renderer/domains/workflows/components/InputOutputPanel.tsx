import { useRef, type ReactNode } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { useWorkflowStore } from '../editor-store'
import { useSignatureStore } from '../hooks/stores/signatureStore'
import { describeFlowOutputs } from '../lib/signatureOutputs'
import { suggestKey } from '../lib/signatureKeys'
import { SIGNATURE_FIELD_TYPES, type SignatureFieldDraft, type SignatureInputDraft, type SignatureSample } from '../lib/signatureDocument'
import { Button } from './controls/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './controls/dialog'
import { Input } from './controls/input'
import { ConfigField } from './config-panels/ConfigField'
import { SignatureImport } from './SignatureImport'
import { SIGNATURE_TYPE_LABELS } from './signatureTypes'

const AUTO_KEY = /^(field|group)\d+$/
const selectClass = 'h-8 w-full rounded-control border bg-[hsl(var(--card))] px-2 text-[13px] disabled:opacity-50'

export function InputOutputPanel({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
      <DialogHeader><DialogTitle>输入与输出</DialogTitle><DialogDescription>说明这个流程需要哪些输入，以及它会交回什么结果。</DialogDescription></DialogHeader>
      <PanelBody />
    </DialogContent>
  </Dialog>
}

function PanelBody() {
  const { inputs, issues, readOnly, loadIssues, serverIssues } = useSignatureStore()
  const store = useSignatureStore.getState
  // Fields already saved keep their key when renamed, so references to them stay valid.
  const saved = useRef(new Set(inputs.flatMap(input => [input.key, ...input.fields.map(field => `${input.key}.${field.key}`)])))
  const byPath = new Map(issues.map(issue => [issue.path, issue.message]))
  const problems = [...new Set([...loadIssues, ...serverIssues].map(issue => issue.message))]
  const addGroup = () => store().addInput({ key: suggestKey('', inputs.map(input => input.key), 'group'), name: `分组${inputs.length + 1}` })
  const addField = (input: SignatureInputDraft, index: number) => {
    const key = suggestKey('', input.fields.map(field => field.key))
    store().addFieldAt(index, { key, name: `字段${input.fields.length + 1}`, type: 'string' })
  }
  return <div className="space-y-6">
    <section aria-labelledby="io-inputs" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="io-inputs" className="text-[14px] font-semibold">输入</h3>
        <div className="flex gap-2">
          <SignatureImport disabled={readOnly} groups={inputs.map(input => ({ key: input.key, name: input.name, fieldKeys: input.fields.map(field => field.key) }))}
            onApply={(target, items) => {
              let groupIndex: number
              if ('groupIndex' in target) groupIndex = target.groupIndex
              else { store().addInput({ key: suggestKey(target.newName, inputs.map(input => input.key), 'group'), name: target.newName }); groupIndex = store().inputs.length - 1 }
              for (const item of items) store().addFieldAt(groupIndex, { key: item.key, name: item.name, type: item.type, required: item.required })
            }} />
          <Button size="sm" variant="outline" disabled={readOnly} onClick={addGroup}><Plus className="h-3.5 w-3.5" />新增分组</Button>
        </div>
      </div>
      {readOnly && <div role="alert" className="space-y-1 rounded-control border p-3 text-xs">
        <p className="m-0 font-medium text-danger">这个流程已有的输入存在问题，暂时只能查看，避免覆盖原内容。</p>
        <ul className="m-0 list-disc pl-5">{problems.map(message => <li key={message}>{message}</li>)}</ul>
        <p className="m-0 text-muted-foreground">请修正后重新打开这个工作流，再编辑输入。</p>
      </div>}
      {!inputs.length && !readOnly && <p className="text-xs text-muted-foreground">还没有输入。新增一个分组（例如“账号”），再为它添加字段。</p>}
      {inputs.map((input, index) => <fieldset key={index} disabled={readOnly} className="m-0 space-y-3 rounded-control border p-3" aria-label={`分组 ${input.name}`}>
        <div className="flex items-end gap-3">
          <div className="min-w-0 flex-1"><ConfigField label="分组名称" error={byPath.get(`signature.inputs.${index}.key`)}>{control =>
            <Input {...control} value={input.name} onChange={event => store().updateInputAt(index, { name: event.target.value })}
              onBlur={() => { if (!saved.current.has(input.key) && !input.keyEdited && AUTO_KEY.test(input.key) && input.name.trim()) store().updateInputAt(index, { key: suggestKey(input.name, inputs.filter(item => item !== input).map(item => item.key), 'group'), keyEdited: false }) }} />}</ConfigField></div>
          <Button size="sm" variant="tonal-danger" aria-label={`删除分组 ${input.name}`} onClick={() => store().removeInputAt(index)}><Trash2 className="h-3.5 w-3.5" />删除分组</Button>
        </div>
        <Advanced label="分组标识" hint="在流程里引用这个分组时使用的名字；已被引用时请不要修改。" value={input.key} onChange={value => store().updateInputAt(index, { key: value })} />
        {input.fields.map((field, fieldIndex) => <FieldRow key={fieldIndex} input={input} inputIndex={index} fieldIndex={fieldIndex} field={field}
          locked={saved.current.has(`${input.key}.${field.key}`)} error={path => byPath.get(`signature.inputs.${index}.fields.${fieldIndex}.${path}`)} />)}
        <Button size="sm" variant="outline" onClick={() => addField(input, index)}><Plus className="h-3.5 w-3.5" />新增字段</Button>
      </fieldset>)}
    </section>
    <Outputs />
  </div>
}

function Advanced({ label, hint, value, onChange, error }: { label: string; hint: string; value: string; onChange(value: string): void; error?: string }) {
  return <details className="text-xs" open={Boolean(error)}><summary className="cursor-pointer text-muted-foreground">高级</summary>
    <div className="mt-2 max-w-xs"><ConfigField label={label} hint={hint} error={error}>{control => <Input {...control} value={value} onChange={event => onChange(event.target.value)} />}</ConfigField></div></details>
}

function FieldRow({ input, inputIndex, fieldIndex, field, locked, error }: { input: SignatureInputDraft; inputIndex: number; fieldIndex: number; field: SignatureFieldDraft; locked: boolean; error(path: string): string | undefined }) {
  const store = useSignatureStore.getState
  const patch = (change: Partial<SignatureFieldDraft>) => store().updateFieldAt(inputIndex, fieldIndex, change)
  const otherKeys = input.fields.filter(item => item !== field).map(item => item.key)
  return <div role="group" aria-label={`字段 ${field.name}`} className="space-y-2 rounded-control border p-3">
    <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto_auto] items-start gap-3">
      <ConfigField label="中文名">{control =>
        <Input {...control} value={field.name} onChange={event => patch({ name: event.target.value })}
          onBlur={() => { if (!locked && !field.keyEdited && AUTO_KEY.test(field.key) && field.name.trim()) patch({ key: suggestKey(field.name, otherKeys), keyEdited: false }) }} />}</ConfigField>
      <ConfigField label="类型" error={error('type')}>{control =>
        <select {...control} className={selectClass} value={field.type} onChange={event => patch({ type: event.target.value, sample: undefined })}>
          {SIGNATURE_FIELD_TYPES.map(type => <option key={type} value={type}>{SIGNATURE_TYPE_LABELS[type]}</option>)}</select>}</ConfigField>
      <label className="mt-6 flex items-center gap-1 text-[13px]"><input type="checkbox" checked={field.required} onChange={event => patch({ required: event.target.checked })} />必填</label>
      <label className="mt-6 flex items-center gap-1 text-[13px]"><input type="checkbox" checked={field.sensitive} onChange={event => patch({ sensitive: event.target.checked })} />敏感</label>
      <Button className="mt-5" size="sm" variant="ghost" aria-label={`删除字段 ${field.name}`} onClick={() => store().removeFieldAt(inputIndex, fieldIndex)}><Trash2 className="h-3.5 w-3.5" /></Button>
    </div>
    <ConfigField label="样例值" hint={field.sensitive ? '敏感字段不保存样例' : '试跑和预览时用来演示，不会当作真实数据。'} error={error('sample')}>{control =>
      <SampleInput control={control} field={field} onChange={sample => patch({ sample })} />}</ConfigField>
    <Advanced label="字段标识" hint={locked ? '这个字段已保存，修改标识会让已有引用失效。' : '在流程里引用这个字段时使用的名字。'} value={field.key} error={error('key')} onChange={value => patch({ key: value })} />
  </div>
}

function SampleInput({ control, field, onChange }: { control: Record<string, unknown>; field: SignatureFieldDraft; onChange(sample: SignatureSample | undefined): void }): ReactNode {
  const sample = field.sample
  if (field.type === 'boolean') {
    return <select {...control} className={selectClass} disabled={field.sensitive} value={sample === undefined ? '' : String(sample)} onChange={event => onChange(event.target.value === '' ? undefined : event.target.value === 'true')}>
      <option value="">未设置</option><option value="true">是</option><option value="false">否</option></select>
  }
  const kind = field.type === 'date' ? 'date' : field.type === 'number' ? 'number' : 'text'
  return <Input {...control} type={kind} disabled={field.sensitive} value={sample === undefined ? '' : String(sample)}
    onChange={event => { const text = event.target.value; onChange(text === '' ? undefined : kind === 'number' ? Number(text) : text) }} />
}

function Outputs() {
  const nodes = useWorkflowStore(state => state.nodes)
  const items = describeFlowOutputs(nodes)
  return <section aria-labelledby="io-outputs" className="space-y-2">
    <h3 id="io-outputs" className="text-[14px] font-semibold">输出</h3>
    <p className="m-0 text-xs text-muted-foreground">输出由节点自动产生，在节点里配置。</p>
    {items.length ? <ul aria-label="流程输出" className="m-0 list-none space-y-1 p-0">{items.map(item => <li key={item.id} className="flex gap-2 text-[13px]">
      <span className="text-muted-foreground">{item.kind === 'result' ? '业务结果' : '写回数据'}</span><span>{item.node}</span><span className="text-muted-foreground">{item.text}</span></li>)}</ul>
      : <p className="text-xs text-muted-foreground">这个流程里还没有结束节点或写回数据的节点。</p>}
  </section>
}
