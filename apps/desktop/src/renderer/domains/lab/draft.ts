import type { InputMode, LayaQuestion, LayaRequest, ModelChoice, QuestionDraft } from './types'

const idPattern = /^[A-Za-z][A-Za-z0-9_]{0,39}$/

export function draftsFromQuestions(questions: LayaRequest['questions']): QuestionDraft[] {
  return Object.entries(questions).map(([id, question]) => ({
    id,
    type: question.type,
    instructions: question.instructions,
    options: question.type === 'choice' ? Object.entries(question.criteria).map(([key, description]) => ({ key, description })) : [],
    levels: question.type === 'score' ? [...question.criteria] : [],
  }))
}

export function buildRequest(model: ModelChoice, mode: InputMode, input: string, drafts: QuestionDraft[]): LayaRequest {
  let state: LayaRequest['state'] = input
  if (mode === 'json') {
    try { state = JSON.parse(input) as LayaRequest['state'] } catch { throw new Error('JSON 格式无效') }
    if (state === null || typeof state !== 'object') throw new Error('JSON 输入须为对象或数组')
  }
  const serialized = typeof state === 'string' ? state : JSON.stringify(state)
  if (!serialized?.trim() || new TextEncoder().encode(serialized).length > 16 * 1024) throw new Error('输入不能为空，且不得超过 16 KiB')
  if (drafts.length < 1 || drafts.length > 8) throw new Error('请配置 1 到 8 个问题')
  const questions: LayaRequest['questions'] = {}
  for (const draft of drafts) {
    if (!idPattern.test(draft.id) || Object.hasOwn(questions, draft.id)) throw new Error('问题 ID 须唯一、以字母开头，且最多 40 位')
    const instructions = draft.instructions.trim()
    if (!instructions || instructions.length > 256) throw new Error('问题说明不能为空，且最多 256 字')
    let question: LayaQuestion
    if (draft.type === 'choice') {
      if (draft.options.length < 2 || draft.options.length > 10) throw new Error('choice 需要 2 到 10 个候选项')
      const criteria: Record<string, string> = {}
      for (const option of draft.options) {
        if (!idPattern.test(option.key) || Object.hasOwn(criteria, option.key) || !option.description.trim() || option.description.length > 160) throw new Error('候选键须唯一、符合 ID 格式，描述必填且最多 160 字')
        criteria[option.key] = option.description
      }
      question = { type: 'choice', instructions, criteria }
    } else if (draft.type === 'score') {
      if (draft.levels.length < 2 || draft.levels.length > 10 || draft.levels.some(level => !level.trim() || level.length > 160) || new Set(draft.levels.map(level => level.trim())).size !== draft.levels.length) throw new Error('score 需要 2 到 10 个不重复的有序等级，每项最多 160 字')
      question = { type: 'score', instructions, criteria: draft.levels }
    } else question = { type: 'noul', instructions }
    questions[draft.id] = question
  }
  return { model, state, questions }
}
