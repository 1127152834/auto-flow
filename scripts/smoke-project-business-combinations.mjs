import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { createServer } from 'node:http'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { installRuntimeKernel, projectSmokeOptions } from './smoke-project-management.mjs'
import { assertOutsideHistory } from './project-smoke-output.mjs'
import { stop, waitForReady } from './smoke-sidecar.mjs'

// Packaged business combinations using production HTTP and real workers.
// Passed assertions cover the declared concurrent scenario, not Sheets or native UI acceptance.
export async function checkBusinessCombinations(baseUrl, token, browserVersion) {
  async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
    const response = await fetch(baseUrl + path, { method, headers: { 'x-autoflow-token': token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(60_000) })
    const value = await response.json()
    assert.ok(response.ok, `${method} ${path}: ${response.status} ${JSON.stringify(value)}`)
    return value
  }
  const node = (id, moduleType, config) => ({ id, type: moduleType, position: { x: 100, y: 100 }, data: { moduleType, ...config } })
  const project = await api('/api/v1/projects', { name: 'PM9 业务组合补证' })
  const prefix = `/api/v1/projects/${project.projectId}`
  const profile = await api('/api/v1/profiles', { name: 'PM9 业务组合浏览器', browserVersion, headless: true })
  const environment = { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }
  const runPolicy = { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 120, manualDeadlineSeconds: 120 }
  const end = () => node('end', 'project_end', { retainEnvironment: { enabled: false } })
  async function table(name, key = 'code') {
    const table = await api(`${prefix}/tables`, { name, sourceKind: 'local' })
    const field = (await api(`${prefix}/tables/${table.tableId}/fields`, { definition: { key, name: '编号', type: 'string', required: false, validation: {} }, sourceColumnPolicy: 'localOnly', expectedTableRevision: 1 })).field
    return { ...table, fieldId: field.ref.fieldId }
  }
  const grant = (table, operation) => ({ tableId: table.tableId, datasetGeneration: table.datasetGeneration, operations: [operation], fieldIds: [table.fieldId], readPurposes: ['condition', 'derivedWrite'] })
  const data = (id, table, operation, args) => node(id, 'project_data', { operation, variableName: id, tableGrant: grant(table, operation), arguments: args })
  const records = table => api(`${prefix}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)
  const create = (table, value) => api(`${prefix}/tables/${table.tableId}/records`, { datasetGeneration: table.datasetGeneration, values: [{ fieldId: table.fieldId, value }] })
  async function workflow(name, nodes) {
    return api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name, variables: [], nodes, edges: nodes.slice(1).map((n, i) => ({ id: randomUUID(), source: nodes[i].id, target: n.id })) })
  }
  const automations = new Map()
  async function start(flow, inputPlan = { inputs: [] }, environmentPolicy = environment, policy = runPolicy) {
    const automation = automations.get(flow.id) ?? await api(prefix + '/automations', { name: randomUUID(), description: '', workflowId: flow.id, inputPlan, parameterSchema: [], environmentPolicy, runPolicy: policy })
    automations.set(flow.id, automation)
    const validation = await api(`${prefix}/automations/${automation.automationId}/validation`)
    assert.equal(validation.runnable, true, JSON.stringify(validation))
    const accepted = await api(`${prefix}/automations/${automation.automationId}/batches`, { expectedAutomationRevision: automation.managementRevision, parameters: {}, maxTasks: policy.maxTasks, concurrency: policy.concurrency })
    return accepted.operation.result.batch.batchId
  }
  async function wait(check, label) {
    for (let i = 0; i < 480; i++) {
      const result = await check()
      if (result) return result
      await new Promise(resolveWait => setTimeout(resolveWait, 250))
    }
    throw new Error(`Timeout: ${label}`)
  }
  async function completed(batchId, expectedStatus = 'succeeded') {
    const state = await wait(async () => {
      const value = await api(`${prefix}/batches/${batchId}`)
      return ['completed', 'failed', 'interrupted', 'stopped'].includes(value.batch.status) && value
    }, 'terminal batch')
    const task = (await api(`${prefix}/tasks?batchId=${batchId}`)).items[0]
    const attempts = await api(`${prefix}/tasks/${task.taskId}/node-attempts`)
    assert.equal(state.statusCounts[expectedStatus], 1, JSON.stringify({ state, attempts }))
    return { task, attempts: attempts.items }
  }
  async function sharedPersonChain() {
    const server = createServer((request, response) => {
      if (request.url === '/login') response.setHeader('Set-Cookie', 'pm9=registered; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax')
      response.setHeader('Content-Type', 'text/html; charset=utf-8')
      response.end(`<output id="auth">${request.headers.cookie?.includes('pm9=registered') ? 'signed-in' : 'signed-out'}</output>`)
    })
    await new Promise(resolveListen => server.listen(0, '127.0.0.1', resolveListen))
    const site = `http://127.0.0.1:${server.address().port}`
    try {
      const person = await table('共享人员', 'personNo'), email = await table('消耗邮箱'), account = await table('新建账号', 'personNo')
      const p1 = await create(person, 'P001'), e1 = await create(email, 'e1@example.invalid')
      const makeStatus = (table, name, revision) => api(`${prefix}/tables/${table.tableId}/statuses`, { name, color: '#123456', order: revision, expectedTableRevision: revision })
      const verified = await makeStatus(person, '已核验', 2), pending = await makeStatus(email, '待使用', 2), registered = await makeStatus(email, '已注册', 3)
      const setInitial = (table, row, statusId) => api(`${prefix}/tables/${table.tableId}/records/${Buffer.from(row.ref.recordKey.value).toString('base64url')}/status`, { datasetGeneration: table.datasetGeneration, recordKeyType: row.ref.recordKey.type, statusId, expectedStatusRevision: row.statusRevision }, 'PUT')
      await setInitial(person, p1, verified.statusId)
      await setInitial(email, e1, pending.statusId)
      const fieldRef = table => ({ projectId: project.projectId, tableId: table.tableId, datasetGeneration: table.datasetGeneration, fieldId: table.fieldId })
      const input = (table, alias, statusId) => ({ inputId: randomUUID(), alias, tableId: table.tableId, datasetGeneration: table.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: alias, fieldRef: fieldRef(table) }], filter: statusId ? { type: 'status', operator: 'eq', statusId } : { type: 'all', items: [] }, orderBy: [{ systemField: 'recordKey', direction: 'asc' }] })
      const readInputs = () => node('inputs', 'project_data', { operation: 'inputs', variableName: 'frozen', arguments: {} })
      const personSetup = await workflow('人员已有独立环境', [readInputs(), node('open', 'open_page', { url: site + '/login' }), node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: '人员原环境', recordTargets: [{ recordRef: "{frozen[0]['recordRef']}", expectedLinkRevision: "{frozen[0]['linkRevision']}", replaceAllowed: false }] } })])
      await completed(await start(personSetup, { inputs: [input(person, '人员', verified.statusId)] }))
      const beforePerson = (await records(person)).items[0]
      assert.ok(beforePerson.currentEnvironmentId, 'person must begin with an existing environment association')
      const firstInputs = { inputs: [input(person, '人员', verified.statusId), input(email, '邮箱', pending.statusId)] }
      const registration = await workflow('共享人员注册新账号', [
        readInputs(), node('login', 'open_page', { url: site + '/login' }),
        data('register', email, 'setRecordStatus', { recordRef: "{frozen[1]['recordRef']}", statusId: registered.statusId, expectedStatusRevision: "{frozen[1]['statusRevision']}", expectedContentRevisionWhenDerived: "{frozen[1]['contentRevision']}" }),
        data('account', account, 'createRecord', { tableId: account.tableId, datasetGeneration: account.datasetGeneration, values: { [account.fieldId]: "{frozen[0]['values'][0]['value']}" } }),
        node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: '邮箱账号共享登录', recordTargets: [{ recordRef: "{frozen[1]['recordRef']}", expectedLinkRevision: "{frozen[1]['linkRevision']}", replaceAllowed: false }, { recordRef: "{account['ref']}", expectedLinkRevision: "{account['linkRevision']}", replaceAllowed: false }] } }),
      ])
      const registeredTask = await completed(await start(registration, firstInputs))
      const accounts = await records(account), emails = await records(email)
      assert.equal(accounts.total, 1)
      const a1 = accounts.items[0], savedEmail = emails.items[0]
      assert.equal(a1.values[0].value, 'P001')
      assert.equal(savedEmail.statusId, registered.statusId)
      assert.ok(a1.currentEnvironmentId)
      assert.equal(savedEmail.currentEnvironmentId, a1.currentEnvironmentId)
      assert.notEqual(a1.currentEnvironmentId, beforePerson.currentEnvironmentId)
      const exhaustedBatch = await start(registration, firstInputs)
      await wait(async () => (await api(`${prefix}/batches/${exhaustedBatch}`)).batch.status === 'completed', 'consumed email no longer matches original filter')
      assert.equal((await api(`${prefix}/tasks?batchId=${exhaustedBatch}`)).total, 0)
      assert.equal((await records(account)).total, 1, 'empty input selection must not create another account')
      const accountInput = input(account, '账号'), personInput = input(person, '关联人员', verified.statusId)
      personInput.mode = 'related'
      personInput.relation = { type: 'fieldEquals', sourceInputId: accountInput.inputId, sourceFieldRef: fieldRef(account), targetFieldRef: fieldRef(person) }
      const restore = await workflow('按账号环境和人员编号继续', [readInputs(), node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#auth', attribute: 'text', variableName: 'login' }), end()])
      const restoredTask = await completed(await start(restore, { inputs: [accountInput, personInput] }, { source: 'inputEnvironment', inputId: accountInput.inputId, proxyOverride: { mode: 'none' }, modelProviderId: null }))
      const detail = await api(`${prefix}/tasks/${restoredTask.task.taskId}`)
      assert.deepEqual(detail.inputSnapshot.inputs.map(item => item.recordRef), [a1.ref, p1.ref])
      assert.equal(detail.run.resourceRequest.profileId, profile.id, 'restore must freeze the selected environment profile')
      const outputs = await api(`${prefix}/tasks/${restoredTask.task.taskId}/outputs`)
      assert.equal(outputs.items.find(output => output.name === 'login')?.value, 'signed-in')
      const afterPerson = (await records(person)).items[0]
      for (const key of ['values', 'statusId', 'currentEnvironmentId', 'contentRevision', 'statusRevision', 'linkRevision']) assert.deepEqual(afterPerson[key], beforePerson[key], `shared person ${key} must remain unchanged`)
      return { status: 'passed', checks: ['P1 verified state/content/environment link and revisions unchanged across both Tasks', 'E1 explicitly registered and excluded from original pending selection; retry batch creates no Task/account', 'Exactly one new A1 and E1 link the same saved login environment', 'Next Task starts from A1 input environment, restores cookie, and selects P1 through personNo field equality'], taskIds: [registeredTask.task.taskId, restoredTask.task.taskId], environmentId: a1.currentEnvironmentId, scope: `${process.platform}/${process.arch} packaged public HTTP and actual worker/browser; no full native UI flow or live Sheets claim` }
    } finally {
      await new Promise((resolveClose, reject) => server.close(error => error ? reject(error) : resolveClose()))
    }
  }
  async function concurrentRecordClaims() {
    const server = createServer((request, response) => {
      if (request.url.startsWith('/set/')) response.setHeader('Set-Cookie', `owner=${request.url.slice(5)}; Path=/; HttpOnly`)
      response.setHeader('Content-Type', 'text/html; charset=utf-8')
      response.end(`<output id="owner">${request.headers.cookie ?? 'missing'}</output>`)
    })
    await new Promise(resolveListen => server.listen(0, '127.0.0.1', resolveListen))
    const site = `http://127.0.0.1:${server.address().port}`
    try {
      const source = await table('同批次并发来源')
      await create(source, 'first'); await create(source, 'second')
      const inputPlan = { inputs: [{ inputId: randomUUID(), alias: 'owner', tableId: source.tableId, datasetGeneration: source.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: 'owner', fieldRef: { projectId: project.projectId, tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldId: source.fieldId } }], filter: { type: 'all', items: [] }, orderBy: [{ systemField: 'recordKey', direction: 'asc' }] }] }
      const flow = await workflow('同来源 Profile 的两个隔离浏览器', [node('inputs', 'project_data', { operation: 'inputs', variableName: 'frozen', arguments: {} }), node('open', 'open_page', { url: site + "/set/{frozen[0]['values'][0]['value']}" }), node('manual', 'project_manual', { reason: '确认两个现场均已启动', timeoutSeconds: 120 }), node('check', 'open_page', { url: site + '/check' }), node('cookie', 'get_element_info', { selector: '#owner', attribute: 'text', variableName: 'ownedCookie' }), end()])
      const batch = await start(flow, inputPlan, environment, { ...runPolicy, maxTasks: 2, concurrency: 2, maxLiveInstances: 2 })
      const waiting = await wait(async () => {
        const tasks = (await api(`${prefix}/tasks?batchId=${batch}`)).items
        const items = (await api(prefix + '/manual-items')).items.filter(item => item.status === 'waiting' && tasks.some(task => task.taskId === item.taskId))
        return items.length === 2 && { tasks, items }
      }, 'two real data Tasks concurrently waiting')
      assert.equal(waiting.tasks.length, 2)
      const details = await Promise.all(waiting.tasks.map(task => api(`${prefix}/tasks/${task.taskId}`)))
      assert.equal(new Set(details.map(detail => detail.inputSnapshot.inputs[0].recordRef.recordKey.value)).size, 2, 'concurrent claims must not lease the same record')
      assert.equal(new Set(details.map(detail => detail.run.runId)).size, 2)
      for (const [index, item] of waiting.items.entries()) {
        await api(`${prefix}/manual-items/${item.manualItemId}/resume`, { checkpointRevision: item.checkpointRevision, expectedStatusRevision: item.statusRevision })
        await wait(async () => (await api(`${prefix}/tasks/${item.taskId}`)).task.status === 'succeeded', 'one data Task completed')
        if (index === 0) assert.equal((await api(`${prefix}/tasks/${waiting.items[1].taskId}`)).run.status, 'waiting_manual')
      }
      const final = await wait(async () => {
        const value = await api(`${prefix}/batches/${batch}`)
        return value.batch.status === 'completed' && value
      }, 'concurrent data batch complete')
      assert.equal(final.statusCounts.succeeded, 2)
      assert.equal((await api(`${prefix}/tasks?batchId=${batch}`)).items.length, 2, 'maxTasks must prevent a third claim')
      for (const detail of details) {
        const outputs = (await api(`${prefix}/tasks/${detail.task.taskId}/outputs`)).items
        const expected = detail.inputSnapshot.inputs[0].values[0].value
        assert.equal(outputs.find(output => output.name === 'ownedCookie')?.value, `owner=${expected}`)
      }
      return { status: 'passed', taskIds: waiting.tasks.map(task => task.taskId), checks: ['One data batch reaches two simultaneous manual checkpoints with distinct leased records', 'Same source Profile produces isolated cookie stores', 'Completing the first Task keeps the second live; both finish once and no third Task is claimed'] }
    } finally { await new Promise((resolveClose, reject) => server.close(error => error ? reject(error) : resolveClose())) }
  }
  const source = await table('旧契约数据'), target = await table('运行中新建记录')
  const first = await create(source, 'row-1'), second = await create(source, 'row-2')
  const status = await api(`${prefix}/tables/${source.tableId}/statuses`, { name: '已提交', color: '#123456', order: 0, expectedTableRevision: 2 })
  const query = (value) => data('query', source, 'queryRecords', { tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldIds: [source.fieldId], readPurpose: 'derivedWrite', filter: { type: 'compare', fieldId: source.fieldId, operator: 'eq', value }, orderBy: [], cursor: null, limit: 10 })
  const update = value => data('update', source, 'updateRecord', { recordRef: "{query['items'][0]['ref']}", changes: { [source.fieldId]: value }, expectedContentRevision: "{query['items'][0]['contentRevision']}" })
  const old = await start(await workflow('T2 先准备旧字段契约', [node('open', 'open_page', { url: 'about:blank' }), node('manual', 'project_manual', { reason: '等待另一个任务完成兼容加列', timeoutSeconds: 120 }), query('row-2'), update('old-contract-written'), end()]))
  const checkpoint = await wait(async () => {
    const tasks = (await api(`${prefix}/tasks?batchId=${old}`)).items
    const items = (await api(prefix + '/manual-items')).items
    return items.find(item => item.status === 'waiting' && tasks.some(task => task.taskId === item.taskId))
  }, 'old prepared task checkpoint')
  const cancelledBatch = await start(await workflow('取消一个 Run 不停止另一个人工现场', [node('open', 'open_page', { url: 'about:blank' }), node('manual', 'project_manual', { reason: '将取消此 Run', timeoutSeconds: 120 }), data('unexpected-write', target, 'createRecord', { tableId: target.tableId, datasetGeneration: target.datasetGeneration, values: { [target.fieldId]: 'must-not-execute' } }), end()]))
  const cancelledManual = await wait(async () => {
    const tasks = (await api(`${prefix}/tasks?batchId=${cancelledBatch}`)).items
    return (await api(prefix + '/manual-items')).items.find(item => item.status === 'waiting' && tasks.some(task => task.taskId === item.taskId))
  }, 'second independent manual owner before cancellation')
  const beforeStop = await api(`${prefix}/batches/${cancelledBatch}`)
  await api(`${prefix}/batches/${cancelledBatch}/stop`, { expectedStatusRevision: beforeStop.batch.statusRevision, reason: '核对 Run 取消隔离' })
  await wait(async () => (await api(`${prefix}/batches/${cancelledBatch}`)).batch.status === 'stopped', 'owned cancellation cleanup')
  assert.equal((await api(`${prefix}/manual-items/${cancelledManual.manualItemId}`)).status, 'cancelled')
  assert.equal((await api(`${prefix}/tasks/${checkpoint.taskId}`)).run.status, 'waiting_manual')
  assert.equal((await records(target)).total, 0, 'cancelled Run must not execute later write')
  const addedFieldId = randomUUID()
  const newer = await start(await workflow('T1 运行中加列增行并写状态', [
    node('open', 'open_page', { url: 'about:blank' }),
    data('ensure', source, 'ensureField', { tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldId: addedFieldId, definition: { key: 'receipt', name: '回执', type: 'string', required: false, validation: {} }, hasDefault: false, default: null, expectedTableRevision: 3 }),
    data('reuse', source, 'ensureField', { tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldId: randomUUID(), definition: { key: 'receipt', name: '回执', type: 'string', required: false, validation: {} }, hasDefault: false, default: null, expectedTableRevision: 4 }),
    data('create', target, 'createRecord', { tableId: target.tableId, datasetGeneration: target.datasetGeneration, values: { [target.fieldId]: 'created-by-T1' } }),
    query('row-1'), update('new-task-written'),
    data('status', source, 'setRecordStatus', { recordRef: "{query['items'][0]['ref']}", statusId: status.statusId, expectedStatusRevision: "{query['items'][0]['statusRevision']}", expectedContentRevisionWhenDerived: "{update['contentRevision']}" }), end(),
  ]))
  const t2WaitingBefore = await api(`${prefix}/tasks/${checkpoint.taskId}`)
  assert.equal(t2WaitingBefore.run.status, 'waiting_manual')
  const overlapStartedAt = new Date().toISOString()
  const t1 = await completed(newer)
  const t1CompletedAt = new Date().toISOString()
  const t2WaitingAfter = await api(`${prefix}/tasks/${checkpoint.taskId}`)
  assert.equal(t2WaitingAfter.run.status, 'waiting_manual', 'T1 must finish while old-contract T2 is still suspended')
  assert.equal((await api(`${prefix}/manual-items/${checkpoint.manualItemId}`)).status, 'waiting')
  assert.notEqual(t1.task.runId, t2WaitingAfter.run.runId)
  const t1Outputs = (await api(`${prefix}/tasks/${t1.task.taskId}/outputs`)).items
  const ensured = t1Outputs.find(output => output.name === 'ensure').value
  const reused = t1Outputs.find(output => output.name === 'reuse').value
  assert.equal(ensured.created, true)
  assert.equal(reused.created, false)
  assert.deepEqual(reused.field.ref, ensured.field.ref)
  assert.equal(reused.tableRevision, ensured.tableRevision, 'identical ensure must not advance schema revision')
  const beforeConflict = { fields: await api(`${prefix}/tables/${source.tableId}/fields`), rows: await records(source) }
  const conflicting = await completed(await start(await workflow('异型同键不得覆盖回执字段', [
    node('open', 'open_page', { url: 'about:blank' }),
    data('conflict', source, 'ensureField', { tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldId: randomUUID(), definition: { key: 'receipt', name: '回执', type: 'number', required: false, validation: {} }, hasDefault: false, default: null, expectedTableRevision: ensured.tableRevision }), end(),
  ])), 'failed')
  assert.equal(conflicting.attempts.find(attempt => attempt.nodeId === 'conflict').error.code, 'FIELD_DEFINITION_CONFLICT')
  assert.equal(conflicting.attempts.some(attempt => attempt.nodeId === 'end'), false)
  assert.deepEqual(await api(`${prefix}/tables/${source.tableId}/fields`), beforeConflict.fields)
  assert.deepEqual(await records(source), beforeConflict.rows)
  assert.equal((await api(`${prefix}/tasks/${checkpoint.taskId}`)).run.status, 'waiting_manual')
  await api(`${prefix}/manual-items/${checkpoint.manualItemId}/resume`, { checkpointRevision: checkpoint.checkpointRevision, expectedStatusRevision: checkpoint.statusRevision })
  const t2 = await completed(old)
  const fields = await api(`${prefix}/tables/${source.tableId}/fields`)
  assert.equal(fields.items.filter(field => field.ref.fieldId === addedFieldId && field.key === 'receipt').length, 1)
  assert.equal(fields.items.filter(field => field.key === 'receipt').length, 1)
  const created = await records(target)
  assert.equal(created.total, 1, 'createRecord must have exactly one effect')
  assert.equal(created.items[0].values[0].value, 'created-by-T1')
  const rows = (await records(source)).items
  const row = original => rows.find(item => item.ref.recordKey.value === original.ref.recordKey.value)
  assert.equal(row(first).values.find(value => value.fieldId === source.fieldId).value, 'new-task-written')
  assert.equal(row(first).statusId, status.statusId)
  assert.equal(row(second).values.find(value => value.fieldId === source.fieldId).value, 'old-contract-written')
  assert.equal(row(second).statusId, null)
  assert.equal(t2.attempts.filter(attempt => attempt.nodeId === 'manual').length, 1)
  return {
    projectId: project.projectId,
    sharedPersonChain: await sharedPersonChain(),
    concurrentRecordClaims: await concurrentRecordClaims(),
    checks: ['Cancelling a second live Run preserves T2 checkpoint/browser and executes no cancelled write', 'T1 started and completed while old-contract T2 remained waiting_manual in its original Run', 'T1 ensured a persistent field, created exactly one second-table record, queried/updated content and explicitly set status before T2 resumed', 'T2 then queried and wrote using its prepared old field contract; manual node executed once'],
    taskIds: [t1.task.taskId, t2.task.taskId],
    schemaEnsure: { status: 'passed', createdFieldRef: ensured.field.ref, reusedFieldRef: reused.field.ref, tableRevision: ensured.tableRevision, conflictingTaskId: conflicting.task.taskId, conflictCode: 'FIELD_DEFINITION_CONFLICT', checks: ['same-definition ensure returns the original field ID without another column or schema revision', 'another real Task requesting the same key with a different type fails without changing fields or values', 'T2 remains waiting in its original Run through both ensure and conflict, then writes its original field'], limits: ['writing the newly returned field is not asserted by this scenario'] },
    concurrency: { status: 'passed', overlapStartedAt, t1CompletedAt, waitingRunId: t2WaitingAfter.run.runId, completedRunId: t1.task.runId, waitingStateBefore: t2WaitingBefore.run.status, waitingStateAfter: t2WaitingAfter.run.status },
    remaining: ['Sheets structure/value phases require authorized live resources', 'Excel source byte preservation belongs to separate native import/export evidence', 'Conflict and partial-success combinations remain separate evidence'],
  }
}

async function main() {
  const options = projectSmokeOptions(process.argv.slice(2))
  assert.ok(options.executable && options['runtime-kernel'] && options['output-dir'], 'requires --executable, --runtime-kernel and --output-dir')
  const root = resolve(import.meta.dirname, '..')
  await assertOutsideHistory(join(root, 'docs'), options['output-dir'])
  const executableSha256 = createHash('sha256').update(await readFile(options.executable)).digest('hex')
  const directory = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm9-business-')))
  const token = randomUUID()
  const report = { status: 'failed', platform: process.platform, arch: process.arch, packaged: true, startedAt: new Date().toISOString(), executableSha256 }
  let child, failure
  try {
    const version = await installRuntimeKernel(options['runtime-kernel'], directory)
    child = spawn(resolve(options.executable), ['--instance-id', randomUUID(), '--data-dir', directory, '--port', '0'], { cwd: root, env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token }, stdio: ['ignore', 'pipe', 'inherit'] })
    const ready = await waitForReady(child, 60_000)
    Object.assign(report, await checkBusinessCombinations(`http://127.0.0.1:${ready.port}`, token, version), { status: 'passed' })
  } catch (error) {
    report.error = String(error.stack ?? error)
    failure = error
  } finally {
    try {
      await stop(child)
      await rm(directory, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 })
      report.cleanup = 'passed'
    } catch (error) {
      report.cleanup = { status: 'failed', error: String(error.stack ?? error), retainedDirectory: directory }
      report.status = 'failed'
      failure ??= error
    }
    await mkdir(options['output-dir'], { recursive: true })
    await writeFile(join(options['output-dir'], 'business-combinations.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify(report, null, 2))
  }
  if (failure) throw failure
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main()
