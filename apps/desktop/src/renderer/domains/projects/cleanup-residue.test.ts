import '@testing-library/jest-dom/vitest'
import { expect, it } from 'vitest'
import type { ProjectOperationPage, ProjectOperationView } from './types'
import { cleanupResidue, reportedCleanupResidue } from './cleanup-residue'

const failed = { kind: 'deleteProject', status: 'failed', error: { details: { cleanup: { residue: ['/tmp/environments/instances/e1', 7, null] } } } } as unknown as ProjectOperationView

it('keeps only the string paths the service reported as residue', () => {
  expect(cleanupResidue(failed)).toEqual(['/tmp/environments/instances/e1'])
  expect(cleanupResidue({ ...failed, error: null })).toEqual([])
  expect(cleanupResidue(undefined)).toEqual([])
})

it('reads the newest delete operation instead of unrelated project operations', () => {
  const page = { items: [{ kind: 'createTable' }, failed] } as unknown as ProjectOperationPage
  expect(reportedCleanupResidue(page)).toEqual(['/tmp/environments/instances/e1'])
  expect(reportedCleanupResidue({ ...page, items: [{ kind: 'createTable' }] } as unknown as ProjectOperationPage)).toEqual([])
})
