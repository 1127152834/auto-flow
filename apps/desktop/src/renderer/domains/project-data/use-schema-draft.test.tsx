import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useSchemaDraft } from './use-schema-draft'
import type { components } from '../../shared/api/generated'

const field: components['schemas']['DataFieldView'] = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'f' }, key: 'title', name: '标题', type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }
const initial = { sessionKey: 's', generation: 'g', directory: { tableRevision: 2, items: [field] } }

it('keeps dirty drafts through background refresh until an explicit reset', () => {
  const { result, rerender } = renderHook(props => useSchemaDraft(props), { initialProps: initial })
  act(() => result.current.apply('f', { definition: { key: 'title', name: '本地草稿', type: 'string', required: false, validation: {} } }))
  rerender({ ...initial, directory: { tableRevision: 3, items: [{ ...field, name: '远端资料', fieldRevision: 2 }] } })
  expect(result.current.candidate.fields[0].definition.name).toBe('本地草稿')
  expect(result.current.candidate.expectedTableRevision).toBe(2)
  act(() => result.current.reset())
  expect(result.current.candidate.fields[0].definition.name).toBe('远端资料')
  expect(result.current.dirty).toBe(false)
})

it('isolates new sessions and accepts a persisted original candidate for recovery', () => {
  const { result, rerender } = renderHook(props => useSchemaDraft(props), { initialProps: initial })
  act(() => result.current.apply('f', { definition: { key: 'title', name: '草稿', type: 'string', required: false, validation: {} } }))
  rerender({ ...initial, sessionKey: 'other' })
  expect(result.current.dirty).toBe(false)
  expect(result.current.candidate.fields[0].definition.name).toBe('标题')
})
