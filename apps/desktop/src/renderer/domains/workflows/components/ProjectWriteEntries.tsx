import { Database } from 'lucide-react'
import { projectWriteDragData, projectWriteEntries } from '../lib/moduleCatalog'

export function ProjectWriteEntries({ query }: { query: string }) {
  const entries = projectWriteEntries.filter(entry => !query || entry.label.includes(query) || entry.description.includes(query) || '项目数据'.includes(query))
  if (entries.length === 0) return null
  return <div className="mb-2" data-testid="project-write-entries">
    <div className="px-2.5 py-1.5 text-[12px] font-semibold text-[hsl(var(--slate-800))]">项目数据</div>
    <div className="ml-3 space-y-0.5 border-l border-dashed border-[hsl(var(--border))] pl-2">
      {entries.map(entry => <div key={entry.id} draggable title={entry.description} onDragStart={event => { event.dataTransfer.setData('application/reactflow', projectWriteDragData(entry)); event.dataTransfer.effectAllowed = 'move' }}
        className="flex cursor-grab items-center gap-2 rounded-control px-2 py-1.5 text-[12px] hover:bg-[hsl(var(--brand-50))]">
        <Database className="size-3.5" />{entry.label}
      </div>)}
    </div>
  </div>
}
