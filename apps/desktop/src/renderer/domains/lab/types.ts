import type { components } from '../../shared/api/generated'

export type LayaRequest = components['schemas']['LayaPredictRequest']
export type LayaResult = components['schemas']['LayaPredictRead']
export type LayaStatus = components['schemas']['LayaStatusRead']
export type LayaQuestion = LayaRequest['questions'][string]
export type ModelChoice = LayaRequest['model']

export type QuestionDraft = {
  id: string
  type: LayaQuestion['type']
  instructions: string
  options: { key: string; description: string }[]
  levels: string[]
}

export type InputMode = 'text' | 'json'

export type ExperimentRecord = {
  id: string
  createdAt: string
  request: LayaRequest
  result: LayaResult
}
