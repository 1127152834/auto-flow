import type { ScheduledTask, ScheduledTaskExecutionLog } from '../hooks/stores/scheduledTaskStore'
const key = 'autoflow:studio:mock:scheduled-tasks:v1'
interface Data { tasks: ScheduledTask[]; logs: ScheduledTaskExecutionLog[] }
const read = (): Data => JSON.parse(localStorage.getItem(key) || '{"tasks":[],"logs":[]}')
const save = (data: Data) => localStorage.setItem(key, JSON.stringify(data))
const fail = (error: string, status = 400) => Response.json({ success: false, error }, { status })
export function finishScheduledFixture(id: string, status: string, executed: number) {
  const data = read(), task = data.tasks.find(task => `scheduled-${task.id}` === id)
  if (!task) return
  const log = data.logs.find(log => log.task_id === task.id && log.status === 'running')
  task.is_running = false
  if (log) {
    log.status = status === 'completed' ? 'success' : status === 'failed' ? 'failed' : 'stopped'
    log.end_time = new Date().toISOString()
    log.duration = (Date.now() - Date.parse(log.start_time)) / 1000
    log.executed_nodes = executed
    task.total_executions++
    if (log.status === 'success') task.success_executions++
    if (log.status === 'failed') task.failed_executions++
    if (log.status !== 'stopped') task.last_execution_status = log.status
    task.last_execution_time = log.end_time
  }
  save(data)
}
export async function mockScheduledRequest(path: string, method: string, query: URLSearchParams, body: Record<string, unknown>, hooks: {
  start: (task: ScheduledTask) => Promise<Response>
  stop: (task: ScheduledTask) => Promise<Response>
}): Promise<Response | undefined> {
  if (!path.startsWith('/scheduled-tasks')) return undefined
  const data = read()
  const json = (value: unknown) => Response.json(value)
  if (path === '/scheduled-tasks/list' && method === 'GET') return json(data.tasks)
  if (path === '/scheduled-tasks/statistics/summary' && method === 'GET') {
    const total = data.tasks.reduce((sum, task) => sum + task.total_executions, 0)
    const success = data.tasks.reduce((sum, task) => sum + task.success_executions, 0)
    return json({ total_tasks: data.tasks.length, enabled_tasks: data.tasks.filter(task => task.enabled).length, disabled_tasks: data.tasks.filter(task => !task.enabled).length,
      total_executions: total, success_executions: success, failed_executions: data.tasks.reduce((sum, task) => sum + task.failed_executions, 0), success_rate: total ? success / total * 100 : 0,
      trigger_types: Object.fromEntries(['time', 'hotkey', 'startup', 'webhook'].map(type => [type, data.tasks.filter(task => task.trigger.type === type).length])) })
  }
  const match = path.match(/^\/scheduled-tasks\/([^/]+)(?:\/(toggle|execute|stop|logs|all))?$/)
  const id = match?.[1], action = match?.[2]
  if (action === 'logs' || (id === 'logs' && action === 'all')) {
    const taskId = id === 'logs' ? undefined : id
    if (taskId && !data.tasks.some(task => task.id === taskId)) return fail('Task not found', 404)
    if (method === 'DELETE') { data.logs = data.logs.filter(log => taskId ? log.task_id !== taskId : false); save(data); return json({ success: true }) }
    if (method === 'GET') {
      const limit = Number(query.get('limit') || 100)
      if (!Number.isInteger(limit) || limit < 1 || limit > 10000) return fail('Invalid log limit')
      return json(data.logs.filter(log => !taskId || log.task_id === taskId).slice(0, limit))
    }
  }
  const task = data.tasks.find(task => task.id === id)
  if (path === '/scheduled-tasks' && method === 'POST' || task && !action && method === 'PUT') {
    const next = { ...task, ...body } as ScheduledTask
    if (typeof next.name !== 'string' || !next.name.trim() || typeof next.workflow_id !== 'string' || !next.workflow_id || !next.trigger || !['time', 'hotkey', 'startup', 'webhook'].includes(next.trigger.type)) return fail('Task name, workflow and valid trigger required', 422)
    if (task?.is_running) return fail('Stop the task before editing', 409)
    next.id = task?.id || crypto.randomUUID()
    next.name = next.name.trim()
    next.created_at = task?.created_at || new Date().toISOString()
    next.updated_at = new Date().toISOString()
    next.total_executions = task?.total_executions || 0
    next.success_executions = task?.success_executions || 0
    next.failed_executions = task?.failed_executions || 0
    next.is_running = false
    // The protocol fixture stores configuration shape, not notification credentials.
    next.notify_channels = (next.notify_channels || []).map(channel => ({ ...channel, password: '', secret: '', access_token: '', key: '', sendkey: '' }))
    data.tasks = [...data.tasks.filter(row => row.id !== next.id), next]
    save(data); return json(next)
  }
  if (!task) return fail('Task not found', 404)
  if (!action && method === 'GET') return json(task)
  if (!action && method === 'DELETE') {
    if (task.is_running) return fail('Stop the task before deleting', 409)
    data.tasks = data.tasks.filter(row => row.id !== id); save(data); return json({ success: true })
  }
  if (action === 'toggle' && method === 'POST') {
    if (typeof body.enabled !== 'boolean') return fail('enabled must be boolean', 422)
    task.enabled = body.enabled; save(data); return json({ success: true, enabled: task.enabled })
  }
  if (action === 'execute' && method === 'POST') {
    if (task.is_running) return fail('Task is already running', 409)
    const previous = structuredClone(data)
    task.is_running = true
    const now = new Date().toISOString()
    data.logs.unshift({ id: crypto.randomUUID(), task_id: task.id, task_name: task.name, workflow_id: task.workflow_id, workflow_name: task.workflow_name || '', start_time: now, trigger_time: now, trigger_type: 'manual', status: 'running', executed_nodes: 0, failed_nodes: 0, collected_data_count: 0 })
    save(data)
    try {
      const result = await hooks.start(task)
      if (!result.ok) { save(previous); return result }
      return json({ success: true, mock: true })
    } catch (error) { save(previous); throw error }
  }
  if (action === 'stop' && method === 'POST') return hooks.stop(task)
  return fail('Unsupported scheduled task operation', 405)
}
