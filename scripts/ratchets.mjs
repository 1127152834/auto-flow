#!/usr/bin/env node
// Ratchet checks: existing debt may only shrink.
// Spec: docs/superpowers/specs/2026-09-30-remediation-m0-baseline-guardrails.md §5.5
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const PALETTE = /\b(?:bg|text|border|ring|from|to|via)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(?:50|[1-9]00|950)\b/g
const CONFIG_KEY = /\b(?:handleChange|onChange)\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]/g
const SKIP = new Set(['node_modules', '.git', '__pycache__', 'dist', 'out'])

function walk(root, accept, out = []) {
  let entries
  try { entries = readdirSync(root) } catch { return out }
  for (const name of entries) {
    if (SKIP.has(name)) continue
    const path = join(root, name)
    if (statSync(path).isDirectory()) walk(path, accept, out)
    else if (accept(path)) out.push(path)
  }
  return out
}

const isTest = path => /\.test\.[cm]?[jt]sx?$/.test(path) || path.split(sep).includes('tests')
const read = path => { try { return readFileSync(path, 'utf8') } catch { return '' } }

export function measure(root) {
  const workflows = join(root, 'apps/desktop/src/renderer/domains/workflows')
  const panels = [join(workflows, 'components/ConfigPanel.tsx'),
    ...walk(join(workflows, 'components/config-panels'), p => p.endsWith('.tsx') && !isTest(p))]
  const keys = new Set()
  for (const file of panels) for (const match of read(file).matchAll(CONFIG_KEY)) keys.add(match[1])
  const backend = walk(join(root, 'apps/backend/src/autoflow'), p => p.endsWith('.py')).map(read).join('\n')
  const unreadConfigKeys = [...keys].filter(key => !backend.includes(`'${key}'`) && !backend.includes(`"${key}"`)).sort()
  let paletteClasses = 0
  for (const file of walk(workflows, p => /\.(?:tsx?|css)$/.test(p))) paletteClasses += (read(file).match(PALETTE) ?? []).length
  const secondIconLibraryFiles = walk(join(root, 'apps/desktop/src'), p => /\.[cm]?[jt]sx?$/.test(p))
    .filter(p => /\bfrom\s*['"]@phosphor-icons\/react['"]/.test(read(p))).length
  const docsPng = walk(join(root, 'docs'), p => p.toLowerCase().endsWith('.png')).length
  return { unreadConfigKeys, paletteClasses, secondIconLibraryFiles, docsPng }
}

export function compare(current, baseline) {
  const failures = []
  const improvements = []
  const newKeys = current.unreadConfigKeys.filter(key => !baseline.unreadConfigKeys.includes(key))
  if (newKeys.length) failures.push(`新增了后端未读取的配置键：${newKeys.join(', ')}`)
  if (current.unreadConfigKeys.length < baseline.unreadConfigKeys.length) improvements.push('unreadConfigKeys')
  for (const name of ['paletteClasses', 'secondIconLibraryFiles', 'docsPng']) {
    if (current[name] > baseline[name]) failures.push(`${name} 从 ${baseline[name]} 增加到 ${current[name]}`)
    if (current[name] < baseline[name]) improvements.push(name)
  }
  return { failures, improvements }
}

function main() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
  const baselinePath = join(root, 'scripts/ratchets-baseline.json')
  const current = measure(root)
  if (process.argv.includes('--write-baseline')) {
    writeFileSync(baselinePath, JSON.stringify(current, null, 2) + '\n')
    console.log(`已写入基线 ${relative(root, baselinePath)}`)
    return
  }
  const { failures, improvements } = compare(current, JSON.parse(readFileSync(baselinePath, 'utf8')))
  for (const failure of failures) console.error(`✗ ${failure}`)
  if (improvements.length) console.log(`↓ 以下指标已减少，请运行 node scripts/ratchets.mjs --write-baseline 收紧基线：${improvements.join(', ')}`)
  console.log(`unreadConfigKeys=${current.unreadConfigKeys.length} paletteClasses=${current.paletteClasses} secondIconLibraryFiles=${current.secondIconLibraryFiles} docsPng=${current.docsPng}`)
  if (failures.length) process.exitCode = 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
