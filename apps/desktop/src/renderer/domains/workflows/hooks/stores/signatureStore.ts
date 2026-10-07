import { create } from 'zustand'
import { parseSignatureDocument, serializeSignature, validateSignature, type SignatureFieldDraft, type SignatureInputDraft, type SignatureIssue } from '../../lib/signatureDocument'

type FieldInit = Pick<SignatureFieldDraft, 'key' | 'name' | 'type'> & Partial<Pick<SignatureFieldDraft, 'required' | 'sensitive' | 'sample'>>
type FieldPatch = Partial<Omit<SignatureFieldDraft, 'rest'>>
type IssueFetcher = (workflowId: string) => Promise<{ success: boolean; data?: { signatureIssues?: SignatureIssue[] } }>

interface SignatureState {
  inputs: SignatureInputDraft[]
  rest: Record<string, unknown>
  baseline: string
  /** Problems in the stored signature (local check). */
  loadIssues: SignatureIssue[]
  /** Problems the backend reported for the stored signature. */
  serverIssues: SignatureIssue[]
  /** Problems in the current edit; empty when saving is allowed. */
  issues: SignatureIssue[]
  dirty: boolean
  /** A stored signature with problems is shown but never overwritten. */
  readOnly: boolean
  canSave: boolean
  epoch: number
  reset(): void
  load(raw: unknown): void
  markSaved(): void
  refreshIssues(workflowId: string, fetchIssues: IssueFetcher): Promise<void>
  addInput(input: { key: string; name: string }): void
  updateInput(key: string, patch: Partial<Pick<SignatureInputDraft, 'key' | 'name'>>): void
  removeInput(key: string): void
  addField(inputKey: string, field: FieldInit): void
  updateField(inputKey: string, fieldKey: string, patch: FieldPatch): void
  removeField(inputKey: string, fieldKey: string): void
  /** The signature to write into the document, or undefined to leave the stored one alone. */
  serialize(): Record<string, unknown> | undefined
}

const snapshot = (inputs: SignatureInputDraft[], rest: Record<string, unknown>) => JSON.stringify(serializeSignature(inputs, rest))
const empty = { inputs: [], rest: {}, baseline: snapshot([], {}), loadIssues: [], serverIssues: [], issues: [], dirty: false, readOnly: false, canSave: true }

export const useSignatureStore = create<SignatureState>((set, get) => {
  const edit = (change: (inputs: SignatureInputDraft[]) => SignatureInputDraft[]) => {
    const state = get()
    if (state.readOnly) return
    const inputs = change(state.inputs)
    const issues = validateSignature(inputs)
    set({ inputs, issues, dirty: snapshot(inputs, state.rest) !== state.baseline, canSave: issues.length === 0 })
  }
  const withInput = (key: string, change: (input: SignatureInputDraft) => SignatureInputDraft) => edit(inputs => inputs.map(input => input.key === key ? change(input) : input))
  return {
    ...empty,
    epoch: 0,
    reset: () => set(state => ({ ...empty, epoch: state.epoch + 1 })),
    load(raw) {
      const parsed = parseSignatureDocument(raw)
      set(state => ({
        inputs: parsed.inputs, rest: parsed.rest, baseline: snapshot(parsed.inputs, parsed.rest), loadIssues: parsed.issues, serverIssues: [],
        issues: parsed.issues, dirty: false, readOnly: parsed.issues.length > 0, canSave: parsed.issues.length === 0, epoch: state.epoch + 1,
      }))
    },
    // A draft that could not be serialized was not saved, so it must stay unsaved instead of looking saved.
    markSaved: () => set(state => (state.canSave && !state.readOnly ? { baseline: snapshot(state.inputs, state.rest), dirty: false } : {})),
    async refreshIssues(workflowId, fetchIssues) {
      const epoch = get().epoch
      const result = await fetchIssues(workflowId)
      if (!result.success || get().epoch !== epoch) return
      const serverIssues = result.data?.signatureIssues ?? []
      set(state => ({ serverIssues, readOnly: state.loadIssues.length > 0 || serverIssues.length > 0 }))
    },
    addInput: ({ key, name }) => edit(inputs => [...inputs, { key, name, fields: [], rest: {} }]),
    updateInput: (key, patch) => withInput(key, input => ({ ...input, ...patch })),
    removeInput: key => edit(inputs => inputs.filter(input => input.key !== key)),
    addField: (inputKey, field) => withInput(inputKey, input => ({
      ...input, fields: [...input.fields, { required: false, sensitive: false, ...field, ...(field.sensitive ? { sample: undefined } : {}), rest: {} }],
    })),
    updateField: (inputKey, fieldKey, patch) => withInput(inputKey, input => ({
      ...input, fields: input.fields.map(field => field.key === fieldKey ? { ...field, ...patch, ...(patch.sensitive ? { sample: undefined } : {}) } : field),
    })),
    removeField: (inputKey, fieldKey) => withInput(inputKey, input => ({ ...input, fields: input.fields.filter(field => field.key !== fieldKey) })),
    serialize() {
      const { dirty, readOnly, canSave, inputs, rest } = get()
      return dirty && !readOnly && canSave ? serializeSignature(inputs, rest) : undefined
    },
  }
})
