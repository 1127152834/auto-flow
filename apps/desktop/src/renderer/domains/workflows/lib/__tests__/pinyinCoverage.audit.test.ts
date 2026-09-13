// Source: WebRPA@5ccb900e, lib/__tests__/pinyinCoverage.audit.test.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 模块拼音 / 首字母搜索全覆盖审计（Property 11 · 需求 1）
 *
 * 目的：把「任意模块都能用全拼、首字母、中文子串、英文 module_type 搜到」这个
 * 当前成立的性质固化成断言，防止后续新增模块时悄悄退化（设计决策 3：只补守护
 * 测试，不改 pinyin.ts 的功能实现）。
 *
 * 数据源（不维护并行清单）：
 *   - moduleTypeLabels（workflowStore）：module_type -> 中文名，模块集合的唯一来源。
 *   - moduleMatchesQuery / getPinyin / getPinyinInitials（lib/pinyin）：被测匹配逻辑。
 *
 * 关于「自证闭环」的说明（设计决策 2）：
 *   全拼查询本身由 getPinyin(label) 生成，若只断言「moduleMatchesQuery 能命中它」，
 *   在字典缺字时会自洽为真（缺字时 getPinyin 原样保留该汉字，查询串与被匹配串同样
 *   带着这个汉字，仍然 includes 成立），从而掩盖「用户按正常拼音搜不到」的真实缺口。
 *   因此本文件把「缺字检查」作为独立且必须的一条断言：
 *     - 逐字校验：中文名里每个汉字都必须能被 pinyin 字典解析成纯字母拼音；
 *     - 整串校验：getPinyin / getPinyinInitials 的输出里不得残留任何汉字。
 *   两者任一不满足即报出「module_type + 中文名 + 缺字清单」。
 *
 * 搜索字段口径：只提供 label 与 type，**故意不提供 keywords**。
 *   需求 1.6 要求「新增模块未登记搜索关键词时，仍能靠中文名拼音搜到」，若把
 *   moduleKeywords 一并传入，模块可能靠关键词命中而掩盖中文名拼音链路的缺口。
 */
import { describe, it, expect } from 'vitest'
import { pinyin } from 'pinyin-pro'
import { getPinyin, getPinyinInitials, moduleMatchesQuery } from '../pinyin'
import { moduleTypeLabels } from '../../editor-store'

/**
 * 不参与搜索覆盖审计的伪类型（requirements 中定义的四个伪类型里的两个）：
 *   - custom_module：自定义模块占位类型，侧边栏中由 CustomModuleList 单独渲染真实自定义模块，
 *     占位类型本身不出现在模块搜索结果里。
 *   - subflow_header：子流程头节点，由执行器内部生成，用户不可搜索、不可拖拽。
 *
 * group（分组）与 note（便签）**保留在审计范围内**：它们是可拖拽的画布工具，
 * 在 ModuleSidebar 分类中有登记并参与搜索，用户确实会用「fz」「bq」去搜它们。
 * 保留后本审计口径 = 571 - 2 = 569，与对外披露口径一致（见 requirements 模块数量口径）。
 */
const NON_SEARCHABLE_PSEUDO_TYPES: ReadonlySet<string> = new Set<string>([
  'custom_module',
  'subflow_header',
])

/** 审计范围内的模块条目：[module_type, 中文名] */
function getAuditedModules(): { type: string; label: string }[] {
  return Object.entries(moduleTypeLabels)
    .filter(([type]) => !NON_SEARCHABLE_PSEUDO_TYPES.has(type))
    .map(([type, label]) => ({ type, label: label as string }))
}

/** 判断一个码点是否为汉字（覆盖 BMP 常用区、扩展 A、兼容区与扩展 B 及以后） */
function isHanCodePoint(cp: number): boolean {
  return (
    (cp >= 0x3400 && cp <= 0x4dbf) || // CJK 扩展 A
    (cp >= 0x4e00 && cp <= 0x9fff) || // CJK 基本区
    (cp >= 0xf900 && cp <= 0xfaff) || // CJK 兼容表意文字
    (cp >= 0x20000 && cp <= 0x3134f) // CJK 扩展 B 及以后（含代理对字符）
  )
}

/** 字符串中是否残留汉字（用于整串纯度校验） */
function containsHanChar(str: string): boolean {
  for (const ch of str) {
    const cp = ch.codePointAt(0)
    if (cp !== undefined && isHanCodePoint(cp)) return true
  }
  return false
}

/** 单字拼音（与 pinyin.ts 相同参数，用于逐字缺字检测） */
function singleCharPinyin(ch: string): string {
  return pinyin(ch, { toneType: 'none', type: 'string', nonZh: 'consecutive', v: true })
    .replace(/\s+/g, '')
    .toLowerCase()
}

/** 取中文名里未被拼音字典覆盖的汉字清单（字典缺字时 pinyin-pro 原样返回该汉字） */
function findUncoveredHanChars(label: string): string[] {
  const missing: string[] = []
  for (const ch of label) {
    const cp = ch.codePointAt(0)
    if (cp === undefined || !isHanCodePoint(cp)) continue
    if (!/^[a-z]+$/.test(singleCharPinyin(ch))) missing.push(ch)
  }
  return Array.from(new Set(missing))
}

/**
 * 取中文名里最长的一段**连续**汉字（用于构造中文子串查询）。
 *
 * 必须取连续段而不是「所有汉字拼起来」：像「刷新Excel数据」「盲水印·嵌入文字」
 * 这类中英/标点混排的名字，把汉字抽出来拼接会得到「新数」「印嵌」这种在原名里
 * 并不存在的串，那不是用户会输入的子串，用它断言只会造出假失败。
 */
function longestHanRunOf(label: string): string[] {
  let best: string[] = []
  let current: string[] = []
  for (const ch of label) {
    const cp = ch.codePointAt(0)
    if (cp !== undefined && isHanCodePoint(cp)) {
      current.push(ch)
      if (current.length > best.length) best = [...current]
    } else {
      current = []
    }
  }
  return best
}

/** 模块搜索字段：只给 label 与 type，不给 keywords（见文件头说明） */
function searchFieldsOf(mod: { type: string; label: string }) {
  return { label: mod.label, type: mod.type }
}

const AUDITED_MODULES = getAuditedModules()

describe('模块拼音与首字母搜索全覆盖审计 - Property 11', () => {
  it('审计范围非空且口径符合预期（防审计函数静默返回空集导致假绿）', () => {
    expect(AUDITED_MODULES.length).toBeGreaterThan(500)
    expect(AUDITED_MODULES.every((m) => typeof m.label === 'string' && m.label.length > 0)).toBe(true)
  })

  // Property 11 · 缺字检查
  // 中文名里每个汉字都必须被 pinyin 字典覆盖，且 getPinyin / getPinyinInitials
  // 的输出里不得残留汉字；否则用户按正常拼音输入必然搜不到（静默降级）。
  // Validates: Requirements 1.8
  it('Property 11e: 拼音字典覆盖全部模块中文名用到的汉字，拼音输出无汉字残留', () => {
    const gaps: { type: string; label: string; missingChars: string[]; pinyin: string; initials: string }[] = []

    for (const mod of AUDITED_MODULES) {
      const missingChars = findUncoveredHanChars(mod.label)
      const full = getPinyin(mod.label)
      const initials = getPinyinInitials(mod.label)
      if (missingChars.length > 0 || containsHanChar(full) || containsHanChar(initials)) {
        gaps.push({ type: mod.type, label: mod.label, missingChars, pinyin: full, initials })
      }
    }

    expect(
      gaps,
      `拼音字典缺字，以下模块无法通过正常拼音搜到（module_type / 中文名 / 缺字清单）：\n${JSON.stringify(gaps, null, 2)}`,
    ).toEqual([])
  })

  // Property 11a: 全拼可搜到
  // Validates: Requirements 1.1, 1.6, 1.7
  it('Property 11a: 每个模块都能被其中文名的无声调全拼连写命中', () => {
    const misses: { type: string; label: string; query: string }[] = []

    for (const mod of AUDITED_MODULES) {
      const query = getPinyin(mod.label)
      if (!query || !moduleMatchesQuery(query, searchFieldsOf(mod))) {
        misses.push({ type: mod.type, label: mod.label, query })
      }
    }

    expect(
      misses,
      `以下模块无法通过全拼搜到（module_type / 中文名 / 查询串）：\n${JSON.stringify(misses, null, 2)}`,
    ).toEqual([])
  })

  // Property 11b: 首字母可搜到
  // Validates: Requirements 1.2, 1.6, 1.7
  it('Property 11b: 每个模块都能被其中文名的拼音首字母连写命中', () => {
    const misses: { type: string; label: string; query: string }[] = []

    for (const mod of AUDITED_MODULES) {
      const query = getPinyinInitials(mod.label)
      if (!query || !moduleMatchesQuery(query, searchFieldsOf(mod))) {
        misses.push({ type: mod.type, label: mod.label, query })
      }
    }

    expect(
      misses,
      `以下模块无法通过拼音首字母搜到（module_type / 中文名 / 查询串）：\n${JSON.stringify(misses, null, 2)}`,
    ).toEqual([])
  })

  // Property 11c: 中文子串可搜到
  // Validates: Requirements 1.3
  it('Property 11c: 每个模块都能被其中文名整串与中文子串命中', () => {
    const misses: { type: string; label: string; query: string }[] = []

    for (const mod of AUDITED_MODULES) {
      const fields = searchFieldsOf(mod)
      const queries = new Set<string>([mod.label])
      const hanRun = longestHanRunOf(mod.label)
      // 取最长连续汉字段的中间两字（不足两字时退化为单字），模拟用户只记得中文名一部分
      if (hanRun.length >= 2) {
        const start = Math.floor((hanRun.length - 2) / 2)
        queries.add(hanRun.slice(start, start + 2).join(''))
      } else if (hanRun.length === 1) {
        queries.add(hanRun[0])
      }

      for (const query of queries) {
        if (!moduleMatchesQuery(query, fields)) {
          misses.push({ type: mod.type, label: mod.label, query })
        }
      }
    }

    expect(
      misses,
      `以下模块无法通过中文子串搜到（module_type / 中文名 / 查询串）：\n${JSON.stringify(misses, null, 2)}`,
    ).toEqual([])
  })

  // Property 11d: 英文 module_type 可搜到
  // Validates: Requirements 1.3
  it('Property 11d: 每个模块都能被其英文 module_type 整串与子串命中', () => {
    const misses: { type: string; label: string; query: string }[] = []

    for (const mod of AUDITED_MODULES) {
      const fields = searchFieldsOf(mod)
      const queries = new Set<string>([mod.type])
      // 取 module_type 的首段（下划线前）作为子串查询，模拟用户只记得英文名前缀
      const head = mod.type.split('_')[0]
      if (head && head !== mod.type) queries.add(head)

      for (const query of queries) {
        if (!moduleMatchesQuery(query, fields)) {
          misses.push({ type: mod.type, label: mod.label, query })
        }
      }
    }

    expect(
      misses,
      `以下模块无法通过英文 module_type 搜到（module_type / 中文名 / 查询串）：\n${JSON.stringify(misses, null, 2)}`,
    ).toEqual([])
  })

  // Property 11 · 大小写不敏感
  // Validates: Requirements 1.4
  it('Property 11f: 大小写混杂查询的结果与全小写查询一致', () => {
    const misses: { type: string; label: string; query: string; upper: boolean; lower: boolean }[] = []

    for (const mod of AUDITED_MODULES) {
      const fields = searchFieldsOf(mod)
      for (const base of [getPinyin(mod.label), getPinyinInitials(mod.label), mod.type]) {
        if (!base) continue
        const lower = moduleMatchesQuery(base.toLowerCase(), fields)
        const upper = moduleMatchesQuery(base.toUpperCase(), fields)
        if (lower !== upper) {
          misses.push({ type: mod.type, label: mod.label, query: base, upper, lower })
        }
      }
    }

    expect(
      misses,
      `以下模块的大小写混杂查询结果与全小写不一致：\n${JSON.stringify(misses, null, 2)}`,
    ).toEqual([])
  })
})
