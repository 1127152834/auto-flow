import { Button } from '../../../../shared/components/ui/button'
import type { InputMatchItem } from '../../input-match-api'
import type { InputMatchState } from '../../use-input-match'

const cell = (value: unknown) => value === null || value === undefined || value === '' ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)

/** Section-level state: loading and failure (with the reason and what to do). */
export function InputMatchStatus({ state }: { state: Pick<InputMatchState, 'status' | 'error' | 'retry'> }) {
  if (state.status === 'error') return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-control border border-warning/40 bg-surface p-3 text-sm"><p className="m-0 min-w-0">无法检查当前条件匹配的行数：{state.error}。已填写的配置不受影响，请检查数据表是否可用后重试。</p><Button size="sm" onClick={state.retry}>重新检查</Button></div>
  if (state.status === 'loading') return <p role="status" className="m-0 text-xs text-muted">正在检查匹配的行数…</p>
  return null
}

/** One input's pre-check: how many rows match, how many are unprocessed, and up to three sample rows. */
export function InputMatchPreview({ item, stale }: { item?: InputMatchItem; stale?: boolean }) {
  if (!item) return null
  const note = (text: string) => <p className="m-0 text-sm text-muted" data-testid="input-match">{text}</p>
  if (item.outcome === 'dependsOnOtherInput') return note('此输入跟随所关联输入的记录，没有单独的匹配行数。')
  if (item.outcome === 'tableUnavailable') return <p className="m-0 text-sm text-warning">所选数据表已不可用，请重新选择数据表。</p>
  if (item.outcome === 'filterInvalid') return <p className="m-0 text-sm text-warning">筛选条件无法使用，请在“筛选与排序”中检查条件。</p>
  if (!item.matchedCount) return <p className="m-0 text-sm text-warning">没有符合条件的行，请检查筛选条件。</p>
  const columns = Array.from(new Set(item.sample.flatMap(row => Object.keys(row))))
  return <div className="grid min-w-0 gap-2" aria-busy={stale || undefined}>
    <p className="m-0 text-sm" data-testid="input-match">当前条件匹配 <strong>{item.matchedCount}</strong> 行{item.unprocessedCount === null ? '' : <>，其中未处理 <strong>{item.unprocessedCount}</strong> 行</>}</p>
    {columns.length ? <div className="min-w-0 overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs" aria-label="样例行">
        <thead><tr>{columns.map(column => <th key={column} scope="col" className="whitespace-nowrap border-b border-line px-2 py-1 font-medium text-muted">{column}</th>)}</tr></thead>
        <tbody>{item.sample.map((row, rowIndex) => <tr key={rowIndex}>{columns.map(column => <td key={column} className="max-w-48 truncate border-b border-line px-2 py-1">{cell(row[column])}</td>)}</tr>)}</tbody>
      </table>
    </div> : <p className="m-0 text-xs text-muted">还没有绑定字段，添加字段映射后可查看样例行。</p>}
  </div>
}
