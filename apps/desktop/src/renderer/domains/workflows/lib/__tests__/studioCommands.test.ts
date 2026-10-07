import { describe, expect, it, vi } from 'vitest'
import { buildStudioCommands, filterCommands, type StudioCommandContext } from '../studioCommands'

const noop = () => {}
const baseActions: StudioCommandContext['actions'] = {
  newWorkflow: noop, save: noop, open: noop, exportDialog: noop, importBundle: noop, scheduledTasks: noop,
  autoBrowser: noop, recorder: noop, globalConfig: noop, variableTracking: noop, documentation: noop,
  assistant: noop, undo: noop, redo: noop, switchView: noop, inputOutput: noop,
}

function ctx(over: Partial<Omit<StudioCommandContext, 'actions'>> = {}, actions: Partial<StudioCommandContext['actions']> = {}): StudioCommandContext {
  return { automation: false, importing: false, canUndo: true, canRedo: true, viewMode: 'flow', ...over, actions: { ...baseActions, ...actions } }
}
const byId = (c: StudioCommandContext) => Object.fromEntries(buildStudioCommands(c).map(x => [x.id, x]))

describe('studioCommands', () => {
  it('registers every required command with a unique id', () => {
    const list = buildStudioCommands(ctx())
    expect(new Set(list.map(c => c.id)).size).toBe(list.length)
    expect(list.map(c => c.label)).toEqual(expect.arrayContaining([
      '新建', '保存', '打开', '导出', '导入整包', '计划任务', '自动化浏览器', '录制', '全局配置',
      '变量追踪', '输入与输出', '教学文档', 'AI 小助手', '撤销', '重做',
    ]))
    expect(list.some(c => c.id === 'switch-view')).toBe(true)
  })

  it('runs the 输入与输出 action and stays available in automation mode', () => {
    const inputOutput = vi.fn()
    const c = byId(ctx({ automation: true }, { inputOutput }))
    expect(c['input-output'].label).toBe('输入与输出')
    expect(c['input-output'].disabled).toBe(false)
    c['input-output'].run()
    expect(inputOutput).toHaveBeenCalledOnce()
    expect(filterCommands(Object.values(c), '签名').map(x => x.id)).toContain('input-output')
  })

  it('disables new/open/import in automation mode like the toolbar buttons', () => {
    const c = byId(ctx({ automation: true }))
    expect(c.new.disabled).toBe(true)
    expect(c.open.disabled).toBe(true)
    expect(c['import-bundle'].disabled).toBe(true)
    expect(c.save.disabled).toBe(false)
    expect(c.export.disabled).toBe(false)
  })

  it('disables import while an import is running, and undo/redo by history state', () => {
    const c = byId(ctx({ importing: true, canUndo: false, canRedo: false }))
    expect(c['import-bundle'].disabled).toBe(true)
    expect(c.new.disabled).toBe(false)
    expect(c.undo.disabled).toBe(true)
    expect(c.redo.disabled).toBe(true)
  })

  it('names the switch-view command after its target and runs the matching action', () => {
    const switchView = vi.fn()
    const flow = byId(ctx({ viewMode: 'flow' }, { switchView }))
    expect(flow['switch-view'].label).toBe('切换到模块条')
    flow['switch-view'].run()
    expect(switchView).toHaveBeenCalledWith('block')
    expect(byId(ctx({ viewMode: 'block' }))['switch-view'].label).toBe('切换到流程图')
  })

  it('runs the reused toolbar handlers', () => {
    const save = vi.fn()
    byId(ctx({}, { save })).save.run()
    expect(save).toHaveBeenCalledTimes(1)
  })

  it('filters by label and keywords, ignoring case and blanks', () => {
    const list = buildStudioCommands(ctx())
    expect(filterCommands(list, '').length).toBe(list.length)
    expect(filterCommands(list, '  保存 ').map(c => c.id)).toContain('save')
    expect(filterCommands(list, 'ai').map(c => c.id)).toContain('assistant')
    expect(filterCommands(list, 'zzzz-none')).toEqual([])
  })
})
