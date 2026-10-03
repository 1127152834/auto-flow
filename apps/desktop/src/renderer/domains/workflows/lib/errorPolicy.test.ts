import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { activePolicy, candidatePolicy, describePolicy } from './errorPolicy'

const cases = JSON.parse(readFileSync(resolve(__dirname, '../../../../../../backend/tests/fixtures/error_policy_candidates.json'), 'utf-8')) as { name: string; config: Record<string, unknown>; candidate: unknown }[]

describe('candidatePolicy matches the backend conversion', () => {
  it.each(cases.map(item => [item.name, item] as const))('%s', (_name, item) => {
    expect(candidatePolicy(item.config)).toEqual(item.candidate)
  })
})

it('treats only a version-2 policy as active and describes it in plain words', () => {
  const enabled = cases.at(-1)!.config
  const policy = activePolicy(enabled)
  expect(policy?.onError).toBe('retry')
  expect(describePolicy(policy!, id => id)).toBe('出错时重试 1 次')
  expect(activePolicy({ errorPolicy: { mode: 'retry-self' } })).toBeNull()
  expect(describePolicy({ ...policy!, onError: 'goto', gotoNodeId: 'login', onExhausted: 'continue' }, () => '登录')).toBe('出错时跳到「登录」×1，仍失败则继续')
})
