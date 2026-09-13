import { ArrowSquareOut, Copy } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { validatedExternalUrl, type ExternalLinkBridge } from '../../../../shared/external-links'
import type { components } from '../../../shared/api/generated'
import { IconButton } from '../../../shared/components/ui/icon-button'

type Schema = components['schemas']
export function recordCellLabel(cell?: Schema['DataCellView']): string {
  if (!cell) return '未填写'
  if (!cell.readable) return '不可读取'
  if (cell.error) return `读取失败：${cell.error}`
  if (cell.value === null) return '空值'
  if (cell.value === '') return '空字符串'
  if (typeof cell.value === 'boolean') return cell.value ? '是' : '否'
  if (typeof cell.value === 'object') return cell.value.value + (cell.value.precision === 'datetime' ? ` ${cell.value.offset ?? '无时区'}` : '')
  return String(cell.value)
}
export function RecordFieldsView({ fields, record, openExternalLink = window.autoflow?.openExternalLink }: {
  fields: Schema['DataFieldView'][]
  record: Schema['DataRecordView']
  openExternalLink?: ExternalLinkBridge['openExternalLink']
}) {
  const identity = JSON.stringify(record.ref)
  const current = useRef(identity), ticket = useRef(0)
  const [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  useEffect(() => { current.current = identity; ticket.current++; setFeedback(null); setBusy(null); return () => { current.current = ''; ticket.current++ } }, [identity])
  const act = async (fieldId: string, action: () => Promise<void>, message?: string) => {
    if (busy) return
    const epoch = ++ticket.current, scope = identity
    setBusy(fieldId); setFeedback(null)
    try { await action(); if (current.current === scope && epoch === ticket.current && message) setFeedback({ error: false, text: message }) }
    catch (error) { if (current.current === scope && epoch === ticket.current) setFeedback({ error: true, text: error instanceof Error ? error.message : '操作失败，请重试' }) }
    finally { if (current.current === scope && epoch === ticket.current) setBusy(null) }
  }
  const cells = new Map(record.values.map(cell => [cell.fieldId, cell]))
  const key = record.ref.recordKey
  return <section aria-label="基本信息" className="min-w-0 rounded-card border border-line bg-surface p-6">
    <h2 className="mb-5 text-base font-semibold">基本信息</h2>
    <dl className="m-0 grid min-w-0 gap-0">
      <div className="grid min-w-0 gap-2 border-b border-line py-4 sm:grid-cols-[8rem_minmax(0,1fr)]"><dt className="text-sm text-muted">记录身份</dt><dd className="m-0 min-w-0 break-all text-sm">{{ text: '文本', integer: '整数', uuid: 'UUID' }[key.type]} · {key.value}<span className="ml-2 text-xs text-muted">只读</span></dd></div>
      {fields.map(field => {
        const cell = cells.get(field.ref.fieldId), label = recordCellLabel(cell)
        let url: string | null = null
        if (cell?.readable && !cell.error && typeof cell.value === 'string') { try { url = validatedExternalUrl(cell.value) } catch { /* non-web values remain plain text */ } }
        return <div key={field.ref.fieldId} className="grid min-w-0 gap-2 border-b border-line py-4 last:border-0 sm:grid-cols-[8rem_minmax(0,1fr)]">
          <dt className="break-words text-sm text-muted">{field.name}</dt>
          <dd className="m-0 min-w-0 text-sm"><div className="flex min-w-0 items-start gap-2"><span className={`min-w-0 flex-1 whitespace-pre-wrap break-words [overflow-wrap:anywhere] ${url ? 'text-clay' : ''}`}>{label}</span>{url ? <span className="flex shrink-0 gap-1">
            <IconButton size="sm" variant="ghost" aria-label={`复制链接 ${field.name}`} disabled={Boolean(busy)} onClick={() => void act(field.ref.fieldId, () => navigator.clipboard.writeText(String(cell!.value)), '链接已复制')}><Copy size={16} /></IconButton>
            <IconButton size="sm" variant="ghost" aria-label={`打开链接 ${field.name}`} disabled={Boolean(busy)} onClick={() => void act(field.ref.fieldId, async () => { if (!openExternalLink) throw new Error('当前环境无法打开外部链接'); const result = await openExternalLink(url!); if (!result.ok) throw new Error(result.error.message) })}><ArrowSquareOut size={16} /></IconButton>
          </span> : null}</div></dd>
        </div>
      })}
    </dl>
    {feedback ? <p role={feedback.error ? 'alert' : 'status'} className={`mt-4 text-sm ${feedback.error ? 'text-danger' : 'text-muted'}`}>{feedback.text}</p> : null}
  </section>
}
