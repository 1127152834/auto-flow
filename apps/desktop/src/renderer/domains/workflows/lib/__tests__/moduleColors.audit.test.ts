// Source: WebRPA@5ccb900e, lib/__tests__/moduleColors.audit.test.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 模块画布配色与分类色一致性审计测试（子系统 4 / 需求 4）
 *
 * 本文件以确定性结构断言核验 Property 7/8/9：配色由 moduleCategories 自动派生，
 * 「模块只要归属某分类则其画布色必等于分类色」结构上天然一致，真正的缺口是：
 *   - 模块未归入任何分类（落默认灰色）；
 *   - 模块被多个分类重复收录（颜色由最后写入者决定，存在歧义）；
 *   - 分类的 color 未在 colorClassMap / tailwindHex 登记（派生时回退默认色）。
 *
 * 数据源（单一真相，不重复维护并行清单）：
 *   - moduleCategories（ModuleSidebar）：分类 -> color -> 模块 type 清单，配色唯一来源。
 *   - moduleColors / colorClassMap / DEFAULT_NODE_COLOR_CLASS（moduleColors.ts）：派生结果与映射表。
 *   - moduleTypeLabels（workflowStore）：模块 type -> 中文名，按 ModuleType 全量键控，
 *     是独立于 moduleCategories 的「前端全模块集合」来源（用于 Property 8 暴露未分类缺口）。
 *
 * 注意：本任务（3.1）是「先红」核验工具，此刻测试可能因暴露真实缺口而失败属预期，
 * 修复在任务 3.2 进行——不在此处改 moduleCategories。
 */
import { describe, it, expect } from 'vitest'
import {
  moduleColors,
  colorClassMap,
  DEFAULT_NODE_COLOR_CLASS,
  findUncategorizedModules,
  findDuplicateCategorizedModules,
  findUnmappedCategoryColors,
} from '../../components/moduleColors'
import { moduleCategories, excludedModuleTypes } from '../../components/ModuleSidebar'
import { moduleTypeLabels } from '../../editor-store'

/**
 * 非执行器的 UI 伪模块类型：分组容器、便签、子流程头、自定义模块。
 * 它们刻意不归入任何配色分类（不是后端注册的真实模块），核验全模块集合时需排除，
 * 以免误报为「未分类缺口」。
 */
const NON_EXECUTOR_PSEUDO_TYPES: ReadonlySet<string> = new Set<string>([
  'group',
  'note',
  'subflow_header',
  'custom_module',
])

/**
 * 前端全模块集合：moduleTypeLabels 的全部 key（独立于 moduleCategories），
 * 剔除非执行器伪模块。作为 Property 8 的「全模块集合」口径。
 */
function getAllModuleTypes(): string[] {
  return Object.keys(moduleTypeLabels).filter(
    (type) => !NON_EXECUTOR_PSEUDO_TYPES.has(type) && !excludedModuleTypes.has(type as never),
  )
}

describe('模块配色审计 - Property 7/8/9', () => {
  // Property 7: 模块配色等于分类色
  // 对任意模块 m，moduleColors[m.type] 等于其所属分类 color 经 colorClassMap 映射的结果，
  // 且不回退到默认灰色。
  // Validates: Requirements 4.2, 4.3
  it('Property 7: 每个模块的画布色等于其分类色经 colorClassMap 的映射结果且不回退灰色', () => {
    const mismatches: { type: string; category: string; color: string; actual: string; expected: string }[] = []

    for (const category of moduleCategories) {
      const expected = colorClassMap[category.color]
      for (const moduleType of category.modules) {
        const type = moduleType as string
        const actual = moduleColors[type]
        // 期望：分类 color 在 colorClassMap 有登记，且 moduleColors 取该映射、不回退灰色。
        if (expected === undefined || actual !== expected || actual === DEFAULT_NODE_COLOR_CLASS) {
          mismatches.push({
            type,
            category: category.name,
            color: category.color,
            actual: actual ?? '(undefined)',
            expected: expected ?? '(unmapped color)',
          })
        }
      }
    }

    expect(
      mismatches,
      `存在模块画布色与分类色不一致（或回退灰色）：\n${JSON.stringify(mismatches, null, 2)}`,
    ).toEqual([])
  })

  // Property 8: 模块在分类中出现且仅一次
  // 每个 module_type 在 moduleCategories 中出现且仅出现一次，即
  // findUncategorizedModules（用全模块集合）与 findDuplicateCategorizedModules 均为空。
  // Validates: Requirements 4.4
  it('Property 8a: 全模块集合中不存在未归入任何分类的模块（否则落默认灰色）', () => {
    const allTypes = getAllModuleTypes()
    const uncategorized = findUncategorizedModules(allTypes)

    expect(
      uncategorized,
      `存在未归入任何分类的模块（画布会落默认灰色）：\n${JSON.stringify(uncategorized, null, 2)}`,
    ).toEqual([])
  })

  it('Property 8b: 不存在被多个分类重复收录的模块（否则配色存在歧义）', () => {
    const duplicates = findDuplicateCategorizedModules()

    expect(
      duplicates,
      `存在被多个分类重复收录的模块（配色由最后写入者决定）：\n${JSON.stringify(duplicates, null, 2)}`,
    ).toEqual([])
  })

  // Property 9: 分类色已登记映射
  // 每个分类的 color 都在 colorClassMap 与 tailwindHex 中登记，即
  // findUnmappedCategoryColors 为空。
  // Validates: Requirements 4.1
  it('Property 9: 每个分类的 color 都已在 colorClassMap 与 tailwindHex 登记', () => {
    const unmapped = findUnmappedCategoryColors()

    expect(
      unmapped,
      `存在未在 colorClassMap/tailwindHex 登记的分类 color（派生时回退默认色）：\n${JSON.stringify(unmapped, null, 2)}`,
    ).toEqual([])
  })
})

// ============================================================================
// 三处取色同源审计（spec: module-integrity-audit / Property 7）
//
// 注意属性编号口径：本文件上方的 Property 7/8/9 沿用早期 spec 的编号；下方新增的
// 「三处同源」对应 spec module-integrity-audit 的 Property 7，为避免混淆一律带 spec 名标注。
//
// 取色的三处使用场景：
//   1) 画布节点 ModuleNode        -> getNodeColorClass(type)
//   2) 缩略图 minimap             -> getModuleHexColor(type)
//   3) 模块条视图 BlockFlowView   -> getBlockRowColorClasses(type)
//
// 「同源」的判定不是「三者相等」（取值域不同：类名 vs hex），而是三者都必须能被
// 同一个分类 color 独立推导出来。因此测试从 category.color 字面量出发**独立复算**
// 期望值，再与三个取色函数的实际返回值比对——不复用被测函数的输出做期望值，避免自证闭环。
// ============================================================================
import {
  getNodeColorClass,
  getModuleHexColor,
  getBlockRowColorClasses,
  findCategoryColorCollisions,
  tailwindHex,
  DEFAULT_NODE_HEX_COLOR,
  type BlockRowColorClasses,
} from '../../components/moduleColors'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

/** 分类 color 字面量（形如 `bg-indigo-600`）解析为颜色名与色阶。 */
function parseCategoryColor(color: string): { name: string; shade: string } {
  const matched = /^bg-([a-z]+)-(\d{2,3})$/.exec(color)
  if (!matched) {
    throw new Error(`分类 color 不符合 bg-{name}-{shade} 约定：${color}`)
  }
  return { name: matched[1], shade: matched[2] }
}

/** 由分类 color 独立推导模块条视图应得的四个类名（与 getBlockRowColorClasses 实现无关）。 */
function deriveExpectedBlockRow(color: string): BlockRowColorClasses {
  const { name, shade } = parseCategoryColor(color)
  return {
    borderClass: `border-${name}-${shade}`,
    bgClass: `bg-${name}-100`,
    accentBarClass: `bg-${name}-${shade}`,
    // 实现规则：border 换 text 前缀，色阶 500 加深一档为 600，其余色阶保持
    accentTextClass: `text-${name}-${shade === '500' ? '600' : shade}`,
  }
}

/** 读取前端源码文件（用于静态扫描调用点，不依赖组件渲染）。 */
function readFrontendSource(relativeFromSrc: string): string {
  const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  return readFileSync(path.join(srcDir, relativeFromSrc), 'utf-8')
}

describe('模块配色三处同源审计 - module-integrity-audit Property 7', () => {
  // 对同一 module_type，画布节点 / 缩略图 hex / 模块条视图三处取到的颜色，
  // 必须都能由其所属分类的同一个 color 推导出来。
  // Validates: Requirements 4.1, 4.2, 4.3, 4.5
  it('Property 7: 画布节点、缩略图 hex、模块条视图三处取色同源于分类 color', () => {
    const mismatches: {
      type: string
      category: string
      color: string
      site: 'canvasNode' | 'minimapHex' | 'blockRow'
      expected: unknown
      actual: unknown
    }[] = []
    let checked = 0

    for (const category of moduleCategories) {
      const expectedNodeClass = colorClassMap[category.color]
      const expectedHex = tailwindHex[category.color]
      const expectedBlockRow = deriveExpectedBlockRow(category.color)

      for (const moduleType of category.modules) {
        const type = moduleType as string
        checked += 1

        const actualNodeClass = getNodeColorClass(type)
        if (actualNodeClass !== expectedNodeClass) {
          mismatches.push({
            type, category: category.name, color: category.color,
            site: 'canvasNode', expected: expectedNodeClass ?? '(unmapped color)', actual: actualNodeClass,
          })
        }

        const actualHex = getModuleHexColor(type)
        if (actualHex !== expectedHex) {
          mismatches.push({
            type, category: category.name, color: category.color,
            site: 'minimapHex', expected: expectedHex ?? '(unmapped color)', actual: actualHex,
          })
        }

        const actualBlockRow = getBlockRowColorClasses(type)
        if (
          actualBlockRow.borderClass !== expectedBlockRow.borderClass ||
          actualBlockRow.bgClass !== expectedBlockRow.bgClass ||
          actualBlockRow.accentBarClass !== expectedBlockRow.accentBarClass ||
          actualBlockRow.accentTextClass !== expectedBlockRow.accentTextClass
        ) {
          mismatches.push({
            type, category: category.name, color: category.color,
            site: 'blockRow', expected: expectedBlockRow, actual: actualBlockRow,
          })
        }
      }
    }

    // 防空跑：分类清单为空或解析异常时，上面的循环不会报错却什么也没测。
    // 用户追加排除48个数据库及9个DP节点；保留严格数量与逐项配色断言。
    expect(checked, '被核验的模块数异常偏少，审计可能空跑').toBe(230)
    expect(
      mismatches,
      `存在三处取色不同源的模块：\n${JSON.stringify(mismatches, null, 2)}`,
    ).toEqual([])
  })

  it('Property 7 交叉核验: 分类 color 相同的模块，三处取色结果必须完全一致', () => {
    const colorToSample = new Map<string, { type: string; node: string; hex: string; row: BlockRowColorClasses }>()
    const conflicts: { color: string; a: string; b: string }[] = []

    for (const category of moduleCategories) {
      for (const moduleType of category.modules) {
        const type = moduleType as string
        const current = {
          type,
          node: getNodeColorClass(type),
          hex: getModuleHexColor(type),
          row: getBlockRowColorClasses(type),
        }
        const sample = colorToSample.get(category.color)
        if (!sample) {
          colorToSample.set(category.color, current)
          continue
        }
        if (
          sample.node !== current.node ||
          sample.hex !== current.hex ||
          JSON.stringify(sample.row) !== JSON.stringify(current.row)
        ) {
          conflicts.push({ color: category.color, a: sample.type, b: current.type })
        }
      }
    }

    expect(
      conflicts,
      `同一分类 color 下的模块取色不一致（说明存在第二份颜色来源）：\n${JSON.stringify(conflicts, null, 2)}`,
    ).toEqual([])
  })

  // 需求 4.6：兜底样式只允许一份定义，调用点不得各自硬编码字面量。
  // Validates: Requirements 4.6
  it('Requirement 4.6: 未知模块的兜底样式来自唯一一份定义', () => {
    expect(getNodeColorClass('__not_a_real_module__')).toBe(DEFAULT_NODE_COLOR_CLASS)
    expect(getNodeColorClass(undefined)).toBe(DEFAULT_NODE_COLOR_CLASS)
    expect(getModuleHexColor('__not_a_real_module__')).toBe(DEFAULT_NODE_HEX_COLOR)
    expect(getModuleHexColor(undefined)).toBe(DEFAULT_NODE_HEX_COLOR)

    // 模块条视图的兜底同样派生自 DEFAULT_NODE_COLOR_CLASS，而非独立字面量
    const fallbackRow = getBlockRowColorClasses('__not_a_real_module__')
    const fallbackParts = DEFAULT_NODE_COLOR_CLASS.split(' ')
    expect(fallbackRow.borderClass).toBe(fallbackParts.find((c) => c.startsWith('border-')))
    expect(fallbackRow.bgClass).toBe(fallbackParts.find((c) => c.startsWith('bg-')))
  })

  it('Requirement 4.6: 三处取色调用点不得硬编码兜底配色字面量', () => {
    const sites: { file: string; requiredImport: string; scanFallbackLiteral: boolean }[] = [
      // 这两处历史上各自写过兜底字面量（'border-gray-500 bg-gray-50' / 'border-slate-300'），需扫描
      { file: 'components/ModuleNode.tsx', requiredImport: 'getNodeColorClass', scanFallbackLiteral: true },
      { file: 'components/BlockFlowView.tsx', requiredImport: 'getBlockRowColorClasses', scanFallbackLiteral: true },
      // 缩略图仅核验调用点：该文件还负责自定义模块的用户自选色，含与模块配色无关的色值默认值
      { file: 'components/WorkflowEditor.tsx', requiredImport: 'getModuleHexColor', scanFallbackLiteral: false },
    ]
    const violations: { file: string; reason: string; snippet?: string }[] = []

    for (const site of sites) {
      const source = readFrontendSource(site.file)
      if (!source.includes(site.requiredImport)) {
        violations.push({ file: site.file, reason: `未使用统一取色函数 ${site.requiredImport}` })
      }
      if (!site.scanFallbackLiteral) continue
      // 形如 `|| 'border-gray-500 bg-gray-50'` / `|| '#3b82f6'` 的兜底字面量
      const hardcoded = source.match(/\|\|\s*['"`](?:border-|bg-|text-|#[0-9a-fA-F]{3,8})[^'"`]*['"`]/g)
      for (const snippet of hardcoded ?? []) {
        violations.push({ file: site.file, reason: '存在硬编码兜底配色字面量', snippet })
      }
    }

    expect(
      violations,
      `兜底配色未收敛到唯一一份定义：\n${JSON.stringify(violations, null, 2)}`,
    ).toEqual([])
  })

  // 需求 4.7：撞色仅报告、不判定失败。
  // Validates: Requirements 4.7
  it('Requirement 4.7: 输出分类撞色报告（仅报告，不判定失败）', () => {
    const collisions = findCategoryColorCollisions()
    const affectedCategories = collisions.reduce((sum, item) => sum + item.categories.length, 0)

    const lines = [
      '[配色审计] 分类撞色报告（不判定失败，供人工决定是否调色）',
      `  撞色 color 数：${collisions.length}，涉及分类数：${affectedCategories}`,
      ...collisions.map((item) => `  ${item.color} <- ${item.categories.join(' / ')}`),
    ]
    console.info(lines.join('\n'))

    // 仅核验报告结构本身可用（每组必须 ≥2 个分类），不对撞色数量设阈值
    for (const item of collisions) {
      expect(item.categories.length).toBeGreaterThanOrEqual(2)
    }
  })
})
