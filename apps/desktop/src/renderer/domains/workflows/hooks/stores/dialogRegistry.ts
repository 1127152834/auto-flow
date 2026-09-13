// Source: WebRPA@5ccb900e, store/dialogRegistry.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 全局弹窗注册表
 *
 * 设计目标：让 AI 小助手能感知任何弹窗的出现并自主操作（提交/取消/选择等）。
 * 所有需要 AI 能感知/操作的弹窗在 mount 时注册自己，unmount 时注销。
 *
 * AI 通过 client_action：
 *   - list_open_dialogs           列出当前所有打开的弹窗
 *   - respond_to_dialog           响应弹窗（执行某个 action）
 *   - dismiss_dialog              关闭弹窗（等同于点取消）
 */
import { create } from 'zustand'

export interface DialogActionDef {
  /** action 唯一名（英文小写下划线，如 'submit' 'cancel' 'confirm' 'overwrite' 'rename'） */
  name: string
  /** 给 AI 看的中文说明（"提交并继续" / "覆盖原文件" 等） */
  label: string
  /** 是否是默认/主要操作（点确定那种） */
  primary?: boolean
  /** 是否是危险操作（"删除" "覆盖原文件"） */
  destructive?: boolean
  /** 这个 action 需要哪些参数（schema 形式让 AI 知道要传什么） */
  params?: Record<string, {
    type: 'string' | 'number' | 'boolean' | 'array'
    description?: string
    required?: boolean
    /** 对枚举值给出选项 */
    options?: string[]
  }>
  /** 实际执行时的回调 */
  handler: (params?: Record<string, any>) => void | Promise<void>
}

export interface DialogInfo {
  /** 弹窗唯一 ID（建议用 nanoid 或弹窗内 requestId） */
  id: string
  /** 弹窗类型，让 AI 一眼分辨："input_prompt" | "confirm_overwrite" | "confirm_delete" | "select" 等 */
  type: string
  /** 标题（中文） */
  title: string
  /** 说明性文字（可选） */
  message?: string
  /** 弹窗上下文数据（让 AI 看到当前默认值/选项/限制范围等） */
  context?: Record<string, any>
  /** 可用操作列表 */
  actions: DialogActionDef[]
  /** 打开时间，便于 AI 识别"最近的"弹窗 */
  openedAt: number
}

interface DialogRegistryState {
  dialogs: DialogInfo[]
  register: (info: Omit<DialogInfo, 'openedAt'>) => void
  unregister: (id: string) => void
  /** 获取某个弹窗的某个 action（被 client_action 用） */
  getAction: (dialogId: string, actionName: string) => DialogActionDef | undefined
  /** 清空（用于测试） */
  clear: () => void
}

export const useDialogRegistry = create<DialogRegistryState>((set, get) => ({
  dialogs: [],
  register: (info) => {
    set((s) => {
      // 防重复注册（如果同 id 已存在，覆盖）
      const filtered = s.dialogs.filter((d) => d.id !== info.id)
      return {
        dialogs: [...filtered, { ...info, openedAt: Date.now() }],
      }
    })
  },
  unregister: (id) => {
    set((s) => ({ dialogs: s.dialogs.filter((d) => d.id !== id) }))
  },
  getAction: (dialogId, actionName) => {
    const d = get().dialogs.find((x) => x.id === dialogId)
    return d?.actions.find((a) => a.name === actionName)
  },
  clear: () => set({ dialogs: [] }),
}))

/**
 * AI 看到的"对外信息"——剥离 handler 函数，只保留可序列化的数据
 */
export function getDialogInfoForAI() {
  return useDialogRegistry.getState().dialogs.map((d) => ({
    id: d.id,
    type: d.type,
    title: d.title,
    message: d.message,
    context: d.context,
    actions: d.actions.map((a) => ({
      name: a.name,
      label: a.label,
      primary: a.primary || false,
      destructive: a.destructive || false,
      params: a.params,
    })),
    opened_at: d.openedAt,
    opened_seconds_ago: Math.round((Date.now() - d.openedAt) / 1000),
  }))
}

/**
 * 让弹窗组件用 hook 风格注册自己（自动处理生命周期）
 */
export function useRegisterDialog(info: DialogInfo | null | undefined): void {
  // 用 zustand 直接订阅，避免 useEffect 依赖混乱
  // 实际是 React 组件内调用：
  //   useEffect(() => { register(info); return () => unregister(info.id) }, [info?.id])
  // 这里给个独立函数，让组件按需自己写 useEffect
  void info
}
