import { Database } from 'lucide-react'
import { projectWriteDragData, type ProjectWriteEntry } from '../lib/moduleCatalog'
import { matchProjectWriteEntries } from '../lib/projectWriteSearch'
import { useProjectInputs } from '../project-inputs'

/** Write-back entries for the current search; empty unless the workflow was opened from a project automation. */
export function useProjectWriteEntries(query: string): readonly ProjectWriteEntry[] {
  const inProject = useProjectInputs(state => state.automation !== null)
  return inProject ? matchProjectWriteEntries(query) : []
}

export function ProjectWriteEntries({ entries }: { entries: readonly ProjectWriteEntry[] }) {
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
