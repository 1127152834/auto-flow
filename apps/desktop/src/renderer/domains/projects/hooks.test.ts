import { expect, it } from 'vitest'
import { projectKeys } from './hooks'

it('scopes directory and project reads by workspace and instance', () => {
  const conditions = { query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 } as const
  expect(projectKeys.directory('w1', 'i1', conditions)).not.toEqual(projectKeys.directory('w1', 'i2', conditions))
  expect(projectKeys.detail('w1', 'i1', 'p1')).not.toEqual(projectKeys.detail('w2', 'i1', 'p1'))
})
