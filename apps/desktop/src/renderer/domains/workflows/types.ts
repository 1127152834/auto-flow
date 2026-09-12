import type { components } from '../../shared/api/generated'

export type WorkflowDocument = components['schemas']['WorkflowDocument']
export type WorkflowNode = components['schemas']['WorkflowNode']
export type WorkflowEdge = components['schemas']['WorkflowEdge']
export type WorkflowVariable = components['schemas']['WorkflowVariable']
export type WorkflowLayout = components['schemas']['WorkflowLayout']
export type WorkflowRead = components['schemas']['WorkflowRead']
export type WorkflowIssue = components['schemas']['WorkflowIssue']
export type NodeDefinition = components['schemas']['WorkflowNodeDefinition']
export type WorkflowList = components['schemas']['WorkflowList']
export type WorkflowCatalog = components['schemas']['WorkflowCatalog']
export type WorkflowContent = Pick<WorkflowRead, 'document' | 'layout'>
export type Point = { x: number; y: number }
