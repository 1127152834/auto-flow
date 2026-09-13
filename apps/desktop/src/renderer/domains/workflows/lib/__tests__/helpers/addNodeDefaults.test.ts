// Source: WebRPA@5ccb900e, lib/__tests__/helpers/addNodeDefaults.test.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * addNode 默认变量字段提取器自测（module-integrity-audit 任务 1）
 *
 * 这个解析器是后续变量一致性审计（P2 / P3 / P14）的事实源，它本身出错会让整条
 * 审计链变成假绿，所以必须先证明：解析结果规模符合实测值、多类型分支被正确展开、
 * 解析失败时确实抛异常。
 */
import { describe, it, expect } from 'vitest'
import {
  extractAddNodeVarFields,
  extractAddNodeBranchTypes,
  extractAddNodeComputedVarFields,
  parseAddNodeSource,
  getAddNodeBodyLines,
  getAddNodeBodyText,
  getAddNodeBranchStats,
} from './addNodeDefaults'
import { VARIABLE_NAME_FIELDS } from '../../moduleDefaultVars'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

/** 两侧解析器共用的口径基线（后端 pytest 侧断言同一份文件） */
interface ParserBaseline {
  forbiddenInBody: string[]
  branchCount: number
  multiTypeBranchCount: number
  moduleTypeCount: number
  varFieldCount: number
  modulesWithVarFieldsCount: number
  computedVarFieldCount: number
  fieldDistribution: Record<string, number>
}

const BASELINE: ParserBaseline = JSON.parse(
  readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), 'addNodeParserBaseline.json'),
    'utf-8',
  ),
)

const VAR_FIELDS = extractAddNodeVarFields()
const BRANCH_TYPES = extractAddNodeBranchTypes()

describe('addNode 默认变量字段提取器', () => {
  // 规模断言以两侧共用的基线文件为准（Property 13）。
  //
  // 后端 pytest 侧（backend/tests/contract/test_addnode_parser_parity.py）断言同一份基线，
  // 因此任一侧解析器逻辑漂移都会立刻失败；源码正常新增模块时两侧同时失败，只需更新基线一处。
  //
  // 关于与 design.md 实测值的差异：design.md 记的是立项时的值（167 处 / 171 个 type），
  // 当前实测 187 处 / 185 个 type。差异来源已核查，不是解析错误：函数体边界正确
  // （第 1467-2448 行，未吞入相邻动作）、多类型分支展开正确、抽样默认值逐字符核对一致、
  // dataSource / saveResult 这类易误报字段实际命中 0 条。增量来自立项后新增的 desktop_*
  // 控件操作整批模块（appVariable 15 + controlVariable 14 条）。
  it('分支覆盖的 module_type 数与共用基线一致', () => {
    expect(
      BRANCH_TYPES.length,
      `实际覆盖 ${BRANCH_TYPES.length} 个 module_type，基线 ${BASELINE.moduleTypeCount} 个`,
    ).toBe(BASELINE.moduleTypeCount)
    expect(new Set(BRANCH_TYPES).size, '分支 type 清单不应有重复').toBe(BRANCH_TYPES.length)
  })

  it('变量字段赋值数与共用基线一致', () => {
    expect(
      VAR_FIELDS.length,
      `实际解析出 ${VAR_FIELDS.length} 处变量字段赋值，基线 ${BASELINE.varFieldCount} 处`,
    ).toBe(BASELINE.varFieldCount)
  })

  it('函数体不吞入相邻 store 动作，分支统计与共用基线一致', () => {
    // 不用绝对行号断言（会随源码任何位置增删行漂移），改为结构性断言：括号配对一旦被
    // 字符串里的花括号带偏，函数体就会延伸到后面的 updateNodeData / blockInsertNode。
    const [startLine, endLine] = getAddNodeBodyLines()
    expect(endLine).toBeGreaterThan(startLine)
    const body = getAddNodeBodyText()
    for (const sig of BASELINE.forbiddenInBody) {
      expect(body, `addNode 函数体吞入了相邻 store 动作 ${sig}，说明括号配对被带偏`).not.toContain(sig)
    }
    const stats = getAddNodeBranchStats()
    expect(stats.branchCount).toBe(BASELINE.branchCount)
    expect(stats.multiTypeBranchCount).toBe(BASELINE.multiTypeBranchCount)
  })

  it('逐字段分布与共用基线一致（只比总数会漏掉互相抵消的偏差）', () => {
    const actual: Record<string, number> = {}
    for (const f of VAR_FIELDS) actual[f.field] = (actual[f.field] ?? 0) + 1
    expect(actual).toEqual(BASELINE.fieldDistribution)
  })

  it('有变量字段的 module_type 数与共用基线一致', () => {
    const modules = new Set(VAR_FIELDS.map((f) => f.moduleType))
    expect(modules.size).toBe(BASELINE.modulesWithVarFieldsCount)
  })

  it('每条记录的字段都在 VARIABLE_NAME_FIELDS 白名单内且取值非空', () => {
    const whitelist = new Set(VARIABLE_NAME_FIELDS)
    const bad = VAR_FIELDS.filter(
      (f) => !whitelist.has(f.field) || !f.defaultValue.trim() || !f.moduleType || f.line <= 0,
    )
    expect(bad, `存在非法记录：\n${JSON.stringify(bad, null, 2)}`).toEqual([])
  })

  it('同一「模块.字段」不重复出现（后写覆盖前写已在解析器内合并）', () => {
    const keys = VAR_FIELDS.map((f) => `${f.moduleType}.${f.field}`)
    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('多类型分支被正确展开', () => {
  // `type === 'a' || type === 'b'` 形式的分支必须展开成每个 module_type 各一条，
  // 否则 P2 审计会漏掉共用分支的模块（历史上 Word / SAP 整批漏登记就是这么来的）。
  it('|| 连接的多类型分支：8 个 ai_* 任务都被识别为独立 module_type', () => {
    const aiTasks = [
      'ai_extract',
      'ai_classify',
      'ai_summarize',
      'ai_translate',
      'ai_sentiment',
      'ai_normalize',
      'ai_dedup_semantic',
      'ai_route',
    ]
    const missing = aiTasks.filter((t) => !BRANCH_TYPES.includes(t))
    expect(missing, `多类型分支未展开，缺失：${missing.join('、')}`).toEqual([])
  })

  it('单类型分支的取值被准确读出（抽样核对源码字面量）', () => {
    const expected: { moduleType: string; field: string; defaultValue: string }[] = [
      { moduleType: 'gesture_trigger', field: 'saveToVariable', defaultValue: 'gesture_data' },
      { moduleType: 'ai_chat', field: 'resultVariable', defaultValue: 'ai_response' },
      { moduleType: 'loop', field: 'indexVariable', defaultValue: 'index' },
      { moduleType: 'foreach', field: 'itemVariable', defaultValue: 'item' },
      { moduleType: 'foreach', field: 'indexVariable', defaultValue: 'index' },
      { moduleType: 'set_variable', field: 'variableName', defaultValue: 'my_var' },
      { moduleType: 'js_script', field: 'resultVariable', defaultValue: 'js_result' },
      { moduleType: 'ai_smart_scraper', field: 'variableName', defaultValue: 'scraper_result' },
      { moduleType: 'universal_doc_convert', field: 'resultVariable', defaultValue: 'convert_output' },
    ]
    const actual = new Map(VAR_FIELDS.map((f) => [`${f.moduleType}.${f.field}`, f.defaultValue]))
    const wrong = expected.filter((e) => actual.get(`${e.moduleType}.${e.field}`) !== e.defaultValue)
    expect(
      wrong.map((e) => ({ ...e, actual: actual.get(`${e.moduleType}.${e.field}`) ?? '(未解析到)' })),
      '抽样核对失败，解析器读错了默认值',
    ).toEqual([])
  })

  it('运行时计算的变量名被单独报出而非静默漏掉（ai_* 的 variableName: varName）', () => {
    const computed = extractAddNodeComputedVarFields()
    const aiComputed = computed.filter((c) => c.moduleType.startsWith('ai_') && c.field === 'variableName')
    expect(aiComputed.length, '8 个 ai_* 任务的运行时变量名应被计入「无法静态确定」').toBeGreaterThanOrEqual(8)
    // 这些模块不应同时出现在字面量结果里，否则说明解析器把表达式当成了字面量
    const literalKeys = new Set(VAR_FIELDS.map((f) => `${f.moduleType}.${f.field}`))
    const leaked = aiComputed.filter((c) => literalKeys.has(`${c.moduleType}.${c.field}`))
    expect(leaked, '运行时表达式被误判为字符串字面量').toEqual([])
  })
})

describe('解析失败必须抛异常（禁止静默返回空结果）', () => {
  // 若解析器在源码结构变化后静默返回空数组，依赖它的 P2/P3/P14 审计会全部变成
  // 「什么都没测」的假绿。这三条锁死失败路径。
  it('找不到 addNode 函数签名锚点时抛异常', () => {
    expect(() => parseAddNodeSource('export const foo = 1\n')).toThrowError(/找不到 addNode 函数签名锚点/)
  })

  it('函数体花括号未配对时抛异常', () => {
    const broken = "addNode: (type, position, extraConfig) => {\n  if (type === 'a') {\n"
    expect(() => parseAddNodeSource(broken)).toThrowError(/未配对/)
  })

  it('分支数为 0 时抛异常', () => {
    const noBranch = 'addNode: (type, position, extraConfig) => {\n  const a = 1\n}\n'
    expect(() => parseAddNodeSource(noBranch)).toThrowError(/未解析出任何/)
  })
})

describe('注释与字符串的处理', () => {
  it('注释里的字段赋值示例不被当成真实赋值', () => {
    const source = [
      'addNode: (type, position, extraConfig) => {',
      "  if (type === 'demo_module') {",
      "    // resultVariable: 'from_comment'",
      "    /* variableName: 'from_block_comment' */",
      "    defaultData = { resultVariable: 'real_value' }",
      '  }',
      '}',
    ].join('\n')
    const { branches } = parseAddNodeSource(source)
    expect(branches).toHaveLength(1)
    expect(branches[0].body).not.toContain('from_comment')
    expect(branches[0].body).toContain('real_value')
  })

  it('行号可用于定位源码（抽样记录的行号落在合理范围）', () => {
    const sample = VAR_FIELDS.find((f) => f.moduleType === 'gesture_trigger')
    expect(sample, '未解析到 gesture_trigger 的记录').toBeDefined()
    expect(sample!.line).toBeGreaterThan(1400)
    expect(sample!.line).toBeLessThan(2500)
  })
})
