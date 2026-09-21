// Source: WebRPA@5ccb900e; see SOURCE.md for provenance and adaptation boundaries.
import { create } from 'zustand'
import { scheduledTaskApi, type ApiResponse } from '../../api'

function requireResponse<T>(response: ApiResponse<T>): ApiResponse<T> & { data: T } {
  if (!response.success || response.data === undefined) throw new Error(response.error || 'Scheduled task request failed')
  return response as ApiResponse<T> & { data: T }
}

export interface ScheduledTaskTrigger {
  type: 'time' | 'hotkey' | 'startup' | 'webhook'

  // 时间触发器配置
  schedule_type?: 'once' | 'daily' | 'weekly' | 'monthly' | 'interval'
  start_date?: string // YYYY-MM-DD
  start_time?: string // HH:MM:SS
  end_date?: string // YYYY-MM-DD

  // 重复配置
  repeat_enabled?: boolean
  repeat_count?: number | null // null表示无限重复
  repeat_interval?: number // 重复间隔（秒）

  // 每日触发配置
  daily_time?: string // HH:MM:SS

  // 每周触发配置
  weekly_days?: number[] // [0-6] 0=周日, 1=周一, ...
  weekly_time?: string // HH:MM:SS

  // 每月触发配置
  monthly_day?: number // 1-31
  monthly_time?: string // HH:MM:SS

  // 间隔触发配置
  interval_seconds?: number

  // 热键触发器配置
  hotkey?: string

  // 启动触发器配置
  startup_delay?: number

  // Webhook触发器配置
  webhook_path?: string
}

export interface ScheduledTask {
  id: string
  name: string
  description?: string
  workflow_id: string
  workflow_name?: string
  profile_id?: string
  trigger: ScheduledTaskTrigger
  enabled: boolean

  // 执行统计
  total_executions: number
  success_executions: number
  failed_executions: number
  last_execution_time?: string
  last_execution_status?: 'success' | 'failed' | 'stopped'
  last_execution_error?: string
  next_execution_time?: string | null

  // 时间戳
  created_at: string
  updated_at: string

  // 内部状态
  is_running?: boolean
  current_repeat_count?: number

  // 运行模式
  open_monitor?: boolean
  headless?: boolean

  // 失败/成功通知
  notify_on_failure?: boolean
  notify_on_success?: boolean
  notify_channels?: NotifyChannel[]
}

const pendingExecutionCommands = new Map<string, string>()

export interface NotifyChannel {
  type: 'email' | 'wecom' | 'dingtalk' | 'serverchan' | 'webhook'
  enabled?: boolean
  // email
  smtp_server?: string
  smtp_port?: number
  username?: string
  password?: string
  to?: string
  use_ssl?: boolean
  // wecom / dingtalk
  key?: string
  webhook?: string
  access_token?: string
  secret?: string
  // serverchan
  sendkey?: string
  // webhook
  url?: string
}

export interface ScheduledTaskExecutionLog {
  id: string
  task_id: string
  task_name: string
  workflow_id: string
  workflow_name: string
  start_time?: string
  end_time?: string
  duration?: number
  status: 'queued' | 'running' | 'success' | 'failed' | 'stopped'
  error?: string
  trigger_type: 'time' | 'hotkey' | 'startup' | 'manual' | 'webhook' | 'repeat'
  trigger_time: string
  executed_nodes: number
  failed_nodes: number
  collected_data_count: number
  // 额外日志（可选）
  workflow_logs?: any[]
}

export interface StatisticsSummary {
  total_tasks: number
  enabled_tasks: number
  disabled_tasks: number
  total_executions: number
  success_executions: number
  failed_executions: number
  success_rate: number
  trigger_types: Record<string, number>
}

interface ScheduledTaskStore {
  tasks: ScheduledTask[]
  logs: ScheduledTaskExecutionLog[]
  statistics: StatisticsSummary | null
  loading: boolean
  error: string | null

  // 任务管理
  fetchTasks: () => Promise<void>
  createTask: (task: Omit<ScheduledTask, 'id' | 'total_executions' | 'success_executions' | 'failed_executions' | 'created_at' | 'updated_at'>) => Promise<ScheduledTask>
  updateTask: (id: string, updates: Partial<ScheduledTask>) => Promise<ScheduledTask>
  deleteTask: (id: string) => Promise<void>
  toggleTask: (id: string, enabled: boolean) => Promise<void>
  executeTask: (id: string) => Promise<void>
  stopTask: (id: string) => Promise<void>

  // 日志管理
  fetchTaskLogs: (taskId: string, limit?: number) => Promise<void>
  fetchAllLogs: (limit?: number) => Promise<void>
  clearTaskLogs: (taskId: string) => Promise<void>
  clearAllLogs: () => Promise<void>

  // 统计信息
  fetchStatistics: () => Promise<void>
}

export const useScheduledTaskStore = create<ScheduledTaskStore>((set) => ({
  tasks: [],
  logs: [],
  statistics: null,
  loading: false,
  error: null,

  fetchTasks: async () => {
    set({ loading: true, error: null })
    try {
      const response = requireResponse(await scheduledTaskApi.list())
      set({ tasks: response.data, loading: false })
    } catch (error: any) {
      set({ error: error.message, loading: false })
    }
  },

  createTask: async (task) => {
    set({ loading: true, error: null })
    try {
      const response = requireResponse(await scheduledTaskApi.create(task))
      const newTask = response.data
      set(state => ({
        tasks: [...state.tasks, newTask],
        loading: false
      }))
      return newTask
    } catch (error: any) {
      set({ error: error.message, loading: false })
      throw error
    }
  },

  updateTask: async (id, updates) => {
    set({ loading: true, error: null })
    try {
      const response = requireResponse(await scheduledTaskApi.update(id, updates))
      const updatedTask = response.data
      set(state => ({
        tasks: state.tasks.map(t => t.id === id ? updatedTask : t),
        loading: false
      }))
      return updatedTask
    } catch (error: any) {
      set({ error: error.message, loading: false })
      throw error
    }
  },

  deleteTask: async (id) => {
    set({ loading: true, error: null })
    try {
      requireResponse(await scheduledTaskApi.delete(id))
      set(state => ({
        tasks: state.tasks.filter(t => t.id !== id),
        loading: false
      }))
    } catch (error: any) {
      set({ error: error.message, loading: false })
      throw error
    }
  },

  toggleTask: async (id, enabled) => {
    try {
      const response = requireResponse(await scheduledTaskApi.toggle(id, enabled))
      set(state => ({
        tasks: state.tasks.map(t => t.id === id ? response.data : t)
      }))
    } catch (error: any) {
      set({ error: error.message })
      throw error
    }
  },

  executeTask: async (id) => {
    const commandId = pendingExecutionCommands.get(id) || crypto.randomUUID()
    pendingExecutionCommands.set(id, commandId)
    try {
      requireResponse(await scheduledTaskApi.execute(id, commandId))
      pendingExecutionCommands.delete(id)
      // 标记任务为执行中
      set(state => ({
        tasks: state.tasks.map(t => t.id === id ? { ...t, is_running: true } : t)
      }))
    } catch (error: any) {
      try {
        requireResponse(await scheduledTaskApi.getCommand(commandId))
        pendingExecutionCommands.delete(id)
        set(state => ({
          tasks: state.tasks.map(t => t.id === id ? { ...t, is_running: true } : t)
        }))
        return
      } catch {
        // Keep the stable command id so a later retry cannot start a duplicate run.
      }
      set({ error: error.message })
      throw error
    }
  },

  stopTask: async (id) => {
    try {
      requireResponse(await scheduledTaskApi.stop(id))
      // 标记任务为未执行
      set(state => ({
        tasks: state.tasks.map(t => t.id === id ? { ...t, is_running: false } : t)
      }))
    } catch (error: any) {
      set({ error: error.message })
      throw error
    }
  },

  fetchTaskLogs: async (taskId, limit = 100) => {
    set({ loading: true, error: null })
    try {
      const response = requireResponse(await scheduledTaskApi.getTaskLogs(taskId, limit))
      set({ logs: response.data, loading: false })
    } catch (error: any) {
      set({ error: error.message, loading: false })
    }
  },

  fetchAllLogs: async (limit = 100) => {
    set({ loading: true, error: null })
    try {
      const response = requireResponse(await scheduledTaskApi.getAllLogs(limit))
      set({ logs: response.data, loading: false })
    } catch (error: any) {
      set({ error: error.message, loading: false })
    }
  },

  clearTaskLogs: async (taskId) => {
    try {
      requireResponse(await scheduledTaskApi.clearTaskLogs(taskId))
      set(state => ({
        logs: state.logs.filter(log => log.task_id !== taskId)
      }))
    } catch (error: any) {
      set({ error: error.message })
      throw error
    }
  },

  clearAllLogs: async () => {
    try {
      requireResponse(await scheduledTaskApi.clearAllLogs())
      set({ logs: [] })
    } catch (error: any) {
      set({ error: error.message })
      throw error
    }
  },

  fetchStatistics: async () => {
    try {
      const response = requireResponse(await scheduledTaskApi.getStatistics())
      set({ statistics: response.data })
    } catch (error: any) {
      set({ error: error.message })
    }
  }
}))
