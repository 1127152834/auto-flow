import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const groups = ['features', 'acceptance_scenarios', 'execution_contracts_and_gates']
const kinds = new Set(['implementation_missing', 'test_missing', 'production_evidence_missing', 'external_acceptance_pending'])

// This validates references, not whether assertions satisfy the specification.
export function verifyCoverage(coverage, read = path => readFileSync(resolve(root, path), 'utf8')) {
  const ids = new Set(), errors = []
  for (const item of groups.flatMap(group => coverage[group] ?? [])) {
    const fail = message => errors.push(`${item.id}: ${message}`)
    if (ids.has(item.id)) fail('duplicate requirement')
    ids.add(item.id)
    const mapping = item.testMapping
    if (!mapping) { fail('missing reviewed test mapping'); continue }
    if (!mapping.checks?.length && !mapping.gaps?.some(gap => gap.kind === 'test_missing')) fail('no assertion or explicit missing-test gap')
    for (const gap of mapping.gaps ?? []) {
      if (!kinds.has(gap.kind) || !gap.detail?.trim()) fail('invalid gap')
    }
    for (const check of mapping.checks ?? []) {
      if (!check.scope?.trim() || !check.level?.startsWith('automated_')) fail('missing assertion scope or level')
      if (check.testName !== undefined) {
        if (!/\.test\.[jt]sx?$/.test(check.file ?? '') || typeof check.testName !== 'string' || !/^[^'"\\\r\n]+$/.test(check.testName) || check.symbol !== undefined) { fail('invalid named test case'); continue }
        const name = check.testName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        try {
          if (!new RegExp(`^\\s*(?:it|test)\\(\\s*['"]${name}['"]\\s*,`, 'm').test(read(check.file))) fail(`missing test case ${check.file}::${check.testName}`)
        } catch { fail(`unreadable test ${check.file}`) }
        continue
      }
      const python = check.file?.endsWith('.py')
      if (!(python ? /^test_\w+$/ : /^\w+$/).test(check.symbol)) { fail('invalid test symbol'); continue }
      try {
        const declaration = python ? `\\s*(?:async )?def` : '(?:export )?(?:async )?function'
        if (!new RegExp(`^${declaration} ${check.symbol}\\(`, 'm').test(read(check.file))) fail(`missing symbol ${check.file}::${check.symbol}`)
      } catch { fail(`unreadable test ${check.file}`) }
    }
    if (item.status === 'verified' && mapping.gaps?.length) fail('cannot promote an open requirement to verified')
  }
  if (ids.size !== 251) errors.push(`expected 251 unique requirements, found ${ids.size}`)
  return errors
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const coverage = JSON.parse(readFileSync(resolve(root, 'docs/project-management/implementation/coverage.json'), 'utf8'))
  const errors = verifyCoverage(coverage)
  if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1 }
  else console.log('251 mappings have valid references. This is not release acceptance.')
}
