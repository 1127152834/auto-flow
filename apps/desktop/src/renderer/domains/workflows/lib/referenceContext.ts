// Builds the ReferenceContext (what {input...}, {node...}, PROJECT_INPUTS and {name} references mean)
// from the signature, canvas nodes, global variables and the project's input plan.
import { useWorkflowStore } from '../editor-store'
import { useSignatureStore } from '../hooks/stores/signatureStore'
import { useProjectInputs, type ProjectAutomation } from '../project-inputs'
import type { ReferenceContext } from './dataReferences'
import { nodeTitles, type DataNode, type DataVariable } from './dataSidebarModel'
import { declaredOutputs } from './nodeOutputs'
import type { SignatureInputDraft } from './signatureDocument'

export type ReferenceSources = { signature: SignatureInputDraft[]; nodes: DataNode[]; variables: DataVariable[]; automation: ProjectAutomation | null }
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)

export function buildReferenceContext({ signature, nodes, variables, automation }: ReferenceSources): ReferenceContext {
  const titles = nodeTitles(nodes)
  return {
    signature: Object.fromEntries(signature.map(input => [input.key, {
      label: input.name,
      fields: Object.fromEntries(input.fields.map(field => [field.key, { label: field.name, type: field.type, sensitive: field.sensitive, sample: field.sensitive || field.sample === undefined ? undefined : String(field.sample) }])),
    }])),
    nodeOutputs: nodes.flatMap(node => isRecord(node.data)
      ? declaredOutputs(String(node.data.moduleType)).map(output => ({ nodeId: node.id, key: output.key, name: output.name, label: titles.get(node.id)!, sensitive: output.sensitive }))
      : []),
    variables: Object.fromEntries(variables.map(variable => [variable.name, { type: variable.type }])),
    inputs: (automation?.inputPlan.inputs ?? []).map(input => ({
      inputId: input.inputId, alias: input.alias, fields: input.fieldBindings.map(binding => ({ fieldId: binding.inputFieldId, alias: binding.inputFieldAlias })),
    })),
  }
}

let lastSources: unknown[] = []
let lastKey = ''
let lastContext: ReferenceContext = {}

/** One shared result for all callers: rebuilt only when a source array changes, and kept (same object) while its content is equal. */
export function selectReferenceContext(nodes: DataNode[], variables: DataVariable[], signature: SignatureInputDraft[], automation: ProjectAutomation | null) {
  const sources = [nodes, variables, signature, automation]
  if (sources.every((source, index) => source === lastSources[index])) return lastContext
  lastSources = sources
  const next = buildReferenceContext({ signature, nodes, variables, automation })
  const key = JSON.stringify(next)
  if (key !== lastKey) { lastKey = key; lastContext = next }
  return lastContext
}

/** Reference context for the open workflow. Re-renders the caller only when the content of the context changes, not on every node drag. */
export function useReferenceContext(): ReferenceContext {
  const signature = useSignatureStore(state => state.inputs)
  const automation = useProjectInputs(state => state.automation)
  return useWorkflowStore(state => selectReferenceContext(state.nodes, state.variables, signature, automation))
}
