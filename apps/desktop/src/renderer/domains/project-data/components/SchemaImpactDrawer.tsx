import { Database, Info, Link } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import type { SchemaChange } from '../schema-draft'

type Impact = components['schemas']['DataSchemaImpact']
export function schemaIssueMessage(issue: Impact['blockers'][number]) {
  switch (issue.code) {
    case 'FIELD_VALUES_INCOMPATIBLE': return `${issue.affectedRecords ?? '部分'} 条记录不满足新的字段规则，请返回修改。`
    case 'EXISTING_RECORD_DEFAULT_REQUIRED': return '新增必填字段需要为现有记录提供合法默认值。'
    case 'SCHEMA_BACKFILL_LIMIT': return '本次默认值回填超过 1,000 条记录或 4 MiB，请缩小变更范围。'
    case 'SCHEMA_BACKFILL_INVALID_JSON': return '现有记录包含无法原样保存的数据，当前不能进行默认值回填。'
    case 'IDENTITY_FIELD_PROTECTED': return '身份字段不能删除。'
    case 'SOURCE_FIELD_MAPPING': return '字段仍有来源列映射，请先处理映射。'
    case 'AUTOMATION_FIELD_DEPENDENCY': return '自动化输入或关联条件仍引用此字段。'
    case 'ACTIVE_TASK_FIELD_DEPENDENCY': return '活动任务的其他节点或输入仍依赖此字段。'
    case 'PENDING_SYNC_FIELD_DEPENDENCY': return '未决同步操作仍引用此字段。'
    default: return '字段变更将影响现有数据，请核对后继续。'
  }
}

export function SchemaImpactDrawer({ open, tableName, sourceLabel, changes, impact, busy = false, recoveryPending = false, error, confirmLabel = '确认保存字段', onOpenChange, onConfirm }: {
  open: boolean; tableName: string; sourceLabel: string; changes: SchemaChange[]; impact: Impact | null;
  busy?: boolean; recoveryPending?: boolean; error?: string | null; confirmLabel?: string; onOpenChange(open: boolean): void; onConfirm(): void;
}) {
  return <Modal open={open} onOpenChange={next => { if (!busy) onOpenChange(next) }} placement="drawer" variant="form" className="w-[min(94vw,32rem)]" title="保存字段前核对影响" description={`${tableName} · ${changes.length} 项待保存修改`}
    footer={<><Button className="h-12 text-base" disabled={busy} onClick={() => onOpenChange(false)}>{recoveryPending ? '返回核对保存结果' : '返回修改'}</Button><Button className="h-12 text-base" variant="primary" disabled={busy || recoveryPending || !impact || impact.blockers.length > 0} onClick={onConfirm}>{busy ? '正在保存…' : confirmLabel}</Button></>}>
    <div className="grid gap-7 text-base">
      <section><h3 className="mb-3 text-lg font-semibold">本次修改</h3><TableScroll label="字段修改摘要" className="rounded-control border border-line"><Table data-variant="facts" className="table-fixed"><TableBody>{changes.map(change => <TableRow key={change.id}><TableHead scope="row" className="break-words">{change.name}<span className="ml-2 text-sm font-normal text-muted">{change.key}</span></TableHead><TableCell className="whitespace-pre-wrap [overflow-wrap:anywhere]">{change.summary}</TableCell></TableRow>)}</TableBody></Table></TableScroll></section>
      <section><h3 className="border-b border-line pb-2 text-lg font-semibold">现有记录</h3><p className="mt-3 flex gap-3"><Database size={24} aria-hidden="true" />{impact ? `${impact.affectedRecords.toLocaleString()} 条记录涉及本次校验或内容变更。` : '正在检查记录…'}</p><p className="mt-3 text-sm text-muted">原有记录身份、业务状态与环境关联保持不变。</p>{impact && impact.backfillBytes > 0 ? <p className="mt-2 text-sm text-muted">回填后记录内容合计 {impact.backfillBytes.toLocaleString()} 字节；多个字段同时回填，每条记录仅保存一次。</p> : null}</section>
      <section><h3 className="border-b border-line pb-2 text-lg font-semibold">来源映射</h3><p className="mt-3 flex gap-3"><Link size={24} aria-hidden="true" />{sourceLabel}</p><p className="mt-3 text-sm text-muted">新增字段仅保存到本地；现有字段映射与来源文件保持不变。</p></section>
      <section><h3 className="border-b border-line pb-2 text-lg font-semibold">自动化引用</h3><p className="mt-3 text-sm text-muted">{impact?.referenceAvailability.automations === 'available' && impact.referenceAvailability.sync === 'available' ? '已检查当前自动化、活动任务与同步依赖，提交前会再次核对。' : '自动化引用检查与同步能力暂未开放。'}</p></section>
      {impact?.blockers.map((issue, index) => <p key={index} role="alert" className="rounded-control border border-danger/25 bg-danger/5 p-3 text-danger">{schemaIssueMessage(issue)}</p>)}
      {impact?.warnings.map((issue, index) => <p key={index} className="rounded-control border border-warning/25 bg-warning/5 p-3">{schemaIssueMessage(issue)}</p>)}
      {error ? <p role="alert" className="text-danger">{error}</p> : null}
      <p className="flex gap-2 rounded-control border border-clay/20 bg-clay/5 p-3 text-clay"><Info size={22} className="shrink-0" aria-hidden="true" />请确认以上影响，再保存字段。</p>
    </div>
  </Modal>
}
