import { useId } from 'react'
import type { InputDefinition, InputTableOption } from './types'

const NODE_W = 150, NODE_H = 44, GAP = 50, TOP = 8

export type RelationEdge = { inputId: string; sourceId: string; label: string; sourceField?: string; targetField?: string }

export function relationEdges(inputs: InputDefinition[], tables: InputTableOption[]): RelationEdge[] {
  return inputs.flatMap(input => {
    const relation = input.mode === 'related' ? input.relation : undefined
    if (!relation || !inputs.some(item => item.inputId === relation.sourceInputId)) return []
    const source = inputs.find(item => item.inputId === relation.sourceInputId)!
    const sourceTable = tables.find(table => table.id === source.tableId), table = tables.find(item => item.id === input.tableId)
    const sourceField = relation.type === 'fieldEquals' ? sourceTable?.fields.find(field => field.ref.fieldId === relation.sourceFieldRef.fieldId)?.name ?? '字段' : undefined
    const targetField = relation.type === 'fieldEquals' ? table?.fields.find(field => field.ref.fieldId === relation.targetFieldRef.fieldId)?.name ?? '字段' : undefined
    const label = relation.type === 'sameRecord' ? '同一记录'
      : relation.type === 'fieldEquals' ? `${sourceTable?.fields.find(field => field.ref.fieldId === relation.sourceFieldRef.fieldId)?.name ?? '字段'} = ${table?.fields.find(field => field.ref.fieldId === relation.targetFieldRef.fieldId)?.name ?? '字段'}`
        : `记录槽：${sourceTable?.slotDefinitions.find(slot => slot.slotId === relation.slotId)?.name ?? '记录槽'}`
    return [{ inputId: input.inputId, sourceId: relation.sourceInputId, label, sourceField, targetField }]
  })
}

const nameOf = (input?: InputDefinition) => input?.alias || '未命名输入'
const STEP = 18

/** Read-only picture of how inputs are linked (plus a text list of the same links); selecting a link jumps to its editor. */
export function RelationGraph({ inputs, tables, onSelect }: { inputs: InputDefinition[]; tables: InputTableOption[]; onSelect(inputId: string): void }) {
  const clipBase = useId().replace(/[^a-zA-Z0-9]/g, '')
  const edges = relationEdges(inputs, tables)
  if (!edges.length) return null
  const x = (inputId: string) => inputs.findIndex(item => item.inputId === inputId) * (NODE_W + GAP) + NODE_W / 2
  // Links between the same two inputs bow out by different heights so they never overlap.
  const seen = new Map<string, number>()
  const placed = edges.map(edge => {
    const pair = [edge.inputId, edge.sourceId].sort().join('|'), rank = seen.get(pair) ?? 0
    seen.set(pair, rank + 1)
    return { edge, lift: 24 + Math.abs(x(edge.inputId) - x(edge.sourceId)) / 4 + rank * STEP }
  })
  const maxLift = Math.max(...placed.map(item => item.lift))
  const width = inputs.length * (NODE_W + GAP) - GAP, baseY = TOP + NODE_H, height = baseY + maxLift / 2 + 28 + (Math.max(...seen.values()) - 1) * STEP
  const textOf = (edge: RelationEdge) => {
    const source = nameOf(inputs.find(item => item.inputId === edge.sourceId)), target = nameOf(inputs.find(item => item.inputId === edge.inputId))
    return edge.sourceField ? `${source}·${edge.sourceField} ↔ ${target}·${edge.targetField}` : `${source} ↔ ${target}（${edge.label}）`
  }
  const keyGo = (go: () => void) => (event: React.KeyboardEvent) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); go() } }
  return <figure className="m-0 grid min-w-0 gap-1">
    <figcaption className="text-sm font-medium">输入之间的关联</figcaption>
    <div className="min-w-0 overflow-x-auto">
      <svg role="group" aria-label="输入关联图" viewBox={`0 0 ${width} ${height}`} width={width} height={height} className="max-w-none text-muted">
        <defs>
          <clipPath id={`${clipBase}-node`}><rect x={0} y={0} width={NODE_W - 12} height={NODE_H}/></clipPath>
          {placed.map(({ edge }) => { const span = Math.max(80, Math.abs(x(edge.inputId) - x(edge.sourceId)) - 8); return <clipPath key={edge.inputId} id={`${clipBase}-e-${edge.inputId.replace(/[^a-zA-Z0-9]/g, '')}`}><rect x={-span / 2} y={-14} width={span} height={20}/></clipPath> })}
        </defs>
        {placed.map(({ edge, lift }) => {
          const x1 = x(edge.sourceId), x2 = x(edge.inputId), cy = baseY + lift, mid = (x1 + x2) / 2, label = nameOf(inputs.find(item => item.inputId === edge.inputId))
          const go = () => onSelect(edge.inputId), ly = baseY + (cy - baseY) / 2 + 14
          return <g key={edge.inputId} role="button" tabIndex={0} aria-label={`关联：${edge.label}，点击跳到“${label}”的关联设置`} className="cursor-pointer" onClick={go} onKeyDown={keyGo(go)}>
            <path d={`M ${x1} ${baseY} Q ${mid} ${cy} ${x2} ${baseY}`} fill="none" stroke="currentColor" strokeWidth={1.5}/>
            <path d={`M ${x1} ${baseY} Q ${mid} ${cy} ${x2} ${baseY}`} fill="none" stroke="transparent" strokeWidth={14}/>
            <g transform={`translate(${mid} ${ly})`} clipPath={`url(#${clipBase}-e-${edge.inputId.replace(/[^a-zA-Z0-9]/g, '')})`}><text textAnchor="middle" fontSize={11} fill="currentColor">{edge.label}</text></g>
          </g>
        })}
        {inputs.map((input, index) => <g key={input.inputId} transform={`translate(${index * (NODE_W + GAP)} ${TOP})`}>
          <rect width={NODE_W} height={NODE_H} rx={6} style={{ fill: 'var(--color-surface)', stroke: 'var(--color-line)' }}/>
          <g transform="translate(6 0)" clipPath={`url(#${clipBase}-node)`}>
            <title>{nameOf(input)}</title>
            <text y={19} fontSize={12} style={{ fill: 'currentColor' }}>{nameOf(input)}</text>
            <text y={34} fontSize={11} style={{ fill: 'var(--color-muted)' }}>{tables.find(table => table.id === input.tableId)?.name ?? '数据表已失效'}</text>
          </g>
        </g>)}
      </svg>
    </div>
    <ul aria-label="关联列表" className="m-0 grid list-none gap-1 p-0">
      {edges.map(edge => <li key={edge.inputId}><button type="button" className="max-w-full cursor-pointer truncate border-0 bg-transparent p-0 text-left text-xs text-muted underline-offset-2 hover:underline" onClick={() => onSelect(edge.inputId)}>{textOf(edge)}</button></li>)}
    </ul>
  </figure>
}
