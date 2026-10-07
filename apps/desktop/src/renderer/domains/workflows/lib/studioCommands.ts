import { emitAssistantUiEvent } from '../api/aiAssistantSkills'
import { useWorkflowStore } from '../editor-store'
import { useLayoutStore } from '../hooks/stores/layoutStore'

export type EditorViewMode = 'flow' | 'block'

export interface StudioCommand {
  id: string
  label: string
  keywords: string
  shortcut?: string
  disabled: boolean
  run: () => void
}

export interface StudioCommandContext {
  /** 与工具栏按钮共用的禁用条件 */
  automation: boolean
  importing: boolean
  canUndo: boolean
  canRedo: boolean
  viewMode: EditorViewMode
  actions: {
    newWorkflow: () => void
    save: () => void
    open: () => void
    exportDialog: () => void
    importBundle: () => void
    scheduledTasks: () => void
    autoBrowser: () => void
    recorder: () => void
    globalConfig: () => void
    variableTracking: () => void
    inputOutput: () => void
    documentation: () => void
    assistant: () => void
    undo: () => void
    redo: () => void
    switchView: (mode: EditorViewMode) => void
  }
}

/** 命令注册表：执行全部委托给工具栏已有的处理函数，这里只负责名称、检索词与禁用条件 */
export function buildStudioCommands({ automation, importing, canUndo, canRedo, viewMode, actions: a }: StudioCommandContext): StudioCommand[] {
  const target: EditorViewMode = viewMode === 'flow' ? 'block' : 'flow'
  return [
    { id: 'new', label: '新建', keywords: '新建工作流 创建', shortcut: 'Alt+N', disabled: automation, run: a.newWorkflow },
    { id: 'save', label: '保存', keywords: '保存工作流', shortcut: 'Ctrl+S', disabled: false, run: a.save },
    { id: 'open', label: '打开', keywords: '打开工作流 载入', disabled: automation, run: a.open },
    { id: 'export', label: '导出', keywords: '导出工作流 脚本 文档', disabled: false, run: a.exportDialog },
    { id: 'import-bundle', label: '导入整包', keywords: '导入 整包 工作流包', disabled: importing || automation, run: a.importBundle },
    { id: 'scheduled-tasks', label: '计划任务', keywords: '定时 巡检 计划', disabled: false, run: a.scheduledTasks },
    { id: 'auto-browser', label: '自动化浏览器', keywords: '浏览器 网页', disabled: false, run: a.autoBrowser },
    { id: 'recorder', label: '录制', keywords: '网页智能录制 录制生成节点', disabled: false, run: a.recorder },
    { id: 'global-config', label: '全局配置', keywords: '设置 配置', disabled: false, run: a.globalConfig },
    { id: 'variable-tracking', label: '变量追踪', keywords: '变量 调试', disabled: false, run: a.variableTracking },
    { id: 'input-output', label: '输入与输出', keywords: '输入 输出 签名 字段 参数 样例', disabled: false, run: a.inputOutput },
    { id: 'documentation', label: '教学文档', keywords: '帮助 教程 文档', disabled: false, run: a.documentation },
    { id: 'assistant', label: 'AI 小助手', keywords: 'ai 助手 小助手', shortcut: 'Ctrl+J', disabled: false, run: a.assistant },
    { id: 'switch-view', label: target === 'block' ? '切换到模块条' : '切换到流程图', keywords: '视图 流程图 模块条', disabled: false, run: () => a.switchView(target) },
    { id: 'undo', label: '撤销', keywords: '回退', shortcut: 'Ctrl+Z', disabled: !canUndo, run: a.undo },
    { id: 'redo', label: '重做', keywords: '恢复', shortcut: 'Ctrl+Shift+Z', disabled: !canRedo, run: a.redo },
  ]
}

export function filterCommands(commands: StudioCommand[], query: string): StudioCommand[] {
  const q = query.trim().toLowerCase()
  if (!q) return commands
  return commands.filter(c => `${c.label} ${c.keywords}`.toLowerCase().includes(q))
}

/** 切换视图；模块条回到流程图时，节点重叠才自动排版（与画布底部原切换浮层行为一致） */
export async function switchEditorView(mode: EditorViewMode): Promise<void> {
  const layout = useLayoutStore.getState()
  const wasBlock = layout.editorViewMode === 'block'
  layout.setEditorViewMode(mode)
  if (mode !== 'flow' || !wasBlock) return
  const st = useWorkflowStore.getState()
  const ns = st.nodes
  if (ns.length < 2) return
  const overlap = ns.some((a, i) => ns.slice(i + 1).some(b =>
    Math.abs(a.position.x - b.position.x) < 40 && Math.abs(a.position.y - b.position.y) < 40))
  if (!overlap) return
  const res = await st.autoLayoutNodes({ direction: 'DOWN' })
  if (res.ok) setTimeout(() => emitAssistantUiEvent('fit_view', {}), 60)
}
