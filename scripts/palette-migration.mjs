#!/usr/bin/env node
// 把写死的调色类（text-gray-500 等）迁移为语义类。默认只预览，--write 才写文件。
// 用法：node scripts/palette-migration.mjs <文件或目录...> [--write] [--report <路径>]
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = dirname(fileURLToPath(import.meta.url))
const SKIP = new Set(['node_modules', '.git', '__pycache__', 'dist', 'out'])
const COLORS = 'gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose'
// 与 ratchets.mjs 同一调色范围；前置字符保证不会吃进更长的标识符，变体前缀与 ! 留在匹配之外
const TOKEN = new RegExp(`(?<=^|[\\s'"\`:!.(])(bg|text|border|ring|from|to|via)-((?:${COLORS})-(?:50|[1-9]00|950))(\\/\\d+)?(?![\\w-])`, 'g')

export function loadMap() {
  return JSON.parse(readFileSync(join(here, 'palette-migration-map.json'), 'utf8'))
}

// 返回需要处理的区段：ts 只取字符串字面量（含模板字面量的静态部分），css 取注释以外的全部。
// ts 用 TypeScript 解析器定位字面量，JSX 文本里的撇号、正则字面量里的引号都不会打乱判断。
function segments(text, ext) {
  if (ext === '.css') return cssSegments(text)
  const out = []
  const file = ts.createSourceFile('x.tsx', text, ts.ScriptTarget.Latest, false, ts.ScriptKind.TSX)
  const visit = node => {
    const [from, to] = [node.getStart(file), node.getEnd()]
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) out.push([from + 1, to - 1])
    else if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node)) out.push([from + 1, to - 2])
    else if (ts.isTemplateTail(node)) out.push([from + 1, to - 1])
    ts.forEachChild(node, visit)
  }
  visit(file)
  return out.sort((a, b) => a[0] - b[0])
}

function cssSegments(text) {
  const out = []
  let i = 0, start = -1
  while (i < text.length) {
    if (text[i] === '/' && text[i + 1] === '*') {
      if (start >= 0) { out.push([start, i]); start = -1 }
      const e = text.indexOf('*/', i + 2)
      i = e < 0 ? text.length : e + 2
      continue
    }
    if (start < 0) start = i
    i++
  }
  if (start >= 0) out.push([start, text.length])
  return out
}

export function migrateText(text, ext, map) {
  let replaced = 0
  const unmapped = []
  let result = '', last = 0
  for (const [from, to] of segments(text, ext)) {
    result += text.slice(last, from)
    result += text.slice(from, to).replace(TOKEN, (all, prefix, key, opacity = '', offset, whole) => {
      const target = map[prefix]?.[key]
      if (!target) {
        const line = text.slice(0, from + offset).split('\n').length
        unmapped.push({ cls: `${prefix}-${key}${opacity}`, line })
        return all
      }
      replaced++
      return target + opacity
    })
    last = to
  }
  return { text: result + text.slice(last), replaced, unmapped }
}

function collect(path, out = []) {
  if (statSync(path).isDirectory()) {
    for (const name of readdirSync(path)) if (!SKIP.has(name)) collect(join(path, name), out)
  } else if (/\.(?:tsx?|css)$/.test(path)) out.push(path)
  return out
}

function renderReport(rows) {
  const lines = ['# 调色类人工校对清单', '', '| 文件 | 行 | 原类名 | 出现次数 |', '|---|---|---|---|']
  for (const r of rows) lines.push(`| ${r.file} | ${r.lines.join(', ')} | \`${r.cls}\` | ${r.lines.length} |`)
  return lines.join('\n') + '\n'
}

function main() {
  const args = process.argv.slice(2)
  const write = args.includes('--write')
  const ri = args.indexOf('--report')
  const reportPath = resolve(ri >= 0 ? args[ri + 1] : join(tmpdir(), 'palette-migration-report.md'))
  const targets = args.filter((a, i) => !a.startsWith('--') && (ri < 0 || i !== ri + 1))
  if (!targets.length) { console.error('用法：palette-migration.mjs <文件或目录...> [--dry-run|--write] [--report <路径>]'); process.exit(2) }
  if (reportPath.split(sep).includes('docs')) { console.error('校对清单不得写入 docs/，请换一个路径'); process.exit(2) }
  const map = loadMap()
  let replaced = 0, files = 0
  const byKey = new Map()
  for (const file of targets.flatMap(t => collect(resolve(t)))) {
    const src = readFileSync(file, 'utf8')
    const r = migrateText(src, file.slice(file.lastIndexOf('.')), map)
    replaced += r.replaced
    for (const u of r.unmapped) {
      const k = `${file}\0${u.cls}`
      if (!byKey.has(k)) byKey.set(k, { file, cls: u.cls, lines: [] })
      byKey.get(k).lines.push(u.line)
    }
    if (write && r.text !== src) { writeFileSync(file, r.text); files++ }
  }
  const rows = [...byKey.values()]
  const unmappedCount = rows.reduce((n, r) => n + r.lines.length, 0)
  mkdirSync(dirname(reportPath), { recursive: true })
  writeFileSync(reportPath, renderReport(rows))
  const total = replaced + unmappedCount
  console.log(`${write ? '已写入' : '预览（未写文件）'}：替换 ${replaced}，未映射 ${unmappedCount}，可替换比例 ${total ? Math.round(replaced / total * 100) : 100}%${write ? `，改动 ${files} 个文件` : ''}`)
  console.log(`校对清单：${reportPath}`)
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
