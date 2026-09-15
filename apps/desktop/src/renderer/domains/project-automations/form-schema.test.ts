import { describe, expect, it } from 'vitest'
import { automationToForm, emptyAutomationForm, normalizeAutomation, validateAutomationForm } from './form-schema'

describe('automation aggregate form', () => {
  it('validates Unicode code points and follows server text trimming', () => {
    const value = { ...emptyAutomationForm('11111111-1111-4111-8111-111111111111'), name: ` ${'😀'.repeat(80)} `, description: ' 说明 ' }
    expect(validateAutomationForm(value)).toEqual({})
    expect(normalizeAutomation(value).name).toBe('😀'.repeat(80))
    expect(normalizeAutomation(value).description).toBe('说明')
    expect(validateAutomationForm({ ...value, name: '😀'.repeat(81) }).name).toBeTruthy()
  })
  it('keeps absence, null, false, zero and empty string distinct in a detached draft', () => {
    const value = { ...emptyAutomationForm('11111111-1111-4111-8111-111111111111'), name: '资料整理', parameterSchema: [undefined, null, false, 0, ''].map((defaultValue, index) => ({ parameterId: `p${index}`, name: `参数${index}`, type: (index === 2 ? 'boolean' : index === 3 ? 'number' : 'string') as 'string' | 'number' | 'boolean', required: false, ...(defaultValue === undefined ? {} : { defaultValue }) })) }
    const draft = automationToForm(value)
    expect(draft.parameterSchema).toEqual(value.parameterSchema)
    expect(Object.hasOwn(draft.parameterSchema[0], 'defaultValue')).toBe(false)
    draft.parameterSchema[0].name = '修改'
    expect(value.parameterSchema[0].name).toBe('参数0')
  })
  it('reports every duplicate parameter and finite number error without coercion', () => {
    const value = { ...emptyAutomationForm('11111111-1111-4111-8111-111111111111'), name: '资料整理', parameterSchema: [{ parameterId: 'a', name: '数量', type: 'number' as const, required: false, defaultValue: Infinity }, { parameterId: 'b', name: '数量', type: 'boolean' as const, required: false, defaultValue: 0 }] }
    const errors = validateAutomationForm(value)
    expect(errors['parameterSchema.0.name']).toBeTruthy()
    expect(errors['parameterSchema.1.name']).toBeTruthy()
    expect(errors['parameterSchema.0.defaultValue']).toBeTruthy()
    expect(errors['parameterSchema.1.defaultValue']).toBeTruthy()
  })
  it('retains fractional seconds and rejects invalid run values', () => {
    const value = { ...emptyAutomationForm('11111111-1111-4111-8111-111111111111'), name: '资料整理' }
    value.runPolicy.automaticExecutionTimeoutSeconds = 0.5
    expect(validateAutomationForm(value)).toEqual({})
    value.runPolicy.maxTasks = 101
    value.runPolicy.manualDeadlineSeconds = Infinity
    expect(validateAutomationForm(value)['runPolicy.maxTasks']).toBeTruthy()
    expect(validateAutomationForm(value)['runPolicy.manualDeadlineSeconds']).toBeTruthy()
  })
})

it('allows bounded data concurrency while parameter-only policies remain serial', () => {
  const value = { ...emptyAutomationForm('workflow'), name: '数据运行' }
  value.runPolicy.concurrency = 4; value.runPolicy.maxLiveInstances = 2
  expect(validateAutomationForm(value)['runPolicy.concurrency']).toBeTruthy()
  value.inputPlan.inputs = [{ inputId: 'input', alias: '资料', tableId: 'table', datasetGeneration: 'generation', mode: 'independent', required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }]
  expect(validateAutomationForm(value)).toEqual({})
  for (const invalid of [0, 101, 1.5, Infinity]) {
    expect(validateAutomationForm({ ...value, runPolicy: { ...value.runPolicy, concurrency: invalid } })['runPolicy.concurrency']).toBeTruthy()
    expect(validateAutomationForm({ ...value, runPolicy: { ...value.runPolicy, maxLiveInstances: invalid } })['runPolicy.maxLiveInstances']).toBeTruthy()
  }
})
