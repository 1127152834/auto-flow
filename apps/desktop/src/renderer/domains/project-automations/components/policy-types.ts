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
  /** Remediation M2 R2-03/R2-04; missing on automations saved before claim modes (treated as cycle). */
  claimMode?: 'unprocessed' | 'cycle' | 'retryFailed' | null
  retryBudget?: number | null
  retryBackoffSeconds?: number[] | null
  failurePolicy?: 'thresholds' | null
}

export type FieldErrors = Record<string, string | undefined>
export type DraftState = { dirty: boolean; valid: boolean }
