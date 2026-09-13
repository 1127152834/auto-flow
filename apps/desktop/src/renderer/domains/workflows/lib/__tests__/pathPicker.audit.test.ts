// Source: WebRPA@5ccb900e, lib/__tests__/pathPicker.audit.test.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 路径选择器完整性审计测试
 *
 * 规则：凡是让用户填「本地文件 / 文件夹路径」的输入框，旁边都必须有选择器
 * （PathInput / ImagePathInput，或手写的 systemApi.selectFile / selectFolder 按钮）。
 *
 * 为什么要用测试守住：只能手打路径的输入框对用户非常不友好，而这类遗漏不会报错、
 * 也不影响功能，只能靠人工发现——「播放音乐」的音频地址就这样漏了很久。
 *
 * 新增字段若命名含 path/file/dir 却不是本地路径（XPath、JSONPath、文件名模板、各种 ID），
 * 请登记到 audit-path-picker.mjs 的 NOT_FILESYSTEM_KEYS 并注明原因，
 * 以此强制每次新增都做一次判断。
 */
import { describe, it, expect } from 'vitest'
// @ts-expect-error mjs 无类型声明
import { findMissingPathPickers, NOT_FILESYSTEM_KEYS } from '../../tests/audits/audit-path-picker.mjs'

describe('路径选择器完整性', () => {
  it('所有本地路径输入框都配了文件/文件夹选择器', () => {
    const gaps = findMissingPathPickers() as Array<{
      file: string
      line: number
      key: string
      detail: string
    }>
    const detail = gaps.map((g) => `  ${g.file}:${g.line} ${g.key} — ${g.detail}`).join('\n')
    expect(
      gaps.length,
      `以下路径输入框缺少选择器（用户只能手打路径）：\n${detail}\n` +
        `若该字段并非本地文件系统路径，请登记到 audit-path-picker.mjs 的 NOT_FILESYSTEM_KEYS。`,
    ).toBe(0)
  })

  it('非路径字段白名单不为空且无重复（登记项应逐条注明原因）', () => {
    const list = Array.from(NOT_FILESYSTEM_KEYS as Set<string>)
    expect(list.length).toBeGreaterThan(0)
    expect(new Set(list).size).toBe(list.length)
  })
})
