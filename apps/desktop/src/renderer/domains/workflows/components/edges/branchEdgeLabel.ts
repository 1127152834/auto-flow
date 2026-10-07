// Text on branch connections: the canvas node only labels its connection points, so a drawn line needs its own words.
const LABELS: Record<string, string> = { true: '是', false: '否', loop: '循环', done: '完成', error: '出错时' }

type LabelledEdge = { sourceHandle?: string | null; label?: unknown }

/** Label props for a branch edge, or none when the edge is a plain connection or already has a label. */
export function branchEdgeLabel(edge: LabelledEdge) {
  const label = edge.sourceHandle ? LABELS[edge.sourceHandle] : undefined
  if (!label || edge.label) return {}
  const danger = edge.sourceHandle === 'error'
  return {
    label,
    labelStyle: { fill: `hsl(var(${danger ? '--danger-700' : '--slate-800'}))`, fontSize: 11, fontWeight: 700 },
    labelBgStyle: { fill: 'hsl(var(--card))', fillOpacity: 0.95 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 4,
  }
}
