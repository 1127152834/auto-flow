import type { components } from '../../../../shared/api/generated'
import type { Automation } from '../../types'

type Schema = components['schemas']
export type Plan = Automation['inputPlan']
export type InputDefinition = Plan['inputs'][number]
export type RecordRef = NonNullable<InputDefinition['fixedRecord']>
export type FieldOption = Schema['DataFieldView']
export type InputTableOption = { id: string; name: string; datasetGeneration: string; identity?: Schema['DataTableView']['identity']; fields: FieldOption[]; statuses: Schema['DataStatusView'][]; slotDefinitions: Schema['TableSlotDefinition'][]; records?: { label: string; ref: RecordRef }[] }
export type SignatureGroup = Schema['WorkflowSignatureInput']
