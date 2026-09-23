import type { LayaResult } from './types'

export function automationPreview(result: LayaResult, threshold: number) {
  return {
    previewOnly: true,
    model: result.runtime.checkpoint,
    routing: result.routing,
    decisions: Object.fromEntries(Object.entries(result.answers).map(([id, answer]) => [id, {
      type: answer.type,
      value: answer.type === 'choice' ? answer.choice : answer.type === 'score' ? answer.score : answer.noul,
      probabilities: answer.probabilities,
      confidence: answer.confidence,
    }])),
    suggestedActions: Object.entries(result.answers).map(([id, answer]) => {
      if (answer.confidence < threshold) return { questionId: id, kind: 'human_review', reason: 'below_demo_threshold' }
      if (answer.type === 'choice') return { questionId: id, kind: 'route', target: answer.choice }
      if (answer.type === 'score') return { questionId: id, kind: 'set_score', value: answer.score }
      return { questionId: id, kind: answer.noul >= 0.5 ? 'flag' : 'pass', probability: answer.noul }
    }),
  }
}
