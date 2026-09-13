// @ts-check
/* ============================================================
   教学文档覆盖与中英同步审计（module-integrity-audit 任务 9）

   要守的规则有两条：
     1. 每个真实模块的中文名，在中文教学文档里至少被提及一次
        —— 用户查文档时搜的就是模块中文名，搜不到等于这个模块没文档。
     2. 中文文档与英文文档一一成对，且章节骨架一致
        —— 单边存在或章节数/层级序列不同，说明英文版漏同步。

   判定口径（与 spec 的「569」口径一致）：
     真实模块 = moduleTypeLabels 全部键 减去 PSEUDO_TYPES（custom_module、subflow_header）。
     group（分组）与 note（便签）是画布工具，但对外披露口径把它们计入 569，
     因此本审计也把它们当作需要文档提及的对象。

   「已提及」判定：
     模块中文名作为**子串**出现在任一 content-*.ts（排除 content-*.en.ts）中。
     标准客观、可自动化，且与用户真实检索行为一致。
     宁可误报也不漏报：文档里只写了别名（如只写「点击」而没写「点击元素」）一律判为未提及；
     确属别名表述的，登记进 MODULE_NAME_ALIASES 并写明理由。

   中英同步判定：
     取两份文档的 Markdown 标题（^#{2,3} ）序列，比对**数量与层级序列**。
     标题是翻译过的，无法直接字符串比对，所以只能比骨架。
     ！已知局限：「标题数与层级都对、但标题下的正文没同步」本脚本查不出来，
       这类问题需要人工评审补足（见 design.md 组件 5）。

   运行：
     node frontend/scripts/audit-module-docs.mjs
   退出码：存在未提及模块 / 单边文档 / 章节序列不一致 → 1，全部通过 → 0。
   本脚本禁止输出 Emoji。
   ============================================================ */
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const __filename = fileURLToPath(import.meta.url)
const FRONTEND_ROOT = resolve(dirname(__filename), '..')
const DOC_DIR = join(FRONTEND_ROOT, 'components', 'documentation')
const STORE_FILE = join(FRONTEND_ROOT, 'src', 'store', 'workflowStore.ts')

/**
 * 伪类型：出现在 moduleTypeLabels 中但不是可拖拽功能模块的条目。
 * 对外披露口径 569 = 571 - 这两项，故审计也排除它们。
 */
export const PSEUDO_TYPES = new Set(['custom_module', 'subflow_header'])

/**
 * 显式别名映射表：module_type -> { aliases: string[], reason: string }
 *
 * 仅用于「文档中确实以别名完整表述了该模块、中文名本身不出现」的情况。
 * 每条必须写明理由。禁止用本表降低未提及数——放宽判定等于把守护网撕个洞。
 * 当前为空：任务 9 阶段只确认失败，别名条目待任务 16 补文档时按需逐条登记。
 */
export const MODULE_NAME_ALIASES = Object.freeze({
  // 示例（当前未启用）：
  // some_type: { aliases: ['某别名'], reason: '文档统一用该别名表述，中文名仅出现在模块列表' },
})

/** 读取 UTF-8 文本。 */
function readText(path) {
  return readFileSync(path, 'utf8')
}

/**
 * 解析 moduleTypeLabels，返回 { type, label }[]。
 * 解析失败（找不到定义、条目为 0）抛异常，禁止静默返回空数组导致审计假绿。
 */
export function parseModuleTypeLabels() {
  const text = readText(STORE_FILE)
  const start = text.indexOf('export const moduleTypeLabels')
  if (start === -1) throw new Error('workflowStore.ts 中未找到 moduleTypeLabels 定义')
  const bodyStart = text.indexOf('{', start)
  const end = text.indexOf('\n}', bodyStart)
  if (bodyStart === -1 || end === -1) throw new Error('moduleTypeLabels 定义体解析失败')
  const body = text.slice(bodyStart, end)

  const entries = []
  const re = /^\s*([A-Za-z0-9_]+)\s*:\s*'([^']+)'\s*,/gm
  let m
  while ((m = re.exec(body)) !== null) {
    entries.push({ type: m[1], label: m[2] })
  }
  if (entries.length === 0) throw new Error('moduleTypeLabels 解析出 0 条，解析器已失效')
  return entries
}

/** 真实模块（排除伪类型）。 */
export function realModules() {
  return parseModuleTypeLabels().filter((e) => !PSEUDO_TYPES.has(e.type))
}

/**
 * 伪类型中未被提及的条目，仅用于与 design.md 的实测值（571 口径 = 213 条）对账。
 * 不计入失败数：伪类型不是用户可拖拽的功能模块，不应要求教学文档为它写章节。
 */
function undocumentedPseudoTypes(corpus) {
  return parseModuleTypeLabels()
    .filter((e) => PSEUDO_TYPES.has(e.type))
    .filter((e) => !corpus.includes(e.label))
}

/**
 * 枚举教学文档文件。
 * 返回 { zhFiles: Map<base, absPath>, enFiles: Map<base, absPath> }
 */
export function enumerateDocFiles() {
  const zhFiles = new Map()
  const enFiles = new Map()
  for (const name of readdirSync(DOC_DIR)) {
    if (!name.startsWith('content-') || !name.endsWith('.ts')) continue
    const base = name.replace(/\.ts$/, '')
    if (base.endsWith('.en')) enFiles.set(base.replace(/\.en$/, ''), join(DOC_DIR, name))
    else zhFiles.set(base, join(DOC_DIR, name))
  }
  if (zhFiles.size === 0) throw new Error('未找到任何 content-*.ts 中文教学文档，解析器已失效')
  return { zhFiles, enFiles }
}

/** 拼接全部中文教学文档正文。 */
function buildZhCorpus(zhFiles) {
  let combined = ''
  for (const path of zhFiles.values()) combined += '\n' + readText(path)
  return combined
}

/**
 * 未被任何中文教学文档提及的模块清单。
 * @returns {{ type: string, label: string }[]}
 */
export function findUndocumentedModules() {
  const { zhFiles } = enumerateDocFiles()
  const corpus = buildZhCorpus(zhFiles)
  const gaps = []
  for (const { type, label } of realModules()) {
    if (corpus.includes(label)) continue
    const alias = MODULE_NAME_ALIASES[type]
    if (alias && alias.aliases.some((a) => corpus.includes(a))) continue
    gaps.push({ type, label })
  }
  return gaps
}

/**
 * 提取 Markdown 二三级标题的层级序列。
 * 文档正文写在 TS 模板字符串里，标题按行首 ## / ### 匹配。
 * @returns {number[]} 每个标题的层级（2 或 3），按出现顺序
 */
export function extractHeadingLevels(text) {
  const levels = []
  const re = /^(#{2,3}) /gm
  let m
  while ((m = re.exec(text)) !== null) levels.push(m[1].length)
  return levels
}

/**
 * 中英文档同步缺口。
 * 三类：中文有英文无（missing-en）、英文有中文无（missing-zh）、章节序列不一致（section-mismatch）。
 * @returns {{ file: string, kind: string, section: string }[]}
 */
export function findDocSectionGaps() {
  const { zhFiles, enFiles } = enumerateDocFiles()
  const gaps = []

  for (const [base, zhPath] of [...zhFiles].sort()) {
    const enPath = join(DOC_DIR, base + '.en.ts')
    if (!existsSync(enPath)) {
      gaps.push({ file: base + '.ts', kind: 'missing-en', section: '缺少对应英文版 ' + base + '.en.ts' })
      continue
    }
    const zhLevels = extractHeadingLevels(readText(zhPath))
    const enLevels = extractHeadingLevels(readText(enPath))
    if (zhLevels.length !== enLevels.length) {
      gaps.push({
        file: base,
        kind: 'section-mismatch',
        section: '标题数不等：中文 ' + zhLevels.length + ' 个 / 英文 ' + enLevels.length + ' 个',
      })
      continue
    }
    const diffAt = zhLevels.findIndex((lv, i) => lv !== enLevels[i])
    if (diffAt !== -1) {
      gaps.push({
        file: base,
        kind: 'section-mismatch',
        section:
          '层级序列第 ' + (diffAt + 1) + ' 个标题不一致：中文 h' + zhLevels[diffAt] + ' / 英文 h' + enLevels[diffAt],
      })
    }
  }

  for (const [base] of [...enFiles].sort()) {
    if (!zhFiles.has(base)) {
      gaps.push({ file: base + '.en.ts', kind: 'missing-zh', section: '缺少对应中文版 ' + base + '.ts' })
    }
  }

  return gaps
}

/**
 * 汇总报告。
 * @returns {{ text: string, undocumented: {type:string,label:string}[], gaps: {file:string,kind:string,section:string}[], failed: boolean }}
 */
export function buildReport() {
  const out = []
  const log = (s) => out.push(s)

  const all = parseModuleTypeLabels()
  const modules = realModules()
  const { zhFiles, enFiles } = enumerateDocFiles()
  const undocumented = findUndocumentedModules()
  const gaps = findDocSectionGaps()
  const pseudoGaps = undocumentedPseudoTypes(buildZhCorpus(zhFiles))

  log('========================================')
  log('  WebRPA 教学文档覆盖与中英同步审计')
  log('========================================')
  log('')
  log('[概览]')
  log('  moduleTypeLabels 条目数: ' + all.length)
  log('  排除伪类型后的真实模块数: ' + modules.length + '  (排除 ' + [...PSEUDO_TYPES].join('、') + ')')
  log('  中文教学文档: ' + zhFiles.size + ' 篇')
  log('  英文教学文档: ' + enFiles.size + ' 篇')
  log('  启用的别名条目: ' + Object.keys(MODULE_NAME_ALIASES).length + ' 条')

  log('')
  log('[Property 9] 每个真实模块的中文名在中文教学文档中至少被提及一次')
  if (undocumented.length === 0) {
    log('  PASS: 全部 ' + modules.length + ' 个模块均被提及')
  } else {
    const rate = ((undocumented.length / modules.length) * 100).toFixed(1)
    log('  FAIL: 未提及模块 ' + undocumented.length + ' / ' + modules.length + ' 个 (' + rate + '%)')
    for (const g of undocumented) log('    - ' + g.type + '  ' + g.label)
  }

  // 与 design.md 实测值对账：design.md 记的 213 条是按 571 全键口径统计的（未排除伪类型）。
  // 本审计按 569 口径判失败，两者相差的就是下列伪类型条目。
  log('')
  log('[口径对账] design.md 实测 213 条 vs 本审计 ' + undocumented.length + ' 条')
  log('  差异来源：design.md 按 moduleTypeLabels 全部 ' + all.length + ' 键统计，未排除伪类型；')
  log('  本审计按对外披露口径 ' + modules.length + ' 统计（排除 ' + [...PSEUDO_TYPES].join('、') + '）。')
  if (pseudoGaps.length === 0) {
    log('  伪类型中未被提及的条目: 0 条')
  } else {
    log('  伪类型中未被提及的条目 ' + pseudoGaps.length + ' 条（不计入失败数）:')
    for (const g of pseudoGaps) log('    - ' + g.type + '  ' + g.label)
  }
  log('  全键口径合计: ' + (undocumented.length + pseudoGaps.length) + ' 条，与 design.md 的 213 一致性可据此核对。')

  const oneSided = gaps.filter((g) => g.kind !== 'section-mismatch')
  const mismatched = gaps.filter((g) => g.kind === 'section-mismatch')

  log('')
  log('[Property 10-a] 中英教学文档一一成对')
  if (oneSided.length === 0) {
    log('  PASS: ' + zhFiles.size + ' 篇中文文档均有对应英文版，无单边文件')
  } else {
    log('  FAIL: 单边文件 ' + oneSided.length + ' 个')
    for (const g of oneSided) log('    - ' + g.file + '  ' + g.section)
  }

  log('')
  log('[Property 10-b] 中英文档章节数量与层级序列一致')
  if (mismatched.length === 0) {
    log('  PASS: 全部成对文档的标题骨架一致')
  } else {
    log('  FAIL: 章节序列不一致 ' + mismatched.length + ' 个文件')
    for (const g of mismatched) log('    - ' + g.file + '  ' + g.section)
  }
  log('  已知局限: 标题数与层级一致但正文未同步的情况本审计无法发现，需人工评审。')

  const failed = undocumented.length > 0 || gaps.length > 0
  log('')
  log('[结论]')
  log('  未提及模块数: ' + undocumented.length)
  log('  单边文档数: ' + oneSided.length)
  log('  章节序列不一致文件数: ' + mismatched.length)
  log('  总判定: ' + (failed ? 'RED' : 'GREEN'))
  log('========================================')

  return { text: out.join('\n'), undocumented, gaps, failed }
}

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(__filename)
if (isMain) {
  const report = buildReport()
  process.stdout.write(report.text + '\n')
  process.exitCode = report.failed ? 1 : 0
}
