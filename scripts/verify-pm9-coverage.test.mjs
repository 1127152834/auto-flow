import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { verifyCoverage } from './verify-pm9-coverage.mjs'

const coverage = JSON.parse(readFileSync(new URL('../docs/project-management/implementation/coverage.json', import.meta.url), 'utf8'))

test('every PM9 requirement names reviewed assertions or a specific missing-test gap', () => {
  for (const group of ['features', 'acceptance_scenarios', 'execution_contracts_and_gates']) {
    for (const item of coverage[group]) {
      assert.ok(item.testMapping, `${item.id}: missing reviewed test mapping`)
      assert.ok(item.testMapping.checks.length || item.testMapping.gaps.some(gap => gap.kind === 'test_missing'), item.id)
    }
  }
})

test('rejects broken references, invalid classifications and unsupported promotions', () => {
  const fixture = structuredClone(coverage)
  const item = fixture.features[0]
  item.testMapping.checks[0].symbol = 'test_missing_pm9_assertion'
  item.testMapping.gaps.push({ kind: 'passed', detail: 'not evidence' })
  item.testMapping.statusBeforeReview = 'planned'
  item.status = 'verified'
  const errors = verifyCoverage(fixture)
  assert.ok(errors.some(error => error.includes('missing symbol')))
  assert.ok(errors.some(error => error.includes('invalid gap')))
  assert.ok(errors.some(error => error.includes('cannot promote')))
})

test('all current references resolve without upgrading acceptance', () => {
  assert.deepEqual(verifyCoverage(coverage), [])
})
