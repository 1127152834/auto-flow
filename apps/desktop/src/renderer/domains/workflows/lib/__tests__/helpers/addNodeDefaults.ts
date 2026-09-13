// Source: WebRPA@5ccb900e, lib/__tests__/helpers/addNodeDefaults.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * addNode 默认变量字段提取器（module-integrity-audit 任务 1）
 *
 * 打破自证闭环的关键组件。现有 moduleDefaultVars.audit.test.ts 恒绿的根因是「用
 * MODULE_DEFAULT_VARS 造输入，再断言读同一张表的函数能拿到它」；本模块改从
 * workflowStore.ts 的 addNode 源码里解析真实默认值，作为审计的事实源（设计决策 2）。
 *
 * 为什么不用 AST：前端 devDependencies 里没有独立的 TS parser，为一个审计引入
 * typescript 编译 API 会显著拖慢 vitest 启动。addNode 的分支结构规整（全是
 * `type === '字面量'` 形式），括号配对 + 正则的词法扫描足够可靠，且解析失败会硬失败。
 *
 * 防假绿：找不到 addNode、分支数为 0、字段数为 0 一律抛异常，绝不返回空数组——
 * 静默返回空会让所有依赖它的审计退化成「什么都没测」。
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { VARIABLE_NAME_FIELDS } from '../../moduleDefaultVars'

/** addNode 里一处「模块 + 变量名字段 + 默认值」的赋值 */
export interface AddNodeVarField {
  /** module_type，如 click_element */
  moduleType: string
  /** 变量名类字段，如 resultVariable */
  field: string
  /** addNode 里写死的默认变量名 */
  defaultValue: string
  /** 源码行号（1 起），便于审计失败时定位 */
  line: number
}

/** 变量名字段白名单（唯一数据源，与 collectNodeVarNames 认的字段完全一致） */
const VAR_FIELD_SET: ReadonlySet<string> = new Set(VARIABLE_NAME_FIELDS)

/** workflowStore.ts 的绝对路径 */
function storeFilePath(): string {
  const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
  return path.join(srcDir, 'editor-store.ts')
}

/**
 * 把行注释与块注释（可选：字符串字面量内容）逐字符置为空格，保留换行，
 * 使输出长度与行号与原文完全一致。
 *
 * 必须置空注释：addNode 的分支里有大量形如 `// 默认60秒` 的说明，若不剥离，
 * 注释中偶然出现的 `xxxVariable: 'yyy'` 写法会被当成真实赋值。
 *
 * blankStrings 的取舍（与后端 addnode_parser.py 的 _blank 完全一致）：
 *   · 结构扫描（括号配对、分支切分）必须置空字符串内容，否则字符串里的花括号会破坏
 *     配对，导致函数体边界判错、分支数量失真；
 *   · 条件里的 type 字面量与字段默认值提取必须保留字符串内容。
 * 两个版本长度一致，偏移可互换。
 */
function blankSource(source: string, blankStrings: boolean): string {
  const out: string[] = []
  let i = 0
  while (i < source.length) {
    const ch = source[i]
    const next = source[i + 1]
    if (ch === '/' && next === '/') {
      while (i < source.length && source[i] !== '\n') {
        out.push(' ')
        i += 1
      }
      continue
    }
    if (ch === '/' && next === '*') {
      out.push(' ', ' ')
      i += 2
      while (i < source.length && !(source[i] === '*' && source[i + 1] === '/')) {
        out.push(source[i] === '\n' ? '\n' : ' ')
        i += 1
      }
      if (i < source.length) {
        out.push(' ', ' ')
        i += 2
      }
      continue
    }
    // 字符串字面量：引号保留，内容按 blankStrings 决定是否置空
    if (ch === '"' || ch === "'" || ch === '`') {
      out.push(ch)
      i += 1
      while (i < source.length && source[i] !== ch) {
        if (source[i] === '\\') {
          out.push(blankStrings ? ' ' : source[i])
          i += 1
          if (i < source.length) {
            out.push(blankStrings ? ' ' : source[i])
            i += 1
          }
          continue
        }
        if (blankStrings) out.push(source[i] === '\n' ? '\n' : ' ')
        else out.push(source[i])
        i += 1
      }
      if (i < source.length) {
        out.push(source[i])
        i += 1
      }
      continue
    }
    out.push(ch)
    i += 1
  }
  return out.join('')
}

/** addNode 函数体在源码中的区间（左花括号之后到配对的右花括号之前，绝对偏移） */
interface FunctionBody {
  /** 函数体起点偏移 */
  offset: number
  /** 函数体终点偏移（不含） */
  end: number
}

/** addNode 的函数签名锚点（zustand store 的动作定义写法） */
const ADD_NODE_ANCHOR = 'addNode: (type, position, extraConfig) => {'

/**
 * 定位 addNode 函数体。找不到锚点或括号不配对时抛异常（防假绿）。
 */
function findAddNodeBody(code: string): FunctionBody {
  const anchorAt = code.indexOf(ADD_NODE_ANCHOR)
  if (anchorAt < 0) {
    throw new Error(
      `在 workflowStore.ts 中找不到 addNode 函数签名锚点「${ADD_NODE_ANCHOR}」，` +
        '解析规则需随源码同步更新（不要让审计静默通过）',
    )
  }
  const braceAt = anchorAt + ADD_NODE_ANCHOR.length - 1
  let depth = 0
  for (let i = braceAt; i < code.length; i += 1) {
    const ch = code[i]
    if (ch === '{') depth += 1
    else if (ch === '}') {
      depth -= 1
      if (depth === 0) {
        return { offset: braceAt + 1, end: i }
      }
    }
  }
  throw new Error('addNode 函数体的花括号未配对，解析规则需更新')
}

/**
 * 取 `open` 位置（指向左花括号）配对的块区间 [内容起点, 内容终点)。
 * 括号不配对时返回 null，由调用方判定为解析失败。
 */
function matchBlock(text: string, open: number): { start: number; end: number } | null {
  let depth = 0
  for (let i = open; i < text.length; i += 1) {
    const ch = text[i]
    if (ch === '{') depth += 1
    else if (ch === '}') {
      depth -= 1
      if (depth === 0) return { start: open + 1, end: i }
    }
  }
  return null
}

/** addNode 里的一个条件分支 */
interface AddNodeBranch {
  /** 该分支条件里 `type === '字面量'` 提取到的全部 module_type（支持 || 连接的多类型分支） */
  moduleTypes: string[]
  /** 分支体文本（保留字符串内容的版本） */
  body: string
  /** 分支体在整份源码中的绝对起点偏移 */
  bodyOffset: number
}

/** 匹配 `if (...) {`，条件里不含嵌套括号（addNode 的分支条件全是简单比较） */
const IF_BRANCH_RE = /\bif\s*\(([^()]*)\)\s*\{/g

/** 从分支条件里提取 `type === '字面量'` 的全部字面量 */
function extractBranchTypes(condition: string): string[] {
  const types: string[] = []
  const re = /\btype\s*===\s*['"]([A-Za-z0-9_]+)['"]/g
  let matched: RegExpExecArray | null
  while ((matched = re.exec(condition)) !== null) types.push(matched[1])
  return types
}

/**
 * 切分 addNode 的全部 `if / else if` 分支。
 *
 * 只收条件里含 `type === '字面量'` 的分支：分支体内层还会有 `if (globalConfig.x)`
 * 这类与 module_type 无关的判断，它们提取不到 type，自然被跳过，不会产生重复条目。
 */
function collectBranches(structural: string, literal: string, body: FunctionBody): AddNodeBranch[] {
  const branches: AddNodeBranch[] = []
  const scope = structural.slice(body.offset, body.end)
  IF_BRANCH_RE.lastIndex = 0
  let matched: RegExpExecArray | null
  while ((matched = IF_BRANCH_RE.exec(scope)) !== null) {
    // 条件里的 type 字面量必须从保留字符串内容的版本取（structural 里已被置空）
    const condStart = body.offset + matched.index + matched[0].indexOf('(') + 1
    const moduleTypes = extractBranchTypes(literal.slice(condStart, condStart + matched[1].length))
    if (moduleTypes.length === 0) continue
    const braceAt = body.offset + matched.index + matched[0].length - 1
    const block = matchBlock(structural, braceAt)
    if (!block) {
      throw new Error(
        `addNode 分支「${moduleTypes.join(' | ')}」的花括号未配对，解析规则需更新`,
      )
    }
    branches.push({
      moduleTypes,
      body: literal.slice(block.start, block.end),
      bodyOffset: block.start,
    })
  }
  return branches
}

/** 分支体内提取到的一处白名单字段赋值 */
interface FieldAssignment {
  field: string
  defaultValue: string
  /** 在分支体文本中的偏移 */
  at: number
}

/**
 * 在分支体内提取白名单字段的**字符串字面量**赋值。
 *
 * 只认字面量：`variableName: varName` 这类运行时计算出来的变量名（8 个 ai_* 分支）
 * 无法静态确定取值，不在此处强行猜测——它们由 extractAddNodeComputedVarFields 单独报出，
 * 使「无法静态确定」的量可见，而不是静默漏掉。
 */
function extractFieldAssignments(body: string): FieldAssignment[] {
  const found: FieldAssignment[] = []
  const re = /(?:^|[\s{,(])([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(['"])((?:\\.|(?!\2)[^\\])*)\2/g
  let matched: RegExpExecArray | null
  while ((matched = re.exec(body)) !== null) {
    const field = matched[1]
    if (!VAR_FIELD_SET.has(field)) continue
    found.push({
      field,
      defaultValue: matched[3],
      at: matched.index + matched[0].indexOf(field),
    })
  }
  return found
}

/** 白名单字段被赋成非字面量（运行时计算）的记录 */
export interface AddNodeComputedVarField {
  moduleType: string
  field: string
  /** 源码里写的表达式，如 varName */
  expression: string
  line: number
}

/** 匹配白名单字段赋成标识符 / 三元 / 成员表达式等非字面量的写法 */
const COMPUTED_ASSIGN_RE = /(?:^|[\s{,(])([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_.[\]]*)\s*(?=[,\n}])/g

/** 预计算每行起点偏移，避免为每处赋值都切一遍大字符串 */
function buildLineStarts(code: string): number[] {
  const starts = [0]
  for (let i = 0; i < code.length; i += 1) {
    if (code[i] === '\n') starts.push(i + 1)
  }
  return starts
}

/** 二分查找偏移所在行号（1 起） */
function lineOf(lineStarts: number[], offset: number): number {
  let low = 0
  let high = lineStarts.length - 1
  while (low < high) {
    const mid = (low + high + 1) >> 1
    if (lineStarts[mid] <= offset) low = mid
    else high = mid - 1
  }
  return low + 1
}

/** 解析结果缓存：同一次 vitest 运行里多个审计都会用到，源码不会变 */
interface ParsedAddNode {
  lineStarts: number[]
  body: FunctionBody
  branches: AddNodeBranch[]
  /** 函数体文本（保留字符串内容的版本），用于结构性边界断言 */
  bodyText: string
}
let cached: ParsedAddNode | null = null

/**
 * 解析任意一段源码（导出以便自测注入假源码，验证「解析失败必须抛异常」的路径）。
 * 生产路径只会用 parseAddNode 读真实的 workflowStore.ts。
 */
export function parseAddNodeSource(source: string): ParsedAddNode {
  const structural = blankSource(source, true)
  const literal = blankSource(source, false)
  const body = findAddNodeBody(structural)
  const branches = collectBranches(structural, literal, body)
  if (branches.length === 0) {
    throw new Error(
      'addNode 中未解析出任何 `type === \'字面量\'` 分支，解析规则已失效——' +
        '禁止在此返回空结果，否则依赖本解析器的审计会退化成假绿',
    )
  }
  return {
    lineStarts: buildLineStarts(literal),
    body,
    branches,
    bodyText: literal.slice(body.offset, body.end),
  }
}

function parseAddNode(): ParsedAddNode {
  if (cached) return cached
  cached = parseAddNodeSource(readFileSync(storeFilePath(), 'utf-8'))
  return cached
}

/** addNode 函数体的起止行号（便于人工核对解析边界，与后端基线比对） */
export function getAddNodeBodyLines(): [number, number] {
  const { body, lineStarts } = parseAddNode()
  return [lineOf(lineStarts, body.offset), lineOf(lineStarts, body.end)]
}

/** addNode 函数体文本（已剥离注释），用于结构性边界断言 */
export function getAddNodeBodyText(): string {
  return parseAddNode().bodyText
}

/** 含 `type === '字面量'` 的分支统计（分支总数 / 其中多类型分支数） */
export function getAddNodeBranchStats(): { branchCount: number; multiTypeBranchCount: number } {
  const { branches } = parseAddNode()
  return {
    branchCount: branches.length,
    multiTypeBranchCount: branches.filter((b) => b.moduleTypes.length > 1).length,
  }
}

/** addNode 中被条件分支覆盖到的全部 module_type（去重，按出现顺序） */
export function extractAddNodeBranchTypes(): string[] {
  const { branches } = parseAddNode()
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const branch of branches) {
    for (const moduleType of branch.moduleTypes) {
      if (seen.has(moduleType)) continue
      seen.add(moduleType)
      ordered.push(moduleType)
    }
  }
  return ordered
}

/**
 * 解析 addNode，返回所有「模块 → 变量名字段 → 默认变量名」赋值（事实源）。
 *
 * 同一分支体内同一字段出现多次时以**最后一次**为准（对象字面量后写覆盖前写）。
 * 结果为空时抛异常，禁止返回空数组。
 */
export function extractAddNodeVarFields(): AddNodeVarField[] {
  const { branches, lineStarts } = parseAddNode()
  const merged = new Map<string, AddNodeVarField>()

  for (const branch of branches) {
    for (const assignment of extractFieldAssignments(branch.body)) {
      const line = lineOf(lineStarts, branch.bodyOffset + assignment.at)
      for (const moduleType of branch.moduleTypes) {
        merged.set(`${moduleType}\u0000${assignment.field}`, {
          moduleType,
          field: assignment.field,
          defaultValue: assignment.defaultValue,
          line,
        })
      }
    }
  }

  const result = Array.from(merged.values())
  if (result.length === 0) {
    throw new Error(
      `addNode 的 ${branches.length} 个分支里未解析出任何变量名字段赋值，` +
        '解析规则已失效（白名单字段名或赋值写法可能已变更）——禁止返回空数组',
    )
  }
  return result
}

/**
 * 白名单字段被赋成运行时表达式（非字符串字面量）的记录。
 *
 * 典型是 8 个 ai_* 分支的 `variableName: varName`：取值由分支内的查表决定，静态无法确定。
 * 单独导出使「无法静态确定」的量可见，供审计计入 skipped 计数而不是静默漏掉。
 */
export function extractAddNodeComputedVarFields(): AddNodeComputedVarField[] {
  const { branches, lineStarts } = parseAddNode()
  const result: AddNodeComputedVarField[] = []

  for (const branch of branches) {
    COMPUTED_ASSIGN_RE.lastIndex = 0
    let matched: RegExpExecArray | null
    while ((matched = COMPUTED_ASSIGN_RE.exec(branch.body)) !== null) {
      const field = matched[1]
      if (!VAR_FIELD_SET.has(field)) continue
      const at = matched.index + matched[0].indexOf(field)
      const line = lineOf(lineStarts, branch.bodyOffset + at)
      for (const moduleType of branch.moduleTypes) {
        result.push({ moduleType, field, expression: matched[2], line })
      }
    }
  }
  return result
}
