// Source: WebRPA@5ccb900e, lib/__tests__/moduleSearchEntries.audit.test.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 三处模块搜索入口复用同一匹配函数的守护（需求 1.5）
 *
 * 背景：模块搜索有三个入口——模块列表侧边栏（ModuleSidebar）、快速选择模块弹窗
 * （QuickModulePicker）、模块条视图内的模块选择弹层（BlockFlowView）。三者必须复用
 * `lib/pinyin.ts` 的 `moduleMatchesQuery`，否则任一入口自己写一段 `label.includes(query)`
 * 就会退化成「只能搜中文原文、搜不了拼音」，而这种退化不会让任何现有测试变红。
 *
 * 实现方式（参考 backend/tests/contract/test_type_utils_signature.py 的静态扫描思路）：
 * 读三个组件的源码做词法级扫描并断言调用点，**不渲染组件**——这三个组件依赖 zustand
 * store、ReactFlow、portal，渲染成本高且与「是否复用同一函数」无关。
 *
 * 判定标准刻意写得具体、可解释，避免误报：
 *   1) 必须从 '../lib/pinyin' 导入 `moduleMatchesQuery`，且不得在本文件内另行定义同名函数；
 *   2) 至少有一处 `moduleMatchesQuery(...)` 调用，且实参里同时出现 `label:` 与 `type:` 字段
 *      （防止写成 `moduleMatchesQuery(q, {})` 这种形同虚设的调用）；
 *   3) 不得直接导入 `pinyinMatch` / `getPinyin` / `getPinyinInitials` 自行拼字段
 *      （逐字段自拼等于把统一函数的逻辑复制一份，日后必然漂移）；
 *   4) 不得存在「绕过统一函数的裸 includes / indexOf 模块名过滤」。
 *
 * 第 4 条的判定规则（同时满足才算违规，单条不算）：
 *   - 出现 `.includes(` 或 `.indexOf(` 调用；
 *   - 调用一侧（接收者或实参）的标识符按驼峰拆词后含**模块元信息词**（label / type /
 *     keywords / category / name）；
 *   - 另一侧含**搜索查询词**（query / q / term / search）。
 * 这样 `dataTransfer.types.includes('application/reactflow')`（实参是字面量）、
 * `favoriteModules.includes(type)`（两侧都不含查询词）、`ids.indexOf(nodeId)` 都不会被误报，
 * 而 `moduleTypeLabels[m].toLowerCase().includes(query)` 会被准确抓出。
 *
 * 扫描前会先把注释与字符串字面量内容置空（逐字符替换、保持长度与行号不变），
 * 避免注释里提到的示例代码或字符串里的 `.includes(` 干扰判定。
 *
 * 确有合法例外时走 `BYPASS_EXEMPTIONS` 显式豁免（必须写明理由），禁止放宽上述判定。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { moduleMatchesQuery } from '../pinyin'

/** 三处模块搜索入口（相对 frontend/src 的路径 + 入口说明，失败信息里直接给人看） */
const SEARCH_ENTRIES: readonly { file: string; entry: string }[] = [
  { file: 'components/ModuleSidebar.tsx', entry: '模块列表侧边栏主搜索' },
  { file: 'components/QuickModulePicker.tsx', entry: '快速选择模块弹窗（画布双击）' },
  { file: 'components/BlockFlowView.tsx', entry: '模块条视图内的模块选择弹层' },
]

/** 统一匹配函数的唯一定义位置 */
const MATCHER_SOURCE_FILE = 'lib/pinyin.ts'
const MATCHER_NAME = 'moduleMatchesQuery'

/** 不允许搜索入口直接导入的底层拼音函数（自行逐字段拼装＝复制一份匹配逻辑） */
const LOW_LEVEL_PINYIN_HELPERS = ['pinyinMatch', 'getPinyin', 'getPinyinInitials'] as const

/** 模块元信息词（驼峰拆词后的小写词） */
const MODULE_METADATA_WORDS: ReadonlySet<string> = new Set([
  'label',
  'labels',
  'keywords',
  'type',
  'category',
  'categories',
  'name',
])

/** 搜索查询词（驼峰拆词后的小写词） */
const QUERY_WORDS: ReadonlySet<string> = new Set(['query', 'q', 'term', 'search'])

/** 被扫描的子串匹配 API */
const SUBSTRING_APIS = ['.includes(', '.indexOf('] as const

/**
 * 绕过式子串过滤的显式豁免。
 * 每条必须写明理由；理由为空或豁免已失效（对应行不再被判违规）都会让测试失败，
 * 避免豁免表变成放宽断言的后门。
 */
interface BypassExemption {
  /** 相对 frontend/src 的文件路径 */
  file: string
  /** 行号（1 起） */
  line: number
  /** 豁免理由，必须具体 */
  reason: string
}
const BYPASS_EXEMPTIONS: readonly BypassExemption[] = []

/** 读取前端源码文件（静态扫描，不依赖组件渲染） */
function readFrontendSource(relativeFromSrc: string): string {
  const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  return readFileSync(path.join(srcDir, relativeFromSrc), 'utf-8')
}

/**
 * 把注释置为空格（可选：同时把字符串 / 模板字面量的**内容**也置为空格），
 * 保留引号、反引号与所有换行。
 *
 * 逐字符 1:1 替换，因此输出长度与行号与原文完全一致，报错行号可直接定位源码。
 * 模板字面量里的 `${ ... }` 会回到代码态继续扫描（插值里也可能写过滤逻辑）。
 *
 * `blankStrings` 的取舍：
 *   - 扫描「绕过式子串过滤」时必须置空字符串内容，否则字符串里的示例代码会误报；
 *   - 扫描 import 语句时必须保留字符串内容，因为模块路径本身就写在字符串里。
 */
function blankSource(source: string, blankStrings: boolean): string {
  const out: string[] = []
  const stack: { kind: 'code' | 'template'; braceDepth: number }[] = [{ kind: 'code', braceDepth: 0 }]
  const keep = (ch: string) => out.push(ch)
  const blank = (ch: string) => out.push(ch === '\n' ? '\n' : ' ')
  /** 字符串 / 模板字面量内部的字符 */
  const body = (ch: string) => (blankStrings ? blank(ch) : keep(ch))
  let i = 0

  while (i < source.length) {
    const ch = source[i]
    const next = source[i + 1]
    const top = stack[stack.length - 1]

    if (top.kind === 'template') {
      if (ch === '\\') {
        body(ch)
        i += 1
        if (i < source.length) {
          body(source[i])
          i += 1
        }
        continue
      }
      if (ch === '$' && next === '{') {
        keep('$')
        keep('{')
        i += 2
        stack.push({ kind: 'code', braceDepth: 0 })
        continue
      }
      if (ch === '`') {
        keep(ch)
        i += 1
        stack.pop()
        continue
      }
      body(ch)
      i += 1
      continue
    }

    // 行注释
    if (ch === '/' && next === '/') {
      while (i < source.length && source[i] !== '\n') {
        blank(source[i])
        i += 1
      }
      continue
    }
    // 块注释
    if (ch === '/' && next === '*') {
      blank(' ')
      blank(' ')
      i += 2
      while (i < source.length && !(source[i] === '*' && source[i + 1] === '/')) {
        blank(source[i])
        i += 1
      }
      if (i < source.length) {
        blank(' ')
        blank(' ')
        i += 2
      }
      continue
    }
    // 普通字符串
    if (ch === '"' || ch === "'") {
      keep(ch)
      i += 1
      while (i < source.length && source[i] !== ch && source[i] !== '\n') {
        if (source[i] === '\\') {
          body(source[i])
          i += 1
          if (i < source.length) {
            body(source[i])
            i += 1
          }
          continue
        }
        body(source[i])
        i += 1
      }
      if (i < source.length && source[i] === ch) {
        keep(source[i])
        i += 1
      }
      continue
    }
    if (ch === '`') {
      keep(ch)
      i += 1
      stack.push({ kind: 'template', braceDepth: 0 })
      continue
    }
    if (ch === '{') {
      top.braceDepth += 1
      keep(ch)
      i += 1
      continue
    }
    if (ch === '}') {
      if (top.braceDepth === 0 && stack.length > 1) {
        stack.pop()
        keep(ch)
        i += 1
        continue
      }
      top.braceDepth = Math.max(0, top.braceDepth - 1)
      keep(ch)
      i += 1
      continue
    }
    keep(ch)
    i += 1
  }

  return out.join('')
}

/** 仅保留代码：注释与字符串内容都置空（用于扫描调用点） */
function codeOnly(source: string): string {
  return blankSource(source, true)
}

/** 保留字符串内容、仅置空注释（用于扫描 import 路径） */
function codeWithStringLiterals(source: string): string {
  return blankSource(source, false)
}

/** 标识符按驼峰 / 下划线 / 非字母数字拆成小写词，用于精确词级判定 */
function splitIdentifierWords(text: string): Set<string> {
  const words = new Set<string>()
  for (const raw of text.split(/[^A-Za-z0-9]+/)) {
    if (!raw) continue
    for (const piece of raw.replace(/([a-z0-9])([A-Z])/g, '$1 $2').split(/\s+/)) {
      if (piece) words.add(piece.toLowerCase())
    }
  }
  return words
}

function hasAnyWord(text: string, dictionary: ReadonlySet<string>): boolean {
  for (const word of splitIdentifierWords(text)) {
    if (dictionary.has(word)) return true
  }
  return false
}

/** 取 `open` 位置（指向左括号）对应的括号内文本；括号不配对时返回剩余全文 */
function readBalancedArgs(source: string, openParenIndex: number): string {
  let depth = 0
  for (let i = openParenIndex; i < source.length; i += 1) {
    const ch = source[i]
    if (ch === '(') depth += 1
    else if (ch === ')') {
      depth -= 1
      if (depth === 0) return source.slice(openParenIndex + 1, i)
    }
  }
  return source.slice(openParenIndex + 1)
}

/** 违规记录 */
interface BypassOffender {
  file: string
  line: number
  api: string
  snippet: string
}

/**
 * 检出「绕过统一匹配函数的裸子串过滤」。
 *
 * 接收者一侧取**同一行左侧的全部文本**（宁可保守多看一点，也不漏掉链式调用），
 * 实参一侧取括号配对后的完整文本（可跨行）。两侧一个含模块元信息词、另一个含查询词
 * 才判违规——单侧命中不算，这是控制误报的关键。
 */
function findSubstringFilterBypasses(file: string, rawSource: string): BypassOffender[] {
  const code = codeOnly(rawSource)
  const rawLines = rawSource.split('\n')
  const offenders: BypassOffender[] = []

  for (const api of SUBSTRING_APIS) {
    let from = 0
    for (;;) {
      const at = code.indexOf(api, from)
      if (at === -1) break
      from = at + api.length

      const lineStart = code.lastIndexOf('\n', at) + 1
      const receiverText = code.slice(lineStart, at)
      const argsText = readBalancedArgs(code, at + api.length - 1)

      const receiverHasMeta = hasAnyWord(receiverText, MODULE_METADATA_WORDS)
      const receiverHasQuery = hasAnyWord(receiverText, QUERY_WORDS)
      const argsHasMeta = hasAnyWord(argsText, MODULE_METADATA_WORDS)
      const argsHasQuery = hasAnyWord(argsText, QUERY_WORDS)

      const isBypass = (receiverHasMeta && argsHasQuery) || (receiverHasQuery && argsHasMeta)
      if (!isBypass) continue

      const line = code.slice(0, at).split('\n').length
      offenders.push({
        file,
        line,
        api: api.replace(/[.(]/g, ''),
        snippet: (rawLines[line - 1] ?? '').trim().slice(0, 160),
      })
    }
  }

  return offenders
}

/** 源码缓存（三个组件文件都不小，避免每条断言重复读盘） */
const SOURCES: Map<string, string> = new Map(
  SEARCH_ENTRIES.map((e) => [e.file, readFrontendSource(e.file)] as const),
)

function sourceOf(file: string): string {
  const source = SOURCES.get(file)
  if (!source) throw new Error(`未读取到源码：${file}`)
  return source
}

/** 取某个标识符的调用点（返回每个调用的实参文本与行号） */
function findCalls(code: string, callee: string): { line: number; args: string }[] {
  const calls: { line: number; args: string }[] = []
  const pattern = new RegExp(`\\b${callee}\\s*\\(`, 'g')
  for (;;) {
    const matched = pattern.exec(code)
    if (!matched) break
    const openParen = code.indexOf('(', matched.index)
    calls.push({
      line: code.slice(0, matched.index).split('\n').length,
      args: readBalancedArgs(code, openParen),
    })
  }
  return calls
}

describe('三处模块搜索入口复用同一匹配函数 - module-integrity-audit 需求 1.5', () => {
  // 扫描器自身的健壮性：置空注释与字符串后长度、行数不变，且真实调用点仍可见。
  // 若扫描器把源码破坏掉（例如误把整段代码当成字符串吞掉），后面所有断言都会退化成
  // 「什么都没测」的假绿，因此这条是前置守卫。
  it('扫描器置空注释与字符串后不改变长度与行号，且保留真实调用点', () => {
    for (const { file } of SEARCH_ENTRIES) {
      const raw = sourceOf(file)

      for (const [label, code] of [
        ['注释+字符串置空', codeOnly(raw)],
        ['仅注释置空', codeWithStringLiterals(raw)],
      ] as const) {
        expect(code.length, `${file}(${label}): 置空后长度变化，行号将不可信`).toBe(raw.length)
        expect(code.split('\n').length, `${file}(${label}): 置空后行数变化`).toBe(raw.split('\n').length)
        expect(
          code.includes(`${MATCHER_NAME}(`),
          `${file}(${label}): 置空后 ${MATCHER_NAME} 调用点消失，说明扫描器把代码误判为字符串或注释`,
        ).toBe(true)
      }

      expect(
        codeWithStringLiterals(raw).includes("'../lib/pinyin'"),
        `${file}: 仅置空注释时应保留 import 路径字符串`,
      ).toBe(true)
    }
  })

  // Validates: Requirements 1.5
  it('三处入口都从 ../lib/pinyin 导入 moduleMatchesQuery，且不在本地另行定义同名函数', () => {
    const problems: string[] = []

    for (const { file, entry } of SEARCH_ENTRIES) {
      const raw = sourceOf(file)
      const importScannable = codeWithStringLiterals(raw)

      const importsMatcher = new RegExp(
        `import\\s*\\{[^}]*\\b${MATCHER_NAME}\\b[^}]*\\}\\s*from\\s*['"]../lib/pinyin['"]`,
      ).test(importScannable)
      if (!importsMatcher) {
        problems.push(`${file}（${entry}）未从 '../lib/pinyin' 导入 ${MATCHER_NAME}`)
      }

      const definesLocally = new RegExp(
        `(function\\s+${MATCHER_NAME}\\b|(?:const|let|var)\\s+${MATCHER_NAME}\\s*=)`,
      ).test(codeOnly(raw))
      if (definesLocally) {
        problems.push(`${file}（${entry}）在本地定义了 ${MATCHER_NAME}，必须复用 lib/pinyin.ts 的唯一实现`)
      }
    }

    expect(problems, `模块搜索入口未复用统一匹配函数：\n  ${problems.join('\n  ')}`).toEqual([])
  })

  // Validates: Requirements 1.5
  it('三处入口的模块过滤都实际调用 moduleMatchesQuery，且传入 label 与 type 字段', () => {
    const problems: string[] = []

    for (const { file, entry } of SEARCH_ENTRIES) {
      const code = codeOnly(sourceOf(file))
      const calls = findCalls(code, MATCHER_NAME).filter((c) => !/^\s*$/.test(c.args))

      if (calls.length === 0) {
        problems.push(`${file}（${entry}）没有任何 ${MATCHER_NAME} 调用`)
        continue
      }

      // 至少一处调用同时给了 label 与 type，否则匹配面不完整（例如只传 type
      // 就搜不到中文名拼音，只传 label 就搜不到英文 module_type）。
      // 两种写法都算：`type: m.type`（显式）与 `type,`（对象简写）。
      const hasField = (args: string, field: string) =>
        new RegExp(`\\b${field}\\s*(?::|,|\\}|$)`).test(args)
      const wellFormed = calls.filter((c) => hasField(c.args, 'label') && hasField(c.args, 'type'))
      if (wellFormed.length === 0) {
        const detail = calls.map((c) => `第 ${c.line} 行: ${c.args.replace(/\s+/g, ' ').slice(0, 120)}`)
        problems.push(
          `${file}（${entry}）的 ${MATCHER_NAME} 调用未同时传入 label 与 type：\n    ${detail.join('\n    ')}`,
        )
      }
    }

    expect(problems, `模块搜索入口的匹配调用不完整：\n  ${problems.join('\n  ')}`).toEqual([])
  })

  // Validates: Requirements 1.5
  it('三处入口不得直接导入底层拼音函数自行逐字段拼装匹配逻辑', () => {
    const problems: string[] = []

    for (const { file, entry } of SEARCH_ENTRIES) {
      const code = codeWithStringLiterals(sourceOf(file))
      const importBlocks = code.match(/import\s*\{[^}]*\}\s*from\s*['"]@\/lib\/pinyin['"]/g) ?? []
      const imported = importBlocks.join(' ')

      for (const helper of LOW_LEVEL_PINYIN_HELPERS) {
        if (new RegExp(`\\b${helper}\\b`).test(imported)) {
          problems.push(
            `${file}（${entry}）直接导入了 ${helper}：逐字段自拼等于复制一份匹配逻辑，必须只用 ${MATCHER_NAME}`,
          )
        }
      }
    }

    expect(problems, `模块搜索入口绕过统一匹配函数：\n  ${problems.join('\n  ')}`).toEqual([])
  })
})

describe('模块搜索入口不得存在绕过式裸子串过滤 - module-integrity-audit 需求 1.5', () => {
  /** 三处入口实际检出的违规（供豁免表校验复用） */
  const detected: BypassOffender[] = SEARCH_ENTRIES.flatMap(({ file }) =>
    findSubstringFilterBypasses(file, sourceOf(file)),
  )

  const isExempt = (o: BypassOffender) =>
    BYPASS_EXEMPTIONS.some((e) => e.file === o.file && e.line === o.line)

  // Validates: Requirements 1.5
  it('三处入口不存在用 includes / indexOf 直接过滤模块名的实现', () => {
    const offenders = detected.filter((o) => !isExempt(o))
    const detail = offenders.map((o) => `${o.file}:${o.line}  [${o.api}]  ${o.snippet}`)

    expect(
      offenders,
      `发现绕过 ${MATCHER_NAME} 的裸子串模块过滤（会导致该入口只能搜中文原文、搜不了拼音）：\n  ${detail.join('\n  ')}`,
    ).toEqual([])
  })

  it('豁免表每条都写明理由且仍然有效（禁止用豁免表放宽断言）', () => {
    const problems: string[] = []

    for (const exemption of BYPASS_EXEMPTIONS) {
      if (exemption.reason.trim().length < 10) {
        problems.push(`${exemption.file}:${exemption.line} 的豁免理由过于简略：「${exemption.reason}」`)
      }
      const stillNeeded = detected.some((o) => o.file === exemption.file && o.line === exemption.line)
      if (!stillNeeded) {
        problems.push(
          `${exemption.file}:${exemption.line} 的豁免已失效（该行不再被判违规），请删除该条豁免`,
        )
      }
    }

    expect(problems, `豁免表存在问题：\n  ${problems.join('\n  ')}`).toEqual([])
  })
})

describe('绕过检测器自身的有效性验证 - module-integrity-audit', () => {
  // 这两条相当于设计文档要求的「注入坏数据确认审计会失败」，但用内联假源码完成，
  // 不需要改动真实源码再回滚：既证明检测器不会恒绿，也证明它不会误报常见写法。
  it('对绕过写法必须报出违规', () => {
    const bypassFixtures: { name: string; code: string }[] = [
      {
        name: 'label 直接 includes 查询词',
        code: 'const hit = cat.modules.filter((m) => moduleTypeLabels[m].includes(query))',
      },
      {
        name: 'label 转小写后 includes 查询词',
        code: 'const hit = mods.filter((m) => m.label.toLowerCase().includes(searchTerm.toLowerCase()))',
      },
      {
        name: 'module_type 用 indexOf 过滤',
        code: 'const hit = mods.filter((m) => m.type.indexOf(q) >= 0)',
      },
      {
        name: '关键词数组元素 includes 查询词',
        code: 'const hit = (moduleKeywords[type] || []).some((kw) => kw.includes(searchQuery))',
      },
      {
        name: '查询词反过来 includes 模块名',
        code: 'const hit = mods.filter((m) => query.includes(m.label))',
      },
    ]

    const missed = bypassFixtures
      .filter((f) => findSubstringFilterBypasses('fixture.tsx', f.code).length === 0)
      .map((f) => f.name)

    expect(missed, `检测器漏报了以下绕过写法（会让守护形同虚设）：\n  ${missed.join('\n  ')}`).toEqual([])
  })

  it('对三处入口现有的合法 includes 写法不得误报', () => {
    const legitimateFixtures: { name: string; code: string }[] = [
      {
        name: '拖拽数据类型判断',
        code: "if (e.dataTransfer.types.includes('application/reactflow')) return",
      },
      { name: '收藏列表成员判断', code: 'const fav = favoriteModules.includes(type)' },
      { name: '节点 id 列表定位', code: 'const idx = ids.indexOf(nodeId)' },
      { name: '高亮片段定位（非过滤）', code: 'const index = lowerText.indexOf(lowerQuery)' },
      {
        name: '统一匹配函数的正常调用',
        code: 'const hit = moduleMatchesQuery(q, { label: moduleTypeLabels[m], type: m, keywords: moduleKeywords[m] })',
      },
      {
        name: '注释里提到的绕过示例不算违规',
        code: '// 不要写成 m.label.includes(query)\nconst hit = moduleMatchesQuery(q, { label: l, type: t })',
      },
      {
        name: '字符串字面量里的写法不算违规',
        code: "const tip = 'm.label.includes(query)'",
      },
    ]

    const falsePositives = legitimateFixtures
      .filter((f) => findSubstringFilterBypasses('fixture.tsx', f.code).length > 0)
      .map((f) => f.name)

    expect(
      falsePositives,
      `检测器对合法写法误报（会逼着后来人放宽断言）：\n  ${falsePositives.join('\n  ')}`,
    ).toEqual([])
  })

  // 在真实（且很大）的组件源码上下文里注入一行绕过写法，确认检测器仍能抓到。
  // 只在内存里改字符串，不动磁盘文件，因此不存在「忘记回滚注入」的风险。
  it('把绕过写法注入真实源码副本后必须报出', () => {
    const undetected: string[] = []

    for (const { file } of SEARCH_ENTRIES) {
      const injected = sourceOf(file).replace(
        /\bmoduleMatchesQuery\s*\(/,
        'moduleTypeLabels[type].includes(searchQuery) || moduleMatchesQuery(',
      )
      expect(injected, `${file}: 注入失败，未找到 ${MATCHER_NAME} 调用点`).not.toBe(sourceOf(file))

      if (findSubstringFilterBypasses(file, injected).length === 0) {
        undetected.push(file)
      }
    }

    expect(
      undetected,
      `检测器在真实源码上下文中漏报注入的绕过写法：\n  ${undetected.join('\n  ')}`,
    ).toEqual([])
  })

  it('统一匹配函数只在 lib/pinyin.ts 中定义一处', () => {
    const matcherSource = readFrontendSource(MATCHER_SOURCE_FILE)
    const definitions = matcherSource.match(new RegExp(`export function ${MATCHER_NAME}\\b`, 'g')) ?? []

    expect(typeof moduleMatchesQuery, `${MATCHER_NAME} 必须是可调用的导出`).toBe('function')
    expect(definitions.length, `${MATCHER_SOURCE_FILE} 中 ${MATCHER_NAME} 的定义数量异常`).toBe(1)
  })
})
