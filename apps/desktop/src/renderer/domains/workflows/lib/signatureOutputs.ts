// Read-only summary of what a flow hands back (End result and record write-backs); configured in the nodes themselves.
type GraphNode = { id: string; data?: unknown }
export interface FlowOutput { id: string; kind: 'result' | 'write'; node: string; text: string }

const WRITES: Record<string, string> = { createRecord: '新增记录', updateRecord: '更新记录', deleteRecord: '删除记录', setRecordStatus: '设置记录状态' }
const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)

export function describeFlowOutputs(nodes: GraphNode[]): FlowOutput[] {
  const items: FlowOutput[] = []
  for (const { id, data } of nodes) {
    if (!isRecord(data)) continue
    const config = isRecord(data.config) ? { ...data, ...data.config } : data
    const node = String(data.label || data.name || (data.moduleType === 'project_end' ? '结束' : '数据操作'))
    if (data.moduleType === 'project_end') {
      items.push({ id, kind: 'result', node, text: `业务结果：${config.businessResult === 'failed' ? '失败' : '成功'}${config.retainEnvironment === true ? '；保留当前登录状态' : ''}` })
    } else if (data.moduleType === 'project_data' && WRITES[String(config.operation)]) {
      items.push({ id, kind: 'write', node, text: WRITES[String(config.operation)] })
    }
  }
  return items
}
