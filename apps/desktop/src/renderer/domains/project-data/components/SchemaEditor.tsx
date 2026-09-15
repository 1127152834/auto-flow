import { Info, Lock, Plus } from '@phosphor-icons/react'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { schemaFieldId } from '../schema-draft'
import { useSchemaDraft } from '../use-schema-draft'
import { SchemaFieldDrawer } from './SchemaFieldDrawer'
import { SchemaImpactDrawer } from './SchemaImpactDrawer'
import { safeProjectError } from '../../projects/presentation-error'

type Schema = components['schemas']
type Props = {
  sessionKey: string; submissionEpoch?: string; generation: string; tableName: string; sourceLabel: string;
  directory: Schema['DataFieldDirectory']; restoredCandidate?: Schema['DataSchemaCandidate']; identityFieldId?: string;
  readonly?: boolean; disabled?: boolean; busy?: boolean; recoveryPending?: boolean; error?: string | null; errorActions?: ReactNode;
  onPreview(candidate: Schema['DataSchemaCandidate']): Promise<Schema['DataSchemaImpact']>;
  onSubmit(body: Schema['DataSchemaCommit']): Promise<unknown>;
  onReset(): void; onRecover?(): Promise<unknown>; onDirtyChange?(dirty: boolean): void;
}
const typeLabel = { string: '文本', number: '数字', boolean: '布尔', date: '日期' }
const ruleLabel = (rules: Schema['DataFieldWrite']['validation']) => {
  const labels = []
  if (rules.minLength !== undefined || rules.maxLength !== undefined) labels.push('文本长度')
  if (rules.pattern !== undefined) labels.push('格式校验')
  if (rules.minimum !== undefined || rules.maximum !== undefined) labels.push('数值范围')
  return labels.join('、') || '—'
}

export function SchemaEditor(props: Props) {
  const { sessionKey, submissionEpoch, generation, directory, readonly, disabled, busy, recoveryPending } = props
  const draft = useSchemaDraft({ sessionKey, generation, directory, restoredCandidate: props.restoredCandidate })
  const [drawer, setDrawer] = useState<{ id: string | null; session: string } | null>(null)
  const [drawerDirty, setDrawerDirty] = useState(false)
  const [impact, setImpact] = useState<Schema['DataSchemaImpact'] | null>(null)
  const [checking, setChecking] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const authority = useRef({ sessionKey, submissionEpoch, disabled, readonly })
  const ticket = useRef(0), mounted = useRef(true)
  const callbacks = useRef(props)
  useLayoutEffect(() => { callbacks.current = props }, [props])
  useLayoutEffect(() => {
    const before = authority.current
    if (before.sessionKey !== sessionKey || before.submissionEpoch !== submissionEpoch || before.disabled !== disabled || before.readonly !== readonly) {
      ticket.current += 1; setChecking(false); setImpact(null)
      if (before.sessionKey !== sessionKey) { setDrawer(null); setDrawerDirty(false); setLocalError(null) }
    }
    authority.current = { sessionKey, submissionEpoch, disabled, readonly }
  }, [sessionKey, submissionEpoch, disabled, readonly])
  useEffect(() => { props.onDirtyChange?.(draft.dirty || drawerDirty) }, [draft.dirty, drawerDirty, props.onDirtyChange])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; ticket.current += 1; callbacks.current.onDirtyChange?.(false) } }, [])
  const frozen = Boolean(readonly || disabled || busy || recoveryPending || checking)
  const selected = drawer?.id ? draft.candidate.fields.find(field => schemaFieldId(field) === drawer.id) : undefined
  const original = selected?.kind === 'existing' ? directory.items.find(field => field.ref.fieldId === selected.fieldId) : undefined
  const run = async (action: () => Promise<unknown>) => {
    const id = ++ticket.current
    setLocalError(null)
    try { await action() } catch (error) { if (mounted.current && ticket.current === id) setLocalError(safeProjectError(error)) }
  }
  const preview = async () => {
    if (frozen || !draft.dirty) return
    const id = ++ticket.current
    setChecking(true); setLocalError(null)
    try { const report = await props.onPreview(structuredClone(draft.candidate)); if (mounted.current && id === ticket.current) setImpact(report) }
    catch (error) { if (mounted.current && id === ticket.current) setLocalError(safeProjectError(error)) }
    finally { if (mounted.current && id === ticket.current) setChecking(false) }
  }
  return <section aria-label="字段目录" className="grid min-w-0 grid-cols-1 gap-4">
    <div className="min-w-0 rounded-control border border-line bg-surface p-4">
      <header className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-2xl font-semibold">字段与校验</h3><p className="mt-1 text-base text-muted">定义业务字段与填写规则，业务状态单独管理。</p></div><Button size="sm" className="text-sm" variant="primary" disabled={frozen} onClick={() => setDrawer({ id: null, session: crypto.randomUUID() })}><Plus size={18} />新增字段</Button></header>
      {localError || props.error ? <div role="alert" className="mb-3 text-sm text-danger">{localError || props.error}{props.errorActions}</div> : null}
      <TableScroll label="字段与校验表格" className="rounded-control border border-line"><Table aria-label="字段与校验" className="min-w-[680px] table-fixed">
        <TableHeader><TableRow><TableHead className="w-[22%]">字段名称</TableHead><TableHead className="w-[18%]">字段键</TableHead><TableHead className="w-[13%]">类型</TableHead><TableHead className="w-[12%]">必填</TableHead><TableHead>规则</TableHead><TableHead className="w-[18%]">操作</TableHead></TableRow></TableHeader>
        <TableBody>{draft.candidate.fields.map(field => { const id = schemaFieldId(field), definition = field.definition, identity = id === props.identityFieldId, source = directory.items.find(item => item.ref.fieldId === id); return <TableRow key={id}><TableCell className="break-words">{definition.name}{draft.changes.some(change => change.id === id) ? <span className="ml-2 text-xs text-clay">{field.kind === 'new' ? '新增' : '已修改'}</span> : null}{identity ? <span className="ml-2 inline-block rounded-control bg-clay/10 px-3 py-1 text-sm text-clay">唯一标识</span> : null}</TableCell><TableCell className="break-words">{definition.key}</TableCell><TableCell>{typeLabel[definition.type]}</TableCell><TableCell><span className={definition.required ? 'inline-flex items-center gap-1 rounded-control bg-clay/10 px-3 py-1 text-sm text-clay' : 'rounded-control bg-surface-subtle px-3 py-1 text-sm text-muted'}>{definition.required ? '是' : '否'}</span></TableCell><TableCell className="break-words">{identity ? '唯一标识' : ruleLabel(definition.validation)}</TableCell><TableCell><Button variant="ghost" className="h-auto px-1 py-0 text-base text-clay" aria-label={`编辑字段 ${definition.name}`} disabled={frozen || Boolean(source?.formula || source && !source.writable)} onClick={() => setDrawer({ id, session: crypto.randomUUID() })}>编辑{source && (!source.writable || source.formula) ? <Lock size={15} /> : null}</Button><Button variant="ghost" className="ml-3 h-auto px-1 py-0 text-base" disabled title="字段删除暂未开放" aria-label={`删除字段 ${definition.name}，暂未开放`}>删除<Lock size={15} /></Button></TableCell></TableRow> })}
          {!draft.candidate.fields.length ? <TableRow><TableCell colSpan={6} className="py-10 text-center text-muted">暂无字段，添加第一个业务字段。</TableCell></TableRow> : null}
        </TableBody></Table></TableScroll>
      <div className="mt-5 grid gap-2 text-base text-muted"><p className="flex items-start gap-2"><Info size={22} className="shrink-0" />记录身份保持稳定，身份字段类型受保护。</p><p className="flex items-start gap-2"><Info size={22} className="shrink-0" />字段修改在点击「保存字段」后统一生效。</p></div>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-3 py-1 text-base"><p>{draft.candidate.fields.length} 个业务字段 · {draft.dirty ? `${draft.changes.length} 项待保存修改` : '暂无未保存修改'}</p><div className="flex gap-3"><Button className="h-12 px-6 text-base" disabled={frozen || !draft.dirty} onClick={props.onReset}>重置修改</Button>{recoveryPending ? <Button className="h-12 text-base" disabled={disabled || busy} onClick={() => void run(() => props.onRecover?.() ?? Promise.resolve())}>核对保存结果</Button> : <Button className="h-12 px-6 text-base" variant="primary" disabled={frozen || !draft.dirty} onClick={() => void preview()}>{checking ? '正在检查…' : '保存字段'}</Button>}</div></footer>
    {drawer ? <SchemaFieldDrawer open sessionKey={drawer.session} submissionEpoch={submissionEpoch} initialField={original} initialDefinition={selected?.definition} existingRecordDefault={selected?.kind === 'new' ? selected.existingRecordDefault : undefined} hasDefault={selected?.kind === 'new' && Object.hasOwn(selected, 'existingRecordDefault')} isIdentityField={drawer.id === props.identityFieldId} readonly={frozen} onDirtyChange={setDrawerDirty} onOpenChange={open => { if (!open) { setDrawer(null); setDrawerDirty(false) } }} onApply={value => { if (frozen) return; draft.apply(drawer.id, value); setDrawer(null); setDrawerDirty(false); setImpact(null) }} /> : null}
    <SchemaImpactDrawer open={impact !== null} tableName={props.tableName} sourceLabel={props.sourceLabel} changes={draft.changes} impact={impact} busy={busy} recoveryPending={recoveryPending} error={localError || props.error} onOpenChange={open => { if (!open) setImpact(null) }} onConfirm={() => { if (!impact || frozen || impact.blockers.length) return; void run(() => props.onSubmit({ candidate: structuredClone(draft.candidate), impactRevision: impact.impactRevision })) }} />
  </section>
}
