import type { InputDefinition, InputTableOption } from './types'

const NODE_W = 150, NODE_H = 44, GAP = 50, TOP = 8

export type RelationEdge = { inputId: string; sourceId: string; label: string }

export function relationEdges(inputs: InputDefinition[], tables: InputTableOption[]): RelationEdge[] {
  return inputs.flatMap(input => {
    const relation = input.mode === 'related' ? input.relation : undefined
    if (!relation || !inputs.some(item => item.inputId === relation.sourceInputId)) return []
    const source = inputs.find(item => item.inputId === relation.sourceInputId)!
    const sourceTable = tables.find(table => table.id === source.tableId), table = tables.find(item => item.id === input.tableId)
    const label = relation.type === 'sameRecord' ? '同一记录'
      : relation.type === 'fieldEquals' ? `${sourceTable?.fields.find(field => field.ref.fieldId === relation.sourceFieldRef.fieldId)?.name ?? '字段'} = ${table?.fields.find(field => field.ref.fieldId === relation.targetFieldRef.fieldId)?.name ?? '字段'}`
        : `记录槽：${sourceTable?.slotDefinitions.find(slot => slot.slotId === relation.slotId)?.name ?? '记录槽'}`
    return [{ inputId: input.inputId, sourceId: relation.sourceInputId, label }]
  })
}

/** Read-only picture of how inputs are linked; selecting a link jumps to its editor. */
export function RelationGraph({ inputs, tables, onSelect }: { inputs: InputDefinition[]; tables: InputTableOption[]; onSelect(inputId: string): void }) {
  const edges = relationEdges(inputs, tables)
  if (!edges.length) return null
  const x = (inputId: string) => inputs.findIndex(item => item.inputId === inputId) * (NODE_W + GAP) + NODE_W / 2
  const lift = (edge: RelationEdge) => 24 + Math.abs(x(edge.inputId) - x(edge.sourceId)) / 4
  const maxLift = Math.max(...edges.map(lift))
  const width = inputs.length * (NODE_W + GAP) - GAP, baseY = TOP + NODE_H, height = baseY + maxLift / 2 + 28
  return <figure className="m-0 grid min-w-0 gap-1">
    <figcaption className="text-sm font-medium">输入之间的关联</figcaption>
    <div className="min-w-0 overflow-x-auto">
      <svg role="img" aria-label="输入关联图" viewBox={`0 0 ${width} ${height}`} width={width} height={height} className="max-w-none text-muted">
        {edges.map(edge => {
          const x1 = x(edge.sourceId), x2 = x(edge.inputId), cy = baseY + lift(edge), mid = (x1 + x2) / 2, label = inputs.find(item => item.inputId === edge.inputId)?.alias || '未命名输入'
          const go = () => onSelect(edge.inputId)
          return <g key={edge.inputId} role="button" tabIndex={0} aria-label={`关联：${edge.label}，点击跳到“${label}”的关联设置`} className="cursor-pointer" onClick={go} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); go() } }}>
            <path d={`M ${x1} ${baseY} Q ${mid} ${cy} ${x2} ${baseY}`} fill="none" stroke="currentColor" strokeWidth={1.5}/>
            <path d={`M ${x1} ${baseY} Q ${mid} ${cy} ${x2} ${baseY}`} fill="none" stroke="transparent" strokeWidth={14}/>
            <text x={mid} y={baseY + (cy - baseY) / 2 + 14} textAnchor="middle" fontSize={11} fill="currentColor">{edge.label}</text>
          </g>
        })}
        {inputs.map((input, index) => <g key={input.inputId} transform={`translate(${index * (NODE_W + GAP)} ${TOP})`}>
          <rect width={NODE_W} height={NODE_H} rx={6} style={{ fill: 'var(--color-surface)', stroke: 'var(--color-line)' }}/>
          <text x={NODE_W / 2} y={19} textAnchor="middle" fontSize={12} style={{ fill: 'currentColor' }}>{(input.alias || '未命名输入').slice(0, 12)}</text>
          <text x={NODE_W / 2} y={34} textAnchor="middle" fontSize={11} style={{ fill: 'var(--color-muted)' }}>{(tables.find(table => table.id === input.tableId)?.name ?? '数据表已失效').slice(0, 14)}</text>
        </g>)}
      </svg>
    </div>
  </figure>
}
