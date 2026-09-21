import { useQuery } from '@tanstack/react-query'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import type { SheetsApi } from '../sheets-api'
import { recordCellLabel } from './RecordFieldsView'

type Schema = components['schemas']
export function RecordSourceObservations({ api, scopeKey, record, fields }: {
  api: SheetsApi
  scopeKey: string
  record: Schema['DataRecordView']
  fields: Schema['DataFieldView'][]
}) {
  const query = useQuery({
    queryKey: ['record-source-observations', scopeKey, record.ref, record.contentRevision],
    queryFn: ({ signal }) => api.observations(record.ref, signal),
  })
  const label = (fieldId: string, value: Schema['SourceFieldObservation']['remoteValue']) => recordCellLabel({ fieldId, value, readable: true, source: 'remote' })
  const items = query.data?.items.filter(item => fields.some(field => field.ref.fieldId === item.fieldId)) ?? []
  return <section aria-label="来源观察" className="mt-4 rounded-card border border-line bg-surface p-6">
    <h3 className="text-xl font-semibold">来源观察</h3>
    <p className="text-sm text-muted">最近一次拉取时的来源值；本地已提交的值保持不变。公式字段按来源刷新。</p>
    {query.isPending ? <p role="status">正在读取来源观察…</p> : query.isError ? <p role="alert">无法读取来源观察。<Button variant="ghost" onClick={() => void query.refetch()}>重试</Button></p> : items.length === 0 ? <p>当前绑定尚无普通字段观察。</p> : <dl>
      {items.map(item => <div key={item.fieldId} className="border-b border-line py-3 last:border-0">
        <dt className="font-medium">{fields.find(field => field.ref.fieldId === item.fieldId)?.name} · {item.differs ? '观察时存在差异' : '观察时一致'}</dt>
        <dd className="m-0 whitespace-pre-wrap break-words">来源值：{label(item.fieldId, item.remoteValue)}</dd>
        <dd className="m-0 whitespace-pre-wrap break-words">观察时本地值：{item.localPresent ? label(item.fieldId, item.localValue) : '未填写'}</dd>
        <dd className="m-0 text-sm text-muted">本地版本 {item.localContentRevision} · 观察时间 {item.observedAt}</dd>
      </div>)}
    </dl>}
  </section>
}
