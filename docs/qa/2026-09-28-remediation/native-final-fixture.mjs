// Fixture setup through production APIs only; subsequent editing is native CUA.
import assert from 'node:assert/strict'
import { randomUUID, createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { connectCdp } from '../../../scripts/electron-cdp.mjs'

const sessionPath = process.argv[2]
assert.ok(sessionPath, 'Provide the dedicated native QA session.json')
const session = JSON.parse(await readFile(sessionPath, 'utf8'))
assert.ok(session.workspace.endsWith('/autoflow-packaged-end-DFc1th'), 'Only this task-owned workspace is allowed')
const targets = await (await fetch(`${session.debugOrigin}/json/list`)).json()
const main = targets.find(target => /\/index\.html/.test(target.url))
assert.ok(main)
const cdp = await connectCdp(main.webSocketDebuggerUrl)
let service
try { service = (await cdp.evaluate('window.autoflow.getRuntimeContext()')).sidecar } finally { cdp.close() }
assert.equal(service.state, 'ready')
async function api(path, body, status = 200, prefix = '/api/v1') {
  const response = await fetch(`${service.baseUrl}${prefix}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'x-autoflow-token': service.token, 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(20_000),
  })
  const value = await response.json()
  assert.equal(response.status, status, JSON.stringify(value))
  return value
}
const projectId = '557fd0e0-4b23-46ca-a1fa-c8733a7f25b8'
const prefix = `/projects/${projectId}`
const sourceBytes = await readFile(new URL('../../../README.md', import.meta.url))
const source = { path: 'README.md', bytes: sourceBytes.length, sha256: createHash('sha256').update(sourceBytes).digest('hex') }
const table = await api(`${prefix}/tables`, { name: '最终 UI 真实仓库文件核验' }, 201)
const base = `${prefix}/tables/${table.tableId}`
const field = await api(`${base}/fields`, { definition: { key: 'repository_file', name: '真实仓库文件', type: 'string', required: false, validation: {} }, sourceColumnPolicy: 'localOnly', expectedTableRevision: 1 })
const record = await api(`${base}/records`, { datasetGeneration: table.datasetGeneration, values: [{ fieldId: field.field.ref.fieldId, value: JSON.stringify(source) }] }, 201)
assert.equal(record.ref.projectId, projectId)
assert.ok(record.ref.datasetGeneration && record.ref.recordKey)
const nodes = [
  { id: 'end', type: 'moduleNode', position: { x: 40, y: 50 }, data: { moduleType: 'project_end', label: '静态目标验收', config: { retainEnvironment: true, name: '最终 UI 保留环境', inputIds: [], recordTargets: [record.ref] } } },
  { id: 'nested-call', type: 'moduleNode', position: { x: 40, y: 190 }, data: { moduleType: 'subflow', label: '子流程选择验收', subflowGroupId: 'stale-outer', subflowName: '外层调用旧名', config: { subflowGroupId: '', subflowName: '' } } },
  { id: 'nested-definition', type: 'groupNode', position: { x: 360, y: 50 }, style: { width: 250, height: 150 }, data: { moduleType: 'group', label: '嵌套定义', isSubflow: false, subflowName: '外层过期名', config: { isSubflow: true, subflowName: '嵌套有效名' } } },
  { id: 'stale-definition', type: 'groupNode', position: { x: 360, y: 250 }, style: { width: 250, height: 150 }, data: { moduleType: 'group', label: '普通分组', isSubflow: true, subflowName: '外层误列名', config: { isSubflow: false, subflowName: '内层非子流程' } } },
]
const workflow = await api('/workflows', { id: randomUUID(), clientRequestId: randomUUID(), projectId, name: '最终配置一致性原生验收', nodes, edges: [], variables: [] }, 201, '/api')
const original = await api(`${prefix}/automations/b98c5949-80f7-410d-8d40-db6247451c8d`)
const automation = await api(`${prefix}/automations`, { name: '最终配置一致性验收', description: '本次专属；编辑保存验收，不启动无记录租约的静态目标', workflowId: workflow.id, inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: original.environmentPolicy, runPolicy: original.runPolicy }, 201)
await writeFile(join(dirname(sessionPath), 'fixture.json'), JSON.stringify({ source, projectId, table, record, workflow, automation, createdAt: new Date().toISOString(), scope: 'Real persisted configuration acceptance; no execution or record lease is claimed' }, null, 2), { flag: 'wx' })
console.log(JSON.stringify({ workflowId: workflow.id, automationId: automation.automationId, recordRef: record.ref }))
