// Source: WebRPA@5ccb900e, scripts/audit-module-docs.mjs; adapted to AutoFlow's retained Chinese-only scope.
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { moduleCategories } from '../../lib/moduleCatalog.ts'

const filename = fileURLToPath(import.meta.url)
const domain = resolve(dirname(filename), '../..')
const docDirectory = join(domain, 'components/documentation')

export function parseModuleTypeLabels() {
  const text = readFileSync(join(domain, 'editor-store.ts'), 'utf8')
  const start = text.indexOf('export const moduleTypeLabels')
  if (start < 0) throw new Error('未找到 moduleTypeLabels，不能确认文档覆盖')
  const end = text.indexOf('\n}', start)
  if (end < 0) throw new Error('moduleTypeLabels 格式发生变化')
  const entries = [...text.slice(start, end).matchAll(/^\s*([A-Za-z0-9_]+)\s*:\s*'([^']+)'\s*,/gm)]
    .map(match => ({ type: match[1], label: match[2] }))
  if (!entries.length) throw new Error('没有解析到任何模块名称')
  return entries
}

export function realModules() {
  const labels = new Map(parseModuleTypeLabels().map(entry => [entry.type, entry.label]))
  const types = moduleCategories.flatMap(category => category.modules)
  if (types.length !== 213 || new Set(types).size !== 213) throw new Error('已批准的 213 节点范围发生变化')
  return types.map(type => {
    const label = labels.get(type)
    if (!label) throw new Error(`保留节点缺少中文名称: ${type}`)
    return { type, label }
  })
}

export function enumerateDocFiles() {
  const files = readdirSync(docDirectory).filter(name => /^content-.*\.ts$/.test(name) && !name.endsWith('.en.ts'))
  if (!files.length) throw new Error('没有找到中文教学文档')
  return files.map(name => join(docDirectory, name))
}

export function findUndocumentedModules() {
  const corpus = enumerateDocFiles().map(path => readFileSync(path, 'utf8')).join('\n')
  return realModules().filter(({ label }) => !corpus.includes(label))
}

export function buildReport() {
  const modules = realModules()
  const undocumented = findUndocumentedModules()
  const text = [
    'AutoFlow 保留节点中文教学覆盖审计',
    `保留节点: ${modules.length}；中文文档: ${enumerateDocFiles().length}`,
    '仅验证中文名称可检索，不代表配置说明完整或节点执行已验收。',
    ...undocumented.map(entry => `未提及: ${entry.type} ${entry.label}`),
    `未提及模块数: ${undocumented.length}`,
    `结果: ${undocumented.length ? 'FAIL' : 'PASS'}`,
  ].join('\n')
  return { text, undocumented, failed: undocumented.length > 0 }
}

if (process.argv[1] && resolve(process.argv[1]) === filename) {
  const report = buildReport()
  process.stdout.write(report.text + '\n')
  process.exitCode = report.failed ? 1 : 0
}
