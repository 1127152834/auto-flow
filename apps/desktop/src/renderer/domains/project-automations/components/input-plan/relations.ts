import type { InputDefinition, InputTableOption } from './types'

export type RelationKind = 'sameRecord' | 'fieldEquals' | 'recordSlot'
export type RelationContext = { tables: InputTableOption[]; inputs: InputDefinition[] }

const tableOf = (context: RelationContext, input: InputDefinition) => context.tables.find(item => item.id === input.tableId)

export function relationCapabilities(context: RelationContext, input: InputDefinition, candidate: InputDefinition): Record<RelationKind, boolean> {
  const table = tableOf(context, input), candidateTable = tableOf(context, candidate)
  return {
    sameRecord: candidate.tableId === input.tableId && candidate.datasetGeneration === input.datasetGeneration,
    fieldEquals: Boolean(candidateTable?.fields.some(field => table?.fields.some(target => target.type === field.type))),
    recordSlot: Boolean(candidateTable?.slotDefinitions.some(slot => slot.targetTableId === input.tableId)),
  }
}

export function relationFor(context: RelationContext, input: InputDefinition, type: string, sourceId: string): InputDefinition['relation'] | null {
  const source = context.inputs.find(item => item.inputId === sourceId)
  if (!source || !relationCapabilities(context, input, source)[type as RelationKind]) return null
  const table = tableOf(context, input), sourceTable = tableOf(context, source)
  if (type === 'sameRecord') return { type: 'sameRecord', sourceInputId: sourceId }
  if (type === 'fieldEquals') {
    const sourceField = sourceTable?.fields.find(field => table?.fields.some(target => target.type === field.type)), targetField = table?.fields.find(field => field.type === sourceField?.type)
    return sourceField && targetField ? { type: 'fieldEquals', sourceInputId: sourceId, sourceFieldRef: sourceField.ref, targetFieldRef: targetField.ref } : null
  }
  const slot = (sourceTable?.slotDefinitions ?? []).find(item => item.targetTableId === input.tableId)
  return slot ? { type: 'recordSlot', sourceInputId: sourceId, slotId: slot.slotId } : null
}

export function firstRelationFor(context: RelationContext, input: InputDefinition, candidate: InputDefinition) {
  const capabilities = relationCapabilities(context, input, candidate)
  const type = (['sameRecord', 'fieldEquals', 'recordSlot'] as const).find(item => capabilities[item])
  return type ? relationFor(context, input, type, candidate.inputId) : null
}
