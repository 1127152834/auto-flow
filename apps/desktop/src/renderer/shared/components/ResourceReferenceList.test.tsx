import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { ApiClientError } from '../api/client'
import { ResourceReferenceList, resourceReferences } from './ResourceReferenceList'

afterEach(cleanup)

const referenced = (details: Record<string, unknown>) =>
  new ApiClientError('资源仍被引用', 409, 'RESOURCE_REFERENCED', details)

it('only lists references behind the RESOURCE_REFERENCED conflict', () => {
  const error = referenced({ references: [{ kind: 'automation', projectName: '甲项目', automationName: '每日签到' }] })
  expect(resourceReferences(error)).toHaveLength(1)
  render(<ResourceReferenceList error={error} />)
  expect(screen.getByRole('alert')).toHaveTextContent('甲项目 · 自动化「每日签到」')
})

it('stays invisible for plain errors, missing details and malformed entries', () => {
  expect(resourceReferences(new Error('资源仍被引用'))).toEqual([])
  expect(resourceReferences(new ApiClientError('冲突', 409, 'PROFILE_DIRECTORY_BUSY'))).toEqual([])
  expect(resourceReferences(referenced({ references: 'not-an-array' }))).toEqual([])
  expect(resourceReferences(referenced({ references: [null, 'x'] }))).toEqual([])
  const { container } = render(<ResourceReferenceList error={new ApiClientError('冲突', 409, 'PROFILE_DIRECTORY_BUSY')} />)
  expect(container).toBeEmptyDOMElement()
})

it('falls back to the raw path when the service only reports a locator', () => {
  const error = referenced({ references: [{ kind: 'record', path: ['inputs', 'mailbox'] }] })
  render(<ResourceReferenceList error={error} />)
  expect(screen.getByRole('alert')).toHaveTextContent('inputs.mailbox')
})
