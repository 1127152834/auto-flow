// Pure helpers behind the tag input: where references sit in a text, what to call them, what to show on hover.
import { parseReferences, type ReferenceContext, type ReferencePart } from '../dataReferences'

export type RefPart = Extract<ReferencePart, { type: 'ref' }>
export type TagGroup = 'input' | 'node' | 'variable'
export type TagCandidate = { raw: string; label: string; group: TagGroup; type?: string; hint?: string }
export type TagSources = {
  context: ReferenceContext
  /** Business names for `{名称}` references the shared parser only knows as variables (e.g. fixed parameters). */
  labels?: Record<string, string>
  candidates: TagCandidate[]
  /** Called after the user picks a candidate from the list. */
  onPick?: (candidate: TagCandidate) => void
}
export type RefRange = { from: number; to: number; part: RefPart }

export const TYPE_LABELS: Record<string, string> = { string: '文本', number: '数字', boolean: '是/否', date: '日期', any: '任意', array: '列表', object: '对象' }
export const typeLabel = (type: string) => TYPE_LABELS[type] ?? type
export const EMPTY_SOURCES: TagSources = { context: {}, candidates: [] }

function resolve(part: RefPart, sources: TagSources): RefPart | null {
  if (part.kind !== 'variable') return part
  const name = part.raw.slice(1, -1)
  const label = sources.labels?.[name]
  if (label) return { ...part, display: label, valid: true }
  if (name.startsWith('PROJECT_INPUTS[')) {
    const [inner] = parseReferences(name, sources.context)
    if (inner?.type === 'ref' && inner.raw === name) return { ...inner, raw: part.raw }
  }
  // An unknown {text} may be plain JSON or prose, so it stays text instead of becoming a red tag.
  return part.valid ? part : null
}

export function findReferenceRanges(text: string, sources: TagSources): RefRange[] {
  const ranges: RefRange[] = []
  let cursor = 0
  for (const raw of parseReferences(text, sources.context)) {
    if (raw.type !== 'ref') continue
    const from = text.indexOf(raw.raw, cursor)
    if (from < 0) continue
    const to = from + raw.raw.length
    cursor = to
    const part = resolve(raw, sources)
    if (part) ranges.push({ from, to, part })
  }
  return ranges
}

export function referenceTooltip(part: RefPart): string {
  if (!part.valid) return `${part.display}\n引用已失效，点击重新选择`
  return [
    part.display,
    part.dataType && `类型：${typeLabel(part.dataType)}`,
    part.source && `来源：${part.source}`,
    part.sample !== undefined && `样例：${part.sample}`,
  ].filter(Boolean).join('\n')
}
