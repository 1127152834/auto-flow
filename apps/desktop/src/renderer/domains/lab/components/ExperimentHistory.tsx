import { Button } from '../../../shared/components/ui/button'
import type { ExperimentRecord } from '../types'

export function ExperimentHistory({ records, pending, onRestore, onRemove }: { records: ExperimentRecord[]; pending: boolean; onRestore(record: ExperimentRecord): void; onRemove(id: string): void }) {
  return <section className="grid gap-4 rounded-card border border-line bg-surface p-5" aria-labelledby="lab-history-heading"><div><h2 id="lab-history-heading" className="m-0 text-lg font-semibold">实验记录</h2><p className="mb-0 mt-1 text-sm text-muted">手动保存，最多保留当前工作区最近 20 条。原始输入存于此设备。</p></div>
    {records.length ? <ul className="m-0 grid list-none gap-2 p-0">{records.map(record => <li key={record.id} className="flex flex-wrap items-center justify-between gap-3 rounded-control bg-surface-subtle px-3 py-2 text-sm"><div className="min-w-0"><strong className="block">{Object.keys(record.request.questions).join(' · ')}</strong><span className="text-xs text-muted">{new Date(record.createdAt).toLocaleString()} · {record.result.routing.selected} · {record.result.timing.inferenceMs.toFixed(1)} ms</span></div><div className="flex gap-1"><Button size="sm" disabled={pending} onClick={() => onRestore(record)}>查看</Button><Button size="sm" variant="ghost" disabled={pending} onClick={() => onRemove(record.id)}>删除</Button></div></li>)}</ul> : <p className="m-0 text-sm text-muted">尚未保存实验。</p>}
  </section>
}
