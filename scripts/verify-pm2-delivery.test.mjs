import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { verifyPm2Delivery } from './verify-pm2-delivery.mjs'
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
const coverage = read('../docs/project-management/implementation/coverage.json')
const original = read('../docs/project-management/implementation/pm2-revised-delivery.json')

test('PM2 static coverage does not certify pending business or real application acceptance', () => {
  const report = structuredClone(original)
  report.status = 'inProgress'
  assert.equal(verifyPm2Delivery(report, coverage, { exists: () => true }).deliveryStatus, 'inProgress')
  assert.throws(() => verifyPm2Delivery(report, coverage, { requireComplete: true, exists: () => true }), /not fully accepted/)
})
test('PM2 rejects lost requirement identifiers and invented evidence paths', () => {
  const report = structuredClone(original)
  report.acceptanceIds.pop()
  assert.throws(() => verifyPm2Delivery(report, coverage, { exists: () => true }))
  assert.throws(() => verifyPm2Delivery(original, coverage, { exists: () => false }), /missing/)
})
test('a green machine report cannot substitute for real application evidence', () => {
  const report = structuredClone(original)
  report.status = 'passed'
  for (const pack of report.packages) { pack.status = 'verified'; pack.evidence = ['test-evidence'] }
  report.realApplication = { status: 'notExecuted', evidence: [] }
  assert.throws(() => verifyPm2Delivery(report, coverage, { requireComplete: true, exists: () => true }), /Real application/)
})
