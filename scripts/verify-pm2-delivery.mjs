import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
const read = path => JSON.parse(readFileSync(path, 'utf8'))
export function verifyPm2Delivery(report, coverage, { requireComplete = false, exists = existsSync } = {}) {
  const ids = entries => entries.map(entry => entry.id).sort()
  for (const collection of ['features', 'acceptance_scenarios', 'execution_contracts_and_gates']) {
    assert.equal(new Set(ids(coverage[collection])).size, coverage[collection].length, `${collection}: duplicate IDs`)
  }
  assert.deepEqual([...report.featureIds].sort(), ids(coverage.features.filter(item => item.first_usable === 'PM2')))
  assert.deepEqual([...report.acceptanceIds].sort(), ids(coverage.acceptance_scenarios.filter(item => item.first_implementation === 'PM2')))
  assert.deepEqual(ids(report.packages), ['P0', 'P1', 'P2', 'P3', 'P4', 'P5'])
  for (const pack of report.packages) {
    for (const file of [...pack.files, ...pack.evidence]) assert.ok(exists(file), `${pack.id}: missing ${file}`)
    if (pack.status === 'verified') assert.ok(pack.evidence.length > 0, `${pack.id}: no evidence`)
  }
  if (requireComplete) {
    assert.equal(report.status, 'passed', 'PM2 is not fully accepted')
    assert.ok(report.packages.every(pack => pack.status === 'verified'))
    assert.equal(report.realApplication.status, 'passed', 'Real application acceptance is required')
    assert.ok(report.realApplication.evidence.length > 0)
    for (const file of report.realApplication.evidence) assert.ok(exists(file), `missing ${file}`)
  }
  return { staticCoverage: 'passed', deliveryStatus: report.status, featureCount: report.featureIds.length, acceptanceCount: report.acceptanceIds.length, realApplication: report.realApplication.status }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const report = read('docs/project-management/implementation/pm2-revised-delivery.json')
  console.log(JSON.stringify(verifyPm2Delivery(report, read(report.coverage), { requireComplete: process.argv.includes('--require-complete') })))
}
