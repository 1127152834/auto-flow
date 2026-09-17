export type JsonScalar = string | number | boolean | null

export type ParameterDefinition = {
  parameterId: string
  name: string
  description?: string
  type: 'string' | 'number' | 'boolean'
  required: boolean
  defaultValue?: JsonScalar
}

export type RunPolicy = {
  maxTasks?: number
  concurrency: number
  maxLiveInstances: number
  continueAfterFailure: boolean
  automaticExecutionTimeoutSeconds: number
  manualDeadlineSeconds: number
}

export type FieldErrors = Record<string, string | undefined>
export type DraftState = { dirty: boolean; valid: boolean }
