// Builds what the tag input needs from Studio data: the parse context for chips and the completion candidates.
import type { ReferenceContext } from '../dataReferences'
import type { AvailableOutput } from '../nodeOutputs'
import type { SignatureInputDraft } from '../signatureDocument'
import type { TagCandidate, TagGroup, TagSources } from './references'

export type TagSourceInput = {
  signature: SignatureInputDraft[]
  nodeOutputs: AvailableOutput[]
  variables: { name: string; type: string; description?: string; builtin?: boolean }[]
  /** Project references: `input.<group>.<field>`, legacy PROJECT_INPUTS[...] and PROJECT_PARAMETERS[...]. */
  projectRefs: { name: string; label: string; type: string }[]
  automationInputs?: ReferenceContext['inputs']
}

const GROUP_RANK: Record<TagGroup, number> = { input: 0, node: 1, variable: 2 }
const dot = (label: string) => label.replace(/\s*→\s*/g, '·')
const STABLE_INPUT = /^input\.([^.{}\s]+)\.([^.{}\s]+)$/

export function buildTagSources(data: TagSourceInput): TagSources {
  const signature: NonNullable<ReferenceContext['signature']> = {}
  const labels: Record<string, string> = {}
  const candidates: TagCandidate[] = []
  const seen = new Set<string>()
  const add = (candidate: TagCandidate) => {
    if (seen.has(candidate.raw)) return
    seen.add(candidate.raw)
    candidates.push(candidate)
  }

  for (const input of data.signature) {
    const fields: NonNullable<ReferenceContext['signature']>[string]['fields'] = {}
    for (const field of input.fields) {
      fields[field.key] = { label: field.name, type: field.type, sensitive: field.sensitive, sample: field.sample === undefined ? undefined : String(field.sample) }
      add({ raw: `{input.${input.key}.${field.key}}`, label: `${input.name}·${field.name}`, group: 'input', type: field.type, hint: '流程输入' })
    }
    signature[input.key] = { label: input.name, fields }
  }
  for (const ref of data.projectRefs) {
    const stable = STABLE_INPUT.exec(ref.name)
    if (stable) {
      const [alias, fieldAlias] = ref.label.split(/\s*→\s*/)
      const entry = signature[stable[1]] ??= { label: alias, fields: {} }
      entry.fields![stable[2]] ??= { label: fieldAlias ?? stable[2], type: ref.type }
    } else labels[ref.name] = dot(ref.label)
    add({ raw: `{${ref.name}}`, label: dot(ref.label), group: 'input', type: ref.type, hint: '项目数据' })
  }
  for (const output of data.nodeOutputs) {
    add({ raw: `{${output.reference}}`, label: `${output.label}·${output.name}`, group: 'node', hint: output.required ? undefined : '可能为空，使用前请判断' })
  }
  for (const variable of data.variables) {
    add({ raw: `{${variable.name}}`, label: variable.name, group: 'variable', type: variable.type, hint: variable.description })
  }

  const context: ReferenceContext = {
    signature,
    nodeOutputs: data.nodeOutputs.map(output => ({ nodeId: output.nodeId, key: output.key, name: output.name, label: output.label, sensitive: output.sensitive })),
    variables: Object.fromEntries(data.variables.map(variable => [variable.name, { type: variable.type }])),
    inputs: data.automationInputs,
  }
  candidates.sort((a, b) => GROUP_RANK[a.group] - GROUP_RANK[b.group])
  return { context, labels, candidates }
}

/** Candidates matching what was typed after `{`, best first; equal matches keep group order. */
export function filterCandidates(candidates: TagCandidate[], query: string): TagCandidate[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return candidates
  const scored = candidates.flatMap((candidate, index) => {
    const label = candidate.label.toLowerCase()
    const rank = label.startsWith(needle) ? 0
      : label.includes(needle) || candidate.raw.toLowerCase().includes(needle) ? 1
      : candidate.hint?.toLowerCase().includes(needle) ? 2 : -1
    return rank < 0 ? [] : [{ candidate, rank, index }]
  })
  scored.sort((a, b) => a.rank - b.rank || GROUP_RANK[a.candidate.group] - GROUP_RANK[b.candidate.group] || a.index - b.index)
  return scored.map(item => item.candidate)
}
